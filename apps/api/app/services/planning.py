from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    Episode,
    PlanningDraft,
    PlanningDraftItem,
    Project,
    Scene,
    Shot,
    SourceFile,
    SourceTextExtraction,
)
from app.models.workbench import utc_now
from app.schemas.planning import PlanningDraftItemView, PlanningDraftView
from app.schemas.workflows import AiTextRunCreate
from app.services.projects import _next_code, get_project


EXTRACTABLE_CATEGORIES = {"script", "script_text", "storyboard_table"}
EXTRACTABLE_SUFFIXES = {".txt", ".md", ".docx", ".xlsx"}
SCENE_RE = re.compile(r"(?:第\s*([一二三四五六七八九十百\d]+)\s*场|SC\s*0*(\d+))", re.I)
SHOT_RE = re.compile(r"(?:镜头\s*([一二三四五六七八九十百\d]+)|SH\s*0*(\d+))", re.I)
EPISODE_MARK_RE = re.compile(r"^第\s*([一二三四五六七八九十百\d]+)\s*集\s*$")
SHORT_DRAMA_MARK_RE = re.compile(r"^\s*(\d+)\s*[-－]\s*(\d+)[,，、.\s]*(.*)$")
VISUAL_LINE_RE = re.compile(r"^(?:△|▲|画面|镜头|【|旁白|VO|Vo|vo|OS|os|[\u4e00-\u9fff]{1,8}[（(].*[）)][:：]|[\u4e00-\u9fff]{1,8}[:：])")
DEFAULT_PLANNING_DRAFT_ITEMS = 120


def _json(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _project_root(projects_root: Path, project: Project) -> Path:
    return projects_root / project.project_code


def _to_int(value: str | None, default: int) -> int:
    if not value:
        return default
    if value.isdigit():
        return int(value)
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if value in mapping:
        return mapping[value]
    if value.startswith("十") and len(value) == 2:
        return 10 + mapping.get(value[1], 0)
    if value.endswith("十") and len(value) == 2:
        return mapping.get(value[0], 1) * 10
    if "十" in value:
        left, right = value.split("十", 1)
        return mapping.get(left, 1) * 10 + mapping.get(right, 0)
    return default


def _read_source_text(projects_root: Path, project: Project, source: SourceFile) -> tuple[str | None, str]:
    suffix = Path(source.original_filename).suffix.lower() or Path(source.relative_path).suffix.lower()
    if source.category not in EXTRACTABLE_CATEGORIES or suffix not in EXTRACTABLE_SUFFIXES:
        return None, "已保存，暂未解析正文。本轮只解析粘贴文本、TXT、MD、DOCX 和 XLSX。"
    path = _project_root(projects_root, project) / source.relative_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="源文件不存在。")
    if suffix == ".docx":
        return _read_docx_text(path), ""
    if suffix == ".xlsx":
        return _read_xlsx_text(path), ""
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding).strip(), ""
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore").strip(), ""


def _read_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as cause:
        raise HTTPException(status_code=400, detail="DOCX 文件结构无效，无法提取正文。") from cause
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as cause:
        raise HTTPException(status_code=400, detail="DOCX 正文 XML 无法解析。") from cause
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{namespace['w']}}}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{{{namespace['w']}}}tab":
                parts.append("\t")
            elif node.tag == f"{{{namespace['w']}}}br":
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs).strip()


def _read_xlsx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = _read_xlsx_shared_strings(archive)
            sheet_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            )
            rows: list[str] = []
            for sheet_name in sheet_names:
                rows.extend(_read_xlsx_sheet_rows(archive.read(sheet_name), shared_strings))
    except (KeyError, zipfile.BadZipFile) as cause:
        raise HTTPException(status_code=400, detail="XLSX 文件结构无效，无法提取正文。") from cause
    except ET.ParseError as cause:
        raise HTTPException(status_code=400, detail="XLSX 工作表 XML 无法解析。") from cause
    return "\n".join(rows).strip()


def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(".//s:si", namespace):
        text = "".join(node.text or "" for node in item.findall(".//s:t", namespace)).strip()
        strings.append(text)
    return strings


def _read_xlsx_sheet_rows(sheet_xml: bytes, shared_strings: list[str]) -> list[str]:
    namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(sheet_xml)
    rows: list[str] = []
    for row in root.findall(".//s:sheetData/s:row", namespace):
        cells: list[str] = []
        for cell in row.findall("s:c", namespace):
            value = _read_xlsx_cell_text(cell, shared_strings, namespace)
            if value:
                cells.append(value)
        if cells:
            rows.append(" | ".join(cells))
    return rows


def _read_xlsx_cell_text(cell: ET.Element, shared_strings: list[str], namespace: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//s:is//s:t", namespace)).strip()
    value_node = cell.find("s:v", namespace)
    raw_value = (value_node.text if value_node is not None else "") or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)].strip()
        except (ValueError, IndexError):
            return ""
    if raw_value:
        return raw_value.strip()
    return "".join(node.text or "" for node in cell.findall(".//s:t", namespace)).strip()


def _latest_extraction(session: Session, project_id: str) -> SourceTextExtraction | None:
    return session.exec(
        select(SourceTextExtraction)
        .where(SourceTextExtraction.project_id == project_id)
        .order_by(SourceTextExtraction.created_at.desc())
    ).first()


def extract_source_text(
    session: Session,
    projects_root: Path,
    source_file_id: str,
) -> SourceTextExtraction:
    source = session.get(SourceFile, source_file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="素材不存在。")
    project = get_project(session, source.project_id)
    existing_versions = session.exec(
        select(SourceTextExtraction.version_number).where(SourceTextExtraction.source_file_id == source.id)
    ).all()
    version_number = max(existing_versions, default=0) + 1
    text, unsupported_reason = _read_source_text(projects_root, project, source)
    root = _project_root(projects_root, project)

    if text is None:
        extraction = SourceTextExtraction(
            project_id=project.id,
            source_file_id=source.id,
            version_number=version_number,
            status="unsupported",
            preview="",
            error=unsupported_reason,
        )
    else:
        target_folder = root / "01_analysis" / "source_extractions"
        target_folder.mkdir(parents=True, exist_ok=True)
        target_path = target_folder / f"{source.id}_{version_number:03d}.txt"
        target_path.write_text(text, encoding="utf-8")
        extraction = SourceTextExtraction(
            project_id=project.id,
            source_file_id=source.id,
            version_number=version_number,
            status="extracted",
            text_relative_path=str(target_path.relative_to(root)),
            character_count=len(text),
            line_count=len([line for line in text.splitlines() if line.strip()]),
            preview=text[:360],
            error="",
        )
    session.add(extraction)
    session.commit()
    session.refresh(extraction)
    return extraction


def list_extractions(session: Session, project_id: str) -> list[SourceTextExtraction]:
    get_project(session, project_id)
    return list(session.exec(
        select(SourceTextExtraction)
        .where(SourceTextExtraction.project_id == project_id)
        .order_by(SourceTextExtraction.created_at.desc())
    ).all())


def read_extraction_text(projects_root: Path, project: Project, extraction: SourceTextExtraction) -> str:
    if extraction.status != "extracted" or not extraction.text_relative_path:
        return ""
    path = _project_root(projects_root, project) / extraction.text_relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _source_segments(text: str, max_items: int) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    items: list[dict[str, str]] = []
    current_scene = 0
    shot_index_by_scene: dict[int, int] = {}
    saw_structure = False
    for raw in lines:
        episode_match = EPISODE_MARK_RE.match(raw)
        if episode_match:
            current_scene = _to_int(episode_match.group(1), max(current_scene + 1, 1))
            shot_index_by_scene.setdefault(current_scene, 0)
            saw_structure = True
            continue
        short_drama_match = SHORT_DRAMA_MARK_RE.match(raw)
        if short_drama_match:
            current_scene = int(short_drama_match.group(1))
            shot_index_by_scene.setdefault(current_scene, 0)
            shot_number = int(short_drama_match.group(2))
            excerpt = (short_drama_match.group(3) or raw).strip()[:220]
            shot_index_by_scene[current_scene] = max(shot_index_by_scene[current_scene], shot_number)
            items.append({
                "episode_code": "EP01",
                "scene_code": f"SC{current_scene:02d}",
                "shot_code": f"SH{shot_number:03d}",
                "source_excerpt": excerpt,
                "suggested_task": _suggest_task(excerpt),
            })
            saw_structure = True
            if len(items) >= max_items:
                break
            continue
        scene_match = SCENE_RE.search(raw)
        if scene_match:
            current_scene = _to_int(scene_match.group(1) or scene_match.group(2), current_scene)
            shot_index_by_scene.setdefault(current_scene, 0)
            saw_structure = True
            continue
        if current_scene <= 0:
            continue
        if raw.startswith("人物："):
            continue
        if not VISUAL_LINE_RE.search(raw) and len(raw) < 8:
            continue
        shot_match = SHOT_RE.search(raw)
        shot_index_by_scene.setdefault(current_scene, 0)
        if shot_match:
            shot_number = _to_int(shot_match.group(1) or shot_match.group(2), shot_index_by_scene[current_scene] + 1)
        else:
            shot_number = shot_index_by_scene[current_scene] + 1
        shot_index_by_scene[current_scene] = max(shot_index_by_scene[current_scene], shot_number)
        excerpt = raw[:220]
        items.append({
            "episode_code": "EP01",
            "scene_code": f"SC{current_scene:02d}",
            "shot_code": f"SH{shot_number:03d}",
            "source_excerpt": excerpt,
            "suggested_task": _suggest_task(excerpt),
        })
        if len(items) >= max_items:
            break
    if not items and not saw_structure:
        paragraph_fallback = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        for index, raw in enumerate(paragraph_fallback or lines[:max_items]):
            items.append({
                "episode_code": "EP01",
                "scene_code": "SC01",
                "shot_code": f"SH{index + 1:03d}",
                "source_excerpt": raw[:220],
                "suggested_task": _suggest_task(raw[:220]),
            })
            if len(items) >= max_items:
                break
    return items


def _suggest_task(excerpt: str) -> str:
    cleaned = re.sub(r"^(?:第\s*[一二三四五六七八九十百\d]+\s*场|SC\s*\d+|镜头\s*[一二三四五六七八九十百\d]+|SH\s*\d+)[:：\s-]*", "", excerpt, flags=re.I).strip()
    if not cleaned:
        cleaned = excerpt.strip()
    return f"根据原文设计镜头：{cleaned[:80]}"


def create_ai_planning_draft(
    session: Session,
    settings,
    project_id: str,
    payload: AiTextRunCreate,
) -> PlanningDraft:
    from app.services.ai_text import run_project_ai_text

    payload.module_type = "planning_draft"
    run = run_project_ai_text(session, settings, project_id, payload)
    project = get_project(session, project_id)
    extraction = session.get(SourceTextExtraction, payload.source_extraction_id) if payload.source_extraction_id else _latest_extraction(session, project.id)
    if extraction is None or extraction.status != "extracted":
        raise HTTPException(status_code=400, detail="请先提取可解析文本，再生成 AI 规划草案。")
    items = _items_from_ai_json(run.response_text, DEFAULT_PLANNING_DRAFT_ITEMS)
    if not items:
        raise HTTPException(
            status_code=422,
            detail=(
                "真实 AI 规划草案缺少可应用的 planning_items JSON。"
                "系统不会用本地规则兜底生成草案；请点击重新生成，或在补充要求中要求模型严格输出 planning_items。"
            ),
        )
    if len(items) == 1 and extraction.character_count > 800:
        raise HTTPException(
            status_code=422,
            detail=(
                "AI 只返回了 1 个镜头，但当前资料较长，不符合“按全文拆分分镜”的要求。"
                "请重新生成分镜规划；系统会要求 AI 一次性输出当前文本内所有场和镜头。"
            ),
        )
    existing_versions = session.exec(
        select(PlanningDraft.version_number).where(PlanningDraft.project_id == project.id)
    ).all()
    draft = PlanningDraft(
        project_id=project.id,
        source_extraction_id=extraction.id,
        version_number=max(existing_versions, default=0) + 1,
        status="draft",
        summary="",
        draft_json="{}",
    )
    session.add(draft)
    session.flush()
    for item in items:
        session.add(PlanningDraftItem(draft_id=draft.id, project_id=project.id, **item))
    draft.summary = (
        f"文本模型已生成规划建议（{run.provider}｜{run.model_name}）。"
        "为保护项目结构，本草案仍需人工审阅后点击应用。"
    )
    draft.draft_json = json.dumps({
        **_json(draft.draft_json, {}),
        "ai_text_run_id": run.id,
        "ai_provider": run.provider,
        "ai_model": run.model_name,
        "ai_cache_hit": run.cache_hit,
    }, ensure_ascii=False)
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


def _items_from_ai_response(text: str, max_items: int) -> list[dict[str, str]]:
    json_items = _items_from_ai_json(text, max_items)
    if json_items:
        return json_items
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"(EP\s*0*(\d+))\s*[｜|\s,，/]+(SC\s*0*(\d+))\s*[｜|\s,，/]+(SH\s*0*(\d+))\s*[｜|:：\s-]*(.*)",
        re.I,
    )
    for raw in [line.strip() for line in text.splitlines() if line.strip()]:
        match = pattern.search(raw)
        if not match:
            continue
        tail = match.group(7).strip()
        parts = re.split(r"[｜|]", tail)
        excerpt = (parts[0] if parts else tail).strip()[:220]
        task = (parts[-1] if len(parts) > 1 else _suggest_task(excerpt)).strip()
        rows.append({
            "episode_code": f"EP{int(match.group(2)):02d}",
            "scene_code": f"SC{int(match.group(4)):02d}",
            "shot_code": f"SH{int(match.group(6)):03d}",
            "source_excerpt": excerpt or raw[:220],
            "suggested_task": task[:220] or _suggest_task(raw[:220]),
        })
        if len(rows) >= max_items:
            break
    return rows


def _items_from_ai_json(text: str, max_items: int) -> list[dict[str, str]]:
    candidates: list[str] = []
    candidates.extend(match.group(1) for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I))
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(text[first_brace:last_brace + 1])
    for candidate in candidates:
        payload = _json(candidate, None)
        if not isinstance(payload, dict):
            continue
        raw_items = payload.get("planning_items") or payload.get("items") or []
        if not isinstance(raw_items, list):
            continue
        rows: list[dict[str, str]] = []
        for index, raw in enumerate(raw_items[:max_items]):
            if not isinstance(raw, dict):
                continue
            episode = str(raw.get("episode_code") or "EP01").upper().replace(" ", "")
            scene = str(raw.get("scene_code") or f"SC{index + 1:02d}").upper().replace(" ", "")
            shot = str(raw.get("shot_code") or f"SH{index + 1:03d}").upper().replace(" ", "")
            episode_match = re.search(r"(\d+)", episode)
            scene_match = re.search(r"(\d+)", scene)
            shot_match = re.search(r"(\d+)", shot)
            excerpt = str(raw.get("source_excerpt") or raw.get("excerpt") or raw.get("原文依据") or "").strip()[:220]
            task = str(raw.get("suggested_task") or raw.get("task") or raw.get("镜头任务") or "").strip()[:220]
            if not excerpt and not task:
                continue
            rows.append({
                "episode_code": f"EP{int(episode_match.group(1)) if episode_match else 1:02d}",
                "scene_code": f"SC{int(scene_match.group(1)) if scene_match else index + 1:02d}",
                "shot_code": f"SH{int(shot_match.group(1)) if shot_match else index + 1:03d}",
                "source_excerpt": excerpt or task,
                "suggested_task": task or _suggest_task(excerpt),
            })
        if rows:
            return rows
    return []


def list_planning_drafts(session: Session, project_id: str) -> list[PlanningDraftView]:
    get_project(session, project_id)
    drafts = session.exec(
        select(PlanningDraft)
        .where(PlanningDraft.project_id == project_id)
        .order_by(PlanningDraft.created_at.desc())
    ).all()
    return [planning_draft_view(session, draft) for draft in drafts]


def _default_structure(session: Session, project_id: str) -> bool:
    episodes = session.exec(select(Episode).where(Episode.project_id == project_id)).all()
    if len(episodes) != 1 or episodes[0].episode_code != "EP01":
        return False
    scenes = session.exec(select(Scene).where(Scene.episode_id == episodes[0].id)).all()
    if len(scenes) != 1 or scenes[0].scene_code != "SC01":
        return False
    shots = session.exec(select(Shot).where(Shot.scene_id == scenes[0].id)).all()
    return len(shots) == 1 and shots[0].shot_code == "SH001"


def apply_planning_draft(session: Session, draft_id: str) -> PlanningDraft:
    draft = session.get(PlanningDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="规划草案不存在。")
    project = get_project(session, draft.project_id)
    if not _default_structure(session, project.id):
        draft.status = "saved_not_applied"
        draft.updated_at = utc_now()
        session.add(draft)
        session.commit()
        session.refresh(draft)
        raise HTTPException(status_code=409, detail="当前项目结构已被修改，规划草案已保存但不会自动覆盖。")

    items = session.exec(
        select(PlanningDraftItem).where(PlanningDraftItem.draft_id == draft.id).order_by(PlanningDraftItem.scene_code, PlanningDraftItem.shot_code)
    ).all()
    episode = session.exec(select(Episode).where(Episode.project_id == project.id, Episode.episode_code == "EP01")).first()
    scenes_by_code: dict[str, Scene] = {}
    for item in items:
        scene = scenes_by_code.get(item.scene_code)
        if scene is None:
            scene = session.exec(select(Scene).where(Scene.episode_id == episode.id, Scene.scene_code == item.scene_code)).first()
            if scene is None:
                scene = Scene(episode_id=episode.id, scene_code=item.scene_code, name=f"第 {int(item.scene_code[2:])} 场")
                session.add(scene)
                session.flush()
            else:
                scene.name = f"第 {int(item.scene_code[2:])} 场"
            scenes_by_code[item.scene_code] = scene
        shot = session.exec(select(Shot).where(Shot.scene_id == scene.id, Shot.shot_code == item.shot_code)).first()
        if shot is None:
            shot = Shot(scene_id=scene.id, shot_code=item.shot_code, name=f"镜头 {int(item.shot_code[2:])}")
        shot.name = item.suggested_task[:120] or f"镜头 {int(item.shot_code[2:])}"
        shot.updated_at = utc_now()
        item.status = "applied"
        item.updated_at = utc_now()
        session.add(shot)
        session.add(item)

    draft.status = "applied"
    draft.applied_at = utc_now()
    draft.updated_at = utc_now()
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


def planning_draft_view(session: Session, draft: PlanningDraft) -> PlanningDraftView:
    items = session.exec(
        select(PlanningDraftItem)
        .where(PlanningDraftItem.draft_id == draft.id)
        .order_by(PlanningDraftItem.scene_code, PlanningDraftItem.shot_code)
    ).all()
    return PlanningDraftView(
        **draft.model_dump(),
        items=[PlanningDraftItemView.model_validate(item, from_attributes=True) for item in items],
    )
