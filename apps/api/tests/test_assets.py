from __future__ import annotations

import json
from pathlib import Path
from io import BytesIO

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app
from app.providers.text import TextSummaryResult
from tests.test_system import SYSTEM_PROMPT_FILENAME, build_settings
from tests.test_workbench import build_client, create_project


def create_character(client: TestClient, project_id: str) -> dict:
    response = client.post(
        f"/api/projects/{project_id}/characters",
        json={
            "name": "朱元璋",
            "face_shape": "清瘦长脸",
            "facial_features": "眉骨清晰，目光克制",
            "age_description": "五十岁上下",
            "height_description": "中等偏高",
            "body_type": "清瘦",
            "hair_style": "束发",
            "identity_temperament": "帝王威严，疲惫克制",
        },
    )
    assert response.status_code == 201
    return response.json()["characters"][0]


def test_local_placeholder_asset_versions_are_disabled(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        project_id = project["id"]
        scene_id = project["episodes"][0]["scenes"][0]["id"]
        character = create_character(client, project_id)

        master_response = client.post(f"/api/characters/{character['id']}/master-versions")

        workspace = client.post(
            f"/api/characters/{character['id']}/costumes",
            json={"usage_context": "登基大典", "description": "玄色礼服"},
        ).json()
        costume = workspace["characters"][0]["costumes"][0]
        assert costume["costume_code"] == "C01"

        costume_response = client.post(f"/api/costumes/{costume['id']}/versions")

        workspace = client.post(
            f"/api/scenes/{scene_id}/assets",
            json={
                "description": "坤宁宫寝殿",
                "spatial_layout": "床榻在北，烛台在东",
                "time_weather_light": "夜，烛光",
                "key_props": "烛台、屏风",
                "palette_mood": "暗红与深木色，压抑",
            },
        ).json()
        scene_asset = workspace["scene_assets"][0]
        scene_response = client.post(f"/api/scene-assets/{scene_asset['id']}/versions")
        final_workspace = client.get(f"/api/projects/{project_id}/assets").json()

    assert master_response.status_code == 410
    assert "本地 SVG 占位人物图已停用" in master_response.json()["detail"]
    assert costume_response.status_code == 410
    assert "本地 SVG 占位服装图已停用" in costume_response.json()["detail"]
    assert scene_response.status_code == 410
    assert "本地 SVG 占位场景图已停用" in scene_response.json()["detail"]
    assert final_workspace["characters"][0]["master_versions"] == []
    assert final_workspace["characters"][0]["costumes"][0]["versions"] == []
    assert final_workspace["scene_assets"][0]["versions"] == []


def _settings_with_fake_real_image(tmp_path: Path, monkeypatch) -> Settings:
    class FakeHuimengImageProvider:
        counter = 0

        def submit_task(self, base_url, api_key, model_id, prompt, ratio="16:9", quality="medium", resolution="2k"):
            self.__class__.counter += 1
            task_id = f"asset-img-{self.__class__.counter}"
            return (
                {"task_id": task_id, "status": "processing", "image_url": ""},
                {"data": {"id": task_id, "status": "processing"}},
                {"model": model_id, "params": {"prompt": prompt, "ratio": ratio, "quality": quality, "resolution": resolution}},
            )

        def poll_task(self, base_url, api_key, external_task_id):
            return (
                {"task_id": external_task_id, "status": "completed", "image_url": f"https://example.test/{external_task_id}.png"},
                {"data": {"id": external_task_id, "status": "success", "image_url": f"https://example.test/{external_task_id}.png"}},
            )

        def download_image(self, image_url):
            return _png_bytes()

    monkeypatch.setattr("app.services.assets.HuimengImageProvider", FakeHuimengImageProvider)
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    base_settings = build_settings(tmp_path, prompt_file)
    return Settings(
        **{
            **base_settings.__dict__,
            "enable_real_image_generation": True,
            "huimengi_api_key": "hm-test-secret",
            "huimengi_image_base_url": "https://api.huimengi.com",
            "huimengi_image_model": "image-2",
        }
    )


def _create_real_character_master_version(client: TestClient, character_id: str) -> dict:
    submitted = client.post(
        f"/api/asset-images/character-master/{character_id}/submit",
        json={"confirm_live_request": True},
    )
    assert submitted.status_code == 201
    job = submitted.json()
    polled = client.post(
        f"/api/asset-image-jobs/{job['id']}/poll",
        json={"confirm_live_request": True},
    )
    assert polled.status_code == 200
    downloaded = client.post(
        f"/api/asset-image-jobs/{job['id']}/download",
        json={"confirm_live_request": True},
    )
    assert downloaded.status_code == 200
    versions = downloaded.json()["characters"][0]["master_versions"]
    return max(versions, key=lambda item: item["version_number"])


def test_version_rollback_preserves_history_and_locked_version_can_be_replaced(tmp_path: Path, monkeypatch) -> None:
    settings = _settings_with_fake_real_image(tmp_path, monkeypatch)
    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        character = create_character(client, project["id"])

        first = _create_real_character_master_version(client, character["id"])
        client.post(f"/api/asset-versions/character-master/{first['id']}/confirm")

        second = _create_real_character_master_version(client, character["id"])
        workspace = client.post(
            f"/api/asset-versions/character-master/{second['id']}/confirm"
        ).json()
        statuses = {
            item["version_number"]: item["status"]
            for item in workspace["characters"][0]["master_versions"]
        }
        assert statuses == {2: "confirmed_current", 1: "confirmed_history"}

        workspace = client.post(
            f"/api/asset-versions/character-master/{first['id']}/rollback"
        ).json()
        statuses = {
            item["version_number"]: item["status"]
            for item in workspace["characters"][0]["master_versions"]
        }
        assert statuses == {2: "confirmed_history", 1: "confirmed_current"}

        client.post(f"/api/asset-versions/character-master/{first['id']}/lock")
        blocked = client.post(
            f"/api/asset-versions/character-master/{second['id']}/confirm"
        )
        unlocked = client.post(
            f"/api/asset-versions/character-master/{first['id']}/unlock"
        )
        switched = client.post(
            f"/api/asset-versions/character-master/{second['id']}/confirm"
        )

    assert blocked.status_code == 409
    assert "已有锁定版本" in blocked.json()["detail"]
    assert unlocked.status_code == 200
    assert switched.status_code == 200
    statuses = {
        item["version_number"]: item["status"]
        for item in switched.json()["characters"][0]["master_versions"]
    }
    assert statuses == {2: "confirmed_current", 1: "confirmed_history"}


def _png_bytes() -> bytes:
    data = BytesIO()
    Image.new("RGB", (64, 36), "#bfbfbf").save(data, "PNG")
    return data.getvalue()


def test_real_asset_image_submit_poll_and_download_creates_new_version(tmp_path: Path, monkeypatch) -> None:
    class FakeHuimengImageProvider:
        def submit_task(self, base_url, api_key, model_id, prompt, ratio="16:9", quality="medium", resolution="2k"):
            assert base_url == "https://api.huimengi.com"
            assert api_key == "hm-test-secret"
            assert model_id == "image-2"
            assert "角色资产 Bible" in prompt
            assert "米白/奶油白/浅暖灰背景" in prompt
            return (
                {"task_id": "asset-img-1", "status": "processing", "image_url": ""},
                {"data": {"id": "asset-img-1", "status": "processing"}},
                {"model": model_id, "params": {"prompt": prompt, "ratio": ratio, "quality": quality, "resolution": resolution}},
            )

        def poll_task(self, base_url, api_key, external_task_id):
            assert external_task_id == "asset-img-1"
            return (
                {"task_id": external_task_id, "status": "completed", "image_url": "https://example.test/asset.png"},
                {"data": {"id": external_task_id, "status": "success", "image_url": "https://example.test/asset.png"}},
            )

        def download_image(self, image_url):
            assert image_url == "https://example.test/asset.png"
            return _png_bytes()

    monkeypatch.setattr("app.services.assets.HuimengImageProvider", FakeHuimengImageProvider)
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
        character = create_character(client, project["id"])
        readiness = client.get(f"/api/asset-images/character-master/{character['id']}/readiness")
        no_confirm = client.post(
            f"/api/asset-images/character-master/{character['id']}/submit",
            json={"confirm_live_request": False},
        )
        submitted = client.post(
            f"/api/asset-images/character-master/{character['id']}/submit",
            json={"confirm_live_request": True},
        )
        job = submitted.json()
        polled = client.post(
            f"/api/asset-image-jobs/{job['id']}/poll",
            json={"confirm_live_request": True},
        )
        downloaded = client.post(
            f"/api/asset-image-jobs/{job['id']}/download",
            json={"confirm_live_request": True},
        )
        version = downloaded.json()["characters"][0]["master_versions"][0]
        image_response = client.get(version["asset_url"])

    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    assert no_confirm.status_code == 409
    assert submitted.status_code == 201
    assert "hm-test-secret" not in submitted.text
    assert job["external_task_id"] == "asset-img-1"
    assert polled.json()["status"] == "completed"
    assert downloaded.status_code == 200
    assert version["version_number"] == 1
    assert version["asset_path"].endswith(".png")
    assert image_response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_download_refreshes_expired_signed_url_and_retries(tmp_path: Path, monkeypatch) -> None:
    class ExpiringHuimengImageProvider:
        download_urls: list[str] = []

        def submit_task(self, base_url, api_key, model_id, prompt, ratio="16:9", quality="medium", resolution="2k"):
            return (
                {"task_id": "asset-img-exp", "status": "completed", "image_url": "https://example.test/stale.png"},
                {"data": {"id": "asset-img-exp", "status": "success", "image_url": "https://example.test/stale.png"}},
                {"model": model_id, "params": {"prompt": prompt}},
            )

        def poll_task(self, base_url, api_key, external_task_id):
            assert external_task_id == "asset-img-exp"
            return (
                {"task_id": external_task_id, "status": "completed", "image_url": "https://example.test/fresh.png"},
                {"data": {"id": external_task_id, "status": "success", "image_url": "https://example.test/fresh.png"}},
            )

        def download_image(self, image_url):
            self.__class__.download_urls.append(image_url)
            if "stale" in image_url:
                request = httpx.Request("GET", image_url)
                raise httpx.HTTPStatusError(
                    "403 Forbidden",
                    request=request,
                    response=httpx.Response(403, request=request),
                )
            return _png_bytes()

    monkeypatch.setattr("app.services.assets.HuimengImageProvider", ExpiringHuimengImageProvider)
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
        character = create_character(client, project["id"])
        submitted = client.post(
            f"/api/asset-images/character-master/{character['id']}/submit",
            json={"confirm_live_request": True},
        )
        job = submitted.json()
        downloaded = client.post(
            f"/api/asset-image-jobs/{job['id']}/download",
            json={"confirm_live_request": True},
        )
        version = downloaded.json()["characters"][0]["master_versions"][0]

    assert submitted.status_code == 201
    assert downloaded.status_code == 200
    assert ExpiringHuimengImageProvider.download_urls == [
        "https://example.test/stale.png",
        "https://example.test/fresh.png",
    ]
    assert version["version_number"] == 1


def test_ai_inventory_upload_confirm_and_auto_bind_complete_asset_loop(tmp_path: Path, monkeypatch) -> None:
    inventory = {
        "characters": [
            {
                "name": "林夏",
                "description": "二十多岁的纪录片导演，短发，神情专注。",
                "visual_prompt": "真人写实角色资产板，林夏，短发，深色冲锋衣。",
                "evidence": "林夏推开仓库门，握紧手中的旧录音机。",
                "scene_scope_codes": ["EP01SC01"],
                "costume": {
                    "name": "仓库调查装",
                    "description": "深色冲锋衣与耐磨长裤。",
                    "visual_prompt": "林夏仓库调查服装资产图，深色冲锋衣。",
                },
            }
        ],
        "scenes": [
            {
                "scope_code": "EP01SC01",
                "name": "废弃仓库",
                "description": "潮湿的废弃仓库，金属货架排列成狭窄通道。",
                "spatial_layout": "入口在南侧，录音机位于北侧工作台。",
                "time_weather_light": "雨夜，冷白顶灯闪烁。",
                "key_props": "旧录音机、金属货架",
                "palette_mood": "冷灰蓝，压迫感",
                "visual_prompt": "真人电影感废弃仓库场景资产图，雨夜冷光。",
                "evidence": "雨夜，林夏进入废弃仓库，工作台上放着旧录音机。",
            }
        ],
        "props": [
            {
                "name": "旧录音机",
                "category": "关键剧情道具",
                "description": "布满划痕的便携式磁带录音机。",
                "visual_details": "银灰金属外壳，红色录音键，边角磨损。",
                "visual_prompt": "旧式便携磁带录音机道具资产图，银灰金属，明显划痕。",
                "evidence": "林夏握紧手中的旧录音机。",
                "scene_scope_codes": ["EP01SC01"],
            }
        ],
    }

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            assert "资产清单" in instructions
            assert "林夏" in input_text
            return TextSummaryResult(json.dumps(inventory, ensure_ascii=False), input_tokens=120, output_tokens=80)

        def summarize(self, report_json: str) -> TextSummaryResult:
            return TextSummaryResult("unused")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB",
        encoding="utf-8",
    )
    base_settings = build_settings(tmp_path, prompt_file)
    settings = Settings(
        **{
            **base_settings.__dict__,
            "enable_real_text_analysis": True,
            "text_provider_mode": "huimeng_chat",
            "huimengi_api_key": "hm-test-secret",
            "huimengi_text_model": "gpt-5.5",
        }
    )

    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        project_id = project["id"]
        scene_id = project["episodes"][0]["scenes"][0]["id"]
        source = client.post(
            f"/api/projects/{project_id}/source-files/text",
            json={
                "category": "script_text",
                "title": "仓库剧本",
                "content": "第一场 雨夜废弃仓库\n林夏推开仓库门，握紧手中的旧录音机。",
            },
        ).json()
        client.post(f"/api/source-files/{source['id']}/extract-text")

        blocked = client.post(f"/api/projects/{project_id}/asset-inventory/analyze", json={})
        analyzed = client.post(
            f"/api/projects/{project_id}/asset-inventory/analyze",
            json={"confirm_live_request": True},
        )
        assert analyzed.status_code == 201, analyzed.text
        workspace = analyzed.json()
        requirements = {item["asset_type"]: item for item in workspace["requirements"]}
        assert set(requirements) == {"character", "costume", "scene", "prop"}
        assert requirements["character"]["evidence"].startswith("林夏推开")
        assert requirements["prop"]["scene_ids"] == [scene_id]

        # A locked character master is independently usable when wardrobe is
        # intentionally left to text. It must not be reported as a missing
        # visual asset merely because no separate costume image exists.
        text_only = client.patch(
            f"/api/asset-requirements/{requirements['costume']['id']}",
            json={"reference_mode": "text_only"},
        )
        assert text_only.status_code == 200, text_only.text

        character_requirement = requirements["character"]
        character_upload = client.post(
            f"/api/asset-images/character-master/{character_requirement['target_id']}/upload",
            files={"file": ("character.png", _png_bytes(), "image/png")},
        )
        assert character_upload.status_code == 201, character_upload.text
        character_version = character_upload.json()["characters"][0]["master_versions"][-1]
        character_confirmed = client.post(
            f"/api/asset-versions/character-master/{character_version['id']}/confirm"
        )
        assert character_confirmed.status_code == 200, character_confirmed.text

        partial_bind = client.post(f"/api/projects/{project_id}/assets/auto-bind")
        assert partial_bind.status_code == 200, partial_bind.text
        partial_workspace = partial_bind.json()
        partial_requirements = {
            item["asset_type"]: item for item in partial_workspace["requirements"]
        }
        assert partial_requirements["character"]["status"] == "bound"
        assert partial_requirements["costume"]["status"] == "text_ready"
        assert partial_workspace["bindings"] == []

        visual_costume = client.patch(
            f"/api/asset-requirements/{requirements['costume']['id']}",
            json={"reference_mode": "visual"},
        )
        assert visual_costume.status_code == 200, visual_costume.text

        target_versions: list[tuple[str, dict]] = []
        for kind in ("costume", "scene", "prop"):
            requirement = requirements[kind]
            api_kind = {"character": "character-master", "costume": "costume", "scene": "scene", "prop": "prop"}[kind]
            uploaded = client.post(
                f"/api/asset-images/{api_kind}/{requirement['target_id']}/upload",
                files={"file": (f"{kind}.png", _png_bytes(), "image/png")},
            )
            assert uploaded.status_code == 201, uploaded.text
            updated = uploaded.json()
            if kind == "character":
                version = updated["characters"][0]["master_versions"][-1]
            elif kind == "costume":
                version = updated["characters"][0]["costumes"][0]["versions"][-1]
            elif kind == "scene":
                version = updated["scene_assets"][0]["versions"][-1]
            else:
                version = updated["props"][0]["versions"][-1]
            target_versions.append((api_kind, version))
            confirmed = client.post(f"/api/asset-versions/{api_kind}/{version['id']}/confirm")
            assert confirmed.status_code == 200, confirmed.text

        bound = client.post(f"/api/projects/{project_id}/assets/auto-bind")
        assert bound.status_code == 200, bound.text
        final_workspace = bound.json()

    assert blocked.status_code == 409
    assert len(final_workspace["bindings"]) == 1
    assert final_workspace["bindings"][0]["scope_code"] == "EP01SC01"
    assert len(final_workspace["prop_bindings"]) == 1
    assert final_workspace["prop_bindings"][0]["prop_name"] == "旧录音机"
    assert {item["status"] for item in final_workspace["requirements"]} == {"bound"}


def test_instant_image_provider_submit_saves_version_immediately(tmp_path: Path, monkeypatch) -> None:
    class FakeOpenAIImagesProvider:
        def generate_image(self, base_url, api_key, model_id, prompt, size="1536x1024"):
            assert base_url == "https://images.example.test/v1"
            assert api_key == "sk-instant"
            assert model_id == "gpt-image-1"
            assert "角色资产 Bible" in prompt
            return _png_bytes(), {"data": [{"b64_json": "fake"}]}, {"model": model_id, "prompt": prompt, "size": size}

    monkeypatch.setattr("app.services.assets.OpenAIImagesProvider", FakeOpenAIImagesProvider)
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
        character = create_character(client, project["id"])
        readiness = client.get(f"/api/asset-images/character-master/{character['id']}/readiness")
        submitted = client.post(
            f"/api/asset-images/character-master/{character['id']}/submit",
            json={"confirm_live_request": True},
        )
        job = submitted.json()
        workspace = client.get(f"/api/projects/{project['id']}/assets").json()
        version = workspace["characters"][0]["master_versions"][0]
        image_response = client.get(version["asset_url"])

    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    assert readiness.json()["provider_name"].startswith("gpt-image-1")
    assert submitted.status_code == 201
    assert job["provider"] == "openai_images"
    assert job["status"] == "downloaded"
    assert "sk-instant" not in submitted.text
    # 即时模式不需要查询/下载两步，提交完成时新版本已经建好
    assert version["version_number"] == 1
    assert version["asset_path"].endswith(".png")
    assert image_response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_scene_image_versions_in_same_scope_use_distinct_files(tmp_path: Path, monkeypatch) -> None:
    class FakeOpenAIImagesProvider:
        def generate_image(self, base_url, api_key, model_id, prompt, size="1536x1024"):
            return _png_bytes(), {"data": [{"b64_json": "fake"}]}, {
                "model": model_id,
                "prompt": prompt,
                "size": size,
            }

    monkeypatch.setattr("app.services.assets.OpenAIImagesProvider", FakeOpenAIImagesProvider)
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB",
        encoding="utf-8",
    )
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
        scene_id = project["episodes"][0]["scenes"][0]["id"]
        first_workspace = client.post(
            f"/api/scenes/{scene_id}/assets",
            json={"name": "红泥坡训练场", "description": "清晨红泥坡"},
        ).json()
        first_id = first_workspace["scene_assets"][0]["id"]
        second_workspace = client.post(
            f"/api/scenes/{scene_id}/assets",
            json={"name": "工厂检测空间", "description": "工业检测空间"},
        ).json()
        second_id = next(
            item["id"]
            for item in second_workspace["scene_assets"]
            if item["name"] == "工厂检测空间"
        )

        client.post(
            f"/api/asset-images/scene/{first_id}/submit",
            json={"confirm_live_request": True},
        )
        client.post(
            f"/api/asset-images/scene/{second_id}/submit",
            json={"confirm_live_request": True},
        )
        workspace = client.get(f"/api/projects/{project['id']}/assets").json()

    paths = {
        asset["name"]: asset["versions"][0]["asset_path"]
        for asset in workspace["scene_assets"]
    }
    assert paths["红泥坡训练场"] != paths["工厂检测空间"]


def test_ai_inventory_creates_separate_scene_assets_per_location(tmp_path: Path, monkeypatch) -> None:
    inventory = {
        "characters": [],
        "scenes": [
            {
                "scope_code": "EP01SC01",
                "name": "红泥坡训练场",
                "description": "清晨森林中的湿滑红泥坡道。",
                "visual_prompt": "红泥坡训练场场景资产图。",
            },
            {
                "scope_code": "EP01SC01",
                "name": "工厂检测空间",
                "description": "冷峻金属光的工业制造与检测空间。",
                "visual_prompt": "工厂检测空间场景资产图。",
            },
        ],
        "props": [
            {
                "name": "普通路边警示带",
                "category": "环境细节",
                "description": "坡道边缘偶尔出现的普通警示带。",
                "reference_mode": "text_only",
                "importance_reason": "只承担环境信息，不需要跨镜头锁定外观。",
                "text_prompt": "坡道边缘可自然出现少量普通警示带，不固定颜色与具体造型。",
                "scene_scope_codes": ["EP01SC01"],
            }
        ],
    }

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(json.dumps(inventory, ensure_ascii=False), input_tokens=10, output_tokens=10)

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB",
        encoding="utf-8",
    )
    base_settings = build_settings(tmp_path, prompt_file)
    settings = Settings(
        **{
            **base_settings.__dict__,
            "enable_real_text_analysis": True,
            "text_provider_mode": "huimeng_chat",
            "huimengi_api_key": "hm-test-secret",
            "huimengi_text_model": "gpt-5.5",
        }
    )

    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        project_id = project["id"]
        source = client.post(
            f"/api/projects/{project_id}/source-files/text",
            json={"category": "script_text", "title": "两个场景", "content": "红泥坡训练场与工厂检测空间。"},
        ).json()
        client.post(f"/api/source-files/{source['id']}/extract-text")
        analyzed = client.post(
            f"/api/projects/{project_id}/asset-inventory/analyze",
            json={"confirm_live_request": True},
        )
        assert analyzed.status_code == 201, analyzed.text
        workspace = analyzed.json()

        scene_requirements = [item for item in workspace["requirements"] if item["asset_type"] == "scene"]
        scene_assets = workspace["scene_assets"]
        target_ids = {item["target_id"] for item in scene_requirements}
        text_requirement = next(
            item for item in workspace["requirements"] if item["name"] == "普通路边警示带"
        )

        # 同一场次下的两个不同地点必须各自建档，不能再合并成同一份场景资产
        assert len(scene_requirements) == 2
        assert len(scene_assets) == 2
        assert len(target_ids) == 2
        assert {asset["name"] for asset in scene_assets} == {"红泥坡训练场", "工厂检测空间"}
        assert text_requirement["reference_mode"] == "text_only"
        assert text_requirement["status"] == "text_ready"
        assert text_requirement["text_prompt"].startswith("坡道边缘可自然出现")

        # 各自独立生成版本，互不影响
        first = scene_assets[0]
        second = scene_assets[1]
        client.post(f"/api/scene-assets/{first['id']}/versions")
        workspace_after = client.get(f"/api/projects/{project_id}/assets").json()
        after_assets = {asset["id"]: asset for asset in workspace_after["scene_assets"]}

    # 占位版本接口已停用（410），但两个资产仍然各自独立存在
    assert set(after_assets) == {first["id"], second["id"]}
