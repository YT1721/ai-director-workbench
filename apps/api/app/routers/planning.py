from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.schemas.planning import (
    PlanningDraftCreate,
    PlanningDraftView,
    SourceTextExtractionView,
)
from app.services.planning import (
    apply_planning_draft,
    create_ai_planning_draft,
    extract_source_text,
    list_extractions,
    list_planning_drafts,
    planning_draft_view,
)
from app.schemas.workflows import AiTextRunCreate


router = APIRouter(prefix="/api", tags=["planning"])


def get_session(request: Request):
    with Session(request.app.state.database_engine) as session:
        yield session


@router.post("/source-files/{source_file_id}/extract-text", response_model=SourceTextExtractionView, status_code=201)
def extract_text(
    source_file_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return extract_source_text(session, request.app.state.settings.projects_root, source_file_id)


@router.get("/projects/{project_id}/source-text-extractions", response_model=list[SourceTextExtractionView])
def project_extractions(project_id: str, session: Session = Depends(get_session)):
    return list_extractions(session, project_id)


@router.get("/projects/{project_id}/planning-drafts", response_model=list[PlanningDraftView])
def project_planning_drafts(project_id: str, session: Session = Depends(get_session)):
    return list_planning_drafts(session, project_id)


@router.post("/projects/{project_id}/planning-drafts", response_model=PlanningDraftView, status_code=201)
def create_project_planning_draft(
    project_id: str,
    payload: PlanningDraftCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    raise HTTPException(
        status_code=410,
        detail="本地规则分镜规划已停用。请使用“用 AI 生成分镜规划”，避免把本地规则结果误当成导演级分析。",
    )


@router.post("/projects/{project_id}/planning-drafts/ai", response_model=PlanningDraftView, status_code=201)
def create_project_ai_planning_draft(
    project_id: str,
    payload: AiTextRunCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    draft = create_ai_planning_draft(
        session,
        request.app.state.settings,
        project_id,
        payload,
    )
    return planning_draft_view(session, draft)


@router.post("/planning-drafts/{draft_id}/apply", response_model=PlanningDraftView)
def apply_project_planning_draft(draft_id: str, session: Session = Depends(get_session)):
    draft = apply_planning_draft(session, draft_id)
    return planning_draft_view(session, draft)
