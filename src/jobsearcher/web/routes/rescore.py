""""Score på nytt" (ARCHITECTURE §5.5, FRONTEND §5.7): jobs scored with an older profile or prompt."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, func, select

from jobsearcher.api.schemas import RescoreEstimate, TaskRef
from jobsearcher.db import models as m
from jobsearcher.db.session import get_session, session_scope
from jobsearcher.web.errors import ApiError
from jobsearcher.web.tasks import ACTIVE, TaskCancelled, TaskContext, TaskFailed, get_runner

router = APIRouter(tags=["rescore"])

SessionDep = Annotated[Session, Depends(get_session)]
DEFAULT_COST_PER_JOB = 0.001  # DeepSeek V4.1 Flash, spike 05
ESTIMATE_DAYS = 30
SKIPPED = {"cost_cap": "Kostnadstaket for denne måneden er nådd."}


def cost_per_job(session: Session) -> float:
    """Average filter cost per scored job over the last 30 days, or the default without data."""
    since = datetime.now(UTC) - timedelta(days=ESTIMATE_DAYS)
    cost = session.exec(
        select(func.coalesce(func.sum(m.AgentRun.cost_usd), 0.0)).where(
            m.AgentRun.agent == "filter", m.AgentRun.created_at >= since
        )
    ).one()
    scored = session.exec(select(func.count()).select_from(m.Evaluation).where(m.Evaluation.created_at >= since)).one()
    return float(cost) / scored if scored and cost else DEFAULT_COST_PER_JOB


@router.get("/rescore")
def rescore_estimate(session: SessionDep) -> RescoreEstimate:
    from jobsearcher.agents.filter import stale_jobs

    n = len(stale_jobs(session))
    per_job = cost_per_job(session)
    return RescoreEstimate(stale_jobs=n, estimated_cost_usd=round(n * per_job, 4), cost_per_job_usd=round(per_job, 5))


def _ensure_none_active() -> None:
    with session_scope() as session:
        active = session.exec(
            select(m.Task.id).where(col(m.Task.kind).in_(("rescore", "run")), col(m.Task.status).in_(ACTIVE))
        ).first()
    if active is not None:
        raise ApiError(409, "rescore_active", "Det pågår allerede en scoring eller kjøring.")


def _rescore_task(ctx: TaskContext) -> str:
    from jobsearcher.agents.filter import rescore

    with session_scope() as session:
        summary = rescore(session, should_cancel=ctx.should_cancel, progress=ctx.progress)
    if ctx.should_cancel():
        raise TaskCancelled
    if summary.skipped_reason and not summary.scored:
        raise TaskFailed(SKIPPED.get(summary.skipped_reason, f"Ingen jobber scoret: {summary.skipped_reason}"))
    message = f"Ferdig: {summary.scored} jobber scoret på nytt"
    return message + (f" ({summary.failed} feilet)" if summary.failed else "")


@router.post("/rescore", status_code=202)
def start_rescore() -> TaskRef:
    return TaskRef(task_id=get_runner().submit("rescore", {}, _rescore_task, guard=_ensure_none_active))
