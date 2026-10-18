from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.routers.workbench import get_session
from app.schemas.storyboards import (
    AxisPlanUpdate,
    StoryboardImageActionCreate,
    StoryboardImageJobView,
    StoryboardImagePromptView,
    StoryboardImageReadinessView,
    StoryboardImageReuseCreate,
    PromptStoryboardExportView,
    StoryboardVersionCreate,
    StoryboardWorkspaceView,
)
from app.services.storyboards import (
    create_execution_page,
    create_storyboard_version,
    download_storyboard_image_job,
    export_prompt_storyboard_pack,
    poll_storyboard_image_job,
    storyboard_image_readiness,
    storyboard_image_prompt_preview,
    storyboard_workspace,
    reuse_storyboard_image,
    submit_storyboard_image_job,
    transition_storyboard_version,
    update_axis_plan,
)
from app.services.image_task_locks import image_task_lock


router = APIRouter(prefix="/api", tags=["storyboards"])


@router.get("/projects/{project_id}/storyboards", response_model=StoryboardWorkspaceView)
def read_storyboards(project_id: str, session: Session = Depends(get_session)):
    return storyboard_workspace(session, project_id)


@router.patch("/scenes/{scene_id}/axis-plan", response_model=StoryboardWorkspaceView)
def save_axis_plan(
    scene_id: str,
    payload: AxisPlanUpdate,
    session: Session = Depends(get_session),
):
    project_id = update_axis_plan(session, scene_id, payload)
    return storyboard_workspace(session, project_id)


@router.post("/shots/{shot_id}/storyboard-versions", response_model=StoryboardWorkspaceView, status_code=201)
def generate_storyboard_version(
    shot_id: str,
    payload: StoryboardVersionCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = create_storyboard_version(
        session,
        request.app.state.settings.projects_root,
        shot_id,
        payload,
    )
    return storyboard_workspace(session, project_id)


@router.get(
    "/storyboard-versions/{version_id}/image-readiness",
    response_model=StoryboardImageReadinessView,
)
def read_storyboard_image_readiness(
    version_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return storyboard_image_readiness(session, request.app.state.settings, version_id)


@router.get(
    "/storyboard-versions/{version_id}/image-prompt",
    response_model=StoryboardImagePromptView,
)
def read_storyboard_image_prompt(
    version_id: str,
    session: Session = Depends(get_session),
):
    return storyboard_image_prompt_preview(session, version_id)


@router.post(
    "/storyboard-versions/{version_id}/image-submit",
    response_model=StoryboardImageJobView,
    status_code=201,
)
def submit_storyboard_image(
    version_id: str,
    payload: StoryboardImageActionCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    result = submit_storyboard_image_job(
        session,
        request.app.state.settings,
        version_id,
        payload.confirm_live_request,
        payload.correction_note,
        payload.prompt_override,
    )
    request.app.state.image_task_supervisor.wake()
    return result


@router.post(
    "/image-generation-jobs/{job_id}/poll",
    response_model=StoryboardImageJobView,
)
def poll_storyboard_image(
    job_id: str,
    payload: StoryboardImageActionCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    with image_task_lock(job_id) as acquired:
        if not acquired:
            raise RuntimeError("生图任务正在后台同步。")
        return poll_storyboard_image_job(
            session,
            request.app.state.settings,
            job_id,
            payload.confirm_live_request,
        )


@router.post(
    "/image-generation-jobs/{job_id}/download",
    response_model=StoryboardWorkspaceView,
)
def download_storyboard_image(
    job_id: str,
    payload: StoryboardImageActionCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    with image_task_lock(job_id) as acquired:
        if not acquired:
            raise RuntimeError("生图任务正在后台同步。")
        return download_storyboard_image_job(
            session,
            request.app.state.settings,
            request.app.state.settings.projects_root,
            job_id,
            payload.confirm_live_request,
        )


@router.post("/storyboard-versions/{version_id}/reuse-image", response_model=StoryboardWorkspaceView, status_code=201)
def reuse_storyboard_version_image(
    version_id: str,
    payload: StoryboardImageReuseCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = reuse_storyboard_image(
        session,
        request.app.state.settings.projects_root,
        version_id,
        payload.source_version_id,
        payload.confirm_reuse,
        payload.force_reuse,
    )
    return storyboard_workspace(session, project_id)


@router.post("/storyboard-versions/{version_id}/{action}", response_model=StoryboardWorkspaceView)
def change_storyboard_version_status(
    version_id: str,
    action: str,
    session: Session = Depends(get_session),
):
    project_id = transition_storyboard_version(session, version_id, action)
    return storyboard_workspace(session, project_id)


@router.post("/scenes/{scene_id}/storyboard-pages", response_model=StoryboardWorkspaceView, status_code=201)
def generate_execution_page(
    scene_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = create_execution_page(
        session,
        request.app.state.settings.projects_root,
        scene_id,
    )
    return storyboard_workspace(session, project_id)


@router.post("/scenes/{scene_id}/prompt-storyboard-export", response_model=PromptStoryboardExportView, status_code=201)
def export_prompt_storyboard(
    scene_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return export_prompt_storyboard_pack(
        session,
        request.app.state.settings.projects_root,
        scene_id,
    )
