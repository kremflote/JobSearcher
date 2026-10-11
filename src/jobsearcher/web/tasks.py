"""Background tasks (ARCHITECTURE §10.1, FRONTEND §3.3).

Each task is a row in `tasks`, run on a ThreadPoolExecutor with 2 workers in the serve
process. Task functions get a TaskContext for progress and cancellation; `cancel_requested`
is checked by the function between steps via `ctx.should_cancel()`.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlmodel import col, select

from jobsearcher.db.models import Task, utcnow
from jobsearcher.db.session import session_scope

log = logging.getLogger(__name__)

ACTIVE = ("queued", "running")
RESTART_MESSAGE = "Avbrutt ved omstart"


class TaskFailed(Exception):
    """Raise from a task function to fail with a user-facing (Norwegian) message."""


class TaskCancelled(Exception):
    """Raise from a task function when it stops because cancellation was requested."""


class TaskContext:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def progress(self, fraction: float | None, message: str | None = None) -> None:
        with session_scope() as session:
            task = session.get(Task, self.task_id)
            if task is None:
                return
            if fraction is not None:
                task.progress = max(0.0, min(1.0, float(fraction)))
            if message is not None:
                task.message = message
            session.add(task)

    def should_cancel(self) -> bool:
        with session_scope() as session:
            task = session.get(Task, self.task_id)
            return task is None or task.cancel_requested


TaskFn = Callable[[TaskContext], dict[str, Any] | str | None]
"""Returns the task result (dict with application_id/draft_id, plus an optional final `message`
that is stored as the task message, not in the result), a final message, or None."""


class TaskRunner:
    def __init__(self, workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="task"
        )
        self._lock = threading.Lock()

    # --- lifecycle

    def recover(self) -> int:
        """Mark tasks left queued/running by a previous process as failed."""
        with session_scope() as session:
            stale = session.exec(select(Task).where(col(Task.status).in_(ACTIVE))).all()
            for task in stale:
                task.status = "failed"
                task.message = RESTART_MESSAGE
                task.finished_at = utcnow()
                session.add(task)
            return len(stale)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # --- API

    def submit(
        self,
        kind: str,
        params: dict[str, Any],
        fn: TaskFn,
        *,
        guard: Callable[[], None] | None = None,
    ) -> str:
        """Create a queued task row and schedule `fn`. `guard` runs under the runner lock
        before the row is created (e.g. to refuse a second run) and may raise."""
        task_id = uuid.uuid4().hex
        with self._lock:
            if guard is not None:
                guard()
            with session_scope() as session:
                session.add(
                    Task(
                        id=task_id,
                        kind=kind,
                        params=params,
                        status="queued",
                        message="I kø",
                    )
                )
        self._executor.submit(self._run, task_id, fn)
        return task_id

    def cancel(self, task_id: str) -> Task | None:
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None:
                return None
            if task.status == "queued":
                task.cancel_requested = True
                _finish(task, "cancelled", "Avbrutt")
            elif task.status == "running":
                task.cancel_requested = True
                task.message = "Avbryter …"
            session.add(task)
            return task

    # --- worker

    def _run(self, task_id: str, fn: TaskFn) -> None:
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None or task.status != "queued":
                return  # cancelled while queued
            task.status = "running"
            task.progress = 0.0
            session.add(task)
        ctx = TaskContext(task_id)
        status, message, result = "done", None, None
        try:
            out = fn(ctx)
            if isinstance(out, dict):
                result = dict(out)
                message = result.pop("message", None)
            elif isinstance(out, str):
                message = out
            if ctx.should_cancel():
                status, message = "cancelled", "Avbrutt"
        except TaskCancelled:
            status, message = "cancelled", "Avbrutt"
        except TaskFailed as e:
            status, message = "failed", str(e)
        except Exception as e:
            log.exception("Task %s failed", task_id)
            status, message = "failed", f"Feilet: {e}"
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task is None:
                return
            if status == "done":
                task.progress = 1.0
                task.result = result
            _finish(
                task,
                status,
                message or ("Ferdig" if status == "done" else task.message),
            )
            session.add(task)


def _finish(task: Task, status: str, message: str | None) -> None:
    task.status = status
    task.message = message
    task.finished_at = utcnow()


_runner: TaskRunner | None = None
_runner_lock = threading.Lock()


def get_runner() -> TaskRunner:
    """The process-wide runner. Created by the app lifespan; lazily otherwise."""
    global _runner
    with _runner_lock:
        if _runner is None:
            _runner = TaskRunner()
        return _runner


def start_runner() -> TaskRunner:
    runner = get_runner()
    try:
        n = runner.recover()
        if n:
            log.info("Marked %d leftover tasks as failed", n)
    except Exception:
        log.exception("Could not recover leftover tasks")
    return runner


def stop_runner() -> None:
    global _runner
    with _runner_lock:
        if _runner is not None:
            _runner.shutdown()
            _runner = None
