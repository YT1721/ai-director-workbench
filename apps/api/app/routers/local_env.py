from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.local_env import LocalEnvStatusView, LocalEnvUpdate
from app.services.local_env import apply_local_env_update, local_env_status


router = APIRouter(prefix="/api", tags=["local-env"])


@router.get("/local-env/status", response_model=LocalEnvStatusView)
def read_local_env_status(request: Request) -> LocalEnvStatusView:
    return local_env_status(request.app.state.settings)


@router.patch("/local-env", response_model=LocalEnvStatusView)
def update_local_env(payload: LocalEnvUpdate, request: Request) -> LocalEnvStatusView:
    return apply_local_env_update(request.app, payload)

