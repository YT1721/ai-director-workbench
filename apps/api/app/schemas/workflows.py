from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkflowIssueView(BaseModel):
    id: str
    category: str
    severity: str
    target_type: str
    target_id: str
    title: str
    detail: str
    fixable: bool
    status: str


class CheckReportView(BaseModel):
    id: str
    project_id: str
    scene_id: str
    scope_code: str
    version_number: int
    status: str
    ready_for_next: bool
    issues: list[WorkflowIssueView]
    created_at: datetime


class TextSummaryView(BaseModel):
    id: str
    report_id: str | None
    provider: str
    model_name: str
    response_text: str
    cache_hit: bool
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    created_at: datetime


class AiTextRunView(BaseModel):
    id: str
    project_id: str | None
    report_id: str | None
    source_extraction_id: str | None
    target_type: str
    target_id: str
    module_type: str
    provider: str
    model_name: str
    response_text: str
    response_json: str
    status: str
    error_message: str
    cache_hit: bool
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    created_at: datetime


class AiTextRunCreate(BaseModel):
    module_type: str = ""
    source_extraction_id: str | None = None
    target_type: str = ""
    target_id: str = ""
    provider_mode: str | None = None
    confirm_live_request: bool = False
    force_regenerate: bool = False
    user_note: str = ""


class TextProviderStatusView(BaseModel):
    mode: str
    mode_label: str
    real_text_enabled: bool
    requires_user_confirmation: bool
    uses_full_system_prompt: bool
    system_prompt_loaded: bool
    system_prompt_filename: str
    system_prompt_version: str
    system_prompt_sha256_short: str
    openai_api_key_configured: bool
    openai_model: str
    huimengi_api_key_configured: bool
    huimengi_text_base_url: str
    huimengi_text_model: str
    text_api_key_configured: bool = False
    text_base_url: str = ""
    text_model: str = ""
    text_service_label: str = ""
    ready: bool
    blocking_reason: str
    network_policy: str


class WorkflowSceneView(BaseModel):
    id: str
    scope_code: str
    name: str


class FixRunView(BaseModel):
    id: str
    issue_id: str
    target_type: str
    created_version_id: str | None
    status: str
    message: str
    created_at: datetime


class OneClickRunView(BaseModel):
    id: str
    scene_id: str
    status: str
    current_stage: str
    message: str
    progress: list[dict[str, str]]
    created_at: datetime


class WorkflowReviewView(BaseModel):
    project_id: str
    project_code: str
    scenes: list[WorkflowSceneView]
    reports: list[CheckReportView]
    fix_runs: list[FixRunView]
    one_click_runs: list[OneClickRunView]
    summaries: list[TextSummaryView]
    text_runs: list[AiTextRunView] = []


class RealTextAcceptanceItemView(BaseModel):
    key: str
    label: str
    status: str
    evidence: str
    action_label: str
    action_href: str
    provider: str = ""
    model_name: str = ""
    output_tokens: int = 0
    created_at: datetime | None = None


class RealTextAcceptanceView(BaseModel):
    project_id: str
    project_code: str
    ready: bool
    current_label: str
    primary_action_label: str
    primary_action_href: str
    summary: str
    items: list[RealTextAcceptanceItemView]


class SummaryCreate(BaseModel):
    confirm_live_request: bool = False
    force_regenerate: bool = False


class FixBatchCreate(BaseModel):
    issue_ids: list[str]
    confirm_fix: bool = False


class AiProviderStatusView(BaseModel):
    mode: str
    real_openai_enabled: bool
    api_key_configured: bool
    text_model_configured: bool
    text_model: str
    routine_model_configured: bool
    routine_model: str
    image_model_configured: bool
    image_model: str
    image_provider_mode: str
    live_task: str
    network_policy: str
