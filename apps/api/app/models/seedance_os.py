from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.workbench import new_id, utc_now


class DirectorProjectState(SQLModel, table=True):
    __tablename__ = "director_project_states"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True, unique=True)
    current_scene_id: str | None = Field(default=None, foreign_key="scenes.id")
    current_video_unit_id: str | None = Field(default=None, index=True)
    canon_json: str = Field(default="{}", sa_column=Column(Text))
    character_state_json: str = Field(default="{}", sa_column=Column(Text))
    environment_state_json: str = Field(default="{}", sa_column=Column(Text))
    object_state_json: str = Field(default="{}", sa_column=Column(Text))
    continuity_state_json: str = Field(default="{}", sa_column=Column(Text))
    accepted_take_ids_json: str = Field(default="[]", sa_column=Column(Text))
    completed_video_unit_ids_json: str = Field(default="[]", sa_column=Column(Text))
    reserved_video_unit_ids_json: str = Field(default="[]", sa_column=Column(Text))
    updated_at: datetime = Field(default_factory=utc_now)


class SceneDirectingState(SQLModel, table=True):
    __tablename__ = "scene_directing_states"

    id: str = Field(default_factory=new_id, primary_key=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True, unique=True)
    scene_function: str = ""
    scene_turn: str = ""
    pov_character: str = ""
    audience_position: str = ""
    power_map_json: str = Field(default="{}", sa_column=Column(Text))
    power_shift: str = ""
    subtext: str = ""
    felt_intent: str = ""
    directorial_voice: str = ""
    arc_position: str = ""
    is_pattern_break: bool = False
    updated_at: datetime = Field(default_factory=utc_now)


class SurfaceProfile(SQLModel, table=True):
    __tablename__ = "surface_profiles"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str | None = Field(default=None, foreign_key="projects.id", index=True)
    name: str
    provider_type: str
    model_id: str = ""
    prompt_strategy: str = "natural_language"
    supported_input_types_json: str = Field(default="[]", sa_column=Column(Text))
    max_duration_seconds: int = 15
    verification_date: datetime | None = None
    duration_range_json: str = Field(default="{}", sa_column=Column(Text))
    prompt_budget: int = 6000
    reference_tag_convention: str = "@参考N"
    supported_modes_json: str = Field(default="[]", sa_column=Column(Text))
    reference_limits_json: str = Field(default="{}", sa_column=Column(Text))
    first_last_frame_support: bool = False
    edit_support: bool = False
    extend_support: bool = False
    audio_behavior: str = "provider_defined"
    resolutions_json: str = Field(default="[]", sa_column=Column(Text))
    aspect_ratios_json: str = Field(default="[]", sa_column=Column(Text))
    region: str = ""
    pricing_json: str = Field(default="{}", sa_column=Column(Text))
    authorization_requirements_json: str = Field(default="{}", sa_column=Column(Text))
    known_constraints_json: str = Field(default="[]", sa_column=Column(Text))
    capability_overrides_json: str = Field(default="{}", sa_column=Column(Text))
    is_default: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class VideoUnit(SQLModel, table=True):
    __tablename__ = "video_units"
    __table_args__ = (UniqueConstraint("shot_id", "unit_index", name="uq_video_unit_shot_index"),)

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    shot_id: str = Field(foreign_key="shots.id", index=True)
    storyboard_version_id: str | None = Field(
        default=None,
        foreign_key="storyboard_shot_versions.id",
        index=True,
    )
    prompt_time_ranges_json: str = Field(default="[]", sa_column=Column(Text))
    unit_index: int = 1
    unit_type: str = "standalone"
    duration_seconds: float = 5.0
    source_video_unit_id: str | None = Field(default=None, foreign_key="video_units.id", index=True)
    source_take_review_id: str | None = Field(default=None, index=True)
    extension_depth: int = 0
    reanchor_required: bool = False
    event_density_score: float = 0.0
    allocation_json: str = Field(default="{}", sa_column=Column(Text))
    intended_start_state_json: str = Field(default="{}", sa_column=Column(Text))
    intended_end_state_json: str = Field(default="{}", sa_column=Column(Text))
    continuation_handoff_json: str = Field(default="{}", sa_column=Column(Text))
    reference_role_map_json: str = Field(default="[]", sa_column=Column(Text))
    surface_profile_id: str | None = Field(default=None, foreign_key="surface_profiles.id")
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ReferenceRoleMap(SQLModel, table=True):
    __tablename__ = "reference_role_maps"

    id: str = Field(default_factory=new_id, primary_key=True)
    video_unit_id: str = Field(foreign_key="video_units.id", index=True)
    reference_id: str
    reference_type: str
    role: str
    intended_influence: str = ""
    protected_attributes_json: str = Field(default="[]", sa_column=Column(Text))
    forbidden_transfer_json: str = Field(default="[]", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now)


class TakeReview(SQLModel, table=True):
    __tablename__ = "take_reviews"

    id: str = Field(default_factory=new_id, primary_key=True)
    video_unit_id: str = Field(foreign_key="video_units.id", index=True)
    provider_run_id: str | None = Field(default=None, index=True)
    source_video_path: str = ""
    observed_start_frame_path: str = ""
    observed_end_frame_path: str = ""
    observed_start_state_json: str = Field(default="{}", sa_column=Column(Text))
    observed_end_state_json: str = Field(default="{}", sa_column=Column(Text))
    review_status: str = "pending"
    rejection_reasons_json: str = Field(default="[]", sa_column=Column(Text))
    reviewer_notes: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
