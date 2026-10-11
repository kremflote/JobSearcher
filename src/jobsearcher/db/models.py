"""SQLModel tables (ARCHITECTURE §9).

Datetimes are timezone-aware UTC (`utcnow()`); sqlmodel rejects naive values.
JSON columns hold lists/dicts. Enum-like columns are plain strings whose values are the
Literal types in `jobsearcher.api.schemas`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _json(default: Any = None) -> Any:
    factory = list if default is None else type(default)
    return Field(default_factory=factory, sa_column=Column(JSON, nullable=False))


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    fingerprint: str = Field(index=True)
    title: str
    company: str
    company_slug: str = Field(index=True)
    org_number: str | None = None
    location_text: str | None = None
    municipality: str | None = None
    remote: str | None = None  # none | hybrid | full
    job_type: str = "unknown"  # permanent | trainee | graduate | summer | unknown
    seniority: str | None = None  # entry | unspecified | experienced
    ad_language: str | None = None  # no | en
    description_clean: str | None = None
    ad_text_status: str = "missing"  # present | missing | imported
    prefiltered: bool = False
    """Source filtered on experience/education server side (Finn API, §4.2)."""
    meta: dict = _json({})
    """Source's structured fields (job_meta slice): employment type, occupation, sector, ..."""
    published_at: datetime | None = None
    expires_at: datetime | None = None
    deadline: date | None = None
    deadline_text: str | None = None
    application_url: str | None = None
    application_url_norm: str | None = Field(default=None, index=True)
    first_seen: datetime = Field(default_factory=utcnow)
    last_seen: datetime = Field(default_factory=utcnow)
    active: bool = True
    content_hash: str | None = None
    reposted_from_id: int | None = Field(default=None, foreign_key="jobs.id")
    filtered_out: bool = False
    """Hidden by the hard filter (§5.1) or by the filter agent (seniority experienced)."""


class JobSource(SQLModel, table=True):
    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("source", "source_id"),)

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    source: str  # finn_api | nav | teamtailor | page_watch | manual
    source_id: str | None = None
    url: str | None = None
    raw_path: str | None = None
    fetched_at: datetime = Field(default_factory=utcnow)
    detail_attempts: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    """Failed ad-page fetches so far (Finn, §4.2). Retries are spaced 1, 3, 7 days, then stop."""
    detail_next_at: datetime | None = None
    """Earliest next ad-page retry; None = due now (or never tried)."""


class JobContact(SQLModel, table=True):
    __tablename__ = "job_contacts"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    name: str
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str = "feed"  # feed | llm | manual


class Evaluation(SQLModel, table=True):
    __tablename__ = "evaluations"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    score: int
    confidence: str
    role_category: str
    job_type: str
    seniority: str
    tech: list = _json()
    summary: str
    key_requirements: list = _json()
    match_reasons: list = _json()
    concerns: list = _json()
    model: str
    prompt_version: str
    profile_hash: str
    content_hash: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class HardfilterLog(SQLModel, table=True):
    __tablename__ = "hardfilter_log"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    rule: str
    detail: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Company(SQLModel, table=True):
    __tablename__ = "companies"

    slug: str = Field(primary_key=True)
    name: str
    org_number: str | None = None
    homepage: str | None = None
    note_path: str | None = None
    note_quality: str | None = None  # full | limited
    researched_at: datetime | None = None


class Application(SQLModel, table=True):
    __tablename__ = "applications"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", unique=True)
    status: str = "interessant"
    created_at: datetime = Field(default_factory=utcnow)
    applied_at: datetime | None = None
    follow_up_at: date | None = None
    next_step: str | None = None
    next_step_at: date | None = None
    notes: str | None = None


class ApplicationEvent(SQLModel, table=True):
    __tablename__ = "application_events"

    id: int | None = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="applications.id", index=True)
    from_status: str | None = None
    to_status: str
    at: datetime = Field(default_factory=utcnow)
    comment: str | None = None


class Draft(SQLModel, table=True):
    __tablename__ = "drafts"

    id: int | None = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="applications.id", index=True)
    version: int
    content: str
    author: str  # agent | user
    instruction: str | None = None
    change_summary: str | None = None
    claims_to_verify: list = _json()
    agent_run_id: int | None = Field(default=None, foreign_key="agent_runs.id")
    created_at: datetime = Field(default_factory=utcnow)


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: int | None = Field(default=None, primary_key=True)
    agent: str
    job_ids: list = _json()
    application_id: int | None = None
    backend: str
    model: str
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    status: str = "ok"  # ok | error
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class ScrapeRun(SQLModel, table=True):
    __tablename__ = "scrape_runs"

    id: int | None = Field(default=None, primary_key=True)
    trigger: str  # schedule | manual
    source: str
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    found: int = 0
    new: int = 0
    updated: int = 0
    filtered_out: int = 0
    errors: list = _json()
    health: str = "ok"  # ok | warn | fail


class SourceState(SQLModel, table=True):
    __tablename__ = "source_state"

    source: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    cursor: str | None = None
    etag: str | None = None
    last_success_at: datetime | None = None


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(primary_key=True)
    kind: str  # run | draft | research | revise | rescore | distill
    params: dict = _json({})
    status: str = "queued"  # queued | running | done | failed | cancelled
    progress: float | None = None
    message: str | None = None
    cancel_requested: bool = False
    result: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class SettingsOverride(SQLModel, table=True):
    __tablename__ = "settings_overrides"

    key: str = Field(primary_key=True)
    value: Any = Field(sa_column=Column(JSON, nullable=True))


class ProfileRevision(SQLModel, table=True):
    __tablename__ = "profile_revisions"

    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(index=True)
    content: str
    content_hash: str
    created_at: datetime = Field(default_factory=utcnow)
