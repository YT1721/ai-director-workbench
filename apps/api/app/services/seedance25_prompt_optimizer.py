from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any


RULE_ID = "sd25-pe-compatible"
RULE_VERSION = "builtin-v1"
SECTION_ORDER = (
    "主体",
    "动作 / 事件",
    "场景与环境",
    "视觉风格",
    "运镜 / 切镜",
    "声音",
)

PURPOSE_LABELS = {
    "subject": "主体身份",
    "product": "产品外观",
    "environment": "场景环境",
    "action": "动作",
    "camera": "运镜",
    "rhythm": "节奏",
    "style": "视觉风格",
    "sound": "声音",
}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value in (None, [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False)


def _summary(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    match = re.search(r"结论[：:]\s*(.+?)(?:。?可执行清单[：:]|$)", text)
    return (match.group(1) if match else text).strip("。； ")


def _precision_map(items: list[dict[str, Any]] | None) -> dict[int, str]:
    return {
        int(item.get("number", 0)): _summary(item.get("content"))
        for item in (items or [])
        if isinstance(item, dict) and str(item.get("number", "")).isdigit()
    }


def _raw_precision_map(items: list[dict[str, Any]] | None) -> dict[int, str]:
    return {
        int(item.get("number", 0)): _text(item.get("content"))
        for item in (items or [])
        if isinstance(item, dict) and str(item.get("number", "")).isdigit()
    }


def _join(values: list[str]) -> str:
    return "；".join(dict.fromkeys(value for value in values if value))


def _format_sound(summary: str, raw: str) -> str:
    parts: list[str] = []
    if summary:
        parts.append(f"<音效与环境声：{summary}>")

    music = re.search(r"音乐(?:使用|采用|为|只用|保持)?[：:]?\s*([^。；]+)", raw)
    if music:
        parts.append(f"(音乐：{music.group(1).strip()})")

    for dialogue in re.findall(r"(?:台词|对白|旁白)[^：“\"]*[：:]?[“\"]([^”\"]+)[”\"]", raw):
        parts.append(f"{{台词：{dialogue.strip()}}}")

    subtitle = re.search(r"字幕(?:内容)?[：:]\s*([^。；]+)", raw)
    if subtitle and not re.search(r"不(?:要|使用|需要|添加)|禁止", subtitle.group(1)):
        parts.append(f"【字幕：{subtitle.group(1).strip()}】")
    return "；".join(parts) or "沿用导演原始执行文本，不补写未确认声音"


def build_structured_sections(
    precision_items: list[dict[str, Any]] | None,
    previous_sections: dict[str, Any] | None = None,
) -> dict[str, str]:
    items = _precision_map(precision_items)
    raw_items = _raw_precision_map(precision_items)
    previous = previous_sections or {}
    sections = {
        "主体": items.get(10, ""),
        "动作 / 事件": items.get(2, ""),
        "场景与环境": _join([items.get(11, ""), items.get(12, "")]),
        "视觉风格": items.get(12, ""),
        "运镜 / 切镜": _join([items.get(6, ""), items.get(7, ""), items.get(8, "")]),
        "声音": _format_sound(items.get(13, ""), raw_items.get(13, "")),
    }
    return {
        name: value or _text(previous.get(name)) or "沿用导演原始执行文本，不补写未确认内容"
        for name, value in sections.items()
    }


def optimize_seedance25_prompt(
    source_prompt: str,
    bindings: list[dict[str, Any]],
    *,
    precision_items: list[dict[str, Any]] | None = None,
    previous_sections: dict[str, Any] | None = None,
    enabled: bool = True,
) -> tuple[str, dict[str, Any]]:
    source = source_prompt.strip()
    sections = build_structured_sections(precision_items, previous_sections)
    reference_lines = ["【全能参考素材职责】"]
    for binding in bindings:
        token = str(binding.get("token") or "").strip()
        if not token:
            continue
        purpose = str(binding.get("purpose") or "").strip()
        purpose_label = PURPOSE_LABELS.get(purpose, purpose or "指定参考")
        reference_lines.append(
            f"{token}：用于{purpose_label}；"
            f"必须保持{binding.get('must_preserve') or binding.get('label') or '已确认特征'}；"
            f"不得迁移{binding.get('must_not_transfer') or '未指定的背景、文字、构图、身份或风格'}。"
        )
    if len(reference_lines) > 1:
        reference_lines.append("每个 @素材仅承担上述职责，不得互换用途或自行推断未声明用途。")
    else:
        reference_lines = []

    if enabled:
        section_lines = ["【Seedance 2.5 执行结构】"]
        for name in SECTION_ORDER:
            value = sections[name]
            section_lines.append(f"{name}：{value}")
        detail_lines = ["【导演原始执行细节｜完整保留】", source]
        prompt = "\n".join(reference_lines + section_lines + detail_lines).strip()
    else:
        prompt = "\n".join(reference_lines + (["【镜头执行】", source] if source else [])).strip()

    warnings: list[str] = []
    if not source:
        warnings.append("原始提示词为空，不能自动优化。")
    if bindings and any(str(item.get("token") or "") not in prompt for item in bindings):
        warnings.append("存在未写入最终提示词的 @参考素材。")
    if enabled and not precision_items and not previous_sections:
        warnings.append("缺少 VP-PRECISION-18 结构，只保留原文并使用保守占位，不补写导演内容。")

    report = {
        "enabled": enabled,
        "mode": "deterministic_local_compiler",
        "rule_id": RULE_ID,
        "rule_version": RULE_VERSION,
        "rule_source": "火山引擎公开提示词规则截图的项目内置实现",
        "official_skill_package_installed": False,
        "section_order": list(SECTION_ORDER),
        "structured_sections": sections,
        "source_prompt_sha256": sha256(source.encode("utf-8")).hexdigest(),
        "optimized_prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
        "warnings": warnings,
    }
    return prompt, report
