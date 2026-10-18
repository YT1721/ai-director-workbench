from __future__ import annotations

import json

from fastapi import HTTPException
from sqlmodel import Session, select

from app.config import Settings
from app.models import (
    AiTextRun,
    AxisPlan,
    BatchVideoJob,
    BatchVideoTask,
    CostUsageLog,
    Episode,
    OneClickRun,
    PlanningDraft,
    RequestCacheRecord,
    Scene,
    SceneAsset,
    SceneAssetVersion,
    SceneCharacterBinding,
    Shot,
    StoryboardShotVersion,
    StoryboardStyleLock,
    VpBlock,
    WorkflowCheckReport,
    WorkflowFixRun,
    WorkflowIssue,
)
from app.models.workbench import utc_now
from app.providers import TextProvider
from app.schemas.workflows import (
    AiProviderStatusView,
    AiTextRunView,
    CheckReportView,
    FixRunView,
    OneClickRunView,
    TextSummaryView,
    WorkflowIssueView,
    RealTextAcceptanceItemView,
    RealTextAcceptanceView,
    WorkflowReviewView,
    WorkflowSceneView,
)
from app.services.ai_text import summarize_report_with_text_provider
from app.services.assets import _scene_with_project, _scope_code
from app.services.projects import get_project


STORYBOARD_SCHEMA_VERSIONS = {"unified_sb_v1", "vp_precision_18_v1"}


def _json(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _active(session: Session, model, field, owner_id: str):
    versions = session.exec(select(model).where(field == owner_id).order_by(model.version_number.desc())).all()
    return next((item for item in versions if item.status in {"confirmed_current", "locked"}), None)


def _latest(session: Session, model, field, owner_id: str):
    return session.exec(select(model).where(field == owner_id).order_by(model.version_number.desc())).first()


def _active_v7_storyboard(session: Session, shot_id: str):
    return next((
        item for item in session.exec(
            select(StoryboardShotVersion).where(StoryboardShotVersion.shot_id == shot_id).order_by(StoryboardShotVersion.version_number.desc())
        ).all()
        if item.schema_version in STORYBOARD_SCHEMA_VERSIONS and item.status in {"confirmed_current", "locked"}
    ), None)


def _active_final_vp(session: Session, shot_id: str):
    return next((
        item for item in session.exec(
            select(VpBlock).where(VpBlock.shot_id == shot_id).order_by(VpBlock.version_number.desc())
        ).all()
        if item.schema_version == "vp_precision_18_v1"
        and item.package_stage == "final_execution"
        and item.status in {"confirmed_current", "locked"}
    ), None)


def _issue(report: WorkflowCheckReport, category: str, target_type: str, target_id: str, title: str, detail: str, fixable: bool) -> WorkflowIssue:
    return WorkflowIssue(
        report_id=report.id, category=category, target_type=target_type, target_id=target_id,
        title=title, detail=detail, fixable=fixable,
    )


def create_check_report(session: Session, scene_id: str) -> WorkflowCheckReport:
    scene, episode, project = _scene_with_project(session, scene_id)
    values = session.exec(select(WorkflowCheckReport.version_number).where(WorkflowCheckReport.scene_id == scene.id)).all()
    report = WorkflowCheckReport(project_id=project.id, scene_id=scene.id, version_number=max(values, default=0) + 1)
    session.add(report)
    session.flush()
    asset_issues: list[WorkflowIssue] = []
    storyboard_issues: list[WorkflowIssue] = []
    video_package_issues: list[WorkflowIssue] = []

    style_lock = session.exec(select(StoryboardStyleLock).where(StoryboardStyleLock.project_id == project.id)).first()
    if not style_lock or not style_lock.enabled or not style_lock.locked:
        storyboard_issues.append(_issue(report, "storyboard", "style_lock", project.id, "故事板风格锁未就绪", "正式故事板必须锁定为白底/浅灰底高信息密度导演故事板说明板风格；镜头画面保持黑白灰铅笔草稿，功能标注使用统一色彩规则。", False))

    scene_asset = session.exec(select(SceneAsset).where(SceneAsset.scene_id == scene.id)).first()
    scene_version = _active(session, SceneAssetVersion, SceneAssetVersion.scene_asset_id, scene_asset.id) if scene_asset else None
    if not scene_version:
        asset_issues.append(_issue(report, "assets", "scene_asset", scene_asset.id if scene_asset else scene.id, "缺少已确认场景资产", "请先准备并确认当前场景设定板。", bool(scene_asset)))

    for binding in session.exec(select(SceneCharacterBinding).where(SceneCharacterBinding.scene_id == scene.id)).all():
        if binding.consistency_status != "passed":
            asset_issues.append(_issue(report, "assets", "binding", binding.id, "人物一致性未通过", binding.consistency_notes or "请回到资产页检查人物与服装绑定。", False))

    shots = session.exec(select(Shot).where(Shot.scene_id == scene.id, Shot.is_archived == False).order_by(Shot.shot_code)).all()  # noqa: E712
    for shot in shots:
        storyboard = _active_v7_storyboard(session, shot.id)
        latest_storyboard = _latest(session, StoryboardShotVersion, StoryboardShotVersion.shot_id, shot.id)
        if not storyboard:
            if latest_storyboard and latest_storyboard.axis_validation_status == "failed":
                storyboard_issues.append(_issue(report, "axis", "storyboard", shot.id, f"{shot.shot_code} 轴线校验失败", latest_storyboard.axis_validation_notes, True))
            else:
                storyboard_issues.append(_issue(report, "storyboard", "storyboard", shot.id, f"{shot.shot_code} 缺少已确认故事板", "请生成并确认风格与轴线通过的故事板。", True))
        elif storyboard.style_validation_status != "passed" or storyboard.axis_validation_status != "passed":
            storyboard_issues.append(_issue(report, "axis", "storyboard", shot.id, f"{shot.shot_code} 故事板校验失败", storyboard.axis_validation_notes or "请修正风格或轴线。", True))
        vp = _active_final_vp(session, shot.id)
        if not vp:
            video_package_issues.append(_issue(report, "video_package", "vp_block", shot.id, f"{shot.shot_code} 缺少已确认视频包", "请在故事板确认后生成成片提示词。", bool(storyboard)))

    # Only surface the earliest failing stage. Later failures are usually
    # consequences of that stage and would otherwise overwhelm the user.
    if storyboard_issues:
        issues = storyboard_issues
    elif asset_issues:
        issues = asset_issues
    elif video_package_issues:
        issues = video_package_issues
    else:
        issues = []
        latest_job = session.exec(select(BatchVideoJob).where(BatchVideoJob.scene_id == scene.id).order_by(BatchVideoJob.created_at.desc())).first()
        if not latest_job:
            issues.append(_issue(report, "batch_queue", "batch_queue", scene.id, "尚未创建批量视频队列", "请先在批量视频页建立当前场的任务队列。", False))
        else:
            tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == latest_job.id)).all()
            blocked = [item for task in tasks for item in _json(task.missing_items_json, [])]
            if blocked:
                issues.append(_issue(report, "provider", "batch_queue", latest_job.id, "批量队列仍有阻塞项", "；".join(blocked), False))
            if not latest_job.budget_confirmed:
                issues.append(_issue(report, "budget", "budget", latest_job.id, "费用尚未人工确认", "请核对服务商价格和账户余额，并确认预计费用或费用风险，避免误触发真实服务。", False))

    for item in issues:
        session.add(item)
    report.ready_for_next = not issues
    report.status = "ready" if report.ready_for_next else "blocked"
    report.report_json = json.dumps({
        "project_code": project.project_code, "scope": _scope_code(episode, scene),
        "status": report.status, "ready_for_next": report.ready_for_next,
        "issues": [{"category": item.category, "title": item.title, "detail": item.detail} for item in issues],
    }, ensure_ascii=False, sort_keys=True)
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def _issue_view(issue: WorkflowIssue) -> WorkflowIssueView:
    return WorkflowIssueView(**issue.model_dump())


def _report_view(session: Session, report: WorkflowCheckReport) -> CheckReportView:
    scene, episode, _ = _scene_with_project(session, report.scene_id)
    issues = session.exec(select(WorkflowIssue).where(WorkflowIssue.report_id == report.id).order_by(WorkflowIssue.created_at)).all()
    return CheckReportView(**report.model_dump(exclude={"report_json"}), scope_code=_scope_code(episode, scene), issues=[_issue_view(item) for item in issues])


def _summary_view(run: AiTextRun, cache_hit: bool | None = None) -> TextSummaryView:
    return TextSummaryView(
        id=run.id,
        report_id=run.report_id,
        provider=run.provider,
        model_name=run.model_name,
        response_text=run.response_text,
        cache_hit=run.cache_hit if cache_hit is None else cache_hit,
        input_tokens=run.input_tokens,
        cached_input_tokens=run.cached_input_tokens,
        output_tokens=run.output_tokens,
        created_at=run.created_at,
    )


def _ai_text_view(run: AiTextRun) -> AiTextRunView:
    return AiTextRunView(
        id=run.id,
        project_id=run.project_id,
        report_id=run.report_id,
        source_extraction_id=run.source_extraction_id,
        target_type=run.target_type,
        target_id=run.target_id,
        module_type=run.module_type,
        provider=run.provider,
        model_name=run.model_name,
        response_text=run.response_text,
        response_json=run.response_json,
        status=run.status,
        error_message=run.error_message,
        cache_hit=run.cache_hit,
        input_tokens=run.input_tokens,
        cached_input_tokens=run.cached_input_tokens,
        output_tokens=run.output_tokens,
        created_at=run.created_at,
    )


def _fix_view(run: WorkflowFixRun) -> FixRunView:
    return FixRunView(**run.model_dump(exclude={"project_id", "scene_id", "source_version_id"}))


def _one_click_view(run: OneClickRun) -> OneClickRunView:
    return OneClickRunView(**run.model_dump(exclude={"project_id", "progress_json", "updated_at"}), progress=_json(run.progress_json, []))


def workflow_review(session: Session, project_id: str) -> WorkflowReviewView:
    project = get_project(session, project_id)
    scenes: list[WorkflowSceneView] = []
    from app.models import Episode
    for episode in session.exec(select(Episode).where(Episode.project_id == project.id)).all():
        for scene in session.exec(select(Scene).where(Scene.episode_id == episode.id, Scene.is_archived == False)).all():  # noqa: E712
            scenes.append(WorkflowSceneView(id=scene.id, scope_code=_scope_code(episode, scene), name=scene.name))
    reports = session.exec(select(WorkflowCheckReport).where(WorkflowCheckReport.project_id == project.id).order_by(WorkflowCheckReport.created_at.desc())).all()
    fix_runs = session.exec(select(WorkflowFixRun).where(WorkflowFixRun.project_id == project.id).order_by(WorkflowFixRun.created_at.desc())).all()
    one_click = session.exec(select(OneClickRun).where(OneClickRun.project_id == project.id).order_by(OneClickRun.created_at.desc())).all()
    summaries = session.exec(select(AiTextRun).join(WorkflowCheckReport).where(WorkflowCheckReport.project_id == project.id).order_by(AiTextRun.created_at.desc())).all()
    text_runs = session.exec(select(AiTextRun).where(AiTextRun.project_id == project.id).order_by(AiTextRun.created_at.desc())).all()
    return WorkflowReviewView(project_id=project.id, project_code=project.project_code, scenes=scenes, reports=[_report_view(session, item) for item in reports], fix_runs=[_fix_view(item) for item in fix_runs], one_click_runs=[_one_click_view(item) for item in one_click], summaries=[_summary_view(item) for item in summaries], text_runs=[_ai_text_view(item) for item in text_runs])


def _latest_ai_text_run(session: Session, project_id: str, module_type: str) -> AiTextRun | None:
    return session.exec(
        select(AiTextRun)
        .where(
            AiTextRun.project_id == project_id,
            AiTextRun.module_type == module_type,
            AiTextRun.status == "completed",
        )
        .order_by(AiTextRun.created_at.desc())
    ).first()


def _acceptance_item(
    key: str,
    label: str,
    action_label: str,
    action_href: str,
    run: AiTextRun | None,
    status: str,
    evidence: str,
) -> RealTextAcceptanceItemView:
    return RealTextAcceptanceItemView(
        key=key,
        label=label,
        status=status,
        evidence=evidence,
        action_label=action_label,
        action_href=action_href,
        provider=run.provider if run else "",
        model_name=run.model_name if run else "",
        output_tokens=run.output_tokens if run else 0,
        created_at=run.created_at if run else None,
    )


def real_text_acceptance(session: Session, project_id: str) -> RealTextAcceptanceView:
    project = get_project(session, project_id)
    director = _latest_ai_text_run(session, project.id, "director_analysis")
    planning = _latest_ai_text_run(session, project.id, "planning_draft")
    asset = _latest_ai_text_run(session, project.id, "asset_brief")
    storyboard = _latest_ai_text_run(session, project.id, "storyboard_brief")
    vp = _latest_ai_text_run(session, project.id, "vp_precision_18")
    summary = _latest_ai_text_run(session, project.id, "workflow_check_summary")

    has_planning_draft = bool(session.exec(select(PlanningDraft).where(PlanningDraft.project_id == project.id)).first())
    episodes = session.exec(select(Episode).where(Episode.project_id == project.id)).all()
    scenes = session.exec(select(Scene).where(Scene.episode_id.in_([item.id for item in episodes]))).all() if episodes else []
    shots = session.exec(select(Shot).where(Shot.scene_id.in_([item.id for item in scenes]))).all() if scenes else []
    has_vp_block = bool(
        session.exec(
            select(VpBlock).where(
                VpBlock.shot_id.in_([item.id for item in shots]),
                VpBlock.schema_version == "vp_precision_18_v1",
            )
        ).first()
    ) if shots else False
    steps = [
        ("director_analysis", "真实导演启动分析", "去开始页生成导演分析", "/start-plan#ai-director-analysis", director, bool(director), "已保存真实 AI 导演分析记录。"),
        ("planning_draft", "真实规划草案", "去开始页生成规划草案", "/start-plan#ai-planning-draft", planning, bool(planning and has_planning_draft), "已保存真实 AI 规划草案，并生成可审阅结构。"),
        ("asset_brief", "真实资产文字建议", "去资产页生成资产建议", "/assets", asset, bool(asset), "已保存人物、服装、场景的真实 AI 文字建议。"),
        ("storyboard_brief", "真实故事板文字拆解", "去故事板页拆解故事板", "/storyboards", storyboard, bool(storyboard), "已保存真实 AI 故事板拆解记录。"),
        ("vp_precision_18", "真实分镜提示词", "去分镜提示词页生成成片提示词", "/video-package", vp, bool(vp and has_vp_block), "已由真实 AI 输出分镜提示词，并保存为可追溯版本。"),
        ("workflow_check_summary", "真实检查摘要", "去检查页生成摘要", "/check-fix?tab=check", summary, bool(summary), "已保存真实 AI 检查摘要。"),
    ]
    first_missing_index = next((index for index, step in enumerate(steps) if not step[5]), None)
    items: list[RealTextAcceptanceItemView] = []
    for index, (key, label, action_label, action_href, run, done, evidence) in enumerate(steps):
        if done:
            status = "done"
            detail = evidence
        elif first_missing_index == index:
            status = "current"
            detail = "还没有真实 AI 完成记录；请在页面逐次确认后生成。"
        else:
            status = "pending"
            detail = "等待前面的真实文本步骤完成后再做。"
        items.append(_acceptance_item(key, label, action_label, action_href, run, status, detail))
    ready = all(item.status == "done" for item in items[:5])
    current = items[first_missing_index] if first_missing_index is not None else items[-1]
    return RealTextAcceptanceView(
        project_id=project.id,
        project_code=project.project_code,
        ready=ready,
        current_label=current.label,
        primary_action_label="真实文本主链已跑通" if ready else current.action_label,
        primary_action_href="/check-fix?tab=check" if ready else current.action_href,
        summary=(
            "导演分析、规划、资产建议、故事板拆解和分镜提示词都已有真实 AI 证据。"
            if ready else f"下一步需要完成：{current.label}。"
        ),
        items=items,
    )


def ai_provider_status(settings: Settings) -> AiProviderStatusView:
    text_mode = settings.text_provider_mode if settings.text_provider_mode in {"huimeng_chat", "openai_responses"} else "huimeng_chat"
    real = settings.enable_real_openai or settings.enable_real_text_analysis
    return AiProviderStatusView(
        mode=text_mode,
        real_openai_enabled=real, api_key_configured=bool(settings.openai_api_key),
        text_model_configured=bool(settings.openai_text_model),
        text_model=settings.openai_text_model,
        routine_model_configured=bool(settings.openai_model_routine),
        routine_model=settings.openai_model_routine,
        image_model_configured=bool(settings.openai_image_model),
        image_model=settings.openai_image_model,
        image_provider_mode="huimeng_image_controlled",
        live_task="允许受控文本分析、规划、提示词和检查摘要；图像与视频仍按页面逐次确认，不会后台自动提交。",
        network_policy="禁止自动真实调用；每次真实文本请求都需要页面确认。",
    )


def summarize_report(session: Session, report_id: str, settings: Settings, confirm_live_request: bool, force_regenerate: bool, provider: TextProvider | None = None) -> TextSummaryView:
    run = summarize_report_with_text_provider(session, report_id, settings, confirm_live_request, force_regenerate, provider)
    return TextSummaryView(**run.model_dump())


def fix_issues(session: Session, projects_root, issue_ids: list[str], confirm_fix: bool) -> list[WorkflowFixRun]:
    if not confirm_fix:
        raise HTTPException(409, "请先确认本次修正。")
    runs: list[WorkflowFixRun] = []
    expected_scene_id = None
    for issue_id in dict.fromkeys(issue_ids):
        issue = session.get(WorkflowIssue, issue_id)
        report = session.get(WorkflowCheckReport, issue.report_id) if issue else None
        if not issue or not report:
            raise HTTPException(404, "检查问题不存在。")
        if expected_scene_id is not None and report.scene_id != expected_scene_id:
            raise HTTPException(400, "一次修正只能处理同一场的检查问题。")
        expected_scene_id = report.scene_id
        created_id = None
        status = "needs_manual"
        message = "请前往对应页面，用真实 AI 或真实生成通道处理；系统不会用本地规则自动伪造新版本。"
        if issue.fixable and issue.target_type == "scene_asset":
            message = "请到资产页填写场景设定，并使用真实生图生成、下载和确认场景版本；系统不会生成占位场景图。"
        elif issue.fixable and issue.target_type == "storyboard":
            message = "请到故事板页先用真实 AI 的视频草案建立任务单，再用真实生图生成并确认故事板；系统不会自动确认本地故事板。"
        elif issue.fixable and issue.target_type == "vp_block":
            message = "请到视频包页用真实文本大脑重新生成 VP-PRECISION-18，并人工确认新版本；系统不会用短提示词或本地规则兜底。"
        run = WorkflowFixRun(project_id=report.project_id, scene_id=report.scene_id, issue_id=issue.id, target_type=issue.target_type,
            created_version_id=created_id, status=status, message=message)
        issue.status = "fixed" if status == "completed" else "needs_manual"; issue.updated_at = utc_now()
        session.add(issue); session.add(run); runs.append(run)
    session.commit()
    return runs


STAGES = [
    ("assets", {"assets"}),
    ("storyboards", {"storyboard", "axis"}),
    ("video_package", {"video_package"}),
    ("batch_queue", {"batch_queue", "provider", "budget"}),
]


def _advance_one_click(session: Session, run: OneClickRun) -> OneClickRun:
    report = create_check_report(session, run.scene_id)
    issues = session.exec(select(WorkflowIssue).where(WorkflowIssue.report_id == report.id)).all()
    progress = []
    for stage, categories in STAGES:
        stage_issues = [item for item in issues if item.category in categories]
        progress.append({"stage": stage, "status": "blocked" if stage_issues else "passed"})
        if stage_issues:
            run.status, run.current_stage = "paused_at_gate", stage
            run.message = f"已暂停：{stage_issues[0].title}"
            break
    else:
        run.status, run.current_stage, run.message = "completed", "completed", "流程闸门全部通过，可以进入下一阶段人工确认或提交。"
    run.progress_json = json.dumps(progress, ensure_ascii=False); run.updated_at = utc_now()
    session.add(run); session.commit(); session.refresh(run)
    return run


def create_one_click(session: Session, scene_id: str) -> OneClickRun:
    _, _, project = _scene_with_project(session, scene_id)
    run = OneClickRun(project_id=project.id, scene_id=scene_id)
    session.add(run); session.commit(); session.refresh(run)
    return _advance_one_click(session, run)


def advance_one_click(session: Session, run_id: str) -> OneClickRun:
    run = session.get(OneClickRun, run_id)
    if not run: raise HTTPException(404, "一键推进记录不存在。")
    return _advance_one_click(session, run)
