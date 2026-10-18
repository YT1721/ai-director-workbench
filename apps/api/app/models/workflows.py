from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.workbench import new_id, utc_now


class WorkflowCheckReport(SQLModel, table=True):
    __tablename__ = "workflow_check_reports"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    version_number: int
    status: str = "blocked"
    ready_for_next: bool = False
    report_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowIssue(SQLModel, table=True):
    __tablename__ = "workflow_issues"

    id: str = Field(default_factory=new_id, primary_key=True)
    report_id: str = Field(foreign_key="workflow_check_reports.id", index=True)
    category: str
    severity: str = "blocking"
    target_type: str
    target_id: str
    title: str
    detail: str
    fixable: bool = False
    status: str = "open"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkflowFixRun(SQLModel, table=True):
    __tablename__ = "workflow_fix_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    issue_id: str = Field(foreign_key="workflow_issues.id", index=True)
    target_type: str
    source_version_id: str | None = None
    created_version_id: str | None = None
    status: str
    message: str
    created_at: datetime = Field(default_factory=utc_now)


class OneClickRun(SQLModel, table=True):
    __tablename__ = "one_click_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    status: str = "paused_at_gate"
    current_stage: str = "assets"
    message: str = ""
    progress_json: str = "[]"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AiTextRun(SQLModel, table=True):
    __tablename__ = "ai_text_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str | None = Field(default=None, foreign_key="projects.id", index=True)
    report_id: str | None = Field(default=None, foreign_key="workflow_check_reports.id", index=True)
    source_extraction_id: str | None = Field(default=None, foreign_key="source_text_extractions.id", index=True)
    target_type: str = ""
    target_id: str = Field(default="", index=True)
    module_type: str = Field(default="workflow_check_summary", index=True)
    provider: str
    model_name: str
    cache_key: str = Field(index=True)
    input_hash: str = Field(default="", index=True)
    response_text: str
    response_json: str = "{}"
    status: str = "completed"
    error_message: str = ""
    cache_hit: bool = False
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime = Field(default_factory=utc_now)
