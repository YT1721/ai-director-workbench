from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PINNED_SEEDANCE_COMMIT = "57d01dc66f93ecb03c2475be5f22dc416d9b701d"


MODULES: dict[str, tuple[str, ...]] = {
    "start": (
        "references/directing-engine.md",
        "skills/seedance-interview-short/SKILL.md",
    ),
    "plan": (
        "skills/seedance-sequence/SKILL.md",
        "references/sequence-project-state.md",
        "references/event-density.md",
        "references/allocation-model.md",
        "references/shot-list-continuity.md",
    ),
    "assets": (
        "skills/seedance-characters/SKILL.md",
        "references/reference-workflow.md",
        "references/reference-transfer-contract.md",
    ),
    "storyboard": (
        "references/dense-storyboard-mode.md",
        "references/multishot-grammar.md",
        "references/cinematography-shot-language.md",
    ),
    "video_package": (
        "skills/seedance-prompt/SKILL.md",
        "skills/seedance-prompt-short/SKILL.md",
        "skills/seedance-camera/SKILL.md",
        "skills/seedance-motion/SKILL.md",
        "skills/seedance-lighting/SKILL.md",
        "skills/seedance-characters/SKILL.md",
        "skills/seedance-style/SKILL.md",
        "skills/seedance-vfx/SKILL.md",
        "skills/seedance-audio/SKILL.md",
        "references/prompt-compiler.md",
        "references/surface-prompt-profiles.md",
        "references/anti-slop-lexicon.md",
    ),
    "check": (
        "references/retake-protocol.md",
        "references/continuity-qc.md",
        "references/sequence-project-state.md",
    ),
    "fix": (
        "skills/seedance-troubleshoot/SKILL.md",
        "references/failure-atlas.md",
        "references/model-mechanics.md",
        "references/retake-protocol.md",
    ),
}


@dataclass(frozen=True)
class LoadedSkillModule:
    path: str
    sha256: str
    content: str


class SeedanceSkillAdapter:
    """Loads only the Seedance modules needed by the current UCODE action."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.vendor_root = (self.repo_root / "vendor" / "seedance-20").resolve()

    def resolve_modules(self, action: str, context: dict[str, Any] | None = None) -> list[str]:
        modules = list(MODULES.get(action, ()))
        context = context or {}
        if context.get("continuation"):
            modules.append("references/continuation-handoff.md")
        if context.get("first_last_frame"):
            modules.append("references/first-last-frame-guide.md")
        if context.get("professional_delivery"):
            modules.append("references/pro-filmmaking-standards.md")
        return list(dict.fromkeys(modules))

    def load_module_content(
        self,
        module_paths: list[str],
        *,
        max_total_chars: int = 24000,
    ) -> list[LoadedSkillModule]:
        loaded: list[LoadedSkillModule] = []
        remaining = max_total_chars
        for relative in module_paths:
            candidate = (self.vendor_root / relative).resolve()
            if self.vendor_root not in candidate.parents or not candidate.is_file():
                continue
            content = candidate.read_text(encoding="utf-8")
            excerpt = content[:remaining]
            if not excerpt:
                break
            loaded.append(
                LoadedSkillModule(
                    path=relative,
                    sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    content=excerpt,
                )
            )
            remaining -= len(excerpt)
        return loaded

    def build_seedance_guidance(
        self,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        loaded = self.load_module_content(self.resolve_modules(action, context))
        guidance = "\n\n".join(
            f"### Seedance Skill 模块：{item.path}\n{item.content}" for item in loaded
        )
        evidence = [{"path": item.path, "sha256": item.sha256} for item in loaded]
        return guidance, evidence

    def status(self) -> dict[str, Any]:
        version_file = self.vendor_root / "VENDOR_VERSION.md"
        return {
            "installed": self.vendor_root.is_dir() and version_file.is_file(),
            "pinned_commit": PINNED_SEEDANCE_COMMIT,
            "vendor_path": str(self.vendor_root),
            "module_count": sum(len(value) for value in MODULES.values()),
            "license_present": (self.repo_root / "third_party" / "seedance-20" / "LICENSE").is_file(),
        }

