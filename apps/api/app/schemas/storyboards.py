from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StyleLockView(BaseModel):
    enabled: bool
    locked: bool
    style_name: str


class AxisPlanUpdate(BaseModel):
    axis_line_description: str
    camera_safe_side: str
    character_blocking: str
    eyeline_direction: str
    movement_direction: str
    allow_cross_axis: bool = False
    cross_axis_transition: str = ""


class AxisPlanView(AxisPlanUpdate):
    id: str
    axis_code: str


class StoryboardVersionCreate(BaseModel):
    shot_size: str = "中景"
    camera_angle: str = "平视"
    camera_movement: str = "固定机位"
    action_start: str = "人物保持动作连续"
    emotion_state: str = "克制"
    sound_light: str = "环境底噪，白底/浅灰故事板说明板中的黑白灰铅笔明暗关系"
    camera_point: str = "CAM01"
    screen_position: str = "左侧"
    eyeline_direction: str = "向右"
    movement_direction: str = "从左向右"
    camera_side: str = "A侧"


class StoryboardImageGateItem(BaseModel):
    label: str
    passed: bool
    detail: str


class StoryboardImageReadinessView(BaseModel):
    ready: bool
    provider_name: str
    model_id: str
    gate_items: list[StoryboardImageGateItem]
    risk_notice: str
    requires_user_confirmation: bool = True


class StoryboardImageActionCreate(BaseModel):
    confirm_live_request: bool = False
    correction_note: str = Field(default="", max_length=1200)
    prompt_override: str = Field(default="", max_length=20000)


class StoryboardImageReuseCreate(BaseModel):
    source_version_id: str
    confirm_reuse: bool = False
    force_reuse: bool = False


class StoryboardImagePromptView(BaseModel):
    prompt: str


class StoryboardImageJobView(BaseModel):
    id: str
    project_id: str
    target_type: str
    target_id: str
    provider: str
    model_name: str
    external_task_id: str
    status: str
    remote_result_url: str
    image_url: str | None
    prompt: str
    error_message: str
    created_at: datetime


class StoryboardVersionView(StoryboardVersionCreate):
    id: str
    version_number: int
    image_url: str
    schema_version: str
    vp_basis_block_id: str | None
    storyboard_mode: str
    density_level: str
    storyboard_grid: int
    grid_reason: str
    annotation_layer: dict[str, Any]
    prompt_match: list[dict[str, Any]]
    timeline_nodes: list[dict[str, Any]]
    storyboard_cells: list[dict[str, Any]]
    unified_sb_meta: dict[str, Any]
    style_validation_status: str
    axis_validation_status: str
    axis_validation_notes: str
    status: str
    created_at: datetime
    latest_image_job: StoryboardImageJobView | None = None


class StoryboardReuseAssessmentView(BaseModel):
    source_version_id: str
    source_version_number: int
    source_image_url: str
    recommendation: str
    can_reuse: bool
    reasons: list[str]
    old_grid: int
    new_grid: int
    old_time_ranges: list[str]
    new_time_ranges: list[str]


class StoryboardShotView(BaseModel):
    id: str
    shot_code: str
    name: str
    latest_vp_draft_id: str | None = None
    versions: list[StoryboardVersionView]
    reuse_assessment: StoryboardReuseAssessmentView | None = None


class StoryboardExecutionPageView(BaseModel):
    id: str
    version_number: int
    html_url: str
    png_url: str
    status: str
    created_at: datetime


class StoryboardSceneView(BaseModel):
    id: str
    scope_code: str
    name: str
    axis_plan: AxisPlanView
    shots: list[StoryboardShotView]
    execution_pages: list[StoryboardExecutionPageView]


class StoryboardWorkspaceView(BaseModel):
    project_id: str
    project_code: str
    style_lock: StyleLockView
    scenes: list[StoryboardSceneView]


class PromptStoryboardExportView(BaseModel):
    scene_id: str
    scope_code: str
    zip_url: str
    relative_path: str
    shot_count: int
    files: list[str]
