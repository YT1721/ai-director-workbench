from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.models import Episode
from app.routers.workbench import get_session
from app.schemas.flow_nav import (
    DirectorOptionConfirmationCreate,
    FlowNavView,
)
from app.services.flow_nav import confirm_director_option, flow_nav


router = APIRouter(prefix="/api", tags=["flow-nav"])


@router.get("/projects/{project_id}/flow-nav", response_model=FlowNavView)
def read_flow_nav(project_id: str, session: Session = Depends(get_session)):
    return flow_nav(session, project_id)


@router.post(
    "/episodes/{episode_id}/director-option-confirmations",
    response_model=FlowNavView,
    status_code=201,
)
def add_director_option_confirmation(
    episode_id: str,
    payload: DirectorOptionConfirmationCreate,
    session: Session = Depends(get_session),
):
    confirmation = confirm_director_option(session, episode_id, payload)
    episode = session.get(Episode, confirmation.episode_id)
    return flow_nav(session, episode.project_id)
