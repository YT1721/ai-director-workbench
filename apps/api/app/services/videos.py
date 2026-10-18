from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageDraw
from sqlmodel import Session, select

from app.models import (
    AssetRequirement,
    BatchVideoJob,
    BatchVideoTask,
    Character,
    CharacterMasterVersion,
    Costume,
    CostumeVersion,
    CostUsageLog,
    Episode,
    Project,
    PropAsset,
    PropAssetVersion,
    ProviderRun,
    Scene,
    SceneAsset,
    SceneAssetVersion,
    SceneCharacterBinding,
    ScenePropBinding,
    Shot,
    SourceFile,
    StoryboardExecutionPage,
    StoryboardShotVersion,
    VideoProviderProfile,
    VideoResultVersion,
    VpBlock,
)
from app.models.workbench import utc_now
from app.config import Settings
from app.providers import (
    HUIMENG_LIVE_PROFILE_ID,
    JimengCliRunner,
    SeedanceAggregatorGenericProvider,
    SeedanceAtlasCloudProvider,
    SeedanceHuimengProvider,
    VolcengineSeedance25MockProvider,
)
from app.providers.huimeng import HUIMENG_MODEL_PAGE
from app.providers.jimeng_cli import (
    JimengCliCapabilities,
    detect_jimeng_cli_capabilities,
    extract_provider_status,
    extract_queue_info,
    extract_submit_id,
    extract_video_paths,
    normalize_status,
)
from app.schemas.videos import (
    BatchJobView,
    BatchTaskView,
    BatchWorkspaceView,
    JimengCliReadinessView,
    JimengCliStatusView,
    JimengVideoModelView,
    VideoGenerationSettingsUpdate,
    VideoProviderModelView,
    LiveReadinessGateView,
    LiveReadinessView,
    LiveProviderStatusView,
    ProviderProfileCreate,
    ProviderProfileView,
    ProviderTemplateView,
    ProviderPreflightView,
    ProviderRequestPreviewView,
    ProviderResponsePreviewView,
    VideoPackageSceneView,
    VideoPackageShotView,
    VideoPackageWorkspaceView,
    VideoResultView,
    VideoReferenceBindingsUpdate,
    VpBlockCreate,
    VpBlockView,
)
from app.schemas.workflows import AiTextRunCreate
from app.services.assets import _asset_url, _scene_with_project, _scope_code
from app.services.ai_text import run_project_ai_text
from app.services.projects import _project_root, get_project, sanitize_filename
from app.services.video_constraints import (
    MAX_SEEDANCE_CLIP_SECONDS,
    MAX_SEEDANCE25_CLIP_SECONDS,
    MIN_SEEDANCE25_CLIP_SECONDS,
    SEEDANCE_SUPPORTED_DURATIONS,
    duration_limit_message,
    recommend_video_duration,
    seedance_duration_instruction,
    time_range_exceeds_seedance_limit,
    validate_provider_duration,
)
from app.services.video_task_locks import video_task_lock
from app.services.seedance25_prompt_optimizer import optimize_seedance25_prompt


MAX_VIDEO_IMPORT_BYTES = 500 * 1024 * 1024
SEEDANCE25_PROFILE_ID = "volcengine_seedance25"
SEEDANCE25_DEFAULT_MODEL_ID = "doubao-seedance-2-5-260628"
SEEDANCE25_MODEL = VideoProviderModelView(
    id=SEEDANCE25_DEFAULT_MODEL_ID,
    provider_type="volcengine_seedance25",
    provider_model_id=SEEDANCE25_DEFAULT_MODEL_ID,
    label="火山方舟 Seedance 2.5（Mock）",
    speed_label="官方模型能力",
    cost_label="费用未知",
    description="首期仅进行本地模拟验收，不会向火山方舟发送请求或消耗额度。",
    supported_resolutions=["480p", "720p"],
    min_duration=MIN_SEEDANCE25_CLIP_SECONDS,
    max_duration=MAX_SEEDANCE25_CLIP_SECONDS,
    supports_smart_duration=True,
    is_mock_only=True,
    mock_only=True,
    capability_source="volcengine_official_api_catalog",
    duration_range=[MIN_SEEDANCE25_CLIP_SECONDS, MAX_SEEDANCE25_CLIP_SECONDS],
    reference_limits={"images": 30, "videos": 10, "audios": 10, "total": 50},
)
JIMENG_DEFAULT_VIDEO_MODEL_ID = "seedance2.0_vip"
JIMENG_VIDEO_MODELS = (
    JimengVideoModelView(
        id="seedance2.0mini",
        label="即梦 Seedance 2.0 mini",
        speed_label="快速",
        cost_label="较低",
        description="适合低成本试稿和批量迭代；最终积分以即梦提交时显示为准。",
        supported_resolutions=["720p"],
    ),
    JimengVideoModelView(
        id="seedance2.0fast_vip",
        label="即梦 Seedance 2.0 Fast VIP",
        speed_label="极速通道",
        cost_label="VIP",
        description="会员快速通道；是否可用及实际积分取决于当前即梦账号。",
        supported_resolutions=["720p"],
    ),
    JimengVideoModelView(
        id="seedance2.0_vip",
        label="即梦 Seedance 2.0 VIP",
        speed_label="会员通道",
        cost_label="VIP",
        description="默认成片模型，支持完整能力；实际可用分辨率和积分以即梦账号为准。",
        supported_resolutions=["720p", "1080p", "4k"],
    ),
    JimengVideoModelView(
        id="seedance2.0fast",
        label="即梦 Seedance 2.0 Fast",
        speed_label="较快",
        cost_label="中等",
        description="兼顾速度与质量，适合常规营销镜头。",
        supported_resolutions=["720p"],
    ),
    JimengVideoModelView(
        id="seedance2.0",
        label="即梦 Seedance 2.0",
        speed_label="标准",
        cost_label="较高",
        description="偏重完整生成质量，适合最终成片候选。",
        supported_resolutions=["720p"],
    ),
)
JIMENG_VIDEO_MODEL_IDS = {item.id for item in JIMENG_VIDEO_MODELS}
VP_PRECISION_18_TITLES = [
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


def _json(value: str, fallback):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def seed_huimeng_provider(session: Session) -> None:
    existing = session.get(VideoProviderProfile, HUIMENG_LIVE_PROFILE_ID)
    if existing:
        changed = False
        prices = _json(existing.price_configs_json, [])
        legacy_zero_price = (
            len(prices) == 1
            and prices[0].get("price_value") == 0
            and prices[0].get("currency") == "CREDITS"
            and prices[0].get("source_url") == HUIMENG_MODEL_PAGE
        )
        if legacy_zero_price:
            template = SeedanceHuimengProvider.profile_template(
                base_url=existing.base_url,
                model_id=_json(existing.config_json, {}).get("model_mapping", {}).get("seedance-2.0", "seedance-2.0-fast"),
            )
            existing.price_configs_json = json.dumps(template["price_configs"], ensure_ascii=False)
            for job in session.exec(
                select(BatchVideoJob).where(BatchVideoJob.provider_profile_id == existing.id)
            ).all():
                job.estimated_cost = None
                session.add(job)
            changed = True
        other_default = session.exec(
            select(VideoProviderProfile).where(
                VideoProviderProfile.id != existing.id,
                VideoProviderProfile.provider_type != "seedance_mock",
                VideoProviderProfile.is_default == True,  # noqa: E712
            )
        ).first()
        if not existing.is_default and other_default is None:
            existing.is_default = True
            changed = True
        elif existing.is_default and other_default is not None:
            existing.is_default = False
            changed = True
        mock = session.get(VideoProviderProfile, "seedance_mock")
        if mock and mock.is_default:
            mock.is_default = False
            session.add(mock)
            changed = True
        if changed:
            session.add(existing)
            session.commit()
        return
    template = SeedanceHuimengProvider.profile_template(
        base_url=os.getenv("HUIMENGI_VIDEO_BASE_URL") or os.getenv("HUIMENGI_BASE_URL", "https://api.huimengi.com"),
        model_id=os.getenv("HUIMENGI_VIDEO_MODEL") or os.getenv("HUIMENGI_MODEL_ID", "seedance-2.0-fast"),
    )
    has_non_mock_default = session.exec(
        select(VideoProviderProfile).where(
            VideoProviderProfile.provider_type != "seedance_mock",
            VideoProviderProfile.is_default == True,  # noqa: E712
        )
    ).first()
    profile = VideoProviderProfile(
        id=HUIMENG_LIVE_PROFILE_ID,
        display_name=template["display_name"],
        provider_type=template["provider_type"],
        base_url=template["base_url"],
        create_task_path=template["create_task_path"],
        get_task_path_template=template["get_task_path_template"],
        auth_type=template["auth_type"],
        auth_header_name=template["auth_header_name"],
        auth_prefix=template["auth_prefix"],
        auth_env_key_name=template["auth_env_key_name"],
        is_default=has_non_mock_default is None,
        config_json=json.dumps(template["config"], ensure_ascii=False),
        capabilities_json=json.dumps(template["capabilities"], ensure_ascii=False),
        price_configs_json=json.dumps(template["price_configs"], ensure_ascii=False),
    )
    session.add(profile)
    mock = session.get(VideoProviderProfile, "seedance_mock")
    if mock and mock.is_default:
        mock.is_default = False
        session.add(mock)
    session.commit()


def seed_configured_seedance_provider(session: Session, settings: Settings) -> None:
    """Seed a configurable third-party Seedance adapter profile from .env.

    This does not send network requests. It only makes the adapter visible for
    readiness checks and explicit user-confirmed submissions.
    """
    profile_id = settings.default_video_provider_id or "seedance_aggregator"
    if profile_id == HUIMENG_LIVE_PROFILE_ID:
        return
    profile = session.get(VideoProviderProfile, profile_id)
    if not profile:
        profile = VideoProviderProfile(
            id=profile_id,
            display_name="Seedance 聚合 API（可配置）",
            provider_type="seedance_aggregator_generic",
            auth_env_key_name="SEEDANCE_AGGREGATOR_API_KEY",
        )
    profile.base_url = settings.seedance_aggregator_base_url
    profile.create_task_path = settings.seedance_aggregator_create_task_path
    profile.get_task_path_template = settings.seedance_aggregator_get_task_path_template
    profile.cancel_task_path_template = settings.seedance_aggregator_cancel_task_path_template
    profile.auth_type = settings.seedance_aggregator_auth_type
    profile.auth_header_name = settings.seedance_aggregator_auth_header
    profile.auth_prefix = settings.seedance_aggregator_auth_prefix
    profile.auth_env_key_name = "SEEDANCE_AGGREGATOR_API_KEY"
    profile.is_default = settings.default_video_provider_id == profile.id
    if profile.is_default:
        for item in session.exec(
            select(VideoProviderProfile).where(
                VideoProviderProfile.id != profile.id,
                VideoProviderProfile.is_default == True,  # noqa: E712
            )
        ).all():
            item.is_default = False
            session.add(item)
    profile.config_json = json.dumps({
        "model_mapping": {"seedance-2.0": settings.seedance_aggregator_model_id},
        "request_field_mapping": {
            "model_id": "model",
            "prompt": "params.prompt",
            "duration_seconds": "params.duration",
            "resolution": "params.resolution",
            "aspect_ratio": "params.ratio",
            "reference_images": "params.reference_images",
            "generate_audio": "params.generate_audio",
        },
        "response_field_mapping": {
            "task_id": "data.id",
            "status": "data.status",
            "video_url": "data.video_url",
            "error_message": "message",
        },
        "response_status_mapping": {
            "pending": "submitted",
            "queued": "submitted",
            "running": "processing",
            "processing": "processing",
            "succeeded": "completed",
            "completed": "completed",
            "failed": "failed",
        },
    }, ensure_ascii=False)
    profile.capabilities_json = json.dumps({
        "supported_models": ["seedance-2.0"],
        "generation_modes": ["text_to_video", "first_frame", "multimodal_reference"],
        "supported_durations": SEEDANCE_SUPPORTED_DURATIONS,
        "supported_resolutions": ["720p"],
        "supported_aspect_ratios": ["16:9", "9:16"],
        "supports_reference_images": True,
        "supports_reference_videos": False,
        "supports_reference_audios": False,
        "max_reference_images": 4,
        "requires_manual_budget_confirmation": True,
    }, ensure_ascii=False)
    session.add(profile)
    session.commit()


def seed_seedance25_provider(session: Session, settings: Settings) -> None:
    """Register the 2.5 capability profile without enabling outbound requests."""
    profile = session.get(VideoProviderProfile, SEEDANCE25_PROFILE_ID)
    if profile is None:
        profile = VideoProviderProfile(
            id=SEEDANCE25_PROFILE_ID,
            display_name="火山方舟 Seedance 2.5（Mock）",
            provider_type="volcengine_seedance25",
            auth_env_key_name="VOLCENGINE_ARK_API_KEY",
        )
    profile.display_name = "火山方舟 Seedance 2.5（Mock）"
    profile.provider_type = "volcengine_seedance25"
    profile.base_url = settings.volcengine_ark_base_url
    profile.auth_env_key_name = "VOLCENGINE_ARK_API_KEY"
    profile.config_json = json.dumps({
        "model_id": settings.seedance25_model_id or SEEDANCE25_DEFAULT_MODEL_ID,
        "live_enabled": False,
        "requested_live_enabled": settings.seedance25_live_enabled,
        "mock_only": True,
        "documentation_url": "https://docs.volcengine.com/docs/82379/2607688?lang=zh",
    }, ensure_ascii=False)
    profile.capabilities_json = json.dumps({
        "supported_models": [settings.seedance25_model_id or SEEDANCE25_DEFAULT_MODEL_ID],
        "generation_modes": ["text_to_video", "multimodal_reference"],
        "duration_modes": ["smart", "specified"],
        "min_duration": MIN_SEEDANCE25_CLIP_SECONDS,
        "max_duration": MAX_SEEDANCE25_CLIP_SECONDS,
        "supported_resolutions": ["480p", "720p"],
        "supports_reference_images": True,
        "supports_reference_videos": True,
        "supports_reference_audios": True,
        "max_reference_images": 30,
        "max_reference_videos": 10,
        "max_reference_audios": 10,
        "max_reference_items": 50,
        "requires_manual_budget_confirmation": True,
        "mock_only": True,
    }, ensure_ascii=False)
    profile.price_configs_json = json.dumps([{
        "price_status": "unknown",
        "currency": "UNSPECIFIED",
        "note": "Mock 阶段不估算费用；真实费用须在第二阶段付费联调前人工核对。",
        "source_url": "https://docs.volcengine.com/docs/82379/2607688?lang=zh",
    }], ensure_ascii=False)
    profile.updated_at = utc_now()
    session.add(profile)
    session.commit()


def _profile_view(profile: VideoProviderProfile, message: str = "") -> ProviderProfileView:
    return ProviderProfileView(
        id=profile.id, display_name=profile.display_name, provider_type=profile.provider_type,
        is_enabled=profile.is_enabled, is_default=profile.is_default, base_url=profile.base_url,
        create_task_path=profile.create_task_path, get_task_path_template=profile.get_task_path_template,
        cancel_task_path_template=profile.cancel_task_path_template, auth_type=profile.auth_type,
        auth_header_name=profile.auth_header_name, auth_prefix=profile.auth_prefix,
        auth_env_key_name=profile.auth_env_key_name, config=_json(profile.config_json, {}),
        capabilities=_json(profile.capabilities_json, {}), price_configs=_json(profile.price_configs_json, []),
        validation_message=message,
    )


def list_profiles(session: Session, settings: Settings | None = None) -> list[ProviderProfileView]:
    seed_huimeng_provider(session)
    if settings:
        seed_configured_seedance_provider(session, settings)
        seed_seedance25_provider(session, settings)
    profiles = session.exec(select(VideoProviderProfile).order_by(VideoProviderProfile.created_at)).all()
    return [
        _profile_view(item)
        for item in profiles
        if item.provider_type != "seedance_mock"
    ]


def save_profile(session: Session, payload: ProviderProfileCreate, profile_id: str | None = None) -> ProviderProfileView:
    profile = session.get(VideoProviderProfile, profile_id) if profile_id else None
    if profile_id and profile is None:
        raise HTTPException(404, "服务通道配置不存在。")
    if profile is None:
        profile = VideoProviderProfile(display_name=payload.display_name, provider_type=payload.provider_type)
    for key, value in payload.model_dump(exclude={"config", "capabilities", "price_configs"}).items():
        setattr(profile, key, value)
    profile.config_json = json.dumps(payload.config, ensure_ascii=False)
    profile.capabilities_json = json.dumps(payload.capabilities, ensure_ascii=False)
    profile.price_configs_json = json.dumps(payload.price_configs, ensure_ascii=False)
    profile.updated_at = utc_now()
    session.add(profile); session.commit(); session.refresh(profile)
    return _profile_view(profile)


def validate_profile(session: Session, profile_id: str) -> ProviderProfileView:
    profile = session.get(VideoProviderProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "服务通道配置不存在。")
    provider = _provider_for(profile)
    return _profile_view(profile, provider.validate_config(_profile_view(profile).model_dump()).message)


def _provider_for(profile: VideoProviderProfile):
    if profile.provider_type == "seedance_mock":
        raise HTTPException(410, "Mock 视频通道已停用。请配置真实 Seedance 聚合 API 或即梦手动辅助通道。")
    if profile.provider_type == "seedance_atlas_cloud_disabled":
        return SeedanceAtlasCloudProvider()
    if profile.provider_type == "seedance_huimeng_live":
        return SeedanceHuimengProvider()
    if profile.provider_type == "volcengine_seedance25":
        return VolcengineSeedance25MockProvider()
    return SeedanceAggregatorGenericProvider()


def _unknown_jimeng_model(model_id: str, capabilities: JimengCliCapabilities) -> JimengVideoModelView:
    version_label = "Seedance 2.5" if "2.5" in model_id else model_id
    return JimengVideoModelView(
        id=model_id,
        label=f"即梦 {version_label}",
        speed_label="以 CLI 为准",
        cost_label="费用未知",
        description="该模型由当前 dreamina CLI 帮助输出发现；实际积分与能力以当前账号为准。",
        supported_resolutions=list(capabilities.supported_resolutions),
    )


def _jimeng_capabilities(runner: JimengCliRunner | None = None) -> JimengCliCapabilities:
    if runner and hasattr(runner, "capabilities"):
        return runner.capabilities()
    if runner:
        return JimengCliCapabilities(
            installed=runner.installed(),
            available_models=tuple(item.id for item in JIMENG_VIDEO_MODELS),
            max_images=9,
            max_videos=3,
            max_audios=3,
            capability_source="test_runner_compatibility",
        )
    return detect_jimeng_cli_capabilities()


def jimeng_video_models(runner: JimengCliRunner | None = None) -> list[JimengVideoModelView]:
    capabilities = _jimeng_capabilities(runner)
    templates = {item.id: item for item in JIMENG_VIDEO_MODELS}
    models: list[JimengVideoModelView] = []
    discovered = set(capabilities.available_models)
    ordered_ids = [item.id for item in JIMENG_VIDEO_MODELS if item.id in discovered]
    ordered_ids.extend(item for item in capabilities.available_models if item not in templates)
    for model_id in ordered_ids:
        base = templates.get(model_id) or _unknown_jimeng_model(model_id, capabilities)
        resolutions = list(base.supported_resolutions)
        detected = set(capabilities.supported_resolutions)
        if detected:
            resolutions = [item for item in resolutions if item in detected] or list(detected)
        models.append(base.model_copy(update={
            "supported_resolutions": resolutions,
            "min_duration": capabilities.min_duration,
            "max_duration": capabilities.max_duration,
            "capability_source": capabilities.capability_source,
            "cli_version": capabilities.cli_version,
            "available": True,
            "duration_range": [capabilities.min_duration, capabilities.max_duration],
            "reference_limits": {
                "images": capabilities.max_images,
                "videos": capabilities.max_videos,
                "audios": capabilities.max_audios,
                "total": capabilities.max_images + capabilities.max_videos + capabilities.max_audios,
            },
        }))
    return models


def video_provider_models(
    provider_type: str,
    settings: Settings | None = None,
    runner: JimengCliRunner | None = None,
) -> list[VideoProviderModelView]:
    if provider_type == "volcengine_seedance25":
        return [SEEDANCE25_MODEL]
    if provider_type in {"jimeng", "jimeng_cli"}:
        return [
            VideoProviderModelView(
                **model.model_dump(),
                provider_type="jimeng_cli",
                provider_model_id=model.id,
            )
            for model in jimeng_video_models(runner)
        ]
    if provider_type in {"huimeng", "seedance_huimeng_live"}:
        model_id = settings.huimengi_model_id if settings else "seedance-2.0-fast"
        return [VideoProviderModelView(
            id=model_id,
            provider_type="huimeng",
            provider_model_id=model_id,
            label="慧梦 Seedance 聚合模型",
            speed_label="聚合 API",
            cost_label="费用未知",
            description="模型由慧梦服务配置决定；价格、余额和最终能力需在服务商账户核对。",
            supported_resolutions=["720p"],
            min_duration=1,
            max_duration=15,
            capability_source="huimeng_provider_config",
            duration_range=[1, 15],
            reference_limits={"images": 1, "videos": 0, "audios": 0, "total": 1},
        )]
    raise HTTPException(404, "该视频服务没有可用的模型目录。")


def atlas_cloud_template() -> ProviderTemplateView:
    return ProviderTemplateView(
        template_id="atlas-cloud-seedance-2-fast-reference",
        title="Atlas Cloud｜Seedance 2.0 Fast Reference",
        description="禁用状态专属模板：只做 uploadMedia / generateVideo / prediction 的本地映射、预算和响应演练。真实上传、提交与下载尚未开放。",
        profile=SeedanceAtlasCloudProvider.profile_template(),
    )


def huimeng_template(settings: Settings) -> ProviderTemplateView:
    return ProviderTemplateView(
        template_id="huimeng-seedance-2-fast-value-live",
        title="慧梦 API｜Seedance 2.0 Fast Value 单镜实测",
        description=f"受控真实单镜模板：仅允许 1 个任务、单条 1-{MAX_SEEDANCE_CLIP_SECONDS} 秒、720p，提交前必须页面确认且服务端开关开启。",
        outbound_requests_enabled=settings.enable_real_seedance,
        profile=SeedanceHuimengProvider.profile_template(settings.huimengi_base_url, settings.huimengi_model_id),
    )


def live_provider_status(settings: Settings) -> LiveProviderStatusView:
    return LiveProviderStatusView(
        provider_mode=settings.provider_mode,
        real_seedance_enabled=settings.enable_real_seedance,
        huimengi_api_key_configured=bool(settings.huimengi_api_key),
        huimengi_video_base_url=settings.huimengi_video_base_url,
        huimengi_video_model=settings.huimengi_video_model,
        huimengi_base_url=settings.huimengi_base_url,
        huimengi_model_id=settings.huimengi_model_id,
        live_video_task="慧梦 Seedance 单镜真实测试",
        single_task_limit=f"只允许 1 个任务，1-{MAX_SEEDANCE_CLIP_SECONDS} 秒，720p；建议先用 5 秒小样",
        network_policy="未开启真实视频提交、未配置密钥、未确认费用风险和页面二次确认时，后端拒绝发送网络请求。",
    )


def _duration_plan_issue(session: Session, task: BatchVideoTask, canonical: dict[str, Any]) -> str:
    shot = session.get(Shot, task.shot_id)
    block = session.get(VpBlock, task.vp_block_id) if task.vp_block_id else None
    if not shot or not block:
        return ""
    recommended, reason = recommend_video_duration(shot.name)
    if block.duration_seconds == 5 and recommended != 5 and canonical.get("duration_seconds") == 5:
        return (
            f"{shot.shot_code} 仍使用旧版统一 5 秒默认值；主规则建议 {recommended} 秒。"
            f"{reason} 请回分镜提示词页重建时间轴。"
        )
    return ""


def live_readiness(session: Session, task_id: str, settings: Settings) -> LiveReadinessView:
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    profile = session.get(VideoProviderProfile, job.provider_profile_id) if job else None
    if task is None or job is None or profile is None:
        raise HTTPException(404, "视频任务不存在。")
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    canonical = _json(task.canonical_request_json, {})
    missing_items = _json(task.missing_items_json, [])
    model_mapping = _json(profile.config_json, {}).get("model_mapping", {})
    model_id = str(model_mapping.get(canonical.get("model_family", ""), settings.huimengi_model_id))
    cost_status, _, _ = _cost_estimate_details(profile, job.estimated_cost)
    duration_issue = _duration_plan_issue(session, task, canonical)
    confirmation_label = "预算确认" if cost_status == "estimated" else "费用风险确认"
    confirmation_detail = (
        f"已确认预计费用 {job.estimated_cost} {job.currency}"
        if job.budget_confirmed and cost_status == "estimated"
        else "已确认费用未知并允许本次提交"
        if job.budget_confirmed
        else f"请先确认预计费用 {job.estimated_cost} {job.currency}"
        if cost_status == "estimated"
        else "当前无法可靠估价，请先核对服务商价格和账户余额，再确认费用风险。"
    )
    gate_items = [
        LiveReadinessGateView(
            label="服务通道",
            passed=profile.provider_type == "seedance_huimeng_live",
            detail=profile.display_name if profile.provider_type == "seedance_huimeng_live" else "真实单镜测试只允许慧梦服务通道。",
        ),
        LiveReadinessGateView(
            label="真实视频开关",
            passed=settings.enable_real_seedance,
            detail="真实视频提交已开启" if settings.enable_real_seedance else "请在设置页开启真实 Seedance 单镜闸门。",
        ),
        LiveReadinessGateView(
            label="视频服务模式",
            passed=settings.provider_mode == "huimeng_live",
            detail=f"当前 VIDEO_PROVIDER_MODE={settings.provider_mode}",
        ),
        LiveReadinessGateView(
            label="慧梦 API Key",
            passed=bool(settings.huimengi_api_key),
            detail="已配置" if settings.huimengi_api_key else "未配置；请在设置页填写 HUIMENGI_API_KEY。",
        ),
        LiveReadinessGateView(
            label="受控批量队列",
            passed=True,
            detail=f"当前批次 {len(tasks)} 个任务；后台逐条提交，不并发发起付费请求。",
        ),
        LiveReadinessGateView(
            label="任务缺失项",
            passed=not missing_items,
            detail="无缺失项" if not missing_items else "；".join(str(item) for item in missing_items),
        ),
        LiveReadinessGateView(
            label="规格限制",
            passed=canonical.get("duration_seconds") in SEEDANCE_SUPPORTED_DURATIONS and canonical.get("resolution") == "720p",
            detail=f"{canonical.get('duration_seconds', '未知')} 秒 / {canonical.get('resolution', '未知')}；Seedance 单条必须在 1-{MAX_SEEDANCE_CLIP_SECONDS} 秒内，当前只开放 720p。",
        ),
        LiveReadinessGateView(
            label="镜头时长规划",
            passed=not duration_issue,
            detail=duration_issue or "当前镜头时长来自镜头任务规划，不是统一默认值。",
        ),
        LiveReadinessGateView(
            label=confirmation_label,
            passed=job.budget_confirmed,
            detail=confirmation_detail,
        ),
        LiveReadinessGateView(
            label="提交状态",
            passed=task.status == "ready",
            detail="ready，可提交" if task.status == "ready" else f"当前状态为 {task.status}；只有 ready 状态可提交。",
        ),
    ]
    return LiveReadinessView(
        ready=all(item.passed for item in gate_items),
        provider_name=profile.display_name,
        model_id=model_id,
        gate_items=gate_items,
        risk_notice="点击真实提交会向慧梦发送一次单镜视频请求，可能消耗账户积分；提交、查询和下载都需要页面逐次确认。",
    )


def provider_preflight(session: Session, profile_id: str) -> ProviderPreflightView:
    profile = session.get(VideoProviderProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "服务通道配置不存在。")
    config = _json(profile.config_json, {})
    request_mapping = config.get("request_field_mapping", {})
    response_mapping = config.get("response_field_mapping", {})
    validation = _provider_for(profile).validate_config(_profile_view(profile).model_dump())
    documentation_url = str(config.get("documentation_url", "")).strip()
    price_source_url = str(config.get("price_source_url", "")).strip()
    prices = _json(profile.price_configs_json, [])
    price_configured = any(
        price.get("price_status", "known") == "known"
        and isinstance(price.get("price_value"), (int, float))
        for price in prices
    )
    request_mapping_complete = all(request_mapping.get(key) for key in ("prompt", "duration_seconds", "resolution", "aspect_ratio"))
    response_mapping_complete = all(response_mapping.get(key) for key in ("task_id", "status", "video_url", "error_message"))
    secret_configured = bool(os.getenv(profile.auth_env_key_name, ""))
    outbound_enabled = profile.provider_type == "seedance_huimeng_live" and (
        os.getenv("SEEDANCE_REAL_SUBMIT_ENABLED")
        or os.getenv("ENABLE_REAL_SEEDANCE", "false")
    ).lower() == "true"
    ready_for_live = bool(
        profile.provider_type == "seedance_huimeng_live"
        and validation.valid
        and secret_configured
        and outbound_enabled
    )
    checklist = [
        f"基础配置：{'通过' if validation.valid else validation.message}",
        f"API 密钥环境变量：{'已配置' if secret_configured else '未配置'}",
        f"官方 API 文档：{'已登记' if documentation_url else '未登记'}",
        f"费用估算：{'已有可靠单价' if price_configured else '费用未知，提交前需人工核对'}",
        f"请求字段映射：{'完整' if request_mapping_complete else '待补充'}",
        f"响应字段映射：{'完整' if response_mapping_complete else '待补充'}",
        f"真实提交开关：{'已开启' if outbound_enabled else '关闭或不适用'}",
        f"真实提交限制：只允许单镜、1-{MAX_SEEDANCE_CLIP_SECONDS} 秒、720p、页面逐次确认；建议先用 5 秒小样",
    ]
    return ProviderPreflightView(
        profile_id=profile.id, provider_type=profile.provider_type, config_valid=validation.valid,
        secret_configured=secret_configured, documentation_url=documentation_url,
        price_source_url=price_source_url, price_configured=price_configured,
        request_mapping_complete=request_mapping_complete, response_mapping_complete=response_mapping_complete,
        outbound_requests_enabled=outbound_enabled, ready_for_live_test=ready_for_live, checklist=checklist,
    )


def provider_request_preview(session: Session, task_id: str) -> ProviderRequestPreviewView:
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    profile = session.get(VideoProviderProfile, job.provider_profile_id) if job else None
    if task is None or job is None or profile is None:
        raise HTTPException(404, "视频任务不存在。")
    canonical = _json(task.canonical_request_json, {})
    if profile.provider_type == "volcengine_seedance25":
        manifest = canonical.get("reference_manifest")
        if not isinstance(manifest, list):
            manifest = canonical.get("assets", {}).get("reference_bindings", [])
        content = [
            {
                "type": str(item.get("media_type") or "image"),
                "asset_version_id": str(item.get("asset_id") or ""),
                "tag": str(item.get("token") or ""),
                "purpose": str(item.get("purpose") or ""),
                "must_preserve": str(item.get("must_preserve") or ""),
                "must_not_transfer": str(item.get("must_not_transfer") or ""),
            }
            for item in manifest
            if isinstance(item, dict)
        ]
        mapped = {
            "model": canonical.get("provider_model_id") or SEEDANCE25_DEFAULT_MODEL_ID,
            "prompt": canonical.get("prompt"),
            "duration": -1 if canonical.get("duration_mode") == "smart" else canonical.get("duration_seconds"),
            "resolution": canonical.get("resolution"),
            "generation_mode": canonical.get("generation_mode"),
            "reference_content": content,
            "mock_only": True,
        }
        missing = []
        if not str(mapped["prompt"] or "").strip():
            missing.append("缺少视频提示词。")
    else:
        mapped, missing = _provider_for(profile).build_request_preview(canonical, _json(profile.config_json, {}))
    snapshot = {"mode": "preview_only", "mapped_request_preview": mapped, "missing_items": missing, "outbound_request_sent": False}
    session.add(ProviderRun(task_id=task.id, provider_profile_id=profile.id, action="preview", response_snapshot_json=json.dumps(snapshot, ensure_ascii=False)))
    session.commit()
    return ProviderRequestPreviewView(
        task_id=task.id, provider_profile_id=profile.id, canonical_request=canonical,
        mapped_request_preview=mapped, missing_items=missing,
    )


def provider_response_preview(session: Session, profile_id: str, sample_response: dict) -> ProviderResponsePreviewView:
    profile = session.get(VideoProviderProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "服务通道配置不存在。")
    normalized, missing = _provider_for(profile).build_response_preview(sample_response, _json(profile.config_json, {}))
    return ProviderResponsePreviewView(
        profile_id=profile.id, normalized_response=normalized, missing_items=missing,
    )


def _masked_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    snapshot = json.loads(json.dumps(payload, ensure_ascii=False))
    for key in ("api_key", "authorization", "Authorization", "token", "secret"):
        if key in snapshot:
            snapshot[key] = "***"
    return snapshot


def _latest_video_url(session: Session, task_id: str) -> str:
    runs = session.exec(select(ProviderRun).where(ProviderRun.task_id == task_id).order_by(ProviderRun.created_at.desc())).all()
    for run in runs:
        snapshot = _json(run.response_snapshot_json, {})
        video_url = snapshot.get("normalized", {}).get("video_url") or snapshot.get("video_url")
        if video_url:
            return str(video_url)
    return ""


def _live_context(session: Session, task_id: str, settings: Settings, confirm_live_request: bool):
    if not confirm_live_request:
        raise HTTPException(409, "真实请求未确认。请在页面确认本次真实请求。")
    if not settings.enable_real_seedance:
        raise HTTPException(409, "真实视频提交闸门未开启，后端拒绝真实视频请求。")
    if not settings.huimengi_api_key:
        raise HTTPException(409, "HUIMENGI_API_KEY 未配置，后端拒绝真实视频请求。")
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    profile = session.get(VideoProviderProfile, job.provider_profile_id) if job else None
    if task is None or job is None or profile is None:
        raise HTTPException(404, "视频任务不存在。")
    if profile.provider_type != "seedance_huimeng_live":
        raise HTTPException(409, "真实单镜测试只允许慧梦 Provider。")
    if not job.budget_confirmed:
        raise HTTPException(409, "请先确认预计费用或费用风险。")
    canonical = _json(task.canonical_request_json, {})
    if task.status not in {"ready", "submitted", "processing", "completed"}:
        raise HTTPException(409, "当前任务状态不允许真实操作。")
    if _json(task.missing_items_json, []):
        raise HTTPException(409, "任务仍有缺失项，不能真实提交。")
    if canonical.get("duration_seconds") not in SEEDANCE_SUPPORTED_DURATIONS or canonical.get("resolution") != "720p":
        raise HTTPException(409, f"真实测试只允许 1-{MAX_SEEDANCE_CLIP_SECONDS} 秒、720p。")
    duration_issue = _duration_plan_issue(session, task, canonical)
    if duration_issue:
        raise HTTPException(409, duration_issue)
    provider = SeedanceHuimengProvider()
    return task, job, profile, provider, canonical


def live_submit_task(session: Session, task_id: str, settings: Settings, confirm_live_request: bool) -> str:
    task, job, profile, provider, canonical = _live_context(session, task_id, settings, confirm_live_request)
    if task.status != "ready":
        raise HTTPException(409, "只有 ready 状态可以真实提交。")
    try:
        normalized, raw = provider.submit_task(settings.huimengi_base_url, settings.huimengi_api_key, canonical, _json(profile.config_json, {}))
    except ValueError as cause:
        raise HTTPException(409, str(cause)) from cause
    except httpx.HTTPError as cause:
        raise HTTPException(502, f"慧梦提交失败：{cause}") from cause
    external_id = normalized.get("task_id")
    if not external_id:
        raise HTTPException(502, "慧梦响应中缺少任务 ID。")
    task.external_task_id = str(external_id)
    task.status = str(normalized.get("status") or "submitted")
    task.updated_at = utc_now()
    job.submission_channel = "huimeng"
    job.updated_at = utc_now()
    session.add(task)
    session.add(job)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=profile.id,
        action="live_submit",
        response_snapshot_json=json.dumps({"normalized": normalized, "raw": _masked_snapshot(raw), "outbound_request_sent": True}, ensure_ascii=False),
    ))
    session.add(CostUsageLog(provider="huimeng", model_name=settings.huimengi_model_id, module_type="video_live_submit", estimated_cost=job.estimated_cost, task_id=task.id))
    session.commit()
    return job.project_id


def _live_poll_task_unlocked(session: Session, task_id: str, settings: Settings, confirm_live_request: bool) -> str:
    task, job, profile, provider, _ = _live_context(session, task_id, settings, confirm_live_request)
    if not task.external_task_id:
        raise HTTPException(409, "任务尚未真实提交。")
    try:
        normalized, raw = provider.poll_task(settings.huimengi_base_url, settings.huimengi_api_key, task.external_task_id)
    except httpx.HTTPError as cause:
        raise HTTPException(502, f"慧梦查询失败：{cause}") from cause
    task.status = str(normalized.get("status") or task.status)
    task.error_message = str(normalized.get("error_message") or "")
    task.updated_at = utc_now()
    session.add(task)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=profile.id,
        action="live_poll",
        response_snapshot_json=json.dumps({"normalized": normalized, "raw": _masked_snapshot(raw), "outbound_request_sent": True}, ensure_ascii=False),
    ))
    session.commit()
    return job.project_id


def live_poll_task(session: Session, task_id: str, settings: Settings, confirm_live_request: bool) -> str:
    with video_task_lock(task_id):
        return _live_poll_task_unlocked(session, task_id, settings, confirm_live_request)


def _live_download_task_unlocked(session: Session, task_id: str, settings: Settings, confirm_live_request: bool, projects_root: Path) -> str:
    task, job, profile, provider, _ = _live_context(session, task_id, settings, confirm_live_request)
    if task.status != "completed":
        raise HTTPException(409, "只有 completed 状态可以下载视频。")
    video_url = _latest_video_url(session, task.id)
    if not video_url:
        raise HTTPException(409, "尚未从慧梦响应中获得视频 URL。")
    try:
        content = provider.download_video(video_url)
    except httpx.HTTPError as cause:
        raise HTTPException(502, f"慧梦视频下载失败：{cause}") from cause
    shot = session.get(Shot, task.shot_id)
    scene, episode, project = _scene_with_project(session, shot.scene_id)
    path = f"07_results/generated_videos/{_scope_code(episode, scene)}/{uuid4().hex[:12]}_{shot.shot_code}_huimeng.mp4"
    target = _project_root(projects_root, project) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    number = len(session.exec(select(VideoResultVersion).where(VideoResultVersion.shot_id == shot.id)).all()) + 1
    session.add(VideoResultVersion(task_id=task.id, shot_id=shot.id, version_number=number, video_path=path, source="huimeng_live", status="imported"))
    task.result_video_path = path
    task.status = "imported"
    task.updated_at = utc_now()
    session.add(task)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=profile.id,
        action="live_download",
        response_snapshot_json=json.dumps({"video_url": video_url, "downloaded": True, "outbound_request_sent": True}, ensure_ascii=False),
    ))
    session.commit()
    return job.project_id


def live_download_task(session: Session, task_id: str, settings: Settings, confirm_live_request: bool, projects_root: Path) -> str:
    with video_task_lock(task_id):
        task = session.get(BatchVideoTask, task_id)
        job = session.get(BatchVideoJob, task.job_id) if task else None
        if task is None or job is None:
            raise HTTPException(404, "视频任务不存在。")
        if task.result_video_path:
            task.status = "imported"
            task.updated_at = utc_now()
            session.add(task)
            session.commit()
            return job.project_id
        existing = session.exec(
            select(VideoResultVersion)
            .where(VideoResultVersion.task_id == task.id)
            .order_by(VideoResultVersion.created_at.desc())
        ).first()
        if existing:
            task.result_video_path = existing.video_path
            task.status = "imported"
            task.updated_at = utc_now()
            session.add(task)
            session.commit()
            return job.project_id
        return _live_download_task_unlocked(
            session,
            task_id,
            settings,
            confirm_live_request,
            projects_root,
        )


def jimeng_cli_status(settings: Settings, runner: JimengCliRunner | None = None) -> JimengCliStatusView:
    runner = runner or JimengCliRunner()
    capabilities = _jimeng_capabilities(runner)
    output_dir = str(settings.projects_root / "_jimeng_cli_downloads")
    if not runner.installed():
        return JimengCliStatusView(
            installed=False,
            logged_in=False,
            ready=False,
            command=runner.command,
            output_dir=output_dir,
            cli_version=capabilities.cli_version,
            blocking_reason="本机没有检测到 dreamina 命令。",
        )
    result = runner.user_credit()
    if not result.ok:
        return JimengCliStatusView(
            installed=True,
            logged_in=False,
            ready=False,
            command=runner.command,
            output_dir=output_dir,
            cli_version=capabilities.cli_version,
            blocking_reason=result.error or "即梦 CLI 未登录或无法读取账号积分。请在终端执行 dreamina login。",
        )
    data = result.data
    account = str(data.get("user") or data.get("account") or data.get("uid") or data.get("username") or "")
    credit = str(data.get("credit") or data.get("credits") or data.get("balance") or data.get("point") or result.summary or "已读取积分摘要")
    return JimengCliStatusView(
        installed=True,
        logged_in=True,
        ready=True,
        command=runner.command,
        account_summary=account or "已登录",
        credit_summary=credit,
        output_dir=output_dir,
        cli_version=capabilities.cli_version,
    )


def _jimeng_task_context(session: Session, task_id: str):
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    profile = session.get(VideoProviderProfile, job.provider_profile_id) if job else None
    shot = session.get(Shot, task.shot_id) if task else None
    if not task or not job or not profile or not shot:
        raise HTTPException(404, "视频任务不存在。")
    scene, episode, project = _scene_with_project(session, shot.scene_id)
    return task, job, profile, shot, scene, episode, project


def _jimeng_model_id(canonical: dict[str, Any]) -> str:
    provider_options = canonical.get("provider_options")
    if isinstance(provider_options, dict):
        selected = str(provider_options.get("jimeng_model_version") or "").strip()
        if re.fullmatch(r"seedance[0-9a-z_.-]+", selected, re.I):
            return selected
    value = str(canonical.get("model_variant") or canonical.get("model_family") or "")
    if value in {"seedance-2.0", "standard", "seedance-2.0-fast"}:
        return JIMENG_DEFAULT_VIDEO_MODEL_ID
    normalized = value.replace("-", "").replace("_", "")
    return normalized if re.fullmatch(r"seedance[0-9a-z.-]+", normalized, re.I) else JIMENG_DEFAULT_VIDEO_MODEL_ID


def _submitted_jimeng_model_id(session: Session, task: BatchVideoTask) -> str:
    run = session.exec(
        select(ProviderRun)
        .where(
            ProviderRun.task_id == task.id,
            ProviderRun.action.in_(("jimeng_cli_submit", "jimeng_cli_submit_failed")),
        )
        .order_by(ProviderRun.created_at.desc())
    ).first()
    snapshot = _json(run.response_snapshot_json, {}) if run else {}
    model_id = str(snapshot.get("model_id") or "").strip()
    return model_id if re.fullmatch(r"seedance[0-9a-z_.-]+", model_id, re.I) else ""


def _is_transient_jimeng_submit_error(message: str) -> bool:
    value = message.lower()
    return any(marker in value for marker in (
        "context deadline exceeded",
        "applyimageupload",
        "timed out",
        "timeout",
        "connection reset",
        "connection refused",
        "temporary failure",
        "temporarily unavailable",
        "network is unreachable",
        "unexpected eof",
        "status code 429",
        "status code 502",
        "status code 503",
        "status code 504",
    ))


def _record_jimeng_submit_transient(
    session: Session,
    task: BatchVideoTask,
    profile: VideoProviderProfile,
    reason: str,
    *,
    attempt_id: str = "",
    summary: str = "",
) -> None:
    task.external_task_id = None
    task.status = "ready"
    task.error_message = "参考图上传暂时超时，后台将自动重新上传；尚未确认建立云端生成任务。"
    task.updated_at = utc_now()
    session.add(task)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=profile.id,
        action="jimeng_cli_submit_transient",
        response_snapshot_json=json.dumps({
            "attempt_id": attempt_id,
            "summary": summary,
            "monitor_error": reason,
            "cloud_task_created": False,
            "will_retry": True,
            "outbound_request_sent": True,
        }, ensure_ascii=False),
    ))
    session.commit()


def update_jimeng_video_model(session: Session, task_id: str, model_id: str) -> str:
    task, job, _, _, _, _, _ = _jimeng_task_context(session, task_id)
    if task.status not in {"blocked", "awaiting_budget_confirm", "ready"}:
        raise HTTPException(409, "任务已经提交，不能中途更换模型。请保留当前任务结果，重新建立队列后再选择模型。")
    if model_id not in {item.id for item in jimeng_video_models()}:
        raise HTTPException(422, "即梦视频模型无效，请重新选择。")
    canonical = _json(task.canonical_request_json, {})
    options = canonical.get("provider_options")
    if not isinstance(options, dict):
        options = {}
    options["jimeng_model_version"] = model_id
    canonical["provider_options"] = options
    task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
    _invalidate_reference_confirmation(task, canonical)
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    if task.status == "ready":
        task.status = "awaiting_budget_confirm"
    job.status = "awaiting_budget_confirm"
    task.updated_at = utc_now()
    session.add(task)
    session.add(job)
    session.commit()
    return job.project_id


def prepare_jimeng_cli_retry(session: Session, task_id: str) -> str:
    task, job, profile, shot, _, _, _ = _jimeng_task_context(session, task_id)
    was_failed = task.status == "failed"
    if task.external_task_id and not was_failed:
        raise HTTPException(409, "即梦任务仍有远端任务 ID，不能重新准备或替换参考图。")
    if task.status not in {"failed", "blocked", "awaiting_budget_confirm", "ready"}:
        raise HTTPException(409, "只有失败或尚未提交的即梦任务可以重新准备；运行中的任务不能替换参考图。")
    previous_submit_id = task.external_task_id or ""
    previous_storyboard_id, current_storyboard_id = _refresh_task_storyboard_reference(
        session,
        task,
        shot,
    )
    canonical = _refresh_task_reference_manifest(session, task, shot, profile.id)
    duration = int(canonical.get("duration_seconds") or 0)
    missing_items = _json(task.missing_items_json, [])
    if not isinstance(missing_items, list):
        missing_items = []
    if 1 <= duration <= 15:
        missing_items = [
            item
            for item in missing_items
            if "Seedance 单条视频必须在 1-15 秒内" not in str(item)
        ]
    task.missing_items_json = json.dumps(missing_items, ensure_ascii=False)
    task.external_task_id = None
    task.error_message = ""
    if was_failed:
        task.retry_count += 1
    task.status = "blocked" if missing_items else "awaiting_budget_confirm"
    task.updated_at = utc_now()
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    job.status = "blocked" if missing_items else "awaiting_budget_confirm"
    session.add(task)
    session.add(job)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=profile.id,
        action="jimeng_cli_retry_prepared",
        response_snapshot_json=json.dumps({
            "previous_submit_id": previous_submit_id,
            "previous_storyboard_version_id": previous_storyboard_id,
            "current_storyboard_version_id": current_storyboard_id,
            "outbound_request_sent": False,
        }, ensure_ascii=False),
    ))
    session.commit()
    return job.project_id


def prepare_video_task_retry(session: Session, task_id: str) -> str:
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    if not task or not job:
        raise HTTPException(404, "视频任务不存在。")
    if job.submission_channel == "jimeng" or task.external_provider == "jimeng_cli":
        return prepare_jimeng_cli_retry(session, task_id)
    if task.status != "failed":
        raise HTTPException(409, "只有明确失败的镜头可以重新准备。")
    task.external_task_id = None
    task.result_video_path = None
    task.error_message = ""
    task.retry_count += 1
    task.status = "ready" if job.budget_confirmed else "awaiting_budget_confirm"
    task.updated_at = utc_now()
    job.dispatch_enabled = False
    job.batch_authorized = False
    _update_batch_job_status(session, job)
    session.add(task)
    session.add(job)
    session.commit()
    return job.project_id


def _task_storyboard_reference(
    session: Session,
    canonical: dict[str, Any],
) -> StoryboardShotVersion | None:
    assets = canonical.get("assets")
    refs = assets.get("reference_images", []) if isinstance(assets, dict) else []
    for value in refs:
        storyboard = session.get(StoryboardShotVersion, value)
        if storyboard is not None:
            return storyboard
    return None


def _refresh_task_storyboard_reference(
    session: Session,
    task: BatchVideoTask,
    shot: Shot,
) -> tuple[str, str]:
    canonical = _json(task.canonical_request_json, {})
    if not isinstance(canonical, dict):
        canonical = {}
    current = _active(
        StoryboardShotVersion,
        session,
        StoryboardShotVersion.shot_id,
        shot.id,
    )
    if current is None:
        raise HTTPException(409, "当前镜头没有已确认或锁定的正式故事板，不能重新准备付费任务。")
    previous = _task_storyboard_reference(session, canonical)
    assets = canonical.get("assets")
    if not isinstance(assets, dict):
        assets = {}
    refs = assets.get("reference_images")
    if not isinstance(refs, list):
        refs = []
    refs = [
        value
        for value in refs
        if session.get(StoryboardShotVersion, value) is None
    ]
    assets["reference_images"] = [current.id, *refs]
    bindings = assets.get("reference_bindings")
    if isinstance(bindings, list):
        storyboard_replaced = False
        for item in bindings:
            if isinstance(item, dict) and item.get("asset_type") == "storyboard":
                item["asset_id"] = current.id
                storyboard_replaced = True
                break
        if not storyboard_replaced:
            bindings.insert(0, {"asset_id": current.id, "asset_type": "storyboard"})
        assets["reference_bindings"] = bindings[:SEEDANCE_MAX_REFERENCE_IMAGES]
    canonical["assets"] = assets
    task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
    return previous.id if previous else "", current.id


SEEDANCE_MAX_REFERENCE_IMAGES = 30
JIMENG_MAX_REFERENCE_IMAGES = 9
SEEDANCE_REFERENCE_ROLE_PURPOSES = {
    "storyboard": "只参考镜头构图、机位、动作节点和时间轴；忽略分格线、箭头、标注文字与黑白铅笔风格。",
    "environment": "参考场景空间、地形、光线和环境质感，不改变主体身份与产品结构。",
    "character": "锁定人物身份、脸、年龄、骨相、体型和身份气质，不继承背景与版式。",
    "costume": "锁定服装款式、颜色、护具和穿着关系，不改变人物身份。",
    "product": "锁定真实产品外形、比例、结构、贴花位置和材质；不生成或篡改可读品牌文字。",
    "prop_detail": "锁定该道具或机械局部的真实结构和状态，不把参考图背景带入成片。",
    "environment_detail": "参考地面、泥水、地形或环境细节，不改变主体外观。",
    "source_video": "参考视频中的动作、镜头或节奏，不迁移无关主体身份与品牌元素。",
    "source_audio": "参考音频中的节奏、音色或声音关系，不复制未授权内容。",
}

REFERENCE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
REFERENCE_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
REFERENCE_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac"}


def _source_file_media_type(source: SourceFile) -> str | None:
    content_type = str(source.content_type or "").lower()
    suffix = Path(source.relative_path).suffix.lower()
    if content_type.startswith("image/") or suffix in REFERENCE_IMAGE_EXTENSIONS:
        return "image"
    if content_type.startswith("video/") or suffix in REFERENCE_VIDEO_EXTENSIONS:
        return "video"
    if content_type.startswith("audio/") or suffix in REFERENCE_AUDIO_EXTENSIONS:
        return "audio"
    return None


def _reference_media_type(session: Session, asset_id: str) -> str:
    source = session.get(SourceFile, asset_id)
    return (_source_file_media_type(source) if source else None) or "image"


def _seedance25_reference_missing(bindings: list[dict[str, Any]]) -> list[str]:
    media_counts = {
        media_type: sum(
            1
            for item in bindings
            if isinstance(item, dict) and str(item.get("media_type") or "image") == media_type
        )
        for media_type in ("image", "video", "audio")
    }
    missing: list[str] = []
    if (
        media_counts["image"] > 30
        or media_counts["video"] > 10
        or media_counts["audio"] > 10
        or sum(media_counts.values()) > 50
    ):
        missing.append("Seedance 2.5 参考素材超限：图片 30、视频 10、音频 10、合计 50。")
    if any(
        isinstance(item, dict) and item.get("asset_type") == "character"
        for item in bindings
    ):
        missing.append(
            "真人肖像参考默认阻塞：请移除人物母版参考，或改用官方明确允许的主体参考方式后重新确认。"
        )
    return missing


def _replace_seedance25_reference_missing(
    existing: list[str],
    bindings: list[dict[str, Any]],
) -> list[str]:
    stable = [
        item
        for item in existing
        if "Seedance 2.5 参考素材" not in item and "真人肖像参考默认阻塞" not in item
    ]
    return [*stable, *_seedance25_reference_missing(bindings)]


def _reference_asset_info(
    session: Session,
    asset_id: str,
) -> tuple[str, str, str, str] | None:
    storyboard = session.get(StoryboardShotVersion, asset_id)
    if storyboard:
        return "storyboard", "storyboard", Path(storyboard.image_path).name, storyboard.image_path
    scene_version = session.get(SceneAssetVersion, asset_id)
    if scene_version:
        scene_asset = session.get(SceneAsset, scene_version.scene_asset_id)
        return "scene", "environment", scene_asset.name if scene_asset else "场景资产", scene_version.asset_path
    character_version = session.get(CharacterMasterVersion, asset_id)
    if character_version:
        character = session.get(Character, character_version.character_id)
        return "character", "character", character.name if character else "人物母版", character_version.asset_path
    costume_version = session.get(CostumeVersion, asset_id)
    if costume_version:
        costume = session.get(Costume, costume_version.costume_id)
        label = costume.usage_context or costume.costume_code if costume else "服装资产"
        return "costume", "costume", label, costume_version.asset_path
    prop_version = session.get(PropAssetVersion, asset_id)
    if prop_version:
        prop = session.get(PropAsset, prop_version.prop_asset_id)
        label = prop.name if prop else "道具资产"
        role = _prop_reference_role(label)
        return "prop", role, label, prop_version.asset_path
    source = session.get(SourceFile, asset_id)
    media_type = _source_file_media_type(source) if source else None
    if source and source.category == "reference" and media_type:
        role = "source_audio" if media_type == "audio" else "source_video" if media_type == "video" else "environment"
        return "source", role, source.original_filename, source.relative_path
    return None


def _current_reference_asset_id(session: Session, asset_id: str) -> str:
    """Resolve a version id to the currently locked version of the same asset."""
    storyboard = session.get(StoryboardShotVersion, asset_id)
    if storyboard:
        current = _active(StoryboardShotVersion, session, StoryboardShotVersion.shot_id, storyboard.shot_id)
        return current.id if current else asset_id
    scene_version = session.get(SceneAssetVersion, asset_id)
    if scene_version:
        current = _active(SceneAssetVersion, session, SceneAssetVersion.scene_asset_id, scene_version.scene_asset_id)
        return current.id if current else asset_id
    character_version = session.get(CharacterMasterVersion, asset_id)
    if character_version:
        current = _active(
            CharacterMasterVersion,
            session,
            CharacterMasterVersion.character_id,
            character_version.character_id,
        )
        return current.id if current else asset_id
    costume_version = session.get(CostumeVersion, asset_id)
    if costume_version:
        current = _active(CostumeVersion, session, CostumeVersion.costume_id, costume_version.costume_id)
        return current.id if current else asset_id
    prop_version = session.get(PropAssetVersion, asset_id)
    if prop_version:
        current = _active(
            PropAssetVersion,
            session,
            PropAssetVersion.prop_asset_id,
            prop_version.prop_asset_id,
        )
        return current.id if current else asset_id
    return asset_id


def _prop_reference_role(label: str) -> str:
    if any(word in label for word in ("产品母版", "产品矩阵", "电动越野摩托", "摩托产品")):
        return "product"
    if any(word in label for word in ("泥", "车辙", "地形", "坡", "水洼", "碎石")):
        return "environment_detail"
    return "prop_detail"


def _shot_has_no_character(block: VpBlock, shot: Shot) -> bool:
    text = f"{shot.name}\n{block.prompt_copy or block.prompt}"
    return any(
        marker in text
        for marker in ("不要出现人物", "不出现人物", "无人物", "不需要人物", "禁止出现人物")
    )


def _character_relevance_score(character: Character, shot_text: str) -> int:
    name = character.name.strip()
    score = 40 if name and name in shot_text else 0
    marker_groups = (
        (("儿童", "孩子", "小朋友"), ("儿童", "孩子", "小朋友")),
        (("青少年", "少年", "年轻"), ("青少年", "少年", "年轻骑手")),
        (("女性", "女骑手", "女人"), ("女性", "女骑手", "女人")),
        (("成人", "成熟"), ("成人", "成熟骑手")),
        (("家长", "父亲", "母亲"), ("家长", "父亲", "母亲", "爸爸", "妈妈")),
        (("教练",), ("教练",)),
        (("工程师", "检测人员"), ("工程师", "检测人员", "装配", "质量检测")),
    )
    for character_markers, shot_markers in marker_groups:
        if any(marker in name for marker in character_markers) and any(marker in shot_text for marker in shot_markers):
            score += 18
    # "成人教练" cannot ground an "成人骑手" asset. Composite rider roles
    # require the prompt to identify that same rider category explicitly.
    if "成人" in name and "骑手" in name and not any(marker in shot_text for marker in ("成人骑手", "成熟骑手")):
        score -= 18
    for token in re.split(r"[/、（）()\s]+", name):
        if len(token) >= 3 and token not in {"角色", "人物", "骑手"} and token in shot_text:
            score += 10
    if "坡侧" in name and "坡侧" not in shot_text:
        score -= 20
    return score


def _is_primary_character(character: Character) -> bool:
    return any(
        marker in character.name
        for marker in ("儿童", "孩子", "小朋友", "青少年", "少年", "女性", "女骑手", "成人", "成熟骑手")
    )


def _continuity_requires_character(shot_text: str) -> bool:
    return any(
        marker in shot_text
        for marker in ("骑手", "眼神", "手势", "点头", "头盔", "手套", "脚撑", "身体", "第二次尝试", "成功通过")
    )


def _shot_character_reference_ids(session: Session, shot: Shot, block: VpBlock) -> list[str]:
    if _shot_has_no_character(block, shot):
        return []
    shot_text = f"{shot.name}\n{block.prompt_copy or block.prompt}\n{block.negative_prompt}"
    scene_bindings = session.exec(
        select(SceneCharacterBinding).where(SceneCharacterBinding.scene_id == shot.scene_id)
    ).all()
    sources: list[tuple[str, str, str, str | None, Character]] = []
    represented_characters: set[str] = set()
    for binding in scene_bindings:
        character = session.get(Character, binding.character_id)
        if not character or character.is_archived:
            continue
        sources.append((
            character.character_code,
            binding.character_id,
            binding.character_master_version_id,
            binding.costume_version_id,
            character,
        ))
        represented_characters.add(binding.character_id)

    # Character masters remain valid references when their costume is handled
    # as text. SceneCharacterBinding requires a costume version, so recover
    # these independently confirmed character requirements here.
    scene = session.get(Scene, shot.scene_id)
    episode = session.get(Episode, scene.episode_id) if scene else None
    if episode:
        requirements = session.exec(select(AssetRequirement).where(
            AssetRequirement.project_id == episode.project_id,
            AssetRequirement.asset_type == "character",
            AssetRequirement.is_current == True,  # noqa: E712
            AssetRequirement.status == "bound",
        )).all()
        active = {"confirmed_current", "locked"}
        for requirement in requirements:
            if requirement.target_id in represented_characters or requirement.reference_mode == "text_only":
                continue
            try:
                scene_ids = json.loads(requirement.scene_ids_json or "[]")
            except (TypeError, json.JSONDecodeError):
                scene_ids = []
            if shot.scene_id not in scene_ids:
                continue
            character = session.get(Character, requirement.target_id)
            if not character or character.is_archived:
                continue
            master = session.exec(select(CharacterMasterVersion).where(
                CharacterMasterVersion.character_id == character.id,
                CharacterMasterVersion.status.in_(active),
            )).first()
            if not master:
                continue
            sources.append((character.character_code, character.id, master.id, None, character))

    candidates: list[tuple[int, str, str, str, str | None, Character]] = []
    for character_code, character_id, master_version_id, costume_version_id, character in sources:
        score = _character_relevance_score(character, shot_text)
        if score > 0:
            candidates.append((
                score,
                character_code,
                character_id,
                master_version_id,
                costume_version_id,
                character,
            ))
    candidates.sort(key=lambda item: (-item[0], item[1]))

    # Continuity shots often omit the actor name. Inherit only the nearest
    # explicitly identified primary actor, and only when this shot has human cues.
    if not any(_is_primary_character(item[5]) for item in candidates) and _continuity_requires_character(shot_text):
        previous_shots = sorted(
            (
                item
                for item in session.exec(select(Shot).where(Shot.scene_id == shot.scene_id)).all()
                if item.shot_code < shot.shot_code and not item.is_archived
            ),
            key=lambda item: item.shot_code,
            reverse=True,
        )
        for previous_shot in previous_shots:
            inherited: list[tuple[int, str, str, str, str | None, Character]] = []
            for character_code, character_id, master_version_id, costume_version_id, character in sources:
                if not character or character.is_archived or not _is_primary_character(character):
                    continue
                score = _character_relevance_score(character, previous_shot.name)
                if score > 0:
                    inherited.append((
                        score,
                        character_code,
                        character_id,
                        master_version_id,
                        costume_version_id,
                        character,
                    ))
            if inherited:
                inherited.sort(key=lambda item: (-item[0], item[1]))
                candidates.append(inherited[0])
                break
        candidates.sort(key=lambda item: (-item[0], item[1]))

    primary_candidates = [item for item in candidates if _is_primary_character(item[5])]
    support_candidates = [item for item in candidates if not _is_primary_character(item[5])]
    selected_candidates = primary_candidates[:3]
    if len(selected_candidates) < 3 and support_candidates:
        selected_candidates.append(support_candidates[0])

    asset_ids: list[str] = []
    seen_characters: set[str] = set()
    for _, _, character_id, master_version_id, costume_version_id, _ in selected_candidates:
        if character_id in seen_characters:
            continue
        seen_characters.add(character_id)
        asset_ids.append(_current_reference_asset_id(session, master_version_id))
        if costume_version_id:
            asset_ids.append(_current_reference_asset_id(session, costume_version_id))
        if len(seen_characters) == 3:
            break
    if not asset_ids and block.has_character:
        asset_ids.extend(
            _current_reference_asset_id(session, value)
            for value in (block.character_master_version_id, block.costume_version_id)
            if value
        )
    return list(dict.fromkeys(asset_ids))


def _prop_relevance_score(prop: PropAsset, shot_text: str) -> int:
    asset_text = prop.name
    groups = (
        (("轮胎", "胎纹", "车轮", "胎块"), 18),
        (("泥水", "红泥", "湿泥", "车辙", "水洼"), 16),
        (("摩托", "车辆", "车身", "车架", "车型", "产品"), 9),
        (("头盔", "扣带", "护具"), 14),
        (("手套",), 14),
        (("车把", "刹车", "仪表"), 14),
        (("泥坑", "碎石", "陡坡", "弯道", "地形"), 14),
        (("电机", "电池", "避震", "技术局部"), 13),
        (("工厂", "装配", "质量检测", "测试台"), 13),
        (("电流", "车灯"), 12),
    )
    score = 0
    for words, weight in groups:
        if any(word in shot_text for word in words) and any(word in asset_text for word in words):
            score += weight
    if prop.name and prop.name in shot_text:
        score += 30
    if _prop_reference_role(prop.name) == "product" and any(
        word in shot_text for word in ("摩托", "车辆", "车身", "车架", "车型")
    ):
        score += 12
    variant_markers = (
        (("儿童",), ("儿童", "孩子", "小朋友")),
        (("青少年",), ("青少年", "少年", "年轻骑手")),
        (("女性",), ("女性", "女人", "女骑手")),
        (("成人", "旗舰"), ("成人", "成熟骑手", "旗舰")),
    )
    for asset_markers, shot_markers in variant_markers:
        if any(marker in prop.name for marker in asset_markers) and not any(
            marker in shot_text for marker in shot_markers
        ):
            score -= 18
    return score


def _scene_prop_reference_ids(session: Session, shot: Shot, block: VpBlock) -> list[str]:
    shot_text = f"{shot.name}\n{block.prompt_copy or block.prompt}\n{block.negative_prompt}"
    candidates: list[tuple[int, str, str]] = []
    for binding in session.exec(
        select(ScenePropBinding).where(ScenePropBinding.scene_id == shot.scene_id)
    ).all():
        prop = session.get(PropAsset, binding.prop_asset_id)
        current_version_id = _current_reference_asset_id(session, binding.prop_asset_version_id)
        version = session.get(PropAssetVersion, current_version_id)
        if not prop or not version or version.status not in {"confirmed_current", "locked"}:
            continue
        score = _prop_relevance_score(prop, shot_text)
        if score >= 12:
            candidates.append((score, prop.prop_code, version.id))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [asset_id for _, _, asset_id in candidates[:3]]


def _best_scene_reference_id(session: Session, shot: Shot, block: VpBlock) -> str | None:
    shot_text = f"{shot.name}\n{block.prompt_copy or block.prompt}"
    groups = (
        ("森林", "红泥", "泥坡", "训练场", "车辙", "林道"),
        ("工厂", "装配", "检测", "测试台", "工业"),
        ("产品矩阵", "成长阶梯", "开阔地", "群像"),
        ("黑色", "落版", "品牌精神", "收束", "无文字背景"),
    )
    candidates: list[tuple[int, int, str]] = []
    for scene_asset in session.exec(
        select(SceneAsset).where(SceneAsset.scene_id == shot.scene_id)
    ).all():
        versions = session.exec(
            select(SceneAssetVersion)
            .where(
                SceneAssetVersion.scene_asset_id == scene_asset.id,
                SceneAssetVersion.status.in_(["confirmed_current", "locked"]),
            )
            .order_by(SceneAssetVersion.version_number.desc())
        ).all()
        if not versions:
            continue
        asset_text = f"{scene_asset.name} {scene_asset.description} {scene_asset.spatial_layout} {scene_asset.time_weather_light}"
        score = sum(
            8
            for words in groups
            for word in words
            if word in shot_text and word in asset_text
        )
        if scene_asset.name and scene_asset.name in shot_text:
            score += 30
        current_bonus = 1 if versions[0].id == block.scene_asset_version_id else 0
        candidates.append((score, current_bonus, versions[0].id))
    if not candidates:
        return block.scene_asset_version_id
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return candidates[0][2] if candidates[0][0] > 0 else block.scene_asset_version_id


def _build_reference_bindings(session: Session, block: VpBlock, shot: Shot) -> list[dict[str, Any]]:
    from app.services.asset_reference_policy import requirement_allows_version

    scene = session.get(Scene, shot.scene_id)
    episode = session.get(Episode, scene.episode_id) if scene else None
    project_id = episode.project_id if episode else ""
    current_storyboard = _active(
        StoryboardShotVersion,
        session,
        StoryboardShotVersion.shot_id,
        shot.id,
    )
    asset_ids = [
        value
        for value in (
            current_storyboard.id if current_storyboard else block.storyboard_version_id,
            _best_scene_reference_id(session, shot, block),
        )
        if value
    ]
    asset_ids.extend(_shot_character_reference_ids(session, shot, block))
    asset_ids.extend(_scene_prop_reference_ids(session, shot, block))
    bindings: list[dict[str, Any]] = []
    for asset_id in dict.fromkeys(asset_ids):
        if project_id and not requirement_allows_version(session, project_id, asset_id, shot.scene_id):
            continue
        info = _reference_asset_info(session, asset_id)
        if not info:
            continue
        asset_type, role, label, asset_path = info
        bindings.append({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "role": role,
            "label": label,
            "asset_path": asset_path,
            "purpose": SEEDANCE_REFERENCE_ROLE_PURPOSES[role],
        })
        if len(bindings) == SEEDANCE_MAX_REFERENCE_IMAGES:
            break
    for index, binding in enumerate(bindings, start=1):
        binding["token"] = f"@图片{index}"
    return bindings


def _reference_candidates(
    session: Session,
    shot: Shot,
    project: Project,
) -> list[dict[str, Any]]:
    from app.services.asset_reference_policy import requirement_allows_version

    candidates: list[dict[str, Any]] = []

    def add(asset_id: str) -> None:
        if not requirement_allows_version(session, project.id, asset_id, shot.scene_id):
            return
        info = _reference_asset_info(session, asset_id)
        if not info or any(item["asset_id"] == asset_id for item in candidates):
            return
        asset_type, role, label, asset_path = info
        candidates.append({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "role": role,
            "label": label,
            "asset_path": asset_path,
            "asset_url": _asset_url(project, asset_path),
            "purpose": SEEDANCE_REFERENCE_ROLE_PURPOSES[role],
            "media_type": _reference_media_type(session, asset_id),
        })

    for item in session.exec(
        select(StoryboardShotVersion).where(
            StoryboardShotVersion.shot_id == shot.id,
            StoryboardShotVersion.status.in_(["confirmed_current", "locked"]),
        ).order_by(StoryboardShotVersion.version_number.desc())
    ).all():
        add(item.id)
    for scene_asset in session.exec(select(SceneAsset).where(SceneAsset.scene_id == shot.scene_id)).all():
        for item in session.exec(
            select(SceneAssetVersion).where(
                SceneAssetVersion.scene_asset_id == scene_asset.id,
                SceneAssetVersion.status.in_(["confirmed_current", "locked"]),
            ).order_by(SceneAssetVersion.version_number.desc())
        ).all():
            add(item.id)
    for character in session.exec(select(Character).where(
        Character.project_id == project.id,
        Character.is_archived == False,  # noqa: E712
    )).all():
        for item in session.exec(select(CharacterMasterVersion).where(
            CharacterMasterVersion.character_id == character.id,
            CharacterMasterVersion.status.in_(["confirmed_current", "locked"]),
        ).order_by(CharacterMasterVersion.version_number.desc())).all():
            add(item.id)
        for costume in session.exec(select(Costume).where(
            Costume.character_id == character.id,
            Costume.is_archived == False,  # noqa: E712
        )).all():
            for item in session.exec(select(CostumeVersion).where(
                CostumeVersion.costume_id == costume.id,
                CostumeVersion.status.in_(["confirmed_current", "locked"]),
            ).order_by(CostumeVersion.version_number.desc())).all():
                add(item.id)
    for prop in session.exec(select(PropAsset).where(
        PropAsset.project_id == project.id,
        PropAsset.is_archived == False,  # noqa: E712
    )).all():
        for item in session.exec(select(PropAssetVersion).where(
            PropAssetVersion.prop_asset_id == prop.id,
            PropAssetVersion.status.in_(["confirmed_current", "locked"]),
        ).order_by(PropAssetVersion.version_number.desc())).all():
            add(item.id)
    for source in session.exec(select(SourceFile).where(
        SourceFile.project_id == project.id,
        SourceFile.category == "reference",
    ).order_by(SourceFile.created_at.desc())).all():
        if _source_file_media_type(source):
            add(source.id)
    return candidates


def _manual_reference_bindings(
    session: Session,
    previous: dict[str, Any],
) -> list[dict[str, Any]]:
    assets = previous.get("assets")
    if not isinstance(assets, dict) or assets.get("reference_bindings_mode") != "manual":
        return []
    bindings = assets.get("reference_bindings")
    if not isinstance(bindings, list):
        return []
    refreshed: list[dict[str, Any]] = []
    for item in bindings[:50]:
        if not isinstance(item, dict):
            continue
        asset_id = _current_reference_asset_id(session, str(item.get("asset_id") or ""))
        if any(existing["asset_id"] == asset_id for existing in refreshed):
            continue
        info = _reference_asset_info(session, asset_id)
        if not info:
            continue
        asset_type, role, label, asset_path = info
        refreshed.append({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "role": role,
            "label": label,
            "asset_path": asset_path,
            "media_type": str(item.get("media_type") or "image"),
            "purpose": str(item.get("purpose") or SEEDANCE_REFERENCE_ROLE_PURPOSES[role]),
            "must_preserve": str(item.get("must_preserve") or ""),
            "must_not_transfer": str(item.get("must_not_transfer") or ""),
        })
    media_counts = {"image": 0, "video": 0, "audio": 0}
    for binding in refreshed:
        media_type = binding["media_type"] if binding["media_type"] in media_counts else "image"
        media_counts[media_type] += 1
        token_label = {"image": "图片", "video": "视频", "audio": "音频"}[media_type]
        binding["token"] = f"@{token_label}{media_counts[media_type]}"
    return refreshed


def _compile_seedance_reference_prompt(
    source_prompt: str,
    bindings: list[dict[str, Any]],
    model_family: str = "seedance-2.0",
) -> str:
    prompt = source_prompt.strip()
    if not bindings:
        return prompt
    lines = [f"【{model_family} 全能参考绑定】"]
    lines.extend(
        (
            f"{binding['token']}（{binding['label']}）：用途={binding['purpose']}；"
            f"必须保持={binding.get('must_preserve') or '该素材承担的指定特征'}；"
            f"禁止迁移={binding.get('must_not_transfer') or '未指定的背景、文字、构图或身份特征'}"
        )
        for binding in bindings
    )
    lines += [
        "严格按以上 @引用分工执行；不得互换图片用途，也不得把故事板文字、分格线或无关参考图背景生成进成片。",
        "",
        "【镜头执行】",
        prompt,
    ]
    return "\n".join(lines)


def _compile_provider_prompt(
    source_prompt: str,
    bindings: list[dict[str, Any]],
    model_family: str,
    *,
    precision_items: list[dict[str, Any]] | None = None,
    previous_report: dict[str, Any] | None = None,
    optimization_enabled: bool = True,
) -> tuple[str, dict[str, Any]]:
    if model_family == "seedance-2.5":
        previous_sections = (
            previous_report.get("structured_sections")
            if isinstance(previous_report, dict)
            and isinstance(previous_report.get("structured_sections"), dict)
            else None
        )
        return optimize_seedance25_prompt(
            source_prompt,
            bindings,
            precision_items=precision_items,
            previous_sections=previous_sections,
            enabled=optimization_enabled,
        )
    return _compile_seedance_reference_prompt(source_prompt, bindings, model_family), {
        "enabled": False,
        "mode": "not_applicable",
        "rule_id": "",
        "rule_version": "",
        "warnings": [],
    }


def _jimeng_reference_assets(
    session: Session,
    project: Project,
    canonical: dict[str, Any],
    projects_root: Path,
) -> list[Path]:
    root = _project_root(projects_root, project)
    assets = canonical.get("assets") if isinstance(canonical.get("assets"), dict) else {}
    bindings = assets.get("reference_bindings") if isinstance(assets, dict) else None
    refs = (
        [item.get("asset_id") for item in bindings if isinstance(item, dict)]
        if isinstance(bindings, list)
        else assets.get("reference_images", [])
    )
    paths: list[Path] = []
    for value in refs:
        info = _reference_asset_info(session, str(value))
        if not info:
            continue
        candidate = root / info[3]
        if candidate.exists():
            paths.append(candidate)
    return paths


def jimeng_cli_readiness(
    session: Session,
    task_id: str,
    settings: Settings,
    runner: JimengCliRunner | None = None,
) -> JimengCliReadinessView:
    runner = runner or JimengCliRunner()
    task, job, profile, shot, _, _, project = _jimeng_task_context(session, task_id)
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    canonical = (
        _refresh_task_reference_manifest(session, task, shot, profile.id)
        if not task.external_task_id and task.status in {"blocked", "awaiting_budget_confirm", "ready"}
        else _json(task.canonical_request_json, {})
    )
    if not task.external_task_id:
        session.commit()
    prompt = str(canonical.get("prompt") or "").strip()
    status = jimeng_cli_status(settings, runner)
    reference_assets = _jimeng_reference_assets(session, project, canonical, settings.projects_root)
    assets = canonical.get("assets") if isinstance(canonical.get("assets"), dict) else {}
    reference_bindings = assets.get("reference_bindings") if isinstance(assets, dict) else []
    if not isinstance(reference_bindings, list):
        reference_bindings = []
    tokens = [str(item.get("token") or "") for item in reference_bindings if isinstance(item, dict)]
    reference_map_ready = bool(
        reference_bindings
        and len(reference_bindings) == len(reference_assets)
        and len(reference_bindings) <= JIMENG_MAX_REFERENCE_IMAGES
        and tokens == [f"@图片{index}" for index in range(1, len(tokens) + 1)]
        and all(token in prompt for token in tokens)
    )
    reference_bindings_view = [
        {
            **item,
            "asset_url": _asset_url(project, str(item.get("asset_path") or "")),
        }
        for item in reference_bindings
        if isinstance(item, dict)
    ]
    reference_candidates = _reference_candidates(session, shot, project)
    requested_storyboard = _task_storyboard_reference(session, canonical)
    current_storyboard = _active(
        StoryboardShotVersion,
        session,
        StoryboardShotVersion.shot_id,
        shot.id,
    )
    storyboard_reference_ready = bool(
        requested_storyboard
        and current_storyboard
        and requested_storyboard.id == current_storyboard.id
        and requested_storyboard.status in {"confirmed_current", "locked"}
    )
    duration_issue = _duration_plan_issue(session, task, canonical)
    model_id = _jimeng_model_id(canonical)
    if task.external_task_id:
        model_id = _submitted_jimeng_model_id(session, task) or model_id
    model = next(item for item in JIMENG_VIDEO_MODELS if item.id == model_id)
    duration = int(canonical.get("duration_seconds") or 0)
    resolution = str(canonical.get("resolution") or "720p")
    cost_status, _, _ = _cost_estimate_details(profile, job.estimated_cost)
    confirmation_label = "预算确认" if cost_status == "estimated" else "费用风险确认"
    gate_items = [
        LiveReadinessGateView(
            label="即梦 CLI",
            passed=status.installed,
            detail="已安装 dreamina" if status.installed else status.blocking_reason,
        ),
        LiveReadinessGateView(
            label="即梦账号",
            passed=status.logged_in,
            detail=status.credit_summary or status.blocking_reason or "请先在终端登录即梦 CLI。",
        ),
        LiveReadinessGateView(
            label="受控批量队列",
            passed=True,
            detail=f"当前批次 {len(tasks)} 个任务；后台逐条调用即梦 CLI。",
        ),
        LiveReadinessGateView(
            label="分镜提示词",
            passed=bool(prompt),
            detail="已有可提交提示词" if prompt else "请先生成分镜视频提示词。",
        ),
        LiveReadinessGateView(
            label="全能参考绑定",
            passed=reference_map_ready,
            detail=(
                f"已按上传顺序绑定 {len(reference_bindings)} 张图片，并在实际提交提示词中逐项写入 @图片1-@图片{len(reference_bindings)}。"
                if reference_map_ready
                else "参考图缺少明确的 @图片N 用途绑定、文件不存在或超过 9 张；不能让 Seedance 自行猜测素材用途。"
            ),
        ),
        LiveReadinessGateView(
            label="正式故事板引用",
            passed=storyboard_reference_ready,
            detail=(
                f"已绑定当前正式故事板：{Path(current_storyboard.image_path).name}"
                if storyboard_reference_ready and current_storyboard
                else f"任务仍引用历史故事板：{Path(requested_storyboard.image_path).name}；当前正式版是 {Path(current_storyboard.image_path).name}。请重新准备任务。"
                if requested_storyboard and current_storyboard
                else "当前任务缺少已确认或锁定的正式故事板引用。"
            ),
        ),
        LiveReadinessGateView(
            label="时长限制",
            passed=model.min_duration <= duration <= model.max_duration,
            detail=f"{duration or '未知'} 秒；{model.label} 的即梦 CLI 多模态视频支持 {model.min_duration}-{model.max_duration} 秒。",
        ),
        LiveReadinessGateView(
            label="分辨率限制",
            passed=resolution in model.supported_resolutions,
            detail=f"当前 {resolution}；{model.label} 支持 {' / '.join(model.supported_resolutions)}。",
        ),
        LiveReadinessGateView(
            label="镜头时长规划",
            passed=not duration_issue,
            detail=duration_issue or "当前镜头时长来自镜头任务规划，不是统一默认值。",
        ),
        LiveReadinessGateView(
            label=confirmation_label,
            passed=job.budget_confirmed,
            detail=(
                "已确认预计费用"
                if job.budget_confirmed and cost_status == "estimated"
                else "已确认费用风险"
                if job.budget_confirmed
                else "请先确认预计费用。"
                if cost_status == "estimated"
                else "费用未知，请先核对即梦积分价格和账户余额。"
            ),
        ),
        LiveReadinessGateView(
            label="任务状态",
            passed=task.status == "ready",
            detail="可提交" if task.status == "ready" else f"当前状态为 {task.status}；只有可提交状态能发给即梦 CLI。",
        ),
    ]
    return JimengCliReadinessView(
        ready=all(item.passed for item in gate_items),
        model_id=model_id,
        gate_items=gate_items,
        risk_notice="点击提交会调用本机 dreamina CLI，使用你已登录的即梦账号，可能消耗积分；提交前请人工核对价格。",
        prompt_preview=prompt[:180],
        asset_count=len(reference_assets),
        reference_bindings=reference_bindings_view,
        reference_candidates=reference_candidates,
    )


def _jimeng_cli_context(
    session: Session,
    task_id: str,
    settings: Settings,
    confirm_live_request: bool,
    runner: JimengCliRunner | None = None,
):
    if not confirm_live_request:
        raise HTTPException(409, "即梦 CLI 请求未确认。请在页面确认本次提交/查询/下载。")
    runner = runner or JimengCliRunner()
    readiness = jimeng_cli_readiness(session, task_id, settings, runner)
    task, job, profile, shot, scene, episode, project = _jimeng_task_context(session, task_id)
    canonical = _json(task.canonical_request_json, {})
    return runner, readiness, task, job, profile, shot, scene, episode, project, canonical


def jimeng_cli_submit_task(
    session: Session,
    task_id: str,
    settings: Settings,
    confirm_live_request: bool,
    runner: JimengCliRunner | None = None,
) -> str:
    runner, readiness, task, job, profile, _, _, _, project, canonical = _jimeng_cli_context(session, task_id, settings, confirm_live_request, runner)
    if not readiness.ready:
        missing = "；".join(item.label for item in readiness.gate_items if not item.passed)
        raise HTTPException(409, f"即梦 CLI 提交条件未通过：{missing}")
    prompt = str(canonical.get("prompt") or "").strip()
    reference_assets = _jimeng_reference_assets(session, project, canonical, settings.projects_root)
    reference_bindings = canonical.get("assets", {}).get("reference_bindings", [])
    result = runner.submit_multimodal2video(
        prompt=prompt,
        model_version=readiness.model_id,
        duration=int(canonical.get("duration_seconds") or 5),
        ratio=str(canonical.get("aspect_ratio") or "16:9"),
        video_resolution=str(canonical.get("resolution") or "720p"),
        images=reference_assets,
    )
    if not result.ok:
        if _is_transient_jimeng_submit_error(result.error):
            _record_jimeng_submit_transient(
                session,
                task,
                profile,
                result.error,
                summary=result.summary,
            )
            raise HTTPException(503, "即梦参考图上传暂时超时，后台将自动重试同一镜头。")
        task.status = "failed"
        task.error_message = result.error
        task.updated_at = utc_now()
        session.add(task)
        session.add(ProviderRun(
            task_id=task.id,
            provider_profile_id=profile.id,
            action="jimeng_cli_submit_failed",
            response_snapshot_json=json.dumps({"summary": result.summary, "error": result.error, "outbound_request_sent": True}, ensure_ascii=False),
        ))
        session.commit()
        raise HTTPException(502, f"即梦 CLI 提交失败：{result.error}")
    submit_id = extract_submit_id(result.data)
    if not submit_id:
        raise HTTPException(502, "即梦 CLI 输出中缺少 submit_id。")
    submit_provider_status = extract_provider_status(result.data)
    if normalize_status(submit_provider_status) == "failed":
        reason = str(
            result.data.get("fail_reason")
            or result.data.get("error")
            or result.data.get("message")
            or result.summary
            or "即梦拒绝了本次提交。"
        )
        if _is_transient_jimeng_submit_error(reason):
            _record_jimeng_submit_transient(
                session,
                task,
                profile,
                reason,
                attempt_id=submit_id,
                summary=result.summary,
            )
            raise HTTPException(503, "即梦参考图上传暂时超时，后台将自动重试同一镜头。")
        task.external_task_id = submit_id
        task.status = "failed"
        task.error_message = reason
        task.updated_at = utc_now()
        session.add(task)
        session.add(ProviderRun(
            task_id=task.id,
            provider_profile_id=profile.id,
            action="jimeng_cli_submit_failed",
            response_snapshot_json=json.dumps({
                "submit_id": submit_id,
                "model_id": readiness.model_id,
                "provider_status": submit_provider_status,
                "summary": result.summary,
                "error": reason,
                "outbound_request_sent": True,
            }, ensure_ascii=False),
        ))
        session.commit()
        raise HTTPException(502, f"即梦 CLI 未创建生成任务：{reason}")
    verification = runner.list_task(submit_id=submit_id, limit=1)
    provider_status = extract_provider_status(verification.data) if verification.ok else ""
    listed_items = verification.data.get("items") if isinstance(verification.data, dict) else None
    task_recorded = bool(
        isinstance(listed_items, list)
        and any(isinstance(item, dict) and extract_submit_id(item) == submit_id for item in listed_items)
    )
    task.external_task_id = submit_id
    normalized_status = normalize_status(provider_status or extract_provider_status(result.data) or "verifying")
    task.status = (
        "submitted"
        if verification.ok and task_recorded and normalized_status == "verifying"
        else normalized_status
    )
    task.error_message = (
        ""
        if verification.ok and task_recorded
        else f"任务 ID 已返回，但即梦任务列表暂未确认这条记录：{verification.error or '尚未同步'}"
    )
    options = canonical.get("provider_options")
    if not isinstance(options, dict):
        options = {}
    options["jimeng_model_version"] = readiness.model_id
    canonical["provider_options"] = options
    task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
    task.updated_at = utc_now()
    job.submission_channel = "jimeng"
    job.updated_at = utc_now()
    session.add(task)
    session.add(job)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=profile.id,
        action="jimeng_cli_submit",
        response_snapshot_json=json.dumps({
            "submit_id": submit_id,
            "model_id": readiness.model_id,
            "provider_status": provider_status,
            "summary": result.summary,
            "verification_summary": verification.summary,
            "verification_ok": verification.ok,
            "task_recorded": task_recorded,
            "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
            "reference_manifest": reference_bindings,
            "uploaded_image_count": len(reference_assets),
            "outbound_request_sent": True,
        }, ensure_ascii=False),
    ))
    session.add(CostUsageLog(provider="jimeng_cli", model_name=readiness.model_id, module_type="video_cli_submit", estimated_cost=None, task_id=task.id))
    session.commit()
    return job.project_id


def _jimeng_cli_poll_task_unlocked(
    session: Session,
    task_id: str,
    settings: Settings,
    confirm_live_request: bool,
    runner: JimengCliRunner | None = None,
) -> str:
    runner, _, task, job, profile, _, _, _, _, _ = _jimeng_cli_context(session, task_id, settings, confirm_live_request, runner)
    if not task.external_task_id:
        raise HTTPException(409, "任务还没有提交到即梦 CLI。")
    latest_submit = session.exec(
        select(ProviderRun)
        .where(
            ProviderRun.task_id == task.id,
            ProviderRun.action.in_(["jimeng_cli_submit", "jimeng_cli_submit_failed"]),
        )
        .order_by(ProviderRun.created_at.desc())
    ).first()
    if latest_submit:
        snapshot = _json(latest_submit.response_snapshot_json, {})
        summary_payload = _json(str(snapshot.get("summary") or ""), {})
        if not isinstance(summary_payload, dict):
            summary_payload = {}
        submit_status = str(snapshot.get("provider_status") or extract_provider_status(summary_payload))
        if normalize_status(submit_status) == "failed":
            reason = str(
                snapshot.get("error")
                or summary_payload.get("fail_reason")
                or summary_payload.get("message")
                or "即梦在提交阶段拒绝了任务。"
            )
            task.status = "failed"
            task.error_message = reason
            task.updated_at = utc_now()
            session.add(task)
            session.add(ProviderRun(
                task_id=task.id,
                provider_profile_id=profile.id,
                action="jimeng_cli_poll_recovered_submit_failure",
                response_snapshot_json=json.dumps({
                    "status": "failed",
                    "provider_status": submit_status,
                    "error": reason,
                }, ensure_ascii=False),
            ))
            session.commit()
            return job.project_id
    result = runner.query_result(task.external_task_id)
    if not result.ok:
        session.add(ProviderRun(task_id=task.id, provider_profile_id=profile.id, action="jimeng_cli_poll_failed", response_snapshot_json=json.dumps({"summary": result.summary, "monitor_error": result.error, "will_retry": True}, ensure_ascii=False)))
        session.commit()
        raise HTTPException(502, f"即梦 CLI 查询失败：{result.error}")
    provider_status = extract_provider_status(result.data)
    queue_info = extract_queue_info(result.data)
    queue_status = str(queue_info.get("queue_status") or "")
    provider_normalized = normalize_status(provider_status)
    queue_normalized = normalize_status(queue_status)
    normalized = (
        provider_normalized
        if provider_normalized in {"failed", "completed", "processing"}
        else queue_normalized or provider_normalized
    )
    if normalized:
        task.status = normalized
    task.error_message = (
        str(result.data.get("fail_reason") or result.data.get("error") or result.data.get("error_message") or result.data.get("message") or result.summary)
        if task.status == "failed"
        else ""
    )
    task.updated_at = utc_now()
    session.add(task)
    session.add(ProviderRun(task_id=task.id, provider_profile_id=profile.id, action="jimeng_cli_poll", response_snapshot_json=json.dumps({
        "status": task.status,
        "provider_status": provider_status,
        "queue_info": queue_info,
        "summary": result.summary,
    }, ensure_ascii=False)))
    session.commit()
    return job.project_id


def jimeng_cli_poll_task(
    session: Session,
    task_id: str,
    settings: Settings,
    confirm_live_request: bool,
    runner: JimengCliRunner | None = None,
) -> str:
    with video_task_lock(task_id):
        return _jimeng_cli_poll_task_unlocked(
            session,
            task_id,
            settings,
            confirm_live_request,
            runner,
        )


def _jimeng_cli_download_task_unlocked(
    session: Session,
    task_id: str,
    settings: Settings,
    confirm_live_request: bool,
    runner: JimengCliRunner | None = None,
) -> str:
    runner, _, task, job, profile, shot, scene, episode, project, _ = _jimeng_cli_context(session, task_id, settings, confirm_live_request, runner)
    if not task.external_task_id:
        raise HTTPException(409, "任务还没有提交到即梦 CLI。")
    if task.status != "completed":
        raise HTTPException(409, "只有已完成的视频任务可以下载。请先查询状态。")
    root = _project_root(settings.projects_root, project)
    scope = _scope_code(episode, scene)
    download_dir = root / "07_results/generated_videos" / scope / "jimeng_cli_downloads"
    result = runner.query_result(task.external_task_id, download_dir=download_dir)
    if not result.ok:
        raise HTTPException(502, f"即梦 CLI 下载失败：{result.error}")
    candidates = [Path(path) for path in extract_video_paths(result.data, result.summary)]
    candidates += sorted(download_dir.glob("*.mp4")) + sorted(download_dir.glob("*.mov"))
    source = next((path for path in candidates if path.exists() and path.is_file()), None)
    if source is None:
        raise HTTPException(502, "即梦 CLI 没有返回可下载的视频文件。")
    suffix = source.suffix.lower() if source.suffix.lower() in {".mp4", ".mov"} else ".mp4"
    relative = f"07_results/generated_videos/{scope}/{uuid4().hex[:12]}_{shot.shot_code}_jimeng_cli{suffix}"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    number = len(session.exec(select(VideoResultVersion).where(VideoResultVersion.shot_id == shot.id)).all()) + 1
    session.add(VideoResultVersion(task_id=task.id, shot_id=shot.id, version_number=number, video_path=relative, source="jimeng_cli", status="imported"))
    task.result_video_path = relative
    task.status = "imported"
    task.error_message = ""
    task.updated_at = utc_now()
    session.add(task)
    session.add(ProviderRun(task_id=task.id, provider_profile_id=profile.id, action="jimeng_cli_download", response_snapshot_json=json.dumps({"downloaded": True, "source": str(source.name), "video_path": relative}, ensure_ascii=False)))
    session.commit()
    return job.project_id


def jimeng_cli_download_task(
    session: Session,
    task_id: str,
    settings: Settings,
    confirm_live_request: bool,
    runner: JimengCliRunner | None = None,
) -> str:
    with video_task_lock(task_id):
        task = session.get(BatchVideoTask, task_id)
        job = session.get(BatchVideoJob, task.job_id) if task else None
        if task is None or job is None:
            raise HTTPException(404, "视频任务不存在。")
        if task.result_video_path:
            task.status = "imported"
            task.updated_at = utc_now()
            session.add(task)
            session.commit()
            return job.project_id
        existing = session.exec(
            select(VideoResultVersion)
            .where(VideoResultVersion.task_id == task.id)
            .order_by(VideoResultVersion.created_at.desc())
        ).first()
        if existing:
            task.result_video_path = existing.video_path
            task.status = "imported"
            task.updated_at = utc_now()
            session.add(task)
            session.commit()
            return job.project_id
        return _jimeng_cli_download_task_unlocked(
            session,
            task_id,
            settings,
            confirm_live_request,
            runner,
        )


def set_default_profile(session: Session, profile_id: str) -> ProviderProfileView:
    profile = session.get(VideoProviderProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "服务通道配置不存在。")
    for item in session.exec(select(VideoProviderProfile)).all():
        item.is_default = item.id == profile.id
        session.add(item)
    session.commit(); session.refresh(profile)
    return _profile_view(profile)


def _active(model, session: Session, field, value):
    return next((item for item in session.exec(select(model).where(field == value).order_by(model.version_number.desc())).all() if item.status in {"confirmed_current", "locked"}), None)


def _shot_assets(session: Session, shot: Shot, has_character: bool):
    scene_asset = session.exec(select(SceneAsset).where(SceneAsset.scene_id == shot.scene_id)).first()
    scene_version = _active(SceneAssetVersion, session, SceneAssetVersion.scene_asset_id, scene_asset.id) if scene_asset else None
    storyboard = _active(StoryboardShotVersion, session, StoryboardShotVersion.shot_id, shot.id)
    binding = session.exec(select(SceneCharacterBinding).where(SceneCharacterBinding.scene_id == shot.scene_id)).first() if has_character else None
    master = session.get(CharacterMasterVersion, binding.character_master_version_id) if binding else None
    costume = session.get(CostumeVersion, binding.costume_version_id) if binding else None
    return scene_version, storyboard, binding, master, costume


def _extract_json_candidates(text: str) -> list[Any]:
    candidates: list[str] = []
    import re

    candidates.extend(match.group(1) for match in re.finditer(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.S | re.I))
    for open_char, close_char in [("{", "}"), ("[", "]")]:
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start >= 0 and end > start:
            candidates.append(text[start:end + 1])
    parsed: list[Any] = []
    for candidate in candidates:
        try:
            parsed.append(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    return parsed


def _content_has_overlong_time_range(content: Any, max_seconds: int) -> bool:
    if isinstance(content, str):
        return time_range_exceeds_seedance_limit(content, max_seconds)
    if isinstance(content, list):
        return any(_content_has_overlong_time_range(item, max_seconds) for item in content)
    if isinstance(content, dict):
        return any(_content_has_overlong_time_range(value, max_seconds) for value in content.values())
    return False


def _normalize_ai_precision_items(text: str, duration_seconds: int = MAX_SEEDANCE_CLIP_SECONDS) -> tuple[list[dict[str, Any]], str]:
    raw_items: Any = None
    for payload in _extract_json_candidates(text):
        if isinstance(payload, dict):
            raw_items = payload.get("vp_precision_18") or payload.get("precision_items") or payload.get("items")
        elif isinstance(payload, list):
            raw_items = payload
        if isinstance(raw_items, list):
            break
    if not isinstance(raw_items, list):
        raise HTTPException(422, "AI 未返回可解析的 VP-PRECISION-18 JSON。")
    by_number: dict[int, dict[str, Any]] = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            number = int(raw.get("number"))
        except (TypeError, ValueError):
            continue
        if not 1 <= number <= 18:
            continue
        content = raw.get("content")
        if content is None:
            content = raw.get("value") or raw.get("text") or ""
        by_number[number] = {
            "number": number,
            "title": VP_PRECISION_18_TITLES[number - 1],
            "content": content,
        }
    missing = [str(index) for index in range(1, 19) if index not in by_number]
    if missing:
        raise HTTPException(422, f"AI 返回的 VP-PRECISION-18 缺少第 {', '.join(missing)} 项。")
    items = [by_number[index] for index in range(1, 19)]
    if _content_has_overlong_time_range(items[4]["content"], min(duration_seconds, MAX_SEEDANCE_CLIP_SECONDS)):
        raise HTTPException(
            422,
            f"AI 返回的第 5 项分时段镜头超过 {min(duration_seconds, MAX_SEEDANCE_CLIP_SECONDS)} 秒。"
            f"Seedance 单条最高 {MAX_SEEDANCE_CLIP_SECONDS} 秒，请拆镜头或重新生成。",
        )
    prompt_value = items[3]["content"]
    prompt_copy = prompt_value if isinstance(prompt_value, str) else json.dumps(prompt_value, ensure_ascii=False)
    if not prompt_copy.strip():
        raise HTTPException(422, "AI 返回的第 4 项“可复制完整视频提示词”为空。")
    return items, prompt_copy


def _normalize_director_tech_payload(text: str) -> dict[str, Any]:
    for payload in _extract_json_candidates(text):
        if not isinstance(payload, dict):
            continue
        value = payload.get("director_tech_plus") or payload.get("director_technique") or payload.get("director_tech")
        if isinstance(value, dict):
            return value
    return {}


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[｜|,，、;；\n]+", value) if item.strip()]
    return []


def create_ai_vp_block(
    session: Session,
    settings: Settings,
    shot_id: str,
    payload: VpBlockCreate,
    ai_payload: AiTextRunCreate,
) -> str:
    shot = session.get(Shot, shot_id)
    if not shot:
        raise HTTPException(404, "镜头不存在。")
    _, _, project = _scene_with_project(session, shot.scene_id)
    profile = session.get(VideoProviderProfile, payload.provider_profile_id)
    if not profile:
        raise HTTPException(404, "服务通道配置不存在。")
    recommended_duration, _ = recommend_video_duration(shot.name)
    duration_seconds = payload.duration_seconds or recommended_duration
    if duration_seconds > MAX_SEEDANCE_CLIP_SECONDS:
        raise HTTPException(422, duration_limit_message(duration_seconds))
    assetless_final = payload.package_stage == "final_execution" and project.creative_goal == "prompt_storyboard"
    effective_has_character = payload.has_character and not assetless_final
    scene_version, storyboard, binding, master, costume = _shot_assets(session, shot, effective_has_character)
    if assetless_final:
        # The lightweight route deliberately creates a text-to-video prompt without
        # pretending that nonexistent character, costume or scene assets are locked.
        scene_version = None
        binding = None
        master = None
        costume = None
    missing = []
    if payload.package_stage == "final_execution":
        latest_draft = next((
            item for item in session.exec(
                select(VpBlock).where(VpBlock.shot_id == shot.id).order_by(VpBlock.version_number.desc())
            ).all()
            if item.schema_version == "vp_precision_18_v1" and item.package_stage == "director_draft"
        ), None)
        if not assetless_final and not scene_version:
            missing.append("成片提示词缺少已确认场景资产。")
        if (
            not storyboard
            or storyboard.schema_version not in {"vp_precision_18_v1", "unified_sb_v1"}
            or storyboard.style_validation_status != "passed"
            or storyboard.axis_validation_status != "passed"
        ):
            missing.append("成片提示词缺少已确认且绑定时间轴的统一故事板。")
        elif latest_draft and storyboard.vp_basis_block_id != latest_draft.id:
            missing.append("已确认故事板仍使用旧时长。请到故事板页按最新分镜提示词重建并确认后再生成成片提示词。")
        if effective_has_character and (not binding or binding.consistency_status != "passed" or not master or not costume):
            missing.append("含人物镜头缺少一致性通过的人物与服装绑定。")
    if missing:
        raise HTTPException(409, "；".join(missing))
    ai_payload.module_type = "vp_precision_18"
    ai_payload.target_type = "shot"
    ai_payload.target_id = shot.id
    asset_mode_instruction = (
        "\n当前项目选择了‘只要分镜提示词和故事板’。本次必须生成无参考图成片提示词，按文生视频使用；"
        "不得写入不存在的资产编号，不得声称人物、服装、场景或道具的跨镜一致性已经锁定。"
        "人物、场景和道具只能依据剧本、导演方案及已确认故事板进行文字描述。"
        "VP 第3项和第15项必须明确：未绑定正式资产图，无法保证跨镜外观一致性；"
        "后续补齐资产图后，应重新生成资产绑定版成片提示词。"
        if assetless_final
        else ""
    )
    ai_payload.user_note = (
        f"{ai_payload.user_note}\n"
        "请输出严格 JSON，键名为 vp_precision_18，数组内必须包含 number/title/content，number 必须为 1-18，且第 4 项必须是可直接复制给视频模型的完整中文提示词。\n"
        f"{seedance_duration_instruction(duration_seconds)}\n"
        "同时可输出 director_tech_plus 对象，包含 director_technique、close_in_start_time、close_in_from_shot_size、close_in_to_shot_size、close_in_target_detail、close_in_emotional_meaning、close_in_return_to_character、close_in_tail_frame、detail_shot_candidates、selected_detail_shot、detail_shot_time_range、detail_shot_meaning、detail_shot_relation_to_character、montage_type、montage_goal、montage_shot_count、montage_entry_point、montage_exit_point、montage_rhythm、montage_return_to_main_story、symbolic_object、object_state_change、symbolic_meaning、object_state_time_range、relation_to_character_emotion、meaning_chain。\n"
        "若适合使用特写进连接器，请写明从哪一秒开始推近、从什么景别推到什么景别、推到什么细节、细节表达什么信息、是否回到人物反应、截尾帧停在哪里；这些内容也必须体现在 VP-PRECISION-18 第5/6/8/10/11/17/18项中。\n"
        f"镜头基础：{shot.shot_code}｜{shot.name}｜{duration_seconds}s｜{payload.aspect_ratio}｜{payload.resolution}｜{payload.generation_mode}。\n"
        f"包阶段：{payload.package_stage}。负面约束：{payload.negative_prompt}。"
        f"{asset_mode_instruction}"
    ).strip()
    run = run_project_ai_text(session, settings, project.id, ai_payload)
    precision_items, prompt_copy = _normalize_ai_precision_items(run.response_text, duration_seconds)
    director_tech = _normalize_director_tech_payload(run.response_text)
    meaning_chain = director_tech.get("meaning_chain") if isinstance(director_tech.get("meaning_chain"), dict) else {}
    values = session.exec(select(VpBlock.version_number).where(VpBlock.shot_id == shot.id)).all()
    block = VpBlock(
        shot_id=shot.id,
        version_number=max(values, default=0) + 1,
        character_master_version_id=master.id if master else None,
        costume_version_id=costume.id if costume else None,
        scene_asset_version_id=scene_version.id if scene_version else None,
        storyboard_version_id=storyboard.id if payload.package_stage == "final_execution" and storyboard else None,
        basis_vp_block_id=storyboard.vp_basis_block_id if payload.package_stage == "final_execution" and storyboard else None,
        precision_json=json.dumps(precision_items, ensure_ascii=False),
        prompt_copy=prompt_copy,
        prompt=payload.prompt.strip() or prompt_copy,
        negative_prompt=payload.negative_prompt,
        duration_seconds=duration_seconds,
        aspect_ratio=payload.aspect_ratio,
        resolution=payload.resolution,
        generation_mode=payload.generation_mode,
        provider_profile_id=payload.provider_profile_id,
        has_character=effective_has_character,
        package_stage=payload.package_stage,
        director_technique=str(director_tech.get("director_technique") or ""),
        close_in_start_time=str(director_tech.get("close_in_start_time") or ""),
        close_in_from_shot_size=str(director_tech.get("close_in_from_shot_size") or ""),
        close_in_to_shot_size=str(director_tech.get("close_in_to_shot_size") or ""),
        close_in_target_detail=str(director_tech.get("close_in_target_detail") or ""),
        close_in_emotional_meaning=str(director_tech.get("close_in_emotional_meaning") or ""),
        close_in_return_to_character=bool(director_tech.get("close_in_return_to_character") or False),
        close_in_tail_frame=str(director_tech.get("close_in_tail_frame") or ""),
        detail_shot_candidates_json=json.dumps(
            _normalize_string_list(director_tech.get("detail_shot_candidates")),
            ensure_ascii=False,
        ),
        selected_detail_shot=str(director_tech.get("selected_detail_shot") or ""),
        detail_shot_time_range=str(director_tech.get("detail_shot_time_range") or ""),
        detail_shot_meaning=str(director_tech.get("detail_shot_meaning") or ""),
        detail_shot_relation_to_character=str(director_tech.get("detail_shot_relation_to_character") or ""),
        montage_type=str(director_tech.get("montage_type") or ""),
        montage_goal=str(director_tech.get("montage_goal") or ""),
        montage_shot_count=_safe_int(director_tech.get("montage_shot_count")),
        montage_entry_point=str(director_tech.get("montage_entry_point") or ""),
        montage_exit_point=str(director_tech.get("montage_exit_point") or ""),
        montage_rhythm=str(director_tech.get("montage_rhythm") or ""),
        montage_return_to_main_story=str(director_tech.get("montage_return_to_main_story") or ""),
        symbolic_object=str(director_tech.get("symbolic_object") or ""),
        object_state_change=str(director_tech.get("object_state_change") or ""),
        symbolic_meaning=str(director_tech.get("symbolic_meaning") or ""),
        object_state_time_range=str(director_tech.get("object_state_time_range") or ""),
        relation_to_character_emotion=str(director_tech.get("relation_to_character_emotion") or ""),
        meaning_chain_json=json.dumps(meaning_chain, ensure_ascii=False),
    )
    session.add(block)
    session.commit()
    return project.id


def transition_vp(session: Session, vp_id: str, action: str) -> str:
    block = session.get(VpBlock, vp_id)
    if not block: raise HTTPException(404, "视频包版本不存在。")
    shot = session.get(Shot, block.shot_id); _, _, project = _scene_with_project(session, shot.scene_id)
    if action not in {"confirm", "lock", "rollback"}: raise HTTPException(400, "不支持该版本操作。")
    if action == "rollback" and block.status != "locked": block.status = "draft"
    elif action == "lock": block.status = "locked"
    elif action == "confirm":
        for item in session.exec(select(VpBlock).where(VpBlock.shot_id == block.shot_id)).all():
            if item.id != block.id and item.status == "confirmed_current": item.status = "history"; session.add(item)
        block.status = "confirmed_current"
    block.updated_at = utc_now(); session.add(block)
    session.flush()
    if action == "confirm" and block.package_stage == "final_execution":
        _refresh_pending_batch_jobs_for_shot(session, block.shot_id)
    session.commit()
    return project.id


def _vp_view(session: Session, block: VpBlock) -> VpBlockView:
    assetless_final = block.package_stage == "final_execution" and not any((
        block.scene_asset_version_id,
        block.character_master_version_id,
        block.costume_version_id,
    ))
    assets = (
        ["无参考图模式：未绑定正式资产图"]
        if assetless_final
        else ([f"场景资产 {block.scene_asset_version_id[:8]}"] if block.scene_asset_version_id else ["未绑定正式场景资产"])
    )
    if block.storyboard_version_id: assets.append(f"故事板 {block.storyboard_version_id[:8]}")
    if block.character_master_version_id: assets += [f"人物母版 {block.character_master_version_id[:8]}", f"服装资产 {block.costume_version_id[:8]}"]
    validations = (
        ["无参考图成片提示词", "VP-PRECISION-18 已完整生成"]
        if assetless_final
        else ["资产引用已冻结", "VP-PRECISION-18 已完整生成"]
    )
    if block.storyboard_version_id: validations += ["故事板已绑定", "轴线校验通过"]
    shot = session.get(Shot, block.shot_id)
    canonical = _canonical(session, block, shot, block.provider_profile_id) if shot else {}
    reference_bindings = canonical.get("assets", {}).get("reference_bindings", [])
    if shot and reference_bindings:
        _, _, project = _scene_with_project(session, shot.scene_id)
        reference_bindings = [
            {
                **item,
                "asset_url": _asset_url(project, str(item.get("asset_path") or "")),
            }
            for item in reference_bindings
        ]
    return VpBlockView(
        **block.model_dump(),
        precision_items=_json(block.precision_json, []),
        detail_shot_candidates=_normalize_string_list(_json(block.detail_shot_candidates_json, [])),
        meaning_chain=_json(block.meaning_chain_json, {}),
        asset_summary=assets,
        validation_items=validations,
        provider_prompt_preview=str(canonical.get("prompt") or block.prompt_copy or block.prompt),
        reference_bindings=reference_bindings,
    )


def video_package_workspace(session: Session, project_id: str) -> VideoPackageWorkspaceView:
    project = get_project(session, project_id); scenes = []
    for episode in session.exec(select(Episode).where(Episode.project_id == project.id)).all():
        for scene in session.exec(select(Scene).where(Scene.episode_id == episode.id)).all():
            shots = []
            for shot in session.exec(select(Shot).where(Shot.scene_id == scene.id, Shot.is_archived == False).order_by(Shot.shot_code)).all():  # noqa
                blocks = session.exec(select(VpBlock).where(
                    VpBlock.shot_id == shot.id,
                    VpBlock.schema_version == "vp_precision_18_v1",
                ).order_by(VpBlock.version_number.desc())).all()
                recommended_duration, duration_reason = recommend_video_duration(shot.name)
                confirmed_storyboard = _active(StoryboardShotVersion, session, StoryboardShotVersion.shot_id, shot.id)
                shots.append(VideoPackageShotView(
                    id=shot.id,
                    shot_code=shot.shot_code,
                    name=shot.name,
                    recommended_duration_seconds=recommended_duration,
                    duration_reason=duration_reason,
                    confirmed_storyboard_vp_basis_block_id=confirmed_storyboard.vp_basis_block_id if confirmed_storyboard else None,
                    versions=[_vp_view(session, item) for item in blocks],
                ))
            scenes.append(VideoPackageSceneView(id=scene.id, scope_code=_scope_code(episode, scene), name=scene.name, shots=shots))
    return VideoPackageWorkspaceView(project_id=project.id, project_code=project.project_code, scenes=scenes)


def _canonical(session: Session, block: VpBlock, shot: Shot, provider_profile_id: str) -> dict:
    from app.services.asset_reference_policy import text_only_asset_descriptions_for_scene

    profile = session.get(VideoProviderProfile, provider_profile_id)
    is_seedance25 = bool(profile and profile.provider_type == "volcengine_seedance25")
    model_family = "seedance-2.5" if is_seedance25 else "seedance-2.0"
    model_id = (
        _json(profile.config_json, {}).get("model_id", SEEDANCE25_DEFAULT_MODEL_ID)
        if is_seedance25 and profile
        else JIMENG_DEFAULT_VIDEO_MODEL_ID
    )
    bindings = _build_reference_bindings(session, block, shot)
    source_prompt = block.prompt_copy or block.prompt
    scene = session.get(Scene, shot.scene_id)
    episode = session.get(Episode, scene.episode_id) if scene else None
    text_descriptions = (
        text_only_asset_descriptions_for_scene(session, episode.project_id, shot.scene_id)
        if episode else []
    )
    prompt_input = source_prompt
    if text_descriptions:
        details = "\n".join(
            f"- {item['name']}：{item['description']}" for item in text_descriptions
        )
        prompt_input += (
            "\n非关键细节（仅按文字描述，不作为外观锁定）：\n"
            f"{details}\n"
            "在不改变关键人物身份、关键产品和已绑定参考的前提下，允许合理补全这些次要细节；不要迁移未指定的外观特征。"
        )
    provider_prompt, optimization_report = _compile_provider_prompt(
        prompt_input,
        bindings,
        model_family,
        precision_items=_json(block.precision_json, []),
    )
    return {"job_id": f"{shot.shot_code}_VID_v001", "model_family": model_family, "model_variant": "standard",
        "generation_mode": block.generation_mode, "duration_mode": "smart" if is_seedance25 else "specified",
        "prompt": provider_prompt, "source_prompt": source_prompt,
        "prompt_optimization": optimization_report,
        "negative_prompt": block.negative_prompt,
        "duration_seconds": block.duration_seconds, "resolution": block.resolution, "aspect_ratio": block.aspect_ratio,
        "generate_audio": False, "seed": 42, "assets": {
            "reference_images": [item["asset_id"] for item in bindings],
            "reference_bindings": bindings,
            "reference_videos": [],
            "reference_audios": [],
            "text_descriptions": text_descriptions,
        },
        "reference_manifest": bindings,
        "provider_model_id": model_id,
        "parent_result_version_id": None,
        "callback_url": None, "provider_profile_id": provider_profile_id,
        "provider_options": {"jimeng_model_version": JIMENG_DEFAULT_VIDEO_MODEL_ID}}


def _provider_model_id(canonical: dict[str, Any]) -> str:
    return str(canonical.get("provider_model_id") or _jimeng_model_id(canonical))


def _reference_bindings_fingerprint(canonical: dict[str, Any]) -> str:
    assets = canonical.get("assets") if isinstance(canonical.get("assets"), dict) else {}
    payload = {
        "prompt": canonical.get("prompt"),
        "duration_seconds": canonical.get("duration_seconds"),
        "resolution": canonical.get("resolution"),
        "aspect_ratio": canonical.get("aspect_ratio"),
        "model": _provider_model_id(canonical),
        "duration_mode": canonical.get("duration_mode"),
        "generation_mode": canonical.get("generation_mode"),
        "reference_bindings": assets.get("reference_bindings", []),
    }
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _invalidate_reference_confirmation(task: BatchVideoTask, canonical: dict[str, Any]) -> None:
    fingerprint = _reference_bindings_fingerprint(canonical)
    if task.reference_bindings_fingerprint != fingerprint:
        task.reference_bindings_confirmed_at = None
    task.reference_bindings_fingerprint = fingerprint


def _refresh_task_reference_manifest(
    session: Session,
    task: BatchVideoTask,
    shot: Shot,
    provider_profile_id: str,
) -> dict[str, Any]:
    block = session.get(VpBlock, task.vp_block_id) if task.vp_block_id else None
    if block is None:
        return _json(task.canonical_request_json, {})
    previous = _json(task.canonical_request_json, {})
    canonical = _canonical(session, block, shot, provider_profile_id)
    for field in (
        "provider_model_id",
        "generation_mode",
        "duration_mode",
        "duration_seconds",
        "resolution",
    ):
        if field in previous:
            canonical[field] = previous[field]
    previous_options = previous.get("provider_options")
    if isinstance(previous_options, dict):
        canonical["provider_options"].update(previous_options)
    previous_optimization = previous.get("prompt_optimization")
    if (
        canonical.get("model_family") == "seedance-2.5"
        and isinstance(previous_optimization, dict)
        and previous_optimization.get("enabled") is False
    ):
        automatic_bindings = canonical.get("assets", {}).get("reference_bindings", [])
        canonical["prompt"], canonical["prompt_optimization"] = _compile_provider_prompt(
            str(canonical.get("source_prompt") or ""),
            automatic_bindings,
            "seedance-2.5",
            precision_items=_json(block.precision_json, []),
            previous_report=previous_optimization,
            optimization_enabled=False,
        )
    manual_bindings = _manual_reference_bindings(session, previous)
    if manual_bindings:
        canonical["assets"]["reference_images"] = [item["asset_id"] for item in manual_bindings]
        canonical["assets"]["reference_bindings"] = manual_bindings
        canonical["assets"]["reference_bindings_mode"] = "manual"
        canonical["reference_manifest"] = manual_bindings
        canonical["prompt"], canonical["prompt_optimization"] = _compile_provider_prompt(
            str(canonical.get("source_prompt") or ""),
            manual_bindings,
            str(canonical.get("model_family") or "seedance-2.0"),
            precision_items=_json(block.precision_json, []),
            previous_report=previous.get("prompt_optimization") if isinstance(previous, dict) else None,
            optimization_enabled=bool(
                previous.get("prompt_optimization", {}).get("enabled", True)
                if isinstance(previous.get("prompt_optimization"), dict)
                else True
            ),
        )
    task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
    _invalidate_reference_confirmation(task, canonical)
    task.updated_at = utc_now()
    session.add(task)
    return canonical


def update_video_reference_bindings(
    session: Session,
    task_id: str,
    payload: VideoReferenceBindingsUpdate,
) -> str:
    task, job, profile, shot, _, _, project = _jimeng_task_context(session, task_id)
    if task.external_task_id or task.status not in {"blocked", "awaiting_budget_confirm", "ready"}:
        raise HTTPException(409, "任务已经提交，不能中途替换参考图。请等待任务结束后重新建立队列。")
    candidate_items = {
        item["asset_id"]: item
        for item in _reference_candidates(session, shot, project)
    }
    requested_items = payload.reference_items or []
    legacy_asset_ids = payload.asset_ids or []
    asset_ids = list(dict.fromkeys(
        [item.asset_id.strip() for item in requested_items if item.asset_id.strip()]
        or [value.strip() for value in legacy_asset_ids if value.strip()]
    ))
    if not asset_ids:
        raise HTTPException(422, "至少保留 1 张参考图。")
    invalid = [value for value in asset_ids if value not in candidate_items]
    if invalid:
        raise HTTPException(422, "所选参考图不属于当前项目的已确认资产，请刷新后重新选择。")
    canonical = _json(task.canonical_request_json, {})
    bindings = []
    media_counts = {"image": 0, "video": 0, "audio": 0}
    for asset_id in asset_ids:
        asset_type, role, label, asset_path = _reference_asset_info(session, asset_id)  # type: ignore[misc]
        requested = next((item for item in requested_items if item.asset_id == asset_id), None)
        actual_media_type = str(candidate_items[asset_id].get("media_type") or "image")
        media_type = requested.media_type if requested else actual_media_type
        if media_type != actual_media_type:
            raise HTTPException(
                422,
                f"{label} 的真实类型是 {actual_media_type}，不能作为 {media_type} 参考提交。",
            )
        media_counts[media_type] += 1
        index = media_counts[media_type]
        token_label = {"image": "图片", "video": "视频", "audio": "音频"}[media_type]
        bindings.append({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "role": role,
            "label": label,
            "asset_path": asset_path,
            "media_type": media_type,
            "purpose": requested.purpose if requested else SEEDANCE_REFERENCE_ROLE_PURPOSES[role],
            "must_preserve": requested.must_preserve if requested else "",
            "must_not_transfer": requested.must_not_transfer if requested else "",
            "token": f"@{token_label}{index}",
        })
    is_seedance25 = str(canonical.get("model_family") or "") == "seedance-2.5"
    if not is_seedance25 and (media_counts["video"] or media_counts["audio"]):
        raise HTTPException(422, "当前 Provider 只支持图片参考；视频和音频参考仅可用于 Seedance 2.5。")
    if not is_seedance25 and media_counts["image"] > JIMENG_MAX_REFERENCE_IMAGES:
        raise HTTPException(422, f"当前 Provider 最多支持 {JIMENG_MAX_REFERENCE_IMAGES} 张图片参考。")
    if media_counts["image"] > 30 or media_counts["video"] > 10 or media_counts["audio"] > 10 or sum(media_counts.values()) > 50:
        raise HTTPException(422, "参考素材超出 Seedance 2.5 限制：图片 30、视频 10、音频 10。")
    assets = canonical.get("assets") if isinstance(canonical.get("assets"), dict) else {}
    assets["reference_images"] = [item["asset_id"] for item in bindings if item["media_type"] == "image"]
    assets["reference_videos"] = [item["asset_id"] for item in bindings if item["media_type"] == "video"]
    assets["reference_audios"] = [item["asset_id"] for item in bindings if item["media_type"] == "audio"]
    assets["reference_bindings"] = bindings
    assets["reference_bindings_mode"] = "manual"
    canonical["assets"] = assets
    canonical["reference_manifest"] = bindings
    block = session.get(VpBlock, task.vp_block_id) if task.vp_block_id else None
    optimization = canonical.get("prompt_optimization") if isinstance(canonical.get("prompt_optimization"), dict) else {}
    canonical["prompt"], canonical["prompt_optimization"] = _compile_provider_prompt(
        str(canonical.get("source_prompt") or ""),
        bindings,
        str(canonical.get("model_family") or "seedance-2.0"),
        precision_items=_json(block.precision_json, []) if block else None,
        previous_report=optimization,
        optimization_enabled=bool(optimization.get("enabled", True)),
    )
    task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
    _invalidate_reference_confirmation(task, canonical)
    existing_missing = [str(item) for item in _json(task.missing_items_json, [])]
    if is_seedance25:
        existing_missing = _replace_seedance25_reference_missing(existing_missing, bindings)
    task.missing_items_json = json.dumps(existing_missing, ensure_ascii=False)
    task.updated_at = utc_now()
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    task.status = "blocked" if existing_missing else "awaiting_budget_confirm"
    sibling_missing = any(
        sibling.id != task.id and bool(_json(sibling.missing_items_json, []))
        for sibling in session.exec(
            select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)
        ).all()
    )
    job.status = "blocked" if existing_missing or sibling_missing else "awaiting_budget_confirm"
    session.add(task)
    session.add(job)
    session.commit()
    return project.id


def reset_video_reference_bindings(session: Session, task_id: str) -> str:
    task, job, profile, shot, _, _, project = _jimeng_task_context(session, task_id)
    if task.external_task_id or task.status not in {"blocked", "awaiting_budget_confirm", "ready"}:
        raise HTTPException(409, "只有尚未提交的任务可以恢复自动推荐参考图。")
    previous = _json(task.canonical_request_json, {})
    assets = previous.get("assets") if isinstance(previous.get("assets"), dict) else {}
    assets.pop("reference_bindings_mode", None)
    previous["assets"] = assets
    task.canonical_request_json = json.dumps(previous, ensure_ascii=False)
    _refresh_task_reference_manifest(session, task, shot, profile.id)
    task.reference_bindings_confirmed_at = None
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    job.status = "awaiting_budget_confirm"
    session.add(task)
    session.add(job)
    session.commit()
    return project.id


def update_batch_jimeng_video_model(session: Session, job_id: str, model_id: str) -> str:
    job = session.get(BatchVideoJob, job_id)
    if not job:
        raise HTTPException(404, "批量任务不存在。")
    if model_id not in {item.id for item in jimeng_video_models()}:
        raise HTTPException(422, "即梦视频模型无效，请重新选择。")
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    if any(task.external_task_id or task.status not in {"blocked", "awaiting_budget_confirm", "ready"} for task in tasks):
        raise HTTPException(409, "批次已经开始，不能统一更换正在运行任务的模型。失败或重做镜头仍可单独调整。")
    for task in tasks:
        canonical = _json(task.canonical_request_json, {})
        options = canonical.get("provider_options") if isinstance(canonical.get("provider_options"), dict) else {}
        options["jimeng_model_version"] = model_id
        canonical["provider_options"] = options
        task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
        _invalidate_reference_confirmation(task, canonical)
        if task.status == "ready":
            task.status = "awaiting_budget_confirm"
        task.updated_at = utc_now()
        session.add(task)
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    job.status = "awaiting_budget_confirm"
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    return job.project_id


def refresh_batch_task_preflight(session: Session, task_id: str) -> str:
    task, job, profile, shot, _, _, project = _jimeng_task_context(session, task_id)
    if task.external_task_id or task.status not in {"blocked", "awaiting_budget_confirm", "ready"}:
        raise HTTPException(409, "只有尚未提交的任务可以重新检查条件。")
    previous = _json(task.canonical_request_json, {})
    block, _, missing, estimate = _queue_task_values(
        session,
        shot,
        profile,
        job.submission_channel,
        _jimeng_model_id(previous),
    )
    task.vp_block_id = block.id if block else None
    canonical = _refresh_task_reference_manifest(session, task, shot, profile.id) if block else {}
    if canonical and job.submission_channel == "volcengine_seedance25":
        bindings = canonical.get("reference_manifest") or canonical.get("assets", {}).get("reference_bindings", [])
        missing = _replace_seedance25_reference_missing(missing, bindings)
    task.missing_items_json = json.dumps(missing, ensure_ascii=False)
    task.error_message = ""
    task.status = "blocked" if missing else "awaiting_budget_confirm"
    task.updated_at = utc_now()
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    job.estimated_cost = estimate
    job.status = "blocked" if missing else "awaiting_budget_confirm"
    job.updated_at = utc_now()
    session.add(task)
    session.add(job)
    session.commit()
    return project.id


def _queue_task_values(
    session: Session,
    shot: Shot,
    profile: VideoProviderProfile,
    submission_channel: str = "jimeng",
    jimeng_model_id: str = JIMENG_DEFAULT_VIDEO_MODEL_ID,
) -> tuple[VpBlock | None, dict, list[str], float | None]:
    block = next((
        item for item in session.exec(
            select(VpBlock).where(VpBlock.shot_id == shot.id).order_by(VpBlock.version_number.desc())
        ).all()
        if item.status in {"confirmed_current", "locked"}
        and item.schema_version == "vp_precision_18_v1"
        and item.package_stage == "final_execution"
    ), None)
    missing = [] if block else ["缺少已确认的 VP-PRECISION-18 正式执行包。"]
    canonical = _canonical(session, block, shot, profile.id) if block else {}
    estimate = None
    if block:
        recommended_duration, duration_reason = recommend_video_duration(shot.name)
        if (
            submission_channel != "volcengine_seedance25"
            and block.duration_seconds == 5
            and recommended_duration != 5
        ):
            missing.append(
                f"当前成片提示词仍使用旧版统一 5 秒默认值；主规则建议 {recommended_duration} 秒。"
                f"{duration_reason} 请先重建分镜提示词和故事板时间轴。"
            )
        if submission_channel == "volcengine_seedance25":
            canonical["model_family"] = "seedance-2.5"
            canonical["provider_model_id"] = str(
                _json(profile.config_json, {}).get("model_id") or SEEDANCE25_DEFAULT_MODEL_ID
            )
            canonical["duration_mode"] = str(canonical.get("duration_mode") or "smart")
            canonical["resolution"] = str(canonical.get("resolution") or "720p")
            duration_error = validate_provider_duration(
                int(canonical.get("duration_seconds") or 0),
                "volcengine_seedance25",
                str(canonical.get("duration_mode") or "smart"),
            )
            if duration_error:
                missing.append(duration_error)
            if canonical["resolution"] not in {"480p", "720p"}:
                missing.append("Seedance 2.5 首期仅开放官方明确支持的 480p / 720p。")
            bindings = canonical.get("reference_manifest") or canonical.get("assets", {}).get("reference_bindings", [])
            missing.extend(_seedance25_reference_missing(bindings))
            estimate = None
        elif submission_channel == "jimeng":
            available_models = jimeng_video_models()
            model = next((item for item in available_models if item.id == jimeng_model_id), None)
            if model is None:
                missing.append(
                    f"当前 dreamina CLI 未开放模型 {jimeng_model_id}。即梦网页可见模型不等于 CLI 已支持，请检查 CLI 升级后重新选择。"
                )
                model = next(
                    (item for item in JIMENG_VIDEO_MODELS if item.id == JIMENG_DEFAULT_VIDEO_MODEL_ID),
                )
            duration = int(canonical.get("duration_seconds") or 0)
            resolution = str(canonical.get("resolution") or "")
            if not model.min_duration <= duration <= model.max_duration:
                missing.append(
                    f"{model.label} 支持 {model.min_duration}-{model.max_duration} 秒；当前为 {duration or '未知'} 秒。"
                )
            if resolution not in model.supported_resolutions:
                missing.append(
                    f"{model.label} 不支持 {resolution or '未知'} 分辨率；可选 {' / '.join(model.supported_resolutions)}。"
                )
        else:
            provider = _provider_for(profile)
            missing += provider.validate_request(canonical, _json(profile.capabilities_json, {}))
            estimate = provider.estimate_cost(canonical, _json(profile.price_configs_json, []))
        canonical["submission_channel"] = submission_channel
        canonical["provider_model_id"] = (
            str(canonical.get("provider_model_id") or SEEDANCE25_DEFAULT_MODEL_ID)
            if submission_channel == "volcengine_seedance25"
            else jimeng_model_id if submission_channel == "jimeng"
            else str(_json(profile.config_json, {}).get("model_id") or "seedance-2.0-fast")
        )
        if submission_channel == "jimeng":
            selected_model = next((item for item in jimeng_video_models() if item.id == jimeng_model_id), None)
            canonical["provider_capability_snapshot"] = selected_model.model_dump() if selected_model else {
                "provider_type": "jimeng_cli",
                "provider_model_id": jimeng_model_id,
                "available": False,
            }
        elif submission_channel == "volcengine_seedance25":
            canonical["provider_capability_snapshot"] = SEEDANCE25_MODEL.model_dump()
        else:
            canonical["provider_capability_snapshot"] = video_provider_models("huimeng")[0].model_dump()
    return block, canonical, missing, estimate


def _refresh_pending_batch_jobs_for_shot(session: Session, shot_id: str) -> None:
    anchors = session.exec(select(BatchVideoTask).where(BatchVideoTask.shot_id == shot_id)).all()
    allowed = {"blocked", "awaiting_budget_confirm", "ready"}
    for job_id in dict.fromkeys(task.job_id for task in anchors):
        job = session.get(BatchVideoJob, job_id)
        profile = session.get(VideoProviderProfile, job.provider_profile_id) if job else None
        if not job or not profile:
            continue
        tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
        if any(task.status not in allowed or task.external_task_id or task.result_video_path for task in tasks):
            continue
        total_cost = 0.0
        reliable_price = True
        for task in tasks:
            shot = session.get(Shot, task.shot_id)
            previous_model_id = _jimeng_model_id(_json(task.canonical_request_json, {}))
            block, canonical, missing, estimate = _queue_task_values(
                session,
                shot,
                profile,
                job.submission_channel,
                previous_model_id,
            )
            task.vp_block_id = block.id if block else None
            if block:
                canonical = _refresh_task_reference_manifest(session, task, shot, profile.id)
            if canonical and job.submission_channel == "volcengine_seedance25":
                bindings = canonical.get("reference_manifest") or canonical.get("assets", {}).get("reference_bindings", [])
                missing = _replace_seedance25_reference_missing(missing, bindings)
            if canonical:
                canonical["provider_options"]["jimeng_model_version"] = previous_model_id
            if block and estimate is None:
                reliable_price = False
            elif estimate is not None:
                total_cost += estimate
            task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
            task.missing_items_json = json.dumps(missing, ensure_ascii=False)
            task.status = "blocked" if missing else "awaiting_budget_confirm"
            task.error_message = ""
            task.updated_at = utc_now()
            session.add(task)
        job.budget_confirmed = False
        job.status = "draft"
        job.estimated_cost = round(total_cost, 4) if reliable_price else None
        job.updated_at = utc_now()
        session.add(job)


def _profile_currency(profile: VideoProviderProfile) -> str:
    prices = _json(profile.price_configs_json, [])
    return str(prices[0].get("currency", "UNSPECIFIED")) if prices else "UNSPECIFIED"


def _cost_estimate_details(profile: VideoProviderProfile, estimated_cost: float | None) -> tuple[str, str, str]:
    prices = _json(profile.price_configs_json, [])
    price = prices[0] if prices else {}
    if estimated_cost is not None and price.get("price_status", "known") == "known":
        status = "estimated"
    else:
        status = "unknown"
    note = str(price.get("note", "")).strip()
    if not note and status == "unknown":
        note = "当前服务配置没有可可靠计算的单价，请在服务商账户核对价格和余额。"
    return status, note, str(price.get("source_url", "")).strip()


def create_batch(
    session: Session,
    scene_id: str,
    provider_profile_id: str,
    max_tasks: int,
    submission_channel: str = "jimeng",
) -> str:
    scene, _, project = _scene_with_project(session, scene_id); profile = session.get(VideoProviderProfile, provider_profile_id)
    if not profile and provider_profile_id == "seedance_mock":
        raise HTTPException(409, "开发调试视频演练已从正式流程关闭。请使用慧梦真实单镜服务通道。")
    if not profile: raise HTTPException(404, "服务通道配置不存在。")
    if not profile.is_enabled: raise HTTPException(409, "服务通道已停用。")
    if profile.provider_type == "seedance_mock":
        raise HTTPException(409, "开发调试视频演练已从正式流程关闭。请使用慧梦真实单镜服务通道。")
    if submission_channel not in {"huimeng", "jimeng", "volcengine_seedance25"}:
        raise HTTPException(422, "本次视频生成服务无效，请重新选择。")
    job = BatchVideoJob(
        project_id=project.id,
        scene_id=scene.id,
        provider_profile_id=profile.id,
        submission_channel=submission_channel,
        currency=_profile_currency(profile),
    )
    session.add(job); session.flush()
    total_cost = 0.0
    reliable_price = True
    confirmed_shot_ids = set(
        session.exec(
            select(VideoResultVersion.shot_id).where(VideoResultVersion.status == "confirmed")
        ).all()
    )
    pending_shots = [
        shot
        for shot in session.exec(
            select(Shot)
            .where(Shot.scene_id == scene.id, Shot.is_archived == False)  # noqa
            .order_by(Shot.shot_code)
        ).all()
        if shot.id not in confirmed_shot_ids
    ][:max_tasks]
    if not pending_shots:
        raise HTTPException(409, "当前场次所有镜头都已通过视频验收，无需继续建立队列。")
    for shot in pending_shots:
        block, canonical, missing, estimate = _queue_task_values(
            session,
            shot,
            profile,
            submission_channel,
        )
        if block and estimate is None:
            reliable_price = False
        elif estimate is not None:
            total_cost += estimate
        session.add(BatchVideoTask(job_id=job.id, shot_id=shot.id, vp_block_id=block.id if block else None,
            canonical_request_json=json.dumps(canonical, ensure_ascii=False), missing_items_json=json.dumps(missing, ensure_ascii=False),
            reference_bindings_fingerprint=_reference_bindings_fingerprint(canonical) if canonical else "",
            status="blocked" if missing else "awaiting_budget_confirm"))
    job.estimated_cost = round(total_cost, 4) if reliable_price else None
    session.add(job); session.commit(); return project.id


def review_video_result(
    session: Session,
    result_id: str,
    decision: str,
) -> str:
    result = session.get(VideoResultVersion, result_id)
    if not result:
        raise HTTPException(404, "视频结果不存在。")
    task = session.get(BatchVideoTask, result.task_id)
    if not task or task.status != "imported" or not task.result_video_path:
        raise HTTPException(409, "视频尚未完整保存到本地，暂不能验收。")
    job = session.get(BatchVideoJob, task.job_id)
    if not job:
        raise HTTPException(404, "视频批次不存在。")
    if decision not in {"confirm", "redo"}:
        raise HTTPException(422, "视频验收决定无效。")
    result.status = "confirmed" if decision == "confirm" else "rejected"
    session.add(result)
    shot = session.get(Shot, result.shot_id)
    if not shot:
        raise HTTPException(404, "视频对应镜头不存在。")
    _, _, project = _scene_with_project(session, shot.scene_id)
    if decision == "redo":
        task.external_task_id = None
        task.result_video_path = None
        task.error_message = ""
        task.status = "ready" if job.budget_confirmed else "awaiting_budget_confirm"
        task.updated_at = utc_now()
        session.add(task)
    _update_batch_job_status(session, job)
    session.commit()
    return project.id


def confirm_all_video_results(session: Session, job_id: str) -> str:
    job = session.get(BatchVideoJob, job_id)
    if not job:
        raise HTTPException(404, "视频批次不存在。")
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    confirmed = 0
    for task in tasks:
        if task.status != "imported" or not task.result_video_path:
            continue
        result = session.exec(
            select(VideoResultVersion)
            .where(VideoResultVersion.task_id == task.id)
            .order_by(VideoResultVersion.created_at.desc())
        ).first()
        if result and result.status != "confirmed":
            result.status = "confirmed"
            session.add(result)
            confirmed += 1
    if not confirmed:
        raise HTTPException(409, "当前没有等待验收且已完整保存的视频。")
    _update_batch_job_status(session, job)
    session.commit()
    return job.project_id


def _update_batch_job_status(session: Session, job: BatchVideoJob) -> None:
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    if not tasks:
        job.status = "draft"
    elif all(task.status == "mock_completed" for task in tasks):
        job.status = "mock_completed"
    elif any(task.status in {"verifying", "submitted", "processing", "completed"} for task in tasks):
        job.status = "processing"
    elif any(task.status == "ready" and not task.external_task_id for task in tasks) and job.dispatch_enabled:
        job.status = "dispatching"
    elif all(task.status in {"imported", "failed"} for task in tasks):
        latest_results = [
            session.exec(
                select(VideoResultVersion)
                .where(VideoResultVersion.task_id == task.id)
                .order_by(VideoResultVersion.created_at.desc())
            ).first()
            for task in tasks
        ]
        if all(result and result.status == "confirmed" for result in latest_results):
            job.status = "completed"
        elif any(task.status == "failed" for task in tasks):
            job.status = "partial_failed"
        else:
            job.status = "awaiting_review"
    elif any(task.status == "failed" for task in tasks):
        job.status = "partial_failed"
    elif any(task.status == "blocked" for task in tasks):
        job.status = "blocked"
    elif not job.budget_confirmed:
        job.status = "awaiting_budget_confirm"
    else:
        job.status = "ready"
    job.updated_at = utc_now()
    session.add(job)


def update_batch_submission_channel(
    session: Session,
    job_id: str,
    submission_channel: str,
    huimeng_provider_profile_id: str = "",
) -> str:
    job = session.get(BatchVideoJob, job_id)
    if not job:
        raise HTTPException(404, "批量任务不存在。")
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    allowed = {"blocked", "awaiting_budget_confirm", "ready"}
    if any(task.status not in allowed or task.external_task_id or task.result_video_path for task in tasks):
        raise HTTPException(409, "当前任务已经提交，不能切换视频服务。请等待本次任务结束后重新建立队列。")
    if submission_channel not in {"huimeng", "jimeng", "volcengine_seedance25"}:
        raise HTTPException(422, "本次视频生成服务无效，请重新选择。")

    if submission_channel == "huimeng":
        profile_id = huimeng_provider_profile_id or job.provider_profile_id
        profile = session.get(VideoProviderProfile, profile_id)
        if not profile or profile.provider_type != "seedance_huimeng_live":
            raise HTTPException(409, "慧梦 API 服务配置不存在，请先在成本与设置页完成配置。")
        if profile.id != job.provider_profile_id:
            remap_batch_provider(session, job.id, profile.id)
            job = session.get(BatchVideoJob, job.id)
            tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    elif submission_channel == "volcengine_seedance25":
        profile = session.get(VideoProviderProfile, SEEDANCE25_PROFILE_ID)
        if not profile:
            raise HTTPException(409, "Seedance 2.5 Mock 服务尚未初始化，请重启后端后重试。")
        if profile.id != job.provider_profile_id:
            remap_batch_provider(session, job.id, profile.id)
            job = session.get(BatchVideoJob, job.id)
            tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()

    job.submission_channel = submission_channel
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    job.status = "awaiting_budget_confirm"
    job.updated_at = utc_now()
    total_cost = 0.0
    reliable_price = True
    for task in tasks:
        previous = _json(task.canonical_request_json, {})
        model_id = _jimeng_model_id(previous)
        shot = session.get(Shot, task.shot_id)
        block, canonical, missing, estimate = _queue_task_values(
            session,
            shot,
            session.get(VideoProviderProfile, job.provider_profile_id),
            submission_channel,
            model_id,
        )
        task.vp_block_id = block.id if block else None
        if block:
            canonical = _refresh_task_reference_manifest(
                session,
                task,
                shot,
                job.provider_profile_id,
            )
        if block and estimate is None:
            reliable_price = False
        elif estimate is not None:
            total_cost += estimate
        options = canonical.get("provider_options")
        if not isinstance(options, dict):
            options = {}
        options["submission_channel"] = submission_channel
        options["jimeng_model_version"] = model_id
        canonical["provider_options"] = options
        if submission_channel == "volcengine_seedance25":
            canonical["model_family"] = "seedance-2.5"
            canonical["provider_model_id"] = str(
                _json(session.get(VideoProviderProfile, job.provider_profile_id).config_json, {}).get("model_id")
                or SEEDANCE25_DEFAULT_MODEL_ID
            )
            canonical["duration_mode"] = "smart"
        task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
        _invalidate_reference_confirmation(task, canonical)
        task.missing_items_json = json.dumps(missing, ensure_ascii=False)
        task.status = "blocked" if missing else "awaiting_budget_confirm"
        task.error_message = ""
        task.updated_at = utc_now()
        session.add(task)
    job.estimated_cost = (
        round(total_cost, 4)
        if submission_channel == "huimeng" and reliable_price
        else None
    )
    if any(task.status == "blocked" for task in tasks):
        job.status = "blocked"
    session.add(job)
    session.commit()
    return job.project_id


def _apply_generation_settings(
    task: BatchVideoTask,
    payload: VideoGenerationSettingsUpdate,
) -> None:
    canonical = _json(task.canonical_request_json, {})
    is_seedance25 = str(canonical.get("model_family") or "") == "seedance-2.5"
    submission_channel = str(canonical.get("submission_channel") or _json(canonical.get("provider_options") if isinstance(canonical.get("provider_options"), dict) else {}, {}).get("submission_channel") or "jimeng")
    provider_type = "volcengine_seedance25" if is_seedance25 else "seedance-2.0"
    provider_options = canonical.get("provider_options") if isinstance(canonical.get("provider_options"), dict) else {}
    provider_model_id = str(
        payload.provider_model_id
        or canonical.get("provider_model_id")
        or provider_options.get("jimeng_model_version")
        or (SEEDANCE25_DEFAULT_MODEL_ID if is_seedance25 else JIMENG_DEFAULT_VIDEO_MODEL_ID)
    )
    resolution = str(payload.resolution or canonical.get("resolution") or "720p")
    duration_mode = payload.duration_mode or str(canonical.get("duration_mode") or ("smart" if is_seedance25 else "specified"))
    if is_seedance25:
        if provider_model_id != SEEDANCE25_DEFAULT_MODEL_ID:
            raise HTTPException(422, "Seedance 2.5 模型 ID 无效，请刷新模型目录。")
        if resolution not in {"480p", "720p"}:
            raise HTTPException(422, "Seedance 2.5 首期只支持 480p / 720p。")
    elif submission_channel == "jimeng" and provider_model_id not in {item.id for item in jimeng_video_models()}:
        raise HTTPException(422, "当前视频模型无效，请刷新模型目录。")
    duration_seconds = int(payload.duration_seconds or canonical.get("duration_seconds") or 0)
    error = validate_provider_duration(duration_seconds, provider_type, duration_mode)
    if error:
        raise HTTPException(422, error)
    canonical["provider_model_id"] = provider_model_id
    canonical["duration_mode"] = duration_mode
    canonical["duration_seconds"] = duration_seconds
    canonical["resolution"] = resolution
    if payload.generation_mode:
        canonical["generation_mode"] = payload.generation_mode
    if is_seedance25 and payload.prompt_optimization_enabled is not None:
        optimization = canonical.get("prompt_optimization") if isinstance(canonical.get("prompt_optimization"), dict) else {}
        assets = canonical.get("assets") if isinstance(canonical.get("assets"), dict) else {}
        bindings = assets.get("reference_bindings") if isinstance(assets.get("reference_bindings"), list) else []
        canonical["prompt"], canonical["prompt_optimization"] = _compile_provider_prompt(
            str(canonical.get("source_prompt") or ""),
            bindings,
            "seedance-2.5",
            previous_report=optimization,
            optimization_enabled=payload.prompt_optimization_enabled,
        )
    if submission_channel == "jimeng":
        provider_options["jimeng_model_version"] = provider_model_id
        canonical["provider_options"] = provider_options
        selected = next((item for item in jimeng_video_models() if item.id == provider_model_id), None)
        canonical["provider_capability_snapshot"] = selected.model_dump() if selected else {}
    elif submission_channel == "huimeng":
        canonical["provider_capability_snapshot"] = video_provider_models("huimeng")[0].model_dump()
    task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
    _invalidate_reference_confirmation(task, canonical)
    task.updated_at = utc_now()


def update_task_generation_settings(
    session: Session,
    task_id: str,
    payload: VideoGenerationSettingsUpdate,
) -> str:
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    if not task or not job:
        raise HTTPException(404, "视频任务不存在。")
    if task.external_task_id or task.status not in {"blocked", "awaiting_budget_confirm", "ready"}:
        raise HTTPException(409, "任务已经提交，不能修改正在运行任务的生成设置。")
    _apply_generation_settings(task, payload)
    task.status = "awaiting_budget_confirm"
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    job.status = "awaiting_budget_confirm"
    session.add(task)
    session.add(job)
    session.commit()
    return job.project_id


def update_job_generation_settings(
    session: Session,
    job_id: str,
    payload: VideoGenerationSettingsUpdate,
) -> str:
    job = session.get(BatchVideoJob, job_id)
    if not job:
        raise HTTPException(404, "批量任务不存在。")
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    if any(task.external_task_id or task.status not in {"blocked", "awaiting_budget_confirm", "ready"} for task in tasks):
        raise HTTPException(409, "批次已经开始，不能统一修改正在运行任务的生成设置。")
    for task in tasks:
        _apply_generation_settings(task, payload)
        task.status = "awaiting_budget_confirm"
        session.add(task)
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    job.status = "awaiting_budget_confirm"
    job.estimated_cost = None
    session.add(job)
    session.commit()
    return job.project_id


def remap_batch_provider(
    session: Session,
    job_id: str,
    provider_profile_id: str,
) -> str:
    job = session.get(BatchVideoJob, job_id)
    profile = session.get(VideoProviderProfile, provider_profile_id)
    if not job: raise HTTPException(404, "批量任务不存在。")
    if not profile and provider_profile_id == "seedance_mock":
        raise HTTPException(409, "开发调试视频演练已从正式流程关闭。请使用慧梦真实单镜服务通道。")
    if not profile: raise HTTPException(404, "服务通道配置不存在。")
    if not profile.is_enabled: raise HTTPException(409, "服务通道已停用。")
    if profile.provider_type == "seedance_mock":
        raise HTTPException(409, "开发调试视频演练已从正式流程关闭。请使用慧梦真实单镜服务通道。")
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    allowed = {"blocked", "awaiting_budget_confirm", "ready"}
    if any(task.status not in allowed or task.external_task_id or task.result_video_path for task in tasks):
        raise HTTPException(409, "只有尚未提交且没有结果文件的任务可以重映射 Provider。")
    total_cost = 0.0
    reliable_price = True
    for task in tasks:
        shot = session.get(Shot, task.shot_id)
        previous_model_id = _jimeng_model_id(_json(task.canonical_request_json, {}))
        block, canonical, missing, estimate = _queue_task_values(
            session,
            shot,
            profile,
            job.submission_channel,
            previous_model_id,
        )
        if canonical:
            canonical["provider_options"]["jimeng_model_version"] = previous_model_id
        if block and estimate is None:
            reliable_price = False
        elif estimate is not None:
            total_cost += estimate
        task.vp_block_id = block.id if block else None
        task.canonical_request_json = json.dumps(canonical, ensure_ascii=False)
        _invalidate_reference_confirmation(task, canonical)
        task.missing_items_json = json.dumps(missing, ensure_ascii=False)
        task.status = "blocked" if missing else "awaiting_budget_confirm"
        task.error_message = ""
        task.updated_at = utc_now()
        session.add(task)
        session.add(ProviderRun(
            task_id=task.id, provider_profile_id=profile.id, action="remap",
            response_snapshot_json=json.dumps({"mode": "remap_only", "outbound_request_sent": False}, ensure_ascii=False),
        ))
    job.provider_profile_id = profile.id
    job.currency = _profile_currency(profile)
    job.budget_confirmed = False
    job.batch_authorized = False
    job.dispatch_enabled = False
    job.status = "draft"
    job.estimated_cost = round(total_cost, 4) if reliable_price else None
    job.updated_at = utc_now()
    session.add(job); session.commit()
    return job.project_id


def confirm_budget(session: Session, job_id: str) -> str:
    job = session.get(BatchVideoJob, job_id)
    if not job: raise HTTPException(404, "批量任务不存在。")
    job.budget_confirmed = True; job.status = "ready"; session.add(job)
    for task in session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all():
        if task.status == "awaiting_budget_confirm": task.status = "ready"; session.add(task)
    session.commit(); return job.project_id


def confirm_task_reference_bindings(session: Session, task_id: str) -> str:
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    if not task or not job:
        raise HTTPException(404, "视频任务不存在。")
    if task.external_task_id or task.status not in {"blocked", "awaiting_budget_confirm", "ready"}:
        raise HTTPException(409, "只有尚未提交的镜头可以确认参考绑定。")
    canonical = _json(task.canonical_request_json, {})
    bindings = canonical.get("assets", {}).get("reference_bindings", [])
    if _json(task.missing_items_json, []) or not bindings:
        raise HTTPException(409, "当前镜头仍有缺失项或没有有效参考图，不能确认。")
    task.reference_bindings_fingerprint = _reference_bindings_fingerprint(canonical)
    task.reference_bindings_confirmed_at = utc_now()
    task.updated_at = utc_now()
    session.add(task)
    session.commit()
    return job.project_id


def confirm_all_reference_bindings(session: Session, job_id: str) -> str:
    job = session.get(BatchVideoJob, job_id)
    if not job:
        raise HTTPException(404, "批量任务不存在。")
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    blockers = []
    for task in tasks:
        canonical = _json(task.canonical_request_json, {})
        if task.external_task_id or task.status not in {"blocked", "awaiting_budget_confirm", "ready"}:
            continue
        if _json(task.missing_items_json, []) or not canonical.get("assets", {}).get("reference_bindings", []):
            shot = session.get(Shot, task.shot_id)
            blockers.append(shot.shot_code if shot else task.id)
    if blockers:
        raise HTTPException(409, f"以下镜头仍有缺失项，不能统一确认：{'、'.join(blockers)}")
    now = utc_now()
    for task in tasks:
        if task.status in {"blocked", "awaiting_budget_confirm", "ready"} and not task.external_task_id:
            canonical = _json(task.canonical_request_json, {})
            task.reference_bindings_fingerprint = _reference_bindings_fingerprint(canonical)
            task.reference_bindings_confirmed_at = now
            task.updated_at = now
            session.add(task)
    session.commit()
    return job.project_id


def launch_batch_video_job(session: Session, job_id: str, confirm_live_request: bool) -> str:
    if not confirm_live_request:
        raise HTTPException(409, "整批真实提交尚未确认。")
    job = session.get(BatchVideoJob, job_id)
    if not job:
        raise HTTPException(404, "批量任务不存在。")
    tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
    blockers = []
    launchable_tasks = []
    for task in tasks:
        # Already submitted or saved tasks belong to the same persistent batch, but must
        # never be submitted again when the remaining shots are re-authorized.
        if task.external_task_id or task.status in {"imported", "mock_completed"}:
            continue
        if task.status not in {"awaiting_budget_confirm", "ready"} or _json(task.missing_items_json, []):
            shot = session.get(Shot, task.shot_id)
            blockers.append(f"{shot.shot_code if shot else task.id}：提交条件未通过")
            continue
        canonical = _json(task.canonical_request_json, {})
        fingerprint = _reference_bindings_fingerprint(canonical)
        if not task.reference_bindings_confirmed_at or task.reference_bindings_fingerprint != fingerprint:
            shot = session.get(Shot, task.shot_id)
            blockers.append(f"{shot.shot_code if shot else task.id}：全能参考尚未确认")
            continue
        launchable_tasks.append(task)
    if blockers:
        raise HTTPException(409, "；".join(blockers))
    if not launchable_tasks:
        raise HTTPException(409, "当前没有需要提交的新镜头；已保存或已提交的镜头不会重复生成。")
    if not job.budget_confirmed:
        raise HTTPException(409, "请先统一确认本批次预计费用或费用风险。")
    job.batch_authorized = True
    job.dispatch_enabled = True
    job.status = "dispatching"
    job.launched_at = utc_now()
    job.updated_at = utc_now()
    for task in tasks:
        if task.status == "awaiting_budget_confirm":
            task.status = "ready"
            task.updated_at = utc_now()
            session.add(task)
    session.add(job)
    session.commit()
    return job.project_id


def _placeholder_png(source: Path, target: Path, label: str) -> None:
    image = Image.new("RGB", (960, 540), "#e5e1d8"); draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 936, 516), outline="#555", width=3); draw.line((90, 420, 820, 130), fill="#444", width=4)
    draw.ellipse((250, 150, 390, 290), outline="#444", width=4); draw.text((50, 50), f"LOCAL MATERIALIZED SVG / {label}", fill="#333")
    target.parent.mkdir(parents=True, exist_ok=True); image.save(target, "PNG")


def _materialize_png(root: Path, relative_source: str | None, target: Path, label: str) -> bool:
    if relative_source:
        source = root / relative_source
        if source.exists() and source.suffix.lower() == ".png":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            return True
        if source.exists() and source.suffix.lower() == ".svg":
            _placeholder_png(source, target, label)
            return True
    return False


def _checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def jimeng_export(session: Session, job_id: str, projects_root: Path) -> str:
    job = session.get(BatchVideoJob, job_id)
    if not job: raise HTTPException(404, "批量任务不存在。")
    scene, episode, project = _scene_with_project(session, job.scene_id); root = _project_root(projects_root, project)
    version = len(list((root / "06_batch_video/jimeng_credit_exports").glob("*"))) + 1
    relative = f"06_batch_video/jimeng_credit_exports/{_scope_code(episode, scene)}_v{version:03d}"
    folder = root / relative; folder.mkdir(parents=True, exist_ok=True); manifest = {"job_id": job.id, "scope": _scope_code(episode, scene), "mode": "jimeng_manual_assist_only", "shots": []}
    execution_page = session.exec(
        select(StoryboardExecutionPage)
        .where(StoryboardExecutionPage.scene_id == scene.id)
        .order_by(StoryboardExecutionPage.version_number.desc())
    ).first()
    for task in session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all():
        shot = session.get(Shot, task.shot_id); block = session.get(VpBlock, task.vp_block_id) if task.vp_block_id else None
        if not block: continue
        storyboard = session.get(StoryboardShotVersion, block.storyboard_version_id) if block.storyboard_version_id else None
        master = session.get(CharacterMasterVersion, block.character_master_version_id) if block.character_master_version_id else None
        costume = session.get(CostumeVersion, block.costume_version_id) if block.costume_version_id else None
        scene_asset = session.get(SceneAssetVersion, block.scene_asset_version_id)
        shot_dir = folder / shot.shot_code; (shot_dir / "import_result_here").mkdir(parents=True, exist_ok=True)
        missing_export_assets: list[str] = []
        storyboard_frame_source = storyboard.image_path if storyboard else None
        storyboard_page_source = execution_page.png_path if execution_page else storyboard_frame_source
        for source, filename, label in [
            (storyboard_frame_source, "storyboard_frame.png", "storyboard_frame"),
            (storyboard_page_source, "storyboard_page.png", "storyboard_page"),
            (master.asset_path if master else None, "character_master.png", "character_master"),
            (costume.asset_path if costume else None, "costume_asset.png", "costume_asset"),
            (scene_asset.asset_path if scene_asset else None, "scene_asset.png", "scene_asset"),
        ]:
            if not _materialize_png(root, source, shot_dir / filename, f"{shot.shot_code} {label}"):
                missing_export_assets.append(filename)
        precision = _json(block.precision_json, [])
        director_technique = {
            "director_technique": block.director_technique,
            "close_in_start_time": block.close_in_start_time,
            "close_in_from_shot_size": block.close_in_from_shot_size,
            "close_in_to_shot_size": block.close_in_to_shot_size,
            "close_in_target_detail": block.close_in_target_detail,
            "close_in_emotional_meaning": block.close_in_emotional_meaning,
            "close_in_return_to_character": block.close_in_return_to_character,
            "close_in_tail_frame": block.close_in_tail_frame,
            "detail_shot_candidates": _normalize_string_list(_json(block.detail_shot_candidates_json, [])),
            "selected_detail_shot": block.selected_detail_shot,
            "detail_shot_time_range": block.detail_shot_time_range,
            "detail_shot_meaning": block.detail_shot_meaning,
            "detail_shot_relation_to_character": block.detail_shot_relation_to_character,
            "montage_type": block.montage_type,
            "montage_goal": block.montage_goal,
            "montage_shot_count": block.montage_shot_count,
            "montage_entry_point": block.montage_entry_point,
            "montage_exit_point": block.montage_exit_point,
            "montage_rhythm": block.montage_rhythm,
            "montage_return_to_main_story": block.montage_return_to_main_story,
            "symbolic_object": block.symbolic_object,
            "object_state_change": block.object_state_change,
            "symbolic_meaning": block.symbolic_meaning,
            "object_state_time_range": block.object_state_time_range,
            "relation_to_character_emotion": block.relation_to_character_emotion,
        }
        meaning_chain = _json(block.meaning_chain_json, {})
        storyboard_grid = {
            "storyboard_grid_count": storyboard.storyboard_grid if storyboard else None,
            "grid_reason": storyboard.grid_reason if storyboard else "",
            "storyboard_mode": storyboard.storyboard_mode if storyboard else "",
            "density_level": storyboard.density_level if storyboard else "",
            "annotation_layer": _json(storyboard.annotation_layer, {}) if storyboard else {},
            "timeline_nodes": _json(storyboard.timeline_nodes_json, []) if storyboard else [],
            "prompt_match": _json(storyboard.prompt_match_json, []) if storyboard else [],
            "storyboard_cells": _json(storyboard.storyboard_cells_json, []) if storyboard else [],
        }
        unified_sb_meta = _json(storyboard.unified_sb_meta_json, {}) if storyboard else {}
        full_prompt = block.vp_prompt_full or block.prompt_copy or block.prompt
        (shot_dir / "vp_prompt_full.txt").write_text(full_prompt, encoding="utf-8")
        (shot_dir / "vp_prompt_copy.txt").write_text(block.prompt_copy or block.prompt, encoding="utf-8")
        (shot_dir / "vp_precision_18.json").write_text(json.dumps(precision, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "director_technique.json").write_text(json.dumps(director_technique, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "meaning_chain.json").write_text(json.dumps(meaning_chain, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "storyboard_grid.json").write_text(json.dumps(storyboard_grid, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "unified_sb_meta.json").write_text(json.dumps(unified_sb_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "copy_card.md").write_text(
            f"# {shot.shot_code}｜即梦手动编排复制卡\n\n## 可复制提示词\n\n{block.prompt_copy or block.prompt}\n\n## 结果导入\n\n生成完成后，将 MP4 / MOV 拖回 AI 导演工作台并绑定当前 Shot ID。\n",
            encoding="utf-8",
        )
        exported_files = [path for path in shot_dir.iterdir() if path.is_file()]
        manifest["shots"].append({
            "shot_id": shot.id,
            "shot_code": shot.shot_code,
            "vp_block_id": block.id,
            "storyboard_version_id": block.storyboard_version_id,
            "asset_version_ids": {
                "character_master": block.character_master_version_id,
                "costume": block.costume_version_id,
                "scene": block.scene_asset_version_id,
            },
            "files": {path.name: _checksum(path) for path in exported_files},
            "missing_optional_files": missing_export_assets,
        })
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = f"{relative}.zip"
    with zipfile.ZipFile(root / zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob("*"):
            if path.is_file(): archive.write(path, path.relative_to(folder))
    job.jimeng_export_path = zip_path; session.add(job); session.commit(); return job.project_id


def import_video(session: Session, task_id: str, file: UploadFile, projects_root: Path) -> str:
    task = session.get(BatchVideoTask, task_id); job = session.get(BatchVideoJob, task.job_id) if task else None
    if not task or not job: raise HTTPException(404, "视频任务不存在。")
    safe = sanitize_filename(file.filename or "video.mp4"); suffix = Path(safe).suffix.lower()
    if suffix not in {".mp4", ".mov"}: raise HTTPException(400, "仅支持 MP4 / MOV 视频。")
    shot = session.get(Shot, task.shot_id); scene, episode, project = _scene_with_project(session, shot.scene_id)
    path = f"07_results/generated_videos/{_scope_code(episode, scene)}/{uuid4().hex[:12]}_{safe}"; target = _project_root(projects_root, project) / path; target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_VIDEO_IMPORT_BYTES: raise HTTPException(413, "单个视频不能超过 500 MB。")
                output.write(chunk)
    except Exception: target.unlink(missing_ok=True); raise
    number = len(session.exec(select(VideoResultVersion).where(VideoResultVersion.shot_id == shot.id)).all()) + 1
    session.add(VideoResultVersion(task_id=task.id, shot_id=shot.id, version_number=number, video_path=path, source="jimeng_manual_import"))
    task.status = "imported"; task.result_video_path = path; session.add(task); session.commit(); return job.project_id


def _task_external_provider(session: Session, task_id: str) -> str:
    runs = session.exec(
        select(ProviderRun)
        .where(ProviderRun.task_id == task_id)
        .order_by(ProviderRun.created_at.desc())
    ).all()
    for run in runs:
        if run.action.startswith("seedance25_mock"):
            return "volcengine_seedance25_mock"
        if run.action.startswith("jimeng_cli"):
            return "jimeng_cli"
        if run.action.startswith("live_"):
            return "huimeng_live"
    return ""


def seedance25_mock_submit_task(session: Session, task_id: str) -> str:
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    if not task or not job:
        raise HTTPException(404, "视频任务不存在。")
    if job.submission_channel != "volcengine_seedance25":
        raise HTTPException(409, "当前任务不是 Seedance 2.5 Mock 通道。")
    if task.external_task_id:
        return job.project_id
    canonical = _json(task.canonical_request_json, {})
    task.external_task_id = f"mock-sd25-{uuid4().hex[:16]}"
    task.status = "submitted"
    task.error_message = ""
    task.updated_at = utc_now()
    session.add(task)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=job.provider_profile_id,
        action="seedance25_mock_submit",
        response_snapshot_json=json.dumps({
            "provider_status": "mock_submitted",
            "summary": "模拟任务已进入本地监督器；未向火山方舟发送请求。",
            "outbound_request_sent": False,
            "mock_task": True,
            "canonical_request_fingerprint": sha256(
                json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        }, ensure_ascii=False),
    ))
    session.commit()
    return job.project_id


def seedance25_mock_poll_task(session: Session, task_id: str) -> str:
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    if not task or not job or not task.external_task_id:
        raise HTTPException(404, "Seedance 2.5 Mock 任务不存在。")
    polls = session.exec(select(ProviderRun).where(
        ProviderRun.task_id == task.id,
        ProviderRun.action == "seedance25_mock_poll",
    )).all()
    task.status = "processing" if not polls else "completed"
    provider_status = "mock_processing" if task.status == "processing" else "mock_completed"
    task.updated_at = utc_now()
    session.add(task)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=job.provider_profile_id,
        action="seedance25_mock_poll",
        response_snapshot_json=json.dumps({
            "provider_status": provider_status,
            "summary": "本地模拟状态推进；没有服务商百分比，也没有真实视频生成。",
            "outbound_request_sent": False,
            "mock_task": True,
        }, ensure_ascii=False),
    ))
    session.commit()
    return job.project_id


def seedance25_mock_download_task(
    session: Session,
    task_id: str,
    projects_root: Path,
) -> str:
    task = session.get(BatchVideoTask, task_id)
    job = session.get(BatchVideoJob, task.job_id) if task else None
    shot = session.get(Shot, task.shot_id) if task else None
    if not task or not job or not shot or task.status != "completed":
        raise HTTPException(409, "Seedance 2.5 Mock 任务尚未完成模拟查询。")
    _, episode, project = _scene_with_project(session, shot.scene_id)
    scene = session.get(Scene, shot.scene_id)
    relative = (
        f"07_results/generated_videos/{_scope_code(episode, scene)}/"
        f"{task.external_task_id}_{shot.shot_code}_mock.json"
    )
    target = _project_root(projects_root, project) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(json.dumps({
            "mock_task": True,
            "outbound_request_sent": False,
            "provider": "volcengine_seedance25",
            "provider_task_id": task.external_task_id,
            "shot_code": shot.shot_code,
            "canonical_request": _json(task.canonical_request_json, {}),
            "notice": "这是链路验收清单，不是视频文件，也未产生真实费用。",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    task.status = "mock_completed"
    task.result_video_path = relative
    task.updated_at = utc_now()
    session.add(task)
    session.add(ProviderRun(
        task_id=task.id,
        provider_profile_id=job.provider_profile_id,
        action="seedance25_mock_download",
        response_snapshot_json=json.dumps({
            "provider_status": "mock_artifact_saved",
            "summary": "Mock 链路验收清单已保存；没有真实视频文件。",
            "outbound_request_sent": False,
            "mock_task": True,
            "artifact_path": relative,
        }, ensure_ascii=False),
    ))
    session.commit()
    return job.project_id


def _task_monitor_fields(
    session: Session,
    task: BatchVideoTask,
    project: Project,
    projects_root: Path | None,
) -> dict[str, Any]:
    progress_by_status = {
        "draft": (0, "等待准备"),
        "blocked": (0, "等待补齐条件"),
        "awaiting_budget_confirm": (5, "等待费用确认"),
        "ready": (10, "可以提交"),
        "verifying": (0, "正在核验服务商任务"),
        "submitted": (25, "服务商已接收任务"),
        "processing": (60, "服务商生成中"),
        "completed": (85, "线上生成完成，等待保存"),
        "mock_completed": (0, "Mock 链路已验收（无真实视频）"),
        "imported": (100, "已保存到本地"),
        "failed": (100, "生成失败"),
    }
    progress_percent, progress_label = progress_by_status.get(
        task.status,
        (15, str(task.status or "等待状态")),
    )
    latest_run = session.exec(
        select(ProviderRun).where(ProviderRun.task_id == task.id).order_by(ProviderRun.created_at.desc())
    ).first()
    provider_status = ""
    provider_status_detail = ""
    provider_queue_status = ""
    provider_queue_position: int | None = None
    provider_queue_length: int | None = None
    if latest_run:
        snapshot = _json(latest_run.response_snapshot_json, {})
        provider_status = str(snapshot.get("provider_status") or "")
        provider_status_detail = str(
            snapshot.get("summary")
            or snapshot.get("monitor_error")
            or snapshot.get("error")
            or ""
        )
        summary_payload = _json(str(snapshot.get("summary") or ""), {})
        queue_info = snapshot.get("queue_info")
        if not isinstance(queue_info, dict):
            queue_info = extract_queue_info(summary_payload)
        if isinstance(queue_info, dict):
            provider_queue_status = str(queue_info.get("queue_status") or "")
            queue_position = queue_info.get("queue_idx")
            queue_length = queue_info.get("queue_length")
            provider_queue_position = int(queue_position) if isinstance(queue_position, (int, float, str)) and str(queue_position).isdigit() else None
            provider_queue_length = int(queue_length) if isinstance(queue_length, (int, float, str)) and str(queue_length).isdigit() else None
        if task.status == "submitted" and _task_external_provider(session, task.id) == "jimeng_cli":
            progress_percent = 0
            progress_label = "即梦云端排队中"
    remote_video_url = _latest_video_url(session, task.id) if task.external_task_id else ""
    local_file_path = ""
    if task.result_video_path and projects_root is not None:
        local_file_path = str((_project_root(projects_root, project) / task.result_video_path).resolve())
    if task.status == "mock_completed":
        storage_status = "mock"
    elif task.result_video_path:
        storage_status = "local"
    elif task.status == "failed":
        storage_status = "failed"
    elif task.status == "completed":
        storage_status = "online"
    else:
        storage_status = "pending"
    return {
        "local_file_path": local_file_path,
        "remote_video_url": remote_video_url,
        "storage_status": storage_status,
        "progress_percent": progress_percent,
        "progress_label": progress_label,
        "provider_status": provider_status,
        "provider_status_detail": provider_status_detail,
        "provider_queue_status": provider_queue_status,
        "provider_queue_position": provider_queue_position,
        "provider_queue_length": provider_queue_length,
    }


def batch_workspace(
    session: Session,
    project_id: str,
    settings: Settings | None = None,
) -> BatchWorkspaceView:
    project = get_project(session, project_id); providers = list_profiles(session, settings); scenes = []; jobs = []
    for episode in session.exec(select(Episode).where(Episode.project_id == project.id)).all():
        for scene in session.exec(select(Scene).where(Scene.episode_id == episode.id)).all():
            scene_shots = session.exec(
                select(Shot).where(Shot.scene_id == scene.id, Shot.is_archived == False)  # noqa
            ).all()
            confirmed_ids = set(
                session.exec(
                    select(VideoResultVersion.shot_id).where(
                        VideoResultVersion.shot_id.in_([shot.id for shot in scene_shots]),
                        VideoResultVersion.status == "confirmed",
                    )
                ).all()
            ) if scene_shots else set()
            scenes.append({
                "id": scene.id,
                "scope_code": _scope_code(episode, scene),
                "name": scene.name,
                "shot_count": len(scene_shots),
                "confirmed_video_count": len(confirmed_ids),
            })
    for job in session.exec(select(BatchVideoJob).where(BatchVideoJob.project_id == project.id).order_by(BatchVideoJob.created_at.desc())).all():
        scene, episode, _ = _scene_with_project(session, job.scene_id); profile = session.get(VideoProviderProfile, job.provider_profile_id); tasks = []
        for task in session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all():
            shot = session.get(Shot, task.shot_id); block = session.get(VpBlock, task.vp_block_id) if task.vp_block_id else None
            is_pending_reference_task = (
                not task.external_task_id
                and not task.result_video_path
                and task.status in {"blocked", "awaiting_budget_confirm", "ready"}
            )
            canonical = (
                _refresh_task_reference_manifest(session, task, shot, profile.id)
                if is_pending_reference_task and shot is not None and profile is not None
                else _json(task.canonical_request_json, {})
            )
            sb = _task_storyboard_reference(session, canonical)
            current_sb = _active(StoryboardShotVersion, session, StoryboardShotVersion.shot_id, shot.id)
            storyboard_reference_status = (
                "missing"
                if sb is None
                else "current"
                if current_sb is not None and sb.id == current_sb.id and sb.status in {"confirmed_current", "locked"}
                else "history"
            )
            storyboard_reference_note = (
                "当前任务引用的是正式确认版故事板。"
                if storyboard_reference_status == "current"
                else f"本次实际提交的是历史故事板 {Path(sb.image_path).name}；当前正式版为 {Path(current_sb.image_path).name if current_sb else '缺失'}。"
                if storyboard_reference_status == "history" and sb
                else "当前任务没有绑定正式故事板。"
            )
            task_reference_bindings = canonical.get("assets", {}).get("reference_bindings", [])
            if not isinstance(task_reference_bindings, list):
                task_reference_bindings = []
            task_reference_bindings = [
                {
                    **item,
                    "asset_url": _asset_url(project, str(item.get("asset_path") or "")),
                    "version_status": (
                        "current"
                        if _current_reference_asset_id(session, str(item.get("asset_id") or ""))
                        == str(item.get("asset_id") or "")
                        else "history"
                    ),
                }
                for item in task_reference_bindings
                if isinstance(item, dict)
            ]
            reference_candidates = _reference_candidates(session, shot, project)
            current_fingerprint = _reference_bindings_fingerprint(canonical) if canonical else ""
            bindings_confirmed = bool(
                task.reference_bindings_confirmed_at
                and task.reference_bindings_fingerprint == current_fingerprint
            )
            reference_binding_status = "current" if is_pending_reference_task else "historical_snapshot"
            reference_binding_note = (
                "已同步当前锁定资产版本；如锁定版、顺序、用途、模型或提示词变化，本镜头会自动撤销确认。"
                if reference_binding_status == "current"
                else "这是该镜头实际提交或生成时使用的历史快照，不会被当前资产换版改写；重做时会重新同步当前锁定版。"
            )
            results = session.exec(
                select(VideoResultVersion)
                .where(VideoResultVersion.task_id == task.id)
                .order_by(VideoResultVersion.created_at)
            ).all()
            monitor = _task_monitor_fields(session, task, project, settings.projects_root if settings else None)
            tasks.append(BatchTaskView(id=task.id, shot_id=shot.id, shot_code=shot.shot_code, status=task.status, external_task_id=task.external_task_id, external_provider=_task_external_provider(session, task.id), result_video_path=task.result_video_path, missing_items=_json(task.missing_items_json, []), canonical_request=canonical, retry_count=task.retry_count, error_message=task.error_message, updated_at=task.updated_at, storyboard_url=_asset_url(project, sb.image_path) if sb else None, current_storyboard_url=_asset_url(project, current_sb.image_path) if current_sb else None, storyboard_reference_status=storyboard_reference_status, storyboard_reference_note=storyboard_reference_note, provider_prompt_preview=str(canonical.get("prompt") or ""), reference_bindings=task_reference_bindings, reference_candidates=reference_candidates, reference_bindings_confirmed=bindings_confirmed, reference_bindings_confirmed_at=task.reference_bindings_confirmed_at, reference_binding_status=reference_binding_status, reference_binding_note=reference_binding_note, results=[VideoResultView(id=r.id, version_number=r.version_number, source=r.source, status=r.status, video_url=_asset_url(project, r.video_path)) for r in results], **monitor))
        cost_status, cost_note, cost_source_url = _cost_estimate_details(profile, job.estimated_cost)
        external_providers = {task.external_provider for task in tasks if task.external_provider}
        submission_channel = (
            "jimeng"
            if "jimeng_cli" in external_providers
            else "huimeng"
            if "huimeng_live" in external_providers
            else job.submission_channel
            if job.submission_channel in {"huimeng", "jimeng", "volcengine_seedance25"}
            else "jimeng"
        )
        task_counts = {
            "total": len(tasks),
            "confirmed_bindings": sum(1 for task in tasks if task.reference_bindings_confirmed),
            "blocked": sum(1 for task in tasks if task.status == "blocked"),
            "waiting": sum(1 for task in tasks if task.status in {"awaiting_budget_confirm", "ready"}),
            "running": sum(1 for task in tasks if task.status in {"verifying", "submitted", "processing", "completed"}),
            "failed": sum(1 for task in tasks if task.status == "failed"),
            "downloaded": sum(1 for task in tasks if task.status == "imported"),
            "approved": sum(1 for task in tasks if task.results and task.results[-1].status == "confirmed"),
        }
        jobs.append(BatchJobView(id=job.id, scene_id=scene.id, scope_code=_scope_code(episode, scene), provider_profile_id=profile.id, provider_name=profile.display_name, submission_channel=submission_channel, status=job.status, budget_confirmed=job.budget_confirmed, batch_authorized=job.batch_authorized, dispatch_enabled=job.dispatch_enabled, launched_at=job.launched_at, estimated_cost=job.estimated_cost, cost_estimate_status=cost_status, cost_estimate_note=cost_note, cost_source_url=cost_source_url, currency=job.currency, total_seconds=sum(t.canonical_request.get("duration_seconds", 0) for t in tasks), task_counts=task_counts, jimeng_zip_url=_asset_url(project, job.jimeng_export_path) if job.jimeng_export_path else None, tasks=tasks))
    session.commit()
    return BatchWorkspaceView(project_id=project.id, project_code=project.project_code, providers=providers, scenes=scenes, jobs=jobs)
