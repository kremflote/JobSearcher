"""API contract v0 (docs/FRONTEND.md §7).

These Pydantic models are the source of truth for the HTTP API. The OpenAPI
document is exported from them (scripts/export_openapi.py) and the frontend's
TypeScript types are generated from that. Change the contract here first.

Response models avoid default values so every field is required (but may be
nullable) in the generated types.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Enums -------------------------------------------------------------------

JobType = Literal["permanent", "trainee", "graduate", "summer", "unknown"]
ApplicationStatus = Literal[
    "ny",
    "interessant",
    "utkast",
    "sokt",
    "intervju",
    "tilbud",
    "ikke_aktuell",
    "avslag",
    "trukket",
    "utlopt",
]
TriageStatus = Literal["interessant", "ikke_aktuell", "ny"]
SourceName = Literal["finn_api", "nav", "teamtailor", "page_watch", "manual"]
RoleCategory = Literal["backend", "frontend", "fullstack", "mobile", "devops", "data", "other"]
Seniority = Literal["entry", "unspecified", "experienced"]
Confidence = Literal["high", "low"]
AdTextStatus = Literal["present", "missing", "imported"]
Remote = Literal["none", "hybrid", "full"]
Health = Literal["ok", "warn", "fail"]
ContactSource = Literal["feed", "llm", "manual"]
TaskKind = Literal["run", "draft", "research", "revise", "rescore", "distill"]
TaskStatus = Literal["queued", "running", "done", "failed", "cancelled"]
DraftAuthor = Literal["agent", "user"]
JobSort = Literal["deadline", "score", "newest"]


class Model(BaseModel):
    # Attribute docstrings become field descriptions in OpenAPI.
    model_config = ConfigDict(use_attribute_docstrings=True)


# --- Common ------------------------------------------------------------------


class ErrorResponse(Model):
    detail: str
    code: str


class TaskRef(Model):
    task_id: str


class HealthStatus(Model):
    status: Literal["ok"]
    version: str


# --- Jobs --------------------------------------------------------------------


class Contact(Model):
    name: str
    role: str | None
    email: str | None
    phone: str | None
    source: ContactSource


class Evaluation(Model):
    score: int = Field(ge=0, le=100)
    confidence: Confidence
    role_category: RoleCategory
    seniority: Seniority
    tech: list[str]
    summary: str
    key_requirements: list[str]
    match_reasons: list[str]
    concerns: list[str]
    model: str
    prompt_version: str
    created_at: datetime


class JobSourceRef(Model):
    source: SourceName
    source_id: str | None
    url: str | None
    fetched_at: datetime


class CompanyNote(Model):
    name: str
    content: str
    """Markdown."""
    quality: Literal["full", "limited"]
    researched_at: datetime


class JobListItem(Model):
    id: int
    title: str
    company: str
    location_text: str | None
    job_type: JobType
    role_category: RoleCategory | None
    status: ApplicationStatus
    """The job's application status; `ny` when no application exists."""
    score: int | None
    deadline: date | None
    deadline_text: str | None
    """Free-text deadline such as "snarest" or "fortløpende"."""
    application_url: str | None
    sources: list[SourceName]
    first_seen: datetime
    is_new: bool
    """First seen after the previous scheduled run."""
    reposted: bool
    ad_text_status: AdTextStatus


class JobList(Model):
    items: list[JobListItem]
    next_cursor: str | None
    total: int


class ApplicationSummary(Model):
    id: int
    status: ApplicationStatus
    latest_draft_id: int | None


class JobDetail(JobListItem):
    municipality: str | None
    remote: Remote | None
    seniority: Seniority | None
    ad_language: Literal["no", "en"] | None
    description: str | None
    """Cleaned ad text; null when only the title is known."""
    published_at: datetime | None
    expires_at: datetime | None
    last_seen: datetime
    reposted_from_id: int | None
    evaluation: Evaluation | None
    contacts: list[Contact]
    source_refs: list[JobSourceRef]
    company_note: CompanyNote | None
    application: ApplicationSummary | None


class JobStatusUpdate(Model):
    status: TriageStatus


class JobStatusResult(Model):
    job_id: int
    status: ApplicationStatus
    application_id: int | None


# --- Applications (tracker) --------------------------------------------------


class ApplicationCard(Model):
    id: int
    job_id: int
    status: ApplicationStatus
    job_title: str
    company: str
    deadline: date | None
    applied_at: datetime | None
    follow_up_at: date | None
    next_step: str | None
    next_step_at: date | None
    contact_name: str | None
    notes: str | None
    created_at: datetime


class ApplicationList(Model):
    items: list[ApplicationCard]


class ApplicationPatch(Model):
    """Only fields present in the request are changed."""

    status: ApplicationStatus | None = None
    next_step: str | None = None
    next_step_at: date | None = None
    follow_up_at: date | None = None
    notes: str | None = None
    comment: str | None = None
    """Stored on the status event when `status` changes."""


class ApplicationEvent(Model):
    id: int
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    at: datetime
    comment: str | None


# --- Drafts ------------------------------------------------------------------


class DraftSummary(Model):
    id: int
    application_id: int
    version: int
    author: DraftAuthor
    instruction: str | None
    change_summary: str | None
    created_at: datetime


class Draft(DraftSummary):
    content: str
    """Markdown."""
    claims_to_verify: list[str]


class DraftCreate(Model):
    content: str


class ReviseRequest(Model):
    instruction: str = Field(min_length=1)


# --- Overview ----------------------------------------------------------------


class NewSinceLast(Model):
    since: datetime | None
    counts_by_type: dict[JobType, int]
    top: list[JobListItem]


class SourceStatus(Model):
    source: SourceName
    health: Health | None
    last_run_at: datetime | None
    found: int | None
    new: int | None
    message: str | None


class CostStatus(Model):
    month_usd: float
    cap_usd: float
    warn: bool
    """True at ≥ 80 % of the cap."""


class Overview(Model):
    deadlines: list[JobListItem]
    new_since_last: NewSinceLast
    follow_ups: list[ApplicationCard]
    sources: list[SourceStatus]
    cost: CostStatus
    last_run_at: datetime | None


# --- Tasks -------------------------------------------------------------------


class TaskResult(Model):
    application_id: int | None
    draft_id: int | None


class Task(Model):
    id: str
    kind: TaskKind
    status: TaskStatus
    progress: float | None = Field(ge=0, le=1)
    message: str | None
    created_at: datetime
    finished_at: datetime | None
    result: TaskResult | None


# --- Profile -----------------------------------------------------------------


class ProfileFileInfo(Model):
    path: str
    """Relative to PROFILE_DIR, forward slashes."""
    size: int
    updated_at: datetime


class ProfileTree(Model):
    files: list[ProfileFileInfo]
    profile_hash: str
    derived_outdated: bool


class ProfileFile(Model):
    path: str
    content: str
    content_hash: str
    updated_at: datetime


class ProfileFileWrite(Model):
    content: str
    base_hash: str | None = None
    """Hash the edit started from; a mismatch gives 409."""


class ProfileRevision(Model):
    id: int
    path: str
    content: str
    content_hash: str
    created_at: datetime


# --- Settings ----------------------------------------------------------------


class SettingItem(Model):
    key: str
    """Dotted key, e.g. `search.geo_mode`."""
    section: str
    value: Any
    default: Any
    """Value from config/*.yaml."""
    overridden: bool


class Settings(Model):
    items: list[SettingItem]


class SettingsPatch(Model):
    values: dict[str, Any]
    """Key → new value. `null` removes the override."""


# --- Logs --------------------------------------------------------------------


class RunLogEntry(Model):
    id: int
    trigger: Literal["schedule", "manual"]
    source: SourceName
    started_at: datetime
    finished_at: datetime | None
    found: int
    new: int
    updated: int
    filtered_out: int
    errors: list[str]
    health: Health


class AgentRunEntry(Model):
    id: int
    agent: str
    backend: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int
    status: Literal["ok", "error"]
    error: str | None
    created_at: datetime


class DiscardedEntry(Model):
    id: int
    job_id: int
    title: str
    company: str
    rule: str
    detail: str | None
    created_at: datetime


class RunLog(Model):
    items: list[RunLogEntry]


class AgentRunLog(Model):
    items: list[AgentRunEntry]


class DiscardedLog(Model):
    items: list[DiscardedEntry]
