from __future__ import annotations

import json
from threading import Event, Lock, Thread

from fastapi import HTTPException
from sqlmodel import Session, select

from app.config import Settings
from app.models.videos import VpBlock, VpGenerationJob
from app.models.workbench import Episode, Scene, Shot, utc_now
from app.schemas.videos import VpBlockCreate, VpGenerationJobView
from app.schemas.workflows import AiTextRunCreate
from app.services.video_constraints import recommend_video_duration
from app.services.videos import create_ai_vp_block


ACTIVE_STATUSES = ("queued", "running", "retrying")
_create_lock = Lock()


def _plan(job: VpGenerationJob) -> list[dict[str, object]]:
    try:
        value = json.loads(job.shot_plan_json or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def vp_generation_job_view(job: VpGenerationJob) -> VpGenerationJobView:
    return VpGenerationJobView(
        id=job.id,
        project_id=job.project_id,
        scene_id=job.scene_id,
        operation=job.operation,
        status=job.status,
        total_count=len(_plan(job)),
        completed_count=job.completed_count,
        failed_count=job.failed_count,
        current_shot_code=job.current_shot_code,
        message=job.message,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def latest_vp_generation_job(session: Session, scene_id: str) -> VpGenerationJob | None:
    return session.exec(
        select(VpGenerationJob)
        .where(VpGenerationJob.scene_id == scene_id)
        .order_by(VpGenerationJob.created_at.desc())
    ).first()


def create_duration_rebuild_job(
    session: Session,
    scene_id: str,
    confirm_live_request: bool,
) -> VpGenerationJob:
    if not confirm_live_request:
        raise HTTPException(400, "后台重建会调用真实文本 AI，请先确认本次生成。")
    scene = session.get(Scene, scene_id)
    episode = session.get(Episode, scene.episode_id) if scene else None
    if scene is None or episode is None:
        raise HTTPException(404, "场景不存在。")

    with _create_lock:
        active = session.exec(
            select(VpGenerationJob)
            .where(
                VpGenerationJob.scene_id == scene_id,
                VpGenerationJob.status.in_(ACTIVE_STATUSES),
            )
            .order_by(VpGenerationJob.created_at.desc())
        ).first()
        if active is not None:
            return active

        plan: list[dict[str, object]] = []
        shots = session.exec(
            select(Shot)
            .where(Shot.scene_id == scene_id, Shot.is_archived == False)  # noqa: E712
            .order_by(Shot.shot_code)
        ).all()
        for shot in shots:
            latest = session.exec(
                select(VpBlock)
                .where(
                    VpBlock.shot_id == shot.id,
                    VpBlock.schema_version == "vp_precision_18_v1",
                    VpBlock.package_stage == "director_draft",
                )
                .order_by(VpBlock.version_number.desc())
            ).first()
            recommended, reason = recommend_video_duration(shot.name)
            if latest is not None and latest.duration_seconds == 5 and recommended != 5:
                plan.append({
                    "shot_id": shot.id,
                    "shot_code": shot.shot_code,
                    "duration_seconds": recommended,
                    "reason": reason,
                })

        job = VpGenerationJob(
            project_id=episode.project_id,
            scene_id=scene.id,
            shot_plan_json=json.dumps(plan, ensure_ascii=False),
            status="queued" if plan else "completed",
            message=f"等待后台重建 {len(plan)} 个镜头" if plan else "当前没有需要重建的旧版 5 秒镜头",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def retry_vp_generation_job(session: Session, job_id: str) -> VpGenerationJob:
    job = session.get(VpGenerationJob, job_id)
    if job is None:
        raise HTTPException(404, "提示词后台任务不存在。")
    if job.status != "failed":
        return job
    job.status = "queued"
    job.retry_count = 0
    job.error_message = ""
    job.message = "已重新加入后台队列"
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def cancel_vp_generation_job(session: Session, job_id: str) -> VpGenerationJob:
    job = session.get(VpGenerationJob, job_id)
    if job is None:
        raise HTTPException(404, "提示词后台任务不存在。")
    if job.status not in ACTIVE_STATUSES:
        return job
    total = len(_plan(job))
    job.status = "cancelled"
    job.message = f"已停止后续重建，保留已完成的 {job.completed_count}/{total} 个镜头"
    job.error_message = ""
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


class VpGenerationSupervisor:
    def __init__(self, engine, settings: Settings) -> None:
        self.engine = engine
        self.settings = settings
        self._stop = Event()
        self._wake = Event()
        self._thread: Thread | None = None
        self._cycle_lock = Lock()

    def start(self) -> None:
        if not self.settings.content_task_supervisor_enabled or self._thread is not None:
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="vp-generation-supervisor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2, self.settings.content_task_poll_interval_seconds + 1))
        self._thread = None

    def wake(self) -> None:
        self._wake.set()

    def run_cycle(self) -> int:
        if not self._cycle_lock.acquire(blocking=False):
            return 0
        try:
            with Session(self.engine) as session:
                job = session.exec(
                    select(VpGenerationJob)
                    .where(VpGenerationJob.status.in_(ACTIVE_STATUSES))
                    .order_by(VpGenerationJob.created_at)
                ).first()
                if job is None:
                    return 0
                job_id = job.id
            self._process_next(job_id)
            return 1
        finally:
            self._cycle_lock.release()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.run_cycle()
            self._wake.wait(self.settings.content_task_poll_interval_seconds)
            self._wake.clear()

    def _process_next(self, job_id: str) -> None:
        with Session(self.engine) as session:
            job = session.get(VpGenerationJob, job_id)
            if job is None or job.status not in ACTIVE_STATUSES:
                return
            plan = _plan(job)
            if job.current_index >= len(plan):
                self._complete(session, job)
                return
            item = plan[job.current_index]
            shot_id = str(item.get("shot_id") or "")
            shot_code = str(item.get("shot_code") or "")
            duration = int(item.get("duration_seconds") or 0)
            latest = session.exec(
                select(VpBlock)
                .where(
                    VpBlock.shot_id == shot_id,
                    VpBlock.schema_version == "vp_precision_18_v1",
                    VpBlock.package_stage == "director_draft",
                )
                .order_by(VpBlock.version_number.desc())
            ).first()
            if latest is not None and latest.duration_seconds == duration:
                self._advance(session, job, shot_code, len(plan))
                return
            job.status = "running"
            job.current_shot_code = shot_code
            job.message = f"正在后台重建 {shot_code}（{job.completed_count + 1}/{len(plan)}）"
            job.error_message = ""
            job.updated_at = utc_now()
            session.add(job)
            session.commit()

        try:
            with Session(self.engine) as generation_session:
                create_ai_vp_block(
                    generation_session,
                    self.settings,
                    shot_id,
                    VpBlockCreate(
                        has_character=True,
                        package_stage="director_draft",
                        duration_seconds=duration,
                    ),
                    AiTextRunCreate(
                        module_type="vp_precision_18",
                        target_type="shot",
                        target_id=shot_id,
                        confirm_live_request=True,
                    ),
                )
        except Exception as cause:
            self._record_error(job_id, shot_code, cause)
            return

        with Session(self.engine) as session:
            job = session.get(VpGenerationJob, job_id)
            if job is not None and job.status in ACTIVE_STATUSES:
                self._advance(session, job, shot_code, len(_plan(job)))

    def _advance(self, session: Session, job: VpGenerationJob, shot_code: str, total: int) -> None:
        job.current_index += 1
        job.completed_count = min(job.current_index, total)
        job.current_shot_code = shot_code
        job.retry_count = 0
        job.error_message = ""
        job.updated_at = utc_now()
        if job.current_index >= total:
            self._complete(session, job)
            return
        job.status = "queued"
        job.message = f"已完成 {job.completed_count}/{total}，继续后台处理"
        session.add(job)
        session.commit()
        self.wake()

    @staticmethod
    def _complete(session: Session, job: VpGenerationJob) -> None:
        total = len(_plan(job))
        job.status = "completed"
        job.completed_count = total
        job.current_index = total
        job.current_shot_code = ""
        job.message = f"已完成 {total}/{total} 个镜头的时长重建"
        job.error_message = ""
        job.updated_at = utc_now()
        session.add(job)
        session.commit()

    def _record_error(self, job_id: str, shot_code: str, cause: Exception) -> None:
        message = str(cause.detail) if isinstance(cause, HTTPException) else str(cause) or cause.__class__.__name__
        with Session(self.engine) as session:
            job = session.get(VpGenerationJob, job_id)
            if job is None or job.status not in ACTIVE_STATUSES:
                return
            job.retry_count += 1
            job.current_shot_code = shot_code
            job.error_message = message
            job.updated_at = utc_now()
            if job.retry_count >= job.max_retries:
                job.failed_count = 1
                job.status = "failed"
                job.message = f"{shot_code} 连续失败，后台任务已暂停"
            else:
                job.status = "retrying"
                job.message = f"{shot_code} 暂时失败，后台将自动重试（{job.retry_count}/{job.max_retries}）"
            session.add(job)
            session.commit()
