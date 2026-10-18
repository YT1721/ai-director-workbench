from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    DirectorProjectState,
    Episode,
    Project,
    ReferenceRoleMap,
    Scene,
    SceneDirectingState,
    Shot,
    StoryboardShotVersion,
    SurfaceProfile,
    TakeReview,
    VideoUnit,
    VpBlock,
)
from app.models.workbench import utc_now
from app.config import Settings
from app.schemas.seedance_os import (
    SceneDirectingStateUpsert,
    SurfaceProfileCreate,
    TakeReviewCreate,
    VideoUnitCreate,
)
from app.services.seedance_prompt_compiler import compile_seedance_prompt, validate_vp_precision_18
from app.services.video_constraints import recommend_video_duration
from app.services.seedance_skill_adapter import SeedanceSkillAdapter


DEFAULT_MAX_EXTENSION_DEPTH = 2
PRODUCTION_CONFIRMED_STATUSES = {"confirmed", "confirmed_current", "locked"}
TIME_RANGE_PATTERN = re.compile(
    r"(?P<start>\d+(?:\.\d+)?)\s*s?\s*[-–—~至]\s*(?P<end>\d+(?:\.\d+)?)\s*s?",
    re.IGNORECASE,
)


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _unique_ids(value: Any) -> list[str]:
    return list(dict.fromkeys(item for item in value if isinstance(item, str) and item))


def _normalize_time_range(value: Any) -> str:
    match = TIME_RANGE_PATTERN.search(str(value or ""))
    if not match:
        return ""
    return f"{float(match.group('start')):g}s-{float(match.group('end')):g}s"


def _storyboard_time_ranges(storyboard: StoryboardShotVersion) -> list[str]:
    sources = (
        _load(storyboard.storyboard_cells_json, []),
        _load(storyboard.timeline_nodes_json, []),
        _load(storyboard.prompt_match_json, []),
    )
    for source in sources:
        ranges: list[str] = []
        for item in source if isinstance(source, list) else []:
            if not isinstance(item, dict):
                continue
            value = (
                item.get("prompt_time_range")
                or item.get("time_range")
                or item.get("range")
            )
            normalized = _normalize_time_range(value)
            if normalized:
                ranges.append(normalized)
        if ranges:
            return ranges
    return []


def _vp_time_ranges(items: list[dict[str, Any]]) -> list[str]:
    if len(items) < 5 or not isinstance(items[4], dict):
        return []
    content = items[4].get("content")
    if not isinstance(content, list):
        return []
    return [
        normalized
        for item in content
        if isinstance(item, dict)
        for normalized in [_normalize_time_range(item.get("time_range") or item.get("prompt_time_range"))]
        if normalized
    ]


def _set_unit_state(
    state: DirectorProjectState,
    *,
    current: str | None = None,
    completed_add: str | None = None,
    rejected_remove: str | None = None,
) -> None:
    completed = _unique_ids(_load(state.completed_video_unit_ids_json, []))
    reserved = _unique_ids(_load(state.reserved_video_unit_ids_json, []))
    previous_current = state.current_video_unit_id
    if current and previous_current and previous_current != current and previous_current not in completed:
        reserved.append(previous_current)
    if completed_add:
        completed.append(completed_add)
    remove_ids = {item for item in (current, completed_add, rejected_remove) if item}
    reserved = [item for item in _unique_ids(reserved) if item not in remove_ids and item not in completed]
    if rejected_remove:
        completed = [item for item in completed if item != rejected_remove]
    state.current_video_unit_id = current
    state.completed_video_unit_ids_json = _dump(_unique_ids(completed))
    state.reserved_video_unit_ids_json = _dump(reserved)


def project_state(session: Session, project_id: str) -> DirectorProjectState:
    if not session.get(Project, project_id):
        raise HTTPException(404, "项目不存在。")
    state = session.exec(
        select(DirectorProjectState).where(DirectorProjectState.project_id == project_id)
    ).first()
    if state:
        return state
    state = DirectorProjectState(project_id=project_id)
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def video_unit_workspace(session: Session, project_id: str) -> dict[str, Any]:
    """Return the production state needed to build and review real Video Units."""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在。")

    episodes = session.exec(
        select(Episode)
        .where(Episode.project_id == project_id)
        .where(Episode.is_archived == False)  # noqa: E712
        .order_by(Episode.episode_code)
    ).all()
    episode_by_id = {item.id: item for item in episodes}
    scenes = session.exec(
        select(Scene)
        .where(Scene.episode_id.in_(list(episode_by_id)))
        .where(Scene.is_archived == False)  # noqa: E712
        .order_by(Scene.scene_code)
    ).all() if episode_by_id else []
    scene_by_id = {item.id: item for item in scenes}
    shots = session.exec(
        select(Shot)
        .where(Shot.scene_id.in_(list(scene_by_id)))
        .where(Shot.is_archived == False)  # noqa: E712
        .order_by(Shot.shot_code)
    ).all() if scene_by_id else []
    shot_by_id = {item.id: item for item in shots}

    storyboards = session.exec(
        select(StoryboardShotVersion)
        .where(StoryboardShotVersion.shot_id.in_(list(shot_by_id)))
        .order_by(StoryboardShotVersion.version_number.desc())
    ).all() if shot_by_id else []
    confirmed_storyboard_by_shot: dict[str, StoryboardShotVersion] = {}
    for storyboard in storyboards:
        if (
            storyboard.status in PRODUCTION_CONFIRMED_STATUSES
            and storyboard.shot_id not in confirmed_storyboard_by_shot
        ):
            confirmed_storyboard_by_shot[storyboard.shot_id] = storyboard

    blocks = session.exec(
        select(VpBlock)
        .where(VpBlock.shot_id.in_(list(shot_by_id)))
        .order_by(VpBlock.version_number.desc())
    ).all() if shot_by_id else []
    final_block_by_shot: dict[str, VpBlock] = {}
    block_by_unit: dict[str, VpBlock] = {}
    for block in blocks:
        if block.video_unit_id:
            block_by_unit.setdefault(block.video_unit_id, block)
        storyboard = confirmed_storyboard_by_shot.get(block.shot_id)
        if (
            block.package_stage == "final_execution"
            and storyboard
            and block.storyboard_version_id == storyboard.id
            and block.shot_id not in final_block_by_shot
        ):
            final_block_by_shot[block.shot_id] = block

    units = session.exec(
        select(VideoUnit)
        .where(VideoUnit.project_id == project_id)
        .order_by(VideoUnit.created_at.desc())
    ).all()
    units_by_shot: dict[str, list[VideoUnit]] = {}
    for unit in units:
        units_by_shot.setdefault(unit.shot_id, []).append(unit)
    reviews = session.exec(
        select(TakeReview).where(TakeReview.video_unit_id.in_([item.id for item in units]))
    ).all() if units else []
    reviews_by_unit: dict[str, list[TakeReview]] = {}
    for review in reviews:
        reviews_by_unit.setdefault(review.video_unit_id, []).append(review)

    candidates: list[dict[str, Any]] = []
    for shot in shots:
        storyboard = confirmed_storyboard_by_shot.get(shot.id)
        block = final_block_by_shot.get(shot.id)
        if not storyboard or not block:
            continue
        scene = scene_by_id[shot.scene_id]
        episode = episode_by_id[scene.episode_id]
        recommended_duration, duration_reason = recommend_video_duration(shot.name)
        duration_needs_rebuild = block.duration_seconds == 5 and recommended_duration != 5
        candidates.append({
            "episode_code": episode.episode_code,
            "scene_id": scene.id,
            "scene_code": scene.scene_code,
            "shot_id": shot.id,
            "shot_code": shot.shot_code,
            "shot_name": shot.name,
            "storyboard_version_id": storyboard.id,
            "storyboard_version": storyboard.version_number,
            "storyboard_status": storyboard.status,
            "storyboard_grid": storyboard.storyboard_grid,
            "prompt_time_ranges": _storyboard_time_ranges(storyboard),
            "vp_block_id": block.id,
            "vp_block_version": block.version_number,
            "vp_block_status": block.status,
            "duration_seconds": min(float(block.duration_seconds), 15.0),
            "recommended_duration_seconds": recommended_duration,
            "duration_reason": duration_reason,
            "duration_needs_rebuild": duration_needs_rebuild,
            "precision_18": _load(block.precision_json, []),
            "existing_video_unit_ids": [item.id for item in units_by_shot.get(shot.id, [])],
            "next_unit_index": max([item.unit_index for item in units_by_shot.get(shot.id, [])], default=0) + 1,
        })

    unit_rows: list[dict[str, Any]] = []
    for unit in units:
        shot = shot_by_id.get(unit.shot_id)
        scene = scene_by_id.get(unit.scene_id)
        block = block_by_unit.get(unit.id) or final_block_by_shot.get(unit.shot_id)
        unit_rows.append({
            **unit.model_dump(),
            "shot_code": shot.shot_code if shot else "",
            "shot_name": shot.name if shot else "",
            "scene_code": scene.scene_code if scene else "",
            "prompt_time_ranges": _load(unit.prompt_time_ranges_json, []),
            "allocation": _load(unit.allocation_json, {}),
            "intended_start_state": _load(unit.intended_start_state_json, {}),
            "intended_end_state": _load(unit.intended_end_state_json, {}),
            "continuation_handoff": _load(unit.continuation_handoff_json, {}),
            "reference_roles": _load(unit.reference_role_map_json, []),
            "vp_block_id": block.id if block else None,
            "vp_block_version": block.version_number if block else None,
            "precision_18": _load(block.precision_json, []) if block else [],
            "vp_prompt_full": block.vp_prompt_full if block else "",
            "vp_prompt_copy": block.prompt_copy if block else "",
            "take_reviews": [
                {
                    **review.model_dump(),
                    "observed_start_state": _load(review.observed_start_state_json, {}),
                    "observed_end_state": _load(review.observed_end_state_json, {}),
                    "rejection_reasons": _load(review.rejection_reasons_json, []),
                }
                for review in reviews_by_unit.get(unit.id, [])
            ],
        })

    state = project_state(session, project_id)
    profiles = session.exec(
        select(SurfaceProfile).where(
            (SurfaceProfile.project_id == project_id) | (SurfaceProfile.project_id == None)  # noqa: E711
        )
    ).all()
    return {
        "project": {"id": project.id, "project_code": project.project_code, "name": project.name},
        "state": {
            **state.model_dump(),
            "canon": _load(state.canon_json, {}),
            "completed_video_unit_ids": _load(state.completed_video_unit_ids_json, []),
            "reserved_video_unit_ids": _load(state.reserved_video_unit_ids_json, []),
        },
        "candidates": candidates,
        "video_units": unit_rows,
        "surface_profiles": profiles,
        "limits": {
            "max_video_unit_seconds": 15,
            "max_extension_depth": DEFAULT_MAX_EXTENSION_DEPTH,
            "provider_submission_requires_confirmation": True,
        },
    }


def upsert_scene_directing_state(
    session: Session,
    scene_id: str,
    payload: SceneDirectingStateUpsert,
) -> SceneDirectingState:
    if not session.get(Scene, scene_id):
        raise HTTPException(404, "场次不存在。")
    state = session.exec(
        select(SceneDirectingState).where(SceneDirectingState.scene_id == scene_id)
    ).first() or SceneDirectingState(scene_id=scene_id)
    for name, value in payload.model_dump(exclude={"power_map"}).items():
        setattr(state, name, value)
    state.power_map_json = _dump(payload.power_map)
    state.updated_at = utc_now()
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def create_surface_profile(
    session: Session,
    project_id: str,
    payload: SurfaceProfileCreate,
) -> SurfaceProfile:
    if not session.get(Project, project_id):
        raise HTTPException(404, "项目不存在。")
    if payload.is_default:
        profiles = session.exec(
            select(SurfaceProfile).where(SurfaceProfile.project_id == project_id)
        ).all()
        for profile in profiles:
            profile.is_default = False
            session.add(profile)
    profile = SurfaceProfile(
        project_id=project_id,
        name=payload.name,
        provider_type=payload.provider_name,
        model_id=payload.model_id,
        prompt_strategy=payload.prompt_strategy,
        supported_input_types_json=_dump(payload.supported_inputs),
        max_duration_seconds=payload.max_duration_seconds,
        verification_date=payload.verification_date,
        duration_range_json=_dump(payload.duration_range),
        prompt_budget=payload.prompt_budget,
        reference_tag_convention=payload.reference_tag_convention,
        supported_modes_json=_dump(payload.supported_modes),
        reference_limits_json=_dump(payload.reference_limits),
        first_last_frame_support=payload.first_last_frame_support,
        edit_support=payload.edit_support,
        extend_support=payload.extend_support,
        audio_behavior=payload.audio_behavior,
        resolutions_json=_dump(payload.resolutions),
        aspect_ratios_json=_dump(payload.aspect_ratios),
        region=payload.region,
        pricing_json=_dump(payload.pricing),
        authorization_requirements_json=_dump(payload.authorization_requirements),
        known_constraints_json=_dump(payload.known_constraints),
        capability_overrides_json=_dump(payload.capability_overrides),
        is_default=payload.is_default,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def _lineage(session: Session, scene_id: str, shot_id: str) -> tuple[Scene, Shot, Project]:
    scene = session.get(Scene, scene_id)
    shot = session.get(Shot, shot_id)
    if not scene or not shot or shot.scene_id != scene.id:
        raise HTTPException(422, "镜头不属于所选场次。")
    episode = session.get(Episode, scene.episode_id)
    project = session.get(Project, episode.project_id) if episode else None
    if not project:
        raise HTTPException(404, "镜头所属项目不存在。")
    return scene, shot, project


def _accepted_source_review(
    session: Session,
    source_unit: VideoUnit,
    review_id: str | None,
) -> TakeReview:
    review = session.get(TakeReview, review_id) if review_id else session.exec(
        select(TakeReview)
        .where(TakeReview.video_unit_id == source_unit.id)
        .where(TakeReview.review_status == "accepted")
        .order_by(TakeReview.created_at.desc())
    ).first()
    if not review or review.video_unit_id != source_unit.id:
        raise HTTPException(409, "续写缺少上一单元的真实验收记录。")
    if review.review_status != "accepted":
        raise HTTPException(409, "被拒绝的成片不能作为下一视频单元来源。")
    if not _load(review.observed_end_state_json, {}):
        raise HTTPException(409, "续写来源缺少真实尾帧状态，不能继续。")
    return review


def _density_and_allocation(payload: VideoUnitCreate) -> tuple[float, dict[str, Any]]:
    start = payload.intended_start_state
    end = payload.intended_end_state
    changed = len({key for key in set(start) | set(end) if start.get(key) != end.get(key)})
    reference_weight = min(len(payload.references), 5) * 0.08
    handoff_weight = min(len(payload.continuity_handoff), 5) * 0.06
    score = min(1.0, round(0.2 + changed * 0.12 + reference_weight + handoff_weight, 2))
    if score < 0.4:
        level, beats = "low", 3
    elif score < 0.7:
        level, beats = "medium", 5
    else:
        level, beats = "high", 8
    primary_spend = "主体状态变化" if changed else "镜头关系与节奏"
    return score, {
        "density_level": level,
        "recommended_visual_beats": beats,
        "duration_seconds": payload.duration_seconds,
        "seconds_per_beat": round(payload.duration_seconds / beats, 2),
        "already_happened": payload.continuity_handoff.get("already_happened", []),
        "this_unit_only": payload.continuity_handoff.get(
            "this_unit_only", list(payload.intended_end_state.keys())
        ),
        "reserved_for_later": payload.continuity_handoff.get("reserved_for_later", []),
        "primary_spend": primary_spend,
        "secondary_spend": "环境动态与连续性" if payload.continuity_handoff else "构图和光线",
        "economized_elements": payload.continuity_handoff.get(
            "economized_elements", ["非关键背景变化", "无叙事作用的额外动作"]
        ),
        "split_recommendation": "建议拆分" if level == "high" and payload.duration_seconds >= 12 else "本单元可承载",
    }


def create_video_unit(
    session: Session,
    project_id: str,
    payload: VideoUnitCreate,
) -> VideoUnit:
    scene, _, project = _lineage(session, payload.scene_id, payload.shot_id)
    if project.id != project_id:
        raise HTTPException(422, "镜头不属于当前项目。")
    storyboard = None
    storyboard_ranges: list[str] = []
    if payload.storyboard_version_id:
        storyboard = session.get(StoryboardShotVersion, payload.storyboard_version_id)
        if not storyboard or storyboard.shot_id != payload.shot_id:
            raise HTTPException(422, "故事板版本与当前镜头不匹配。")
        if storyboard.status not in PRODUCTION_CONFIRMED_STATUSES:
            raise HTTPException(409, "故事板尚未确认，不能建立生产视频单元。")
        storyboard_ranges = _storyboard_time_ranges(storyboard)
        requested_ranges = [
            value for item in payload.prompt_time_ranges
            if (value := _normalize_time_range(item))
        ]
        if requested_ranges and requested_ranges != storyboard_ranges:
            raise HTTPException(422, "视频单元时间段与故事板格子时间段不一致。")
    profile = session.get(SurfaceProfile, payload.surface_profile_id) if payload.surface_profile_id else None
    if profile and payload.duration_seconds > profile.max_duration_seconds:
        raise HTTPException(422, f"当前生成服务单条最多 {profile.max_duration_seconds} 秒。")

    source_unit = None
    source_review = None
    extension_depth = 0
    start_state = payload.intended_start_state
    if payload.unit_type == "continuation":
        source_unit = session.get(VideoUnit, payload.source_video_unit_id)
        if not source_unit or source_unit.project_id != project_id:
            raise HTTPException(409, "续写缺少有效的上一视频单元。")
        source_review = _accepted_source_review(session, source_unit, payload.source_take_review_id)
        extension_depth = source_unit.extension_depth + 1
        if extension_depth > DEFAULT_MAX_EXTENSION_DEPTH:
            raise HTTPException(409, "连续扩展已超过 2 层，请用真实首帧或已确认资产重新锚定。")
        observed_end = _load(source_review.observed_end_state_json, {})
        start_state = start_state or observed_end

    density, allocation = _density_and_allocation(payload)
    unit = VideoUnit(
        project_id=project_id,
        scene_id=scene.id,
        shot_id=payload.shot_id,
        storyboard_version_id=storyboard.id if storyboard else None,
        prompt_time_ranges_json=_dump(storyboard_ranges),
        unit_index=payload.unit_index,
        unit_type=payload.unit_type,
        duration_seconds=payload.duration_seconds,
        source_video_unit_id=source_unit.id if source_unit else None,
        source_take_review_id=source_review.id if source_review else None,
        extension_depth=extension_depth,
        reanchor_required=False,
        event_density_score=density,
        allocation_json=_dump(allocation),
        intended_start_state_json=_dump(start_state),
        intended_end_state_json=_dump(payload.intended_end_state),
        continuation_handoff_json=_dump(payload.continuity_handoff),
        reference_role_map_json=_dump([item.model_dump() for item in payload.references]),
        surface_profile_id=profile.id if profile else None,
    )
    session.add(unit)
    session.flush()
    for item in payload.references:
        session.add(ReferenceRoleMap(
            video_unit_id=unit.id,
            reference_id=item.reference_id or item.local_path,
            reference_type=item.reference_type,
            role=item.role,
            intended_influence=str(item.influence),
            protected_attributes_json=_dump(item.protected_elements),
            forbidden_transfer_json=_dump(item.forbidden_transfer),
        ))
    state = project_state(session, project_id)
    state.current_scene_id = scene.id
    _set_unit_state(state, current=unit.id)
    state.updated_at = utc_now()
    session.add(state)
    session.commit()
    session.refresh(unit)
    return unit


def review_take(
    session: Session,
    video_unit_id: str,
    payload: TakeReviewCreate,
) -> TakeReview:
    unit = session.get(VideoUnit, video_unit_id)
    if not unit:
        raise HTTPException(404, "视频单元不存在。")
    if payload.status == "accepted" and not payload.observed_end_state:
        raise HTTPException(422, "通过成片前必须填写实际结束状态，供下一视频单元续接。")

    review = session.exec(
        select(TakeReview)
        .where(TakeReview.video_unit_id == unit.id)
        .where(TakeReview.review_status == "pending")
        .order_by(TakeReview.created_at.desc())
    ).first()
    if review is None:
        review = TakeReview(video_unit_id=unit.id)
    if payload.provider_run_id:
        review.provider_run_id = payload.provider_run_id
    if payload.source_video_path:
        review.source_video_path = payload.source_video_path
    review.observed_start_state_json = _dump(payload.observed_start_state)
    review.observed_end_state_json = _dump(payload.observed_end_state)
    review.review_status = payload.status
    review.rejection_reasons_json = _dump(payload.rejection_reasons)
    review.reviewer_notes = payload.review_notes
    review.updated_at = utc_now()
    session.add(review)
    unit.status = "accepted" if payload.status == "accepted" else "rejected"
    unit.updated_at = utc_now()
    session.add(unit)
    if payload.status == "accepted":
        state = project_state(session, unit.project_id)
        accepted = _load(state.accepted_take_ids_json, [])
        accepted.append(review.id)
        state.accepted_take_ids_json = _dump(list(dict.fromkeys(accepted)))
        _set_unit_state(state, current=None, completed_add=unit.id)
        state.character_state_json = _dump(payload.observed_end_state.get("characters", {}))
        state.environment_state_json = _dump(payload.observed_end_state.get("environment", {}))
        state.object_state_json = _dump(payload.observed_end_state.get("objects", {}))
        state.continuity_state_json = _dump(payload.observed_end_state)
        state.updated_at = utc_now()
        session.add(state)
    else:
        state = project_state(session, unit.project_id)
        next_current = None if state.current_video_unit_id == unit.id else state.current_video_unit_id
        _set_unit_state(state, current=next_current, rejected_remove=unit.id)
        state.updated_at = utc_now()
        session.add(state)
    session.commit()
    session.refresh(review)
    return review


def _project_file(settings: Settings, source_video_path: str) -> Path:
    candidate = Path(source_video_path).expanduser()
    if not candidate.is_absolute():
        candidate = settings.projects_root / candidate
    candidate = candidate.resolve()
    root = settings.projects_root.resolve()
    if root != candidate and root not in candidate.parents:
        raise HTTPException(422, "只能读取当前项目目录中的结果视频。")
    if not candidate.is_file():
        raise HTTPException(404, "结果视频不存在，无法提取首尾帧。")
    return candidate


def extract_boundary_frames(
    session: Session,
    settings: Settings,
    video_unit_id: str,
    source_video_path: str,
) -> dict[str, Any]:
    unit = session.get(VideoUnit, video_unit_id)
    if not unit:
        raise HTTPException(404, "视频单元不存在。")
    project = session.get(Project, unit.project_id)
    if not project:
        raise HTTPException(404, "视频单元所属项目不存在。")
    source = _project_file(settings, source_video_path)
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise HTTPException(503, "本机缺少 ffmpeg/ffprobe，暂时不能提取首尾帧。")

    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if probe.returncode != 0:
        raise HTTPException(422, "无法读取结果视频时长。")
    try:
        duration = max(float(probe.stdout.strip()), 0.05)
    except ValueError as exc:
        raise HTTPException(422, "结果视频时长格式无效。") from exc

    output_dir = settings.projects_root / project.project_code / "07_results" / "take_reviews" / unit.id
    output_dir.mkdir(parents=True, exist_ok=True)
    first_frame = output_dir / "first_frame.png"
    last_frame = output_dir / "last_frame.png"
    positions = ((0.0, first_frame), (max(duration - 0.05, 0.0), last_frame))
    for position, target in positions:
        result = subprocess.run(
            [ffmpeg, "-y", "-ss", f"{position:.3f}", "-i", str(source), "-frames:v", "1", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0 or not target.is_file():
            raise HTTPException(422, "首尾帧提取失败，请检查结果视频是否完整。")

    review = TakeReview(
        video_unit_id=unit.id,
        source_video_path=str(source),
        observed_start_frame_path=str(first_frame),
        observed_end_frame_path=str(last_frame),
        review_status="pending",
        reviewer_notes="已提取真实首尾帧，等待人工填写观察状态并验收。",
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return {
        "video_unit_id": unit.id,
        "take_review_id": review.id,
        "source_video_path": str(source),
        "first_frame_path": str(first_frame),
        "last_frame_path": str(last_frame),
        "status": "pending",
    }


def compile_unit_prompt(
    session: Session,
    video_unit_id: str,
    vp_block_id: str,
    adapter: SeedanceSkillAdapter,
    additional_constraints: list[str],
) -> dict[str, Any]:
    unit = session.get(VideoUnit, video_unit_id)
    block = session.get(VpBlock, vp_block_id)
    if not unit or not block or block.shot_id != unit.shot_id:
        raise HTTPException(422, "视频包与视频单元没有保持 1:1 镜头绑定。")
    if block.video_unit_id and block.video_unit_id != unit.id:
        raise HTTPException(409, "该视频包版本已经绑定其他视频单元，不能重复使用。")
    existing_block = session.exec(
        select(VpBlock)
        .where(VpBlock.video_unit_id == unit.id)
        .where(VpBlock.id != block.id)
    ).first()
    if existing_block:
        raise HTTPException(409, "该视频单元已经绑定其他视频包版本，不能重复绑定。")
    items = validate_vp_precision_18(_load(block.precision_json, []))
    if not block.storyboard_version_id or not unit.storyboard_version_id:
        raise HTTPException(409, "生产视频单元必须绑定已确认故事板。")
    if block.storyboard_version_id != unit.storyboard_version_id:
        raise HTTPException(409, "视频包与视频单元绑定的故事板版本不一致。")
    storyboard = session.get(StoryboardShotVersion, unit.storyboard_version_id)
    if (
        not storyboard
        or storyboard.shot_id != unit.shot_id
        or storyboard.status not in PRODUCTION_CONFIRMED_STATUSES
    ):
        raise HTTPException(409, "绑定的故事板不存在、镜头不匹配或尚未确认。")
    storyboard_ranges = _storyboard_time_ranges(storyboard)
    vp_ranges = _vp_time_ranges(items)
    unit_ranges = [
        normalized
        for value in _load(unit.prompt_time_ranges_json, [])
        if (normalized := _normalize_time_range(value))
    ]
    if not storyboard_ranges or storyboard_ranges != vp_ranges or storyboard_ranges != unit_ranges:
        raise HTTPException(409, "故事板格子时间段、视频包分时段描述与视频单元时间轴必须完全一致。")
    references = _load(unit.reference_role_map_json, [])
    profile = session.get(SurfaceProfile, unit.surface_profile_id) if unit.surface_profile_id else None
    profile_data = {
        "prompt_strategy": profile.prompt_strategy,
        "provider_type": profile.provider_type,
        "surface_name": profile.name,
        "model_id": profile.model_id,
        "prompt_budget": profile.prompt_budget,
        "reference_tag_convention": profile.reference_tag_convention,
        "supported_modes": _load(profile.supported_modes_json, []),
        "known_constraints": _load(profile.known_constraints_json, []),
    } if profile else {}
    compiled = compile_seedance_prompt(
        items,
        adapter=adapter,
        reference_roles=references,
        additional_constraints=additional_constraints,
        surface_profile=profile_data,
    )
    block.video_unit_id = unit.id
    block.vp_prompt_full = compiled["vp_prompt_full"]
    block.prompt_copy = compiled["vp_prompt_copy"]
    block.reference_tag_map_json = _dump(compiled["reference_tag_map"])
    block.preserved_constraints_json = _dump(compiled["preserved_constraints"])
    block.removed_redundancy_json = _dump(compiled["removed_redundancy"])
    block.prompt_budget_report_json = _dump(compiled["prompt_budget_report"])
    block.compile_warnings_json = _dump(compiled["compile_warnings"])
    block.updated_at = utc_now()
    session.add(block)
    session.commit()
    return compiled
