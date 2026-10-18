from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


SECRET_PATTERNS = re.compile(r"(token|cookie|authorization|password|secret|apikey|api_key)", re.I)


@dataclass
class JimengCliResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error: str = ""
    raw_output: str = ""


@dataclass(frozen=True)
class JimengCliCapabilities:
    installed: bool
    cli_version: str = ""
    available_models: tuple[str, ...] = ()
    min_duration: int = 4
    max_duration: int = 15
    supported_resolutions: tuple[str, ...] = ("720p",)
    max_images: int = 0
    max_videos: int = 0
    max_audios: int = 0
    capability_source: str = "dreamina_cli_help"
    unavailable_reason: str = ""


def parse_multimodal2video_help(text: str, *, installed: bool = True, cli_version: str = "") -> JimengCliCapabilities:
    model_values = re.findall(r"\bseedance\d+(?:\.\d+)+(?:[a-z0-9_.-]*)\b", text, re.I)
    models = tuple(dict.fromkeys(item.rstrip(".") for item in model_values))
    duration_match = re.search(r"(?:--)?duration[^\n]*?(\d+)\s*[-~]\s*(\d+)", text, re.I)
    resolutions = tuple(dict.fromkeys(re.findall(r"\b(?:480p|720p|1080p|4k)\b", text, re.I))) or ("720p",)

    def limit(flag: str) -> int:
        match = re.search(rf"(?:--)?{flag}\s*(?:<=|≤|最多|maximum|max)\s*(\d+)", text, re.I)
        return int(match.group(1)) if match else 0

    reason = "" if models else "当前 dreamina CLI 帮助中没有发现可用的视频模型参数。"
    return JimengCliCapabilities(
        installed=installed,
        cli_version=cli_version,
        available_models=models,
        min_duration=int(duration_match.group(1)) if duration_match else 4,
        max_duration=int(duration_match.group(2)) if duration_match else 15,
        supported_resolutions=resolutions,
        max_images=limit("image"),
        max_videos=limit("video"),
        max_audios=limit("audio"),
        unavailable_reason=reason,
    )


def _parse_scalar(value: str) -> str | int | float | bool:
    value = value.strip().strip("\"'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def parse_cli_output(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {"items": payload}
    except json.JSONDecodeError:
        pass
    data: dict[str, Any] = {}
    for line in text.splitlines():
        if SECRET_PATTERNS.search(line):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
        elif "=" in line:
            key, value = line.split("=", 1)
        else:
            continue
        key = key.strip().lower().replace(" ", "_").replace("-", "_")
        if key:
            data[key] = _parse_scalar(value)
    return data


def sanitized_summary(stdout: str, stderr: str = "") -> str:
    lines: list[str] = []
    for line in (stdout + "\n" + stderr).splitlines():
        if not line.strip() or SECRET_PATTERNS.search(line):
            continue
        lines.append(line.strip())
    return "\n".join(lines[:20])


def normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"success", "succeeded", "done", "finish", "finished", "complete", "completed"}:
        return "completed"
    if status in {"failed", "fail", "error", "canceled", "cancelled"}:
        return "failed"
    if status in {"running", "processing", "generating"}:
        return "processing"
    if status in {"queued", "queueing", "pending", "submitted"}:
        return "submitted"
    if status in {"querying", "verifying"}:
        return "verifying"
    return str(value or "")


def extract_provider_status(payload: dict[str, Any]) -> str:
    for key in ("gen_status", "status", "state", "task_status"):
        if payload.get(key) not in (None, ""):
            return str(payload[key])
    for section in ("data", "result"):
        child = payload.get(section)
        if isinstance(child, dict):
            value = extract_provider_status(child)
            if value:
                return value
    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                value = extract_provider_status(item)
                if value:
                    return value
    return ""


def extract_submit_id(payload: dict[str, Any]) -> str:
    for key in ("submit_id", "task_id", "id"):
        if payload.get(key):
            return str(payload[key])
    for section in ("data", "result"):
        child = payload.get(section)
        if isinstance(child, dict):
            value = extract_submit_id(child)
            if value:
                return value
    return ""


def extract_queue_info(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    queue_info = payload.get("queue_info")
    if isinstance(queue_info, dict):
        return queue_info
    for section in ("data", "result"):
        child = payload.get(section)
        if isinstance(child, dict):
            value = extract_queue_info(child)
            if value:
                return value
    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                value = extract_queue_info(item)
                if value:
                    return value
    return {}


def extract_video_paths(payload: dict[str, Any], text: str = "") -> list[str]:
    found: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str) and value.lower().endswith((".mp4", ".mov")):
            found.append(value)

    visit(payload)
    found.extend(re.findall(r"(/[^\s]+?\.(?:mp4|mov))", text, flags=re.I))
    deduped: list[str] = []
    for item in found:
        if item not in deduped:
            deduped.append(item)
    return deduped


class JimengCliRunner:
    def __init__(self, command: str = "dreamina") -> None:
        self.command = command

    def installed(self) -> bool:
        return shutil.which(self.command) is not None

    def _run(self, args: list[str], timeout: int = 120) -> JimengCliResult:
        if not self.installed():
            return JimengCliResult(ok=False, error="本机没有检测到 dreamina 命令。")
        try:
            completed = subprocess.run(
                [self.command, *args],
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return JimengCliResult(ok=False, error="即梦 CLI 执行超时。")
        except OSError as cause:
            return JimengCliResult(ok=False, error=f"即梦 CLI 无法执行：{cause}")
        data = parse_cli_output(completed.stdout)
        summary = sanitized_summary(completed.stdout, completed.stderr)
        if completed.returncode != 0:
            return JimengCliResult(ok=False, data=data, summary=summary, error=summary or "即梦 CLI 返回失败。", raw_output=completed.stdout + "\n" + completed.stderr)
        return JimengCliResult(ok=True, data=data, summary=summary, raw_output=completed.stdout + "\n" + completed.stderr)

    def capabilities(self) -> JimengCliCapabilities:
        if not self.installed():
            return JimengCliCapabilities(installed=False, unavailable_reason="本机没有检测到 dreamina 命令。")
        version_result = self._run(["--version"], timeout=30)
        version = str(version_result.data.get("version") or (version_result.summary.splitlines()[0] if version_result.summary else ""))
        help_result = self._run(["multimodal2video", "--help"], timeout=30)
        if not help_result.ok and not help_result.raw_output:
            return JimengCliCapabilities(installed=True, cli_version=version, unavailable_reason=help_result.error or "无法读取 CLI 模型能力。")
        return parse_multimodal2video_help(help_result.raw_output or help_result.summary, cli_version=version)

    def user_credit(self) -> JimengCliResult:
        return self._run(["user_credit"], timeout=30)

    def list_task(self, submit_id: str = "", limit: int = 20) -> JimengCliResult:
        args = ["list_task", f"--limit={limit}"]
        if submit_id:
            args.append(f"--submit_id={submit_id}")
        return self._run(args, timeout=60)

    def submit_multimodal2video(
        self,
        *,
        prompt: str,
        model_version: str,
        duration: int,
        ratio: str,
        video_resolution: str,
        images: list[Path] | None = None,
        videos: list[Path] | None = None,
        audios: list[Path] | None = None,
    ) -> JimengCliResult:
        args = [
            "multimodal2video",
            f"--prompt={prompt}",
            f"--model_version={model_version}",
            f"--duration={duration}",
            f"--ratio={ratio}",
            f"--video_resolution={video_resolution}",
        ]
        for image in images or []:
            args.append(f"--image={image}")
        for video in videos or []:
            args.append(f"--video={video}")
        for audio in audios or []:
            args.append(f"--audio={audio}")
        return self._run(args, timeout=180)

    def query_result(self, submit_id: str, download_dir: Path | None = None) -> JimengCliResult:
        args = ["query_result", f"--submit_id={submit_id}"]
        if download_dir is not None:
            download_dir.mkdir(parents=True, exist_ok=True)
            args.append(f"--download_dir={download_dir}")
        return self._run(args, timeout=180)


@lru_cache(maxsize=4)
def detect_jimeng_cli_capabilities(command: str = "dreamina") -> JimengCliCapabilities:
    return JimengCliRunner(command).capabilities()
