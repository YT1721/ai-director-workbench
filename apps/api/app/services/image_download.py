from __future__ import annotations

import json

from fastapi import HTTPException
from sqlmodel import Session

from app.config import Settings
from app.models import ImageGenerationJob
from app.models.workbench import utc_now
from app.providers.image import ImageProvider


def download_image_with_url_refresh(
    session: Session,
    settings: Settings,
    job: ImageGenerationJob,
    provider: ImageProvider,
) -> bytes:
    """下载慧梦生成图。

    慧梦返回的 OSS 签名链接会过期（403），过期后直接用旧链接下载一定失败。
    这里在首次下载失败时重新查询一次任务换取新链接，再重试一次下载。
    """
    try:
        return provider.download_image(job.remote_result_url)
    except Exception as cause:
        if not job.external_task_id:
            raise HTTPException(status_code=502, detail=f"慧梦图片下载失败：{cause}") from cause
        try:
            normalized, raw = provider.poll_task(
                settings.huimengi_image_base_url,
                settings.huimengi_api_key,
                job.external_task_id,
            )
        except Exception as poll_cause:
            raise HTTPException(
                status_code=502,
                detail=f"图片下载链接已过期，重新获取链接失败：{poll_cause}",
            ) from poll_cause
        fresh_status = str(normalized.get("status") or "")
        if fresh_status in {"failed", "cancelled"}:
            raise HTTPException(
                status_code=502,
                detail="服务端的生成结果已过期被清理，请重新生成图片。",
            ) from cause
        fresh_url = str(normalized.get("image_url") or "")
        if not fresh_url or fresh_url == job.remote_result_url:
            raise HTTPException(
                status_code=502,
                detail="图片下载链接已过期（生成结果只在服务端保留约 24 小时），请重新生成图片。",
            ) from cause
        job.remote_result_url = fresh_url
        job.response_snapshot_json = json.dumps(raw, ensure_ascii=False)
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
        try:
            return provider.download_image(fresh_url)
        except Exception as retry_cause:
            raise HTTPException(
                status_code=502,
                detail="图片下载链接已过期或已失效（生成结果只在服务端保留约 24 小时），请重新生成图片。",
            ) from retry_cause
