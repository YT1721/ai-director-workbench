from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.system import SystemPromptStatusResponse


DEFAULT_VERSION = (
    "V7.0 Plus R1｜UCODE-9 + FLOW-NAV + VP-PRECISION-18 + "
    "DIRECTOR-TECH PLUS + UNIFIED-SB + Seedance Skill OS"
)

LEGACY_VERSION = (
    "V7.0 Plus R1｜UCODE-9 + FLOW-NAV + VP-PRECISION-18 + "
    "DIRECTOR-TECH PLUS + UNIFIED-SB"
)


def _last_updated(prompt_file: Path) -> str | None:
    try:
        return datetime.fromtimestamp(prompt_file.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def load_system_prompt_status(
    prompt_file: Path,
    provider_mode: str,
) -> SystemPromptStatusResponse:
    try:
        content = prompt_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return SystemPromptStatusResponse(
            loaded=False,
            filename=prompt_file.name,
            version=DEFAULT_VERSION,
            provider_mode=provider_mode,
            error="系统规则主文件不存在，请检查 SYSTEM_PROMPT_FILE 配置。",
        )
    except OSError:
        return SystemPromptStatusResponse(
            loaded=False,
            filename=prompt_file.name,
            version=DEFAULT_VERSION,
            provider_mode=provider_mode,
            error="系统规则主文件无法读取，请检查文件权限。",
        )

    version_match = re.search(r"V7\.0 Plus R1", content)
    ucode_match = re.search(r"UCODE-9", content)
    flow_nav_match = re.search(r"FLOW-NAV", content)
    vp_precision_match = re.search(r"VP-PRECISION-18", content)
    director_tech_match = re.search(r"DIRECTOR-TECH", content)
    director_tech_plus_match = re.search(r"DIRECTOR-TECH PLUS|特写进连接器", content)
    unified_sb_match = re.search(r"UNIFIED-SB|统一故事板", content)
    skill_os_match = re.search(r"Seedance\s*(?:2\.0\s*)?Skill\s*OS|SeedanceSkillOS", content, re.I)
    if (
        not version_match
        or not ucode_match
        or not flow_nav_match
        or not vp_precision_match
        or not director_tech_match
        or not director_tech_plus_match
        or not unified_sb_match
    ):
        return SystemPromptStatusResponse(
            loaded=False,
            filename=prompt_file.name,
            version=DEFAULT_VERSION,
            provider_mode=provider_mode,
            last_updated=_last_updated(prompt_file),
            error=(
                "系统规则主文件缺少 V7.0 Plus R1、UCODE-9、FLOW-NAV、"
                "VP-PRECISION-18、DIRECTOR-TECH PLUS 或 UNIFIED-SB 标识。"
            ),
        )

    return SystemPromptStatusResponse(
        loaded=True,
        filename=prompt_file.name,
        version=DEFAULT_VERSION if skill_os_match else LEGACY_VERSION,
        provider_mode=provider_mode,
        last_updated=_last_updated(prompt_file),
    )
