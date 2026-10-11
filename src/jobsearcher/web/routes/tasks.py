from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from jobsearcher.api.schemas import Task, TaskRef
from jobsearcher.db import models as m
from jobsearcher.db.session import get_session
from jobsearcher.web.errors import ApiError
from jobsearcher.web.queries import task_out
from jobsearcher.web.tasks import (
    ACTIVE,
    TaskCancelled,
    TaskContext,
    TaskFailed,
    get_runner,
)

router = APIRouter(tags=["tasks"])

SessionDep = Annotated[Session, Depends(get_session)]
TASK_LIST_LIMIT = 50


def _run_active_error() -> ApiError:
    return ApiError(409, "run_active", "En kjøring pågår allerede.")


def _ensure_no_run() -> None:
    from jobsearcher.db.session import session_scope

    with session_scope() as session:
        active = session.exec(
            select(m.Task.id).where(
                m.Task.kind == "run", col(m.Task.status).in_(ACTIVE)
            )
        ).first()
    if active is not None or _lock_held():
        raise _run_active_error()


def _lock_held() -> bool:
    """A CLI or scheduled run holding data/run.lock. Taking and releasing the lock is the
    public way to ask; it also clears a stale lock."""
    from jobsearcher.pipeline.lock import RunLock, RunLockedError

    lock = RunLock()
    try:
        lock.acquire()
    except RunLockedError:
        return True
    lock.release()
    return False


def _summary_message(summary: object) -> str:
    sources = getattr(summary, "sources", None) or []
    new = sum(getattr(src, "new", 0) or 0 for src in sources)
    failed = [src.source for src in sources if getattr(src, "health", "ok") == "fail"]
    message = "Ferdig: ingen nye jobber" if new == 0 else f"Ferdig: {new} nye jobber"
    if failed:
        message += f" (feil: {', '.join(failed)})"
    skipped = [src.source for src in sources if getattr(src, "skipped", False)]
    if skipped:
        message += f" ({', '.join(skipped)} hoppet over: hentet nylig)"
    return message


def make_run_task(trigger: str = "manual"):
    def run_task(ctx: TaskContext) -> str:
        return _run(ctx, trigger)

    return run_task


def submit_run(trigger: str = "manual") -> str:
    """Queue a pipeline run as a task. Raises 409 `run_active` if one is running."""
    return get_runner().submit("run", {"trigger": trigger}, make_run_task(trigger), guard=_ensure_no_run)


def _run(ctx: TaskContext, trigger: str) -> str:
    from jobsearcher.pipeline.lock import RunLockedError
    from jobsearcher.pipeline.run import run_pipeline

    try:
        summary = run_pipeline(
            trigger=trigger, progress=ctx.progress, should_cancel=ctx.should_cancel
        )
    except RunLockedError as e:
        raise TaskFailed("En kjøring pågår allerede.") from e
    if getattr(summary, "cancelled", False):
        raise TaskCancelled
    return _summary_message(summary)


@router.post("/runs", status_code=202)
def start_run() -> TaskRef:
    return TaskRef(task_id=submit_run("manual"))


@router.get("/tasks")
def list_tasks(session: SessionDep, active: bool = False) -> list[Task]:
    query = select(m.Task).order_by(col(m.Task.created_at).desc())
    if active:
        query = query.where(col(m.Task.status).in_(ACTIVE))
    else:
        query = query.limit(TASK_LIST_LIMIT)
    return [task_out(t) for t in session.exec(query).all()]


@router.get("/tasks/{task_id}")
def get_task(task_id: str, session: SessionDep) -> Task:
    task = session.get(m.Task, task_id)
    if task is None:
        raise ApiError(404, "not_found", "Fant ikke bakgrunnsjobben.")
    return task_out(task)


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str) -> Task:
    task = get_runner().cancel(task_id)
    if task is None:
        raise ApiError(404, "not_found", "Fant ikke bakgrunnsjobben.")
    return task_out(task)
