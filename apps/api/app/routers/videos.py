from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlmodel import Session

from app.routers.workbench import get_session
from app.schemas.videos import (
    BatchCreate,
    BatchLaunch,
    BatchSubmissionChannelUpdate,
    BatchWorkspaceView,
    JimengCliReadinessView,
    JimengCliStatusView,
    JimengVideoModelUpdate,
    JimengVideoModelView,
    VideoGenerationSettingsUpdate,
    VideoProviderModelView,
    LiveReadinessView,
    LiveProviderStatusView,
    LiveVideoAction,
    ProviderProfileCreate,
    ProviderProfileView,
    ProviderTemplateView,
    ProviderPreflightView,
    ProviderRequestPreviewView,
    ProviderResponsePreviewCreate,
    ProviderResponsePreviewView,
    VideoPackageWorkspaceView,
    VideoResultReview,
    VideoReferenceBindingsUpdate,
    VideoTaskSupervisorStatusView,
    VpGenerationJobCreate,
    VpGenerationJobView,
    AiVpBlockCreate,
    VpBlockCreate,
)
from app.services.videos import (
    batch_workspace,
    atlas_cloud_template,
    confirm_budget,
    confirm_all_reference_bindings,
    confirm_all_video_results,
    confirm_task_reference_bindings,
    create_batch,
    create_ai_vp_block,
    huimeng_template,
    import_video,
    jimeng_cli_download_task,
    jimeng_cli_poll_task,
    jimeng_cli_readiness,
    jimeng_cli_status,
    jimeng_cli_submit_task,
    jimeng_video_models,
    jimeng_export,
    list_profiles,
    live_download_task,
    live_poll_task,
    live_readiness,
    live_provider_status,
    live_submit_task,
    launch_batch_video_job,
    provider_preflight,
    provider_request_preview,
    provider_response_preview,
    review_video_result,
    refresh_batch_task_preflight,
    reset_video_reference_bindings,
    prepare_jimeng_cli_retry,
    prepare_video_task_retry,
    remap_batch_provider,
    save_profile,
    set_default_profile,
    transition_vp,
    update_jimeng_video_model,
    update_batch_jimeng_video_model,
    update_video_reference_bindings,
    update_job_generation_settings,
    update_task_generation_settings,
    update_batch_submission_channel,
    validate_profile,
    video_package_workspace,
    video_provider_models,
)
from app.services.vp_generation_supervisor import (
    cancel_vp_generation_job,
    create_duration_rebuild_job,
    latest_vp_generation_job,
    retry_vp_generation_job,
    vp_generation_job_view,
)


router = APIRouter(prefix="/api", tags=["videos"])


@router.get("/projects/{project_id}/video-packages", response_model=VideoPackageWorkspaceView)
def read_video_packages(project_id: str, session: Session = Depends(get_session)):
    return video_package_workspace(session, project_id)


@router.get("/scenes/{scene_id}/vp-generation-jobs/latest", response_model=VpGenerationJobView | None)
def read_latest_vp_generation_job(scene_id: str, session: Session = Depends(get_session)):
    job = latest_vp_generation_job(session, scene_id)
    return vp_generation_job_view(job) if job else None


@router.post("/scenes/{scene_id}/vp-generation-jobs", response_model=VpGenerationJobView, status_code=202)
def add_vp_generation_job(
    scene_id: str,
    payload: VpGenerationJobCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    job = create_duration_rebuild_job(session, scene_id, payload.confirm_live_request)
    request.app.state.vp_generation_supervisor.wake()
    return vp_generation_job_view(job)


@router.post("/vp-generation-jobs/{job_id}/retry", response_model=VpGenerationJobView)
def retry_vp_job(job_id: str, request: Request, session: Session = Depends(get_session)):
    job = retry_vp_generation_job(session, job_id)
    request.app.state.vp_generation_supervisor.wake()
    return vp_generation_job_view(job)


@router.post("/vp-generation-jobs/{job_id}/cancel", response_model=VpGenerationJobView)
def cancel_vp_job(job_id: str, session: Session = Depends(get_session)):
    return vp_generation_job_view(cancel_vp_generation_job(session, job_id))


@router.post("/shots/{shot_id}/vp-blocks", response_model=VideoPackageWorkspaceView, status_code=201)
def generate_vp_block(shot_id: str, payload: VpBlockCreate, session: Session = Depends(get_session)):
    raise HTTPException(
        status_code=410,
        detail="本地规则视频提示词已停用。请使用“用真实 AI 生成故事板参考提示词 / 最终视频提示词”。",
    )


@router.post("/shots/{shot_id}/vp-blocks/ai-version", response_model=VideoPackageWorkspaceView, status_code=201)
def generate_ai_vp_block(shot_id: str, payload: AiVpBlockCreate, request: Request, session: Session = Depends(get_session)):
    project_id = create_ai_vp_block(session, request.app.state.settings, shot_id, payload.vp_block, payload.ai_text)
    return video_package_workspace(session, project_id)


@router.post("/vp-blocks/{version_id}/{action}", response_model=VideoPackageWorkspaceView)
def change_vp_status(version_id: str, action: str, session: Session = Depends(get_session)):
    return video_package_workspace(session, transition_vp(session, version_id, action))


@router.get("/projects/{project_id}/batch-video", response_model=BatchWorkspaceView)
def read_batch_video(project_id: str, request: Request, session: Session = Depends(get_session)):
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/scenes/{scene_id}/batch-video-jobs", response_model=BatchWorkspaceView, status_code=201)
def add_batch(scene_id: str, payload: BatchCreate, request: Request, session: Session = Depends(get_session)):
    settings = request.app.state.settings
    submission_channel = payload.submission_channel or (
        "jimeng" if settings.provider_mode == "jimeng_cli"
        else "volcengine_seedance25" if settings.provider_mode == "volcengine_seedance25"
        else "huimeng"
    )
    project_id = create_batch(
        session,
        scene_id,
        payload.provider_profile_id,
        settings.max_video_tasks_per_batch,
        submission_channel,
    )
    return batch_workspace(session, project_id, settings)


@router.post("/batch-video-jobs/{job_id}/confirm-budget", response_model=BatchWorkspaceView)
def approve_budget(job_id: str, request: Request, session: Session = Depends(get_session)):
    return batch_workspace(session, confirm_budget(session, job_id), request.app.state.settings)


@router.post("/batch-video-jobs/{job_id}/confirm-cost-risk", response_model=BatchWorkspaceView)
def approve_cost_risk(job_id: str, request: Request, session: Session = Depends(get_session)):
    return batch_workspace(session, confirm_budget(session, job_id), request.app.state.settings)


@router.post("/batch-video-jobs/{job_id}/reference-bindings/confirm", response_model=BatchWorkspaceView)
def approve_all_reference_bindings(job_id: str, request: Request, session: Session = Depends(get_session)):
    return batch_workspace(session, confirm_all_reference_bindings(session, job_id), request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/reference-bindings/confirm", response_model=BatchWorkspaceView)
def approve_task_reference_bindings(task_id: str, request: Request, session: Session = Depends(get_session)):
    return batch_workspace(session, confirm_task_reference_bindings(session, task_id), request.app.state.settings)


@router.post("/batch-video-jobs/{job_id}/launch", response_model=BatchWorkspaceView, status_code=202)
def launch_batch(job_id: str, payload: BatchLaunch, request: Request, session: Session = Depends(get_session)):
    project_id = launch_batch_video_job(session, job_id, payload.confirm_live_request)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.patch("/batch-video-jobs/{job_id}/submission-channel", response_model=BatchWorkspaceView)
def change_submission_channel(
    job_id: str,
    payload: BatchSubmissionChannelUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = update_batch_submission_channel(
        session,
        job_id,
        payload.submission_channel,
        payload.huimeng_provider_profile_id,
    )
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-jobs/{job_id}/remap-provider", response_model=BatchWorkspaceView)
def remap_provider(job_id: str, payload: BatchCreate, request: Request, session: Session = Depends(get_session)):
    settings = request.app.state.settings
    return batch_workspace(
        session,
        remap_batch_provider(session, job_id, payload.provider_profile_id),
        settings,
    )


@router.post("/batch-video-jobs/{job_id}/jimeng-export", response_model=BatchWorkspaceView)
def export_jimeng(job_id: str, request: Request, session: Session = Depends(get_session)):
    project_id = jimeng_export(session, job_id, request.app.state.settings.projects_root)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/import-video", response_model=BatchWorkspaceView)
def add_imported_video(task_id: str, request: Request, file: UploadFile = File(...), session: Session = Depends(get_session)):
    project_id = import_video(session, task_id, file, request.app.state.settings.projects_root)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/video-result-versions/{result_id}/review", response_model=BatchWorkspaceView)
def review_result(
    result_id: str,
    payload: VideoResultReview,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = review_video_result(session, result_id, payload.decision)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-jobs/{job_id}/review-completed", response_model=BatchWorkspaceView)
def review_all_completed(job_id: str, request: Request, session: Session = Depends(get_session)):
    project_id = confirm_all_video_results(session, job_id)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.get("/video-provider-profiles", response_model=list[ProviderProfileView])
def read_profiles(request: Request, session: Session = Depends(get_session)):
    return list_profiles(session, request.app.state.settings)


@router.get("/video-provider-templates/atlas-cloud", response_model=ProviderTemplateView)
def read_atlas_cloud_template():
    return atlas_cloud_template()


@router.get("/video-provider-live-status", response_model=LiveProviderStatusView)
def read_live_provider_status(request: Request):
    return live_provider_status(request.app.state.settings)


@router.get("/jimeng-cli/status", response_model=JimengCliStatusView)
def read_jimeng_cli_status(request: Request):
    return jimeng_cli_status(request.app.state.settings)


@router.get("/video-task-supervisor/status", response_model=VideoTaskSupervisorStatusView)
def read_video_task_supervisor_status(request: Request):
    return request.app.state.video_task_supervisor.status()


@router.get("/jimeng-cli/video-models", response_model=list[JimengVideoModelView])
def read_jimeng_video_models():
    return jimeng_video_models()


@router.get("/video-provider-models", response_model=list[VideoProviderModelView])
def read_video_provider_models(provider_type: str, request: Request):
    return video_provider_models(provider_type, request.app.state.settings)


@router.get("/video-provider-templates/huimeng", response_model=ProviderTemplateView)
def read_huimeng_template(request: Request):
    return huimeng_template(request.app.state.settings)


@router.post("/video-provider-profiles", response_model=ProviderProfileView, status_code=201)
def add_profile(payload: ProviderProfileCreate, session: Session = Depends(get_session)):
    return save_profile(session, payload)


@router.patch("/video-provider-profiles/{profile_id}", response_model=ProviderProfileView)
def update_profile(profile_id: str, payload: ProviderProfileCreate, session: Session = Depends(get_session)):
    return save_profile(session, payload, profile_id)


@router.post("/video-provider-profiles/{profile_id}/validate", response_model=ProviderProfileView)
def check_profile(profile_id: str, session: Session = Depends(get_session)):
    return validate_profile(session, profile_id)


@router.post("/video-provider-profiles/{profile_id}/set-default", response_model=ProviderProfileView)
def use_default_profile(profile_id: str, session: Session = Depends(get_session)):
    return set_default_profile(session, profile_id)


@router.post("/video-provider-profiles/{profile_id}/preflight", response_model=ProviderPreflightView)
def preflight_profile(profile_id: str, session: Session = Depends(get_session)):
    return provider_preflight(session, profile_id)


@router.post("/video-provider-profiles/{profile_id}/response-preview", response_model=ProviderResponsePreviewView)
def preview_provider_response(profile_id: str, payload: ProviderResponsePreviewCreate, session: Session = Depends(get_session)):
    return provider_response_preview(session, profile_id, payload.sample_response)


@router.post("/batch-video-tasks/{task_id}/provider-request-preview", response_model=ProviderRequestPreviewView)
def preview_provider_request(task_id: str, session: Session = Depends(get_session)):
    return provider_request_preview(session, task_id)


@router.get("/batch-video-tasks/{task_id}/live-readiness", response_model=LiveReadinessView)
def read_live_readiness(task_id: str, request: Request, session: Session = Depends(get_session)):
    return live_readiness(session, task_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/jimeng-cli-readiness", response_model=JimengCliReadinessView)
def read_jimeng_cli_readiness(task_id: str, request: Request, session: Session = Depends(get_session)):
    return jimeng_cli_readiness(session, task_id, request.app.state.settings)


@router.patch("/batch-video-tasks/{task_id}/jimeng-cli-model", response_model=BatchWorkspaceView)
def change_jimeng_video_model(
    task_id: str,
    payload: JimengVideoModelUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = update_jimeng_video_model(session, task_id, payload.model_id)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.patch("/batch-video-jobs/{job_id}/jimeng-cli-model", response_model=BatchWorkspaceView)
def change_batch_jimeng_video_model(
    job_id: str,
    payload: JimengVideoModelUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = update_batch_jimeng_video_model(session, job_id, payload.model_id)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.patch("/batch-video-jobs/{job_id}/generation-settings", response_model=BatchWorkspaceView)
def change_batch_generation_settings(
    job_id: str,
    payload: VideoGenerationSettingsUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = update_job_generation_settings(session, job_id, payload)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.patch("/batch-video-tasks/{task_id}/generation-settings", response_model=BatchWorkspaceView)
def change_task_generation_settings(
    task_id: str,
    payload: VideoGenerationSettingsUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = update_task_generation_settings(session, task_id, payload)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.patch("/batch-video-tasks/{task_id}/reference-bindings", response_model=BatchWorkspaceView)
def change_video_reference_bindings(
    task_id: str,
    payload: VideoReferenceBindingsUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = update_video_reference_bindings(session, task_id, payload)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/reference-bindings/reset", response_model=BatchWorkspaceView)
def reset_task_video_reference_bindings(
    task_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    project_id = reset_video_reference_bindings(session, task_id)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/refresh-preflight", response_model=BatchWorkspaceView)
def refresh_video_task_preflight(task_id: str, request: Request, session: Session = Depends(get_session)):
    project_id = refresh_batch_task_preflight(session, task_id)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/jimeng-cli-prepare-retry", response_model=BatchWorkspaceView)
def prepare_jimeng_retry(task_id: str, request: Request, session: Session = Depends(get_session)):
    project_id = prepare_jimeng_cli_retry(session, task_id)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/prepare-retry", response_model=BatchWorkspaceView)
def prepare_task_retry(task_id: str, request: Request, session: Session = Depends(get_session)):
    project_id = prepare_video_task_retry(session, task_id)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/jimeng-cli-submit", response_model=BatchWorkspaceView)
def submit_jimeng_cli_task(task_id: str, payload: LiveVideoAction, request: Request, session: Session = Depends(get_session)):
    project_id = jimeng_cli_submit_task(session, task_id, request.app.state.settings, payload.confirm_live_request)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/jimeng-cli-poll", response_model=BatchWorkspaceView)
def poll_jimeng_cli_task(task_id: str, payload: LiveVideoAction, request: Request, session: Session = Depends(get_session)):
    project_id = jimeng_cli_poll_task(session, task_id, request.app.state.settings, payload.confirm_live_request)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/jimeng-cli-download", response_model=BatchWorkspaceView)
def download_jimeng_cli_task(task_id: str, payload: LiveVideoAction, request: Request, session: Session = Depends(get_session)):
    project_id = jimeng_cli_download_task(session, task_id, request.app.state.settings, payload.confirm_live_request)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/live-submit", response_model=BatchWorkspaceView)
def submit_live_task(task_id: str, payload: LiveVideoAction, request: Request, session: Session = Depends(get_session)):
    project_id = live_submit_task(session, task_id, request.app.state.settings, payload.confirm_live_request)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/live-poll", response_model=BatchWorkspaceView)
def poll_live_task(task_id: str, payload: LiveVideoAction, request: Request, session: Session = Depends(get_session)):
    project_id = live_poll_task(session, task_id, request.app.state.settings, payload.confirm_live_request)
    return batch_workspace(session, project_id, request.app.state.settings)


@router.post("/batch-video-tasks/{task_id}/live-download", response_model=BatchWorkspaceView)
def download_live_task(task_id: str, payload: LiveVideoAction, request: Request, session: Session = Depends(get_session)):
    project_id = live_download_task(session, task_id, request.app.state.settings, payload.confirm_live_request, request.app.state.settings.projects_root)
    return batch_workspace(session, project_id, request.app.state.settings)
