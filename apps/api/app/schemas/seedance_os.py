from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class SceneDirectingStateUpsert(BaseModel):
    scene_function: str = ""
    scene_turn: str = ""
    pov_character: str = ""
    audience_position: str = ""
    power_map: dict[str, Any] = Field(default_factory=dict)
    power_shift: str = ""
    subtext: str = ""
    felt_intent: str = ""
    directorial_voice: str = ""
    arc_position: str = ""
    is_pattern_break: bool = False


class SurfaceProfileCreate(BaseModel):
    name: str
    provider_name: str
    model_id: str
    prompt_strategy: str = "balanced"
    supported_inputs: list[str] = Field(default_factory=lambda: ["text"])
    max_duration_seconds: int = Field(default=15, ge=1, le=15)
    verification_date: datetime | None = None
    duration_range: dict[str, float] = Field(default_factory=lambda: {"min": 1, "max": 15})
    prompt_budget: int = Field(default=6000, ge=1)
    reference_tag_convention: str = "@参考N"
    supported_modes: list[str] = Field(default_factory=lambda: ["text_to_video"])
    reference_limits: dict[str, Any] = Field(default_factory=dict)
    first_last_frame_support: bool = False
    edit_support: bool = False
    extend_support: bool = False
    audio_behavior: str = "provider_defined"
    resolutions: list[str] = Field(default_factory=list)
    aspect_ratios: list[str] = Field(default_factory=list)
    region: str = ""
    pricing: dict[str, Any] = Field(default_factory=dict)
    authorization_requirements: dict[str, Any] = Field(default_factory=dict)
    known_constraints: list[str] = Field(default_factory=list)
    capability_overrides: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ReferenceRoleInput(BaseModel):
    reference_type: str
    reference_id: str = ""
    local_path: str = ""
    role: Literal[
        "identity",
        "appearance",
        "costume",
        "environment",
        "composition",
        "motion",
        "start_frame",
        "end_frame",
        "style",
    ]
    influence: float = Field(default=1.0, ge=0, le=1)
    protected_elements: list[str] = Field(default_factory=list)
    forbidden_transfer: list[str] = Field(default_factory=list)


class VideoUnitCreate(BaseModel):
    scene_id: str
    shot_id: str
    storyboard_version_id: str | None = None
    prompt_time_ranges: list[str] = Field(default_factory=list)
    unit_index: int = Field(default=1, ge=1)
    unit_type: Literal["standalone", "continuation", "transition", "retake"] = "standalone"
    duration_seconds: float = Field(default=5, gt=0, le=15)
    source_video_unit_id: str | None = None
    source_take_review_id: str | None = None
    extension_depth: int = Field(default=0, ge=0)
    intended_start_state: dict[str, Any] = Field(default_factory=dict)
    intended_end_state: dict[str, Any] = Field(default_factory=dict)
    continuity_handoff: dict[str, Any] = Field(default_factory=dict)
    references: list[ReferenceRoleInput] = Field(default_factory=list)
    surface_profile_id: str | None = None

    @model_validator(mode="after")
    def validate_continuation_source(self):
        if self.unit_type == "continuation" and not self.source_video_unit_id:
            raise ValueError("续作单元必须指定上一 Video Unit。")
        return self


class TakeReviewCreate(BaseModel):
    provider_run_id: str | None = None
    source_video_path: str = ""
    observed_start_state: dict[str, Any] = Field(default_factory=dict)
    observed_end_state: dict[str, Any] = Field(default_factory=dict)
    status: Literal["accepted", "rejected"]
    rejection_reasons: list[str] = Field(default_factory=list)
    review_notes: str = ""

    @model_validator(mode="after")
    def accepted_requires_end_state(self):
        if self.status == "accepted" and not self.observed_end_state:
            raise ValueError("通过的成片必须记录真实尾帧状态。")
        return self


class BoundaryFrameExtractRequest(BaseModel):
    source_video_path: str


class BoundaryFrameExtractResponse(BaseModel):
    video_unit_id: str
    take_review_id: str
    source_video_path: str
    first_frame_path: str
    last_frame_path: str
    status: Literal["pending"] = "pending"


class PromptCompileRequest(BaseModel):
    vp_precision_18: list[dict[str, Any]]
    surface_profile_id: str | None = None
    references: list[ReferenceRoleInput] = Field(default_factory=list)
    additional_constraints: list[str] = Field(default_factory=list)


class PromptCompileResponse(BaseModel):
    vp_prompt_full: str
    vp_prompt_copy: str
    reference_tag_map: list[dict[str, Any]]
    preserved_constraints: list[str]
    removed_redundancy: list[str]
    prompt_budget_report: dict[str, Any]
    compile_warnings: list[str]
    skill_modules: list[str]


class SkillStatusResponse(BaseModel):
    installed: bool
    pinned_commit: str
    vendor_path: str
    module_count: int
    license_present: bool
