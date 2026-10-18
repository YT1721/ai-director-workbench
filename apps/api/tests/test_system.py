from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.config as app_config
from app.config import DEFAULT_SYSTEM_PROMPT, REPO_ROOT, Settings
from app.main import create_app
from app.services.system_prompt import load_system_prompt_status


SYSTEM_PROMPT_FILENAME = (
    "剧本视觉化创作系统_V7.0_Plus_R1_当前主版本.txt"
)
SYSTEM_PROMPT_TEST_CONTENT = (
    "剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV "
    "VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器"
)


def build_settings(tmp_path: Path, prompt_file: Path) -> Settings:
    return Settings(
        repo_root=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        projects_root=tmp_path / "projects",
        system_prompt_file=prompt_file,
        provider_mode="huimeng_live",
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        cors_origins=("http://localhost:3000",),
    )


def test_health_initializes_sqlite_and_reports_loaded_prompt(tmp_path: Path) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(SYSTEM_PROMPT_TEST_CONTENT, encoding="utf-8")

    with TestClient(create_app(build_settings(tmp_path, prompt_file))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "initialized"
    assert body["provider_mode"] == "huimeng_live"
    assert body["system_prompt"]["loaded"] is True
    assert body["system_prompt"]["filename"] == SYSTEM_PROMPT_FILENAME
    assert body["system_prompt"]["version"] == "V7.0 Plus R1｜UCODE-9 + FLOW-NAV + VP-PRECISION-18 + DIRECTOR-TECH PLUS + UNIFIED-SB"
    assert body["system_prompt"]["provider_mode"] == "huimeng_live"
    assert body["system_prompt"]["error"] is None
    assert body["system_prompt"]["last_updated"]
    assert (tmp_path / "app.db").exists()
    assert (tmp_path / "projects").is_dir()


def test_settings_rejects_unknown_video_mode_by_falling_back_to_jimeng(monkeypatch) -> None:
    monkeypatch.setattr(app_config, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("VIDEO_PROVIDER_MODE", "unsupported_mode")

    settings = Settings.from_environment()

    assert settings.provider_mode == "jimeng_cli"


def test_settings_defaults_to_real_generation_modes(monkeypatch) -> None:
    monkeypatch.setattr(app_config, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("TEXT_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("ENABLE_REAL_TEXT_ANALYSIS", raising=False)
    monkeypatch.delenv("VIDEO_PROVIDER_MODE", raising=False)

    settings = Settings.from_environment()

    assert settings.text_provider_mode == "huimeng_chat"
    assert settings.enable_real_text_analysis is True
    assert settings.provider_mode == "jimeng_cli"


def test_settings_ignores_legacy_disabled_real_text(monkeypatch) -> None:
    monkeypatch.setattr(app_config, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("ENABLE_REAL_TEXT_ANALYSIS", "false")

    settings = Settings.from_environment()

    assert settings.enable_real_text_analysis is True


def test_prompt_status_degrades_when_file_is_missing(tmp_path: Path) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME

    with TestClient(create_app(build_settings(tmp_path, prompt_file))) as client:
        response = client.get("/api/system-prompt/status")

    assert response.status_code == 200
    assert response.json()["loaded"] is False
    assert "不存在" in response.json()["error"]


def test_prompt_status_never_returns_prompt_body(tmp_path: Path) -> None:
    secret_marker = "THIS_PROMPT_BODY_MUST_NOT_LEAK"
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text(
        f"剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 {secret_marker}",
        encoding="utf-8",
    )

    with TestClient(create_app(build_settings(tmp_path, prompt_file))) as client:
        response = client.get("/api/system-prompt/status")

    assert response.status_code == 200
    assert secret_marker not in response.text


def test_default_repo_prompt_points_to_existing_main_version() -> None:
    prompt_file = REPO_ROOT / DEFAULT_SYSTEM_PROMPT
    status = load_system_prompt_status(prompt_file, "huimeng_live")

    assert prompt_file.exists()
    assert status.loaded is True
    assert status.filename == SYSTEM_PROMPT_FILENAME


def test_local_env_status_never_returns_secret_values(tmp_path: Path) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    settings = build_settings(tmp_path, prompt_file)
    settings = Settings(
        **{
            **settings.__dict__,
            "openai_api_key": "sk-test-secret",
            "huimengi_api_key": "hm-test-secret",
            "openai_model_routine": "gpt-test",
        }
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/local-env/status")

    assert response.status_code == 200
    body = response.json()
    assert body["openai_api_key_configured"] is True
    assert body["huimengi_api_key_configured"] is True
    assert "sk-test-secret" not in response.text
    assert "hm-test-secret" not in response.text


def test_text_service_env_vars_override_huimeng_fallback(tmp_path: Path, monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setattr(app_config, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("HUIMENGI_API_KEY", "hm-shared-key")
    monkeypatch.setenv("HUIMENGI_TEXT_BASE_URL", "https://api.huimengi.com/v1")
    monkeypatch.setenv("HUIMENGI_TEXT_MODEL", "gpt-5.5")
    monkeypatch.setenv("TEXT_API_KEY", "sk-kimi-key")
    monkeypatch.setenv("TEXT_BASE_URL", "https://api.moonshot.cn/v1/")
    monkeypatch.setenv("TEXT_MODEL", "kimi-k2-0905-preview")
    overridden = Settings.from_environment()
    monkeypatch.delenv("TEXT_API_KEY")
    monkeypatch.delenv("TEXT_BASE_URL")
    monkeypatch.delenv("TEXT_MODEL")
    fallback = Settings.from_environment()

    assert overridden.text_api_key == "sk-kimi-key"
    assert overridden.text_base_url == "https://api.moonshot.cn/v1"
    assert overridden.text_model == "kimi-k2-0905-preview"
    assert overridden.huimengi_api_key == "hm-shared-key"
    assert fallback.text_api_key == "hm-shared-key"
    assert fallback.text_base_url == "https://api.huimengi.com/v1"
    assert fallback.text_model == "gpt-5.5"


def test_text_provider_status_labels_known_service(tmp_path: Path) -> None:
    from app.services.ai_text import text_provider_status, text_service_label

    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    settings = build_settings(tmp_path, prompt_file)
    kimi_settings = Settings(
        **{
            **settings.__dict__,
            "text_api_key": "sk-kimi-key",
            "text_base_url": "https://api.moonshot.cn/v1",
            "text_model": "kimi-k2-0905-preview",
        }
    )
    status = text_provider_status(kimi_settings)

    assert text_service_label("https://api.moonshot.cn/v1") == "Kimi"
    assert text_service_label("https://api.deepseek.com/v1") == "DeepSeek"
    assert text_service_label("https://open.bigmodel.cn/api/paas/v4") == "智谱 GLM"
    assert text_service_label("https://generativelanguage.googleapis.com/v1beta/openai") == "Gemini"
    assert text_service_label("https://example.com/v1") == "自定义服务"
    assert status.text_service_label == "Kimi"
    assert status.mode_label == "Kimi 文本通道（kimi-k2-0905-preview）"
    assert status.text_api_key_configured is True
    assert status.ready is True


def test_local_env_update_writes_text_service_keys(tmp_path: Path) -> None:
    from app.schemas.local_env import LocalEnvUpdate
    from app.services.local_env import build_env_updates

    updates = build_env_updates(LocalEnvUpdate(
        confirm_local_env_write=True,
        text_api_key="sk-kimi-key",
        text_base_url="https://api.moonshot.cn/v1/",
        text_model="kimi-k2-0905-preview",
    ))

    assert updates["TEXT_API_KEY"] == "sk-kimi-key"
    assert updates["TEXT_BASE_URL"] == "https://api.moonshot.cn/v1"
    assert updates["TEXT_MODEL"] == "kimi-k2-0905-preview"


def test_local_env_update_requires_confirmation(tmp_path: Path) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")

    with TestClient(create_app(build_settings(tmp_path, prompt_file))) as client:
        response = client.patch("/api/local-env", json={"openai_model_routine": "gpt-test"})

    assert response.status_code == 409
    assert not (tmp_path / ".env").exists()


def test_local_env_rejects_unsupported_video_mode(tmp_path: Path) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    settings = build_settings(tmp_path, prompt_file)

    with TestClient(create_app(settings)) as client:
        response = client.patch(
            "/api/local-env",
            json={
                "confirm_local_env_write": True,
                "video_provider_mode": "unsupported_mode",
            },
        )

    assert response.status_code == 400
    assert not (tmp_path / ".env").exists()


def test_local_env_respects_text_analysis_toggle(tmp_path: Path) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    settings = build_settings(tmp_path, prompt_file)

    with TestClient(create_app(settings)) as client:
        response = client.patch(
            "/api/local-env",
            json={
                "confirm_local_env_write": True,
                "enable_real_text_analysis": False,
            },
        )

    assert response.status_code == 200
    assert response.json()["enable_real_text_analysis"] is False
    assert "ENABLE_REAL_TEXT_ANALYSIS=false" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_local_env_update_preserves_unknown_fields_and_refreshes_status(tmp_path: Path, monkeypatch) -> None:
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_TEXT_MODEL",
        "OPENAI_MODEL_ROUTINE",
        "OPENAI_IMAGE_MODEL",
        "ENABLE_REAL_OPENAI",
        "HUIMENGI_API_KEY",
        "HUIMENGI_TEXT_BASE_URL",
        "HUIMENGI_TEXT_MODEL",
        "HUIMENGI_IMAGE_BASE_URL",
        "HUIMENGI_IMAGE_MODEL",
        "HUIMENGI_VIDEO_BASE_URL",
        "HUIMENGI_VIDEO_MODEL",
        "HUIMENGI_BASE_URL",
        "HUIMENGI_MODEL_ID",
        "ENABLE_REAL_SEEDANCE",
        "VIDEO_PROVIDER_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# keep comment\nUNKNOWN_FLAG=keep-me\nOPENAI_API_KEY=old-openai-secret\nHUIMENGI_API_KEY=old-huimeng-secret\n",
        encoding="utf-8",
    )
    settings = build_settings(tmp_path, prompt_file)
    settings = Settings(
        **{
            **settings.__dict__,
            "openai_api_key": "old-openai-secret",
            "huimengi_api_key": "old-huimeng-secret",
        }
    )

    with TestClient(create_app(settings)) as client:
        response = client.patch(
            "/api/local-env",
            json={
                "confirm_local_env_write": True,
                "openai_api_key": "",
                "openai_model_routine": "gpt-4.1-mini",
                "openai_image_model": "gpt-image-test",
                "enable_real_openai": True,
                "huimengi_api_key": "new-huimeng-secret",
                "huimengi_text_base_url": "https://api.huimengi.com/v1/",
                "huimengi_text_model": "gpt-5.5",
                "huimengi_image_base_url": "https://api.huimengi.com/",
                "huimengi_image_model": "image-2",
                "huimengi_video_base_url": "https://api.huimengi.com/",
                "huimengi_video_model": "seedance-2.0-fast",
                "enable_real_seedance": True,
                "video_provider_mode": "huimeng_live",
            },
        )
        ai_status = client.get("/api/ai-provider/status")
        live_status = client.get("/api/video-provider-live-status")

    assert response.status_code == 200
    assert response.json()["openai_api_key_configured"] is True
    assert response.json()["huimengi_api_key_configured"] is True
    assert "old-openai-secret" not in response.text
    assert "new-huimeng-secret" not in response.text
    saved = env_file.read_text(encoding="utf-8")
    assert "# keep comment" in saved
    assert "UNKNOWN_FLAG=keep-me" in saved
    assert "OPENAI_API_KEY=old-openai-secret" in saved
    assert "OPENAI_TEXT_MODEL=gpt-4.1-mini" in saved
    assert "OPENAI_MODEL_ROUTINE=gpt-4.1-mini" in saved
    assert "OPENAI_IMAGE_MODEL=gpt-image-test" in saved
    assert "HUIMENGI_API_KEY=new-huimeng-secret" in saved
    assert "HUIMENGI_TEXT_MODEL=gpt-5.5" in saved
    assert "HUIMENGI_IMAGE_MODEL=image-2" in saved
    assert "HUIMENGI_VIDEO_MODEL=seedance-2.0-fast" in saved
    assert "HUIMENGI_MODEL_ID=seedance-2.0-fast" in saved
    assert ai_status.json()["real_openai_enabled"] is True
    assert ai_status.json()["routine_model"] == "gpt-4.1-mini"
    assert live_status.json()["provider_mode"] == "huimeng_live"
    assert live_status.json()["real_seedance_enabled"] is True
    assert live_status.json()["huimengi_base_url"] == "https://api.huimengi.com"
    assert live_status.json()["huimengi_video_model"] == "seedance-2.0-fast"


def test_image_service_env_vars_override_and_mode_aware_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HUIMENGI_API_KEY", "hm-shared-key")
    monkeypatch.setenv("HUIMENGI_IMAGE_BASE_URL", "https://api.huimengi.com")
    monkeypatch.setenv("HUIMENGI_IMAGE_MODEL", "image-2")
    monkeypatch.setenv("IMAGE_PROVIDER_MODE", "huimeng_tasks")
    fallback = Settings.from_environment()

    monkeypatch.setenv("IMAGE_PROVIDER_MODE", "openai_images")
    monkeypatch.setenv("IMAGE_API_KEY", "sk-img-key")
    monkeypatch.setenv("IMAGE_BASE_URL", "https://api.openai.com/v1/")
    monkeypatch.setenv("IMAGE_MODEL", "gpt-image-1")
    overridden = Settings.from_environment()

    monkeypatch.delenv("IMAGE_API_KEY")
    monkeypatch.delenv("IMAGE_BASE_URL")
    monkeypatch.delenv("IMAGE_MODEL")
    unconfigured = Settings.from_environment()

    assert fallback.image_provider_mode == "huimeng_tasks"
    assert fallback.image_api_key == "hm-shared-key"
    assert fallback.image_base_url == "https://api.huimengi.com"
    assert fallback.image_model == "image-2"
    assert overridden.image_provider_mode == "openai_images"
    assert overridden.image_api_key == "sk-img-key"
    assert overridden.image_base_url == "https://api.openai.com/v1"
    assert overridden.image_model == "gpt-image-1"
    # 即时 API 模式不做慧梦回退；未配置时保持为空，由就绪检查明确提示
    assert unconfigured.image_provider_mode == "openai_images"
    assert unconfigured.image_api_key == ""
    assert unconfigured.image_base_url == ""
    assert unconfigured.image_model == ""


def test_local_env_update_writes_image_service_keys(tmp_path: Path) -> None:
    from app.schemas.local_env import LocalEnvUpdate
    from app.services.local_env import build_env_updates

    updates = build_env_updates(LocalEnvUpdate(
        confirm_local_env_write=True,
        image_provider_mode="openai_images",
        image_api_key="sk-img-key",
        image_base_url="https://api.openai.com/v1/",
        image_model="gpt-image-1",
    ))

    assert updates["IMAGE_PROVIDER_MODE"] == "openai_images"
    assert updates["IMAGE_API_KEY"] == "sk-img-key"
    assert updates["IMAGE_BASE_URL"] == "https://api.openai.com/v1"
    assert updates["IMAGE_MODEL"] == "gpt-image-1"


def test_local_env_rejects_unsupported_image_mode(tmp_path: Path) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    settings = build_settings(tmp_path, prompt_file)

    with TestClient(create_app(settings)) as client:
        response = client.patch(
            "/api/local-env",
            json={
                "confirm_local_env_write": True,
                "image_provider_mode": "mock",
            },
        )

    assert response.status_code == 400
    assert not (tmp_path / ".env").exists()


def test_scene_asset_migration_upgrades_old_schema(tmp_path: Path) -> None:
    import sqlalchemy
    from app.database import _ensure_scene_asset_columns

    engine = sqlalchemy.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(sqlalchemy.text("""
            CREATE TABLE scene_assets (
                id VARCHAR NOT NULL PRIMARY KEY,
                scene_id VARCHAR NOT NULL,
                description VARCHAR NOT NULL DEFAULT '',
                spatial_layout VARCHAR NOT NULL DEFAULT '',
                time_weather_light VARCHAR NOT NULL DEFAULT '',
                key_props VARCHAR NOT NULL DEFAULT '',
                palette_mood VARCHAR NOT NULL DEFAULT '',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        connection.execute(sqlalchemy.text("CREATE UNIQUE INDEX ix_scene_assets_scene_id ON scene_assets (scene_id)"))
        connection.execute(sqlalchemy.text(
            "INSERT INTO scene_assets (id, scene_id, created_at, updated_at) VALUES ('a1', 's1', '2026-01-01', '2026-01-01')"
        ))

    _ensure_scene_asset_columns(engine)

    with engine.connect() as connection:
        inspector = sqlalchemy.inspect(connection)
        columns = {item["name"] for item in inspector.get_columns("scene_assets")}
        indexes = inspector.get_indexes("scene_assets")
        row = connection.execute(sqlalchemy.text("SELECT id, scene_id, name FROM scene_assets")).first()

    assert "name" in columns
    assert not any(
        index.get("unique") and "scene_id" in list(index.get("column_names") or [])
        for index in indexes
    )
    assert any(index["name"] == "ix_scene_assets_scene_id" for index in indexes)
    assert row == ("a1", "s1", "")
