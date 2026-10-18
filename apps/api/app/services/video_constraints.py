from __future__ import annotations

import re
from typing import Any


MAX_SEEDANCE_CLIP_SECONDS = 15
MAX_SEEDANCE25_CLIP_SECONDS = 30
MIN_SEEDANCE25_CLIP_SECONDS = 4
MAX_SUPPORTED_VIDEO_CLIP_SECONDS = MAX_SEEDANCE25_CLIP_SECONDS
DEFAULT_VIDEO_DURATION_SECONDS = 5
SEEDANCE_SUPPORTED_DURATIONS = list(range(1, MAX_SEEDANCE_CLIP_SECONDS + 1))
SEEDANCE_RECOMMENDED_DURATIONS = [5, 10, 15]

_TIME_RANGE_RE = re.compile(
    r"(?P<start>\d+(?:\.\d+)?)\s*s?\s*[-–—~至到]\s*(?P<end>\d+(?:\.\d+)?)\s*s?",
    re.I,
)

_EXPLICIT_DURATION_RE = re.compile(r"(?<!\d)(?P<seconds>\d{1,2})\s*(?:秒|s)\b", re.I)


def recommend_video_duration(shot_task: str) -> tuple[int, str]:
    """Return a conservative 1-15 second timing budget from the shot task."""
    text = str(shot_task or "").strip()
    explicit = _EXPLICIT_DURATION_RE.search(text)
    if explicit:
        seconds = max(1, min(int(explicit.group("seconds")), MAX_SEEDANCE_CLIP_SECONDS))
        return seconds, "镜头任务中已明确写出时长，按原规划执行。"

    if any(marker in text for marker in ("最终品牌落版", "品牌落版", "片尾定帧", "静态落版", "仅规划后期")):
        return 4, "静态落版或后期定帧镜头，保留识别时间并避免无意义延长。"

    score = min(text.count("，") // 3 + text.count("；"), 3)
    reasons: list[str] = []
    if any(marker in text for marker in ("蒙太奇", "快切", "穿越", "群像", "用户矩阵", "产品矩阵", "多机位")):
        score += 4
        reasons.append("包含蒙太奇或多节点信息")
    if (
        ("先" in text and any(marker in text for marker in ("再", "随后", "然后", "后")))
        or any(marker in text for marker in ("随后", "然后", "转为", "从紧张", "进入产品", "情绪释放"))
    ):
        score += 2
        reasons.append("包含明确动作或情绪阶段变化")
    action_markers = (
        "起步", "打滑", "飞溅", "调整", "通过", "进入", "横移", "推近",
        "后拉", "扫过", "加速", "切换", "反射", "抬头",
    )
    if sum(marker in text for marker in action_markers) >= 3:
        score += 2
        reasons.append("需要容纳多个连续动作")
    if any(marker in text for marker in ("对白", "台词", "旁白", "解说")):
        score += 2
        reasons.append("需要保留语言节奏")

    if score <= 1:
        seconds = 6
    elif score <= 3:
        seconds = 8
    elif score <= 5:
        seconds = 10
    else:
        seconds = 12
    reason = "、".join(reasons) if reasons else "按单一镜头动作和构图变化估算"
    return seconds, f"{reason}；建议 {seconds} 秒，超过 15 秒的内容应拆分 Video Unit。"


def seedance_duration_instruction(duration_seconds: int | None = None) -> str:
    target = duration_seconds or DEFAULT_VIDEO_DURATION_SECONDS
    return (
        f"Seedance 单条视频最高 {MAX_SEEDANCE_CLIP_SECONDS} 秒；本镜头目标时长为 {target} 秒。"
        f"VP-PRECISION-18 第 1 项时长不得超过 {MAX_SEEDANCE_CLIP_SECONDS} 秒，"
        f"第 5 项分时段镜头描述必须从 0.0s 开始并止于 {target:.1f}s 以内。"
        f"如果原剧情超过 {MAX_SEEDANCE_CLIP_SECONDS} 秒，必须拆成多个 SH 镜头，不要塞进同一个视频提示词。"
    )


def duration_limit_message(duration_seconds: Any) -> str:
    return (
        f"当前任务为 {duration_seconds} 秒，超过 Seedance 单条视频最高 "
        f"{MAX_SEEDANCE_CLIP_SECONDS} 秒；请拆成多个镜头后再生成。"
    )


def validate_provider_duration(
    duration_seconds: int,
    provider_type: str,
    duration_mode: str = "specified",
) -> str | None:
    if provider_type == "volcengine_seedance25":
        if duration_mode == "smart":
            return None
        if MIN_SEEDANCE25_CLIP_SECONDS <= duration_seconds <= MAX_SEEDANCE25_CLIP_SECONDS:
            return None
        return "Seedance 2.5 指定时长必须在 4-30 秒内；也可以改用智能时长。"
    if 1 <= duration_seconds <= MAX_SEEDANCE_CLIP_SECONDS:
        return None
    return duration_limit_message(duration_seconds)


def parse_time_range_bounds(value: Any) -> tuple[float, float] | None:
    match = _TIME_RANGE_RE.search(str(value or ""))
    if not match:
        return None
    start = float(match.group("start"))
    end = float(match.group("end"))
    if end < start:
        start, end = end, start
    return start, end


def time_range_exceeds_seedance_limit(value: Any, max_seconds: int = MAX_SEEDANCE_CLIP_SECONDS) -> bool:
    bounds = parse_time_range_bounds(value)
    return bool(bounds and bounds[1] > max_seconds)


def cap_time_range_to_seedance(value: Any, max_seconds: int = MAX_SEEDANCE_CLIP_SECONDS) -> str | None:
    text = str(value or "").strip()
    bounds = parse_time_range_bounds(text)
    if not bounds:
        return text or None
    start, end = bounds
    if start >= max_seconds:
        return None
    capped_end = min(end, float(max_seconds))
    if end <= max_seconds:
        return text
    replacement = f"{start:.1f}s-{capped_end:.1f}s"
    return _TIME_RANGE_RE.sub(replacement, text, count=1)
