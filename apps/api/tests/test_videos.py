from __future__ import annotations

from dataclasses import replace
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from tests.test_assets import _png_bytes, create_character
from tests.test_storyboards import storyboard_payload
from tests.test_system import SYSTEM_PROMPT_FILENAME, build_settings
from tests.test_workbench import build_client, create_project
from app.main import create_app
from app.models.assets import (
    AssetRequirement,
    CharacterMasterVersion,
    CostumeVersion,
    PropAsset,
    PropAssetVersion,
    SceneAssetVersion,
    ScenePropBinding,
)
from app.models import AiTextRun, Character, RequestCacheRecord, SceneCharacterBinding, Shot
from app.models.videos import BatchVideoTask, ProviderRun, VideoProviderProfile, VideoResultVersion, VpBlock, VpGenerationJob
from app.providers.jimeng_cli import JimengCliResult, parse_multimodal2video_help
from app.providers.huimeng import SeedanceHuimengProvider
from app.providers.text import TextSummaryResult
from app.services.video_constraints import recommend_video_duration
from app.services.videos import _character_relevance_score, _shot_character_reference_ids


def build_live_client(
    tmp_path: Path,
    *,
    max_tasks: int = 1,
    api_key: str = "hm-test-key",
    supervisor_enabled: bool = False,
) -> TestClient:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        provider_mode="huimeng_live",
        max_video_tasks_per_batch=max_tasks,
        enable_real_seedance=True,
        huimengi_api_key=api_key,
        huimengi_base_url="https://api.huimengi.com",
        huimengi_video_base_url="https://api.huimengi.com",
        huimengi_video_model="seedance-2.0-fast",
        huimengi_model_id="seedance-2.0-fast",
        video_task_supervisor_enabled=supervisor_enabled,
        content_task_supervisor_enabled=False,
    )
    return TestClient(create_app(settings))


def _write_test_png(client: TestClient, project_code: str, asset_path: str) -> None:
    target = client.app.state.settings.projects_root / project_code / asset_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_png_bytes())


def _precision_items(duration_seconds: int = 6) -> list[dict]:
    items = [
        {"number": index, "title": f"第 {index} 项", "content": f"真实 AI 视频提示词第 {index} 项"}
        for index in range(1, 19)
    ]
    items[3]["content"] = "真实 AI 完整视频提示词；不得改脸，保持黑白故事板和轴线连续。"
    items[4]["content"] = [
        {"time_range": "0.0s-1.0s", "description": "建立空间与人物姿态"},
        {"time_range": f"1.0s-{duration_seconds - 1:.1f}s", "description": "主体动作推进"},
        {"time_range": f"{duration_seconds - 1:.1f}s-{duration_seconds:.1f}s", "description": "收束到截尾帧"},
    ]
    return items


def _seed_vp_block(
    client: TestClient,
    shot_id: str,
    scene_version_id: str,
    master_id: str,
    costume_version_id: str,
    package_stage: str,
    storyboard_version_id: str | None = None,
) -> dict:
    with Session(client.app.state.database_engine) as session:
        version_number = len(session.exec(select(VpBlock).where(VpBlock.shot_id == shot_id)).all()) + 1
        shot = session.get(Shot, shot_id)
        duration_seconds, _ = recommend_video_duration(shot.name if shot else "")
        block = VpBlock(
            shot_id=shot_id,
            version_number=version_number,
            has_character=True,
            character_master_version_id=master_id,
            costume_version_id=costume_version_id,
            scene_asset_version_id=scene_version_id,
            storyboard_version_id=storyboard_version_id,
            package_stage=package_stage,
            precision_json=json.dumps(_precision_items(duration_seconds), ensure_ascii=False),
            prompt_copy="真实 AI 完整视频提示词；不得改脸，保持黑白故事板和轴线连续。",
            prompt="真实 AI 完整视频提示词；不得改脸，保持黑白故事板和轴线连续。",
            negative_prompt="不要彩色，不要破坏轴线，不要改变人物身份。",
            duration_seconds=duration_seconds,
            provider_profile_id="huimeng_live",
        )
        session.add(block)
        session.commit()
        session.refresh(block)
        return {"id": block.id, "version_number": block.version_number}


def _seed_ready_assets(client: TestClient, project: dict, scene_id: str) -> tuple[dict, dict, dict]:
    project_code = project["project_code"]
    character = create_character(client, project["id"])
    master_path = "02_characters/masters/CH01/CH01_master_real_test.png"
    _write_test_png(client, project_code, master_path)
    with Session(client.app.state.database_engine) as session:
        master = CharacterMasterVersion(
            character_id=character["id"],
            version_number=1,
            asset_path=master_path,
            status="confirmed_current",
        )
        session.add(master)
        session.commit()
        session.refresh(master)
        master_id = master.id

    workspace = client.post(
        f"/api/characters/{character['id']}/costumes",
        json={"usage_context": "常服", "description": "玄色"},
    ).json()
    costume = workspace["characters"][0]["costumes"][0]
    costume_path = "02_characters/costumes/CH01/C01/CH01_C01_real_test.png"
    _write_test_png(client, project_code, costume_path)
    with Session(client.app.state.database_engine) as session:
        costume_version = CostumeVersion(
            costume_id=costume["id"],
            character_master_version_id=master_id,
            version_number=1,
            asset_path=costume_path,
            status="confirmed_current",
        )
        session.add(costume_version)
        session.commit()
        session.refresh(costume_version)
        costume_version_id = costume_version.id

    workspace = client.post(
        f"/api/scenes/{scene_id}/assets",
        json={"description": "宫殿", "spatial_layout": "左右对峙"},
    ).json()
    scene_asset = workspace["scene_assets"][0]
    scene_path = f"03_scenes/{scene_asset['scope_code']}/scene_asset_real_test.png"
    _write_test_png(client, project_code, scene_path)
    with Session(client.app.state.database_engine) as session:
        scene_version = SceneAssetVersion(
            scene_asset_id=scene_asset["id"],
            version_number=1,
            asset_path=scene_path,
            status="confirmed_current",
        )
        session.add(scene_version)
        session.commit()
        session.refresh(scene_version)
        scene_version_id = scene_version.id

    client.post(
        f"/api/scenes/{scene_id}/bindings",
        json={
            "character_id": character["id"],
            "character_master_version_id": master_id,
            "costume_version_id": costume_version_id,
            "scene_state": "",
            "hair_change_reason": "",
        },
    )
    return {"id": master_id}, {"id": costume_version_id}, {"id": scene_version_id}


def ready_three_shot_project(client):
    project = create_project(client)
    project_id = project["id"]
    scene = project["episodes"][0]["scenes"][0]
    scene_id = scene["id"]
    client.post(f"/api/scenes/{scene_id}/shots")
    detail = client.post(f"/api/scenes/{scene_id}/shots").json()
    shots = detail["episodes"][0]["scenes"][0]["shots"]
    master, costume_version, scene_version = _seed_ready_assets(client, project, scene_id)
    for index, shot in enumerate(shots):
        draft = _seed_vp_block(client, shot["id"], scene_version["id"], master["id"], costume_version["id"], "director_draft")
        payload = storyboard_payload(); payload["camera_point"] = f"CAM0{index + 1}"
        workspace = client.post(f"/api/shots/{shot['id']}/storyboard-versions", json=payload).json()
        version = next(item for item in workspace["scenes"][0]["shots"] if item["id"] == shot["id"])["versions"][0]
        client.post(f"/api/storyboard-versions/{version['id']}/confirm")
        vp = _seed_vp_block(client, shot["id"], scene_version["id"], master["id"], costume_version["id"], "final_execution", version["id"])
        client.post(f"/api/vp-blocks/{vp['id']}/confirm")
    return project, scene_id


def test_reference_binding_uses_current_locked_character_assets_when_vp_ids_are_missing(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        _, scene_id = ready_three_shot_project(client)
        with Session(client.app.state.database_engine) as session:
            shots = session.exec(
                select(Shot).where(Shot.scene_id == scene_id).order_by(Shot.shot_code)
            ).all()
            binding = session.exec(
                select(SceneCharacterBinding).where(SceneCharacterBinding.scene_id == scene_id)
            ).one()
            character = session.get(Character, binding.character_id)
            old_master = session.get(CharacterMasterVersion, binding.character_master_version_id)
            old_costume = session.get(CostumeVersion, binding.costume_version_id)
            assert character and old_master and old_costume

            character.name = "儿童骑手"
            old_master.status = "history"
            old_costume.status = "history"
            current_master = CharacterMasterVersion(
                character_id=character.id,
                version_number=2,
                asset_path="02_characters/masters/CH01/CH01_master_locked_v2.png",
                status="locked",
            )
            session.add(current_master)
            session.commit()
            session.refresh(current_master)
            current_costume = CostumeVersion(
                costume_id=old_costume.costume_id,
                character_master_version_id=current_master.id,
                version_number=2,
                asset_path="02_characters/costumes/CH01/C01/CH01_C01_locked_v2.png",
                status="locked",
            )
            session.add(current_costume)

            first_block = session.exec(
                select(VpBlock).where(VpBlock.shot_id == shots[0].id).order_by(VpBlock.version_number.desc())
            ).first()
            continuity_block = session.exec(
                select(VpBlock).where(VpBlock.shot_id == shots[1].id).order_by(VpBlock.version_number.desc())
            ).first()
            assert first_block and continuity_block
            for block in (first_block, continuity_block):
                block.has_character = False
                block.character_master_version_id = None
                block.costume_version_id = None
                session.add(block)
            shots[0].name = "儿童骑手准备起步"
            shots[1].name = "骑手完成第二次尝试并成功通过"
            session.add(shots[0])
            session.add(shots[1])
            session.commit()

            direct_ids = _shot_character_reference_ids(session, shots[0], first_block)
            continuity_ids = _shot_character_reference_ids(session, shots[1], continuity_block)

        assert direct_ids == [current_master.id, current_costume.id]
        assert continuity_ids == [current_master.id, current_costume.id]


def test_reference_binding_uses_locked_character_master_when_costume_is_text_only(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project, scene_id = ready_three_shot_project(client)
        with Session(client.app.state.database_engine) as session:
            shots = session.exec(
                select(Shot).where(Shot.scene_id == scene_id).order_by(Shot.shot_code)
            ).all()
            binding = session.exec(
                select(SceneCharacterBinding).where(SceneCharacterBinding.scene_id == scene_id)
            ).one()
            character = session.get(Character, binding.character_id)
            current_master = session.get(CharacterMasterVersion, binding.character_master_version_id)
            assert character and current_master

            character.name = "儿童骑手"
            session.delete(binding)
            session.add(AssetRequirement(
                project_id=project["id"],
                asset_type="character",
                name=character.name,
                reference_mode="visual",
                scene_ids_json=json.dumps([scene_id]),
                target_id=character.id,
                status="bound",
            ))

            first_block = session.exec(
                select(VpBlock).where(VpBlock.shot_id == shots[0].id).order_by(VpBlock.version_number.desc())
            ).first()
            continuity_block = session.exec(
                select(VpBlock).where(VpBlock.shot_id == shots[1].id).order_by(VpBlock.version_number.desc())
            ).first()
            assert first_block and continuity_block
            for block in (first_block, continuity_block):
                block.has_character = False
                block.character_master_version_id = None
                block.costume_version_id = None
                session.add(block)
            shots[0].name = "儿童骑手准备起步"
            shots[1].name = "骑手完成第二次尝试并成功通过"
            session.add(shots[0])
            session.add(shots[1])
            session.commit()

            direct_ids = _shot_character_reference_ids(session, shots[0], first_block)
            continuity_ids = _shot_character_reference_ids(session, shots[1], continuity_block)

        assert direct_ids == [current_master.id]
        assert continuity_ids == [current_master.id]


def test_adult_coach_does_not_match_adult_rider_asset() -> None:
    adult_rider = Character(
        project_id="project-1",
        character_code="CH06",
        name="成人骑手",
    )

    assert _character_relevance_score(adult_rider, "一名成人教练在儿童右后方陪走") == 0
    assert _character_relevance_score(adult_rider, "成人骑手完成稳定收束动作") > 0


def generic_profile_payload():
    return {
        "display_name": "准备中的聚合平台",
        "base_url": "https://example.invalid",
        "create_task_path": "/tasks",
        "get_task_path_template": "/tasks/{id}",
        "auth_env_key_name": "SEEDANCE_AGGREGATOR_API_KEY",
        "config": {
            "documentation_url": "https://example.invalid/docs",
            "price_source_url": "https://example.invalid/pricing",
            "model_mapping": {"seedance-2.0": "provider-seedance-model"},
            "request_field_mapping": {
                "prompt": "prompt_text",
                "duration_seconds": "duration",
                "resolution": "resolution",
                "aspect_ratio": "ratio",
                "reference_images": "images",
            },
            "response_field_mapping": {
                "task_id": "id",
                "status": "status",
                "video_url": "video_url",
                "error_message": "error",
            },
        },
        "capabilities": {
            "generation_modes": ["multimodal_reference"],
            "supported_durations": list(range(1, 16)),
            "supported_resolutions": ["720p"],
            "supported_aspect_ratios": ["16:9"],
            "supports_reference_images": True,
            "max_reference_images": 4,
        },
        "price_configs": [{"price_value": 1.5, "billing_unit": "per_task", "currency": "CNY"}],
    }


def _vp_ai_json(director_tech_plus: dict | None = None) -> str:
    items = []
    titles = [
        "镜头编号 / 时长 / 画幅 / 目标模型",
        "镜头任务 / 导演意图",
        "输入参考资产",
        "可复制完整视频提示词",
        "分时段镜头描述",
        "景别",
        "机位",
        "运镜",
        "构图",
        "主体动作",
        "微表情 / 物体状态 / 环境动态",
        "光线 / 氛围",
        "音效说明",
        "轴线与空间连续性约束",
        "强约束",
        "负面约束",
        "截尾帧",
        "与上一镜 / 下一镜衔接",
    ]
    for index, title in enumerate(titles, start=1):
        content = "完整视频提示词：女孩推门进入雨夜宫殿，镜头稳定推进，保持人物身份和轴线连续。" if index == 4 else f"AI 生成第 {index} 项内容"
        items.append({"number": index, "title": title, "content": content})
    import json
    payload = {"vp_precision_18": items}
    if director_tech_plus is not None:
        payload["director_tech_plus"] = director_tech_plus
    return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"


def test_local_rule_vp_block_endpoint_is_disabled(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        shot = project["episodes"][0]["scenes"][0]["shots"][0]
        response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks",
            json={"has_character": False, "package_stage": "director_draft"},
        )

    assert response.status_code == 410
    assert "本地规则视频提示词已停用" in response.json()["detail"]


def test_ai_vp_block_writes_precision_18_version(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )
    calls = []

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            calls.append((instructions, input_text))
            return TextSummaryResult(_vp_ai_json(), input_tokens=80, output_tokens=120)

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频包必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        project_id = project["id"]
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        _seed_ready_assets(client, project, scene["id"])
        response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": True, "package_stage": "director_draft"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )

    assert response.status_code == 201
    version = response.json()["scenes"][0]["shots"][0]["versions"][0]
    shot_view = response.json()["scenes"][0]["shots"][0]
    assert version["package_stage"] == "director_draft"
    assert version["duration_seconds"] == 6
    assert shot_view["recommended_duration_seconds"] == 6
    assert "拆分 Video Unit" in shot_view["duration_reason"]
    assert len(version["precision_items"]) == 18
    assert version["prompt_copy"].startswith("完整视频提示词")
    assert version["precision_items"][3]["content"] == version["prompt_copy"]
    assert "TEST_SYSTEM_RULES" in calls[0][0]
    assert "工作台现有上下文" in calls[0][1]
    assert "资产状态" in calls[0][1]
    assert "宫殿" in calls[0][1]
    assert "常服" in calls[0][1]
    assert "故事板与分镜提示词状态" in calls[0][1]


def test_video_package_normalizes_string_detail_shot_candidates(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES",
        encoding="utf-8",
    )
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="deepseek-v4.1-flash",
    )

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(
                _vp_ai_json({
                    "detail_shot_candidates": "灯笼流苏特写｜福字贴纸反光特写｜红纸屑飘动特写",
                }),
                input_tokens=100,
                output_tokens=5000,
            )

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频包必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    app = create_app(settings)
    with TestClient(app) as client:
        project = create_project(client)
        shot = project["episodes"][0]["scenes"][0]["shots"][0]
        created = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": False, "package_stage": "director_draft"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )
        assert created.status_code == 201
        version = created.json()["scenes"][0]["shots"][0]["versions"][0]
        assert version["detail_shot_candidates"] == ["灯笼流苏特写", "福字贴纸反光特写", "红纸屑飘动特写"]

        with Session(app.state.database_engine) as session:
            block = session.exec(select(VpBlock).where(VpBlock.shot_id == shot["id"])).one()
            assert json.loads(block.detail_shot_candidates_json) == version["detail_shot_candidates"]
            block.detail_shot_candidates_json = json.dumps("旧版候选一｜旧版候选二", ensure_ascii=False)
            session.add(block)
            session.commit()

        legacy = client.get(f"/api/projects/{project['id']}/video-packages")

    assert legacy.status_code == 200
    legacy_version = legacy.json()["scenes"][0]["shots"][0]["versions"][0]
    assert legacy_version["detail_shot_candidates"] == ["旧版候选一", "旧版候选二"]


def test_storyboard_reference_prompt_does_not_require_asset_images(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(_vp_ai_json(), input_tokens=80, output_tokens=120)

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频提示词必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        shot = project["episodes"][0]["scenes"][0]["shots"][0]
        response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": True, "package_stage": "director_draft"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )

    assert response.status_code == 201
    version = response.json()["scenes"][0]["shots"][0]["versions"][0]
    assert version["package_stage"] == "director_draft"
    assert "未绑定正式场景资产" in version["asset_summary"]
    assert version["character_master_version_id"] is None
    assert version["costume_version_id"] is None


def test_assetless_final_prompt_requires_storyboard_but_not_asset_images(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES",
        encoding="utf-8",
    )
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(_vp_ai_json(), input_tokens=80, output_tokens=120)

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频提示词必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        goal_response = client.patch(
            f"/api/projects/{project['id']}/creative-goal",
            json={"creative_goal": "prompt_storyboard"},
        )
        assert goal_response.status_code == 200

        draft_response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": False, "package_stage": "director_draft"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )
        assert draft_response.status_code == 201

        storyboard_workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        storyboard_version = next(
            item for item in storyboard_workspace["scenes"][0]["shots"] if item["id"] == shot["id"]
        )["versions"][0]
        confirm_response = client.post(f"/api/storyboard-versions/{storyboard_version['id']}/confirm")
        assert confirm_response.status_code == 200

        final_response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": False, "package_stage": "final_execution"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )

    assert final_response.status_code == 201
    version = final_response.json()["scenes"][0]["shots"][0]["versions"][0]
    assert version["package_stage"] == "final_execution"
    assert len(version["precision_items"]) == 18
    assert version["storyboard_version_id"] == storyboard_version["id"]
    assert version["scene_asset_version_id"] is None
    assert version["character_master_version_id"] is None
    assert version["costume_version_id"] is None
    assert "无参考图模式：未绑定正式资产图" in version["asset_summary"]
    assert "无参考图成片提示词" in version["validation_items"]


def test_full_pipeline_final_prompt_still_requires_confirmed_assets(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES",
        encoding="utf-8",
    )
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(_vp_ai_json(), input_tokens=80, output_tokens=120)

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频提示词必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        shot = project["episodes"][0]["scenes"][0]["shots"][0]
        draft_response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": False, "package_stage": "director_draft"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )
        assert draft_response.status_code == 201
        storyboard_workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        storyboard_version = next(
            item for item in storyboard_workspace["scenes"][0]["shots"] if item["id"] == shot["id"]
        )["versions"][0]
        client.post(f"/api/storyboard-versions/{storyboard_version['id']}/confirm")
        final_response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": False, "package_stage": "final_execution"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )

    assert final_response.status_code == 409
    assert "场景资产" in final_response.json()["detail"]


def test_ai_vp_block_rejects_incomplete_precision_18_without_fallback(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(
                json.dumps({"vp_precision_18": [{"number": 4, "title": "可复制完整视频提示词", "content": "只有短提示词"}]}, ensure_ascii=False),
                input_tokens=50,
                output_tokens=20,
            )

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频包必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    app = create_app(settings)
    with TestClient(app) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        _seed_ready_assets(client, project, scene["id"])
        response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": True, "package_stage": "director_draft"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )
        with Session(app.state.database_engine) as session:
            vp_blocks = session.exec(select(VpBlock)).all()
            text_runs = session.exec(select(AiTextRun)).all()

    assert response.status_code == 422
    assert "缺少第" in response.json()["detail"]
    assert vp_blocks == []
    assert len(text_runs) == 1
    assert text_runs[0].module_type == "vp_precision_18"


def test_ai_vp_block_rejects_empty_provider_output_as_failed_run(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES",
        encoding="utf-8",
    )
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="deepseek-v4.1-flash",
    )

    class EmptyHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(
                "",
                input_tokens=16105,
                output_tokens=3200,
                reasoning_tokens=3200,
                finish_reason="length",
            )

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频包必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", EmptyHuimengProvider)
    app = create_app(settings)
    with TestClient(app) as client:
        project = create_project(client)
        shot = project["episodes"][0]["scenes"][0]["shots"][0]
        response = client.post(
            f"/api/shots/{shot['id']}/vp-blocks/ai-version",
            json={
                "vp_block": {"has_character": False, "package_stage": "director_draft"},
                "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
            },
        )
        with Session(app.state.database_engine) as session:
            vp_blocks = session.exec(select(VpBlock)).all()
            text_runs = session.exec(select(AiTextRun)).all()

    assert response.status_code == 502
    assert "输出额度" in response.json()["detail"]
    assert "不会自动重试" in response.json()["detail"]
    assert vp_blocks == []
    assert len(text_runs) == 1
    assert text_runs[0].status == "failed"
    assert text_runs[0].response_text == ""


def test_ai_vp_block_replaces_legacy_empty_success_cache(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES",
        encoding="utf-8",
    )
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="deepseek-v4.1-flash",
    )

    class EmptyHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult("", input_tokens=100, output_tokens=12000, finish_reason="length")

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频包必须走 generate")

    class ValidHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(_vp_ai_json(), input_tokens=100, output_tokens=5000, finish_reason="stop")

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("AI 视频包必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", EmptyHuimengProvider)
    app = create_app(settings)
    with TestClient(app) as client:
        project = create_project(client)
        shot = project["episodes"][0]["scenes"][0]["shots"][0]
        payload = {
            "vp_block": {"has_character": False, "package_stage": "director_draft"},
            "ai_text": {"module_type": "vp_precision_18", "confirm_live_request": True},
        }
        first = client.post(f"/api/shots/{shot['id']}/vp-blocks/ai-version", json=payload)
        assert first.status_code == 502
        with Session(app.state.database_engine) as session:
            legacy_run = session.exec(select(AiTextRun)).one()
            legacy_run.status = "completed"
            session.add(legacy_run)
            session.add(RequestCacheRecord(
                cache_key=legacy_run.cache_key,
                module_type="vp_precision_18",
                result_reference_id=legacy_run.id,
            ))
            session.commit()

        monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", ValidHuimengProvider)
        repaired = client.post(f"/api/shots/{shot['id']}/vp-blocks/ai-version", json=payload)
        with Session(app.state.database_engine) as session:
            cache = session.exec(select(RequestCacheRecord)).one()
            cached_run = session.get(AiTextRun, cache.result_reference_id)

    assert repaired.status_code == 201
    assert cached_run is not None
    assert cached_run.response_text.startswith("```json")
    assert cached_run.status == "completed"


def test_video_packages_batch_real_queue_jimeng_export_and_import(tmp_path: Path) -> None:
    with build_live_client(tmp_path, max_tasks=3) as client:
        project, scene_id = ready_three_shot_project(client)
        response = client.post(f"/api/scenes/{scene_id}/batch-video-jobs", json={"provider_profile_id": "huimeng_live"})
        assert response.status_code == 201
        job = response.json()["jobs"][0]
        assert [task["status"] for task in job["tasks"]] == ["awaiting_budget_confirm"] * 3
        assert job["tasks"][0]["canonical_request"]["model_family"] == "seedance-2.0"

        workspace = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()
        job = workspace["jobs"][0]
        assert [task["status"] for task in job["tasks"]] == ["ready"] * 3
        first = job["tasks"][0]

        workspace = client.post(f"/api/batch-video-jobs/{job['id']}/jimeng-export").json()
        zip_url = workspace["jobs"][0]["jimeng_zip_url"]
        zip_path = tmp_path / "projects" / "PRJ001" / zip_url.split("/PRJ001/")[1]
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
        assert "manifest.json" in names
        assert "SH001/storyboard_frame.png" in names
        assert "SH001/storyboard_page.png" in names
        assert "SH001/vp_prompt_full.txt" in names
        assert "SH001/vp_prompt_copy.txt" in names
        assert "SH001/vp_precision_18.json" in names
        assert "SH001/copy_card.md" in names

        imported = client.post(f"/api/batch-video-tasks/{first['id']}/import-video", files={"file": ("结果.mov", b"video", "video/quicktime")})
        assert imported.status_code == 200
        assert imported.json()["jobs"][0]["tasks"][0]["status"] == "imported"
        result = imported.json()["jobs"][0]["tasks"][0]["results"][0]

        reviewed = client.post(
            f"/api/video-result-versions/{result['id']}/review",
            json={"decision": "confirm"},
        )
        assert reviewed.status_code == 200
        reviewed_workspace = reviewed.json()
        assert reviewed_workspace["jobs"][0]["tasks"][0]["results"][0]["status"] == "confirmed"
        assert reviewed_workspace["scenes"][0]["confirmed_video_count"] == 1
        assert reviewed_workspace["scenes"][0]["shot_count"] == 3

        next_job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        )
        assert next_job.status_code == 201
        assert next_job.json()["jobs"][0]["tasks"][0]["shot_code"] == "SH002"


def test_provider_profile_validation_never_needs_real_secret(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.post("/api/video-provider-profiles", json={"display_name": "本地配置", "base_url": "https://example.invalid", "create_task_path": "/tasks", "get_task_path_template": "/tasks/{id}", "auth_env_key_name": "SEEDANCE_AGGREGATOR_API_KEY"})
        assert response.status_code == 201
        profile = response.json()
        assert "API_KEY" not in response.text or "SEEDANCE_AGGREGATOR_API_KEY" in response.text
        validated = client.post(f"/api/video-provider-profiles/{profile['id']}/validate").json()
        assert "未发送网络请求" in validated["validation_message"]


def test_generic_provider_preflight_and_request_preview_never_send_network(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project, scene_id = ready_three_shot_project(client)
        profile = client.post("/api/video-provider-profiles", json=generic_profile_payload()).json()
        preflight = client.post(f"/api/video-provider-profiles/{profile['id']}/preflight").json()
        assert preflight["documentation_url"] == "https://example.invalid/docs"
        assert preflight["secret_configured"] is False
        assert preflight["outbound_requests_enabled"] is False
        assert preflight["ready_for_live_test"] is False

        workspace = client.post(f"/api/scenes/{scene_id}/batch-video-jobs", json={"provider_profile_id": profile["id"]}).json()
        job = workspace["jobs"][0]
        assert job["estimated_cost"] == 4.5
        assert job["cost_estimate_status"] == "estimated"
        assert job["tasks"][0]["canonical_request"]["provider_profile_id"] == profile["id"]
        preview = client.post(f"/api/batch-video-tasks/{job['tasks'][0]['id']}/provider-request-preview").json()
        assert preview["mapped_request_preview"]["prompt_text"]
        assert preview["mapped_request_preview"]["model"] == "provider-seedance-model"
        assert preview["outbound_request_sent"] is False
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        removed_mock_route = client.post(f"/api/batch-video-tasks/{ready['tasks'][0]['id']}/mock-transition", json={"action": "submit"})
        assert removed_mock_route.status_code == 404


def test_workflow_check_accepts_unified_storyboards_as_confirmed(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project, scene_id = ready_three_shot_project(client)

        report = client.post(f"/api/scenes/{scene_id}/workflow-check-reports").json()["reports"][0]

    assert all("缺少已确认故事板" not in issue["title"] for issue in report["issues"])


def test_batch_provider_remap_rebuilds_pending_requests_without_touching_assets(tmp_path: Path) -> None:
    with build_live_client(tmp_path, max_tasks=3) as client:
        project, scene_id = ready_three_shot_project(client)
        packages_before = client.get(f"/api/projects/{project['id']}/video-packages").json()
        job = client.post(f"/api/scenes/{scene_id}/batch-video-jobs", json={"provider_profile_id": "huimeng_live"}).json()["jobs"][0]
        original_assets = job["tasks"][0]["canonical_request"]["assets"]
        profile = client.post("/api/video-provider-profiles", json=generic_profile_payload()).json()
        client.post(f"/api/video-provider-profiles/{profile['id']}/set-default")

        workspace = client.post(f"/api/batch-video-jobs/{job['id']}/remap-provider", json={"provider_profile_id": profile["id"]}).json()
        remapped = workspace["jobs"][0]
        assert remapped["provider_profile_id"] == profile["id"]
        assert remapped["budget_confirmed"] is False
        assert remapped["estimated_cost"] == 4.5
        assert [task["status"] for task in remapped["tasks"]] == ["awaiting_budget_confirm"] * 3
        assert remapped["tasks"][0]["canonical_request"]["provider_profile_id"] == profile["id"]
        assert remapped["tasks"][0]["canonical_request"]["assets"] == original_assets
        assert client.get(f"/api/projects/{project['id']}/video-packages").json() == packages_before

        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        task_id = ready["tasks"][0]["id"]
        with Session(client.app.state.database_engine) as session:
            task = session.get(BatchVideoTask, task_id)
            task.status = "submitted"
            task.external_task_id = "external-task-001"
            session.add(task)
            session.commit()
        blocked = client.post(f"/api/batch-video-jobs/{job['id']}/remap-provider", json={"provider_profile_id": profile["id"]})
        assert blocked.status_code == 409
        assert "尚未提交" in blocked.json()["detail"]


def test_confirming_vp_refreshes_existing_blocked_batch_task(tmp_path: Path) -> None:
    with build_live_client(tmp_path) as client:
        project, scene_id = ready_three_shot_project(client)
        packages = client.get(f"/api/projects/{project['id']}/video-packages").json()
        first_shot = packages["scenes"][0]["shots"][0]
        final = next(item for item in first_shot["versions"] if item["package_stage"] == "final_execution")
        client.post(f"/api/vp-blocks/{final['id']}/rollback")

        blocked_job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        assert blocked_job["tasks"][0]["status"] == "blocked"
        assert blocked_job["tasks"][0]["missing_items"]

        refreshed = client.post(f"/api/vp-blocks/{final['id']}/confirm").json()
        batch = client.get(f"/api/projects/{project['id']}/batch-video").json()["jobs"][0]

    assert refreshed["scenes"][0]["shots"][0]["versions"][0]["status"] == "confirmed_current"
    assert batch["budget_confirmed"] is False
    assert batch["tasks"][0]["status"] == "awaiting_budget_confirm"
    assert batch["tasks"][0]["missing_items"] == []
    assert batch["tasks"][0]["canonical_request"]["prompt"]


def test_mock_video_profile_is_disabled_in_formal_flow(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project, scene_id = ready_three_shot_project(client)
        profiles = client.get("/api/video-provider-profiles").json()
        response = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "seedance_mock"},
        )

    assert all(item["provider_type"] != "seedance_mock" for item in profiles)
    assert response.status_code == 409
    assert "开发调试视频演练已从正式流程关闭" in response.json()["detail"]


def test_generic_provider_response_preview_normalizes_nested_sample_without_side_effects(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        payload = generic_profile_payload()
        payload["config"]["response_field_mapping"] = {
            "task_id": "data.task.id",
            "status": "data.task.state",
            "video_url": "data.task.output.url",
            "error_message": "data.task.error.message",
        }
        payload["config"]["response_status_mapping"] = {"SUCCESS": "completed"}
        profile = client.post("/api/video-provider-profiles", json=payload).json()
        preview = client.post(f"/api/video-provider-profiles/{profile['id']}/response-preview", json={
            "sample_response": {
                "data": {"task": {"id": "external-001", "state": "SUCCESS", "output": {"url": "https://example.invalid/video.mp4"}, "error": {"message": ""}}},
            },
        })
        assert preview.status_code == 200
        result = preview.json()
        assert result["normalized_response"] == {
            "task_id": "external-001",
            "status": "completed",
            "video_url": "https://example.invalid/video.mp4",
            "error_message": "",
        }
        assert result["missing_items"] == []
        assert result["sample_saved"] is False
        assert result["outbound_requests_sent"] is False
        assert result["result_downloaded"] is False


def test_atlas_cloud_disabled_template_budget_and_local_previews(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        template_response = client.get("/api/video-provider-templates/atlas-cloud")
        assert template_response.status_code == 200
        template = template_response.json()
        assert template["outbound_requests_enabled"] is False
        payload = template["profile"]
        assert payload["provider_type"] == "seedance_atlas_cloud_disabled"
        assert payload["auth_env_key_name"] == "ATLASCLOUD_API_KEY"
        assert payload["price_configs"][0]["currency"] == "USD"

        profile = client.post("/api/video-provider-profiles", json=payload).json()
        validated = client.post(f"/api/video-provider-profiles/{profile['id']}/validate").json()
        assert "禁用状态 Adapter 配置完整" in validated["validation_message"]
        assert "未发送网络请求" in validated["validation_message"]

        _, scene_id = ready_three_shot_project(client)
        job = client.post(f"/api/scenes/{scene_id}/batch-video-jobs", json={"provider_profile_id": profile["id"]}).json()["jobs"][0]
        assert job["currency"] == "USD"
        assert job["estimated_cost"] == 3.483
        assert job["cost_estimate_status"] == "estimated"
        request_preview = client.post(f"/api/batch-video-tasks/{job['tasks'][0]['id']}/provider-request-preview").json()
        assert request_preview["mapped_request_preview"]["model"] == "bytedance/seedance-2.0-fast/reference-to-video"
        assert request_preview["mapped_request_preview"]["input"]["prompt"]
        assert request_preview["mapped_request_preview"]["_local_preview_only"]["outbound_request_sent"] is False
        assert "uploadMedia" in request_preview["missing_items"][0]
        assert request_preview["outbound_request_sent"] is False

        response_preview = client.post(f"/api/video-provider-profiles/{profile['id']}/response-preview", json={
            "sample_response": {
                "data": {
                    "id": "atlas-task-001",
                    "status": "succeeded",
                    "outputs": ["https://example.invalid/atlas.mp4"],
                    "error": "",
                },
            },
        }).json()
        assert response_preview["normalized_response"] == {
            "task_id": "atlas-task-001",
            "status": "completed",
            "video_url": "https://example.invalid/atlas.mp4",
            "error_message": "",
        }
        assert response_preview["missing_items"] == []


def test_huimeng_live_status_and_gates_require_confirm_and_secret(tmp_path: Path) -> None:
    with build_live_client(tmp_path, api_key="") as client:
        status = client.get("/api/video-provider-live-status").json()
        assert status["real_seedance_enabled"] is True
        assert status["huimengi_api_key_configured"] is False
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        with Session(client.app.state.database_engine) as session:
            profile = session.get(VideoProviderProfile, "huimeng_live")
            capabilities = json.loads(profile.capabilities_json)
            capabilities["supported_durations"] = [5]
            profile.capabilities_json = json.dumps(capabilities, ensure_ascii=False)
            session.add(profile)
            session.commit()
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live", "submission_channel": "jimeng"},
        ).json()["jobs"][0]
        assert job["submission_channel"] == "jimeng"
        assert job["tasks"][0]["canonical_request"]["duration_seconds"] != 5
        assert job["tasks"][0]["missing_items"] == []
        switched = client.patch(
            f"/api/batch-video-jobs/{job['id']}/submission-channel",
            json={
                "submission_channel": "huimeng",
                "huimeng_provider_profile_id": "huimeng_live",
            },
        ).json()["jobs"][0]
        assert switched["submission_channel"] == "huimeng"
        assert switched["tasks"][0]["status"] == "blocked"
        assert "配置允许时长：5 秒" in "；".join(switched["tasks"][0]["missing_items"])
        switched = client.patch(
            f"/api/batch-video-jobs/{job['id']}/submission-channel",
            json={"submission_channel": "jimeng"},
        ).json()["jobs"][0]
        assert switched["submission_channel"] == "jimeng"
        assert switched["tasks"][0]["missing_items"] == []
        assert switched["tasks"][0]["status"] == "awaiting_budget_confirm"
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        task_id = ready["tasks"][0]["id"]
        readiness = client.get(f"/api/batch-video-tasks/{task_id}/live-readiness")
        assert readiness.status_code == 200
        assert readiness.json()["ready"] is False
        assert "hm-test" not in readiness.text
        assert any(item["label"] == "慧梦 API Key" and not item["passed"] for item in readiness.json()["gate_items"])
        unconfirmed = client.post(f"/api/batch-video-tasks/{task_id}/live-submit", json={"confirm_live_request": False})
        assert unconfirmed.status_code == 409
        missing_secret = client.post(f"/api/batch-video-tasks/{task_id}/live-submit", json={"confirm_live_request": True})
        assert missing_secret.status_code == 409
        assert "HUIMENGI_API_KEY" in missing_secret.json()["detail"]


def test_huimeng_live_accepts_controlled_multi_task_queue(tmp_path: Path) -> None:
    with build_live_client(tmp_path, max_tasks=3) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(f"/api/scenes/{scene_id}/batch-video-jobs", json={"provider_profile_id": "huimeng_live"}).json()["jobs"][0]
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        assert len(ready["tasks"]) == 3
        response = client.get(f"/api/batch-video-tasks/{ready['tasks'][0]['id']}/live-readiness")
        assert response.status_code == 200
        gate = next(item for item in response.json()["gate_items"] if item["label"] == "受控批量队列")
        assert gate["passed"] is True
        assert "3 个任务" in gate["detail"]


def test_batch_launch_requires_all_reference_confirmations(tmp_path: Path) -> None:
    with build_live_client(tmp_path, max_tasks=3, supervisor_enabled=False) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget")

        blocked = client.post(
            f"/api/batch-video-jobs/{job['id']}/launch",
            json={"confirm_live_request": True},
        )
        assert blocked.status_code == 409
        assert "全能参考尚未确认" in blocked.json()["detail"]

        confirmed = client.post(f"/api/batch-video-jobs/{job['id']}/reference-bindings/confirm")
        assert confirmed.status_code == 200
        launched = client.post(
            f"/api/batch-video-jobs/{job['id']}/launch",
            json={"confirm_live_request": True},
        )
        assert launched.status_code == 202
        launched_job = launched.json()["jobs"][0]
        assert launched_job["batch_authorized"] is True
        assert launched_job["dispatch_enabled"] is True
        assert launched_job["status"] == "dispatching"
        assert all(task["external_task_id"] is None for task in launched_job["tasks"])


def test_batch_resume_ignores_preserved_result_and_launches_remaining_tasks(tmp_path: Path) -> None:
    with build_live_client(tmp_path, max_tasks=3, supervisor_enabled=False) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        preserved_id = job["tasks"][0]["id"]

        with Session(client.app.state.database_engine) as session:
            preserved = session.get(BatchVideoTask, preserved_id)
            assert preserved is not None
            preserved.status = "imported"
            preserved.external_task_id = "provider-already-saved"
            preserved.reference_bindings_fingerprint = ""
            preserved.reference_bindings_confirmed_at = None
            session.add(preserved)
            session.commit()

        confirmed = client.post(f"/api/batch-video-jobs/{job['id']}/reference-bindings/confirm")
        assert confirmed.status_code == 200, confirmed.text
        assert client.post(f"/api/batch-video-jobs/{job['id']}/confirm-cost-risk").status_code == 200
        launched = client.post(
            f"/api/batch-video-jobs/{job['id']}/launch",
            json={"confirm_live_request": True},
        )
        assert launched.status_code == 202, launched.text
        launched_job = next(item for item in launched.json()["jobs"] if item["id"] == job["id"])
        preserved_view = next(item for item in launched_job["tasks"] if item["id"] == preserved_id)
        remaining = [item for item in launched_job["tasks"] if item["id"] != preserved_id]
        assert preserved_view["status"] == "imported"
        assert preserved_view["external_task_id"] == "provider-already-saved"
        assert all(item["status"] == "ready" for item in remaining)
        assert launched_job["batch_authorized"] is True


def test_supervisor_dispatches_batch_one_task_per_cycle(tmp_path: Path, monkeypatch) -> None:
    import app.services.video_task_supervisor as supervisor_module

    submitted_ids: list[str] = []

    def fake_submit(session, task_id, settings, confirm_live_request):
        task = session.get(BatchVideoTask, task_id)
        assert task is not None
        submitted_ids.append(task_id)
        task.external_task_id = f"fake-{len(submitted_ids)}"
        task.status = "submitted"
        session.add(task)
        session.commit()
        return task_id

    monkeypatch.setattr(supervisor_module, "live_submit_task", fake_submit)
    with build_live_client(tmp_path, max_tasks=3, supervisor_enabled=False) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        references = client.post(f"/api/batch-video-jobs/{job['id']}/reference-bindings/confirm")
        assert references.status_code == 200
        budget = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget")
        assert budget.status_code == 200
        launch = client.post(
            f"/api/batch-video-jobs/{job['id']}/launch",
            json={"confirm_live_request": True},
        )
        assert launch.status_code == 202, launch.text
        launched_job = launch.json()["jobs"][0]
        assert launched_job["dispatch_enabled"] is True
        assert launched_job["batch_authorized"] is True
        assert all(task["status"] == "ready" for task in launched_job["tasks"])
        supervisor = client.app.state.video_task_supervisor
        monkeypatch.setattr(supervisor, "_process_task", lambda task_id: None)

        processed = supervisor.run_cycle()
        assert processed == 1, supervisor.status().last_error
        assert len(submitted_ids) == 1
        assert supervisor.run_cycle() == 2
        assert len(submitted_ids) == 2
        assert len(set(submitted_ids)) == 2


def test_huimeng_provider_rejects_over_limit_live_spec() -> None:
    provider = SeedanceHuimengProvider()
    template = SeedanceHuimengProvider.profile_template()
    capabilities = template["capabilities"]
    request = {
        "generation_mode": "multimodal_reference",
        "duration_seconds": 16,
        "resolution": "1080p",
        "aspect_ratio": "16:9",
        "assets": {"reference_images": []},
    }
    missing = provider.validate_request(request, capabilities)
    assert "配置允许时长" in "；".join(missing)
    assert "720p" in "；".join(missing)
    assert template["price_configs"][0]["price_status"] == "unknown"
    assert "price_value" not in template["price_configs"][0]
    assert provider.estimate_cost(request, template["price_configs"]) is None


def test_video_duration_recommendation_follows_shot_density_instead_of_fixed_five() -> None:
    simple, _ = recommend_video_duration("人物停下，抬头看向远方。")
    montage, montage_reason = recommend_video_duration("快速蒙太奇穿越泥坑、碎石和陡坡，随后切换到轮胎与骑手反应。")
    end_card, _ = recommend_video_duration("最终品牌落版，仅规划后期静态画面。")

    assert simple == 6
    assert montage == 12
    assert end_card == 4
    assert "拆分 Video Unit" in montage_reason
    assert len({simple, montage, end_card}) == 3


def test_huimeng_live_submit_poll_download_with_fake_provider(tmp_path: Path, monkeypatch) -> None:
    def fake_submit(self, base_url, api_key, request, profile_config):
        assert api_key == "hm-test-key"
        assert request["duration_seconds"] == 6
        assert request["resolution"] == "720p"
        return {"task_id": "hm-task-001", "status": "submitted", "video_url": "", "error_message": ""}, {"data": {"id": "hm-task-001", "status": "submitted"}}

    def fake_poll(self, base_url, api_key, external_task_id):
        assert external_task_id == "hm-task-001"
        return {"task_id": "hm-task-001", "status": "completed", "video_url": "https://example.invalid/hm.mp4", "error_message": ""}, {"data": {"id": "hm-task-001", "status": "completed", "video_url": "https://example.invalid/hm.mp4"}}

    def fake_download(self, video_url):
        assert video_url == "https://example.invalid/hm.mp4"
        return b"HUI-MENG-LIVE-VIDEO"

    monkeypatch.setattr(SeedanceHuimengProvider, "submit_task", fake_submit)
    monkeypatch.setattr(SeedanceHuimengProvider, "poll_task", fake_poll)
    monkeypatch.setattr(SeedanceHuimengProvider, "download_video", fake_download)

    with build_live_client(tmp_path) as client:
        providers = client.get("/api/video-provider-profiles").json()
        assert any(item["id"] == "huimeng_live" for item in providers)
        _, scene_id = ready_three_shot_project(client)
        job = client.post(f"/api/scenes/{scene_id}/batch-video-jobs", json={"provider_profile_id": "huimeng_live"}).json()["jobs"][0]
        assert len(job["tasks"]) == 1
        assert job["estimated_cost"] is None
        assert job["cost_estimate_status"] == "unknown"
        assert job["currency"] == "CREDITS"
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-cost-risk").json()["jobs"][0]
        task_id = ready["tasks"][0]["id"]
        readiness = client.get(f"/api/batch-video-tasks/{task_id}/live-readiness").json()
        assert readiness["ready"] is True
        assert readiness["provider_name"] == "慧梦 API｜Seedance 2.0 Fast 单镜实测"
        assert readiness["model_id"] == "seedance-2.0-fast"
        assert any(item["label"] == "费用风险确认" and item["passed"] for item in readiness["gate_items"])

        submitted = client.post(f"/api/batch-video-tasks/{task_id}/live-submit", json={"confirm_live_request": True})
        assert submitted.status_code == 200
        submitted_task = submitted.json()["jobs"][0]["tasks"][0]
        assert submitted_task["status"] == "submitted"
        assert submitted_task["progress_percent"] == 25
        assert submitted_task["storage_status"] == "pending"

        polled = client.post(f"/api/batch-video-tasks/{task_id}/live-poll", json={"confirm_live_request": True})
        assert polled.status_code == 200
        online_task = polled.json()["jobs"][0]["tasks"][0]
        assert online_task["status"] == "completed"
        assert online_task["progress_percent"] == 85
        assert online_task["storage_status"] == "online"
        assert online_task["remote_video_url"] == "https://example.invalid/hm.mp4"

        downloaded = client.post(f"/api/batch-video-tasks/{task_id}/live-download", json={"confirm_live_request": True})
        assert downloaded.status_code == 200
        task = downloaded.json()["jobs"][0]["tasks"][0]
        assert task["status"] == "imported"
        assert task["progress_percent"] == 100
        assert task["storage_status"] == "local"
        assert task["local_file_path"].endswith(task["result_video_path"])
        assert task["results"][0]["source"] == "huimeng_live"
        result_path = tmp_path / "projects" / "PRJ001" / task["results"][0]["video_url"].split("/PRJ001/")[1]
        assert result_path.read_bytes() == b"HUI-MENG-LIVE-VIDEO"


def test_huimeng_response_normalization_accepts_common_result_shapes() -> None:
    provider = SeedanceHuimengProvider()
    normalized = provider.normalize_response({
        "result": {
            "task_id": "hm-task-002",
            "state": "succeeded",
            "outputs": [{"url": "https://example.invalid/result.mp4"}],
        },
    })
    assert normalized["task_id"] == "hm-task-002"
    assert normalized["status"] == "completed"
    assert normalized["video_url"] == "https://example.invalid/result.mp4"


class MissingJimengRunner:
    command = "dreamina"

    def installed(self) -> bool:
        return False

    def user_credit(self) -> JimengCliResult:
        return JimengCliResult(ok=False, error="本机没有检测到 dreamina 命令。")


class FakeJimengRunner:
    command = "dreamina"

    def installed(self) -> bool:
        return True

    def user_credit(self) -> JimengCliResult:
        return JimengCliResult(ok=True, data={"account": "demo-user", "credit": "177.74 积分"}, summary="credit: 177.74")

    def submit_multimodal2video(self, **kwargs) -> JimengCliResult:
        assert kwargs["prompt"]
        assert kwargs["model_version"] == "seedance2.0mini"
        assert kwargs["video_resolution"] == "720p"
        assert kwargs["images"]
        for index in range(1, len(kwargs["images"]) + 1):
            assert f"@图片{index}" in kwargs["prompt"]
        return JimengCliResult(ok=True, data={"submit_id": "jm-submit-001", "status": "submitted"}, summary="submit_id: jm-submit-001")

    def list_task(self, submit_id: str = "", limit: int = 20) -> JimengCliResult:
        assert submit_id == "jm-submit-001"
        assert limit == 1
        return JimengCliResult(
            ok=True,
            data={"items": [{"submit_id": submit_id, "gen_status": "queued"}]},
            summary="gen_status: queued",
        )

    def query_result(self, submit_id: str, download_dir: Path | None = None) -> JimengCliResult:
        assert submit_id == "jm-submit-001"
        data = {"submit_id": submit_id, "status": "completed"}
        if download_dir is not None:
            target = download_dir / "jm-result.mp4"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"JIMENG-CLI-VIDEO")
            data["video_path"] = str(target)
        return JimengCliResult(ok=True, data=data, summary="status: completed")


class RejectedJimengRunner(FakeJimengRunner):
    def submit_multimodal2video(self, **kwargs) -> JimengCliResult:
        return JimengCliResult(
            ok=True,
            data={
                "submit_id": "jm-rejected-001",
                "gen_status": "fail",
                "fail_reason": "invalid param:video_resolution_type",
            },
            summary="gen_status: fail",
        )

    def list_task(self, submit_id: str = "", limit: int = 20) -> JimengCliResult:
        raise AssertionError("被即梦明确拒绝后不应继续伪验证任务列表")


class UploadTimeoutJimengRunner(FakeJimengRunner):
    def submit_multimodal2video(self, **kwargs) -> JimengCliResult:
        return JimengCliResult(
            ok=True,
            data={
                "submit_id": "local-attempt-001",
                "gen_status": "fail",
                "fail_reason": "ApplyImageUpload: context deadline exceeded",
            },
            summary="upload image failed before cloud task creation",
        )

    def list_task(self, submit_id: str = "", limit: int = 20) -> JimengCliResult:
        raise AssertionError("参考图上传失败后不应查询不存在的云端任务")


class TemporarilyUnavailableJimengRunner(FakeJimengRunner):
    def query_result(self, submit_id: str, download_dir: Path | None = None) -> JimengCliResult:
        return JimengCliResult(ok=False, error="即梦 CLI 暂时无法连接")


class QueueingJimengRunner(FakeJimengRunner):
    def submit_multimodal2video(self, **kwargs) -> JimengCliResult:
        assert kwargs["prompt"]
        assert kwargs["model_version"] == "seedance2.0_vip"
        assert kwargs["video_resolution"] == "720p"
        return JimengCliResult(
            ok=True,
            data={"submit_id": "jm-submit-001", "gen_status": "querying"},
            summary="submit_id: jm-submit-001",
        )

    def query_result(self, submit_id: str, download_dir: Path | None = None) -> JimengCliResult:
        return JimengCliResult(
            ok=True,
            data={
                "submit_id": submit_id,
                "gen_status": "querying",
                "queue_info": {
                    "queue_idx": 4097,
                    "queue_status": "Queueing",
                    "queue_length": 570856,
                },
            },
            summary="queue_status: Queueing",
        )


class FailedAfterQueueJimengRunner(QueueingJimengRunner):
    def query_result(self, submit_id: str, download_dir: Path | None = None) -> JimengCliResult:
        return JimengCliResult(
            ok=True,
            data={
                "submit_id": submit_id,
                "gen_status": "fail",
                "fail_reason": "generation failed: final generation failed",
                "queue_info": {
                    "queue_idx": 0,
                    "queue_status": "Finish",
                    "queue_length": 0,
                },
            },
            summary="gen_status: fail",
        )


def test_seedance_reference_manifest_uses_relevant_props_and_drops_people_from_no_character_shot(
    tmp_path: Path,
) -> None:
    with build_live_client(tmp_path) as client:
        client.get("/api/video-provider-profiles")
        project, scene_id = ready_three_shot_project(client)
        text_only_version_id = ""
        with Session(client.app.state.database_engine) as session:
            shot = session.exec(
                select(Shot).where(Shot.scene_id == scene_id).order_by(Shot.shot_code)
            ).first()
            shot.name = "不要出现人物；超低机位沿红泥车辙推进到电动越野摩托轮胎胎纹。"
            session.add(shot)
            for code, name, path in (
                ("PR01", "APOLLO RFN 电动越野摩托产品矩阵", "04_props/PR01/product.png"),
                ("PR02", "越野轮胎 / 残留湿泥车轮", "04_props/PR02/wheel.png"),
                ("PR03", "湿滑红泥 / 深车辙 / 泥水反光", "04_props/PR03/mud.png"),
            ):
                prop = PropAsset(project_id=project["id"], prop_code=code, name=name)
                session.add(prop)
                session.commit()
                session.refresh(prop)
                version = PropAssetVersion(
                    prop_asset_id=prop.id,
                    version_number=1,
                    asset_path=path,
                    status="locked",
                )
                session.add(version)
                session.commit()
                session.refresh(version)
                session.add(ScenePropBinding(
                    scene_id=scene_id,
                    prop_asset_id=prop.id,
                    prop_asset_version_id=version.id,
                ))
                if code == "PR03":
                    text_only_version_id = version.id
                    session.add(AssetRequirement(
                        project_id=project["id"],
                        asset_type="prop",
                        name=name,
                        description="普通泥水环境细节。",
                        reference_mode="text_only",
                        importance_reason="不是需要跨镜头锁定的主体或英雄产品。",
                        text_prompt="湿滑红泥、深车辙与少量泥水反光由模型自然补全。",
                        scene_ids_json=json.dumps([scene_id]),
                        target_id=prop.id,
                        status="text_ready",
                    ))
                _write_test_png(client, project["project_code"], path)
            session.commit()

        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        task = job["tasks"][0]
        bindings = task["canonical_request"]["assets"]["reference_bindings"]
        roles = [item["role"] for item in bindings]
        asset_types = [item["asset_type"] for item in bindings]
        provider_prompt = task["canonical_request"]["prompt"]

        assert "character" not in asset_types
        assert "costume" not in asset_types
        assert "product" in roles
        assert "environment_detail" in roles
        assert text_only_version_id not in [item["asset_id"] for item in bindings]
        assert "湿滑红泥、深车辙与少量泥水反光由模型自然补全" in provider_prompt
        assert task["canonical_request"]["assets"]["text_descriptions"] == [{
            "asset_type": "prop",
            "name": "湿滑红泥 / 深车辙 / 泥水反光",
            "description": "湿滑红泥、深车辙与少量泥水反光由模型自然补全。",
        }]
        assert [item["token"] for item in bindings] == [
            f"@图片{index}" for index in range(1, len(bindings) + 1)
        ]
        assert all(item["token"] in provider_prompt for item in bindings)
        assert "忽略分格线、箭头、标注文字与黑白铅笔风格" in provider_prompt


def test_jimeng_cli_status_blocks_when_command_missing(tmp_path: Path, monkeypatch) -> None:
    import app.services.videos as video_services

    monkeypatch.setattr(video_services, "JimengCliRunner", MissingJimengRunner)

    with build_client(tmp_path) as client:
        status = client.get("/api/jimeng-cli/status").json()

    assert status["installed"] is False
    assert status["ready"] is False
    assert "dreamina" in status["blocking_reason"]


def test_jimeng_cli_submit_poll_download_with_fake_runner(tmp_path: Path, monkeypatch) -> None:
    import app.services.videos as video_services

    monkeypatch.setattr(video_services, "JimengCliRunner", FakeJimengRunner)

    with build_live_client(tmp_path) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(f"/api/scenes/{scene_id}/batch-video-jobs", json={"provider_profile_id": "huimeng_live"}).json()["jobs"][0]
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        task_id = ready["tasks"][0]["id"]

        with Session(client.app.state.database_engine) as session:
            stale_task = session.get(BatchVideoTask, task_id)
            stale_task.status = "blocked"
            stale_task.missing_items_json = json.dumps(["旧任务快照：缺少成片提示词。"], ensure_ascii=False)
            session.add(stale_task)
            session.commit()
        refreshed = client.post(f"/api/batch-video-tasks/{task_id}/refresh-preflight").json()["jobs"][0]
        assert refreshed["tasks"][0]["missing_items"] == []
        assert refreshed["tasks"][0]["status"] == "awaiting_budget_confirm"
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        assert ready["tasks"][0]["status"] == "ready"

        status = client.get("/api/jimeng-cli/status").json()
        assert status["ready"] is True
        assert status["credit_summary"] == "177.74 积分"

        readiness = client.post(f"/api/batch-video-tasks/{task_id}/jimeng-cli-readiness").json()
        assert readiness["ready"] is True
        assert readiness["model_id"] == "seedance2.0_vip"
        assert "177.74" in readiness["gate_items"][1]["detail"]
        assert readiness["reference_bindings"]
        assert readiness["reference_bindings"][0]["token"] == "@图片1"
        assert "@图片1" in readiness["prompt_preview"]
        assert len(readiness["reference_candidates"]) >= 2

        original_ids = [item["asset_id"] for item in readiness["reference_bindings"]]
        manual_ids = list(reversed(original_ids))
        changed_bindings = client.patch(
            f"/api/batch-video-tasks/{task_id}/reference-bindings",
            json={"asset_ids": manual_ids},
        ).json()["jobs"][0]
        assert changed_bindings["budget_confirmed"] is False
        manual_assets = changed_bindings["tasks"][0]["canonical_request"]["assets"]
        assert manual_assets["reference_bindings_mode"] == "manual"
        assert manual_assets["reference_images"] == manual_ids
        refreshed_readiness = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-readiness"
        ).json()
        assert [item["asset_id"] for item in refreshed_readiness["reference_bindings"]] == manual_ids
        assert "@图片1" in refreshed_readiness["prompt_preview"]

        models = client.get("/api/jimeng-cli/video-models").json()
        model_ids = [item["id"] for item in models]
        assert model_ids[:5] == [
            "seedance2.0mini",
            "seedance2.0fast_vip",
            "seedance2.0_vip",
            "seedance2.0fast",
            "seedance2.0",
        ]
        assert {
            "seedance2.0mini",
            "seedance2.0fast",
            "seedance2.0",
            "seedance2.0fast_vip",
            "seedance2.0_vip",
        }.issubset(model_ids)
        changed = client.patch(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-model",
            json={"model_id": "seedance2.0mini"},
        ).json()["jobs"][0]
        assert changed["budget_confirmed"] is False
        assert changed["tasks"][0]["status"] == "awaiting_budget_confirm"
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        readiness = client.post(f"/api/batch-video-tasks/{task_id}/jimeng-cli-readiness").json()
        assert readiness["ready"] is True
        assert readiness["model_id"] == "seedance2.0mini"

        unconfirmed = client.post(f"/api/batch-video-tasks/{task_id}/jimeng-cli-submit", json={"confirm_live_request": False})
        assert unconfirmed.status_code == 409

        submitted = client.post(f"/api/batch-video-tasks/{task_id}/jimeng-cli-submit", json={"confirm_live_request": True})
        assert submitted.status_code == 200
        task = submitted.json()["jobs"][0]["tasks"][0]
        assert task["status"] == "submitted"
        assert task["external_task_id"] == "jm-submit-001"
        assert task["external_provider"] == "jimeng_cli"
        assert submitted.json()["jobs"][0]["submission_channel"] == "jimeng"
        assert task["canonical_request"]["provider_options"]["jimeng_model_version"] == "seedance2.0mini"
        locked_model = client.patch(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-model",
            json={"model_id": "seedance2.0_vip"},
        )
        assert locked_model.status_code == 409
        locked_channel = client.patch(
            f"/api/batch-video-jobs/{job['id']}/submission-channel",
            json={
                "submission_channel": "huimeng",
                "huimeng_provider_profile_id": "huimeng_live",
            },
        )
        assert locked_channel.status_code == 409
        assert client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-readiness"
        ).json()["model_id"] == "seedance2.0mini"

        polled = client.post(f"/api/batch-video-tasks/{task_id}/jimeng-cli-poll", json={"confirm_live_request": True})
        assert polled.status_code == 200
        assert polled.json()["jobs"][0]["tasks"][0]["status"] == "completed"

        downloaded = client.post(f"/api/batch-video-tasks/{task_id}/jimeng-cli-download", json={"confirm_live_request": True})
        assert downloaded.status_code == 200
        task = downloaded.json()["jobs"][0]["tasks"][0]
        assert task["status"] == "imported"
        assert task["results"][0]["source"] == "jimeng_cli"
        result_path = tmp_path / "projects" / "PRJ001" / task["results"][0]["video_url"].split("/PRJ001/")[1]
        assert result_path.read_bytes() == b"JIMENG-CLI-VIDEO"


def test_jimeng_cli_querying_with_queue_info_is_truthfully_reported_as_submitted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.services.videos as video_services

    monkeypatch.setattr(video_services, "JimengCliRunner", QueueingJimengRunner)

    with build_live_client(tmp_path) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget")
        task_id = job["tasks"][0]["id"]

        submitted = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-submit",
            json={"confirm_live_request": True},
        )
        assert submitted.status_code == 200

        polled = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-poll",
            json={"confirm_live_request": True},
        )
        assert polled.status_code == 200
        task = polled.json()["jobs"][0]["tasks"][0]
        assert task["status"] == "submitted"
        assert task["progress_percent"] == 0
        assert task["progress_label"] == "即梦云端排队中"
        assert task["provider_status"] == "querying"
        assert task["provider_queue_status"] == "Queueing"
        assert task["provider_queue_position"] == 4097
        assert task["provider_queue_length"] == 570856


def test_jimeng_cli_explicit_failure_wins_over_finished_queue_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.services.videos as video_services

    monkeypatch.setattr(video_services, "JimengCliRunner", FailedAfterQueueJimengRunner)

    with build_live_client(tmp_path) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget")
        task_id = job["tasks"][0]["id"]
        client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-submit",
            json={"confirm_live_request": True},
        )

        polled = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-poll",
            json={"confirm_live_request": True},
        )
        assert polled.status_code == 200
        task = polled.json()["jobs"][0]["tasks"][0]
        assert task["status"] == "failed"
        assert task["error_message"] == "generation failed: final generation failed"
        assert task["provider_status"] == "fail"
        assert task["provider_queue_status"] == "Finish"


def test_jimeng_cli_prepare_retry_preserves_failure_history(tmp_path: Path) -> None:
    with build_live_client(tmp_path) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        task_id = job["tasks"][0]["id"]
        shot_id = job["tasks"][0]["shot_id"]
        previous_storyboard_id = job["tasks"][0]["canonical_request"]["assets"]["reference_images"][0]
        storyboard_workspace = client.post(
            f"/api/shots/{shot_id}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        current_storyboard = next(
            item for item in storyboard_workspace["scenes"][0]["shots"] if item["id"] == shot_id
        )["versions"][0]
        client.post(f"/api/storyboard-versions/{current_storyboard['id']}/confirm")
        with Session(client.app.state.database_engine) as session:
            task = session.get(BatchVideoTask, task_id)
            task.status = "failed"
            task.external_task_id = "failed-submit-001"
            task.error_message = "invalid param:video_resolution_type"
            session.add(task)
            session.commit()

        stale_readiness = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-readiness"
        ).json()
        storyboard_gate = next(
            item for item in stale_readiness["gate_items"] if item["label"] == "正式故事板引用"
        )
        assert storyboard_gate["passed"] is False
        assert "历史故事板" in storyboard_gate["detail"]

        prepared = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-prepare-retry"
        ).json()["jobs"][0]

        assert prepared["budget_confirmed"] is False
        prepared_task = prepared["tasks"][0]
        assert prepared_task["status"] == "awaiting_budget_confirm"
        assert prepared_task["external_task_id"] is None
        assert prepared_task["retry_count"] == 1
        assert prepared_task["error_message"] == ""
        refs = prepared_task["canonical_request"]["assets"]["reference_images"]
        assert refs[0] == current_storyboard["id"]
        assert previous_storyboard_id not in refs
        assert prepared_task["storyboard_reference_status"] == "current"
        assert prepared_task["current_storyboard_url"]
        assert prepared_task["storyboard_url"] == prepared_task["current_storyboard_url"]

        refreshed_readiness = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-readiness"
        ).json()
        storyboard_gate = next(
            item for item in refreshed_readiness["gate_items"] if item["label"] == "正式故事板引用"
        )
        assert storyboard_gate["passed"] is True


def test_jimeng_cli_exit_zero_with_failed_payload_is_not_submitted(tmp_path: Path, monkeypatch) -> None:
    import app.services.videos as video_services

    monkeypatch.setattr(video_services, "JimengCliRunner", RejectedJimengRunner)
    with build_live_client(tmp_path) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        task_id = ready["tasks"][0]["id"]

        response = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-submit",
            json={"confirm_live_request": True},
        )

        assert response.status_code == 502
        with Session(client.app.state.database_engine) as session:
            task = session.get(BatchVideoTask, task_id)
            assert task.status == "failed"
            assert task.external_task_id == "jm-rejected-001"
            assert "video_resolution_type" in task.error_message


def test_jimeng_cli_upload_timeout_stays_ready_for_supervisor_retry(tmp_path: Path, monkeypatch) -> None:
    import app.services.videos as video_services

    monkeypatch.setattr(video_services, "JimengCliRunner", UploadTimeoutJimengRunner)
    with build_live_client(tmp_path) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        ready = client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget").json()["jobs"][0]
        task_id = ready["tasks"][0]["id"]

        response = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-submit",
            json={"confirm_live_request": True},
        )

        assert response.status_code == 503
        with Session(client.app.state.database_engine) as session:
            task = session.get(BatchVideoTask, task_id)
            assert task.status == "ready"
            assert task.external_task_id is None
            assert "后台将自动重新上传" in task.error_message
            run = session.exec(
                select(ProviderRun)
                .where(
                    ProviderRun.task_id == task_id,
                    ProviderRun.action == "jimeng_cli_submit_transient",
                )
            ).one()
            snapshot = json.loads(run.response_snapshot_json)
            assert snapshot["cloud_task_created"] is False
            assert snapshot["will_retry"] is True


def test_video_supervisor_recovers_after_restart_and_downloads_idempotently(tmp_path: Path, monkeypatch) -> None:
    import app.services.videos as video_services

    monkeypatch.setattr(video_services, "JimengCliRunner", FakeJimengRunner)
    settings = None
    task_id = ""
    with build_live_client(tmp_path, supervisor_enabled=False) as client:
        client.get("/api/video-provider-profiles")
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget")
        task_id = job["tasks"][0]["id"]
        client.patch(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-model",
            json={"model_id": "seedance2.0mini"},
        )
        client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget")
        submitted = client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-submit",
            json={"confirm_live_request": True},
        )
        assert submitted.status_code == 200
        assert submitted.json()["jobs"][0]["tasks"][0]["status"] == "submitted"
        settings = client.app.state.settings

    resumed_settings = replace(
        settings,
        video_task_supervisor_enabled=True,
        video_task_poll_interval_seconds=60,
    )
    with TestClient(create_app(resumed_settings)) as resumed:
        status = resumed.get("/api/video-task-supervisor/status").json()
        assert status["running"] is True
        assert status["poll_interval_seconds"] == 60

        assert resumed.app.state.video_task_supervisor.run_cycle() == 1
        with Session(resumed.app.state.database_engine) as session:
            task = session.get(BatchVideoTask, task_id)
            versions = session.exec(
                select(VideoResultVersion).where(VideoResultVersion.task_id == task_id)
            ).all()
            assert task.status == "imported"
            assert task.result_video_path
            assert len(versions) == 1

        assert resumed.app.state.video_task_supervisor.run_cycle() == 0
        with Session(resumed.app.state.database_engine) as session:
            versions = session.exec(
                select(VideoResultVersion).where(VideoResultVersion.task_id == task_id)
            ).all()
            assert len(versions) == 1


def test_video_supervisor_retries_transient_cli_errors_without_marking_task_failed(tmp_path: Path, monkeypatch) -> None:
    import app.services.videos as video_services

    monkeypatch.setattr(video_services, "JimengCliRunner", TemporarilyUnavailableJimengRunner)
    with build_live_client(tmp_path, supervisor_enabled=False) as client:
        client.get("/api/video-provider-profiles")
        project, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={"provider_profile_id": "huimeng_live"},
        ).json()["jobs"][0]
        client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget")
        task_id = job["tasks"][0]["id"]
        client.patch(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-model",
            json={"model_id": "seedance2.0mini"},
        )
        client.post(f"/api/batch-video-jobs/{job['id']}/confirm-budget")
        client.post(
            f"/api/batch-video-tasks/{task_id}/jimeng-cli-submit",
            json={"confirm_live_request": True},
        )

        assert client.app.state.video_task_supervisor.run_cycle() == 0
        with Session(client.app.state.database_engine) as session:
            task = session.get(BatchVideoTask, task_id)
            runs = session.exec(
                select(ProviderRun)
                .where(ProviderRun.task_id == task_id)
                .order_by(ProviderRun.created_at.desc())
            ).all()
            assert task.status == "submitted"
            assert task.error_message == ""
            assert runs[0].action == "video_supervisor_retry"

        assert client.app.state.video_task_supervisor.run_cycle() == 0
        with Session(client.app.state.database_engine) as session:
            retry_runs = session.exec(
                select(ProviderRun).where(
                    ProviderRun.task_id == task_id,
                    ProviderRun.action == "video_supervisor_retry",
                )
            ).all()
            assert len(retry_runs) == 1

        status = client.get("/api/video-task-supervisor/status").json()
        assert "暂时无法连接" in status["last_error"]
        workspace = client.get(f"/api/projects/{project['id']}/batch-video").json()
        assert workspace["jobs"][0]["tasks"][0]["external_provider"] == "jimeng_cli"


def test_vp_generation_job_survives_page_exit_and_service_restart(tmp_path: Path, monkeypatch) -> None:
    import app.services.vp_generation_supervisor as supervisor_service

    generated_shots: list[str] = []

    def fake_create_ai_vp_block(session, settings, shot_id, payload, ai_payload):
        versions = session.exec(select(VpBlock).where(VpBlock.shot_id == shot_id)).all()
        session.add(VpBlock(
            shot_id=shot_id,
            version_number=len(versions) + 1,
            package_stage="director_draft",
            prompt=f"后台生成 {payload.duration_seconds} 秒提示词",
            negative_prompt="禁止跳轴",
            duration_seconds=payload.duration_seconds,
            provider_profile_id="huimeng_live",
        ))
        session.commit()
        generated_shots.append(shot_id)
        return "project-unused-by-supervisor"

    monkeypatch.setattr(supervisor_service, "create_ai_vp_block", fake_create_ai_vp_block)

    with build_live_client(tmp_path, supervisor_enabled=False) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        first_shot_id = scene["shots"][0]["id"]
        with Session(client.app.state.database_engine) as session:
            first_shot = session.get(Shot, first_shot_id)
            first_shot.name = "建立单一动作镜头并缓慢推近"
            second_shot = Shot(
                scene_id=scene["id"],
                shot_code="SH002",
                name="快速蒙太奇穿越泥坑，随后切换多个动作节点",
            )
            session.add(first_shot)
            session.add(second_shot)
            session.commit()
            session.refresh(second_shot)
            shot_ids = [first_shot_id, second_shot.id]
            for shot_id in shot_ids:
                session.add(VpBlock(
                    shot_id=shot_id,
                    version_number=1,
                    package_stage="director_draft",
                    prompt="旧版 5 秒提示词",
                    negative_prompt="",
                    duration_seconds=5,
                    provider_profile_id="huimeng_live",
                ))
            session.commit()

        response = client.post(
            f"/api/scenes/{scene['id']}/vp-generation-jobs",
            json={"operation": "duration_rebuild", "confirm_live_request": True},
        )
        assert response.status_code == 202
        assert response.json()["total_count"] == 2
        job_id = response.json()["id"]

        assert client.app.state.vp_generation_supervisor.run_cycle() == 1
        with Session(client.app.state.database_engine) as session:
            job = session.get(VpGenerationJob, job_id)
            assert job.status == "queued"
            assert job.completed_count == 1
        settings = client.app.state.settings

    with TestClient(create_app(settings)) as resumed:
        latest = resumed.get(f"/api/scenes/{scene['id']}/vp-generation-jobs/latest").json()
        assert latest["completed_count"] == 1
        assert latest["status"] == "queued"

        assert resumed.app.state.vp_generation_supervisor.run_cycle() == 1
        finished = resumed.get(f"/api/scenes/{scene['id']}/vp-generation-jobs/latest").json()
        assert finished["status"] == "completed"
        assert finished["completed_count"] == 2
        assert resumed.app.state.vp_generation_supervisor.run_cycle() == 0

        with Session(resumed.app.state.database_engine) as session:
            for shot_id in shot_ids:
                versions = session.exec(
                    select(VpBlock)
                    .where(VpBlock.shot_id == shot_id, VpBlock.package_stage == "director_draft")
                    .order_by(VpBlock.version_number)
                ).all()
                assert len(versions) == 2
                assert versions[-1].duration_seconds != 5

    assert generated_shots == shot_ids


def test_vp_generation_job_can_stop_before_next_shot(tmp_path: Path) -> None:
    with build_live_client(tmp_path, supervisor_enabled=False) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot_id = scene["shots"][0]["id"]
        with Session(client.app.state.database_engine) as session:
            shot = session.get(Shot, shot_id)
            shot.name = "建立单一动作镜头并缓慢推近"
            session.add(shot)
            session.add(VpBlock(
                shot_id=shot_id,
                version_number=1,
                package_stage="director_draft",
                prompt="旧版 5 秒提示词",
                negative_prompt="",
                duration_seconds=5,
                provider_profile_id="huimeng_live",
            ))
            session.commit()

        created = client.post(
            f"/api/scenes/{scene['id']}/vp-generation-jobs",
            json={"operation": "duration_rebuild", "confirm_live_request": True},
        ).json()
        stopped = client.post(f"/api/vp-generation-jobs/{created['id']}/cancel")

        assert stopped.status_code == 200
        assert stopped.json()["status"] == "cancelled"
        assert "保留已完成" in stopped.json()["message"]
        assert client.app.state.vp_generation_supervisor.run_cycle() == 0

        with Session(client.app.state.database_engine) as session:
            versions = session.exec(select(VpBlock).where(VpBlock.shot_id == shot_id)).all()
            assert len(versions) == 1


def test_jimeng_cli_capability_parser_only_exposes_help_models() -> None:
    current = parse_multimodal2video_help(
        "model_version: seedance2.0, seedance2.0fast, seedance2.0_vip\n"
        "duration: 4-15s\ninput limits: image<=9, video<=3, audio<=3\n"
        "video_resolution: 720p, 1080p, 4k",
        cli_version="2a20fff",
    )
    assert current.available_models == ("seedance2.0", "seedance2.0fast", "seedance2.0_vip")
    assert not any("2.5" in item for item in current.available_models)
    assert (current.max_images, current.max_videos, current.max_audios) == (9, 3, 3)

    future = parse_multimodal2video_help(
        "supported values: seedance2.5, seedance2.0_vip\n"
        "duration supported range: 4-30\ninput limits: image<=30, video<=10, audio<=10\n"
        "video_resolution: 480p, 720p",
        cli_version="future",
    )
    assert future.available_models[0] == "seedance2.5"
    assert future.max_duration == 30


def test_seedance25_model_catalog_and_generation_settings_are_provider_aware(tmp_path: Path) -> None:
    with build_live_client(tmp_path, supervisor_enabled=False) as client:
        catalog = client.get("/api/video-provider-models", params={"provider_type": "volcengine_seedance25"})
        assert catalog.status_code == 200
        model = catalog.json()[0]
        assert model["provider_model_id"] == "doubao-seedance-2-5-260628"
        assert model["supported_resolutions"] == ["480p", "720p"]
        assert model["min_duration"] == 4
        assert model["max_duration"] == 30
        assert model["supports_smart_duration"] is True
        assert model["is_mock_only"] is True
        validated = client.post("/api/video-provider-profiles/volcengine_seedance25/validate")
        assert validated.status_code == 200, validated.text
        assert "只运行本地链路验收" in validated.json()["validation_message"]

        project, scene_id = ready_three_shot_project(client)
        created = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={
                "provider_profile_id": "volcengine_seedance25",
                "submission_channel": "volcengine_seedance25",
            },
        )
        assert created.status_code == 201, created.text
        job = created.json()["jobs"][0]
        task = job["tasks"][0]
        assert task["canonical_request"]["model_family"] == "seedance-2.5"
        assert task["canonical_request"]["duration_mode"] == "smart"
        assert task["canonical_request"]["resolution"] == "720p"
        assert task["canonical_request"]["prompt_optimization"]["enabled"] is True
        assert task["canonical_request"]["prompt_optimization"]["mode"] == "deterministic_local_compiler"
        assert "【Seedance 2.5 执行结构】" in task["canonical_request"]["prompt"]
        assert any("真人肖像参考默认阻塞" in item for item in task["missing_items"])

        updated = client.patch(
            f"/api/batch-video-jobs/{job['id']}/generation-settings",
            json={"duration_mode": "specified", "duration_seconds": 30, "resolution": "480p"},
        )
        assert updated.status_code == 200, updated.text
        canonical = updated.json()["jobs"][0]["tasks"][0]["canonical_request"]
        assert canonical["duration_mode"] == "specified"
        assert canonical["duration_seconds"] == 30
        assert canonical["resolution"] == "480p"

        invalid = client.patch(
            f"/api/batch-video-jobs/{job['id']}/generation-settings",
            json={"duration_mode": "specified", "duration_seconds": 31},
        )
        assert invalid.status_code == 422
        assert project["id"]


def test_seedance25_structured_references_use_real_media_types_and_at_tokens(tmp_path: Path) -> None:
    with build_live_client(tmp_path, supervisor_enabled=False) as client:
        project, scene_id = ready_three_shot_project(client)
        video = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "reference"},
            files={"file": ("camera_move.mp4", b"mock-video", "video/mp4")},
        )
        audio = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "reference"},
            files={"file": ("rhythm.wav", b"mock-audio", "audio/wav")},
        )
        assert video.status_code == 201, video.text
        assert audio.status_code == 201, audio.text

        created = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={
                "provider_profile_id": "volcengine_seedance25",
                "submission_channel": "volcengine_seedance25",
            },
        ).json()["jobs"][0]
        task = created["tasks"][0]
        image = next(
            item for item in task["reference_candidates"]
            if item["asset_type"] not in {"character", "costume", "source"}
        )
        video_candidate = next(item for item in task["reference_candidates"] if item["asset_id"] == video.json()["id"])
        audio_candidate = next(item for item in task["reference_candidates"] if item["asset_id"] == audio.json()["id"])
        assert video_candidate["media_type"] == "video"
        assert audio_candidate["media_type"] == "audio"

        saved = client.patch(
            f"/api/batch-video-tasks/{task['id']}/reference-bindings",
            json={
                "reference_items": [
                    {"asset_id": image["asset_id"], "media_type": "image", "purpose": "camera"},
                    {"asset_id": video_candidate["asset_id"], "media_type": "video", "purpose": "action"},
                    {"asset_id": audio_candidate["asset_id"], "media_type": "audio", "purpose": "sound"},
                ]
            },
        )
        assert saved.status_code == 200, saved.text
        saved_task = saved.json()["jobs"][0]["tasks"][0]
        assert [item["token"] for item in saved_task["reference_bindings"]] == ["@图片1", "@视频1", "@音频1"]
        assert "@图片1" in saved_task["provider_prompt_preview"]
        assert "@视频1" in saved_task["provider_prompt_preview"]
        assert "@音频1" in saved_task["provider_prompt_preview"]
        assert saved_task["canonical_request"]["prompt_optimization"]["rule_id"] == "sd25-pe-compatible"
        assert saved_task["canonical_request"]["source_prompt"] in saved_task["provider_prompt_preview"]
        assert not any("真人肖像参考默认阻塞" in item for item in saved_task["missing_items"])

        disabled = client.patch(
            f"/api/batch-video-tasks/{task['id']}/generation-settings",
            json={"prompt_optimization_enabled": False},
        )
        assert disabled.status_code == 200, disabled.text
        disabled_task = disabled.json()["jobs"][0]["tasks"][0]
        assert disabled_task["canonical_request"]["prompt_optimization"]["enabled"] is False
        assert "【Seedance 2.5 执行结构】" not in disabled_task["provider_prompt_preview"]
        assert "@图片1" in disabled_task["provider_prompt_preview"]

        wrong_type = client.patch(
            f"/api/batch-video-tasks/{task['id']}/reference-bindings",
            json={
                "reference_items": [
                    {"asset_id": image["asset_id"], "media_type": "video", "purpose": "action"}
                ]
            },
        )
        assert wrong_type.status_code == 422
        assert "真实类型是 image" in wrong_type.json()["detail"]

        audio_ids = [audio.json()["id"]]
        for index in range(10):
            extra_audio = client.post(
                f"/api/projects/{project['id']}/source-files",
                data={"category": "reference"},
                files={"file": (f"rhythm-{index}.wav", b"mock-audio", "audio/wav")},
            )
            assert extra_audio.status_code == 201, extra_audio.text
            audio_ids.append(extra_audio.json()["id"])
        over_audio_limit = client.patch(
            f"/api/batch-video-tasks/{task['id']}/reference-bindings",
            json={
                "reference_items": [
                    {"asset_id": asset_id, "media_type": "audio", "purpose": "sound"}
                    for asset_id in audio_ids
                ]
            },
        )
        assert over_audio_limit.status_code == 422
        assert "图片 30、视频 10、音频 10" in over_audio_limit.json()["detail"]


def test_seedance25_mock_supervisor_never_creates_fake_video_result(tmp_path: Path) -> None:
    with build_live_client(tmp_path, supervisor_enabled=False) as client:
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={
                "provider_profile_id": "volcengine_seedance25",
                "submission_channel": "volcengine_seedance25",
            },
        ).json()["jobs"][0]
        task = job["tasks"][0]
        safe_images = [
            item for item in task["reference_candidates"]
            if item["asset_type"] not in {"character", "costume", "source"}
        ][:2]
        saved = client.patch(
            f"/api/batch-video-tasks/{task['id']}/reference-bindings",
            json={
                "reference_items": [
                    {"asset_id": item["asset_id"], "media_type": "image", "purpose": "camera"}
                    for item in safe_images
                ]
            },
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["jobs"][0]["tasks"][0]["missing_items"] == []
        assert client.post(f"/api/batch-video-jobs/{job['id']}/reference-bindings/confirm").status_code == 200
        assert client.post(f"/api/batch-video-jobs/{job['id']}/confirm-cost-risk").status_code == 200
        launched = client.post(
            f"/api/batch-video-jobs/{job['id']}/launch",
            json={"confirm_live_request": True},
        )
        assert launched.status_code == 202, launched.text

        supervisor = client.app.state.video_task_supervisor
        assert supervisor.run_cycle() == 1
        assert supervisor.run_cycle() == 1
        assert supervisor.run_cycle() == 1

        workspace = client.get(f"/api/projects/{launched.json()['project_id']}/batch-video").json()
        finished_job = next(item for item in workspace["jobs"] if item["id"] == job["id"])
        finished_task = finished_job["tasks"][0]
        assert finished_job["status"] == "mock_completed"
        assert finished_task["status"] == "mock_completed"
        assert finished_task["storage_status"] == "mock"
        assert finished_task["results"] == []
        assert finished_task["local_file_path"].endswith("_mock.json")

        mock_record = Path(finished_task["local_file_path"])
        assert mock_record.exists()
        assert json.loads(mock_record.read_text(encoding="utf-8"))["outbound_request_sent"] is False

        with Session(client.app.state.database_engine) as session:
            runs = session.exec(select(ProviderRun).where(ProviderRun.task_id == task["id"])).all()
            assert [run.action for run in runs] == [
                "seedance25_mock_submit",
                "seedance25_mock_poll",
                "seedance25_mock_poll",
                "seedance25_mock_download",
            ]
            assert all(
                json.loads(run.response_snapshot_json).get("outbound_request_sent") is False
                for run in runs
            )
            assert session.exec(
                select(VideoResultVersion).where(VideoResultVersion.task_id == task["id"])
            ).all() == []
        assert supervisor.run_cycle() == 0


def test_seedance25_mock_supervisor_recovers_after_fastapi_restart(tmp_path: Path) -> None:
    with build_live_client(tmp_path, supervisor_enabled=False) as client:
        _, scene_id = ready_three_shot_project(client)
        job = client.post(
            f"/api/scenes/{scene_id}/batch-video-jobs",
            json={
                "provider_profile_id": "volcengine_seedance25",
                "submission_channel": "volcengine_seedance25",
            },
        ).json()["jobs"][0]
        task = job["tasks"][0]
        safe_images = [
            item for item in task["reference_candidates"]
            if item["asset_type"] not in {"character", "costume", "source"}
        ][:2]
        saved = client.patch(
            f"/api/batch-video-tasks/{task['id']}/reference-bindings",
            json={
                "reference_items": [
                    {"asset_id": item["asset_id"], "media_type": "image", "purpose": "camera"}
                    for item in safe_images
                ]
            },
        )
        assert saved.status_code == 200, saved.text
        assert client.post(f"/api/batch-video-jobs/{job['id']}/reference-bindings/confirm").status_code == 200
        assert client.post(f"/api/batch-video-jobs/{job['id']}/confirm-cost-risk").status_code == 200
        launched = client.post(
            f"/api/batch-video-jobs/{job['id']}/launch",
            json={"confirm_live_request": True},
        )
        assert launched.status_code == 202, launched.text
        project_id = launched.json()["project_id"]
        assert client.app.state.video_task_supervisor.run_cycle() == 1
        settings = client.app.state.settings

    with TestClient(create_app(settings)) as resumed_client:
        supervisor = resumed_client.app.state.video_task_supervisor
        assert supervisor.run_cycle() == 1
        assert supervisor.run_cycle() == 1
        workspace = resumed_client.get(f"/api/projects/{project_id}/batch-video").json()
        resumed_job = next(item for item in workspace["jobs"] if item["id"] == job["id"])
        resumed_task = resumed_job["tasks"][0]
        assert resumed_job["status"] == "mock_completed"
        assert resumed_task["status"] == "mock_completed"
        assert resumed_task["storage_status"] == "mock"
        assert resumed_task["results"] == []
        assert Path(resumed_task["local_file_path"]).exists()
