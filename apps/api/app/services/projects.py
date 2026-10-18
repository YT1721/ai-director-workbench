from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from app.models import (
    AiTextRun,
    AxisPlan,
    BatchVideoJob,
    BatchVideoTask,
    Character,
    CharacterMasterVersion,
    CostUsageLog,
    Costume,
    CostumeVersion,
    DirectorOptionConfirmation,
    Episode,
    ImageGenerationJob,
    OneClickRun,
    PlanningDraft,
    PlanningDraftItem,
    Project,
    ProviderRun,
    RequestCacheRecord,
    Scene,
    SceneAsset,
    SceneAssetVersion,
    SceneCharacterBinding,
    Shot,
    SourceFile,
    SourceTextExtraction,
    StoryboardExecutionPage,
    StoryboardShotVersion,
    StoryboardStyleLock,
    UcodeCommand,
    UcodeExecutionRun,
    VideoResultVersion,
    VpBlock,
    WorkflowCheckpoint,
    WorkflowCheckReport,
    WorkflowFixRun,
    WorkflowIssue,
)
from app.models.workbench import utc_now
from app.schemas.workbench import (
    CheckpointView,
    EpisodeView,
    ProjectDetail,
    ProjectOverview,
    ProjectSummary,
    SceneView,
    ShotView,
    UcodeRunView,
)


PROJECT_SUBDIRECTORIES = (
    "00_source/scripts",
    "00_source/references/storyboard_style",
    "00_source/references/character_style",
    "00_source/references/scene_style",
    "01_analysis/director_options",
    "01_analysis/g_blocks",
    "01_analysis/s_blocks",
    "01_analysis/source_extractions",
    "01_analysis/planning_drafts",
    "02_characters/masters",
    "02_characters/costumes",
    "02_characters/state_assets",
    "02_characters/bindings",
    "03_scenes",
    "04_storyboards/style_locks",
    "04_storyboards/frames",
    "04_storyboards/pages",
    "05_video_prompts",
    "06_batch_video/seedance_api",
    "06_batch_video/jimeng_credit_exports",
    "07_results/generated_videos",
    "07_results/confirmed_clips",
    "99_logs",
)
ALLOWED_EXTENSIONS = {
    "script": {".txt", ".md", ".pdf", ".docx", ".xlsx"},
    "reference": {
        ".png", ".jpg", ".jpeg", ".webp",
        ".mp4", ".mov", ".m4v", ".webm",
        ".mp3", ".wav", ".m4a", ".aac",
    },
    "storyboard_table": {".txt", ".md", ".pdf", ".docx", ".xlsx"},
    "storyboard_table_image": {".png", ".jpg", ".jpeg", ".webp"},
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TEXT_SOURCE_BYTES = 2 * 1024 * 1024


def _next_code(values: list[str], prefix: str, digits: int) -> str:
    numbers = [
        int(match.group(1))
        for value in values
        if (match := re.fullmatch(rf"{prefix}(\d+)", value))
    ]
    return f"{prefix}{max(numbers, default=0) + 1:0{digits}d}"


def _project_root(projects_root: Path, project: Project) -> Path:
    return projects_root / project.project_code


def create_project_directories(projects_root: Path, project: Project) -> None:
    root = _project_root(projects_root, project)
    for relative_path in PROJECT_SUBDIRECTORIES:
        (root / relative_path).mkdir(parents=True, exist_ok=True)


def create_project(session: Session, projects_root: Path, name: str, description: str) -> Project:
    if not name.strip():
        raise HTTPException(status_code=422, detail="项目名称不能为空。")
    existing_codes = list(session.exec(select(Project.project_code)).all())
    project = Project(
        project_code=_next_code(existing_codes, "PRJ", 3),
        name=name.strip(),
        description=description.strip(),
    )
    session.add(project)
    session.flush()
    episode = Episode(project_id=project.id, episode_code="EP01", name="第 1 集")
    session.add(episode)
    session.flush()
    scene = Scene(episode_id=episode.id, scene_code="SC01", name="第 1 场")
    session.add(scene)
    session.flush()
    session.add(Shot(scene_id=scene.id, shot_code="SH001", name="镜头 1"))
    session.commit()
    session.refresh(project)
    create_project_directories(projects_root, project)
    return project


def reveal_in_folder(projects_root: Path, project: Project, relative_path: str = "") -> Path:
    """在本机文件管理器中定位项目文件（macOS 访达）。

    只允许打开当前项目目录内的路径，防止越权访问其他目录。
    """
    root = _project_root(projects_root, project).resolve()
    target = root if not relative_path.strip() else (root / relative_path.strip()).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(status_code=400, detail="只能打开当前项目目录内的文件。")
    if not target.exists():
        raise HTTPException(status_code=404, detail="这个文件不在项目目录里，请刷新页面后再试。")
    if sys.platform != "darwin":
        raise HTTPException(status_code=501, detail=f"当前系统暂不支持自动打开文件夹，请手动打开：{target}")
    command = ["open", str(target)] if target.is_dir() else ["open", "-R", str(target)]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as cause:
        raise HTTPException(status_code=500, detail=f"打开文件夹失败：{cause}") from cause
    return target


def get_project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在。")
    return project


def project_summary(project: Project) -> ProjectSummary:
    return ProjectSummary.model_validate(project, from_attributes=True)


def project_detail(session: Session, project: Project) -> ProjectDetail:
    episodes = session.exec(
        select(Episode)
        .where(Episode.project_id == project.id)
        .order_by(Episode.episode_code)
    ).all()
    episode_views: list[EpisodeView] = []
    for episode in episodes:
        scenes = session.exec(
            select(Scene)
            .where(Scene.episode_id == episode.id)
            .order_by(Scene.scene_code)
        ).all()
        scene_views: list[SceneView] = []
        for scene in scenes:
            shots = session.exec(
                select(Shot)
                .where(Shot.scene_id == scene.id)
                .order_by(Shot.shot_code)
            ).all()
            scene_views.append(
                SceneView(
                    id=scene.id,
                    scene_code=scene.scene_code,
                    name=scene.name,
                    is_archived=scene.is_archived,
                    shots=[
                        ShotView.model_validate(shot, from_attributes=True)
                        for shot in shots
                    ],
                )
            )
        episode_views.append(
            EpisodeView(
                id=episode.id,
                episode_code=episode.episode_code,
                name=episode.name,
                is_archived=episode.is_archived,
                scenes=scene_views,
            )
        )
    return ProjectDetail(
        **project_summary(project).model_dump(),
        episodes=episode_views,
    )


def project_counts(session: Session, project: Project) -> tuple[int, int, int, int]:
    episodes = list(session.exec(select(Episode.id).where(Episode.project_id == project.id)).all())
    scenes = list(
        session.exec(select(Scene.id).where(Scene.episode_id.in_(episodes))).all()
        if episodes
        else []
    )
    shots = list(
        session.exec(select(Shot.id).where(Shot.scene_id.in_(scenes))).all()
        if scenes
        else []
    )
    source_count = len(list(session.exec(select(SourceFile.id).where(SourceFile.project_id == project.id)).all()))
    return len(episodes), len(scenes), len(shots), source_count


def project_overview(
    session: Session,
    project: Project,
    *,
    current_stage: str = "等待开始",
    short_status: str = "等待资料",
    primary_action_label: str = "继续工作",
    primary_action_href: str = "/start-plan#source-intake",
) -> ProjectOverview:
    episode_count, scene_count, shot_count, source_file_count = project_counts(session, project)
    return ProjectOverview(
        **project_summary(project).model_dump(),
        episode_count=episode_count,
        scene_count=scene_count,
        shot_count=shot_count,
        source_file_count=source_file_count,
        current_stage=current_stage,
        short_status=short_status,
        primary_action_label=primary_action_label,
        primary_action_href=primary_action_href,
    )


def archive_record(record) -> None:
    record.is_archived = True
    record.updated_at = utc_now()


def restore_record(record) -> None:
    record.is_archived = False
    record.updated_at = utc_now()


def project_archive_manifest(session: Session, project: Project) -> dict:
    detail = project_detail(session, project)
    episode_count, scene_count, shot_count, source_file_count = project_counts(session, project)
    return {
        "export_type": "ai_director_workbench_project_archive",
        "exported_at": utc_now().isoformat(),
        "project": detail.model_dump(mode="json"),
        "counts": {
            "episodes": episode_count,
            "scenes": scene_count,
            "shots": shot_count,
            "source_files": source_file_count,
        },
        "notice": "本存档只包含项目本地文件与项目结构清单，不包含 .env、API Key 或系统密钥。",
    }


def iter_project_files(projects_root: Path, project: Project):
    root = _project_root(projects_root, project)
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".env" in path.parts or path.name == ".env":
            continue
        yield path


def _delete_records(session: Session, model, condition) -> None:
    for item in session.exec(select(model).where(condition)).all():
        session.delete(item)


def hard_delete_project(session: Session, projects_root: Path, project: Project, confirm_project_name: str) -> None:
    if confirm_project_name.strip() != project.name:
        raise HTTPException(status_code=400, detail="项目名称不匹配，已取消彻底删除。")

    episode_ids = list(session.exec(select(Episode.id).where(Episode.project_id == project.id)).all())
    scene_ids = list(
        session.exec(select(Scene.id).where(Scene.episode_id.in_(episode_ids))).all()
        if episode_ids
        else []
    )
    shot_ids = list(
        session.exec(select(Shot.id).where(Shot.scene_id.in_(scene_ids))).all()
        if scene_ids
        else []
    )
    character_ids = list(session.exec(select(Character.id).where(Character.project_id == project.id)).all())
    master_ids = list(
        session.exec(select(CharacterMasterVersion.id).where(CharacterMasterVersion.character_id.in_(character_ids))).all()
        if character_ids
        else []
    )
    costume_ids = list(
        session.exec(select(Costume.id).where(Costume.character_id.in_(character_ids))).all()
        if character_ids
        else []
    )
    costume_version_ids = list(
        session.exec(select(CostumeVersion.id).where(CostumeVersion.costume_id.in_(costume_ids))).all()
        if costume_ids
        else []
    )
    scene_asset_ids = list(
        session.exec(select(SceneAsset.id).where(SceneAsset.scene_id.in_(scene_ids))).all()
        if scene_ids
        else []
    )
    scene_asset_version_ids = list(
        session.exec(select(SceneAssetVersion.id).where(SceneAssetVersion.scene_asset_id.in_(scene_asset_ids))).all()
        if scene_asset_ids
        else []
    )
    report_ids = list(session.exec(select(WorkflowCheckReport.id).where(WorkflowCheckReport.project_id == project.id)).all())
    issue_ids = list(
        session.exec(select(WorkflowIssue.id).where(WorkflowIssue.report_id.in_(report_ids))).all()
        if report_ids
        else []
    )
    job_ids = list(session.exec(select(BatchVideoJob.id).where(BatchVideoJob.project_id == project.id)).all())
    task_ids = list(
        session.exec(select(BatchVideoTask.id).where(BatchVideoTask.job_id.in_(job_ids))).all()
        if job_ids
        else []
    )
    text_run_ids = list(session.exec(select(AiTextRun.id).where(AiTextRun.project_id == project.id)).all())
    extraction_ids = list(
        session.exec(select(SourceTextExtraction.id).where(SourceTextExtraction.project_id == project.id)).all()
    )
    planning_draft_ids = list(session.exec(select(PlanningDraft.id).where(PlanningDraft.project_id == project.id)).all())

    if task_ids:
        _delete_records(session, ProviderRun, ProviderRun.task_id.in_(task_ids))
        _delete_records(session, VideoResultVersion, VideoResultVersion.task_id.in_(task_ids))
        _delete_records(session, CostUsageLog, CostUsageLog.task_id.in_(task_ids))
    if text_run_ids:
        _delete_records(session, CostUsageLog, CostUsageLog.text_run_id.in_(text_run_ids))
        _delete_records(session, RequestCacheRecord, RequestCacheRecord.result_reference_id.in_(text_run_ids))
    if issue_ids:
        _delete_records(session, WorkflowFixRun, WorkflowFixRun.issue_id.in_(issue_ids))
    if report_ids:
        _delete_records(session, AiTextRun, AiTextRun.report_id.in_(report_ids))
    if planning_draft_ids:
        _delete_records(session, PlanningDraftItem, PlanningDraftItem.draft_id.in_(planning_draft_ids))

    _delete_records(session, WorkflowIssue, WorkflowIssue.report_id.in_(report_ids)) if report_ids else None
    _delete_records(session, WorkflowCheckReport, WorkflowCheckReport.project_id == project.id)
    _delete_records(session, OneClickRun, OneClickRun.project_id == project.id)
    _delete_records(session, AiTextRun, AiTextRun.project_id == project.id)
    _delete_records(session, PlanningDraftItem, PlanningDraftItem.project_id == project.id)
    _delete_records(session, PlanningDraft, PlanningDraft.project_id == project.id)
    _delete_records(session, SourceTextExtraction, SourceTextExtraction.project_id == project.id)
    _delete_records(session, WorkflowCheckpoint, WorkflowCheckpoint.project_id == project.id)
    _delete_records(session, UcodeExecutionRun, UcodeExecutionRun.project_id == project.id)
    _delete_records(session, SourceFile, SourceFile.project_id == project.id)
    _delete_records(session, StoryboardStyleLock, StoryboardStyleLock.project_id == project.id)
    _delete_records(session, ImageGenerationJob, ImageGenerationJob.project_id == project.id)

    if task_ids:
        _delete_records(session, BatchVideoTask, BatchVideoTask.id.in_(task_ids))
    _delete_records(session, BatchVideoJob, BatchVideoJob.project_id == project.id)

    if shot_ids:
        _delete_records(session, StoryboardShotVersion, StoryboardShotVersion.shot_id.in_(shot_ids))
        _delete_records(session, VpBlock, VpBlock.shot_id.in_(shot_ids))
    if scene_ids:
        _delete_records(session, StoryboardExecutionPage, StoryboardExecutionPage.scene_id.in_(scene_ids))
        _delete_records(session, AxisPlan, AxisPlan.scene_id.in_(scene_ids))
        _delete_records(session, SceneCharacterBinding, SceneCharacterBinding.scene_id.in_(scene_ids))
        _delete_records(session, SceneAsset, SceneAsset.scene_id.in_(scene_ids))
    if scene_asset_version_ids:
        _delete_records(session, VpBlock, VpBlock.scene_asset_version_id.in_(scene_asset_version_ids))
    if scene_asset_ids:
        _delete_records(session, SceneAssetVersion, SceneAssetVersion.scene_asset_id.in_(scene_asset_ids))
    if costume_version_ids:
        _delete_records(session, SceneCharacterBinding, SceneCharacterBinding.costume_version_id.in_(costume_version_ids))
    if costume_ids:
        _delete_records(session, CostumeVersion, CostumeVersion.costume_id.in_(costume_ids))
    if master_ids:
        _delete_records(session, CostumeVersion, CostumeVersion.character_master_version_id.in_(master_ids))
        _delete_records(session, SceneCharacterBinding, SceneCharacterBinding.character_master_version_id.in_(master_ids))
        _delete_records(session, CharacterMasterVersion, CharacterMasterVersion.id.in_(master_ids))
    if costume_ids:
        _delete_records(session, Costume, Costume.id.in_(costume_ids))
    if character_ids:
        _delete_records(session, Character, Character.id.in_(character_ids))
    if shot_ids:
        _delete_records(session, Shot, Shot.id.in_(shot_ids))
    if scene_ids:
        _delete_records(session, Scene, Scene.id.in_(scene_ids))
    if episode_ids:
        _delete_records(session, DirectorOptionConfirmation, DirectorOptionConfirmation.episode_id.in_(episode_ids))
        _delete_records(session, Episode, Episode.id.in_(episode_ids))

    session.delete(project)
    session.commit()
    shutil.rmtree(_project_root(projects_root, project), ignore_errors=True)


def sanitize_filename(filename: str) -> str:
    basename = Path(filename).name.strip()
    stem = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", Path(basename).stem).strip("._")
    suffix = Path(basename).suffix.lower()
    return f"{stem or 'file'}{suffix}"


def save_source_file(
    session: Session,
    projects_root: Path,
    project: Project,
    category: str,
    uploaded_file: UploadFile,
) -> SourceFile:
    allowed = ALLOWED_EXTENSIONS.get(category)
    if allowed is None:
        raise HTTPException(status_code=400, detail="素材分类不支持。")

    original_filename = uploaded_file.filename or "file"
    safe_filename = sanitize_filename(original_filename)
    suffix = Path(safe_filename).suffix.lower()
    if suffix not in allowed:
        readable = "、".join(sorted(allowed))
        raise HTTPException(status_code=400, detail=f"不支持该文件格式。允许格式：{readable}")

    root = _project_root(projects_root, project)
    target_folder = {
        "script": root / "00_source" / "scripts",
        "storyboard_table": root / "00_source" / "scripts",
        "storyboard_table_image": root / "00_source" / "references" / "storyboard_style",
        "reference": root / "00_source" / "references",
    }[category]
    target_folder.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex[:12]}_{safe_filename}"
    target_path = target_folder / stored_filename

    size_bytes = 0
    try:
        with target_path.open("wb") as output:
            while chunk := uploaded_file.file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="单个文件不能超过 25 MB。")
                output.write(chunk)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise

    relative_path = target_path.relative_to(root)
    source_file = SourceFile(
        project_id=project.id,
        category=category,
        original_filename=original_filename,
        stored_filename=stored_filename,
        relative_path=str(relative_path),
        content_type=uploaded_file.content_type,
        size_bytes=size_bytes,
    )
    session.add(source_file)
    session.commit()
    session.refresh(source_file)
    return source_file


def save_source_text(
    session: Session,
    projects_root: Path,
    project: Project,
    category: str,
    title: str,
    content: str,
) -> SourceFile:
    if category not in {"script_text", "storyboard_table"}:
        raise HTTPException(status_code=400, detail="文本资料分类必须为 script_text 或 storyboard_table。")
    text = content.strip()
    if not text:
        raise HTTPException(status_code=422, detail="文本内容不能为空。")
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_TEXT_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="粘贴文本不能超过 2 MB。")

    safe_title = sanitize_filename(f"{title}.txt")
    root = _project_root(projects_root, project)
    target_folder = root / "00_source" / "scripts"
    target_folder.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex[:12]}_{safe_title}"
    target_path = target_folder / stored_filename
    target_path.write_bytes(encoded)

    source_file = SourceFile(
        project_id=project.id,
        category=category,
        original_filename=safe_title,
        stored_filename=stored_filename,
        relative_path=str(target_path.relative_to(root)),
        content_type="text/plain; charset=utf-8",
        size_bytes=len(encoded),
    )
    session.add(source_file)
    session.commit()
    session.refresh(source_file)
    return source_file


def create_ucode_run(
    session: Session,
    project: Project,
    action: str,
    scope_code: str,
    additional_request: str,
    projects_root: Path | None = None,
) -> UcodeExecutionRun:
    command = session.get(UcodeCommand, action)
    if command is None:
        raise HTTPException(status_code=400, detail="不支持该 UCODE-9 动作。")

    command_text = command.default_template.format(scope=scope_code)
    result_summary = (
        f"手动记录已保存：{command.display_name}。范围为 {scope_code}。"
        "这不是 AI 分析结果；真正的导演级产出请使用页面上的真实文本大脑入口。"
    )
    run = UcodeExecutionRun(
        project_id=project.id,
        ucode_action=action,
        scope_code=scope_code,
        additional_request=additional_request.strip(),
        command_text=command_text,
        result_summary=result_summary,
        checkpoint_required=command.checkpoint_required,
    )
    session.add(run)
    session.flush()
    if command.checkpoint_required:
        session.add(
            WorkflowCheckpoint(
                project_id=project.id,
                execution_run_id=run.id,
                title=f"请确认“{command.display_name}”手动记录后再进入下一步。",
            )
        )
    session.commit()
    session.refresh(run)
    return run


def ucode_run_view(session: Session, run: UcodeExecutionRun) -> UcodeRunView:
    checkpoints = session.exec(
        select(WorkflowCheckpoint)
        .where(WorkflowCheckpoint.execution_run_id == run.id)
        .order_by(WorkflowCheckpoint.created_at)
    ).all()
    return UcodeRunView(
        **run.model_dump(),
        checkpoints=[
            CheckpointView.model_validate(checkpoint, from_attributes=True)
            for checkpoint in checkpoints
        ],
    )
