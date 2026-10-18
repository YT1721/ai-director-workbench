from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SYSTEM_PROMPT = (
    "system-prompts/"
    "剧本视觉化创作系统_V7.0_Plus_R1_当前主版本.txt"
)


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _normalize_database_url(value: str) -> str:
    relative_prefix = "sqlite:///./"
    if value.startswith(relative_prefix):
        database_path = _resolve_repo_path(value.removeprefix(relative_prefix))
        return f"sqlite:///{database_path}"
    return value


def _normalize_text_provider_mode(value: str) -> str:
    mode = (value or "huimeng_chat").strip()
    return mode if mode in {"huimeng_chat", "openai_responses"} else "huimeng_chat"


def _normalize_video_provider_mode(value: str) -> str:
    mode = (value or "jimeng_cli").strip()
    return mode if mode in {"huimeng_live", "jimeng_cli", "volcengine_seedance25"} else "jimeng_cli"


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    database_url: str
    projects_root: Path
    system_prompt_file: Path
    provider_mode: str
    cors_origins: tuple[str, ...]
    max_video_tasks_per_batch: int = 100
    text_provider_mode: str = "huimeng_chat"
    text_api_key: str = ""
    text_base_url: str = "https://api.huimengi.com/v1"
    text_model: str = "gpt-5.5"
    image_provider_mode: str = "huimeng_tasks"
    image_api_key: str = ""
    image_base_url: str = ""
    image_model: str = ""
    enable_real_text_analysis: bool = True
    enable_real_openai: bool = False
    enable_real_image_generation: bool = False
    enable_real_seedance: bool = False
    openai_api_key: str = ""
    openai_model_director: str = ""
    openai_text_model: str = ""
    openai_model_routine: str = ""
    openai_image_model_production: str = ""
    openai_image_model_draft: str = ""
    openai_image_model: str = ""
    openai_max_output_tokens: int = 4000
    huimengi_api_key: str = ""
    huimengi_text_base_url: str = "https://api.huimengi.com/v1"
    huimengi_text_model: str = "gpt-5.5"
    huimengi_image_base_url: str = "https://api.huimengi.com"
    huimengi_image_model: str = "image-2"
    huimengi_video_base_url: str = "https://api.huimengi.com"
    huimengi_video_model: str = "seedance-2.0-fast"
    huimengi_base_url: str = "https://api.huimengi.com"
    huimengi_model_id: str = "seedance-2.0-fast"
    default_video_provider_id: str = "seedance_aggregator"
    seedance_real_submit_enabled: bool = False
    seedance_aggregator_api_key: str = ""
    seedance_aggregator_base_url: str = ""
    seedance_aggregator_create_task_path: str = ""
    seedance_aggregator_get_task_path_template: str = ""
    seedance_aggregator_cancel_task_path_template: str = ""
    seedance_aggregator_auth_type: str = "bearer"
    seedance_aggregator_auth_header: str = "Authorization"
    seedance_aggregator_auth_prefix: str = "Bearer "
    seedance_aggregator_model_id: str = ""
    volcengine_ark_api_key: str = ""
    volcengine_ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    seedance25_model_id: str = "doubao-seedance-2-5-260628"
    seedance25_live_enabled: bool = False
    video_task_supervisor_enabled: bool = True
    video_task_poll_interval_seconds: int = 5
    content_task_supervisor_enabled: bool = True
    content_task_poll_interval_seconds: int = 2
    image_task_supervisor_enabled: bool = False
    image_task_poll_interval_seconds: int = 5

    def __post_init__(self) -> None:
        # 文字/生图服务未单独配置时，回落到慧梦共用配置，保证旧 .env 与旧构造方式继续可用。
        if not self.text_api_key:
            object.__setattr__(self, "text_api_key", self.huimengi_api_key)
        if not self.text_base_url:
            object.__setattr__(self, "text_base_url", self.huimengi_text_base_url)
        if not self.text_model:
            object.__setattr__(self, "text_model", self.huimengi_text_model)
        if self.image_provider_mode not in {"huimeng_tasks", "openai_images"}:
            object.__setattr__(self, "image_provider_mode", "huimeng_tasks")
        if self.image_provider_mode == "huimeng_tasks":
            # 慧梦任务制沿用慧梦共用配置；即时 API 模式必须显式配置，缺失时由就绪检查明确提示。
            if not self.image_api_key:
                object.__setattr__(self, "image_api_key", self.huimengi_api_key)
            if not self.image_base_url:
                object.__setattr__(self, "image_base_url", self.huimengi_image_base_url)
            if not self.image_model:
                object.__setattr__(self, "image_model", self.huimengi_image_model)

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv(REPO_ROOT / ".env", override=False)

        openai_model_director = os.getenv("OPENAI_MODEL_DIRECTOR", "")
        openai_text_model = os.getenv("OPENAI_TEXT_MODEL") or os.getenv("OPENAI_MODEL_ROUTINE", "")
        openai_image_model_production = os.getenv("OPENAI_IMAGE_MODEL_PRODUCTION") or os.getenv("OPENAI_IMAGE_MODEL", "")
        openai_image_model_draft = os.getenv("OPENAI_IMAGE_MODEL_DRAFT") or openai_image_model_production
        huimengi_text_base_url = os.getenv("HUIMENGI_TEXT_BASE_URL", "https://api.huimengi.com/v1").rstrip("/")
        text_api_key = os.getenv("TEXT_API_KEY") or os.getenv("HUIMENGI_API_KEY", "")
        text_base_url = (os.getenv("TEXT_BASE_URL") or huimengi_text_base_url).rstrip("/")
        text_model = os.getenv("TEXT_MODEL") or os.getenv("HUIMENGI_TEXT_MODEL", "gpt-5.5")
        image_provider_mode = (os.getenv("IMAGE_PROVIDER_MODE", "huimeng_tasks").strip() or "huimeng_tasks")
        huimengi_image_base_url = os.getenv("HUIMENGI_IMAGE_BASE_URL", "https://api.huimengi.com").rstrip("/")
        huimengi_video_base_url = (
            os.getenv("HUIMENGI_VIDEO_BASE_URL")
            or os.getenv("HUIMENGI_BASE_URL", "https://api.huimengi.com")
        ).rstrip("/")
        huimengi_video_model = (
            os.getenv("HUIMENGI_VIDEO_MODEL")
            or os.getenv("HUIMENGI_MODEL_ID", "seedance-2.0-fast")
        )
        origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:6001,http://127.0.0.1:6001",
        )
        return cls(
            repo_root=REPO_ROOT,
            database_url=_normalize_database_url(
                os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
            ),
            projects_root=_resolve_repo_path(
                os.getenv("PROJECTS_ROOT", "./data/projects")
            ),
            system_prompt_file=_resolve_repo_path(
                os.getenv("SYSTEM_PROMPT_FILE", DEFAULT_SYSTEM_PROMPT)
            ),
            provider_mode=_normalize_video_provider_mode(os.getenv("VIDEO_PROVIDER_MODE", "jimeng_cli")),
            cors_origins=tuple(
                origin.strip() for origin in origins.split(",") if origin.strip()
            ),
            max_video_tasks_per_batch=int(os.getenv("MAX_VIDEO_TASKS_PER_BATCH", "100")),
            text_provider_mode=_normalize_text_provider_mode(os.getenv("TEXT_PROVIDER_MODE", "huimeng_chat")),
            text_api_key=text_api_key,
            text_base_url=text_base_url,
            text_model=text_model,
            image_provider_mode=image_provider_mode,
            image_api_key=os.getenv("IMAGE_API_KEY", ""),
            image_base_url=os.getenv("IMAGE_BASE_URL", "").rstrip("/"),
            image_model=os.getenv("IMAGE_MODEL", ""),
            enable_real_text_analysis=True,
            enable_real_openai=os.getenv("ENABLE_REAL_OPENAI", "false").lower() == "true",
            enable_real_image_generation=(
                os.getenv("IMAGE_REAL_SUBMIT_ENABLED")
                or os.getenv("ENABLE_REAL_IMAGE_GENERATION", "false")
            ).lower() == "true",
            enable_real_seedance=(
                os.getenv("SEEDANCE_REAL_SUBMIT_ENABLED")
                or os.getenv("ENABLE_REAL_SEEDANCE", "false")
            ).lower() == "true",
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model_director=openai_model_director,
            openai_text_model=openai_text_model,
            openai_model_routine=openai_text_model,
            openai_image_model_production=openai_image_model_production,
            openai_image_model_draft=openai_image_model_draft,
            openai_image_model=openai_image_model_production,
            openai_max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "4000")),
            huimengi_api_key=os.getenv("HUIMENGI_API_KEY", ""),
            huimengi_text_base_url=huimengi_text_base_url,
            huimengi_text_model=os.getenv("HUIMENGI_TEXT_MODEL", "gpt-5.5"),
            huimengi_image_base_url=huimengi_image_base_url,
            huimengi_image_model=os.getenv("HUIMENGI_IMAGE_MODEL", "image-2"),
            huimengi_video_base_url=huimengi_video_base_url,
            huimengi_video_model=huimengi_video_model,
            huimengi_base_url=huimengi_video_base_url,
            huimengi_model_id=huimengi_video_model,
            default_video_provider_id=os.getenv("DEFAULT_VIDEO_PROVIDER_ID", "seedance_aggregator"),
            seedance_real_submit_enabled=(
                os.getenv("SEEDANCE_REAL_SUBMIT_ENABLED")
                or os.getenv("ENABLE_REAL_SEEDANCE", "false")
            ).lower() == "true",
            seedance_aggregator_api_key=os.getenv("SEEDANCE_AGGREGATOR_API_KEY", ""),
            seedance_aggregator_base_url=os.getenv("SEEDANCE_AGGREGATOR_BASE_URL", "").rstrip("/"),
            seedance_aggregator_create_task_path=os.getenv("SEEDANCE_AGGREGATOR_CREATE_TASK_PATH", ""),
            seedance_aggregator_get_task_path_template=os.getenv("SEEDANCE_AGGREGATOR_GET_TASK_PATH_TEMPLATE", ""),
            seedance_aggregator_cancel_task_path_template=os.getenv("SEEDANCE_AGGREGATOR_CANCEL_TASK_PATH_TEMPLATE", ""),
            seedance_aggregator_auth_type=os.getenv("SEEDANCE_AGGREGATOR_AUTH_TYPE", "bearer"),
            seedance_aggregator_auth_header=os.getenv("SEEDANCE_AGGREGATOR_AUTH_HEADER", "Authorization"),
            seedance_aggregator_auth_prefix=os.getenv("SEEDANCE_AGGREGATOR_AUTH_PREFIX", "Bearer "),
            seedance_aggregator_model_id=os.getenv("SEEDANCE_AGGREGATOR_MODEL_ID", ""),
            volcengine_ark_api_key=os.getenv("VOLCENGINE_ARK_API_KEY", ""),
            volcengine_ark_base_url=os.getenv(
                "VOLCENGINE_ARK_BASE_URL",
                "https://ark.cn-beijing.volces.com/api/v3",
            ).rstrip("/"),
            seedance25_model_id=os.getenv(
                "SEEDANCE25_MODEL_ID",
                "doubao-seedance-2-5-260628",
            ),
            seedance25_live_enabled=os.getenv("SEEDANCE25_LIVE_ENABLED", "false").lower() == "true",
            video_task_supervisor_enabled=os.getenv("VIDEO_TASK_SUPERVISOR_ENABLED", "true").lower() == "true",
            video_task_poll_interval_seconds=max(
                1,
                int(os.getenv("VIDEO_TASK_POLL_INTERVAL_SECONDS", "5")),
            ),
            content_task_supervisor_enabled=os.getenv("CONTENT_TASK_SUPERVISOR_ENABLED", "true").lower() == "true",
            content_task_poll_interval_seconds=max(
                1,
                int(os.getenv("CONTENT_TASK_POLL_INTERVAL_SECONDS", "2")),
            ),
            image_task_supervisor_enabled=os.getenv("IMAGE_TASK_SUPERVISOR_ENABLED", "true").lower() == "true",
            image_task_poll_interval_seconds=max(
                1,
                int(os.getenv("IMAGE_TASK_POLL_INTERVAL_SECONDS", "5")),
            ),
        )
