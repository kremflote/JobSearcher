"""Source interface (ARCHITECTURE §4.1).

A source returns `RawJob`s with as many structured fields as it has. The pipeline
(`jobsearcher.pipeline`) normalizes, dedupes, filters and stores them. Each source keeps
its own cursors in `source_state`, keyed by (source, key), e.g. one key per Finn search.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from jobsearcher.api.schemas import Health, JobType, Remote, SourceName


class RawContact(BaseModel):
    name: str
    role: str | None = None
    email: str | None = None
    phone: str | None = None


class RawJob(BaseModel):
    source: SourceName
    source_id: str
    url: str | None = None
    """The ad on the source (Finn ad page, NAV ad)."""
    title: str
    company: str | None = None
    org_number: str | None = None
    location_text: str | None = None
    municipality: str | None = None
    """Municipality name as the source gives it; normalized by the pipeline."""
    county: str | None = None
    country: str | None = None
    remote: Remote | None = None
    published_at: datetime | None = None
    """Timezone-aware (UTC)."""
    expires_at: datetime | None = None
    deadline: date | None = None
    deadline_text: str | None = None
    application_url: str | None = None
    description_html: str | None = None
    """Raw ad text (HTML or plain). Cleaned by pipeline/clean.py. None = not fetched yet."""
    job_type_hint: JobType | None = None
    employment_type: str | None = None
    occupation: list[str] = Field(default_factory=list)
    """Source's occupation categories (NAV: occupationCategories/STYRK names)."""
    contacts: list[RawContact] = Field(default_factory=list)
    prefiltered: bool = False
    """True when the source filtered experience/education server side (Finn API)."""
    needs_detail: bool = False
    """True when the ad text must be fetched with `fetch_details` after the hard filter."""
    active: bool = True
    """False when the source says the ad is withdrawn/expired (NAV INACTIVE)."""
    raw_path: str | None = None
    """Path of the raw response in DATA_DIR/cache, relative to DATA_DIR."""
    meta: dict[str, Any] = Field(default_factory=dict)
    """Other structured fields for the job_meta slice (sector, extent, search ids, ...)."""


@dataclass
class CursorState:
    cursor: str | None = None
    etag: str | None = None


class CollectResult(BaseModel):
    jobs: list[RawJob] = Field(default_factory=list)
    state: dict[str, CursorState] = Field(default_factory=dict)
    """New cursor per key; written to source_state only when the run succeeds."""
    found: int = 0
    errors: list[str] = Field(default_factory=list)
    health: Health = "ok"
    message: str | None = None
    """Short status for the dashboard, e.g. "NAV-feeden svarte 401: token utløpt?"."""

    model_config = {"arbitrary_types_allowed": True}


class JobSource(Protocol):
    name: SourceName

    def collect(self, state: dict[str, CursorState]) -> CollectResult:
        """Fetch new and changed ads since the cursors in `state`."""
        ...

    def fetch_details(self, jobs: list[RawJob]) -> list[RawJob]:
        """Fill `description_html` (and other fields) for jobs with `needs_detail`.

        Called by the pipeline only for new jobs that passed the hard filter. Failures
        leave `description_html = None`; the job is stored with ad_text_status=missing and
        retried next run.
        """
        ...
