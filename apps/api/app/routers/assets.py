from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlmodel import Session

from app.routers.workbench import get_session
from app.schemas.assets import (
    AssetInventoryAnalyzeCreate,
    AssetImageActionCreate,
    AssetImageJobView,
    AssetImageReadinessView,
    AssetRequirementUpdate,
    AssetWorkspaceView,
    BindingCreate,
    CharacterCreate,
    CostumeCreate,
    SceneAssetCreate,
)
from app.services.asset_inventory import (
    analyze_asset_inventory,
    auto_bind_assets,
    update_asset_requirement,
)
from app.services.assets import (
    asset_image_readiness,
    asset_version_project_id,
    asset_workspace,
    character_project_id,
    create_character,
    create_costume,
    download_asset_image_job,
    list_asset_image_jobs,
    poll_asset_image_job,
    scene_project_id,
    submit_asset_image_job,
    transition_version,
    upsert_binding,
    upsert_scene_asset,
    upload_asset_image_file,
)
from app.services.image_task_locks import image_task_lock


router = APIRouter(prefix="/api", tags=["assets"])


@router.get("/projects/{project_id}/assets", response_model=AssetWorkspaceView)
def read_assets(project_id: str, session: Session = Depends(get_session)):
    return asset_workspace(session, project_id)


@router.get(
    "/projects/{project_id}/asset-image-jobs",
    response_model=list[AssetImageJobView],
)
def read_asset_image_jobs(
    project_id: str,
    session: Session = Depends(get_session),
):
    return list_asset_image_jobs(session, project_id)


@router.post(
    "/projects/{project_id}/asset-inventory/analyze",
    response_model=AssetWorkspaceView,
    status_code=201,
)
def analyze_project_asset_inventory(
    project_id: str,
    payload: AssetInventoryAnalyzeCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    return analyze_asset_inventory(
        session,
        request.app.state.settings,
        project_id,
        payload,
    )


@router.patch(
    "/asset-requirements/{requirement_id}",
    response_model=AssetWorkspaceView,
)
def edit_asset_requirement(
    requirement_id: str,
    payload: AssetRequirementUpdate,
    session: Session = Depends(get_session),
):
    return update_asset_requirement(session, requirement_id, payload)


@router.post(
    "/projects/{project_id}/assets/auto-bind",
    response_model=AssetWorkspaceView,
)
def bind_project_assets(
    project_id: str,
    session: Session = Depends(get_session),
):
    return auto_bind_assets(session, project_id)


@router.post("/projects/{project_id}/characters", response_model=AssetWorkspaceView, status_code=201)
def add_character(
    project_id: str,
    payload: CharacterCreate,
    session: Session = Depends(get_session),
):
    create_character(session, project_id, payload)
    return asset_workspace(session, project_id)


@router.post("/characters/{character_id}/master-versions", response_model=AssetWorkspaceView, status_code=201)
def generate_character_master(
    character_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    raise HTTPException(
        status_code=410,
        detail="本地 SVG 占位人物图已停用。请使用“真实生图”逐次确认生成正式人物母版。",
    )


@router.post("/characters/{character_id}/costumes", response_model=AssetWorkspaceView, status_code=201)
def add_costume(
    character_id: str,
    payload: CostumeCreate,
    session: Session = Depends(get_session),
):
    costume = create_costume(session, character_id, payload)
    return asset_workspace(session, character_project_id(session, costume.character_id))


@router.post("/costumes/{costume_id}/versions", response_model=AssetWorkspaceView, status_code=201)
def generate_costume_version(
    costume_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    raise HTTPException(
        status_code=410,
        detail="本地 SVG 占位服装图已停用。请使用“真实生图”逐次确认生成正式服装版本。",
    )


@router.post("/scenes/{scene_id}/assets", response_model=AssetWorkspaceView, status_code=201)
def save_scene_asset(
    scene_id: str,
    payload: SceneAssetCreate,
    session: Session = Depends(get_session),
):
    scene_asset = upsert_scene_asset(session, scene_id, payload)
    return asset_workspace(session, scene_project_id(session, scene_asset.scene_id))


@router.post("/scene-assets/{scene_asset_id}/versions", response_model=AssetWorkspaceView, status_code=201)
def generate_scene_asset_version(
    scene_asset_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    raise HTTPException(
        status_code=410,
        detail="本地 SVG 占位场景图已停用。请使用“真实生图”逐次确认生成正式场景版本。",
    )


@router.post("/scenes/{scene_id}/bindings", response_model=AssetWorkspaceView, status_code=201)
def save_binding(
    scene_id: str,
    payload: BindingCreate,
    session: Session = Depends(get_session),
):
    binding = upsert_binding(session, scene_id, payload)
    return asset_workspace(session, scene_project_id(session, binding.scene_id))


@router.post("/asset-versions/{kind}/{version_id}/{action}", response_model=AssetWorkspaceView)
def change_version_status(
    kind: str,
    version_id: str,
    action: str,
    session: Session = Depends(get_session),
):
    project_id = asset_version_project_id(session, kind, version_id)
    transition_version(session, kind, version_id, action)
    return asset_workspace(session, project_id)


@router.get(
    "/asset-images/{kind}/{target_id}/readiness",
    response_model=AssetImageReadinessView,
)
def read_asset_image_readiness(
    kind: str,
    target_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return asset_image_readiness(session, request.app.state.settings, kind, target_id)


@router.post(
    "/asset-images/{kind}/{target_id}/submit",
    response_model=AssetImageJobView,
    status_code=201,
)
def submit_asset_image(
    kind: str,
    target_id: str,
    payload: AssetImageActionCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    result = submit_asset_image_job(
        session,
        request.app.state.settings,
        kind,
        target_id,
        payload.confirm_live_request,
    )
    request.app.state.image_task_supervisor.wake()
    return result


@router.post(
    "/asset-images/{kind}/{target_id}/upload",
    response_model=AssetWorkspaceView,
    status_code=201,
)
async def upload_asset_image(
    kind: str,
    target_id: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    return upload_asset_image_file(
        session,
        request.app.state.settings.projects_root,
        kind,
        target_id,
        file.filename or "asset.png",
        await file.read(),
    )


@router.post(
    "/asset-image-jobs/{job_id}/poll",
    response_model=AssetImageJobView,
)
def poll_asset_image(
    job_id: str,
    payload: AssetImageActionCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    with image_task_lock(job_id) as acquired:
        if not acquired:
            raise RuntimeError("生图任务正在后台同步。")
        return poll_asset_image_job(
            session,
            request.app.state.settings,
            job_id,
            payload.confirm_live_request,
        )


@router.post(
    "/asset-image-jobs/{job_id}/download",
    response_model=AssetWorkspaceView,
)
def download_asset_image(
    job_id: str,
    payload: AssetImageActionCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    with image_task_lock(job_id) as acquired:
        if not acquired:
            raise RuntimeError("生图任务正在后台同步。")
        return download_asset_image_job(
            session,
            request.app.state.settings,
            request.app.state.settings.projects_root,
            job_id,
            payload.confirm_live_request,
        )
