from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceTextExtractionView(BaseModel):
    id: str
    project_id: str
    source_file_id: str
    version_number: int
    status: str
    text_relative_path: str
    character_count: int
    line_count: int
    preview: str
    error: str
    created_at: datetime


class PlanningDraftItemView(BaseModel):
    id: str
    draft_id: str
    project_id: str
    episode_code: str
    scene_code: str
    shot_code: str
    source_excerpt: str
    suggested_task: str
    status: str
    created_at: datetime


class PlanningDraftView(BaseModel):
    id: str
    project_id: str
    source_extraction_id: str | None
    version_number: int
    status: str
    summary: str
    draft_json: str
    applied_at: datetime | None
    created_at: datetime
    items: list[PlanningDraftItemView] = []


class PlanningDraftCreate(BaseModel):
    source_extraction_id: str | None = None
    max_items: int = Field(default=80, ge=1, le=120)
