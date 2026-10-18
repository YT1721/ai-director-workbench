from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.models import ReferenceRoleMap, SurfaceProfile, TakeReview, VideoUnit
from app.schemas.seedance_os import (
    BoundaryFrameExtractRequest,
    BoundaryFrameExtractResponse,
    PromptCompileRequest,
    PromptCompileResponse,
    SceneDirectingStateUpsert,
    SkillStatusResponse,
    SurfaceProfileCreate,
    TakeReviewCreate,
    VideoUnitCreate,
)
from app.services.seedance_os import (
    compile_unit_prompt,
    create_surface_profile,
    create_video_unit,
    extract_boundary_frames,
    project_state,
    review_take,
    upsert_scene_directing_state,
    video_unit_workspace,
)
from app.services.seedance_skill_adapter import SeedanceSkillAdapter


router = APIRouter(prefix="/api", tags=["seedance-skill-os"])


def get_session(request: Request):
    with Session(request.app.state.database_engine) as session:
        yield session


def _adapter(request: Request) -> SeedanceSkillAdapter:
    root = Path(__file__).resolve().parents[4]
    return SeedanceSkillAdapter(root)


@router.get("/seedance-skill-os/status", response_model=SkillStatusResponse)
def skill_status(request: Request):
    return _adapter(request).status()


@router.get("/projects/{project_id}/director-state")
def get_project_state(project_id: str, session: Session = Depends(get_session)):
    return project_state(session, project_id)


@router.get("/projects/{project_id}/video-units/workspace")
def get_video_unit_workspace(project_id: str, session: Session = Depends(get_session)):
    return video_unit_workspace(session, project_id)


@router.put("/scenes/{scene_id}/directing-state")
def put_scene_state(
    scene_id: str,
    payload: SceneDirectingStateUpsert,
    session: Session = Depends(get_session),
):
    return upsert_scene_directing_state(session, scene_id, payload)


@router.get("/projects/{project_id}/surface-profiles")
def list_surface_profiles(project_id: str, session: Session = Depends(get_session)):
    return session.exec(select(SurfaceProfile).where(SurfaceProfile.project_id == project_id)).all()


@router.post("/projects/{project_id}/surface-profiles")
def post_surface_profile(
    project_id: str,
    payload: SurfaceProfileCreate,
    session: Session = Depends(get_session),
):
    return create_surface_profile(session, project_id, payload)


@router.post("/projects/{project_id}/video-units")
def post_video_unit(
    project_id: str,
    payload: VideoUnitCreate,
    session: Session = Depends(get_session),
):
    return create_video_unit(session, project_id, payload)


@router.get("/video-units/{video_unit_id}")
def get_video_unit(video_unit_id: str, session: Session = Depends(get_session)):
    unit = session.get(VideoUnit, video_unit_id)
    if not unit:
        from fastapi import HTTPException
        raise HTTPException(404, "视频单元不存在。")
    return {
        "unit": unit,
        "reference_roles": session.exec(
            select(ReferenceRoleMap).where(ReferenceRoleMap.video_unit_id == unit.id)
        ).all(),
        "take_reviews": session.exec(
            select(TakeReview).where(TakeReview.video_unit_id == unit.id)
        ).all(),
    }


@router.post("/video-units/{video_unit_id}/take-reviews")
def post_take_review(
    video_unit_id: str,
    payload: TakeReviewCreate,
    session: Session = Depends(get_session),
):
    return review_take(session, video_unit_id, payload)


@router.post(
    "/video-units/{video_unit_id}/extract-boundary-frames",
    response_model=BoundaryFrameExtractResponse,
)
def post_extract_boundary_frames(
    request: Request,
    video_unit_id: str,
    payload: BoundaryFrameExtractRequest,
    session: Session = Depends(get_session),
):
    return extract_boundary_frames(
        session,
        request.app.state.settings,
        video_unit_id,
        payload.source_video_path,
    )


@router.post("/video-units/{video_unit_id}/compile/{vp_block_id}", response_model=PromptCompileResponse)
def compile_prompt(
    request: Request,
    video_unit_id: str,
    vp_block_id: str,
    payload: PromptCompileRequest,
    session: Session = Depends(get_session),
):
    return compile_unit_prompt(
        session,
        video_unit_id,
        vp_block_id,
        _adapter(request),
        payload.additional_constraints,
    )
