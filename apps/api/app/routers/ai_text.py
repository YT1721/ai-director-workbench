from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.routers.workbench import get_session
from app.schemas.workflows import AiTextRunCreate, AiTextRunView, TextProviderStatusView
from app.services.ai_text import list_project_ai_text_runs, run_project_ai_text, run_text_provider_smoke_test, text_provider_status


router = APIRouter(prefix="/api", tags=["ai-text"])


def _project_id_for_shot(session: Session, shot_id: str) -> str:
    from app.models import Episode, Scene, Shot

    shot = session.get(Shot, shot_id)
    if not shot:
        raise HTTPException(404, "镜头不存在。")
    scene = session.get(Scene, shot.scene_id)
    episode = session.get(Episode, scene.episode_id) if scene else None
    if not episode:
        raise HTTPException(404, "镜头所属项目不存在。")
    return episode.project_id


@router.get("/text-provider/status", response_model=TextProviderStatusView)
def read_text_provider_status(request: Request):
    return text_provider_status(request.app.state.settings)


@router.post("/text-provider/smoke-test", response_model=AiTextRunView, status_code=201)
def create_text_provider_smoke_test(
    payload: AiTextRunCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    return run_text_provider_smoke_test(session, request.app.state.settings, payload)


@router.get("/projects/{project_id}/ai-text-runs", response_model=list[AiTextRunView])
def read_project_ai_text_runs(project_id: str, session: Session = Depends(get_session)):
    return list_project_ai_text_runs(session, project_id)


@router.post("/projects/{project_id}/ai-text-runs", response_model=AiTextRunView, status_code=201)
def create_project_ai_text_run(
    project_id: str,
    payload: AiTextRunCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    return run_project_ai_text(session, request.app.state.settings, project_id, payload)


@router.post("/projects/{project_id}/director-analyses/ai", response_model=AiTextRunView, status_code=201)
def create_director_analysis(
    project_id: str,
    payload: AiTextRunCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    payload.module_type = "director_analysis"
    return run_project_ai_text(session, request.app.state.settings, project_id, payload)


@router.post("/projects/{project_id}/asset-briefs/ai", response_model=AiTextRunView, status_code=201)
def create_asset_brief(
    project_id: str,
    payload: AiTextRunCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    payload.module_type = "asset_brief"
    return run_project_ai_text(session, request.app.state.settings, project_id, payload)


@router.post("/shots/{shot_id}/storyboard-briefs/ai", response_model=AiTextRunView, status_code=201)
def create_storyboard_brief(
    shot_id: str,
    payload: AiTextRunCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    payload.module_type = "storyboard_brief"
    payload.target_type = "shot"
    payload.target_id = shot_id
    return run_project_ai_text(session, request.app.state.settings, _project_id_for_shot(session, shot_id), payload)


@router.post("/shots/{shot_id}/vp-blocks/ai", response_model=AiTextRunView, status_code=201)
def create_vp_precision_text(
    shot_id: str,
    payload: AiTextRunCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    payload.module_type = "vp_precision_18"
    payload.target_type = "shot"
    payload.target_id = shot_id
    return run_project_ai_text(session, request.app.state.settings, _project_id_for_shot(session, shot_id), payload)
