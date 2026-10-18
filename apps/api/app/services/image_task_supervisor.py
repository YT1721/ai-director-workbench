from __future__ import annotations

from threading import Event, Lock, Thread

from sqlmodel import Session, select

from app.config import Settings
from app.models import ImageGenerationJob
from app.services.assets import download_asset_image_job, poll_asset_image_job
from app.services.image_task_locks import image_task_lock
from app.services.storyboards import download_storyboard_image_job, poll_storyboard_image_job


ACTIVE_IMAGE_STATUSES = ("submitted", "processing", "completed")
ASSET_TARGET_TYPES = {"character-master", "costume", "scene", "prop"}


class ImageTaskSupervisor:
    def __init__(self, engine, settings: Settings) -> None:
        self.engine = engine
        self.settings = settings
        self._stop = Event()
        self._wake = Event()
        self._thread: Thread | None = None
        self._cycle_lock = Lock()

    def start(self) -> None:
        if not self.settings.image_task_supervisor_enabled or self._thread is not None:
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="image-task-supervisor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2, self.settings.image_task_poll_interval_seconds + 1))
        self._thread = None

    def wake(self) -> None:
        self._wake.set()

    def run_cycle(self) -> int:
        if not self._cycle_lock.acquire(blocking=False):
            return 0
        try:
            with Session(self.engine) as session:
                jobs = list(
                    session.exec(
                        select(ImageGenerationJob)
                        .where(
                            ImageGenerationJob.provider == "huimeng_image",
                            ImageGenerationJob.external_task_id != "",
                            ImageGenerationJob.status.in_(ACTIVE_IMAGE_STATUSES),
                        )
                        .order_by(ImageGenerationJob.created_at.desc())
                    ).all()
                )
                latest_job_ids: list[str] = []
                seen_targets: set[tuple[str, str]] = set()
                for job in jobs:
                    target = (job.target_type, job.target_id)
                    if target in seen_targets:
                        job.status = "superseded"
                        job.error_message = "已有更新的同目标任务，本任务已停止监控，避免重复下载和重复生成版本。"
                        session.add(job)
                        continue
                    seen_targets.add(target)
                    latest_job_ids.append(job.id)
                session.commit()
            processed = 0
            for job_id in latest_job_ids:
                with image_task_lock(job_id, blocking=False) as acquired:
                    if not acquired:
                        continue
                    try:
                        self._process_job(job_id)
                        processed += 1
                    except Exception:
                        # 临时网络或服务异常保留原状态，下轮继续，不误判为生成失败。
                        continue
            return processed
        finally:
            self._cycle_lock.release()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.run_cycle()
            self._wake.wait(self.settings.image_task_poll_interval_seconds)
            self._wake.clear()

    def _process_job(self, job_id: str) -> None:
        with Session(self.engine) as session:
            job = session.get(ImageGenerationJob, job_id)
            if job is None or job.status not in ACTIVE_IMAGE_STATUSES:
                return
            target_type = job.target_type
            status = job.status

        if target_type == "storyboard_version":
            with Session(self.engine) as session:
                if status != "completed":
                    poll_storyboard_image_job(session, self.settings, job_id, True)
                job = session.get(ImageGenerationJob, job_id)
                if job is not None and job.status == "completed":
                    download_storyboard_image_job(
                        session,
                        self.settings,
                        self.settings.projects_root,
                        job_id,
                        True,
                    )
            return

        if target_type in ASSET_TARGET_TYPES:
            with Session(self.engine) as session:
                if status != "completed":
                    poll_asset_image_job(session, self.settings, job_id, True)
                job = session.get(ImageGenerationJob, job_id)
                if job is not None and job.status == "completed":
                    download_asset_image_job(
                        session,
                        self.settings,
                        self.settings.projects_root,
                        job_id,
                        True,
                    )
