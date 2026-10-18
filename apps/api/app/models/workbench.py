from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_code: str = Field(index=True, unique=True)
    name: str
    description: str = ""
    creative_goal: str = "full_pipeline"
    is_archived: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Episode(SQLModel, table=True):
    __tablename__ = "episodes"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    episode_code: str = Field(index=True)
    name: str
    is_archived: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Scene(SQLModel, table=True):
    __tablename__ = "scenes"

    id: str = Field(default_factory=new_id, primary_key=True)
    episode_id: str = Field(foreign_key="episodes.id", index=True)
    scene_code: str = Field(index=True)
    name: str
    is_archived: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Shot(SQLModel, table=True):
    __tablename__ = "shots"

    id: str = Field(default_factory=new_id, primary_key=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    shot_code: str = Field(index=True)
    name: str
    is_archived: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SourceFile(SQLModel, table=True):
    __tablename__ = "source_files"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    category: str
    original_filename: str
    stored_filename: str
    relative_path: str
    content_type: str | None = None
    size_bytes: int
    created_at: datetime = Field(default_factory=utc_now)


class UcodeCommand(SQLModel, table=True):
    __tablename__ = "ucode_commands"

    id: str = Field(primary_key=True)
    display_name: str
    action: str = Field(index=True, unique=True)
    default_template: str
    checkpoint_required: bool = False


class UcodeExecutionRun(SQLModel, table=True):
    __tablename__ = "ucode_execution_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    ucode_action: str = Field(index=True)
    scope_code: str
    additional_request: str = ""
    command_text: str
    status: str = "completed"
    result_summary: str
    checkpoint_required: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkflowCheckpoint(SQLModel, table=True):
    __tablename__ = "workflow_checkpoints"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    execution_run_id: str = Field(foreign_key="ucode_execution_runs.id", index=True)
    title: str
    status: str = "pending_confirmation"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DirectorOptionConfirmation(SQLModel, table=True):
    __tablename__ = "director_option_confirmations"

    id: str = Field(default_factory=new_id, primary_key=True)
    episode_id: str = Field(foreign_key="episodes.id", index=True)
    version_number: int
    option_name: str
    notes: str = ""
    status: str = "confirmed_current"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SourceTextExtraction(SQLModel, table=True):
    __tablename__ = "source_text_extractions"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    source_file_id: str = Field(foreign_key="source_files.id", index=True)
    version_number: int
    status: str = Field(index=True)
    text_relative_path: str = ""
    character_count: int = 0
    line_count: int = 0
    preview: str = Field(default="", sa_column=Column(Text))
    error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PlanningDraft(SQLModel, table=True):
    __tablename__ = "planning_drafts"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    source_extraction_id: str | None = Field(default=None, foreign_key="source_text_extractions.id", index=True)
    version_number: int
    status: str = Field(default="draft", index=True)
    summary: str = Field(default="", sa_column=Column(Text))
    draft_json: str = Field(default="{}", sa_column=Column(Text))
    applied_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PlanningDraftItem(SQLModel, table=True):
    __tablename__ = "planning_draft_items"

    id: str = Field(default_factory=new_id, primary_key=True)
    draft_id: str = Field(foreign_key="planning_drafts.id", index=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    episode_code: str = "EP01"
    scene_code: str = Field(index=True)
    shot_code: str = Field(index=True)
    source_excerpt: str = Field(default="", sa_column=Column(Text))
    suggested_task: str = Field(default="", sa_column=Column(Text))
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
