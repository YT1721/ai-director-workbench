from __future__ import annotations

import json
from pathlib import Path
from io import BytesIO
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.config import Settings
from app.main import create_app
from app.models import Episode, Project, Scene, Shot, StoryboardShotVersion
from app.models.assets import SceneAssetVersion
from app.models.videos import VpBlock
from tests.test_system import SYSTEM_PROMPT_FILENAME, build_settings
from tests.test_workbench import build_client, create_project


def add_three_shots(client: TestClient, project: dict) -> tuple[str, list[dict]]:
    scene = project["episodes"][0]["scenes"][0]
    client.post(f"/api/scenes/{scene['id']}/shots")
    detail = client.post(f"/api/scenes/{scene['id']}/shots").json()
    return scene["id"], detail["episodes"][0]["scenes"][0]["shots"]


def storyboard_payload(camera_side: str = "A侧") -> dict:
    return {
        "shot_size": "中景",
        "camera_angle": "平视",
        "camera_movement": "固定机位",
        "action_start": "人物保持动作连续",
        "emotion_state": "克制",
        "sound_light": "环境底噪，白底/浅灰故事板说明板中的黑白灰铅笔明暗关系",
        "camera_point": "CAM01",
        "screen_position": "左侧",
        "eyeline_direction": "向右",
        "movement_direction": "从左向右",
        "camera_side": camera_side,
    }


def prepare_scene_asset(client: TestClient, scene_id: str) -> None:
    workspace = client.post(f"/api/scenes/{scene_id}/assets", json={"description": "本地测试场景", "spatial_layout": "左右对峙"}).json()
    scene_asset = workspace["scene_assets"][0]
    scope = scene_asset["scope_code"]
    asset_path = f"03_scenes/{scope}/scene_asset_real_test.png"
    target = client.app.state.settings.projects_root / workspace["project_code"] / asset_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_png_bytes())
    with Session(client.app.state.database_engine) as session:
        session.add(SceneAssetVersion(scene_asset_id=scene_asset["id"], version_number=1, asset_path=asset_path, status="confirmed_current"))
        session.commit()


def prepare_director_draft(client: TestClient, shot_id: str) -> dict:
    with Session(client.app.state.database_engine) as session:
        scene_version = session.exec(select(SceneAssetVersion).order_by(SceneAssetVersion.created_at.desc())).first()
        existing = session.exec(select(VpBlock).where(VpBlock.shot_id == shot_id)).all()
        items = [
            {"number": index, "title": f"第 {index} 项", "content": f"真实 AI 草案第 {index} 项"}
            for index in range(1, 19)
        ]
        items[4]["content"] = [
            {"time_range": "0.0s-1.0s", "description": "建立空间与人物姿态"},
            {"time_range": "1.0s-3.0s", "description": "主体动作推进"},
            {"time_range": "3.0s-5.0s", "description": "收束到截尾帧"},
        ]
        items[5]["content"] = "真实 AI 指定景别：近景压迫"
        items[6]["content"] = "真实 AI 指定机位：低机位仰拍"
        items[7]["content"] = "真实 AI 指定运镜：缓慢前推后轻微横移"
        items[8]["content"] = "真实 AI 指定构图：人物偏左，右侧留出压迫性空白"
        items[9]["content"] = "真实 AI 指定主体动作：主角抬头握紧信封"
        items[10]["content"] = "真实 AI 指定状态：眼神颤动，信封边角被捏皱"
        items[11]["content"] = "真实 AI 指定光线：冷色窗光切出脸部阴影"
        block = VpBlock(
            shot_id=shot_id,
            version_number=len(existing) + 1,
            has_character=False,
            scene_asset_version_id=scene_version.id,
            package_stage="director_draft",
            precision_json="[]",
            prompt_copy="真实 AI 草案提示词；不得改脸，不得改变身份气质。",
            prompt="真实 AI 草案提示词；不得改脸，不得改变身份气质。",
            negative_prompt="不要彩色，不要破坏轴线",
            provider_profile_id="huimeng_live",
        )
        import json
        block.precision_json = json.dumps(items, ensure_ascii=False)
        session.add(block)
        session.commit()
    return {}


def promote_storyboard_to_real_png(client: TestClient, version_id: str) -> None:
    with Session(client.app.state.database_engine) as session:
        version = session.get(StoryboardShotVersion, version_id)
        assert version is not None
        shot = session.get(Shot, version.shot_id)
        assert shot is not None
        scene = session.get(Scene, shot.scene_id)
        assert scene is not None
        episode = session.get(Episode, scene.episode_id)
        assert episode is not None
        project = session.get(Project, episode.project_id)
        assert project is not None
        asset_path = version.image_path.replace(".svg", "_real_test.png")
        target = client.app.state.settings.projects_root / project.project_code / asset_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_png_bytes())
        version.image_path = asset_path
        session.add(version)
        session.commit()


def test_storyboard_workspace_generates_grayscale_versions_and_execution_png(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        scene_id, shots = add_three_shots(client, project)
        prepare_scene_asset(client, scene_id)
        workspace = client.get(f"/api/projects/{project['id']}/storyboards").json()

        assert workspace["style_lock"] == {
            "enabled": True,
            "locked": True,
            "style_name": "统一白底高信息密度导演故事板说明板风格",
        }
        assert workspace["scenes"][0]["axis_plan"]["camera_safe_side"] == "A侧"

        for index, shot in enumerate(shots):
            payload = storyboard_payload()
            payload["camera_point"] = f"CAM0{index + 1}"
            prepare_director_draft(client, shot["id"])
            workspace = client.post(
                f"/api/shots/{shot['id']}/storyboard-versions",
                json=payload,
            ).json()
            version = next(
                item for item in workspace["scenes"][0]["shots"] if item["id"] == shot["id"]
            )["versions"][0]
            assert version["style_validation_status"] == "passed"
            assert version["axis_validation_status"] == "passed"
            assert version["schema_version"] == "unified_sb_v1"
            assert version["storyboard_mode"] == "unified_sb"
            assert version["storyboard_grid"] in {3, 4, 6, 9, 12}
            assert len(version["prompt_match"]) == version["storyboard_grid"]
            assert len(version["storyboard_cells"]) == version["storyboard_grid"]
            assert client.get(version["image_url"]).status_code == 200
            workspace = client.post(
                f"/api/storyboard-versions/{version['id']}/confirm"
            ).json()

        response = client.post(f"/api/scenes/{scene_id}/storyboard-pages")
        assert response.status_code == 201
        page = response.json()["scenes"][0]["execution_pages"][0]
        html = client.get(page["html_url"])
        png = client.get(page["png_url"])
        export = client.post(f"/api/scenes/{scene_id}/prompt-storyboard-export")
        export_payload = export.json()

    assert html.status_code == 200
    assert "TOP-DOWN BLOCKING DIAGRAM" in html.text
    assert "统一白底高信息密度导演故事板说明板风格" in html.text
    assert png.status_code == 200
    assert png.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert export.status_code == 201
    assert export_payload["shot_count"] == 3
    zip_path = tmp_path / "projects" / "PRJ001" / export_payload["relative_path"]
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        prompt = archive.read("SH001/video_prompt_copy.txt").decode("utf-8")
    assert "manifest.json" in names
    assert "SH001/storyboard_frame.png" in names
    assert "SH001/video_prompt_copy.txt" in names
    assert "SH001/vp_precision_18.json" in names
    assert "SH001/storyboard_grid.json" in names
    assert "SH001/unified_sb_meta.json" in names
    assert "SH001/copy_card.md" in names
    assert "不得改脸" in prompt


def test_cross_axis_version_cannot_be_confirmed_without_transition(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        prepare_scene_asset(client, scene["id"])
        prepare_director_draft(client, shot["id"])
        workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(camera_side="B侧"),
        ).json()
        version = workspace["scenes"][0]["shots"][0]["versions"][0]
        response = client.post(f"/api/storyboard-versions/{version['id']}/confirm")

    assert version["axis_validation_status"] == "failed"
    assert "未登记跨轴过渡" in version["axis_validation_notes"]
    assert response.status_code == 409
    assert "不能确认" in response.json()["detail"]


def test_storyboard_real_image_can_be_reused_for_compatible_new_timeline(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        prepare_scene_asset(client, scene["id"])
        prepare_director_draft(client, shot["id"])
        first_workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        first_version = first_workspace["scenes"][0]["shots"][0]["versions"][0]
        client.post(f"/api/storyboard-versions/{first_version['id']}/confirm")
        promote_storyboard_to_real_png(client, first_version["id"])
        with Session(client.app.state.database_engine) as session:
            stored = session.get(StoryboardShotVersion, first_version["id"])
            assert stored is not None
            stored.grid_reason = f"{stored.grid_reason}｜本版本由真实生图生成。"
            session.add(stored)
            session.commit()

        prepare_director_draft(client, shot["id"])
        second_workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        second_shot = second_workspace["scenes"][0]["shots"][0]
        second_version = second_shot["versions"][0]
        assert second_shot["reuse_assessment"]["recommendation"] == "reuse"
        assert second_shot["reuse_assessment"]["source_version_id"] == first_version["id"]

        client.post(f"/api/storyboard-versions/{second_version['id']}/confirm")
        refused = client.post(
            f"/api/storyboard-versions/{second_version['id']}/reuse-image",
            json={"source_version_id": first_version["id"], "confirm_reuse": False},
        )
        reused_response = client.post(
            f"/api/storyboard-versions/{second_version['id']}/reuse-image",
            json={"source_version_id": first_version["id"], "confirm_reuse": True},
        )
        reused_shot = reused_response.json()["scenes"][0]["shots"][0]
        reused_version = reused_shot["versions"][0]

    assert refused.status_code == 409
    assert reused_response.status_code == 201
    assert "_sb_reused_" in reused_version["image_url"]
    assert reused_version["vp_basis_block_id"] == second_shot["latest_vp_draft_id"]
    assert reused_version["status"] == "confirmed_current"
    assert reused_shot["reuse_assessment"] is None


def test_storyboard_incompatible_image_requires_explicit_force_reuse(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        prepare_scene_asset(client, scene["id"])
        prepare_director_draft(client, shot["id"])
        first_workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        first_version = first_workspace["scenes"][0]["shots"][0]["versions"][0]
        client.post(f"/api/storyboard-versions/{first_version['id']}/confirm")
        promote_storyboard_to_real_png(client, first_version["id"])
        with Session(client.app.state.database_engine) as session:
            stored = session.get(StoryboardShotVersion, first_version["id"])
            stored.grid_reason = f"{stored.grid_reason}｜本版本由真实生图生成。"
            session.add(stored)
            session.commit()

        prepare_director_draft(client, shot["id"])
        second_workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        second_version = second_workspace["scenes"][0]["shots"][0]["versions"][0]
        client.post(f"/api/storyboard-versions/{second_version['id']}/confirm")
        with Session(client.app.state.database_engine) as session:
            target = session.get(StoryboardShotVersion, second_version["id"])
            target.storyboard_grid = 6
            target.status = "confirmed_current"
            session.add(target)
            session.commit()

        refused = client.post(
            f"/api/storyboard-versions/{second_version['id']}/reuse-image",
            json={"source_version_id": first_version["id"], "confirm_reuse": True},
        )
        assert refused.status_code == 409, refused.text
        forced = client.post(
            f"/api/storyboard-versions/{second_version['id']}/reuse-image",
            json={"source_version_id": first_version["id"], "confirm_reuse": True, "force_reuse": True},
        )
        assert forced.status_code == 201, forced.text
        forced_version = forced.json()["scenes"][0]["shots"][0]["versions"][0]

    assert refused.status_code == 409
    assert "明确选择强制沿用" in refused.json()["detail"]
    assert "用户人工确认忽略结构差异" in forced_version["grid_reason"]
    assert "_sb_reused_" in forced_version["image_url"]


def test_storyboard_version_uses_ai_vp_precision_fields_instead_of_frontend_defaults(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        prepare_scene_asset(client, scene["id"])
        prepare_director_draft(client, shot["id"])
        workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        version = workspace["scenes"][0]["shots"][0]["versions"][0]

    assert version["shot_size"] == "真实 AI 指定景别：近景压迫"
    assert version["camera_angle"] == "真实 AI 指定机位：低机位仰拍"
    assert version["camera_movement"] == "真实 AI 指定运镜：缓慢前推后轻微横移"
    assert version["screen_position"] == "真实 AI 指定构图：人物偏左，右侧留出压迫性空白"
    assert version["action_start"] == "真实 AI 指定主体动作：主角抬头握紧信封"
    assert version["emotion_state"] == "真实 AI 指定状态：眼神颤动，信封边角被捏皱"
    assert version["sound_light"] == "真实 AI 指定光线：冷色窗光切出脸部阴影"


def test_storyboard_accepts_text_timeline_from_ai_vp_precision(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        prepare_scene_asset(client, scene["id"])
        prepare_director_draft(client, shot["id"])
        with Session(client.app.state.database_engine) as session:
            block = session.exec(
                select(VpBlock).where(VpBlock.shot_id == shot["id"]).order_by(VpBlock.version_number.desc())
            ).first()
            assert block is not None
            precision = json.loads(block.precision_json)
            precision[4]["content"] = (
                "0.0s-1.2s：数字微粒消散后渐亮进入画面。"
                "1.2s-3.2s：绿皮火车穿行，镜头保持克制平稳。"
                "3.2s-5.0s：切到办公室，完成时间转场。"
            )
            block.precision_json = json.dumps(precision, ensure_ascii=False)
            session.add(block)
            session.commit()

        response = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        )
        assert response.status_code == 201
        version = response.json()["scenes"][0]["shots"][0]["versions"][0]

    assert version["storyboard_grid"] == 4
    assert version["timeline_nodes"][0]["time_range"] == "0.0s-1.2s"
    assert "数字微粒" in version["timeline_nodes"][0]["description"]
    assert len(version["prompt_match"]) == 4


def _png_bytes() -> bytes:
    data = BytesIO()
    Image.new("RGB", (64, 36), "#d8d8d8").save(data, "PNG")
    return data.getvalue()


def test_storyboard_real_image_gate_submit_poll_and_download(tmp_path: Path, monkeypatch) -> None:
    submit_calls: list[str] = []

    class FakeHuimengImageProvider:
        def submit_task(self, base_url, api_key, model_id, prompt, ratio="16:9", quality="medium", resolution="2k"):
            submit_calls.append(prompt)
            assert base_url == "https://api.huimengi.com"
            assert api_key == "hm-test-secret"
            assert model_id == "image-2"
            assert ratio == "16:9"
            assert "白底或浅灰底的高信息密度导演故事板说明板" in prompt
            assert "功能色" in prompt
            assert "彩色人物环境主体" in prompt
            assert "必须是越野摩托车，不要汽车" in prompt
            assert "本次人工修正要求" in prompt
            request_payload = {
                "model": model_id,
                "params": {"prompt": prompt, "ratio": ratio, "quality": quality, "resolution": resolution},
            }
            return {"task_id": "img-task-1", "status": "processing", "image_url": ""}, {"data": {"id": "img-task-1", "status": "processing"}}, request_payload

        def poll_task(self, base_url, api_key, external_task_id):
            assert external_task_id == "img-task-1"
            return {"task_id": external_task_id, "status": "completed", "image_url": "https://example.test/storyboard.png"}, {"data": {"id": external_task_id, "status": "success", "image_url": "https://example.test/storyboard.png"}}

        def download_image(self, image_url):
            assert image_url == "https://example.test/storyboard.png"
            return _png_bytes()

    monkeypatch.setattr("app.services.storyboards.HuimengImageProvider", FakeHuimengImageProvider)
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    base_settings = build_settings(tmp_path, prompt_file)
    settings = Settings(
        **{
            **base_settings.__dict__,
            "enable_real_image_generation": True,
            "huimengi_api_key": "hm-test-secret",
            "huimengi_image_base_url": "https://api.huimengi.com",
            "huimengi_image_model": "image-2",
        }
    )

    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        prepare_scene_asset(client, scene["id"])
        prepare_director_draft(client, shot["id"])
        workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        version = workspace["scenes"][0]["shots"][0]["versions"][0]
        readiness = client.get(f"/api/storyboard-versions/{version['id']}/image-readiness")
        prompt_preview = client.get(f"/api/storyboard-versions/{version['id']}/image-prompt")
        no_confirm = client.post(f"/api/storyboard-versions/{version['id']}/image-submit", json={"confirm_live_request": False})
        submitted = client.post(
            f"/api/storyboard-versions/{version['id']}/image-submit",
            json={"confirm_live_request": True, "correction_note": "必须是越野摩托车，不要汽车"},
        )
        job = submitted.json()
        duplicate = client.post(
            f"/api/storyboard-versions/{version['id']}/image-submit",
            json={"confirm_live_request": True, "correction_note": "重复点击不应再次付费提交"},
        )
        restored_workspace = client.get(f"/api/projects/{project['id']}/storyboards").json()
        restored_version = restored_workspace["scenes"][0]["shots"][0]["versions"][0]
        polled = client.post(f"/api/image-generation-jobs/{job['id']}/poll", json={"confirm_live_request": True})
        downloaded = client.post(f"/api/image-generation-jobs/{job['id']}/download", json={"confirm_live_request": True})
        versions = downloaded.json()["scenes"][0]["shots"][0]["versions"]
        downloaded_again = client.post(f"/api/image-generation-jobs/{job['id']}/download", json={"confirm_live_request": True})
        repeated_versions = downloaded_again.json()["scenes"][0]["shots"][0]["versions"]
        new_version = versions[0]
        image_response = client.get(new_version["image_url"])

    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    assert prompt_preview.status_code == 200
    assert "为电影导演生成单镜头故事板图片" in prompt_preview.json()["prompt"]
    assert no_confirm.status_code == 409
    assert submitted.status_code == 201
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == job["id"]
    assert len(submit_calls) == 1
    assert job["external_task_id"] == "img-task-1"
    assert job["status"] == "processing"
    assert "必须是越野摩托车，不要汽车" in job["prompt"]
    assert restored_version["latest_image_job"]["id"] == job["id"]
    assert restored_version["latest_image_job"]["status"] == "processing"
    assert "hm-test-secret" not in submitted.text
    assert polled.json()["status"] == "completed"
    assert downloaded.status_code == 200
    assert len(versions) == 2
    assert downloaded_again.status_code == 200
    assert len(repeated_versions) == 2
    assert new_version["version_number"] == 2
    assert new_version["image_url"].endswith(".png")
    assert image_response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_storyboard_image_url_marks_task_completed_even_when_status_is_submitted(tmp_path: Path, monkeypatch) -> None:
    class FakeHuimengImageProvider:
        def submit_task(self, base_url, api_key, model_id, prompt, ratio="16:9", quality="medium", resolution="2k"):
            return (
                {"task_id": "img-task-ready", "status": "submitted", "image_url": "https://example.test/ready.png"},
                {"data": {"id": "img-task-ready", "status": "submitted", "image_url": "https://example.test/ready.png"}},
                {"model": model_id, "params": {"prompt": prompt}},
            )

        def poll_task(self, base_url, api_key, external_task_id):
            return (
                {"task_id": external_task_id, "status": "submitted", "image_url": "https://example.test/ready.png"},
                {"data": {"id": external_task_id, "status": "submitted", "image_url": "https://example.test/ready.png"}},
            )

        def download_image(self, image_url):
            assert image_url == "https://example.test/ready.png"
            return _png_bytes()

    monkeypatch.setattr("app.services.storyboards.HuimengImageProvider", FakeHuimengImageProvider)
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    base_settings = build_settings(tmp_path, prompt_file)
    settings = Settings(
        **{
            **base_settings.__dict__,
            "enable_real_image_generation": True,
            "huimengi_api_key": "hm-test-secret",
            "huimengi_image_base_url": "https://api.huimengi.com",
            "huimengi_image_model": "image-2",
        }
    )

    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        prepare_scene_asset(client, scene["id"])
        prepare_director_draft(client, shot["id"])
        workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        version = workspace["scenes"][0]["shots"][0]["versions"][0]
        submitted = client.post(f"/api/storyboard-versions/{version['id']}/image-submit", json={"confirm_live_request": True})
        job = submitted.json()
        downloaded = client.post(f"/api/image-generation-jobs/{job['id']}/download", json={"confirm_live_request": True})

    assert job["status"] == "completed"
    assert job["remote_result_url"] == "https://example.test/ready.png"
    assert downloaded.status_code == 200
    assert downloaded.json()["scenes"][0]["shots"][0]["versions"][0]["image_url"].endswith(".png")


def test_storyboard_instant_image_submit_saves_version_immediately(tmp_path: Path, monkeypatch) -> None:
    class FakeOpenAIImagesProvider:
        def generate_image(self, base_url, api_key, model_id, prompt, size="1536x1024"):
            assert base_url == "https://images.example.test/v1"
            assert api_key == "sk-instant"
            assert model_id == "gpt-image-1"
            assert "白底或浅灰底的高信息密度导演故事板说明板" in prompt
            return _png_bytes(), {"data": [{"b64_json": "fake"}]}, {"model": model_id, "prompt": prompt, "size": size}

    monkeypatch.setattr("app.services.storyboards.OpenAIImagesProvider", FakeOpenAIImagesProvider)
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    base_settings = build_settings(tmp_path, prompt_file)
    settings = Settings(
        **{
            **base_settings.__dict__,
            "enable_real_image_generation": True,
            "image_provider_mode": "openai_images",
            "image_api_key": "sk-instant",
            "image_base_url": "https://images.example.test/v1",
            "image_model": "gpt-image-1",
        }
    )

    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        scene = project["episodes"][0]["scenes"][0]
        shot = scene["shots"][0]
        prepare_scene_asset(client, scene["id"])
        prepare_director_draft(client, shot["id"])
        workspace = client.post(
            f"/api/shots/{shot['id']}/storyboard-versions",
            json=storyboard_payload(),
        ).json()
        version = workspace["scenes"][0]["shots"][0]["versions"][0]
        readiness = client.get(f"/api/storyboard-versions/{version['id']}/image-readiness")
        submitted = client.post(
            f"/api/storyboard-versions/{version['id']}/image-submit",
            json={"confirm_live_request": True},
        )
        job = submitted.json()
        restored = client.get(f"/api/projects/{project['id']}/storyboards").json()
        versions = restored["scenes"][0]["shots"][0]["versions"]
        new_version = versions[0]
        image_response = client.get(new_version["image_url"])

    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    assert submitted.status_code == 201
    assert job["provider"] == "openai_images"
    assert job["status"] == "downloaded"
    assert "sk-instant" not in submitted.text
    # 即时模式提交完成时新版本已经建好，无需再查询/下载
    assert new_version["version_number"] == 2
    assert new_version["image_url"].endswith(".png")
    assert image_response.content.startswith(b"\x89PNG\r\n\x1a\n")
