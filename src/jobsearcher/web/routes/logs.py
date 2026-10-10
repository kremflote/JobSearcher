from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from jobsearcher.api.schemas import (
    AgentRunEntry,
    AgentRunLog,
    DiscardedEntry,
    DiscardedLog,
    RunLog,
    RunLogEntry,
)
from jobsearcher.db import models as m
from jobsearcher.db.session import get_session

router = APIRouter(prefix="/logs", tags=["logs"])

SessionDep = Annotated[Session, Depends(get_session)]
LOG_LIMIT = 200


@router.get("/runs")
def list_runs(session: SessionDep) -> RunLog:
    rows = session.exec(
        select(m.ScrapeRun)
        .order_by(col(m.ScrapeRun.started_at).desc(), col(m.ScrapeRun.id).desc())
        .limit(LOG_LIMIT)
    ).all()
    return RunLog(
        items=[
            RunLogEntry(
                id=r.id,
                trigger=r.trigger,
                source=r.source,
                started_at=r.started_at,
                finished_at=r.finished_at,
                found=r.found,
                new=r.new,
                updated=r.updated,
                filtered_out=r.filtered_out,
                errors=[str(e) for e in r.errors],
                health=r.health,
            )
            for r in rows
        ]
    )


@router.get("/agent-runs")
def list_agent_runs(session: SessionDep) -> AgentRunLog:
    rows = session.exec(
        select(m.AgentRun)
        .order_by(col(m.AgentRun.created_at).desc(), col(m.AgentRun.id).desc())
        .limit(LOG_LIMIT)
    ).all()
    return AgentRunLog(
        items=[
            AgentRunEntry(
                id=r.id,
                agent=r.agent,
                backend=r.backend,
                model=r.model,
                prompt_version=r.prompt_version,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cost_usd=r.cost_usd,
                duration_ms=r.duration_ms,
                status=r.status,
                error=r.error,
                created_at=r.created_at,
            )
            for r in rows
        ]
    )


@router.get("/discarded")
def list_discarded(session: SessionDep) -> DiscardedLog:
    rows = session.exec(
        select(m.HardfilterLog, m.Job)
        .join(m.Job, col(m.Job.id) == col(m.HardfilterLog.job_id))
        .order_by(
            col(m.HardfilterLog.created_at).desc(), col(m.HardfilterLog.id).desc()
        )
        .limit(LOG_LIMIT)
    ).all()
    return DiscardedLog(
        items=[
            DiscardedEntry(
                id=log.id,
                job_id=job.id,
                title=job.title,
                company=job.company,
                rule=log.rule,
                detail=log.detail,
                created_at=log.created_at,
            )
            for log, job in rows
        ]
    )
