from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.video_constraints import MAX_SUPPORTED_VIDEO_CLIP_SECONDS
from app.schemas.workflows import AiTextRunCreate


class VpBlockCreate(BaseModel):
    has_character: bool = True
    package_stage: str = Field(default="director_draft", pattern="^(director_draft|final_execution)$")
    prompt: str = Field(default="", max_length=3000)
    negative_prompt: str = Field(default="禁止跳轴、身份漂移、服装漂移、画面彩色化", max_length=1000)
    duration_seconds: int | None = Field(default=None, ge=1, le=MAX_SUPPORTED_VIDEO_CLIP_SECONDS)
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    generation_mode: str = "multimodal_reference"
    provider_profile_id: str = "huimeng_live"


class AiVpBlockCreate(BaseModel):
    vp_block: VpBlockCreate = Field(default_factory=VpBlockCreate)
    ai_text: AiTextRunCreate = Field(default_factory=lambda: AiTextRunCreate(module_type="vp_precision_18"))


class VpBlockView(VpBlockCreate):
    duration_seconds: int
    id: str
    version_number: int
    shot_id: str
    status: str
    schema_version: str
    prompt_copy: str
    basis_vp_block_id: str | None
    character_master_version_id: str | None
    costume_version_id: str | None
    scene_asset_version_id: str | None
    storyboard_version_id: str | None
    precision_items: list[dict[str, Any]]
    director_technique: str = ""
    close_in_start_time: str = ""
    close_in_from_shot_size: str = ""
    close_in_to_shot_size: str = ""
    close_in_target_detail: str = ""
    close_in_emotional_meaning: str = ""
    close_in_return_to_character: bool = False
    close_in_tail_frame: str = ""
    detail_shot_candidates: list[str] = Field(default_factory=list)
    selected_detail_shot: str = ""
    detail_shot_time_range: str = ""
    detail_shot_meaning: str = ""
    detail_shot_relation_to_character: str = ""
    montage_type: str = ""
    montage_goal: str = ""
    montage_shot_count: int = 0
    montage_entry_point: str = ""
    montage_exit_point: str = ""
    montage_rhythm: str = ""
    montage_return_to_main_story: str = ""
    symbolic_object: str = ""
    object_state_change: str = ""
    symbolic_meaning: str = ""
    object_state_time_range: str = ""
    relation_to_character_emotion: str = ""
    meaning_chain: dict[str, Any] = Field(default_factory=dict)
    asset_summary: list[str]
    validation_items: list[str]
    provider_prompt_preview: str = ""
    reference_bindings: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class VideoPackageShotView(BaseModel):
    id: str
    shot_code: str
    name: str
    recommended_duration_seconds: int = 8
    duration_reason: str = ""
    confirmed_storyboard_vp_basis_block_id: str | None = None
    versions: list[VpBlockView]


class VideoPackageSceneView(BaseModel):
    id: str
    scope_code: str
    name: str
    shots: list[VideoPackageShotView]


class VideoPackageWorkspaceView(BaseModel):
    project_id: str
    project_code: str
    scenes: list[VideoPackageSceneView]


class VpGenerationJobCreate(BaseModel):
    operation: Literal["duration_rebuild"] = "duration_rebuild"
    confirm_live_request: bool = False


class VpGenerationJobView(BaseModel):
    id: str
    project_id: str
    scene_id: str
    operation: str
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    current_shot_code: str
    message: str
    error_message: str
    created_at: datetime
    updated_at: datetime


class ProviderProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    provider_type: str = "seedance_aggregator_generic"
    is_enabled: bool = True
    base_url: str = ""
    create_task_path: str = ""
    get_task_path_template: str = ""
    cancel_task_path_template: str = ""
    auth_type: str = "bearer"
    auth_header_name: str = "Authorization"
    auth_prefix: str = "Bearer "
    auth_env_key_name: str = "SEEDANCE_AGGREGATOR_API_KEY"
    config: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    price_configs: list[dict[str, Any]] = Field(default_factory=list)


class ProviderProfileView(ProviderProfileCreate):
    id: str
    is_default: bool
    validation_message: str = ""


class ProviderTemplateView(BaseModel):
    template_id: str
    title: str
    description: str
    outbound_requests_enabled: bool = False
    profile: ProviderProfileCreate


class LiveProviderStatusView(BaseModel):
    provider_mode: str
    real_seedance_enabled: bool
    huimengi_api_key_configured: bool
    huimengi_video_base_url: str
    huimengi_video_model: str
    huimengi_base_url: str
    huimengi_model_id: str
    live_video_task: str
    single_task_limit: str
    network_policy: str


class LiveReadinessGateView(BaseModel):
    label: str
    passed: bool
    detail: str


class LiveReadinessView(BaseModel):
    ready: bool
    provider_name: str
    model_id: str
    gate_items: list[LiveReadinessGateView]
    risk_notice: str
    requires_user_confirmation: bool = True


class JimengCliStatusView(BaseModel):
    installed: bool
    logged_in: bool
    ready: bool
    command: str = "dreamina"
    account_summary: str = ""
    credit_summary: str = ""
    output_dir: str = ""
    blocking_reason: str = ""
    cli_version: str = ""
    install_hint: str = "请按即梦官方 CLI 文档安装 dreamina；安装后在终端执行 dreamina login。"


class JimengVideoModelView(BaseModel):
    id: str
    label: str
    speed_label: str
    cost_label: str
    description: str
    supported_resolutions: list[str]
    min_duration: int = 4
    max_duration: int = 15
    capability_source: str = "configured_catalog"
    cli_version: str = ""
    available: bool = True
    unavailable_reason: str = ""
    duration_range: list[int] = Field(default_factory=lambda: [4, 15])
    reference_limits: dict[str, int] = Field(default_factory=dict)
    mock_only: bool = False


class VideoProviderModelView(JimengVideoModelView):
    provider_type: str
    provider_model_id: str
    supports_smart_duration: bool = False
    is_mock_only: bool = False


class VideoGenerationSettingsUpdate(BaseModel):
    provider_model_id: str | None = None
    generation_mode: str | None = None
    duration_mode: Literal["smart", "specified"] | None = None
    duration_seconds: int | None = Field(default=None, ge=1, le=30)
    resolution: Literal["480p", "720p", "1080p", "4k"] | None = None
    prompt_optimization_enabled: bool | None = None


class VideoReferenceItemUpdate(BaseModel):
    asset_id: str = Field(min_length=1)
    media_type: Literal["image", "video", "audio"] = "image"
    purpose: Literal["subject", "product", "environment", "action", "camera", "rhythm", "style", "sound"]
    must_preserve: str = ""
    must_not_transfer: str = ""


class JimengVideoModelUpdate(BaseModel):
    model_id: str


class VideoReferenceBindingsUpdate(BaseModel):
    asset_ids: list[str] | None = Field(default=None, min_length=1, max_length=30)
    reference_items: list[VideoReferenceItemUpdate] | None = Field(default=None, min_length=1, max_length=50)


class BatchLaunch(BaseModel):
    confirm_live_request: bool = False


class JimengCliReadinessView(BaseModel):
    ready: bool
    provider_name: str = "即梦 CLI"
    model_id: str
    gate_items: list[LiveReadinessGateView]
    risk_notice: str
    requires_user_confirmation: bool = True
    prompt_preview: str = ""
    asset_count: int = 0
    reference_bindings: list[dict[str, Any]] = Field(default_factory=list)
    reference_candidates: list[dict[str, Any]] = Field(default_factory=list)


class VideoTaskSupervisorStatusView(BaseModel):
    enabled: bool
    running: bool
    poll_interval_seconds: int
    active_task_count: int = 0
    last_cycle_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str = ""


class ProviderPreflightView(BaseModel):
    profile_id: str
    provider_type: str
    config_valid: bool
    secret_configured: bool
    documentation_url: str
    price_source_url: str
    price_configured: bool
    request_mapping_complete: bool
    response_mapping_complete: bool
    outbound_requests_enabled: bool = False
    ready_for_live_test: bool = False
    checklist: list[str]


class ProviderRequestPreviewView(BaseModel):
    task_id: str
    provider_profile_id: str
    canonical_request: dict[str, Any]
    mapped_request_preview: dict[str, Any]
    missing_items: list[str]
    outbound_request_sent: bool = False


class ProviderResponsePreviewCreate(BaseModel):
    sample_response: dict[str, Any]


class ProviderResponsePreviewView(BaseModel):
    profile_id: str
    normalized_response: dict[str, Any]
    missing_items: list[str]
    sample_saved: bool = False
    outbound_requests_sent: bool = False
    result_downloaded: bool = False


class BatchCreate(BaseModel):
    provider_profile_id: str = "huimeng_live"
    submission_channel: Literal["huimeng", "jimeng", "volcengine_seedance25"] | None = None


class BatchSubmissionChannelUpdate(BaseModel):
    submission_channel: Literal["huimeng", "jimeng", "volcengine_seedance25"]
    huimeng_provider_profile_id: str = ""


class LiveVideoAction(BaseModel):
    confirm_live_request: bool = False


class VideoResultReview(BaseModel):
    decision: Literal["confirm", "redo"]


class VideoResultView(BaseModel):
    id: str
    version_number: int
    source: str
    status: str
    video_url: str


class BatchTaskView(BaseModel):
    id: str
    shot_id: str
    shot_code: str
    status: str
    external_task_id: str | None = None
    external_provider: str = ""
    result_video_path: str | None = None
    local_file_path: str = ""
    remote_video_url: str = ""
    storage_status: Literal["pending", "online", "local", "failed", "mock"] = "pending"
    progress_percent: int = Field(default=0, ge=0, le=100)
    progress_label: str = ""
    provider_status: str = ""
    provider_status_detail: str = ""
    provider_queue_status: str = ""
    provider_queue_position: int | None = None
    provider_queue_length: int | None = None
    missing_items: list[str]
    canonical_request: dict[str, Any]
    retry_count: int
    error_message: str
    updated_at: datetime
    storyboard_url: str | None
    current_storyboard_url: str | None = None
    storyboard_reference_status: Literal["current", "history", "missing"] = "missing"
    storyboard_reference_note: str = ""
    provider_prompt_preview: str = ""
    reference_bindings: list[dict[str, Any]] = Field(default_factory=list)
    reference_candidates: list[dict[str, Any]] = Field(default_factory=list)
    reference_bindings_confirmed: bool = False
    reference_bindings_confirmed_at: datetime | None = None
    reference_binding_status: Literal["current", "historical_snapshot"] = "current"
    reference_binding_note: str = ""
    results: list[VideoResultView]


class BatchJobView(BaseModel):
    id: str
    scene_id: str
    scope_code: str
    provider_profile_id: str
    provider_name: str
    submission_channel: Literal["huimeng", "jimeng", "volcengine_seedance25"]
    status: str
    budget_confirmed: bool
    batch_authorized: bool = False
    dispatch_enabled: bool = False
    launched_at: datetime | None = None
    estimated_cost: float | None
    cost_estimate_status: Literal["estimated", "unknown"]
    cost_estimate_note: str
    cost_source_url: str
    currency: str
    total_seconds: int
    task_counts: dict[str, int] = Field(default_factory=dict)
    jimeng_zip_url: str | None
    tasks: list[BatchTaskView]


class BatchWorkspaceView(BaseModel):
    project_id: str
    project_code: str
    providers: list[ProviderProfileView]
    scenes: list[dict[str, Any]]
    jobs: list[BatchJobView]
