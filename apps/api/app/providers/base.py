from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderValidationResult:
    valid: bool
    message: str


class VideoProvider:
    provider_type = "base"

    def validate_config(self, profile: dict[str, Any]) -> ProviderValidationResult:
        raise NotImplementedError

    def validate_request(self, request: dict[str, Any], capabilities: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        if request["generation_mode"] not in capabilities.get("generation_modes", []):
            missing.append("当前服务通道不支持这个生成方式。")
        if request["duration_seconds"] not in capabilities.get("supported_durations", []):
            missing.append("当前服务通道不支持这个视频时长。")
        if request["resolution"] not in capabilities.get("supported_resolutions", []):
            missing.append("当前服务通道不支持这个分辨率。")
        if request["aspect_ratio"] not in capabilities.get("supported_aspect_ratios", []):
            missing.append("当前服务通道不支持这个画幅。")
        references = sum(len(value) for key, value in request["assets"].items() if isinstance(value, list) and "image" in key)
        if references and not capabilities.get("supports_reference_images", False):
            missing.append("当前服务通道不支持参考图片。")
        if references > capabilities.get("max_reference_images", 0):
            missing.append("参考图片数量超过当前服务通道限制。")
        return missing

    def estimate_cost(self, request: dict[str, Any], price_configs: list[dict[str, Any]]) -> float | None:
        if not price_configs:
            return None
        price = price_configs[0]
        if price.get("price_status", "known") != "known":
            return None
        value = price.get("price_value")
        if not isinstance(value, (int, float)):
            return None
        if price.get("billing_unit") == "per_second":
            return round(float(value) * int(request.get("duration_seconds", 0)), 4)
        return round(float(value), 4)

    def build_request_preview(self, request: dict[str, Any], profile_config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        raise NotImplementedError

    def build_response_preview(self, response: dict[str, Any], profile_config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        raise NotImplementedError
