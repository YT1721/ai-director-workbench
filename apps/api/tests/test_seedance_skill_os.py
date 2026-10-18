from __future__ import annotations

import json

import pytest
from sqlmodel import Session, select

from app.models import DirectorProjectState, StoryboardShotVersion, VideoUnit, VpBlock
from tests.test_workbench import build_client, create_project


PINNED_COMMIT = "57d01dc66f93ecb03c2475be5f22dc416d9b701d"
IMAGE_STYLE_LOCK = "IMAGE-STYLE-LOCK：白底或浅灰底高信息密度导演故事板说明板"


@pytest.fixture
def client(tmp_path):
    with build_client(tmp_path) as running_client:
        yield running_client


def _precision_items() -> list[dict]:
    items = [
        {"number": index, "title": f"第 {index} 项", "content": f"导演视频包第 {index} 项"}
        for index in range(1, 19)
    ]
    items[3]["content"] = "镜头沿人物视线缓慢推进，保持身份、轴线和白底故事板构图。"
    items[4]["content"] = [
        {"time_range": "0.0s-1.0s", "description": "建立人物与空间关系"},
        {"time_range": "1.0s-3.0s", "description": "推进主体动作与情绪"},
        {"time_range": "3.0s-5.0s", "description": "停在可续接的真实尾帧"},
    ]
    return items


def _lineage(project: dict) -> tuple[dict, dict, dict]:
    episode = project["episodes"][0]
    scene = episode["scenes"][0]
    shot = scene["shots"][0]
    return episode, scene, shot


def _unit_payload(scene: dict, shot: dict, unit_index: int = 1, **overrides) -> dict:
    payload = {
        "scene_id": scene["id"],
        "shot_id": shot["id"],
        "unit_index": unit_index,
        "unit_type": "standalone",
        "duration_seconds": 5,
        "intended_start_state": {"pose": "standing"},
        "intended_end_state": {"pose": "turning"},
        "continuity_handoff": {"tail_frame": "人物转身后停住"},
        "references": [],
    }
    payload.update(overrides)
    return payload


def _create_unit(client, project: dict, unit_index: int = 1, **overrides) -> dict:
    _, scene, shot = _lineage(project)
    response = client.post(
        f"/api/projects/{project['id']}/video-units",
        json=_unit_payload(scene, shot, unit_index, **overrides),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _seed_vp_block(
    client,
    shot_id: str,
    unit_id: str,
    items: list[dict] | None = None,
) -> VpBlock:
    precision_items = items or _precision_items()
    time_ranges = [entry["time_range"] for entry in precision_items[4]["content"]]
    with Session(client.app.state.database_engine) as session:
        block = VpBlock(
            shot_id=shot_id,
            version_number=1,
            package_stage="final_execution",
            precision_json=json.dumps(precision_items, ensure_ascii=False),
            prompt="导演完整提示词",
            prompt_copy="导演完整提示词",
            negative_prompt="不得改脸，不得破坏轴线",
            provider_profile_id="seedance-skill-os-test",
        )
        session.add(block)
        session.flush()
        storyboard = StoryboardShotVersion(
            shot_id=shot_id,
            version_number=1,
            image_path="05_video_prompts/storyboards/test.png",
            vp_basis_block_id=block.id,
            storyboard_grid=len(time_ranges),
            timeline_nodes_json=json.dumps(
                [{"time_range": value, "description": f"节点 {index}"} for index, value in enumerate(time_ranges, 1)],
                ensure_ascii=False,
            ),
            storyboard_cells_json=json.dumps(
                [
                    {
                        "cell_index": index,
                        "shot_id": shot_id,
                        "prompt_time_range": value,
                        "action_note": f"动作节点 {index}",
                    }
                    for index, value in enumerate(time_ranges, 1)
                ],
                ensure_ascii=False,
            ),
            status="confirmed",
        )
        session.add(storyboard)
        session.flush()
        block.storyboard_version_id = storyboard.id
        unit = session.get(VideoUnit, unit_id)
        assert unit is not None
        unit.storyboard_version_id = storyboard.id
        unit.prompt_time_ranges_json = json.dumps(time_ranges, ensure_ascii=False)
        session.add(unit)
        session.add(block)
        session.commit()
        session.refresh(block)
        session.expunge(block)
        return block


def test_skill_status_is_pinned_and_vendorized(client):
    response = client.get("/api/seedance-skill-os/status")

    assert response.status_code == 200
    status = response.json()
    assert status["installed"] is True
    assert status["pinned_commit"] == PINNED_COMMIT
    assert status["license_present"] is True
    assert status["module_count"] > 0


def test_video_unit_workspace_exposes_production_contract(client):
    project = create_project(client)
    unit = _create_unit(client, project)
    block = _seed_vp_block(client, unit["shot_id"], unit["id"])

    response = client.get(f"/api/projects/{project['id']}/video-units/workspace")

    assert response.status_code == 200, response.text
    workspace = response.json()
    assert workspace["project"]["project_code"] == project["project_code"]
    assert workspace["limits"] == {
        "max_video_unit_seconds": 15,
        "max_extension_depth": 2,
        "provider_submission_requires_confirmation": True,
    }
    assert len(workspace["candidates"][0]["precision_18"]) == 18
    assert workspace["video_units"][0]["vp_block_id"] == block.id
    assert workspace["video_units"][0]["prompt_time_ranges"] == [
        "0.0s-1.0s",
        "1.0s-3.0s",
        "3.0s-5.0s",
    ]


def test_video_unit_never_exceeds_fifteen_seconds_and_continuation_needs_source(client):
    project = create_project(client)
    _, scene, shot = _lineage(project)

    too_long = client.post(
        f"/api/projects/{project['id']}/video-units",
        json=_unit_payload(scene, shot, duration_seconds=15.1),
    )
    assert too_long.status_code == 422

    missing_source = client.post(
        f"/api/projects/{project['id']}/video-units",
        json=_unit_payload(scene, shot, unit_type="continuation"),
    )
    assert missing_source.status_code == 422

    maximum = _create_unit(client, project, duration_seconds=15)
    assert maximum["duration_seconds"] == 15


def test_rejected_take_cannot_be_continuation_source(client):
    project = create_project(client)
    unit = _create_unit(client, project)

    rejected = client.post(
        f"/api/video-units/{unit['id']}/take-reviews",
        json={
            "status": "rejected",
            "rejection_reasons": ["主体身份漂移"],
            "review_notes": "不能用于续拍",
        },
    )
    assert rejected.status_code == 200

    continuation = client.post(
        f"/api/projects/{project['id']}/video-units",
        json=_unit_payload(
            _lineage(project)[1],
            _lineage(project)[2],
            unit_index=2,
            unit_type="continuation",
            source_video_unit_id=unit["id"],
        ),
    )
    assert continuation.status_code == 409
    assert "真实验收记录" in continuation.json()["detail"]


def test_accepted_take_requires_observed_end_state_and_extension_depth_reanchors(client):
    project = create_project(client)
    root = _create_unit(client, project)

    missing_end = client.post(
        f"/api/video-units/{root['id']}/take-reviews",
        json={"status": "accepted", "observed_end_state": {}},
    )
    assert missing_end.status_code == 422

    previous = root
    for unit_index in (2, 3):
        accepted = client.post(
            f"/api/video-units/{previous['id']}/take-reviews",
            json={
                "status": "accepted",
                "observed_end_state": {
                    "characters": {"lead": {"pose": f"pose-{unit_index}"}},
                    "environment": {"light": "continuous"},
                    "objects": {"letter": "held"},
                },
            },
        )
        assert accepted.status_code == 200, accepted.text
        previous = _create_unit(
            client,
            project,
            unit_index=unit_index,
            unit_type="continuation",
            source_video_unit_id=previous["id"],
            intended_start_state={},
        )
        assert previous["extension_depth"] == unit_index - 1

    accepted = client.post(
        f"/api/video-units/{previous['id']}/take-reviews",
        json={
            "status": "accepted",
            "observed_end_state": {"characters": {"lead": {"pose": "final"}}},
        },
    )
    assert accepted.status_code == 200

    blocked = client.post(
        f"/api/projects/{project['id']}/video-units",
        json=_unit_payload(
            _lineage(project)[1],
            _lineage(project)[2],
            unit_index=4,
            unit_type="continuation",
            source_video_unit_id=previous["id"],
            intended_start_state={},
        ),
    )
    assert blocked.status_code == 409
    assert "重新锚定" in blocked.json()["detail"]

    with Session(client.app.state.database_engine) as session:
        state = session.exec(
            select(DirectorProjectState).where(DirectorProjectState.project_id == project["id"])
        ).first()
        assert state is not None
        accepted_ids = json.loads(state.accepted_take_ids_json)
        assert len(accepted_ids) == 3
        assert json.loads(state.character_state_json)["lead"]["pose"] == "final"
        completed = set(json.loads(state.completed_video_unit_ids_json))
        reserved = set(json.loads(state.reserved_video_unit_ids_json))
        current = {state.current_video_unit_id} if state.current_video_unit_id else set()
        assert completed.isdisjoint(reserved)
        assert completed.isdisjoint(current)
        assert reserved.isdisjoint(current)


def test_prompt_compiler_preserves_vp18_style_lock_reference_roles_and_one_to_one(client):
    project = create_project(client)
    _, _, shot = _lineage(project)
    unit = _create_unit(
        client,
        project,
        references=[{
            "reference_type": "character_master",
            "reference_id": "CH01-V01",
            "role": "identity",
            "protected_elements": ["脸型", "年龄", "体型"],
            "forbidden_transfer": ["服装纹样不得迁移到场景"],
        }],
    )
    allocation = json.loads(unit["allocation_json"])
    assert {
        "already_happened",
        "this_unit_only",
        "reserved_for_later",
        "primary_spend",
        "secondary_spend",
        "economized_elements",
        "split_recommendation",
    } <= allocation.keys()
    block = _seed_vp_block(client, shot["id"], unit["id"])

    compiled = client.post(
        f"/api/video-units/{unit['id']}/compile/{block.id}",
        json={
            "vp_precision_18": _precision_items(),
            "additional_constraints": [IMAGE_STYLE_LOCK, "AXIS-CONTINUITY-LOCK"],
        },
    )
    assert compiled.status_code == 200, compiled.text
    result = compiled.json()
    assert not result["vp_prompt_copy"].lstrip().startswith("{")
    assert "第 1 项" not in result["vp_prompt_copy"]
    assert IMAGE_STYLE_LOCK in result["vp_prompt_copy"]
    assert "AXIS-CONTINUITY-LOCK" in result["preserved_constraints"]
    assert result["reference_tag_map"][0]["forbidden_transfer"] == ["服装纹样不得迁移到场景"]

    with Session(client.app.state.database_engine) as session:
        stored = session.get(VpBlock, block.id)
        assert stored.video_unit_id == unit["id"]
        assert len(json.loads(stored.precision_json)) == 18
        assert stored.vp_prompt_full
        assert stored.prompt_copy == result["vp_prompt_copy"]

    second = _create_unit(client, project, unit_index=2)
    duplicate = client.post(
        f"/api/video-units/{second['id']}/compile/{block.id}",
        json={"vp_precision_18": _precision_items(), "additional_constraints": []},
    )
    assert duplicate.status_code == 409


def test_surface_profile_labels_and_constraints_reach_compiled_prompt(client):
    project = create_project(client)
    _, _, shot = _lineage(project)
    profile_response = client.post(
        f"/api/projects/{project['id']}/surface-profiles",
        json={
            "name": "慧梦 Seedance 生产面",
            "provider_name": "慧梦",
            "model_id": "seedance-2.0-fast",
            "prompt_budget": 2400,
            "reference_tag_convention": "@素材{index}",
            "supported_inputs": ["text", "image"],
            "supported_modes": ["text_to_video", "image_to_video"],
            "known_constraints": ["单条不超过15秒", "禁止身份漂移"],
        },
    )
    assert profile_response.status_code == 200, profile_response.text
    profile = profile_response.json()
    unit = _create_unit(
        client,
        project,
        surface_profile_id=profile["id"],
        references=[{
            "reference_type": "character_master",
            "reference_id": "CH01-V01",
            "role": "identity",
            "forbidden_transfer": ["服装纹样不得迁移到场景"],
        }],
    )
    block = _seed_vp_block(client, shot["id"], unit["id"])

    response = client.post(
        f"/api/video-units/{unit['id']}/compile/{block.id}",
        json={
            "vp_precision_18": _precision_items(),
            "surface_profile_id": profile["id"],
            "additional_constraints": [IMAGE_STYLE_LOCK],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert "慧梦" in result["vp_prompt_copy"]
    assert "seedance-2.0-fast" in result["vp_prompt_copy"]
    assert result["reference_tag_map"][0]["tag"] == "@素材1"
    assert result["reference_tag_map"][0]["forbidden_transfer"] == ["服装纹样不得迁移到场景"]
    assert result["prompt_budget_report"]["provider_name"] == "慧梦"
    assert result["prompt_budget_report"]["model_id"] == "seedance-2.0-fast"
    assert result["prompt_budget_report"]["prompt_budget"] == 2400
    assert result["prompt_budget_report"]["supported_modes"] == ["text_to_video", "image_to_video"]


def test_invalid_vp_precision_18_is_rejected(client):
    project = create_project(client)
    _, _, shot = _lineage(project)
    unit = _create_unit(client, project)
    block = _seed_vp_block(client, shot["id"], unit["id"], _precision_items()[:-1])

    response = client.post(
        f"/api/video-units/{unit['id']}/compile/{block.id}",
        json={"vp_precision_18": _precision_items()[:-1], "additional_constraints": []},
    )
    assert response.status_code == 422
    assert "18" in response.json()["detail"]


def test_storyboard_video_unit_and_vp_timeline_must_match(client):
    project = create_project(client)
    _, _, shot = _lineage(project)
    unit = _create_unit(client, project)
    block = _seed_vp_block(client, shot["id"], unit["id"])

    with Session(client.app.state.database_engine) as session:
        stored_unit = session.get(VideoUnit, unit["id"])
        assert stored_unit is not None
        stored_unit.prompt_time_ranges_json = json.dumps(["0s-2s", "2s-5s"])
        session.add(stored_unit)
        session.commit()

    response = client.post(
        f"/api/video-units/{unit['id']}/compile/{block.id}",
        json={"vp_precision_18": _precision_items(), "additional_constraints": []},
    )
    assert response.status_code == 409
    assert "时间段" in response.json()["detail"]


def test_mock_runtime_entry_does_not_exist(client):
    paths = [route.path.lower() for route in client.app.routes]
    assert not [path for path in paths if "mock" in path]
