from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

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
from jobsearcher.web.errors import not_implemented

router = APIRouter(tags=["jobs"])


@router.get("/jobs")
def list_jobs(
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
    raise not_implemented()


@router.get("/jobs/{job_id}")
def get_job(job_id: int) -> JobDetail:
    raise not_implemented()


@router.put("/jobs/{job_id}/status")
def set_job_status(job_id: int, body: JobStatusUpdate) -> JobStatusResult:
    raise not_implemented()


@router.post("/jobs/{job_id}/draft", status_code=202)
def start_draft(job_id: int) -> TaskRef:
    raise not_implemented()
