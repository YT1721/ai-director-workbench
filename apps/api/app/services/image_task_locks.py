from __future__ import annotations

from contextlib import contextmanager
from threading import Lock


_registry_lock = Lock()
_job_locks: dict[str, Lock] = {}


@contextmanager
def image_task_lock(job_id: str, *, blocking: bool = True):
    with _registry_lock:
        lock = _job_locks.setdefault(job_id, Lock())
    acquired = lock.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
