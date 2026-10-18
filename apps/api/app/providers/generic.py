from __future__ import annotations

from typing import Any

from app.providers.base import ProviderValidationResult, VideoProvider


INTERNAL_VIDEO_STATUSES = {
    "draft", "blocked", "ready", "awaiting_budget_confirm", "submitted",
    "processing", "completed", "failed", "cancelled", "imported", "confirmed", "rejected",
}


def _path_value(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if isinstance(value, list) and part.isdigit():
            index = int(part)
            if index >= len(value):
                return None
            value = value[index]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


class SeedanceAggregatorGenericProvider(VideoProvider):
    provider_type = "seedance_aggregator_generic"

    def validate_config(self, profile: dict[str, Any]) -> ProviderValidationResult:
        required = ("base_url", "create_task_path", "get_task_path_template", "auth_env_key_name")
        missing = [field for field in required if not str(profile.get(field, "")).strip()]
        if missing:
            return ProviderValidationResult(False, f"缺少配置字段：{', '.join(missing)}。未发送网络请求。")
        return ProviderValidationResult(True, "通用聚合 Provider 基础配置完整；未发送网络请求。请继续核对官方文档、价格和字段映射。")

    def build_request_preview(self, request: dict[str, Any], profile_config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        model_mapping = profile_config.get("model_mapping", {})
        field_mapping = profile_config.get("request_field_mapping", {})
        missing: list[str] = []
        payload: dict[str, Any] = {}
        model_family = request.get("model_family", "")
        model_id = model_mapping.get(model_family)
        if model_id:
            payload[field_mapping.get("model_id", "model")] = model_id
        else:
            missing.append(f"缺少模型映射：{model_family}。")
        for canonical_name in ("prompt", "duration_seconds", "resolution", "aspect_ratio"):
            provider_name = field_mapping.get(canonical_name)
            if not provider_name:
                missing.append(f"缺少请求字段映射：{canonical_name}。")
                continue
            payload[provider_name] = request.get(canonical_name)
        for canonical_name in ("reference_images", "reference_videos", "reference_audios"):
            values = request.get("assets", {}).get(canonical_name, [])
            provider_name = field_mapping.get(canonical_name)
            if values and not provider_name:
                missing.append(f"缺少请求字段映射：{canonical_name}。")
            elif provider_name:
                payload[provider_name] = values
        for canonical_name in ("generate_audio", "seed"):
            provider_name = field_mapping.get(canonical_name)
            if provider_name:
                payload[provider_name] = request.get(canonical_name)
        return payload, missing

    def build_response_preview(self, response: dict[str, Any], profile_config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        field_mapping = profile_config.get("response_field_mapping", {})
        status_mapping = profile_config.get("response_status_mapping", {})
        missing: list[str] = []
        normalized: dict[str, Any] = {}
        for canonical_name in ("task_id", "status", "video_url", "error_message"):
            provider_path = field_mapping.get(canonical_name)
            if not provider_path:
                missing.append(f"缺少响应字段映射：{canonical_name}。")
                continue
            normalized[canonical_name] = _path_value(response, provider_path)
        external_status = normalized.get("status")
        if external_status:
            mapped_status = status_mapping.get(str(external_status), external_status)
            if mapped_status not in INTERNAL_VIDEO_STATUSES:
                missing.append(f"缺少状态映射：{external_status}。")
            else:
                normalized["status"] = mapped_status
        if not normalized.get("task_id"):
            missing.append("响应样例中未找到任务 ID。")
        if not external_status:
            missing.append("响应样例中未找到状态。")
        return normalized, missing
