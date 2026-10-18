from __future__ import annotations

from contextlib import contextmanager
from threading import Lock, RLock


_registry_lock = Lock()
_task_locks: dict[str, RLock] = {}


def _lock_for(task_id: str) -> RLock:
    with _registry_lock:
        return _task_locks.setdefault(task_id, RLock())


@contextmanager
def video_task_lock(task_id: str, *, blocking: bool = True):
    lock = _lock_for(task_id)
    acquired = lock.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
