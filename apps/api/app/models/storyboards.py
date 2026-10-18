from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.workbench import new_id, utc_now


class StoryboardStyleLock(SQLModel, table=True):
    __tablename__ = "storyboard_style_locks"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True, unique=True)
    enabled: bool = True
    locked: bool = True
    style_name: str = "统一白底高信息密度导演故事板说明板风格"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AxisPlan(SQLModel, table=True):
    __tablename__ = "axis_plans"

    id: str = Field(default_factory=new_id, primary_key=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True, unique=True)
    axis_code: str = "AXIS-01"
    axis_line_description: str = "人物连线作为主轴线"
    camera_safe_side: str = "A侧"
    character_blocking: str = "主角位于画面左侧，对手位于画面右侧"
    eyeline_direction: str = "主角向右，对手向左"
    movement_direction: str = "从左向右"
    allow_cross_axis: bool = False
    cross_axis_transition: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StoryboardShotVersion(SQLModel, table=True):
    __tablename__ = "storyboard_shot_versions"

    id: str = Field(default_factory=new_id, primary_key=True)
    shot_id: str = Field(foreign_key="shots.id", index=True)
    version_number: int
    image_path: str
    schema_version: str = "unified_sb_v1"
    vp_basis_block_id: str | None = Field(default=None, foreign_key="vp_blocks.id")
    storyboard_mode: str = "unified_sb"
    density_level: str = "medium"
    storyboard_grid: int = 6
    grid_reason: str = ""
    annotation_layer: str = "{}"
    prompt_match: str = "[]"
    prompt_match_json: str = "[]"
    timeline_nodes_json: str = "[]"
    storyboard_cells_json: str = "[]"
    unified_sb_meta_json: str = "{}"
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
    style_validation_status: str = "passed"
    axis_validation_status: str = "passed"
    axis_validation_notes: str = ""
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StoryboardExecutionPage(SQLModel, table=True):
    __tablename__ = "storyboard_execution_pages"

    id: str = Field(default_factory=new_id, primary_key=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    version_number: int
    html_path: str
    png_path: str
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StoryboardGridCell(SQLModel, table=True):
    __tablename__ = "storyboard_grid_cells"

    id: str = Field(default_factory=new_id, primary_key=True)
    storyboard_page_id: str = Field(foreign_key="storyboard_execution_pages.id", index=True)
    shot_id: str = Field(foreign_key="shots.id", index=True)
    cell_index: int
    time_range: str = ""
    action_note: str = ""
    camera_note: str = ""
    composition_note: str = ""
    meaning_note: str = ""
    vfx_note: str = ""
    tail_frame_note: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class ImageGenerationJob(SQLModel, table=True):
    __tablename__ = "image_generation_jobs"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    target_type: str = Field(index=True)
    target_id: str = Field(index=True)
    provider: str = "huimeng_image"
    model_name: str = ""
    prompt: str
    request_json: str = "{}"
    response_snapshot_json: str = "{}"
    external_task_id: str = Field(default="", index=True)
    remote_result_url: str = ""
    result_image_path: str = ""
    status: str = Field(default="submitted", index=True)
    error_message: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
