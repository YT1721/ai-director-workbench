from __future__ import annotations

from typing import Any

from app.providers.base import ProviderValidationResult
from app.providers.generic import SeedanceAggregatorGenericProvider
from app.services.video_constraints import SEEDANCE_SUPPORTED_DURATIONS


ATLAS_CLOUD_MODEL_PAGE = "https://www.atlascloud.ai/models/bytedance/seedance-2.0-fast/reference-to-video"


class SeedanceAtlasCloudProvider(SeedanceAggregatorGenericProvider):
    """Atlas Cloud local-only adapter.

    The adapter intentionally stops at request and response previews. Reference
    asset upload and live task submission remain disabled until a later gate.
    """

    provider_type = "seedance_atlas_cloud_disabled"

    @classmethod
    def profile_template(cls) -> dict[str, Any]:
        return {
            "display_name": "Atlas Cloud｜Seedance 2.0 Fast Reference",
            "provider_type": cls.provider_type,
            "base_url": "https://api.atlascloud.ai",
            "create_task_path": "/api/v1/model/generateVideo",
            "get_task_path_template": "/api/v1/model/prediction/{id}",
            "auth_type": "bearer",
            "auth_header_name": "Authorization",
            "auth_prefix": "Bearer ",
            "auth_env_key_name": "ATLASCLOUD_API_KEY",
            "config": {
                "documentation_url": ATLAS_CLOUD_MODEL_PAGE,
                "price_source_url": ATLAS_CLOUD_MODEL_PAGE,
                "upload_media_path": "/api/v1/file/uploadMedia",
                "live_flow_note": "本地预览流程：uploadMedia 素材映射 → generateVideo 请求映射 → prediction 轮询映射。真实上传和提交仍关闭。",
                "model_mapping": {
                    "seedance-2.0": "bytedance/seedance-2.0-fast/reference-to-video",
                },
                "request_field_mapping": {
                    "prompt": "input.prompt",
                },
                "response_field_mapping": {
                    "task_id": "data.id",
                    "status": "data.status",
                    "video_url": "data.outputs.0",
                    "error_message": "data.error",
                },
                "response_status_mapping": {
                    "processing": "processing",
                    "completed": "completed",
                    "succeeded": "completed",
                    "failed": "failed",
                },
                "live_submission_enabled": False,
                "reference_upload_status": "upload_media_mapping_only_not_implemented",
                "official_docs_verified_on": "2026-06-02",
            },
            "capabilities": {
                "supported_models": ["seedance-2.0"],
                "generation_modes": ["multimodal_reference"],
                "supported_durations": SEEDANCE_SUPPORTED_DURATIONS,
                "supported_resolutions": ["720p"],
                "supported_aspect_ratios": ["16:9", "9:16"],
                "supports_audio_generation": True,
                "supports_callback": False,
                "supports_reference_images": True,
                "max_reference_images": 4,
                "supports_reference_videos": True,
                "supports_reference_audios": True,
                "result_delivery": "poll_prediction",
            },
            "price_configs": [{
                "price_status": "known",
                "price_value": 0.1935,
                "billing_unit": "per_second",
                "currency": "USD",
                "source_url": ATLAS_CLOUD_MODEL_PAGE,
                "note": "Fast Reference-to-Video 720p 页面展示价；提交前仍需人工核对。",
            }],
        }

    def validate_config(self, profile: dict[str, Any]) -> ProviderValidationResult:
        generic = super().validate_config(profile)
        if not generic.valid:
            return generic
        expected = self.profile_template()
        checks = {
            "base_url": expected["base_url"],
            "create_task_path": expected["create_task_path"],
            "get_task_path_template": expected["get_task_path_template"],
            "auth_env_key_name": expected["auth_env_key_name"],
        }
        mismatched = [field for field, value in checks.items() if profile.get(field) != value]
        if mismatched:
            return ProviderValidationResult(
                False,
                f"Atlas Cloud 模板字段已被修改：{', '.join(mismatched)}。未发送网络请求。",
            )
        return ProviderValidationResult(
            True,
            "Atlas Cloud 禁用状态 Adapter 配置完整；未发送网络请求。真实提交与素材上传仍被强制关闭。",
        )

    def build_request_preview(self, request: dict[str, Any], profile_config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        model_mapping = profile_config.get("model_mapping", {})
        model_family = request.get("model_family", "")
        model_id = model_mapping.get(model_family)
        missing: list[str] = []
        payload: dict[str, Any] = {
            "model": model_id,
            "input": {
                "prompt": request.get("prompt", ""),
            },
            "_local_preview_only": {
                "canonical_not_submitted": {
                    "duration_seconds": request.get("duration_seconds"),
                    "resolution": request.get("resolution"),
                    "aspect_ratio": request.get("aspect_ratio"),
                    "generate_audio": request.get("generate_audio"),
                    "assets": request.get("assets", {}),
                },
                "outbound_request_sent": False,
            },
        }
        if not model_id:
            missing.append(f"缺少模型映射：{model_family}。")
        if any(request.get("assets", {}).values()):
            missing.append("Atlas Cloud 参考素材需先接入 uploadMedia 本地映射；当前只生成预览，不提交任务。")
        return payload, missing
