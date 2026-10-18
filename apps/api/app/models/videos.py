from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.workbench import new_id, utc_now


class VpBlock(SQLModel, table=True):
    __tablename__ = "vp_blocks"

    id: str = Field(default_factory=new_id, primary_key=True)
    shot_id: str = Field(foreign_key="shots.id", index=True)
    version_number: int
    has_character: bool = True
    character_master_version_id: str | None = Field(default=None, foreign_key="character_master_versions.id")
    costume_version_id: str | None = Field(default=None, foreign_key="costume_versions.id")
    scene_asset_version_id: str | None = Field(default=None, foreign_key="scene_asset_versions.id")
    storyboard_version_id: str | None = Field(default=None, foreign_key="storyboard_shot_versions.id")
    schema_version: str = "vp_precision_18_v1"
    package_stage: str = "director_draft"
    precision_json: str = "{}"
    video_unit_id: str | None = Field(default=None, foreign_key="video_units.id", index=True)
    vp_prompt_full: str = ""
    prompt_copy: str = ""
    reference_tag_map_json: str = "{}"
    preserved_constraints_json: str = "[]"
    removed_redundancy_json: str = "[]"
    prompt_budget_report_json: str = "{}"
    compile_warnings_json: str = "[]"
    basis_vp_block_id: str | None = Field(default=None, foreign_key="vp_blocks.id")
    prompt: str
    negative_prompt: str
    duration_seconds: int = 5
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    generation_mode: str = "multimodal_reference"
    provider_profile_id: str = Field(foreign_key="video_provider_profiles.id")
    director_technique: str = ""
    close_in_start_time: str = ""
    close_in_from_shot_size: str = ""
    close_in_to_shot_size: str = ""
    close_in_target_detail: str = ""
    close_in_emotional_meaning: str = ""
    close_in_return_to_character: bool = False
    close_in_tail_frame: str = ""
    detail_shot_candidates_json: str = "[]"
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
    meaning_chain_json: str = "{}"
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class VpGenerationJob(SQLModel, table=True):
    __tablename__ = "vp_generation_jobs"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    operation: str = "duration_rebuild"
    shot_plan_json: str = "[]"
    status: str = "queued"
    current_index: int = 0
    completed_count: int = 0
    failed_count: int = 0
    current_shot_code: str = ""
    retry_count: int = 0
    max_retries: int = 3
    message: str = "等待后台开始"
    error_message: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class VideoProviderProfile(SQLModel, table=True):
    __tablename__ = "video_provider_profiles"

    id: str = Field(default_factory=new_id, primary_key=True)
    display_name: str
    provider_type: str
    is_enabled: bool = True
    is_default: bool = False
    base_url: str = ""
    create_task_path: str = ""
    get_task_path_template: str = ""
    cancel_task_path_template: str = ""
    auth_type: str = "bearer"
    auth_header_name: str = "Authorization"
    auth_prefix: str = "Bearer "
    auth_env_key_name: str = ""
    config_json: str = "{}"
    capabilities_json: str = "{}"
    price_configs_json: str = "[]"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BatchVideoJob(SQLModel, table=True):
    __tablename__ = "batch_video_jobs"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    provider_profile_id: str = Field(foreign_key="video_provider_profiles.id")
    submission_channel: str = "jimeng"
    status: str = "draft"
    budget_confirmed: bool = False
    batch_authorized: bool = False
    dispatch_enabled: bool = False
    launched_at: datetime | None = None
    estimated_cost: float | None = None
    currency: str = "CNY"
    jimeng_export_path: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BatchVideoTask(SQLModel, table=True):
    __tablename__ = "batch_video_tasks"

    id: str = Field(default_factory=new_id, primary_key=True)
    job_id: str = Field(foreign_key="batch_video_jobs.id", index=True)
    shot_id: str = Field(foreign_key="shots.id", index=True)
    vp_block_id: str | None = Field(default=None, foreign_key="vp_blocks.id")
    video_unit_id: str | None = Field(default=None, foreign_key="video_units.id", index=True)
    canonical_request_json: str = "{}"
    missing_items_json: str = "[]"
    status: str = "draft"
    external_task_id: str | None = None
    result_video_path: str | None = None
    retry_count: int = 0
    error_message: str = ""
    reference_bindings_fingerprint: str = ""
    reference_bindings_confirmed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class VideoResultVersion(SQLModel, table=True):
    __tablename__ = "video_result_versions"

    id: str = Field(default_factory=new_id, primary_key=True)
    task_id: str = Field(foreign_key="batch_video_tasks.id", index=True)
    shot_id: str = Field(foreign_key="shots.id", index=True)
    version_number: int
    video_path: str
    source: str
    status: str = "imported"
    created_at: datetime = Field(default_factory=utc_now)


class ProviderRun(SQLModel, table=True):
    __tablename__ = "provider_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    task_id: str = Field(foreign_key="batch_video_tasks.id", index=True)
    provider_profile_id: str = Field(foreign_key="video_provider_profiles.id")
    action: str
    response_snapshot_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)


class CostUsageLog(SQLModel, table=True):
    __tablename__ = "cost_usage_logs"

    id: str = Field(default_factory=new_id, primary_key=True)
    provider: str
    model_name: str = ""
    module_type: str
    estimated_cost: float | None = None
    task_id: str | None = Field(default=None, index=True)
    text_run_id: str | None = Field(default=None, index=True)
    cache_key: str = ""
    cache_hit: bool = False
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class RequestCacheRecord(SQLModel, table=True):
    __tablename__ = "request_cache_records"

    id: str = Field(default_factory=new_id, primary_key=True)
    cache_key: str = Field(index=True, unique=True)
    module_type: str
    result_reference_id: str
    created_at: datetime = Field(default_factory=utc_now)


class ShotDirectorTechnique(SQLModel, table=True):
    __tablename__ = "shot_director_techniques"

    id: str = Field(default_factory=new_id, primary_key=True)
    shot_id: str = Field(foreign_key="shots.id", index=True)
    technique_type: str = ""
    montage_type: str = ""
    symbolic_object: str = ""
    symbolic_meaning: str = ""
    detail_shot_candidates_json: str = "[]"
    selected_detail_shot: str = ""
    detail_shot_time_range: str = ""
    detail_shot_meaning: str = ""
    detail_shot_relation_to_character: str = ""
    close_in_start_time: str = ""
    close_in_from_shot_size: str = ""
    close_in_to_shot_size: str = ""
    close_in_target_detail: str = ""
    close_in_emotional_meaning: str = ""
    close_in_return_to_character: bool = False
    close_in_tail_frame: str = ""
    montage_goal: str = ""
    montage_shot_count: int = 0
    montage_entry_point: str = ""
    montage_exit_point: str = ""
    montage_rhythm: str = ""
    montage_return_to_main_story: str = ""
    object_state_change: str = ""
    object_state_time_range: str = ""
    relation_to_character_emotion: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ShotMeaningChain(SQLModel, table=True):
    __tablename__ = "shot_meaning_chains"

    id: str = Field(default_factory=new_id, primary_key=True)
    shot_id: str = Field(foreign_key="shots.id", index=True)
    reason: str = ""
    relation_to_previous: str = ""
    audience_association: str = ""
    emotional_function: str = ""
    transition_to_next: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RealProviderRun(SQLModel, table=True):
    __tablename__ = "real_provider_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    provider_name: str
    provider_type: str
    task_id: str = Field(index=True)
    request_payload_snapshot: str = "{}"
    response_snapshot: str = "{}"
    status: str = "created"
    cost_estimate: float | None = None
    actual_cost: float | None = None
    created_at: datetime = Field(default_factory=utc_now)
