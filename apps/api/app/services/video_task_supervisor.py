from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from threading import Event, Lock, Thread
from time import monotonic

from fastapi import HTTPException
from sqlmodel import Session, select

from app.config import Settings
from app.models.videos import BatchVideoJob, BatchVideoTask, ProviderRun
from app.models.workbench import utc_now
from app.schemas.videos import VideoTaskSupervisorStatusView
from app.services.video_task_locks import video_task_lock
from app.services.videos import (
    _task_external_provider,
    _update_batch_job_status,
    jimeng_cli_download_task,
    jimeng_cli_poll_task,
    jimeng_cli_submit_task,
    live_download_task,
    live_poll_task,
    live_submit_task,
    seedance25_mock_download_task,
    seedance25_mock_poll_task,
    seedance25_mock_submit_task,
)


ACTIVE_VIDEO_STATUSES = ("verifying", "submitted", "processing", "completed")


@dataclass
class _SupervisorState:
    running: bool = False
    active_task_count: int = 0
    last_cycle_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str = ""


class VideoTaskSupervisor:
    def __init__(self, engine, settings: Settings) -> None:
        self.engine = engine
        self.settings = settings
        self._state = _SupervisorState()
        self._state_lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._retry_state: dict[str, tuple[int, float]] = {}

    def start(self) -> None:
        if not self.settings.video_task_supervisor_enabled or self._thread is not None:
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="video-task-supervisor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(2, self.settings.video_task_poll_interval_seconds + 1))
        self._thread = None
        with self._state_lock:
            self._state.running = False

    def status(self) -> VideoTaskSupervisorStatusView:
        with self._state_lock:
            state = _SupervisorState(**self._state.__dict__)
        return VideoTaskSupervisorStatusView(
            enabled=self.settings.video_task_supervisor_enabled,
            running=state.running,
            poll_interval_seconds=self.settings.video_task_poll_interval_seconds,
            active_task_count=state.active_task_count,
            last_cycle_at=state.last_cycle_at,
            last_success_at=state.last_success_at,
            last_error=state.last_error,
        )

    def run_cycle(self) -> int:
        with Session(self.engine) as session:
            dispatch_task_ids = []
            for job in session.exec(
                select(BatchVideoJob).where(
                    BatchVideoJob.dispatch_enabled == True,  # noqa: E712
                    BatchVideoJob.batch_authorized == True,  # noqa: E712
                )
            ).all():
                next_task = session.exec(
                    select(BatchVideoTask)
                    .where(
                        BatchVideoTask.job_id == job.id,
                        BatchVideoTask.status == "ready",
                        BatchVideoTask.external_task_id.is_(None),
                    )
                    .order_by(BatchVideoTask.created_at)
                ).first()
                if next_task:
                    dispatch_task_ids.append(next_task.id)
            task_ids = list(
                session.exec(
                    select(BatchVideoTask.id).where(
                        BatchVideoTask.external_task_id.is_not(None),
                        BatchVideoTask.status.in_(ACTIVE_VIDEO_STATUSES),
                    )
                ).all()
            )
        with self._state_lock:
            self._state.active_task_count = len(set(task_ids + dispatch_task_ids))
            self._state.last_cycle_at = utc_now()

        cycle_errors: list[str] = []
        processed = 0
        for task_id in dispatch_task_ids:
            retry_state = self._retry_state.get(task_id)
            if retry_state is not None and monotonic() < retry_state[1]:
                continue
            with video_task_lock(task_id, blocking=False) as acquired:
                if not acquired:
                    continue
                try:
                    self._dispatch_task(task_id)
                    self._retry_state.pop(task_id, None)
                    processed += 1
                except Exception as cause:
                    cycle_errors.append(f"{task_id}: {self._error_text(cause)}")
                    retry_count = (retry_state[0] if retry_state else 0) + 1
                    retry_delay = min(60, self.settings.video_task_poll_interval_seconds * (2 ** (retry_count - 1)))
                    self._retry_state[task_id] = (retry_count, monotonic() + retry_delay)
                    self._record_dispatch_error(task_id, cause, retry_count, retry_delay)
        for task_id in task_ids:
            retry_state = self._retry_state.get(task_id)
            if retry_state is not None and monotonic() < retry_state[1]:
                continue
            with video_task_lock(task_id, blocking=False) as acquired:
                if not acquired:
                    continue
                try:
                    self._process_task(task_id)
                    self._retry_state.pop(task_id, None)
                    processed += 1
                except Exception as cause:
                    cycle_errors.append(f"{task_id}: {self._error_text(cause)}")
                    retry_count = (retry_state[0] if retry_state is not None else 0) + 1
                    retry_delay = min(
                        60,
                        self.settings.video_task_poll_interval_seconds * (2 ** (retry_count - 1)),
                    )
                    self._retry_state[task_id] = (retry_count, monotonic() + retry_delay)
                    self._record_transient_error(task_id, cause, retry_count, retry_delay)

        active_ids = set(task_ids + dispatch_task_ids)
        for stale_task_id in tuple(self._retry_state):
            if stale_task_id not in active_ids:
                self._retry_state.pop(stale_task_id, None)

        with self._state_lock:
            if cycle_errors:
                self._state.last_error = "；".join(cycle_errors[:3])
            elif processed or not task_ids:
                self._state.last_error = ""
                self._state.last_success_at = utc_now()
        self._sync_job_states()
        return processed

    def _dispatch_task(self, task_id: str) -> None:
        with Session(self.engine) as session:
            task = session.get(BatchVideoTask, task_id)
            job = session.get(BatchVideoJob, task.job_id) if task else None
            if not task or not job or not job.dispatch_enabled or task.status != "ready":
                return
            if job.submission_channel == "jimeng":
                jimeng_cli_submit_task(session, task.id, self.settings, True)
            elif job.submission_channel == "volcengine_seedance25":
                seedance25_mock_submit_task(session, task.id)
            else:
                live_submit_task(session, task.id, self.settings, True)

    def _sync_job_states(self) -> None:
        with Session(self.engine) as session:
            jobs = session.exec(select(BatchVideoJob).where(BatchVideoJob.batch_authorized == True)).all()  # noqa: E712
            for job in jobs:
                tasks = session.exec(select(BatchVideoTask).where(BatchVideoTask.job_id == job.id)).all()
                if not any(task.status == "ready" and not task.external_task_id for task in tasks):
                    job.dispatch_enabled = False
                _update_batch_job_status(session, job)
            session.commit()

    def _run(self) -> None:
        with self._state_lock:
            self._state.running = True
        interval = self.settings.video_task_poll_interval_seconds
        while not self._stop.wait(interval):
            self.run_cycle()

    def _process_task(self, task_id: str) -> None:
        with Session(self.engine) as session:
            task = session.get(BatchVideoTask, task_id)
            if task is None or task.status not in ACTIVE_VIDEO_STATUSES:
                return
            provider = _task_external_provider(session, task.id)
            status = task.status

        with Session(self.engine) as session:
            if provider == "jimeng_cli":
                if status != "completed":
                    jimeng_cli_poll_task(session, task_id, self.settings, True)
                task = session.get(BatchVideoTask, task_id)
                if task is not None and task.status == "completed":
                    jimeng_cli_download_task(session, task_id, self.settings, True)
                return
            if provider == "huimeng_live":
                if status != "completed":
                    live_poll_task(session, task_id, self.settings, True)
                task = session.get(BatchVideoTask, task_id)
                if task is not None and task.status == "completed":
                    live_download_task(
                        session,
                        task_id,
                        self.settings,
                        True,
                        self.settings.projects_root,
                    )
                return
            if provider == "volcengine_seedance25_mock":
                if status != "completed":
                    seedance25_mock_poll_task(session, task_id)
                task = session.get(BatchVideoTask, task_id)
                if task is not None and task.status == "completed":
                    seedance25_mock_download_task(session, task_id, self.settings.projects_root)
                return
            raise RuntimeError("无法识别任务使用的视频服务，后台监控已跳过。")

    def _record_transient_error(
        self,
        task_id: str,
        cause: Exception,
        retry_count: int,
        retry_delay_seconds: int,
    ) -> None:
        with Session(self.engine) as session:
            task = session.get(BatchVideoTask, task_id)
            if task is None:
                return
            run = session.exec(
                select(ProviderRun)
                .where(ProviderRun.task_id == task.id)
                .order_by(ProviderRun.created_at.desc())
            ).first()
            if run is None:
                return
            session.add(
                ProviderRun(
                    task_id=task.id,
                    provider_profile_id=run.provider_profile_id,
                    action="video_supervisor_retry",
                    response_snapshot_json=json.dumps(
                        {
                            "monitor_error": self._error_text(cause),
                            "will_retry": True,
                            "retry_count": retry_count,
                            "retry_delay_seconds": retry_delay_seconds,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
            session.commit()

    def _record_dispatch_error(
        self,
        task_id: str,
        cause: Exception,
        retry_count: int,
        retry_delay_seconds: int,
    ) -> None:
        with Session(self.engine) as session:
            task = session.get(BatchVideoTask, task_id)
            job = session.get(BatchVideoJob, task.job_id) if task else None
            if not task or not job:
                return
            session.add(ProviderRun(
                task_id=task.id,
                provider_profile_id=job.provider_profile_id,
                action="video_supervisor_dispatch_retry",
                response_snapshot_json=json.dumps({
                    "monitor_error": self._error_text(cause),
                    "will_retry": True,
                    "retry_count": retry_count,
                    "retry_delay_seconds": retry_delay_seconds,
                }, ensure_ascii=False),
            ))
            session.commit()

    @staticmethod
    def _error_text(cause: Exception) -> str:
        if isinstance(cause, HTTPException):
            return str(cause.detail)
        return str(cause) or cause.__class__.__name__
