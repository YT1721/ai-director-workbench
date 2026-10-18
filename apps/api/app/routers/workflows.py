from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.routers.workbench import get_session
from app.schemas.workflows import (
    AiProviderStatusView,
    FixBatchCreate,
    OneClickRunView,
    SummaryCreate,
    TextSummaryView,
    RealTextAcceptanceView,
    WorkflowReviewView,
)
from app.services.workflows import (
    _one_click_view,
    advance_one_click,
    ai_provider_status,
    create_check_report,
    create_one_click,
    fix_issues,
    real_text_acceptance,
    summarize_report,
    workflow_review,
)


router = APIRouter(prefix="/api", tags=["workflows"])


@router.get("/projects/{project_id}/workflow-review", response_model=WorkflowReviewView)
def read_workflow_review(project_id: str, session: Session = Depends(get_session)):
    return workflow_review(session, project_id)


@router.get("/projects/{project_id}/real-text-acceptance", response_model=RealTextAcceptanceView)
def read_real_text_acceptance(project_id: str, session: Session = Depends(get_session)):
    return real_text_acceptance(session, project_id)


@router.post("/scenes/{scene_id}/workflow-check-reports", response_model=WorkflowReviewView, status_code=201)
def generate_check_report(scene_id: str, session: Session = Depends(get_session)):
    report = create_check_report(session, scene_id)
    return workflow_review(session, report.project_id)


@router.post("/workflow-check-reports/{report_id}/summarize", response_model=TextSummaryView)
def summarize_check_report(report_id: str, payload: SummaryCreate, request: Request, session: Session = Depends(get_session)):
    return summarize_report(session, report_id, request.app.state.settings, payload.confirm_live_request, payload.force_regenerate)


@router.post("/workflow-issues/fix-batch", response_model=WorkflowReviewView)
def fix_batch(payload: FixBatchCreate, request: Request, session: Session = Depends(get_session)):
    runs = fix_issues(session, request.app.state.settings.projects_root, payload.issue_ids, payload.confirm_fix)
    if not runs:
        raise HTTPException(400, "至少选择一个检查问题。")
    return workflow_review(session, runs[0].project_id)


@router.post("/scenes/{scene_id}/one-click-runs", response_model=OneClickRunView, status_code=201)
def start_one_click(scene_id: str, session: Session = Depends(get_session)):
    return _one_click_view(create_one_click(session, scene_id))


@router.post("/one-click-runs/{run_id}/advance", response_model=OneClickRunView)
def continue_one_click(run_id: str, session: Session = Depends(get_session)):
    return _one_click_view(advance_one_click(session, run_id))


@router.get("/ai-provider/status", response_model=AiProviderStatusView)
def read_ai_provider_status(request: Request):
    return ai_provider_status(request.app.state.settings)
