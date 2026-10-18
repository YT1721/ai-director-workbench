from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DirectorOptionConfirmationCreate(BaseModel):
    option_name: str = Field(min_length=1, max_length=160)
    notes: str = Field(default="", max_length=2000)


class DirectorOptionConfirmationView(BaseModel):
    id: str
    episode_id: str
    version_number: int
    option_name: str
    notes: str
    status: str
    created_at: datetime


class FlowNavItemView(BaseModel):
    key: str
    label: str
    command: str
    marker: str
    status_level: str
    short_status: str
    detail: str
    href: str


class FlowNavView(BaseModel):
    project_id: str
    project_code: str
    project_name: str
    scope_code: str
    current_stage: str
    completed_labels: list[str]
    pending_labels: list[str]
    director_option: DirectorOptionConfirmationView | None
    directory: list[FlowNavItemView]
    next_command: str
    next_reason: str
    blocking_reason: str
    primary_action_label: str
    primary_action_href: str
