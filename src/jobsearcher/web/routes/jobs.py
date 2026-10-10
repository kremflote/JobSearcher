from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from jobsearcher.api.schemas import (
    JobDetail,
    JobList,
    JobSort,
    JobStatusResult,
    JobStatusUpdate,
    JobType,
    RoleCategory,
    SourceName,
    TaskRef,
    TriageStatus,
)
from jobsearcher.db import models as m
from jobsearcher.db.session import get_session
from jobsearcher.tracking.status import InvalidTransition, local_today, triage
from jobsearcher.web import queries
from jobsearcher.web.errors import ApiError, not_implemented

router = APIRouter(tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]


def _get_job(session: Session, job_id: int) -> m.Job:
    job = session.get(m.Job, job_id)
    if job is None:
        raise ApiError(404, "not_found", "Fant ikke jobben.")
    return job


@router.get("/jobs")
def list_jobs(
    session: SessionDep,
    type: JobType | None = None,
    status: TriageStatus | None = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    source: SourceName | None = None,
    deadline_before: date | None = None,
    role: RoleCategory | None = None,
    q: str | None = None,
    sort: JobSort = "deadline",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> JobList:
    offset = queries.decode_cursor(cursor)
    today = local_today()
    since = queries.new_since(session)
    jobs = queries.visible_jobs(session)
    bundle = queries.JobBundle(session, jobs)
    needle = q.strip().lower() if q else ""

    items = []
    for job in jobs:
        item = queries.list_item(job, bundle, since)
        if queries.hidden_as_stale(job, item, today):
            continue
        if type and item.job_type != type:
            continue
        if status and item.status != status:
            continue
        if min_score is not None and (item.score or 0) < min_score:
            continue
        if source and source not in item.sources:
            continue
        if deadline_before and (
            item.deadline is None or item.deadline > deadline_before
        ):
            continue
        if role and item.role_category != role:
            continue
        if needle:
            hay = " ".join(
                x or ""
                for x in (
                    job.title,
                    job.company,
                    job.location_text,
                    job.description_clean,
                )
            ).lower()
            if needle not in hay:
                continue
        items.append(item)

    items = queries.sort_items(items, sort)
    page = items[offset : offset + limit]
    next_cursor = (
        queries.encode_cursor(offset + limit) if offset + limit < len(items) else None
    )
    return JobList(items=page, next_cursor=next_cursor, total=len(items))


@router.get("/jobs/{job_id}")
def get_job(job_id: int, session: SessionDep) -> JobDetail:
    job = _get_job(session, job_id)
    return queries.job_detail(session, job, queries.new_since(session))


@router.put("/jobs/{job_id}/status")
def set_job_status(
    job_id: int, body: JobStatusUpdate, session: SessionDep
) -> JobStatusResult:
    job = _get_job(session, job_id)
    try:
        app = triage(session, job, body.status)
    except InvalidTransition as e:
        raise ApiError(
            409, "invalid_transition", f"{e} Status endres i Tracker."
        ) from e
    session.commit()
    return JobStatusResult(
        job_id=job_id, status=body.status, application_id=app.id if app else None
    )


@router.post("/jobs/{job_id}/draft", status_code=202)
def start_draft(job_id: int) -> TaskRef:
    raise not_implemented()
