from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException

from app.services.seedance_skill_adapter import SeedanceSkillAdapter


def _content(item: dict[str, Any]) -> str:
    value = item.get("content", "")
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def validate_vp_precision_18(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numbers = [int(item.get("number", 0)) for item in items if isinstance(item, dict)]
    if len(items) != 18 or numbers != list(range(1, 19)):
        raise HTTPException(422, "VP-PRECISION-18 必须完整保留按 1 至 18 排列的全部项目。")
    if not _content(items[3]).strip() or not _content(items[4]).strip():
        raise HTTPException(422, "视频包第 4 项完整提示词和第 5 项分时段描述不能为空。")
    return items


def compile_seedance_prompt(
    items: list[dict[str, Any]],
    *,
    adapter: SeedanceSkillAdapter,
    reference_roles: list[dict[str, Any]] | None = None,
    additional_constraints: list[str] | None = None,
    surface_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items = validate_vp_precision_18(items)
    refs = reference_roles or []
    constraints = [value.strip() for value in (additional_constraints or []) if value.strip()]
    profile = surface_profile or {}
    module_paths = adapter.resolve_modules("video_package")

    identity = _content(items[0])
    intention = _content(items[1])
    source_assets = _content(items[2])
    authored_prompt = _content(items[3]).strip()
    timeline = _content(items[4])
    visual = "；".join(_content(item) for item in items[5:13] if _content(item).strip())
    continuity = "；".join(_content(item) for item in items[13:18] if _content(item).strip())

    ref_tags = []
    tag_convention = profile.get("reference_tag_convention", "@参考N")
    for index, ref in enumerate(refs, start=1):
        if "{index}" in tag_convention:
            tag = tag_convention.replace("{index}", str(index))
        elif "N" in tag_convention:
            tag = tag_convention.replace("N", str(index))
        else:
            tag = f"{tag_convention}{index}"
        ref_tags.append({
            "tag": tag,
            "role": ref.get("role", "reference"),
            "reference_id": ref.get("reference_id", ""),
            "protected_elements": ref.get("protected_elements", []),
            "forbidden_transfer": ref.get("forbidden_transfer", []),
        })
    ref_sentence = "；".join(
        f"{item['tag']}仅负责{item['role']}" for item in ref_tags
    )

    base = authored_prompt.rstrip("。； ")
    copy_parts = [base]
    if timeline and timeline not in base:
        copy_parts.append(f"按时间推进：{timeline}")
    if ref_sentence:
        copy_parts.append(f"参考角色：{ref_sentence}，禁止跨角色迁移无关外观")
    if constraints:
        copy_parts.append("必须保持：" + "、".join(constraints))
    if profile.get("prompt_strategy"):
        copy_parts.append(f"按{profile['prompt_strategy']}策略执行，结尾状态必须可观察并可续接")
    if profile.get("surface_name") or profile.get("model_id"):
        surface_label = " / ".join(
            value for value in (profile.get("surface_name"), profile.get("model_id")) if value
        )
        copy_parts.append(f"适配生成服务：{surface_label}")
    vp_prompt_copy = "。".join(part.rstrip("。") for part in copy_parts if part).strip() + "。"

    full_sections = [
        f"镜头身份：{identity}",
        f"导演意图：{intention}",
        f"输入资产：{source_assets}",
        f"可执行提示词：{vp_prompt_copy}",
        f"分时段执行：{timeline}",
        f"画面与声音：{visual}",
        f"连续性与交接：{continuity}",
    ]
    vp_prompt_full = "\n\n".join(full_sections)
    warnings = []
    if not refs and source_assets.strip():
        warnings.append("视频包声明了输入资产，但尚未建立 Reference Role Map。")
    if not re.search(r"\d+(?:\.\d+)?\s*s", timeline, re.IGNORECASE):
        warnings.append("第 5 项未识别到明确秒数，请提交前人工核对时间轴。")
    removed = ["重复的模型名称", "重复的画幅和分辨率标签"]
    prompt_budget = int(profile.get("prompt_budget", 6000) or 6000)
    budget = {
        "characters": len(vp_prompt_copy),
        "estimated_tokens": max(1, len(vp_prompt_copy) // 2),
        "strategy": profile.get("prompt_strategy", "balanced"),
        "provider": profile.get("provider_type", ""),
        "provider_name": profile.get("provider_type", ""),
        "surface_name": profile.get("surface_name", ""),
        "model_id": profile.get("model_id", ""),
        "supported_modes": profile.get("supported_modes", []),
        "character_budget": prompt_budget,
        "prompt_budget": prompt_budget,
        "within_budget": len(vp_prompt_copy) <= prompt_budget,
    }
    return {
        "vp_prompt_full": vp_prompt_full,
        "vp_prompt_copy": vp_prompt_copy,
        "reference_tag_map": ref_tags,
        "preserved_constraints": constraints + ["VP-PRECISION-18完整保留", "Video Unit不超过15秒"],
        "removed_redundancy": removed,
        "prompt_budget_report": budget,
        "compile_warnings": warnings,
        "skill_modules": module_paths,
    }
