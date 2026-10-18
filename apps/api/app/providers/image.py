from __future__ import annotations

import base64
from typing import Any, Protocol

import httpx


class ImageProvider(Protocol):
    def submit_task(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        prompt: str,
        ratio: str = "16:9",
        quality: str = "medium",
        resolution: str = "2k",
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]: ...

    def poll_task(
        self,
        base_url: str,
        api_key: str,
        external_task_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]: ...

    def download_image(self, image_url: str) -> bytes: ...


class HuimengImageProvider:
    """慧梦 image-2 受控生图通道。"""

    def submit_task(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        prompt: str,
        ratio: str = "16:9",
        quality: str = "medium",
        resolution: str = "2k",
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        request_payload = {
            "model": model_id,
            "params": {
                "prompt": prompt,
                "ratio": ratio,
                "quality": quality,
                "resolution": resolution,
            },
        }
        response = httpx.post(
            f"{base_url.rstrip('/')}/api/v1/tasks",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=request_payload,
            timeout=45,
        )
        response.raise_for_status()
        raw = response.json()
        return self.normalize_response(raw), raw, request_payload

    def poll_task(
        self,
        base_url: str,
        api_key: str,
        external_task_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        response = httpx.get(
            f"{base_url.rstrip('/')}/api/v1/tasks/{external_task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        raw = response.json()
        return self.normalize_response(raw), raw

    def download_image(self, image_url: str) -> bytes:
        response = httpx.get(image_url, timeout=120, follow_redirects=True)
        response.raise_for_status()
        return response.content

    def normalize_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data") or payload.get("result") or payload
        output = data.get("output") if isinstance(data, dict) else None
        outputs = data.get("outputs") or data.get("images") or data.get("urls") if isinstance(data, dict) else None
        image_url = ""
        if isinstance(output, dict):
            image_url = str(output.get("image_url") or output.get("url") or output.get("output_url") or "")
        if not image_url and isinstance(outputs, list) and outputs:
            first = outputs[0]
            if isinstance(first, str):
                image_url = first
            elif isinstance(first, dict):
                image_url = str(first.get("url") or first.get("image_url") or first.get("output_url") or "")
        status = str(data.get("status") or data.get("state") or "").lower() if isinstance(data, dict) else ""
        status_map = {
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
        }
        if not isinstance(data, dict):
            return {
                "task_id": "",
                "status": "submitted",
                "image_url": image_url,
                "error_message": "",
            }
        normalized_status = status_map.get(status, status or "submitted")
        final_image_url = data.get("image_url") or data.get("url") or data.get("output_url") or image_url
        if final_image_url and normalized_status not in {"failed", "cancelled"}:
            normalized_status = "completed"
        return {
            "task_id": data.get("id") or data.get("task_id") or "",
            "status": normalized_status,
            "image_url": final_image_url,
            "error_message": data.get("error") or data.get("error_message") or "",
        }



class OpenAIImagesProvider:
    """OpenAI 兼容图像 API（即时返回，不需要任务轮询）。

    适用于 OpenAI 官方 /images/generations 及兼容该格式的聚合服务。
    """

    def generate_image(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        prompt: str,
        size: str = "1536x1024",
    ) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
        request_payload = {"model": model_id, "prompt": prompt, "size": size}
        response = httpx.post(
            f"{base_url.rstrip('/')}/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=request_payload,
            timeout=180,
        )
        response.raise_for_status()
        raw = response.json()
        items = raw.get("data") or []
        first = items[0] if items and isinstance(items[0], dict) else {}
        if first.get("b64_json"):
            return base64.b64decode(first["b64_json"]), raw, request_payload
        if first.get("url"):
            image = httpx.get(str(first["url"]), timeout=120, follow_redirects=True)
            image.raise_for_status()
            return image.content, raw, request_payload
        raise ValueError("图像服务没有返回图片数据（缺少 b64_json 或 url）。")
