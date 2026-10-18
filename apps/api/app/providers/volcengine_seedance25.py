from __future__ import annotations

from typing import Any

from app.providers.base import ProviderValidationResult, VideoProvider


class VolcengineSeedance25MockProvider(VideoProvider):
    """Seedance 2.5 首期适配器，只负责本地请求编译与能力验收。"""

    provider_type = "volcengine_seedance25"

    def validate_config(self, profile: dict[str, Any]) -> ProviderValidationResult:
        config = profile.get("config") if isinstance(profile.get("config"), dict) else {}
        if config.get("mock_only") is not True:
            return ProviderValidationResult(False, "Seedance 2.5 真实提交尚未开放；当前配置必须保持 Mock。")
        return ProviderValidationResult(
            True,
            "Seedance 2.5 Mock Provider 已就绪；只运行本地链路验收，不发送网络请求。",
        )

    def build_request_preview(
        self,
        request: dict[str, Any],
        profile_config: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        manifest = request.get("reference_manifest")
        if not isinstance(manifest, list):
            manifest = []
        content = [
            {
                "type": item.get("media_type", "image"),
                "token": item.get("token", ""),
                "asset_id": item.get("asset_id", ""),
                "purpose": item.get("purpose", ""),
                "must_keep": item.get("must_keep", ""),
                "must_not_transfer": item.get("must_not_transfer", ""),
            }
            for item in manifest
        ]
        content.append({"type": "text", "text": request.get("prompt", "")})
        return {
            "model": request.get("provider_model_id"),
            "content": content,
            "duration": -1 if request.get("duration_mode") == "smart" else request.get("duration_seconds"),
            "resolution": request.get("resolution"),
            "generation_mode": request.get("generation_mode"),
            "mock_only": True,
            "outbound_request_sent": False,
        }, []

    def build_response_preview(
        self,
        response: dict[str, Any],
        profile_config: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        return {
            "status": "mock_only",
            "outbound_request_sent": False,
        }, ["首期 Mock Provider 不接受真实服务商响应。"]
