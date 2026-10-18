from __future__ import annotations

import json
from threading import Lock
import re
import shutil
import zipfile
from io import BytesIO
from hashlib import sha256
from html import escape
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont
from sqlmodel import Session, select

from app.config import Settings
from app.models import (
    AxisPlan,
    Episode,
    ImageGenerationJob,
    Project,
    Scene,
    Shot,
    StoryboardExecutionPage,
    StoryboardShotVersion,
    StoryboardStyleLock,
    VpBlock,
)
from app.models.workbench import utc_now
from app.providers.image import HuimengImageProvider, OpenAIImagesProvider
from app.services.image_download import download_image_with_url_refresh
from app.schemas.storyboards import (
    AxisPlanUpdate,
    AxisPlanView,
    PromptStoryboardExportView,
    StoryboardExecutionPageView,
    StoryboardImageGateItem,
    StoryboardImageJobView,
    StoryboardImagePromptView,
    StoryboardImageReadinessView,
    StoryboardReuseAssessmentView,
    StoryboardSceneView,
    StoryboardShotView,
    StoryboardVersionCreate,
    StoryboardVersionView,
    StoryboardWorkspaceView,
    StyleLockView,
)
from app.services.assets import _asset_url, _scene_with_project, _scope_code
from app.services.projects import _project_root, get_project
from app.services.video_constraints import (
    MAX_SEEDANCE_CLIP_SECONDS,
    cap_time_range_to_seedance,
)

STORYBOARD_STYLE_NAME = "统一白底高信息密度导演故事板说明板风格"
STORYBOARD_STYLE_RULE = (
    "白底/浅灰底高信息密度导演故事板说明板；镜头画面保持黑白灰写实铅笔草稿，"
    "红/蓝/绿/橙/黄/紫仅用于功能箭头与文字标注。"
)


def _next_version(values: list[int]) -> int:
    return max(values, default=0) + 1


def _json(value: str, fallback):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _ensure_style_lock(session: Session, project_id: str) -> StoryboardStyleLock:
    style_lock = session.exec(
        select(StoryboardStyleLock).where(StoryboardStyleLock.project_id == project_id)
    ).first()
    if style_lock is None:
        style_lock = StoryboardStyleLock(project_id=project_id)
        session.add(style_lock)
        session.commit()
        session.refresh(style_lock)
    elif style_lock.style_name != STORYBOARD_STYLE_NAME:
        style_lock.style_name = STORYBOARD_STYLE_NAME
        style_lock.updated_at = utc_now()
        session.add(style_lock)
        session.commit()
        session.refresh(style_lock)
    return style_lock


def _ensure_axis_plan(session: Session, scene_id: str) -> AxisPlan:
    axis_plan = session.exec(
        select(AxisPlan).where(AxisPlan.scene_id == scene_id)
    ).first()
    if axis_plan is None:
        axis_plan = AxisPlan(scene_id=scene_id)
        session.add(axis_plan)
        session.commit()
        session.refresh(axis_plan)
    return axis_plan


def _version_view(
    version: StoryboardShotVersion,
    project: Project,
    latest_image_job: ImageGenerationJob | None = None,
) -> StoryboardVersionView:
    return StoryboardVersionView(
        **version.model_dump(
            include={
                "id",
                "version_number",
                "schema_version",
                "storyboard_mode",
                "density_level",
                "vp_basis_block_id",
                "storyboard_grid",
                "grid_reason",
                "shot_size",
                "camera_angle",
                "camera_movement",
                "action_start",
                "emotion_state",
                "sound_light",
                "camera_point",
                "screen_position",
                "eyeline_direction",
                "movement_direction",
                "camera_side",
                "style_validation_status",
                "axis_validation_status",
                "axis_validation_notes",
                "status",
                "created_at",
            }
        ),
        image_url=_asset_url(project, version.image_path),
        annotation_layer=_json(version.annotation_layer, {}),
        prompt_match=_json(version.prompt_match_json or version.prompt_match, []),
        timeline_nodes=_json(version.timeline_nodes_json, []),
        storyboard_cells=_json(version.storyboard_cells_json, []),
        unified_sb_meta=_json(version.unified_sb_meta_json, {}),
        latest_image_job=_image_job_view(latest_image_job, project) if latest_image_job else None,
    )


def _is_real_storyboard(version: StoryboardShotVersion) -> bool:
    path = version.image_path.lower()
    return "真实生图" in version.grid_reason or "_sb_real_" in path or "_sb_reused_" in path


def _time_ranges(version: StoryboardShotVersion) -> list[str]:
    return [
        str(item.get("time_range", "")).strip()
        for item in _json(version.timeline_nodes_json, [])
        if str(item.get("time_range", "")).strip()
    ]


def _reuse_assessment(
    project: Project,
    current: StoryboardShotVersion | None,
    source: StoryboardShotVersion | None,
) -> StoryboardReuseAssessmentView | None:
    if current is None or source is None or _is_real_storyboard(current):
        return None
    hard_changes: list[str] = []
    review_changes: list[str] = []
    old_nodes = _json(source.timeline_nodes_json, [])
    new_nodes = _json(current.timeline_nodes_json, [])
    if source.storyboard_grid != current.storyboard_grid:
        hard_changes.append(f"故事板格数由 {source.storyboard_grid} 格变为 {current.storyboard_grid} 格")
    if len(old_nodes) != len(new_nodes):
        hard_changes.append(f"动作节点由 {len(old_nodes)} 个变为 {len(new_nodes)} 个")
    for label, field in (
        ("安全机位", "camera_side"),
        ("运动方向", "movement_direction"),
        ("人物画面位置", "screen_position"),
        ("视线方向", "eyeline_direction"),
    ):
        if getattr(source, field) != getattr(current, field):
            hard_changes.append(f"{label}发生变化")
    for label, field in (
        ("景别", "shot_size"),
        ("机位角度", "camera_angle"),
        ("运镜", "camera_movement"),
        ("摄影机位置", "camera_point"),
        ("起始动作", "action_start"),
        ("情绪状态", "emotion_state"),
    ):
        if getattr(source, field) != getattr(current, field):
            review_changes.append(f"{label}发生变化")
    old_actions = [_compact_text(item.get("description")) for item in old_nodes]
    new_actions = [_compact_text(item.get("description")) for item in new_nodes]
    if old_actions != new_actions:
        review_changes.append("动作内容发生变化")
    if hard_changes:
        recommendation = "regenerate"
        reasons = [*hard_changes, *review_changes, "画面结构已明显变化，旧图不能安全沿用"]
        can_reuse = False
    elif review_changes:
        recommendation = "review"
        reasons = [*review_changes, "格数与动作节点一致，可预览旧图后人工决定是否沿用"]
        can_reuse = True
    else:
        recommendation = "reuse"
        reasons = ["格数、动作节点、机位方向均一致，仅时间段发生调整，建议沿用旧图"]
        can_reuse = True
    return StoryboardReuseAssessmentView(
        source_version_id=source.id,
        source_version_number=source.version_number,
        source_image_url=_asset_url(project, source.image_path),
        recommendation=recommendation,
        can_reuse=can_reuse,
        reasons=reasons,
        old_grid=source.storyboard_grid,
        new_grid=current.storyboard_grid,
        old_time_ranges=_time_ranges(source),
        new_time_ranges=_time_ranges(current),
    )


def _execution_page_view(
    page: StoryboardExecutionPage,
    project: Project,
) -> StoryboardExecutionPageView:
    return StoryboardExecutionPageView(
        id=page.id,
        version_number=page.version_number,
        html_url=_asset_url(project, page.html_path),
        png_url=_asset_url(project, page.png_path),
        status=page.status,
        created_at=page.created_at,
    )


def _axis_plan_view(axis_plan: AxisPlan) -> AxisPlanView:
    return AxisPlanView(
        id=axis_plan.id,
        axis_code=axis_plan.axis_code,
        axis_line_description=axis_plan.axis_line_description,
        camera_safe_side=axis_plan.camera_safe_side,
        character_blocking=axis_plan.character_blocking,
        eyeline_direction=axis_plan.eyeline_direction,
        movement_direction=axis_plan.movement_direction,
        allow_cross_axis=axis_plan.allow_cross_axis,
        cross_axis_transition=axis_plan.cross_axis_transition,
    )


def storyboard_workspace(session: Session, project_id: str) -> StoryboardWorkspaceView:
    project = get_project(session, project_id)
    style_lock = _ensure_style_lock(session, project.id)
    episodes = list(
        session.exec(
            select(Episode)
            .where(Episode.project_id == project.id, Episode.is_archived == False)  # noqa: E712
            .order_by(Episode.episode_code)
        ).all()
    )
    scenes: list[StoryboardSceneView] = []
    for episode in episodes:
        episode_scenes = list(
            session.exec(
                select(Scene)
                .where(Scene.episode_id == episode.id, Scene.is_archived == False)  # noqa: E712
                .order_by(Scene.scene_code)
            ).all()
        )
        for scene in episode_scenes:
            axis_plan = _ensure_axis_plan(session, scene.id)
            shots = list(
                session.exec(
                    select(Shot)
                    .where(Shot.scene_id == scene.id, Shot.is_archived == False)  # noqa: E712
                    .order_by(Shot.shot_code)
                ).all()
            )
            shot_views: list[StoryboardShotView] = []
            for shot in shots:
                versions = list(
                    session.exec(
                        select(StoryboardShotVersion)
                        .where(
                            StoryboardShotVersion.shot_id == shot.id,
                            StoryboardShotVersion.schema_version.in_(["vp_precision_18_v1", "unified_sb_v1"]),
                        )
                        .order_by(StoryboardShotVersion.version_number.desc())
                    ).all()
                )
                version_jobs = {}
                if versions:
                    jobs = list(
                        session.exec(
                            select(ImageGenerationJob)
                            .where(
                                ImageGenerationJob.target_type == "storyboard_version",
                                ImageGenerationJob.target_id.in_([version.id for version in versions]),  # type: ignore[attr-defined]
                            )
                            .order_by(ImageGenerationJob.created_at.desc())
                        ).all()
                    )
                    for job in jobs:
                        version_jobs.setdefault(job.target_id, job)
                latest_vp_draft_id = next((
                    item.id
                    for item in session.exec(
                        select(VpBlock)
                        .where(VpBlock.shot_id == shot.id)
                        .order_by(VpBlock.version_number.desc())
                    ).all()
                    if item.schema_version == "vp_precision_18_v1"
                    and item.package_stage == "director_draft"
                ), None)
                current_version = next((version for version in versions if version.vp_basis_block_id == latest_vp_draft_id), None)
                stale_real_version = next((
                    version for version in versions
                    if version.vp_basis_block_id != latest_vp_draft_id and _is_real_storyboard(version)
                ), None)
                shot_views.append(
                    StoryboardShotView(
                        id=shot.id,
                        shot_code=shot.shot_code,
                        name=shot.name,
                        latest_vp_draft_id=latest_vp_draft_id,
                        versions=[_version_view(version, project, version_jobs.get(version.id)) for version in versions],
                        reuse_assessment=_reuse_assessment(project, current_version, stale_real_version),
                    )
                )
            pages = list(
                session.exec(
                    select(StoryboardExecutionPage)
                    .where(StoryboardExecutionPage.scene_id == scene.id)
                    .order_by(StoryboardExecutionPage.version_number.desc())
                ).all()
            )
            scenes.append(
                StoryboardSceneView(
                    id=scene.id,
                    scope_code=_scope_code(episode, scene),
                    name=scene.name,
                    axis_plan=_axis_plan_view(axis_plan),
                    shots=shot_views,
                    execution_pages=[_execution_page_view(page, project) for page in pages],
                )
            )
    return StoryboardWorkspaceView(
        project_id=project.id,
        project_code=project.project_code,
        style_lock=StyleLockView(
            enabled=style_lock.enabled,
            locked=style_lock.locked,
            style_name=style_lock.style_name,
        ),
        scenes=scenes,
    )


def update_axis_plan(
    session: Session,
    scene_id: str,
    payload: AxisPlanUpdate,
) -> str:
    _, _, project = _scene_with_project(session, scene_id)
    axis_plan = _ensure_axis_plan(session, scene_id)
    for key, value in payload.model_dump().items():
        setattr(axis_plan, key, value)
    axis_plan.updated_at = utc_now()
    session.add(axis_plan)
    session.commit()
    return project.id


def _latest_confirmed_version(
    session: Session,
    shot_id: str,
) -> StoryboardShotVersion | None:
    versions = list(
        session.exec(
            select(StoryboardShotVersion)
            .where(
                StoryboardShotVersion.shot_id == shot_id,
                StoryboardShotVersion.schema_version.in_(["vp_precision_18_v1", "unified_sb_v1"]),
            )
            .order_by(StoryboardShotVersion.version_number.desc())
        ).all()
    )
    return next(
        (
            version
            for version in versions
            if version.status in {"confirmed_current", "locked"}
        ),
        versions[0] if versions else None,
    )


def _axis_validation(
    session: Session,
    shot: Shot,
    axis_plan: AxisPlan,
    payload: StoryboardVersionCreate,
) -> tuple[str, str]:
    failures: list[str] = []
    if payload.camera_side != axis_plan.camera_safe_side:
        if not (axis_plan.allow_cross_axis and axis_plan.cross_axis_transition.strip()):
            failures.append("机位越过安全侧，且未登记跨轴过渡。")

    sibling_shots = list(
        session.exec(
            select(Shot)
            .where(Shot.scene_id == shot.scene_id, Shot.is_archived == False)  # noqa: E712
            .order_by(Shot.shot_code)
        ).all()
    )
    shot_index = next(
        (index for index, candidate in enumerate(sibling_shots) if candidate.id == shot.id),
        0,
    )
    if shot_index > 0:
        previous = _latest_confirmed_version(session, sibling_shots[shot_index - 1].id)
        reversed_directions = {
            ("从左向右", "从右向左"),
            ("从右向左", "从左向右"),
        }
        if previous and (previous.movement_direction, payload.movement_direction) in reversed_directions:
            if not axis_plan.cross_axis_transition.strip():
                failures.append("连续镜头运动方向反转，缺少重新建立空间或过渡说明。")

    return ("failed", "；".join(failures)) if failures else ("passed", "轴线连续性通过。")


def _write_storyboard_svg(
    projects_root: Path,
    project: Project,
    asset_path: str,
    shot: Shot,
    version_number: int,
    payload: StoryboardVersionCreate,
    grid: int,
    timeline_nodes: list[dict],
) -> None:
    target_path = _project_root(projects_root, project) / asset_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    columns = 2 if grid == 4 else 3 if grid in {6, 9} else 4
    rows = (grid + columns - 1) // columns
    gap, left, top, width, height = 10, 28, 84, 904, 414
    card_w = (width - gap * (columns - 1)) / columns
    card_h = (height - gap * (rows - 1)) / rows
    cards = []
    function_colors = ["#e11d48", "#2563eb", "#16a34a", "#f97316", "#eab308", "#9333ea"]
    for index in range(grid):
        node = timeline_nodes[min(index, len(timeline_nodes) - 1)] if timeline_nodes else {"time_range": "关键节点", "description": "等待时间轴说明"}
        x = left + (index % columns) * (card_w + gap)
        y = top + (index // columns) * (card_h + gap)
        color = function_colors[index % len(function_colors)]
        cards.append(f"""<g>
  <rect x="{x:.1f}" y="{y:.1f}" width="{card_w:.1f}" height="{card_h:.1f}" fill="#f3f1ea" stroke="#3f3f46"/>
  <path d="M{x + 18:.1f} {y + card_h - 22:.1f} L{x + card_w - 22:.1f} {y + 26:.1f}" stroke="#52525b"/>
  <ellipse cx="{x + card_w * .48:.1f}" cy="{y + card_h * .48:.1f}" rx="18" ry="24"/>
  <path d="M{x + 32:.1f} {y + card_h - 44:.1f} C{x + card_w * .42:.1f} {y + card_h - 68:.1f}, {x + card_w * .58:.1f} {y + 62:.1f}, {x + card_w - 38:.1f} {y + 38:.1f}" stroke="{color}" stroke-width="3" fill="none"/>
  <polygon points="{x + card_w - 38:.1f},{y + 38:.1f} {x + card_w - 58:.1f},{y + 35:.1f} {x + card_w - 48:.1f},{y + 52:.1f}" fill="{color}"/>
  <text x="{x + 10:.1f}" y="{y + 20:.1f}" fill="#18181b" font-size="13">{escape(str(node.get("time_range", "关键节点")))}</text>
</g>""")
    target_path.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
<defs>
  <filter id="pencil"><feTurbulence baseFrequency=".85" numOctaves="2" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="1.3"/></filter>
</defs>
<rect width="960" height="540" fill="#f7f3ea"/>
<rect x="18" y="18" width="924" height="504" fill="#fbfaf7" stroke="#27272a" stroke-width="2"/>
<g stroke="#343434" fill="none" stroke-width="2" opacity=".9" filter="url(#pencil)">{"".join(cards)}</g>
<g font-family="Arial, sans-serif">
  <text x="28" y="42" fill="#c2410c" font-size="20" letter-spacing="2">UNIFIED-SB HIGH DENSITY DIRECTOR BOARD</text>
  <text x="28" y="68" fill="#18181b" font-size="15">{escape(shot.shot_code)} · V{version_number:03d} · GRID {grid} · 白底高信息密度故事板说明板</text>
  <text x="28" y="524" fill="#27272a" font-size="15">{escape(payload.shot_size)} / {escape(payload.camera_angle)} / {escape(payload.camera_point)} / 黑白灰铅笔画面 + 功能色标注</text>
</g>
</svg>""",
        encoding="utf-8",
    )


def _precision_text(precision: list[dict], number: int, fallback: str = "") -> str:
    value = next((item.get("content") for item in precision if item.get("number") == number), "")
    if isinstance(value, list):
        parts = [
            f"{item.get('time_range', '')} {item.get('description', '')}".strip()
            for item in value
            if isinstance(item, dict)
        ]
        value = "；".join(part for part in parts if part)
    if not isinstance(value, str):
        value = str(value or "")
    return value.strip() or fallback


_TIME_SEGMENT_RE = re.compile(
    r"(?P<time>\d+(?:\.\d+)?\s*s?\s*[-–—~至到]\s*\d+(?:\.\d+)?\s*s?)\s*[：:]\s*"
    r"(?P<description>.*?)(?=(?:\d+(?:\.\d+)?\s*s?\s*[-–—~至到]\s*\d+(?:\.\d+)?\s*s?\s*[：:])|$)",
    re.S,
)


def _compact_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _timeline_nodes_from_precision(precision: list[dict], shot: Shot) -> list[dict]:
    raw = next((item.get("content") for item in precision if item.get("number") == 5), [])
    nodes: list[dict] = []

    if isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            if isinstance(item, dict):
                time_range = _compact_text(item.get("time_range") or item.get("time") or item.get("range"))
                description = _compact_text(
                    item.get("description")
                    or item.get("content")
                    or item.get("text")
                    or item.get("action")
                )
            else:
                time_range = f"关键节点 {index}"
                description = _compact_text(item)
            if time_range or description:
                nodes.append(
                    {
                        "time_range": time_range or f"关键节点 {index}",
                        "description": description or shot.name,
                    }
                )
        return nodes or [{"time_range": "关键节点", "description": shot.name}]

    text = _compact_text(raw)
    if not text:
        return [{"time_range": "关键节点", "description": shot.name}]

    for match in _TIME_SEGMENT_RE.finditer(text):
        time_range = _compact_text(match.group("time"))
        description = _compact_text(match.group("description")).strip("；;。 ")
        if time_range or description:
            nodes.append(
                {
                    "time_range": time_range or f"关键节点 {len(nodes) + 1}",
                    "description": description or shot.name,
                }
            )

    if nodes:
        return nodes

    pieces = [piece.strip("；;。 ") for piece in re.split(r"[。；;\n]+", text) if piece.strip("；;。 ")]
    if len(pieces) > 1:
        return [
            {"time_range": f"关键节点 {index}", "description": piece}
            for index, piece in enumerate(pieces[:12], start=1)
        ]
    return [{"time_range": "关键节点", "description": text}]


def _seedance_safe_timeline_nodes(nodes: list[dict], shot: Shot) -> list[dict]:
    safe_nodes: list[dict] = []
    for node in nodes:
        time_range = _compact_text(node.get("time_range"))
        capped = cap_time_range_to_seedance(time_range)
        if capped is None:
            continue
        description = _compact_text(node.get("description") or shot.name)
        if capped != time_range and description:
            description = f"{description}（原时间段超过 {MAX_SEEDANCE_CLIP_SECONDS} 秒，已按单条视频上限截到 {MAX_SEEDANCE_CLIP_SECONDS} 秒内）"
        safe_nodes.append({"time_range": capped or time_range or "关键节点", "description": description})
    return safe_nodes or [{"time_range": f"0.0s-{MAX_SEEDANCE_CLIP_SECONDS}.0s", "description": shot.name}]


def _density_level_from_nodes(timeline_nodes: list[dict], precision: list[dict]) -> str:
    text = " ".join(
        [
            *[_compact_text(node.get("description")) for node in timeline_nodes],
            _precision_text(precision, 8),
            _precision_text(precision, 10),
            _precision_text(precision, 11),
        ]
    )
    high_markers = [
        "蒙太奇",
        "爆炸",
        "烟尘",
        "能量",
        "打斗",
        "追逐",
        "多人",
        "复杂",
        "VFX",
        "特效",
        "群像",
    ]
    medium_markers = ["特写", "细节", "推近", "插入", "横移", "环绕", "变焦", "跟拍", "转场"]
    if len(timeline_nodes) >= 7 or any(marker in text for marker in high_markers):
        return "high"
    if len(timeline_nodes) >= 4 or any(marker in text for marker in medium_markers):
        return "medium"
    return "low"


def _grid_count_for_density(density_level: str, node_count: int) -> int:
    if density_level == "low":
        return 3 if node_count <= 3 else 4
    if density_level == "medium":
        return 4 if node_count <= 4 else 6
    if node_count <= 6:
        return 6
    return 9 if node_count <= 9 else 12


def _annotation_layer_for_density(density_level: str) -> dict:
    base = {
        "body_motion": "red",
        "camera_motion": "blue",
        "composition": "green",
        "light_and_focus": "orange",
        "energy_vfx_object_state": "yellow",
    }
    return {
        "enabled": density_level in {"medium", "high"},
        "rule": "白底/浅灰底高信息密度导演故事板说明板；人物和环境画面保持黑白灰铅笔草稿，彩色只用于方向、构图、光线、能量、声音情绪和物体状态标注。",
        "colors": base,
    }


def _storyboard_cells_from_nodes(
    shot: Shot,
    payload: StoryboardVersionCreate,
    timeline_nodes: list[dict],
    grid: int,
) -> list[dict]:
    cells: list[dict] = []
    for index in range(grid):
        node = timeline_nodes[min(index, len(timeline_nodes) - 1)] if timeline_nodes else {}
        description = _compact_text(node.get("description") or shot.name)
        cells.append(
            {
                "cell_index": index + 1,
                "shot_id": shot.id,
                "prompt_time_range": _compact_text(node.get("time_range") or f"关键节点 {index + 1}"),
                "action_note": description,
                "camera_note": payload.camera_movement or payload.camera_angle,
                "composition_note": payload.screen_position,
                "meaning_chain_note": payload.emotion_state,
                "vfx_note": "如有烟尘、能量或物体状态变化，仅用功能色标注；人物和环境主体仍保持黑白灰铅笔草稿。",
                "tail_frame_note": "本格尾帧应能自然衔接下一格或下一镜。",
            }
        )
    return cells


def _storyboard_payload_from_vp(
    payload: StoryboardVersionCreate,
    precision: list[dict],
) -> StoryboardVersionCreate:
    return StoryboardVersionCreate(
        shot_size=_precision_text(precision, 6, payload.shot_size),
        camera_angle=_precision_text(precision, 7, payload.camera_angle),
        camera_movement=_precision_text(precision, 8, payload.camera_movement),
        action_start=_precision_text(precision, 10, payload.action_start),
        emotion_state=_precision_text(precision, 11, payload.emotion_state),
        sound_light=_precision_text(precision, 12, payload.sound_light),
        camera_point=payload.camera_point,
        screen_position=_precision_text(precision, 9, payload.screen_position),
        eyeline_direction=payload.eyeline_direction,
        movement_direction=payload.movement_direction,
        camera_side=payload.camera_side,
    )


def create_storyboard_version(
    session: Session,
    projects_root: Path,
    shot_id: str,
    payload: StoryboardVersionCreate,
) -> str:
    shot = session.get(Shot, shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="镜头不存在。")
    scene, episode, project = _scene_with_project(session, shot.scene_id)
    axis_plan = _ensure_axis_plan(session, scene.id)
    vp_basis = next((
        item for item in session.exec(
            select(VpBlock).where(VpBlock.shot_id == shot.id).order_by(VpBlock.version_number.desc())
        ).all()
        if item.schema_version == "vp_precision_18_v1" and item.package_stage == "director_draft"
    ), None)
    if vp_basis is None:
        raise HTTPException(status_code=409, detail="请先生成 VP-PRECISION-18 导演草案，再生成绑定时间轴的故事板。")
    precision = _json(vp_basis.precision_json, [])
    payload = _storyboard_payload_from_vp(payload, precision)
    timeline_nodes = _seedance_safe_timeline_nodes(_timeline_nodes_from_precision(precision, shot), shot)
    node_count = len(timeline_nodes)
    density_level = _density_level_from_nodes(timeline_nodes, precision)
    grid = _grid_count_for_density(density_level, node_count)
    density_label = {"low": "低密度", "medium": "中密度", "high": "高密度"}[density_level]
    grid_reason = f"读取 VP-PRECISION-18 第 5 项中的 {node_count} 个分时段关键节点；判断为{density_label}镜头，整理为 {grid} 格统一故事板。"
    annotation_layer = _annotation_layer_for_density(density_level)
    storyboard_cells = _storyboard_cells_from_nodes(shot, payload, timeline_nodes, grid)
    prompt_match = [
        {
            "grid_index": index + 1,
            "time_range": timeline_nodes[min(index, node_count - 1)].get(
                "time_range",
                f"关键节点 {index + 1}",
            ),
            "vp_item_5_node": timeline_nodes[min(index, node_count - 1)].get("description", shot.name),
        }
        for index in range(grid)
    ] if timeline_nodes else []
    unified_sb_meta = {
        "storyboard_mode": "unified_sb",
        "density_level": density_level,
        "storyboard_grid_count": grid,
        "grid_reason": grid_reason,
        "axis_validation": "pending_until_saved",
        "annotation_layer": annotation_layer,
        "visual_rule": "白底/浅灰底高信息密度导演故事板说明板；镜头画面保持黑白灰写实铅笔草稿，红/蓝/绿/橙/黄/紫仅用于功能箭头与文字标注。",
    }
    values = list(
        session.exec(
            select(StoryboardShotVersion.version_number).where(
                StoryboardShotVersion.shot_id == shot.id
            )
        ).all()
    )
    number = _next_version(values)
    asset_path = (
        f"04_storyboards/frames/{_scope_code(episode, scene)}/{shot.shot_code}/"
        f"{shot.shot_code}_sb_v{number:03d}.svg"
    )
    _write_storyboard_svg(projects_root, project, asset_path, shot, number, payload, grid, timeline_nodes)
    axis_status, axis_notes = _axis_validation(session, shot, axis_plan, payload)
    version = StoryboardShotVersion(
        shot_id=shot.id,
        version_number=number,
        image_path=asset_path,
        schema_version="unified_sb_v1",
        storyboard_mode="unified_sb",
        density_level=density_level,
        vp_basis_block_id=vp_basis.id,
        storyboard_grid=grid,
        grid_reason=grid_reason,
        annotation_layer=json.dumps(annotation_layer, ensure_ascii=False),
        prompt_match=json.dumps(prompt_match, ensure_ascii=False),
        prompt_match_json=json.dumps(prompt_match, ensure_ascii=False),
        timeline_nodes_json=json.dumps(timeline_nodes, ensure_ascii=False),
        storyboard_cells_json=json.dumps(storyboard_cells, ensure_ascii=False),
        unified_sb_meta_json=json.dumps(unified_sb_meta, ensure_ascii=False),
        axis_validation_status=axis_status,
        axis_validation_notes=axis_notes,
        **payload.model_dump(),
    )
    session.add(version)
    session.commit()
    return project.id


def _storyboard_context(
    session: Session,
    version_id: str,
) -> tuple[StoryboardShotVersion, Shot, Scene, Episode, Project]:
    version = session.get(StoryboardShotVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="故事板版本不存在。")
    shot = session.get(Shot, version.shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="镜头不存在。")
    scene, episode, project = _scene_with_project(session, shot.scene_id)
    return version, shot, scene, episode, project


def _image_job_view(job: ImageGenerationJob, project: Project) -> StoryboardImageJobView:
    image_url = _asset_url(project, job.result_image_path) if job.result_image_path else None
    return StoryboardImageJobView(
        id=job.id,
        project_id=job.project_id,
        target_type=job.target_type,
        target_id=job.target_id,
        provider=job.provider,
        model_name=job.model_name,
        external_task_id=job.external_task_id,
        status=job.status,
        remote_result_url=job.remote_result_url,
        image_url=image_url,
        prompt=job.prompt,
        error_message=job.error_message,
        created_at=job.created_at,
    )


def storyboard_image_prompt_preview(
    session: Session,
    version_id: str,
) -> StoryboardImagePromptView:
    version, shot, scene, _, _ = _storyboard_context(session, version_id)
    return StoryboardImagePromptView(prompt=_storyboard_image_prompt(version, shot, scene))


def storyboard_image_readiness(
    session: Session,
    settings: Settings,
    version_id: str,
) -> StoryboardImageReadinessView:
    version, _, _, _, _ = _storyboard_context(session, version_id)
    gates = [
        StoryboardImageGateItem(
            label="已开启真实生图闸门",
            passed=settings.enable_real_image_generation,
            detail="在设置页开启“真实生图逐次确认”后才允许发起 image-2 请求。",
        ),
        StoryboardImageGateItem(
            label="生图服务 Key 已配置",
            passed=bool(settings.image_api_key),
            detail="密钥只读取本机 .env，接口不会返回密钥正文。",
        ),
        StoryboardImageGateItem(
            label="生图模型已填写",
            passed=bool(settings.image_model.strip()),
            detail=settings.image_model or "请填写要使用的生图模型 ID。",
        ),
        StoryboardImageGateItem(
            label="故事板版本可用",
            passed=version.schema_version in {"vp_precision_18_v1", "unified_sb_v1"} and version.status != "locked",
            detail="只对新版统一故事板版本发起真实生图；锁定版不会被覆盖。",
        ),
    ]
    if settings.image_provider_mode == "openai_images":
        gates.append(
            StoryboardImageGateItem(
                label="生图服务地址已填写",
                passed=bool(settings.image_base_url.strip()),
                detail=settings.image_base_url or "请填写即时生图 API 的 Base URL。",
            )
        )
    instant_mode = settings.image_provider_mode == "openai_images"
    provider_label = f"{settings.image_model}（即时 API）" if instant_mode else f"慧梦 {settings.huimengi_image_model}"
    return StoryboardImageReadinessView(
        ready=all(item.passed for item in gates),
        provider_name=provider_label,
        model_id=settings.image_model if instant_mode else settings.huimengi_image_model,
        gate_items=gates,
        risk_notice="这一步只生成当前镜头的一张故事板图片，不生成视频；提交前请人工核对生图服务的价格。",
        requires_user_confirmation=True,
    )


def _storyboard_image_prompt(
    version: StoryboardShotVersion,
    shot: Shot,
    scene: Scene,
    correction_note: str = "",
) -> str:
    timeline_nodes = _json(version.timeline_nodes_json, [])
    timeline_text = "\n".join(
        f"- {item.get('time_range', '关键节点')}：{item.get('description', '')}"
        for item in timeline_nodes[:12]
        if isinstance(item, dict)
    )
    prompt = (
        "为电影导演生成单镜头故事板图片。\n"
        "画风必须是：白底或浅灰底的高信息密度导演故事板说明板；镜头画面为黑白灰写实铅笔草稿；局部允许功能色箭头和文字标注。\n"
        "功能色规则：红色=身体运动/动作轨迹；蓝色=摄影机运动/视线引导；绿色=构图/空间关系；橙色=光线方向；黄色=能量/烟尘/物体状态变化；紫色=声音/情绪/心理提示。\n"
        "禁止：黑底故事板、深色 UI 控制台故事板、无标注纯美术图、商业海报、精修剧照、彩色人物环境主体。\n"
        f"镜头：{shot.shot_code}｜{shot.name}\n"
        f"场景：{scene.name}\n"
        f"景别：{version.shot_size}；机位：{version.camera_angle}；摄影机运动：{version.camera_movement}。\n"
        f"主体动作：{version.action_start}；情绪/状态：{version.emotion_state}；光线声音氛围：{version.sound_light}。\n"
        f"画面位置：{version.screen_position}；视线方向：{version.eyeline_direction}；运动方向：{version.movement_direction}。\n"
        f"故事板格数：{version.storyboard_grid} 格。请生成一张适合导演查看的单镜故事板总图。\n"
        f"时间段关键节点：\n{timeline_text or '按镜头动作连续性自行拆成关键画面。'}"
    )
    correction = correction_note.strip()
    if correction:
        prompt += (
            "\n\n用户本次人工修正要求（优先级高于旧图结果）：\n"
            f"{correction}\n"
            "请严格按这条修正重新生成。如果旧图里出现错误对象、错误载具、错误场景或错误动作，必须以本次修正为准。"
        )
    return prompt


def submit_storyboard_image_job(
    session: Session,
    settings: Settings,
    version_id: str,
    confirm_live_request: bool,
    correction_note: str = "",
    prompt_override: str = "",
) -> StoryboardImageJobView:
    readiness = storyboard_image_readiness(session, settings, version_id)
    if not readiness.ready:
        missing = "；".join(item.label for item in readiness.gate_items if not item.passed)
        raise HTTPException(status_code=409, detail=f"还不能真实生图：{missing}")
    if not confirm_live_request:
        raise HTTPException(status_code=409, detail="真实生图必须由你在页面逐次确认。")
    version, shot, scene, episode, project = _storyboard_context(session, version_id)
    prompt = prompt_override.strip() or _storyboard_image_prompt(version, shot, scene, correction_note)
    with _storyboard_image_submit_lock:
        active_job = session.exec(
            select(ImageGenerationJob)
            .where(
                ImageGenerationJob.target_type == "storyboard_version",
                ImageGenerationJob.target_id == version_id,
                ImageGenerationJob.status.in_(ACTIVE_IMAGE_JOB_STATUSES),
            )
            .order_by(ImageGenerationJob.created_at.desc())
        ).first()
        if active_job is not None:
            return _image_job_view(active_job, project)
        return _submit_storyboard_image_job(
            session, settings, version, shot, scene, episode, project, prompt
        )


def _submit_storyboard_image_job(
    session: Session,
    settings: Settings,
    version: StoryboardShotVersion,
    shot: Shot,
    scene: Scene,
    episode: Episode,
    project: Project,
    prompt: str,
) -> StoryboardImageJobView:
    if settings.image_provider_mode == "openai_images":
        instant = OpenAIImagesProvider()
        try:
            image_bytes, raw, request_payload = instant.generate_image(
                settings.image_base_url,
                settings.image_api_key,
                settings.image_model,
                prompt,
            )
        except Exception as cause:
            raise HTTPException(status_code=502, detail=f"图片生成失败：{cause}") from cause
        job = ImageGenerationJob(
            project_id=project.id,
            target_type="storyboard_version",
            target_id=version.id,
            provider="openai_images",
            model_name=settings.image_model,
            prompt=prompt,
            request_json=json.dumps(request_payload, ensure_ascii=False),
            response_snapshot_json=json.dumps(raw, ensure_ascii=False),
            external_task_id="",
            remote_result_url="",
            status="downloaded",
        )
        session.add(job)
        session.flush()
        _save_storyboard_image_as_new_version(
            session, settings.projects_root, project, job, version, shot, scene, episode, image_bytes
        )
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
        session.refresh(job)
        return _image_job_view(job, project)
    provider = HuimengImageProvider()
    try:
        normalized, raw, request_payload = provider.submit_task(
            settings.huimengi_image_base_url,
            settings.huimengi_api_key,
            settings.huimengi_image_model,
            prompt,
            ratio="16:9",
            quality="medium",
            resolution="2k",
        )
    except Exception as cause:  # pragma: no cover - exercised with fakes in tests
        raise HTTPException(status_code=502, detail=f"慧梦生图提交失败：{cause}") from cause
    remote_result_url = str(normalized.get("image_url") or "")
    status = str(normalized.get("status") or "submitted")
    if remote_result_url and status not in {"failed", "cancelled"}:
        status = "completed"
    job = ImageGenerationJob(
        project_id=project.id,
        target_type="storyboard_version",
        target_id=version.id,
        provider="huimeng_image",
        model_name=settings.huimengi_image_model,
        prompt=prompt,
        request_json=json.dumps(request_payload, ensure_ascii=False),
        response_snapshot_json=json.dumps(raw, ensure_ascii=False),
        external_task_id=str(normalized.get("task_id") or ""),
        remote_result_url=remote_result_url,
        status=status,
        error_message=str(normalized.get("error_message") or ""),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return _image_job_view(job, project)


def poll_storyboard_image_job(
    session: Session,
    settings: Settings,
    job_id: str,
    confirm_live_request: bool,
) -> StoryboardImageJobView:
    if not confirm_live_request:
        raise HTTPException(status_code=409, detail="查询真实生图任务也需要页面确认，避免误触发外部请求。")
    job = session.get(ImageGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="生图任务不存在。")
    project = get_project(session, job.project_id)
    if not settings.huimengi_api_key:
        raise HTTPException(status_code=409, detail="慧梦 Key 未配置。")
    if not job.external_task_id:
        raise HTTPException(status_code=409, detail="该生图任务缺少外部任务 ID，无法查询。")
    provider = HuimengImageProvider()
    try:
        normalized, raw = provider.poll_task(
            settings.huimengi_image_base_url,
            settings.huimengi_api_key,
            job.external_task_id,
        )
    except Exception as cause:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"慧梦生图查询失败：{cause}") from cause
    job.status = str(normalized.get("status") or job.status)
    job.remote_result_url = str(normalized.get("image_url") or job.remote_result_url)
    if job.remote_result_url and job.status not in {"failed", "cancelled"}:
        job.status = "completed"
    job.error_message = str(normalized.get("error_message") or "")
    job.response_snapshot_json = json.dumps(raw, ensure_ascii=False)
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return _image_job_view(job, project)


def _save_downloaded_image(image_bytes: bytes, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(image_bytes)) as image:
        image.convert("RGB").save(target_path, "PNG")


def download_storyboard_image_job(
    session: Session,
    settings: Settings,
    projects_root: Path,
    job_id: str,
    confirm_live_request: bool,
) -> StoryboardWorkspaceView:
    if not confirm_live_request:
        raise HTTPException(status_code=409, detail="下载真实生图结果必须由你在页面逐次确认。")
    job = session.get(ImageGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="生图任务不存在。")
    project = get_project(session, job.project_id)
    if job.result_image_path and (_project_root(projects_root, project) / job.result_image_path).is_file():
        if job.status != "downloaded":
            job.status = "downloaded"
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
        return storyboard_workspace(session, project.id)
    if not job.remote_result_url:
        raise HTTPException(status_code=409, detail="生图任务尚未完成，不能下载结果。")
    if job.status != "completed":
        job.status = "completed"
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
        session.refresh(job)
    version, shot, scene, episode, project = _storyboard_context(session, job.target_id)
    provider = HuimengImageProvider()
    image_bytes = download_image_with_url_refresh(session, settings, job, provider)
    _save_storyboard_image_as_new_version(
        session, projects_root, project, job, version, shot, scene, episode, image_bytes
    )
    job.status = "downloaded"
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    return storyboard_workspace(session, project.id)


def _save_storyboard_image_as_new_version(
    session: Session,
    projects_root: Path,
    project: Project,
    job: ImageGenerationJob,
    version: StoryboardShotVersion,
    shot: Shot,
    scene: Scene,
    episode: Episode,
    image_bytes: bytes,
) -> str:
    values = list(
        session.exec(
            select(StoryboardShotVersion.version_number).where(
                StoryboardShotVersion.shot_id == shot.id
            )
        ).all()
    )
    number = _next_version(values)
    asset_path = (
        f"04_storyboards/frames/{_scope_code(episode, scene)}/{shot.shot_code}/"
        f"{shot.shot_code}_sb_real_v{number:03d}.png"
    )
    _save_downloaded_image(image_bytes, _project_root(projects_root, project) / asset_path)
    new_version = StoryboardShotVersion(
        shot_id=shot.id,
        version_number=number,
        image_path=asset_path,
        schema_version=version.schema_version,
        storyboard_mode=version.storyboard_mode,
        density_level=version.density_level,
        vp_basis_block_id=version.vp_basis_block_id,
        storyboard_grid=version.storyboard_grid,
        grid_reason=f"{version.grid_reason}｜本版本由慧梦 image-2 真实生图下载生成。",
        annotation_layer=version.annotation_layer,
        prompt_match=version.prompt_match,
        prompt_match_json=version.prompt_match_json,
        timeline_nodes_json=version.timeline_nodes_json,
        storyboard_cells_json=version.storyboard_cells_json,
        unified_sb_meta_json=version.unified_sb_meta_json,
        shot_size=version.shot_size,
        camera_angle=version.camera_angle,
        camera_movement=version.camera_movement,
        action_start=version.action_start,
        emotion_state=version.emotion_state,
        sound_light=version.sound_light,
        camera_point=version.camera_point,
        screen_position=version.screen_position,
        eyeline_direction=version.eyeline_direction,
        movement_direction=version.movement_direction,
        camera_side=version.camera_side,
        style_validation_status=version.style_validation_status,
        axis_validation_status=version.axis_validation_status,
        axis_validation_notes=version.axis_validation_notes,
        status="draft",
    )
    session.add(new_version)
    job.result_image_path = asset_path
    return asset_path


def transition_storyboard_version(
    session: Session,
    version_id: str,
    action: str,
) -> str:
    version = session.get(StoryboardShotVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="故事板版本不存在。")
    shot = session.get(Shot, version.shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="镜头不存在。")
    _, _, project = _scene_with_project(session, shot.scene_id)
    if action not in {"confirm", "lock", "rollback"}:
        raise HTTPException(status_code=400, detail="不支持该版本操作。")
    if action in {"confirm", "lock"} and (
        version.style_validation_status != "passed"
        or version.axis_validation_status != "passed"
    ):
        raise HTTPException(status_code=409, detail="风格或轴线校验未通过，不能确认该版本。")
    if action == "rollback":
        if version.status == "locked":
            raise HTTPException(status_code=409, detail="锁定版本不能回退。")
        version.status = "draft"
    else:
        versions = list(
            session.exec(
                select(StoryboardShotVersion).where(
                    StoryboardShotVersion.shot_id == shot.id
                )
            ).all()
        )
        for candidate in versions:
            if candidate.id != version.id and candidate.status == "confirmed_current":
                candidate.status = "history"
                session.add(candidate)
        version.status = "locked" if action == "lock" else "confirmed_current"
    version.updated_at = utc_now()
    session.add(version)
    session.commit()
    return project.id


def reuse_storyboard_image(
    session: Session,
    projects_root: Path,
    target_version_id: str,
    source_version_id: str,
    confirm_reuse: bool,
    force_reuse: bool = False,
) -> str:
    if not confirm_reuse:
        raise HTTPException(status_code=409, detail="沿用旧图前必须由用户确认。")
    target = session.get(StoryboardShotVersion, target_version_id)
    source = session.get(StoryboardShotVersion, source_version_id)
    if target is None or source is None:
        raise HTTPException(status_code=404, detail="故事板版本不存在。")
    if target.shot_id != source.shot_id:
        raise HTTPException(status_code=409, detail="只能沿用同一镜头的历史故事板图片。")
    if target.status not in {"confirmed_current", "locked"}:
        raise HTTPException(status_code=409, detail="请先确认新版故事板的结构与时间段，再决定是否沿用旧图。")
    if not _is_real_storyboard(source):
        raise HTTPException(status_code=409, detail="历史版本不是真实故事板图片，不能沿用。")
    shot = session.get(Shot, target.shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="镜头不存在。")
    scene, episode, project = _scene_with_project(session, shot.scene_id)
    latest_vp_draft_id = next((
        item.id
        for item in session.exec(
            select(VpBlock).where(VpBlock.shot_id == shot.id).order_by(VpBlock.version_number.desc())
        ).all()
        if item.schema_version == "vp_precision_18_v1" and item.package_stage == "director_draft"
    ), None)
    if not latest_vp_draft_id or target.vp_basis_block_id != latest_vp_draft_id:
        raise HTTPException(status_code=409, detail="目标故事板不是最新分镜提示词生成的版本，请刷新后重试。")
    assessment = _reuse_assessment(project, target, source)
    if assessment is None:
        reason = "；".join(assessment.reasons) if assessment else "当前版本不需要或不能沿用旧图"
        raise HTTPException(status_code=409, detail=f"旧图不能安全沿用：{reason}。请重新生成图片。")
    if not assessment.can_reuse and not force_reuse:
        reason = "；".join(assessment.reasons)
        raise HTTPException(
            status_code=409,
            detail=f"旧图不能安全沿用：{reason}。如已人工核对画面，可明确选择强制沿用。",
        )
    existing = next((
        version for version in session.exec(
            select(StoryboardShotVersion)
            .where(StoryboardShotVersion.shot_id == shot.id)
            .order_by(StoryboardShotVersion.version_number.desc())
        ).all()
        if version.vp_basis_block_id == latest_vp_draft_id and _is_real_storyboard(version)
    ), None)
    if existing is not None:
        return project.id
    values = list(session.exec(
        select(StoryboardShotVersion.version_number).where(StoryboardShotVersion.shot_id == shot.id)
    ).all())
    number = _next_version(values)
    source_path = _project_root(projects_root, project) / source.image_path
    if not source_path.exists():
        raise HTTPException(status_code=409, detail="历史故事板图片文件不存在，不能沿用。")
    suffix = source_path.suffix.lower() or ".png"
    asset_path = (
        f"04_storyboards/frames/{_scope_code(episode, scene)}/{shot.shot_code}/"
        f"{shot.shot_code}_sb_reused_v{number:03d}{suffix}"
    )
    target_path = _project_root(projects_root, project) / asset_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)
    values = target.model_dump(exclude={"id", "version_number", "image_path", "grid_reason", "status", "created_at", "updated_at"})
    reuse_note = (
        f"用户人工确认忽略结构差异，强制沿用历史真实故事板 V{source.version_number:03d}，已重新绑定当前时间轴。"
        if force_reuse and not assessment.can_reuse
        else f"沿用历史真实故事板 V{source.version_number:03d}，已重新绑定当前时间轴。"
    )
    reused = StoryboardShotVersion(
        **values,
        version_number=number,
        image_path=asset_path,
        grid_reason=f"{target.grid_reason}｜{reuse_note}",
        status="confirmed_current",
    )
    for candidate in session.exec(
        select(StoryboardShotVersion).where(StoryboardShotVersion.shot_id == shot.id)
    ).all():
        if candidate.status == "confirmed_current":
            candidate.status = "history"
            candidate.updated_at = utc_now()
            session.add(candidate)
    session.add(reused)
    session.commit()
    return project.id


def _font(size: int):
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_execution_png(
    target_path: Path,
    scene: Scene,
    episode: Episode,
    axis_plan: AxisPlan,
    entries: list[tuple[Shot, StoryboardShotVersion]],
) -> None:
    image = Image.new("RGB", (1920, 1080), "#f7f3ea")
    draw = ImageDraw.Draw(image)
    orange, dark, gray, line = "#f97316", "#1f2937", "#6b7280", "#c7bda8"
    font_lg, font_md, font_sm = _font(34), _font(23), _font(18)
    draw.rectangle((34, 24, 1886, 1056), fill="#fffaf0", outline="#d6c8b3", width=3)
    draw.text((54, 36), "UNIFIED-SB DIRECTOR STORYBOARD SHEET", font=font_lg, fill=dark)
    draw.text((54, 82), f"{episode.episode_code}{scene.scene_code}  {scene.name}", font=font_md, fill=orange)
    draw.rectangle((54, 142, 760, 420), outline=line, width=2)
    draw.text((78, 164), "TOP-DOWN BLOCKING DIAGRAM", font=font_sm, fill=orange)
    draw.line((150, 310, 668, 220), fill=gray, width=3)
    draw.text((316, 236), f"{axis_plan.axis_code} / AXIS LINE", font=font_sm, fill=dark)
    draw.arc((178, 242, 292, 356), 0, 360, fill=dark, width=3)
    draw.arc((518, 220, 632, 334), 0, 360, fill=dark, width=3)
    draw.text((188, 362), "CAM01", font=font_sm, fill=orange)
    draw.text((522, 340), "CAM02", font=font_sm, fill=orange)
    draw.line((322, 366, 508, 366), fill="#2563eb", width=3)
    draw.polygon(((508, 366), (486, 354), (486, 378)), fill="#2563eb")
    draw.text((324, 380), axis_plan.movement_direction, font=font_sm, fill=dark)
    draw.rectangle((806, 142, 1866, 420), outline=line, width=2)
    metadata = [
        ("SCENE", f"{episode.episode_code}{scene.scene_code} / {scene.name}"),
        ("AXIS", f"{axis_plan.axis_code} · 安全机位 {axis_plan.camera_safe_side}"),
        ("BLOCKING", axis_plan.character_blocking),
        ("EYELINE", axis_plan.eyeline_direction),
        ("STYLE", STORYBOARD_STYLE_NAME),
    ]
    for index, (label, value) in enumerate(metadata):
        y = 164 + index * 47
        draw.text((834, y), label, font=font_sm, fill=orange)
        draw.text((998, y), value, font=font_sm, fill=dark)
    card_y, card_w, card_h, gap = 462, 574, 242, 20
    for index, (shot, version) in enumerate(entries[:6]):
        row, column = divmod(index, 3)
        x, y = 54 + column * (card_w + gap), card_y + row * (card_h + gap)
        draw.rectangle((x, y, x + card_w, y + card_h), outline=line, width=2)
        draw.text((x + 18, y + 16), shot.shot_code, font=font_md, fill=orange)
        draw.text((x + 164, y + 20), f"GRID {version.storyboard_grid} · {version.camera_point}", font=font_sm, fill=gray)
        draw.rectangle((x + 18, y + 64, x + card_w - 18, y + 170), fill="#e5e1d8", outline="#888")
        draw.line((x + 60, y + 154, x + card_w - 62, y + 82), fill="#444", width=3)
        draw.arc((x + 226, y + 96, x + 308, y + 160), 0, 360, fill="#444", width=3)
        draw.text((x + 18, y + 192), f"{version.camera_angle} / {version.camera_movement}", font=font_sm, fill=dark)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(target_path, "PNG")


def _checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_placeholder_storyboard_png(target_path: Path, shot: Shot, label: str) -> None:
    image = Image.new("RGB", (1280, 720), "#e5e1d8")
    draw = ImageDraw.Draw(image)
    font_lg, font_md = _font(36), _font(22)
    draw.rectangle((32, 32, 1248, 688), outline="#444", width=4)
    draw.line((120, 580, 1120, 180), fill="#555", width=5)
    draw.ellipse((470, 230, 610, 390), outline="#444", width=5)
    draw.text((70, 70), f"{shot.shot_code}｜故事板图片", font=font_lg, fill="#222")
    draw.text((70, 126), label, font=font_md, fill="#555")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(target_path, "PNG")


def _materialize_storyboard_image(root: Path, source_relative_path: str, target_path: Path, shot: Shot) -> None:
    source = root / source_relative_path
    if source.exists() and source.suffix.lower() == ".png":
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target_path)
        return
    _write_placeholder_storyboard_png(
        target_path,
        shot,
        "本地从故事板草稿物化得到；正式绘图风格以工作台预览为准。",
    )


def export_prompt_storyboard_pack(
    session: Session,
    projects_root: Path,
    scene_id: str,
) -> PromptStoryboardExportView:
    scene, episode, project = _scene_with_project(session, scene_id)
    root = _project_root(projects_root, project)
    scope = _scope_code(episode, scene)
    base_folder = root / "05_video_prompts" / "prompt_storyboard_exports"
    version_number = len(list(base_folder.glob(f"{scope}_v*"))) + 1
    relative_folder = f"05_video_prompts/prompt_storyboard_exports/{scope}_v{version_number:03d}"
    folder = root / relative_folder
    folder.mkdir(parents=True, exist_ok=True)

    shots = list(
        session.exec(
            select(Shot)
            .where(Shot.scene_id == scene.id, Shot.is_archived == False)  # noqa: E712
            .order_by(Shot.shot_code)
        ).all()
    )
    manifest: dict = {
        "project_id": project.id,
        "project_code": project.project_code,
        "scope_code": scope,
        "mode": "prompt_storyboard_export",
        "notice": "本包只导出导演级分镜提示词与对应故事板，不触发真实视频提交。",
        "shots": [],
    }
    exported_files: list[str] = []
    for shot in shots:
        storyboard = _latest_confirmed_version(session, shot.id)
        if not storyboard or storyboard.status not in {"confirmed_current", "locked"}:
            continue
        vp_block = session.get(VpBlock, storyboard.vp_basis_block_id) if storyboard.vp_basis_block_id else None
        if vp_block is None:
            vp_block = next(
                (
                    item
                    for item in session.exec(
                        select(VpBlock)
                        .where(VpBlock.shot_id == shot.id)
                        .order_by(VpBlock.version_number.desc())
                    ).all()
                    if item.schema_version == "vp_precision_18_v1"
                    and item.package_stage == "director_draft"
                ),
                None,
            )
        if vp_block is None:
            continue
        shot_dir = folder / shot.shot_code
        shot_dir.mkdir(parents=True, exist_ok=True)
        precision = _json(vp_block.precision_json, [])
        prompt = vp_block.prompt_copy or vp_block.prompt
        _materialize_storyboard_image(root, storyboard.image_path, shot_dir / "storyboard_frame.png", shot)
        if (root / storyboard.image_path).exists():
            shutil.copyfile(root / storyboard.image_path, shot_dir / f"storyboard_source{Path(storyboard.image_path).suffix}")
        director_technique = {
            "director_technique": vp_block.director_technique,
            "close_in_start_time": vp_block.close_in_start_time,
            "close_in_from_shot_size": vp_block.close_in_from_shot_size,
            "close_in_to_shot_size": vp_block.close_in_to_shot_size,
            "close_in_target_detail": vp_block.close_in_target_detail,
            "close_in_emotional_meaning": vp_block.close_in_emotional_meaning,
            "close_in_return_to_character": vp_block.close_in_return_to_character,
            "close_in_tail_frame": vp_block.close_in_tail_frame,
            "detail_shot_candidates": _json(vp_block.detail_shot_candidates_json, []),
            "selected_detail_shot": vp_block.selected_detail_shot,
            "detail_shot_time_range": vp_block.detail_shot_time_range,
            "detail_shot_meaning": vp_block.detail_shot_meaning,
            "detail_shot_relation_to_character": vp_block.detail_shot_relation_to_character,
            "montage_type": vp_block.montage_type,
            "montage_goal": vp_block.montage_goal,
            "montage_shot_count": vp_block.montage_shot_count,
            "montage_entry_point": vp_block.montage_entry_point,
            "montage_exit_point": vp_block.montage_exit_point,
            "montage_rhythm": vp_block.montage_rhythm,
            "montage_return_to_main_story": vp_block.montage_return_to_main_story,
            "symbolic_object": vp_block.symbolic_object,
            "object_state_change": vp_block.object_state_change,
            "object_state_time_range": vp_block.object_state_time_range,
            "symbolic_meaning": vp_block.symbolic_meaning,
            "relation_to_character_emotion": vp_block.relation_to_character_emotion,
        }
        storyboard_grid = {
            "storyboard_mode": storyboard.storyboard_mode,
            "density_level": storyboard.density_level,
            "storyboard_grid_count": storyboard.storyboard_grid,
            "grid_reason": storyboard.grid_reason,
            "annotation_layer": _json(storyboard.annotation_layer, {}),
            "prompt_match": _json(storyboard.prompt_match_json or storyboard.prompt_match, []),
            "timeline_nodes": _json(storyboard.timeline_nodes_json, []),
            "storyboard_cells": _json(storyboard.storyboard_cells_json, []),
        }
        unified_sb_meta = _json(storyboard.unified_sb_meta_json, {})
        (shot_dir / "video_prompt_copy.txt").write_text(prompt, encoding="utf-8")
        full_prompt = vp_block.vp_prompt_full or prompt
        (shot_dir / "video_prompt_full.txt").write_text(full_prompt, encoding="utf-8")
        (shot_dir / "vp_prompt_copy.txt").write_text(prompt, encoding="utf-8")
        (shot_dir / "vp_prompt_full.txt").write_text(full_prompt, encoding="utf-8")
        (shot_dir / "vp_precision_18.json").write_text(json.dumps(precision, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "director_technique.json").write_text(json.dumps(director_technique, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "meaning_chain.json").write_text(json.dumps(_json(vp_block.meaning_chain_json, {}), ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "storyboard_grid.json").write_text(json.dumps(storyboard_grid, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "unified_sb_meta.json").write_text(json.dumps(unified_sb_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (shot_dir / "copy_card.md").write_text(
            f"# {shot.shot_code}｜提示词 + 故事板复制卡\n\n"
            "## 什么时候用\n\n"
            "本卡适合只需要导演级分镜提示词和对应故事板的创作场景，不需要继续走批量视频。\n\n"
            "## 可复制分镜提示词\n\n"
            f"{prompt}\n\n"
            "## 对应故事板\n\n"
            "- `storyboard_frame.png`：给人看的故事板图片。\n"
            "- `vp_precision_18.json`：分镜提示词的完整导演结构。\n",
            encoding="utf-8",
        )
        file_hashes = {
            path.name: _checksum(path)
            for path in shot_dir.iterdir()
            if path.is_file()
        }
        manifest["shots"].append({
            "shot_id": shot.id,
            "shot_code": shot.shot_code,
            "shot_name": shot.name,
            "storyboard_version_id": storyboard.id,
            "vp_block_id": vp_block.id,
            "storyboard_mode": storyboard.storyboard_mode,
            "density_level": storyboard.density_level,
            "files": file_hashes,
        })
    if not manifest["shots"]:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(
            status_code=409,
            detail="还没有可导出的镜头。请先生成故事板用草案，并确认至少 1 个镜头故事板。",
        )
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_relative = f"{relative_folder}.zip"
    with zipfile.ZipFile(root / zip_relative, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(folder))
                exported_files.append(str(path.relative_to(folder)))
    return PromptStoryboardExportView(
        scene_id=scene.id,
        scope_code=scope,
        zip_url=_asset_url(project, zip_relative),
        relative_path=zip_relative,
        shot_count=len(manifest["shots"]),
        files=sorted(exported_files),
    )


def _write_execution_html(
    target_path: Path,
    scene: Scene,
    episode: Episode,
    axis_plan: AxisPlan,
    project: Project,
    entries: list[tuple[Shot, StoryboardShotVersion]],
) -> None:
    cards = "".join(
        f"""<article class="shot"><header><b>{escape(shot.shot_code)}</b><span>{escape(version.shot_size)} · {escape(version.camera_point)}</span></header>
<img src="{escape(_asset_url(project, version.image_path))}" alt="{escape(shot.shot_code)} 黑白故事板">
<p>{escape(version.camera_angle)} / {escape(version.camera_movement)}</p><small>{escape(version.emotion_state)}</small></article>"""
        for shot, version in entries
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        f"""<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f7f3ea;color:#1f2937;font:16px Arial,"PingFang SC",sans-serif}}main{{width:100%;min-height:100vh;padding:2.1%;background:#fffaf0}}h1{{margin:0;font-size:28px}}.orange{{color:#f97316}}.top{{display:grid;grid-template-columns:42% 1fr;gap:16px;margin-top:22px}}section,.shot{{border:1px solid #c7bda8;background:#fffdf8;padding:16px}}.diagram{{height:224px;position:relative}}.axis{{position:absolute;left:76px;right:60px;top:122px;border-top:2px solid #6b7280;transform:rotate(-10deg)}}.arrow{{color:#2563eb;font-size:34px;margin:46px 0 0 190px}}dl{{display:grid;grid-template-columns:130px 1fr;gap:12px;margin:0}}dt{{color:#f97316}}dd{{margin:0}}.shots{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:16px}}header{{display:flex;justify-content:space-between;color:#f97316;margin-bottom:12px}}img{{display:block;width:100%;height:190px;object-fit:cover;background:#e5e1d8;filter:grayscale(1)}}p,small{{color:#4b5563}}
</style></head><body><main><h1>UNIFIED-SB DIRECTOR STORYBOARD SHEET</h1><p class="orange">{escape(episode.episode_code + scene.scene_code)} · {escape(scene.name)}</p>
<div class="top"><section class="diagram"><b class="orange">TOP-DOWN BLOCKING DIAGRAM</b><div class="axis"></div><div class="arrow">CAM01 → CAM02</div><p>{escape(axis_plan.axis_code)} / AXIS LINE · {escape(axis_plan.movement_direction)}</p></section>
<section><dl><dt>SCENE</dt><dd>{escape(scene.name)}</dd><dt>SAFE SIDE</dt><dd>{escape(axis_plan.camera_safe_side)}</dd><dt>BLOCKING</dt><dd>{escape(axis_plan.character_blocking)}</dd><dt>EYELINE</dt><dd>{escape(axis_plan.eyeline_direction)}</dd><dt>STYLE</dt><dd>{escape(STORYBOARD_STYLE_NAME)}</dd></dl></section></div>
<div class="shots">{cards}</div></main></body></html>""",
        encoding="utf-8",
    )


def create_execution_page(
    session: Session,
    projects_root: Path,
    scene_id: str,
) -> str:
    scene, episode, project = _scene_with_project(session, scene_id)
    axis_plan = _ensure_axis_plan(session, scene.id)
    shots = list(
        session.exec(
            select(Shot)
            .where(Shot.scene_id == scene.id, Shot.is_archived == False)  # noqa: E712
            .order_by(Shot.shot_code)
        ).all()
    )
    entries: list[tuple[Shot, StoryboardShotVersion]] = []
    for shot in shots:
        version = _latest_confirmed_version(session, shot.id)
        if (
            version
            and version.status in {"confirmed_current", "locked"}
            and version.style_validation_status == "passed"
            and version.axis_validation_status == "passed"
        ):
            entries.append((shot, version))
    if not entries:
        raise HTTPException(status_code=409, detail="请先准备至少 1 个已确认且校验通过的新版网格故事板镜头。")
    values = list(
        session.exec(
            select(StoryboardExecutionPage.version_number).where(
                StoryboardExecutionPage.scene_id == scene.id
            )
        ).all()
    )
    number = _next_version(values)
    base = f"04_storyboards/pages/{_scope_code(episode, scene)}/execution_page_v{number:03d}"
    html_path, png_path = f"{base}.html", f"{base}.png"
    root = _project_root(projects_root, project)
    _write_execution_html(root / html_path, scene, episode, axis_plan, project, entries)
    _draw_execution_png(root / png_path, scene, episode, axis_plan, entries)
    session.add(
        StoryboardExecutionPage(
            scene_id=scene.id,
            version_number=number,
            html_path=html_path,
            png_path=png_path,
        )
    )
    session.commit()
    return project.id
_storyboard_image_submit_lock = Lock()
ACTIVE_IMAGE_JOB_STATUSES = ("submitted", "processing", "completed")
