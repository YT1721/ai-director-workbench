from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import ProviderValidationResult
from app.providers.generic import SeedanceAggregatorGenericProvider
from app.services.video_constraints import MAX_SEEDANCE_CLIP_SECONDS, SEEDANCE_SUPPORTED_DURATIONS


HUIMENG_API_HOME = "https://api.huimengi.com/"
HUIMENG_MODEL_PAGE = "https://api.huimengi.com/models/seedance-2.0-fast"
HUIMENG_LIVE_PROFILE_ID = "huimeng_live"


class SeedanceHuimengProvider(SeedanceAggregatorGenericProvider):
    """HuiMeng live-test adapter with a hard single-shot gate."""

    provider_type = "seedance_huimeng_live"

    @classmethod
    def profile_template(cls, base_url: str = "https://api.huimengi.com", model_id: str = "seedance-2.0-fast") -> dict[str, Any]:
        return {
            "id": HUIMENG_LIVE_PROFILE_ID,
            "display_name": "慧梦 API｜Seedance 2.0 Fast 单镜实测",
            "provider_type": cls.provider_type,
            "base_url": base_url.rstrip("/"),
            "create_task_path": "/api/v1/tasks",
            "get_task_path_template": "/api/v1/tasks/{id}",
            "auth_type": "bearer",
            "auth_header_name": "Authorization",
            "auth_prefix": "Bearer ",
            "auth_env_key_name": "HUIMENGI_API_KEY",
            "config": {
                "documentation_url": HUIMENG_API_HOME,
                "price_source_url": HUIMENG_MODEL_PAGE,
                "model_mapping": {"seedance-2.0": model_id},
                "request_field_mapping": {
                    "prompt": "params.prompt",
                    "duration_seconds": "params.duration",
                    "resolution": "params.resolution",
                },
                "response_field_mapping": {
                    "task_id": "data.id",
                    "status": "data.status",
                    "video_url": "data.video_url",
                    "error_message": "data.error",
                },
                "response_status_mapping": {
                    "pending": "submitted",
                    "queued": "submitted",
                    "submitted": "submitted",
                    "running": "processing",
                    "processing": "processing",
                    "success": "completed",
                    "succeeded": "completed",
                    "completed": "completed",
                    "failed": "failed",
                    "error": "failed",
                    "cancelled": "cancelled",
                    "canceled": "cancelled",
                    "expired": "failed",
                },
                "live_submission_enabled": True,
                "live_test_limit": "single_task_max_15s_720p",
                "official_docs_verified_on": "2026-06-04",
            },
            "capabilities": {
                "supported_models": ["seedance-2.0"],
                "generation_modes": ["multimodal_reference"],
                "supported_durations": SEEDANCE_SUPPORTED_DURATIONS,
                "supported_resolutions": ["720p"],
                "supported_aspect_ratios": ["16:9", "9:16"],
                "supports_audio_generation": False,
                "supports_callback": False,
                "supports_reference_images": False,
                "max_reference_images": 0,
                "result_delivery": "poll_task",
            },
            "price_configs": [{
                "price_status": "unknown",
                "billing_unit": "provider_defined",
                "currency": "CREDITS",
                "source_url": HUIMENG_MODEL_PAGE,
                "note": "当前没有可可靠计算的固定单价；积分消耗会随模型、时长和分辨率变化，请在服务商账户人工核对。",
            }],
        }

    def validate_config(self, profile: dict[str, Any]) -> ProviderValidationResult:
        required = ("base_url", "create_task_path", "get_task_path_template", "auth_env_key_name")
        missing = [field for field in required if not str(profile.get(field, "")).strip()]
        if missing:
            return ProviderValidationResult(False, f"缺少慧梦配置字段：{', '.join(missing)}。未发送网络请求。")
        if profile.get("auth_env_key_name") != "HUIMENGI_API_KEY":
            return ProviderValidationResult(False, "慧梦真实测试只允许使用 HUIMENGI_API_KEY 环境变量。未发送网络请求。")
        return ProviderValidationResult(True, "慧梦真实单镜测试配置完整；真实提交仍需费用风险确认、页面确认和服务端开关。")

    def validate_request(self, request: dict[str, Any], capabilities: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        if request["generation_mode"] not in capabilities.get("generation_modes", []):
            missing.append("慧梦服务通道不支持当前生成方式。")
        if request["duration_seconds"] not in capabilities.get("supported_durations", []):
            supported = capabilities.get("supported_durations", [])
            supported_text = " / ".join(str(value) for value in supported) or "未配置"
            missing.append(
                f"当前慧梦服务配置不支持 {request['duration_seconds']} 秒；配置允许时长：{supported_text} 秒。"
            )
        if request["resolution"] not in capabilities.get("supported_resolutions", []):
            missing.append("慧梦真实单镜测试只允许 720p。")
        if request["aspect_ratio"] not in capabilities.get("supported_aspect_ratios", []):
            missing.append("慧梦服务通道不支持当前画幅。")
        return missing

    def build_request_preview(self, request: dict[str, Any], profile_config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        model_mapping = profile_config.get("model_mapping", {})
        model_id = model_mapping.get(request.get("model_family", ""), "seedance-2.0-fast")
        payload = {
            "model": model_id,
            "params": {
                "prompt": request.get("prompt", ""),
                "duration": request.get("duration_seconds"),
                "resolution": request.get("resolution"),
            },
        }
        missing: list[str] = []
        if request.get("duration_seconds") not in SEEDANCE_SUPPORTED_DURATIONS:
            missing.append(f"Seedance 单条视频必须在 1-{MAX_SEEDANCE_CLIP_SECONDS} 秒内。")
        if request.get("resolution") != "720p":
            missing.append("慧梦真实单镜测试只允许 720p。")
        return payload, missing

    def submit_task(self, base_url: str, api_key: str, request: dict[str, Any], profile_config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        payload, missing = self.build_request_preview(request, profile_config)
        if missing:
            raise ValueError("；".join(missing))
        response = httpx.post(
            f"{base_url.rstrip('/')}/api/v1/tasks",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        raw = response.json()
        return self.normalize_response(raw), raw

    def poll_task(self, base_url: str, api_key: str, external_task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        response = httpx.get(
            f"{base_url.rstrip('/')}/api/v1/tasks/{external_task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        raw = response.json()
        return self.normalize_response(raw), raw

    def download_video(self, video_url: str) -> bytes:
        response = httpx.get(video_url, timeout=120, follow_redirects=True)
        response.raise_for_status()
        return response.content

    def _first_video_url(self, data: dict[str, Any]) -> str:
        outputs = data.get("outputs") or data.get("videos") or data.get("urls")
        if isinstance(outputs, list) and outputs:
            first = outputs[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return str(first.get("url") or first.get("video_url") or first.get("output_url") or "")
        output = data.get("output") or data.get("result")
        if isinstance(output, dict):
            return str(output.get("video_url") or output.get("url") or output.get("output_url") or "")
        return ""

    def normalize_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized, missing = self.build_response_preview(payload, self.profile_template()["config"])
        if missing:
            # Public quick-start examples do not define the full envelope. Fall back
            # across common task response shapes before surfacing a missing field.
            data = payload.get("data") or payload.get("result") or payload
            normalized = {
                "task_id": data.get("id") or data.get("task_id"),
                "status": data.get("status") or data.get("state"),
                "video_url": data.get("video_url") or data.get("url") or data.get("output_url") or self._first_video_url(data),
                "error_message": data.get("error") or data.get("error_message") or "",
            }
        status = str(normalized.get("status") or "").lower()
        status_map = self.profile_template()["config"]["response_status_mapping"]
        normalized["status"] = status_map.get(status, status or "submitted")
        return normalized
