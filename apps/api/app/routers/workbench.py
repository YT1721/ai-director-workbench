from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.models import Episode, Project, Scene, Shot, SourceFile, UcodeExecutionRun
from app.models.workbench import utc_now
from app.schemas.workbench import (
    NamedUpdate,
    ProjectCreate,
    ProjectCreativeGoalUpdate,
    ProjectDetail,
    ProjectHardDelete,
    ProjectOverview,
    ProjectReveal,
    ProjectRevealResult,
    RealAcceptanceProjectCreate,
    ProjectSummary,
    ProjectUpdate,
    SourceFileView,
    SourceTextCreate,
    UcodeRunCreate,
    UcodeRunView,
)
from app.services.projects import (
    archive_record,
    create_project,
    get_project,
    hard_delete_project,
    iter_project_files,
    project_archive_manifest,
    project_detail,
    project_overview,
    project_summary,
    restore_record,
    reveal_in_folder,
    save_source_file,
    save_source_text,
    create_ucode_run,
    ucode_run_view,
    _next_code,
)
from app.services.planning import extract_source_text
from app.services.flow_nav import flow_nav


router = APIRouter(prefix="/api", tags=["workbench"])


def get_session(request: Request):
    with Session(request.app.state.database_engine) as session:
        yield session


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(
    include_archived: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    projects = session.exec(select(Project).order_by(Project.project_code)).all()
    return [
        project_summary(project)
        for project in projects
        if include_archived or not project.is_archived
    ]


@router.get("/projects/overview", response_model=list[ProjectOverview])
def list_project_overview(
    include_archived: bool = Query(default=True),
    session: Session = Depends(get_session),
):
    projects = session.exec(select(Project).order_by(Project.updated_at.desc())).all()
    overviews: list[ProjectOverview] = []
    for project in projects:
        if project.is_archived and not include_archived:
            continue
        try:
            flow = flow_nav(session, project.id)
            directory_item = next(
                (item for item in flow.directory if item.status_level in {"current", "blocked"}),
                None,
            )
            overviews.append(
                project_overview(
                    session,
                    project,
                    current_stage=flow.current_stage,
                    short_status=directory_item.short_status if directory_item else flow.next_reason,
                    primary_action_label=flow.primary_action_label,
                    primary_action_href=flow.primary_action_href,
                )
            )
        except Exception:
            overviews.append(project_overview(session, project))
    return overviews


@router.post("/projects", response_model=ProjectDetail, status_code=201)
def create_new_project(
    payload: ProjectCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    project = create_project(
        session,
        request.app.state.settings.projects_root,
        payload.name,
        payload.description,
    )
    return project_detail(session, project)


@router.post("/projects/real-acceptance", response_model=ProjectDetail, status_code=201)
def create_real_acceptance_project(
    payload: RealAcceptanceProjectCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    project = create_project(
        session,
        request.app.state.settings.projects_root,
        payload.name,
        payload.description,
    )
    source = save_source_text(
        session,
        request.app.state.settings.projects_root,
        project,
        "script_text",
        "真实验收剧本",
        payload.script_text,
    )
    extract_source_text(session, request.app.state.settings.projects_root, source.id)
    return project_detail(session, project)


@router.get("/projects/{project_id}/export")
def export_project(
    project_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    project = get_project(session, project_id)
    projects_root = request.app.state.settings.projects_root
    archive = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{project.project_code}.zip")
    archive_path = Path(archive.name)
    archive.close()

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        manifest = project_archive_manifest(session, project)
        zip_file.writestr(
            f"{project.project_code}/project_manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        root = projects_root / project.project_code
        for file_path in iter_project_files(projects_root, project) or []:
            zip_file.write(file_path, f"{project.project_code}/{file_path.relative_to(root)}")

    background_tasks.add_task(archive_path.unlink, missing_ok=True)
    safe_name = f"{project.project_code}_{project.name}_项目存档.zip".replace("/", "_")
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=safe_name,
        background=background_tasks,
    )


@router.post("/projects/{project_id}/hard-delete", status_code=204)
def delete_project_permanently(
    project_id: str,
    payload: ProjectHardDelete,
    request: Request,
    session: Session = Depends(get_session),
):
    if not payload.confirm_delete:
        raise HTTPException(status_code=400, detail="请先确认彻底删除。")
    project = get_project(session, project_id)
    hard_delete_project(
        session,
        request.app.state.settings.projects_root,
        project,
        payload.confirm_project_name,
    )
    return None


@router.post("/projects/{project_id}/reveal", response_model=ProjectRevealResult)
def reveal_project_folder(
    project_id: str,
    payload: ProjectReveal,
    request: Request,
    session: Session = Depends(get_session),
):
    project = get_project(session, project_id)
    target = reveal_in_folder(
        request.app.state.settings.projects_root,
        project,
        payload.relative_path,
    )
    return ProjectRevealResult(opened=True, path=str(target))


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def read_project(project_id: str, session: Session = Depends(get_session)):
    return project_detail(session, get_project(session, project_id))


@router.patch("/projects/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    session: Session = Depends(get_session),
):
    project = get_project(session, project_id)
    project.name = payload.name.strip()
    project.description = payload.description.strip()
    project.updated_at = utc_now()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project_detail(session, project)


@router.patch("/projects/{project_id}/creative-goal", response_model=ProjectDetail)
def update_project_creative_goal(
    project_id: str,
    payload: ProjectCreativeGoalUpdate,
    session: Session = Depends(get_session),
):
    project = get_project(session, project_id)
    project.creative_goal = payload.creative_goal
    project.updated_at = utc_now()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project_detail(session, project)


@router.delete("/projects/{project_id}", response_model=ProjectDetail)
def archive_project(project_id: str, session: Session = Depends(get_session)):
    project = get_project(session, project_id)
    archive_record(project)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project_detail(session, project)


@router.post("/projects/{project_id}/restore", response_model=ProjectDetail)
def restore_project(project_id: str, session: Session = Depends(get_session)):
    project = get_project(session, project_id)
    restore_record(project)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project_detail(session, project)


@router.post("/projects/{project_id}/episodes", response_model=ProjectDetail, status_code=201)
def create_episode(project_id: str, session: Session = Depends(get_session)):
    project = get_project(session, project_id)
    codes = list(
        session.exec(select(Episode.episode_code).where(Episode.project_id == project.id)).all()
    )
    code = _next_code(codes, "EP", 2)
    session.add(Episode(project_id=project.id, episode_code=code, name=f"第 {int(code[2:])} 集"))
    session.commit()
    return project_detail(session, project)


@router.patch("/episodes/{episode_id}", response_model=ProjectDetail)
def rename_episode(episode_id: str, payload: NamedUpdate, session: Session = Depends(get_session)):
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="集不存在。")
    episode.name = payload.name.strip()
    episode.updated_at = utc_now()
    session.add(episode)
    session.commit()
    return project_detail(session, get_project(session, episode.project_id))


@router.delete("/episodes/{episode_id}", response_model=ProjectDetail)
def archive_episode(episode_id: str, session: Session = Depends(get_session)):
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="集不存在。")
    archive_record(episode)
    session.add(episode)
    session.commit()
    return project_detail(session, get_project(session, episode.project_id))


@router.post("/episodes/{episode_id}/restore", response_model=ProjectDetail)
def restore_episode(episode_id: str, session: Session = Depends(get_session)):
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="集不存在。")
    restore_record(episode)
    session.add(episode)
    session.commit()
    return project_detail(session, get_project(session, episode.project_id))


@router.post("/episodes/{episode_id}/scenes", response_model=ProjectDetail, status_code=201)
def create_scene(episode_id: str, session: Session = Depends(get_session)):
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="集不存在。")
    codes = list(session.exec(select(Scene.scene_code).where(Scene.episode_id == episode.id)).all())
    code = _next_code(codes, "SC", 2)
    session.add(Scene(episode_id=episode.id, scene_code=code, name=f"第 {int(code[2:])} 场"))
    session.commit()
    return project_detail(session, get_project(session, episode.project_id))


@router.patch("/scenes/{scene_id}", response_model=ProjectDetail)
def rename_scene(scene_id: str, payload: NamedUpdate, session: Session = Depends(get_session)):
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="场不存在。")
    scene.name = payload.name.strip()
    scene.updated_at = utc_now()
    session.add(scene)
    session.commit()
    episode = session.get(Episode, scene.episode_id)
    return project_detail(session, get_project(session, episode.project_id))


@router.delete("/scenes/{scene_id}", response_model=ProjectDetail)
def archive_scene(scene_id: str, session: Session = Depends(get_session)):
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="场不存在。")
    archive_record(scene)
    session.add(scene)
    session.commit()
    episode = session.get(Episode, scene.episode_id)
    return project_detail(session, get_project(session, episode.project_id))


@router.post("/scenes/{scene_id}/restore", response_model=ProjectDetail)
def restore_scene(scene_id: str, session: Session = Depends(get_session)):
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="场不存在。")
    restore_record(scene)
    session.add(scene)
    session.commit()
    episode = session.get(Episode, scene.episode_id)
    return project_detail(session, get_project(session, episode.project_id))


@router.post("/scenes/{scene_id}/shots", response_model=ProjectDetail, status_code=201)
def create_shot(scene_id: str, session: Session = Depends(get_session)):
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="场不存在。")
    codes = list(session.exec(select(Shot.shot_code).where(Shot.scene_id == scene.id)).all())
    code = _next_code(codes, "SH", 3)
    session.add(Shot(scene_id=scene.id, shot_code=code, name=f"镜头 {int(code[2:])}"))
    session.commit()
    episode = session.get(Episode, scene.episode_id)
    return project_detail(session, get_project(session, episode.project_id))


@router.patch("/shots/{shot_id}", response_model=ProjectDetail)
def rename_shot(shot_id: str, payload: NamedUpdate, session: Session = Depends(get_session)):
    shot = session.get(Shot, shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="镜头不存在。")
    shot.name = payload.name.strip()
    shot.updated_at = utc_now()
    session.add(shot)
    session.commit()
    scene = session.get(Scene, shot.scene_id)
    episode = session.get(Episode, scene.episode_id)
    return project_detail(session, get_project(session, episode.project_id))


@router.delete("/shots/{shot_id}", response_model=ProjectDetail)
def archive_shot(shot_id: str, session: Session = Depends(get_session)):
    shot = session.get(Shot, shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="镜头不存在。")
    archive_record(shot)
    session.add(shot)
    session.commit()
    scene = session.get(Scene, shot.scene_id)
    episode = session.get(Episode, scene.episode_id)
    return project_detail(session, get_project(session, episode.project_id))


@router.post("/shots/{shot_id}/restore", response_model=ProjectDetail)
def restore_shot(shot_id: str, session: Session = Depends(get_session)):
    shot = session.get(Shot, shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="镜头不存在。")
    restore_record(shot)
    session.add(shot)
    session.commit()
    scene = session.get(Scene, shot.scene_id)
    episode = session.get(Episode, scene.episode_id)
    return project_detail(session, get_project(session, episode.project_id))


@router.get("/projects/{project_id}/source-files", response_model=list[SourceFileView])
def list_source_files(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    return session.exec(
        select(SourceFile)
        .where(SourceFile.project_id == project_id)
        .order_by(SourceFile.created_at.desc())
    ).all()


@router.post("/projects/{project_id}/source-files", response_model=SourceFileView, status_code=201)
def upload_source_file(
    project_id: str,
    request: Request,
    category: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    return save_source_file(
        session,
        request.app.state.settings.projects_root,
        get_project(session, project_id),
        category,
        file,
    )


@router.post("/projects/{project_id}/source-files/text", response_model=SourceFileView, status_code=201)
def save_source_text_file(
    project_id: str,
    payload: SourceTextCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    return save_source_text(
        session,
        request.app.state.settings.projects_root,
        get_project(session, project_id),
        payload.category,
        payload.title,
        payload.content,
    )


@router.get("/projects/{project_id}/ucode-runs", response_model=list[UcodeRunView])
def list_ucode_runs(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    runs = session.exec(
        select(UcodeExecutionRun)
        .where(UcodeExecutionRun.project_id == project_id)
        .order_by(UcodeExecutionRun.created_at.desc())
    ).all()
    return [ucode_run_view(session, run) for run in runs]


@router.post("/projects/{project_id}/ucode-runs", response_model=UcodeRunView, status_code=201)
def save_ucode_manual_record(
    project_id: str,
    payload: UcodeRunCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    run = create_ucode_run(
        session,
        get_project(session, project_id),
        payload.ucode_action,
        payload.scope_code,
        payload.additional_request,
        request.app.state.settings.projects_root,
    )
    return ucode_run_view(session, run)
