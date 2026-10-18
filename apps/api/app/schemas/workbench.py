from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class NamedUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectUpdate(ProjectCreate):
    pass


class ProjectReveal(BaseModel):
    relative_path: str = Field(default="", max_length=500)


class ProjectRevealResult(BaseModel):
    opened: bool
    path: str


class ProjectCreativeGoalUpdate(BaseModel):
    creative_goal: str = Field(pattern="^(full_pipeline|prompt_storyboard|asset_only|analysis_plan)$")


class ProjectSummary(BaseModel):
    id: str
    project_code: str
    name: str
    description: str
    creative_goal: str = "full_pipeline"
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class ProjectOverview(ProjectSummary):
    episode_count: int = 0
    scene_count: int = 0
    shot_count: int = 0
    source_file_count: int = 0
    current_stage: str = "等待开始"
    short_status: str = "等待资料"
    primary_action_label: str = "继续工作"
    primary_action_href: str = "/start-plan#source-intake"


class ProjectHardDelete(BaseModel):
    confirm_delete: bool = False
    confirm_project_name: str = Field(default="", max_length=120)


class ShotView(BaseModel):
    id: str
    shot_code: str
    name: str
    is_archived: bool


class SceneView(BaseModel):
    id: str
    scene_code: str
    name: str
    is_archived: bool
    shots: list[ShotView]


class EpisodeView(BaseModel):
    id: str
    episode_code: str
    name: str
    is_archived: bool
    scenes: list[SceneView]


class ProjectDetail(ProjectSummary):
    episodes: list[EpisodeView]


class SourceFileView(BaseModel):
    id: str
    project_id: str
    category: str
    original_filename: str
    stored_filename: str
    relative_path: str
    content_type: str | None
    size_bytes: int
    created_at: datetime


class SourceTextCreate(BaseModel):
    category: str = Field(default="script_text", max_length=80)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=200000)


class RealAcceptanceProjectCreate(BaseModel):
    name: str = Field(default="真实验收短片", min_length=1, max_length=120)
    description: str = Field(default="用于验证真实文本、真实生图和真实单镜视频链路。", max_length=1000)
    script_text: str = Field(
        default=(
            "第一场：夜，旧楼走廊。\n"
            "镜头一：女孩抱着一封旧信站在昏暗灯下，远处传来脚步声。\n"
            "镜头二：她抬头看向走廊尽头，神情紧张，手指攥紧信封。\n"
            "镜头三：门外影子停住，她把信藏进抽屉，空气突然安静。"
        ),
        min_length=20,
        max_length=200000,
    )


class UcodeRunCreate(BaseModel):
    ucode_action: str
    scope_code: str = Field(min_length=1, max_length=120)
    additional_request: str = Field(default="", max_length=4000)


class CheckpointView(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime


class UcodeRunView(BaseModel):
    id: str
    project_id: str
    ucode_action: str
    scope_code: str
    additional_request: str
    command_text: str
    status: str
    result_summary: str
    checkpoint_required: bool
    created_at: datetime
    checkpoints: list[CheckpointView] = []
