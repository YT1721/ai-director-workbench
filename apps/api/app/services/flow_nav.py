from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    BatchVideoJob,
    AiTextRun,
    CharacterMasterVersion,
    CostumeVersion,
    DirectorOptionConfirmation,
    Episode,
    PlanningDraft,
    Project,
    Scene,
    SceneAsset,
    SceneAssetVersion,
    SceneCharacterBinding,
    Shot,
    StoryboardShotVersion,
    SourceFile,
    SourceTextExtraction,
    UcodeExecutionRun,
    VpBlock,
)
from app.models.workbench import utc_now
from app.schemas.flow_nav import (
    DirectorOptionConfirmationCreate,
    DirectorOptionConfirmationView,
    FlowNavItemView,
    FlowNavView,
)
from app.services.projects import get_project
from app.services.video_constraints import recommend_video_duration


ACTIVE_STATUSES = {"confirmed_current", "locked"}
STORYBOARD_SCHEMA_VERSIONS = {"unified_sb_v1", "vp_precision_18_v1"}
SOURCE_MATERIAL_CATEGORIES = {"script", "script_text", "storyboard_table", "storyboard_table_image"}


def _active_episode(session: Session, project_id: str) -> Episode | None:
    return session.exec(
        select(Episode)
        .where(Episode.project_id == project_id, Episode.is_archived == False)  # noqa: E712
        .order_by(Episode.episode_code)
    ).first()


def _active_scene(session: Session, episode_id: str) -> Scene | None:
    return session.exec(
        select(Scene)
        .where(Scene.episode_id == episode_id, Scene.is_archived == False)  # noqa: E712
        .order_by(Scene.scene_code)
    ).first()


def _shots(session: Session, scene_id: str) -> list[Shot]:
    return list(
        session.exec(
            select(Shot)
            .where(Shot.scene_id == scene_id, Shot.is_archived == False)  # noqa: E712
            .order_by(Shot.shot_code)
        ).all()
    )


def _latest_option(session: Session, episode_id: str) -> DirectorOptionConfirmation | None:
    return session.exec(
        select(DirectorOptionConfirmation)
        .where(DirectorOptionConfirmation.episode_id == episode_id)
        .order_by(DirectorOptionConfirmation.version_number.desc())
    ).first()


def _has_ucode_run(session: Session, project_id: str, action: str) -> bool:
    return session.exec(
        select(UcodeExecutionRun).where(
            UcodeExecutionRun.project_id == project_id,
            UcodeExecutionRun.ucode_action == action,
        )
    ).first() is not None


def _has_ai_text_run(session: Session, project_id: str, module_type: str) -> bool:
    return session.exec(
        select(AiTextRun).where(
            AiTextRun.project_id == project_id,
            AiTextRun.module_type == module_type,
            AiTextRun.status == "completed",
        )
    ).first() is not None


def _has_source_material(session: Session, project_id: str) -> bool:
    return session.exec(
        select(SourceFile).where(
            SourceFile.project_id == project_id,
            SourceFile.category.in_(SOURCE_MATERIAL_CATEGORIES),
        )
    ).first() is not None


def _latest_extraction(session: Session, project_id: str) -> SourceTextExtraction | None:
    return session.exec(
        select(SourceTextExtraction)
        .where(SourceTextExtraction.project_id == project_id)
        .order_by(SourceTextExtraction.created_at.desc())
    ).first()


def _has_applied_planning_draft(session: Session, project_id: str) -> bool:
    return session.exec(
        select(PlanningDraft).where(
            PlanningDraft.project_id == project_id,
            PlanningDraft.status == "applied",
        )
    ).first() is not None


def _has_planning_draft(session: Session, project_id: str) -> bool:
    return session.exec(
        select(PlanningDraft).where(PlanningDraft.project_id == project_id)
    ).first() is not None


def _has_active_scene_asset(session: Session, scene_id: str) -> bool:
    asset = session.exec(select(SceneAsset).where(SceneAsset.scene_id == scene_id)).first()
    if not asset:
        return False
    return any(
        item.status in ACTIVE_STATUSES
        for item in session.exec(
            select(SceneAssetVersion).where(SceneAssetVersion.scene_asset_id == asset.id)
        ).all()
    )


def _has_ready_character_binding(session: Session, scene_id: str) -> bool:
    binding = session.exec(
        select(SceneCharacterBinding).where(SceneCharacterBinding.scene_id == scene_id)
    ).first()
    if not binding or binding.consistency_status != "passed":
        return False
    master = session.get(CharacterMasterVersion, binding.character_master_version_id)
    costume = session.get(CostumeVersion, binding.costume_version_id)
    return bool(
        master
        and costume
        and master.status in ACTIVE_STATUSES
        and costume.status in ACTIVE_STATUSES
    )


def _has_ready_assets_for_character_shots(session: Session, scene_id: str) -> bool:
    return _has_active_scene_asset(session, scene_id) and _has_ready_character_binding(session, scene_id)


def _latest_vp_block(session: Session, shot_id: str, package_stage: str) -> VpBlock | None:
    return next((
        item
        for item in session.exec(
            select(VpBlock).where(VpBlock.shot_id == shot_id).order_by(VpBlock.version_number.desc())
        ).all()
        if item.schema_version == "vp_precision_18_v1" and item.package_stage == package_stage
    ), None)


def _duration_needs_rebuild(session: Session, shot: Shot) -> bool:
    draft = _latest_vp_block(session, shot.id, "director_draft")
    recommended, _ = recommend_video_duration(shot.name)
    return bool(draft and draft.duration_seconds == 5 and recommended != 5)


def _all_director_drafts_exist(session: Session, shots: list[Shot]) -> bool:
    return bool(shots) and all(
        _latest_vp_block(session, shot.id, "director_draft") is not None
        and not _duration_needs_rebuild(session, shot)
        for shot in shots
    )


def _all_v7_storyboards_confirmed(session: Session, shots: list[Shot]) -> bool:
    if not shots:
        return False
    for shot in shots:
        draft = _latest_vp_block(session, shot.id, "director_draft")
        if draft is None or _duration_needs_rebuild(session, shot):
            return False
        storyboard_ready = any(
            item.schema_version in STORYBOARD_SCHEMA_VERSIONS
            and item.status in ACTIVE_STATUSES
            and item.vp_basis_block_id == draft.id
            for item in session.exec(
                select(StoryboardShotVersion).where(StoryboardShotVersion.shot_id == shot.id)
            ).all()
        )
        if not storyboard_ready:
            return False
    return True


def _all_final_vp_blocks_confirmed(session: Session, shots: list[Shot]) -> bool:
    if not shots:
        return False
    for shot in shots:
        draft = _latest_vp_block(session, shot.id, "director_draft")
        if draft is None or _duration_needs_rebuild(session, shot):
            return False
        final = next((
            item
            for item in session.exec(
                select(VpBlock).where(VpBlock.shot_id == shot.id).order_by(VpBlock.version_number.desc())
            ).all()
            if item.schema_version == "vp_precision_18_v1"
            and item.package_stage == "final_execution"
            and item.basis_vp_block_id == draft.id
        ), None)
        if final is None or final.status not in ACTIVE_STATUSES:
            return False
    return True


def _option_view(item: DirectorOptionConfirmation | None) -> DirectorOptionConfirmationView | None:
    return DirectorOptionConfirmationView.model_validate(item, from_attributes=True) if item else None


def confirm_director_option(
    session: Session,
    episode_id: str,
    payload: DirectorOptionConfirmationCreate,
) -> DirectorOptionConfirmation:
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="集不存在。")
    existing = list(
        session.exec(
            select(DirectorOptionConfirmation)
            .where(DirectorOptionConfirmation.episode_id == episode.id)
            .order_by(DirectorOptionConfirmation.version_number)
        ).all()
    )
    for item in existing:
        if item.status == "confirmed_current":
            item.status = "history"
            item.updated_at = utc_now()
            session.add(item)
    confirmation = DirectorOptionConfirmation(
        episode_id=episode.id,
        version_number=max((item.version_number for item in existing), default=0) + 1,
        option_name=payload.option_name.strip(),
        notes=payload.notes.strip(),
    )
    session.add(confirmation)
    session.commit()
    session.refresh(confirmation)
    return confirmation


def flow_nav(session: Session, project_id: str) -> FlowNavView:
    project: Project = get_project(session, project_id)
    episode = _active_episode(session, project.id)
    scene = _active_scene(session, episode.id) if episode else None
    shots = _shots(session, scene.id) if scene else []
    first_shot = shots[0] if shots else None
    ep_scope = episode.episode_code if episode else "EP01"
    scene_scope = f"{ep_scope}{scene.scene_code if scene else 'SC01'}"
    shot_scope = f"{scene_scope}｜{first_shot.shot_code if first_shot else 'SH001'}"
    storyboard_scope = f"{scene_scope}｜SH001-SH{len(shots):03d}" if shots else f"{scene_scope}｜SH001"
    option = _latest_option(session, episode.id) if episode else None
    has_source_material = _has_source_material(session, project.id)
    has_director_analysis = _has_ai_text_run(session, project.id, "director_analysis")
    latest_extraction = _latest_extraction(session, project.id)
    has_extracted_text = latest_extraction is not None and latest_extraction.status == "extracted"
    has_planning_draft = _has_planning_draft(session, project.id)
    has_applied_planning = _has_applied_planning_draft(session, project.id)
    has_plan_record = _has_ucode_run(session, project.id, "plan") or has_applied_planning
    assets_ready = bool(scene and _has_ready_assets_for_character_shots(session, scene.id))
    duration_rebuild_count = sum(_duration_needs_rebuild(session, shot) for shot in shots)
    drafts_ready = _all_director_drafts_exist(session, shots)
    storyboards_ready = _all_v7_storyboards_confirmed(session, shots)
    final_vp_ready = _all_final_vp_blocks_confirmed(session, shots)
    has_batch_job = bool(scene and session.exec(select(BatchVideoJob).where(BatchVideoJob.scene_id == scene.id)).first())

    step_by_key = {
        "start": ("start", "开始", f"V7｜开始｜{ep_scope}", has_source_material and has_director_analysis, "上传剧本 / 分镜资料，并完成一次真实 AI 导演分析。", "/start-plan#source-intake"),
        "plan": ("plan", "导演分析 / 规划", f"V7｜规划｜{ep_scope}", has_plan_record, "生成并确认分镜规划，确认场次和镜头拆分。", "/start-plan#planning-draft-panel"),
        "director_option": ("director_option", "导演方案选择", "确认导演方案", option is not None, "人工确认当前集采用的导演方案，后续分镜提示词和故事板都沿这个方向推进。", "/start-plan#director-option-panel"),
        "video_package_draft": (
            "video_package_draft",
            "故事板提示词",
            f"V7｜分镜提示词｜{storyboard_scope}｜故事板参考",
            drafts_ready,
            f"仍有 {duration_rebuild_count} 个旧版 5 秒镜头，请按主规则重建时长。" if duration_rebuild_count else "先生成给故事板看的分镜提示词，告诉故事板每个时间段该画什么。",
            "/video-package",
        ),
        "storyboard": ("storyboard", "故事板", f"V7｜故事板｜{storyboard_scope}", storyboards_ready, "根据故事板提示词生成并确认自适应网格故事板。", "/storyboards"),
        "assets": ("assets", "资产图", f"V7｜资产｜{scene_scope}", assets_ready, "成片提示词和批量视频需要人物、场景、道具资产图；黑白故事板草稿不强制等资产。", "/assets"),
        "video_package": ("video_package", "成片提示词", f"V7｜分镜提示词｜{shot_scope}｜成片", final_vp_ready, "故事板确认后，再生成给视频生成服务使用的成片提示词。", "/video-package"),
        "batch_video": ("batch_video", "批量视频", f"V7｜批量视频｜{scene_scope}", has_batch_job, "组装本地队列并进入预算闸门。", "/batch-video"),
    }
    common_order = ["start", "plan", "director_option"]
    if project.creative_goal == "prompt_storyboard":
        production_order = ["video_package_draft", "storyboard", "video_package", "assets", "batch_video"]
    elif project.creative_goal == "asset_only":
        production_order = ["assets", "video_package_draft", "storyboard", "video_package", "batch_video"]
    else:
        production_order = ["video_package_draft", "storyboard", "assets", "video_package", "batch_video"]
    all_steps = [step_by_key[key] for key in [*common_order, *production_order]]
    required_by_goal = {
        "full_pipeline": {"start", "plan", "director_option", "video_package_draft", "storyboard", "assets", "video_package", "batch_video"},
        "prompt_storyboard": {"start", "plan", "director_option", "video_package_draft", "storyboard", "video_package"},
        "asset_only": {"start", "plan", "director_option", "assets"},
        "analysis_plan": {"start", "plan", "director_option"},
    }
    required_keys = required_by_goal.get(project.creative_goal, required_by_goal["full_pipeline"])
    first_incomplete = next((key for key, _, _, complete, _, _ in all_steps if key in required_keys and not complete), "")
    missing_source = first_incomplete == "start" and not has_source_material

    short_statuses = {
        "start": "真实AI已分析" if has_director_analysis else "已解析资料，等待AI分析" if has_source_material and has_extracted_text else "已保存，暂未解析正文" if has_source_material else "请先上传资料",
        "plan": "分镜规划已确认" if has_applied_planning else "等待确认分镜规划" if has_planning_draft else "待生成分镜规划",
        "director_option": "已确认方案" if option else "等待选方案",
        "assets": "资产图已就绪" if assets_ready else "缺少资产图",
        "video_package_draft": "故事板提示词已生成" if drafts_ready else f"{duration_rebuild_count} 个旧版 5 秒镜头待重建" if duration_rebuild_count else "先生成故事板提示词",
        "storyboard": "故事板已确认" if storyboards_ready else "时长重建后需重新确认" if duration_rebuild_count else "缺少故事板",
        "video_package": "成片提示词已确认" if final_vp_ready else "需先重建镜头时长" if duration_rebuild_count else "缺少成片提示词",
        "batch_video": "已有批量队列" if has_batch_job else "待创建队列",
    }
    if project.creative_goal == "prompt_storyboard":
        short_statuses["assets"] = "资产可选，需要一致性时再做" if not assets_ready else "资产图已就绪"
        short_statuses["video_package"] = "无参考图成片提示词已生成" if final_vp_ready else "待生成无参考图成片提示词"

    directory = []
    for key, label, command, complete, detail, href in all_steps:
        required = key in required_keys
        if project.creative_goal == "prompt_storyboard" and key == "assets":
            detail = "需要跨镜外观一致性或图生视频参考时，再补人物、服装、场景和道具资产图。"
        if project.creative_goal == "prompt_storyboard" and key == "video_package":
            detail = "故事板确认后生成不绑定正式资产图的文生视频提示词；不会假装具备人物或场景资产一致性。"
        directory.append(
            FlowNavItemView(
                key=key,
                label=label,
                command=command,
                marker="已完成" if complete else "可选辅助" if not required else "当前建议" if key == first_incomplete else "待进行",
                status_level="done" if complete else "optional" if not required else "blocked" if key == first_incomplete and missing_source else "current" if key == first_incomplete else "pending",
                short_status=short_statuses[key],
                detail=detail,
                href=href,
            )
        )
    directory.append(
        FlowNavItemView(
            key="check",
            label="流程体检",
            command=f"V7｜检查｜{scene_scope}",
            marker="可选辅助",
            status_level="optional",
            short_status="提交前检查",
            detail="按制作顺序检查当前最早的阻塞阶段，并直接定位到处理页面。",
            href="/check-fix",
        )
    )
    current = next((item for item in directory if item.marker == "当前建议"), None)
    completed = [label for key, label, _, complete, _, _ in all_steps if key in required_keys and complete]
    pending = [label for key, label, _, complete, _, _ in all_steps if key in required_keys and not complete]
    if not has_source_material:
        current_stage = "上传剧本 / 分镜资料"
        next_command = "上传剧本 / 分镜表开始"
        next_reason = "请先提供剧本、分镜表或图片资料，系统会保存到本地；随后使用 AI 分析执行 V7｜开始｜EP01 导演分析。"
        blocking_reason = "当前项目还没有剧本或分镜资料，所以不能进入导演分析。"
        primary_action_label = "上传资料"
        primary_action_href = "/start-plan#source-intake"
    elif not has_director_analysis:
        current_stage = "真实 AI 导演分析"
        next_command = f"V7｜开始｜{ep_scope}"
        next_reason = "资料已保存，请用 AI 分析生成导演分析；这一步决定后续镜头理解和视觉方向。"
        blocking_reason = "资料已上传，但还没有完成真实 AI 导演分析。"
        primary_action_label = "用真实 AI 分析"
        primary_action_href = "/start-plan#ai-director-analysis"
    elif has_extracted_text and not has_planning_draft:
        current_stage = "生成分镜规划"
        next_command = f"V7｜规划｜{ep_scope}"
        next_reason = "导演分析已完成，请用 AI 生成 EP / SC / SH 分镜规划；生成后你再选择导演方案并人工确认。"
        blocking_reason = "资料已解析，但尚未生成分镜规划。"
        primary_action_label = "生成分镜规划"
        primary_action_href = "/start-plan#planning-draft-panel"
    elif has_extracted_text and has_planning_draft and option is None:
        current_stage = "选择导演方案"
        next_command = "确认导演方案"
        next_reason = "分镜规划已经有了，请从 AI 给出的导演方案中选择一个方向；后续分镜提示词和故事板会沿这个方向推进。"
        blocking_reason = ""
        primary_action_label = "选择导演方案"
        primary_action_href = "/start-plan#director-option-panel"
    elif has_extracted_text and not has_applied_planning:
        current_stage = "确认分镜规划"
        next_command = f"V7｜规划｜{ep_scope}"
        next_reason = "导演方案已确认，请查看分镜规划表；确认无误后点击“确认分镜规划”，再去生成分镜提示词。"
        blocking_reason = ""
        primary_action_label = "查看并确认分镜规划"
        primary_action_href = "/start-plan#planning-draft-panel"
    else:
        current_stage = current.label if current else "主链路已完成"
        next_command = current.command if current else f"V7｜检查｜{scene_scope}"
        next_reason = current.detail if current else "主链路已完成，建议运行检查确认当前场状态。"
        blocking_reason = "" if current and current.status_level != "blocked" else next_reason
        primary_action_label = "处理下一步" if current else "运行检查"
        primary_action_href = current.href if current else "/check-fix?tab=check"
    return FlowNavView(
        project_id=project.id,
        project_code=project.project_code,
        project_name=project.name,
        scope_code=scene_scope,
        current_stage=current_stage,
        completed_labels=completed,
        pending_labels=pending,
        director_option=_option_view(option),
        directory=directory,
        next_command=next_command,
        next_reason=next_reason,
        blocking_reason=blocking_reason,
        primary_action_label=primary_action_label,
        primary_action_href=primary_action_href,
    )
