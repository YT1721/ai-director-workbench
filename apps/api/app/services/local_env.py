from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import HTTPException

from app.config import Settings, _normalize_text_provider_mode, _normalize_video_provider_mode
from app.schemas.local_env import LocalEnvStatusView, LocalEnvUpdate
from app.services.ai_text import text_service_label
from app.services.system_prompt import load_system_prompt_status


SECRET_KEYS = {"OPENAI_API_KEY", "HUIMENGI_API_KEY", "SEEDANCE_AGGREGATOR_API_KEY", "TEXT_API_KEY", "IMAGE_API_KEY"}
UPDATABLE_ENV_KEYS = {
    "OPENAI_API_KEY",
    "OPENAI_MODEL_DIRECTOR",
    "OPENAI_TEXT_MODEL",
    "OPENAI_MODEL_ROUTINE",
    "OPENAI_IMAGE_MODEL",
    "OPENAI_IMAGE_MODEL_PRODUCTION",
    "OPENAI_IMAGE_MODEL_DRAFT",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "TEXT_PROVIDER_MODE",
    "AUTO_RUN_TEXT_TASKS",
    "ENABLE_REAL_TEXT_ANALYSIS",
    "ENABLE_REAL_OPENAI",
    "ENABLE_REAL_IMAGE_GENERATION",
    "IMAGE_REAL_SUBMIT_ENABLED",
    "HUIMENGI_API_KEY",
    "HUIMENGI_TEXT_BASE_URL",
    "HUIMENGI_TEXT_MODEL",
    "TEXT_API_KEY",
    "TEXT_BASE_URL",
    "TEXT_MODEL",
    "IMAGE_PROVIDER_MODE",
    "IMAGE_API_KEY",
    "IMAGE_BASE_URL",
    "IMAGE_MODEL",
    "HUIMENGI_IMAGE_BASE_URL",
    "HUIMENGI_IMAGE_MODEL",
    "HUIMENGI_VIDEO_BASE_URL",
    "HUIMENGI_VIDEO_MODEL",
    "HUIMENGI_BASE_URL",
    "HUIMENGI_MODEL_ID",
    "ENABLE_REAL_SEEDANCE",
    "SEEDANCE_REAL_SUBMIT_ENABLED",
    "VIDEO_PROVIDER_MODE",
    "DEFAULT_VIDEO_PROVIDER_ID",
    "SEEDANCE_AGGREGATOR_API_KEY",
    "SEEDANCE_AGGREGATOR_BASE_URL",
    "SEEDANCE_AGGREGATOR_CREATE_TASK_PATH",
    "SEEDANCE_AGGREGATOR_GET_TASK_PATH_TEMPLATE",
    "SEEDANCE_AGGREGATOR_CANCEL_TASK_PATH_TEMPLATE",
    "SEEDANCE_AGGREGATOR_AUTH_TYPE",
    "SEEDANCE_AGGREGATOR_AUTH_HEADER",
    "SEEDANCE_AGGREGATOR_AUTH_PREFIX",
    "SEEDANCE_AGGREGATOR_MODEL_ID",
}


def local_env_status(settings: Settings) -> LocalEnvStatusView:
    env_file = settings.repo_root / ".env"
    return LocalEnvStatusView(
        openai_api_key_configured=bool(settings.openai_api_key),
        openai_model_director=settings.openai_model_director,
        openai_text_model=settings.openai_text_model,
        openai_model_routine=settings.openai_model_routine,
        openai_image_model_production=settings.openai_image_model_production,
        openai_image_model_draft=settings.openai_image_model_draft,
        openai_image_model=settings.openai_image_model,
        openai_max_output_tokens=settings.openai_max_output_tokens,
        text_provider_mode=settings.text_provider_mode,
        enable_real_text_analysis=settings.enable_real_text_analysis,
        enable_real_openai=settings.enable_real_openai,
        enable_real_image_generation=settings.enable_real_image_generation,
        huimengi_api_key_configured=bool(settings.huimengi_api_key),
        huimengi_text_base_url=settings.huimengi_text_base_url,
        huimengi_text_model=settings.huimengi_text_model,
        text_api_key_configured=bool(settings.text_api_key),
        text_base_url=settings.text_base_url,
        text_model=settings.text_model,
        text_service_label=text_service_label(settings.text_base_url),
        # 状态只回报用户显式配置的 IMAGE_* 原值；慧梦任务制下的回退值不回显，避免误导保存。
        image_provider_mode=settings.image_provider_mode,
        image_api_key_configured=bool(os.getenv("IMAGE_API_KEY", "").strip()),
        image_base_url=os.getenv("IMAGE_BASE_URL", "").rstrip("/"),
        image_model=os.getenv("IMAGE_MODEL", ""),
        huimengi_image_base_url=settings.huimengi_image_base_url,
        huimengi_image_model=settings.huimengi_image_model,
        huimengi_video_base_url=settings.huimengi_video_base_url,
        huimengi_video_model=settings.huimengi_video_model,
        huimengi_base_url=settings.huimengi_base_url,
        huimengi_model_id=settings.huimengi_model_id,
        enable_real_seedance=settings.enable_real_seedance,
        seedance_real_submit_enabled=settings.seedance_real_submit_enabled,
        video_provider_mode=settings.provider_mode,
        default_video_provider_id=settings.default_video_provider_id,
        seedance_aggregator_base_url=settings.seedance_aggregator_base_url,
        seedance_aggregator_create_task_path=settings.seedance_aggregator_create_task_path,
        seedance_aggregator_get_task_path_template=settings.seedance_aggregator_get_task_path_template,
        seedance_aggregator_auth_type=settings.seedance_aggregator_auth_type,
        seedance_aggregator_auth_header=settings.seedance_aggregator_auth_header,
        seedance_aggregator_auth_prefix=settings.seedance_aggregator_auth_prefix,
        seedance_aggregator_model_id=settings.seedance_aggregator_model_id,
        seedance_aggregator_api_key_configured=bool(settings.seedance_aggregator_api_key),
        env_file_exists=env_file.exists(),
        env_file_path=str(env_file),
        secret_policy="密钥只写入本机 .env；接口只返回是否已配置，不返回密钥正文。",
    )


def build_env_updates(payload: LocalEnvUpdate) -> dict[str, str]:
    if not payload.confirm_local_env_write:
        raise HTTPException(409, "写入本地 .env 需要明确确认。")
    updates: dict[str, str] = {}
    if payload.openai_api_key.strip():
        updates["OPENAI_API_KEY"] = payload.openai_api_key.strip()
    if payload.openai_model_director.strip():
        updates["OPENAI_MODEL_DIRECTOR"] = payload.openai_model_director.strip()
    if payload.openai_text_model.strip():
        model = payload.openai_text_model.strip()
        updates["OPENAI_TEXT_MODEL"] = model
        updates["OPENAI_MODEL_ROUTINE"] = model
    if payload.openai_model_routine.strip():
        model = payload.openai_model_routine.strip()
        updates["OPENAI_TEXT_MODEL"] = model
        updates["OPENAI_MODEL_ROUTINE"] = model
    if payload.openai_image_model.strip():
        updates["OPENAI_IMAGE_MODEL"] = payload.openai_image_model.strip()
        updates["OPENAI_IMAGE_MODEL_PRODUCTION"] = payload.openai_image_model.strip()
    if payload.openai_image_model_production.strip():
        updates["OPENAI_IMAGE_MODEL_PRODUCTION"] = payload.openai_image_model_production.strip()
        updates["OPENAI_IMAGE_MODEL"] = payload.openai_image_model_production.strip()
    if payload.openai_image_model_draft.strip():
        updates["OPENAI_IMAGE_MODEL_DRAFT"] = payload.openai_image_model_draft.strip()
    if payload.openai_max_output_tokens is not None:
        updates["OPENAI_MAX_OUTPUT_TOKENS"] = str(payload.openai_max_output_tokens)
    if payload.text_provider_mode.strip():
        mode = _normalize_text_provider_mode(payload.text_provider_mode.strip())
        if mode not in {"huimeng_chat", "openai_responses"}:
            raise HTTPException(400, "TEXT_PROVIDER_MODE 只允许 huimeng_chat 或 openai_responses。")
        updates["TEXT_PROVIDER_MODE"] = mode
    if payload.enable_real_text_analysis is not None:
        updates["ENABLE_REAL_TEXT_ANALYSIS"] = str(payload.enable_real_text_analysis).lower()
    if payload.enable_real_openai is not None:
        updates["ENABLE_REAL_OPENAI"] = str(payload.enable_real_openai).lower()
    if payload.enable_real_image_generation is not None:
        enabled = str(payload.enable_real_image_generation).lower()
        updates["ENABLE_REAL_IMAGE_GENERATION"] = enabled
        updates["IMAGE_REAL_SUBMIT_ENABLED"] = enabled
    if payload.huimengi_api_key.strip():
        updates["HUIMENGI_API_KEY"] = payload.huimengi_api_key.strip()
    if payload.text_api_key.strip():
        updates["TEXT_API_KEY"] = payload.text_api_key.strip()
    if payload.text_base_url.strip():
        updates["TEXT_BASE_URL"] = payload.text_base_url.strip().rstrip("/")
    if payload.text_model.strip():
        updates["TEXT_MODEL"] = payload.text_model.strip()
    if payload.image_provider_mode.strip():
        mode = payload.image_provider_mode.strip()
        if mode not in {"huimeng_tasks", "openai_images"}:
            raise HTTPException(400, "IMAGE_PROVIDER_MODE 只允许 huimeng_tasks 或 openai_images。")
        updates["IMAGE_PROVIDER_MODE"] = mode
    if payload.image_api_key.strip():
        updates["IMAGE_API_KEY"] = payload.image_api_key.strip()
    if payload.image_base_url.strip():
        updates["IMAGE_BASE_URL"] = payload.image_base_url.strip().rstrip("/")
    if payload.image_model.strip():
        updates["IMAGE_MODEL"] = payload.image_model.strip()
    if payload.huimengi_text_base_url.strip():
        updates["HUIMENGI_TEXT_BASE_URL"] = payload.huimengi_text_base_url.strip().rstrip("/")
    if payload.huimengi_text_model.strip():
        updates["HUIMENGI_TEXT_MODEL"] = payload.huimengi_text_model.strip()
    if payload.huimengi_image_base_url.strip():
        updates["HUIMENGI_IMAGE_BASE_URL"] = payload.huimengi_image_base_url.strip().rstrip("/")
    if payload.huimengi_image_model.strip():
        updates["HUIMENGI_IMAGE_MODEL"] = payload.huimengi_image_model.strip()
    if payload.huimengi_video_base_url.strip():
        base_url = payload.huimengi_video_base_url.strip().rstrip("/")
        updates["HUIMENGI_VIDEO_BASE_URL"] = base_url
        updates["HUIMENGI_BASE_URL"] = base_url
    if payload.huimengi_video_model.strip():
        model = payload.huimengi_video_model.strip()
        updates["HUIMENGI_VIDEO_MODEL"] = model
        updates["HUIMENGI_MODEL_ID"] = model
    if payload.huimengi_base_url.strip():
        base_url = payload.huimengi_base_url.strip().rstrip("/")
        updates["HUIMENGI_VIDEO_BASE_URL"] = base_url
        updates["HUIMENGI_BASE_URL"] = base_url
    if payload.huimengi_model_id.strip():
        model = payload.huimengi_model_id.strip()
        updates["HUIMENGI_VIDEO_MODEL"] = model
        updates["HUIMENGI_MODEL_ID"] = model
    if payload.enable_real_seedance is not None:
        enabled = str(payload.enable_real_seedance).lower()
        updates["ENABLE_REAL_SEEDANCE"] = enabled
        updates["SEEDANCE_REAL_SUBMIT_ENABLED"] = enabled
    if payload.seedance_real_submit_enabled is not None:
        enabled = str(payload.seedance_real_submit_enabled).lower()
        updates["SEEDANCE_REAL_SUBMIT_ENABLED"] = enabled
        updates["ENABLE_REAL_SEEDANCE"] = enabled
    if payload.video_provider_mode.strip():
        mode = payload.video_provider_mode.strip()
        if mode not in {"huimeng_live", "jimeng_cli"}:
            raise HTTPException(400, "VIDEO_PROVIDER_MODE 只允许 huimeng_live 或 jimeng_cli。")
        updates["VIDEO_PROVIDER_MODE"] = mode
    if payload.default_video_provider_id.strip():
        updates["DEFAULT_VIDEO_PROVIDER_ID"] = payload.default_video_provider_id.strip()
    if payload.seedance_aggregator_api_key.strip():
        updates["SEEDANCE_AGGREGATOR_API_KEY"] = payload.seedance_aggregator_api_key.strip()
    if payload.seedance_aggregator_base_url.strip():
        updates["SEEDANCE_AGGREGATOR_BASE_URL"] = payload.seedance_aggregator_base_url.strip().rstrip("/")
    if payload.seedance_aggregator_create_task_path.strip():
        updates["SEEDANCE_AGGREGATOR_CREATE_TASK_PATH"] = payload.seedance_aggregator_create_task_path.strip()
    if payload.seedance_aggregator_get_task_path_template.strip():
        updates["SEEDANCE_AGGREGATOR_GET_TASK_PATH_TEMPLATE"] = payload.seedance_aggregator_get_task_path_template.strip()
    if payload.seedance_aggregator_auth_type.strip():
        updates["SEEDANCE_AGGREGATOR_AUTH_TYPE"] = payload.seedance_aggregator_auth_type.strip()
    if payload.seedance_aggregator_auth_header.strip():
        updates["SEEDANCE_AGGREGATOR_AUTH_HEADER"] = payload.seedance_aggregator_auth_header.strip()
    if payload.seedance_aggregator_auth_prefix:
        updates["SEEDANCE_AGGREGATOR_AUTH_PREFIX"] = payload.seedance_aggregator_auth_prefix
    if payload.seedance_aggregator_model_id.strip():
        updates["SEEDANCE_AGGREGATOR_MODEL_ID"] = payload.seedance_aggregator_model_id.strip()
    unknown = set(updates) - UPDATABLE_ENV_KEYS
    if unknown:
        raise HTTPException(400, f"不允许写入这些环境变量：{', '.join(sorted(unknown))}")
    return updates


def write_local_env(env_file: Path, updates: dict[str, str]) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else [
        "# AI导演工作台本地配置",
        "# 由设置页写入；不要提交真实密钥。",
    ]
    seen: set[str] = set()
    next_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            next_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            next_lines.append(line)
    missing = [key for key in updates if key not in seen]
    if missing and next_lines and next_lines[-1].strip():
        next_lines.append("")
    for key in missing:
        next_lines.append(f"{key}={updates[key]}")

    fd, temp_name = tempfile.mkstemp(prefix=".env.", dir=str(env_file.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            temp_file.write("\n".join(next_lines).rstrip() + "\n")
        os.replace(temp_name, env_file)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def refresh_settings(current: Settings, updates: dict[str, str]) -> Settings:
    for key, value in updates.items():
        os.environ[key] = value
    openai_text_model = os.getenv("OPENAI_TEXT_MODEL") or os.getenv("OPENAI_MODEL_ROUTINE", current.openai_text_model)
    openai_image_model_production = os.getenv("OPENAI_IMAGE_MODEL_PRODUCTION") or os.getenv("OPENAI_IMAGE_MODEL", current.openai_image_model_production)
    openai_image_model_draft = os.getenv("OPENAI_IMAGE_MODEL_DRAFT", current.openai_image_model_draft or openai_image_model_production)
    huimengi_video_base_url = (
        os.getenv("HUIMENGI_VIDEO_BASE_URL")
        or os.getenv("HUIMENGI_BASE_URL", current.huimengi_video_base_url)
    ).rstrip("/")
    huimengi_video_model = (
        os.getenv("HUIMENGI_VIDEO_MODEL")
        or os.getenv("HUIMENGI_MODEL_ID", current.huimengi_video_model)
    )
    return Settings(
        repo_root=current.repo_root,
        database_url=current.database_url,
        projects_root=current.projects_root,
        system_prompt_file=current.system_prompt_file,
        provider_mode=_normalize_video_provider_mode(os.getenv("VIDEO_PROVIDER_MODE", current.provider_mode)),
        cors_origins=current.cors_origins,
        max_video_tasks_per_batch=current.max_video_tasks_per_batch,
        text_provider_mode=_normalize_text_provider_mode(os.getenv("TEXT_PROVIDER_MODE", current.text_provider_mode)),
        text_api_key=os.getenv("TEXT_API_KEY", current.text_api_key),
        text_base_url=os.getenv("TEXT_BASE_URL", current.text_base_url).rstrip("/"),
        text_model=os.getenv("TEXT_MODEL", current.text_model),
        image_provider_mode=os.getenv("IMAGE_PROVIDER_MODE", current.image_provider_mode),
        image_api_key=os.getenv("IMAGE_API_KEY", ""),
        image_base_url=os.getenv("IMAGE_BASE_URL", "").rstrip("/"),
        image_model=os.getenv("IMAGE_MODEL", ""),
        enable_real_text_analysis=(
            os.getenv("ENABLE_REAL_TEXT_ANALYSIS", "true").lower() == "true"
        ),
        enable_real_openai=os.getenv("ENABLE_REAL_OPENAI", str(current.enable_real_openai).lower()).lower() == "true",
        enable_real_image_generation=os.getenv("ENABLE_REAL_IMAGE_GENERATION", str(current.enable_real_image_generation).lower()).lower() == "true",
        enable_real_seedance=(
            os.getenv("SEEDANCE_REAL_SUBMIT_ENABLED")
            or os.getenv("ENABLE_REAL_SEEDANCE", str(current.enable_real_seedance).lower())
        ).lower() == "true",
        openai_api_key=os.getenv("OPENAI_API_KEY", current.openai_api_key),
        openai_model_director=os.getenv("OPENAI_MODEL_DIRECTOR", current.openai_model_director),
        openai_text_model=openai_text_model,
        openai_model_routine=openai_text_model,
        openai_image_model_production=openai_image_model_production,
        openai_image_model_draft=openai_image_model_draft,
        openai_image_model=openai_image_model_production,
        openai_max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", str(current.openai_max_output_tokens))),
        huimengi_api_key=os.getenv("HUIMENGI_API_KEY", current.huimengi_api_key),
        huimengi_text_base_url=os.getenv("HUIMENGI_TEXT_BASE_URL", current.huimengi_text_base_url).rstrip("/"),
        huimengi_text_model=os.getenv("HUIMENGI_TEXT_MODEL", current.huimengi_text_model),
        huimengi_image_base_url=os.getenv("HUIMENGI_IMAGE_BASE_URL", current.huimengi_image_base_url).rstrip("/"),
        huimengi_image_model=os.getenv("HUIMENGI_IMAGE_MODEL", current.huimengi_image_model),
        huimengi_video_base_url=huimengi_video_base_url,
        huimengi_video_model=huimengi_video_model,
        huimengi_base_url=huimengi_video_base_url,
        huimengi_model_id=huimengi_video_model,
        default_video_provider_id=os.getenv("DEFAULT_VIDEO_PROVIDER_ID", current.default_video_provider_id),
        seedance_real_submit_enabled=(
            os.getenv("SEEDANCE_REAL_SUBMIT_ENABLED")
            or os.getenv("ENABLE_REAL_SEEDANCE", str(current.seedance_real_submit_enabled).lower())
        ).lower() == "true",
        seedance_aggregator_api_key=os.getenv("SEEDANCE_AGGREGATOR_API_KEY", current.seedance_aggregator_api_key),
        seedance_aggregator_base_url=os.getenv("SEEDANCE_AGGREGATOR_BASE_URL", current.seedance_aggregator_base_url).rstrip("/"),
        seedance_aggregator_create_task_path=os.getenv("SEEDANCE_AGGREGATOR_CREATE_TASK_PATH", current.seedance_aggregator_create_task_path),
        seedance_aggregator_get_task_path_template=os.getenv("SEEDANCE_AGGREGATOR_GET_TASK_PATH_TEMPLATE", current.seedance_aggregator_get_task_path_template),
        seedance_aggregator_cancel_task_path_template=os.getenv("SEEDANCE_AGGREGATOR_CANCEL_TASK_PATH_TEMPLATE", current.seedance_aggregator_cancel_task_path_template),
        seedance_aggregator_auth_type=os.getenv("SEEDANCE_AGGREGATOR_AUTH_TYPE", current.seedance_aggregator_auth_type),
        seedance_aggregator_auth_header=os.getenv("SEEDANCE_AGGREGATOR_AUTH_HEADER", current.seedance_aggregator_auth_header),
        seedance_aggregator_auth_prefix=os.getenv("SEEDANCE_AGGREGATOR_AUTH_PREFIX", current.seedance_aggregator_auth_prefix),
        seedance_aggregator_model_id=os.getenv("SEEDANCE_AGGREGATOR_MODEL_ID", current.seedance_aggregator_model_id),
    )


def apply_local_env_update(app, payload: LocalEnvUpdate) -> LocalEnvStatusView:
    updates = build_env_updates(payload)
    current: Settings = app.state.settings
    write_local_env(current.repo_root / ".env", updates)
    next_settings = refresh_settings(current, updates)
    app.state.settings = next_settings
    app.state.system_prompt_status = load_system_prompt_status(
        next_settings.system_prompt_file,
        next_settings.provider_mode,
    )
    return local_env_status(next_settings)
