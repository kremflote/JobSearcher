"""Job and application lifecycle after collection (ARCHITECTURE §9.1, §11, §12).

Each function does one thing, takes `now` for testability and returns a count.
"""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete
from sqlmodel import Session, select

from jobsearcher.config import today as config_today
from jobsearcher.config import Settings, env
from jobsearcher.db.models import Application, ApplicationEvent, Job, JobContact, JobSource

log = logging.getLogger(__name__)

# Statuses that become `utlopt` when the deadline passes (§9.1: not applied).
EXPIRABLE_STATUSES = ("ny", "interessant", "utkast")
OSLO = ZoneInfo("Europe/Oslo")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def deactivate_sources_reported_inactive(session: Session, source: str, source_ids: list[str]) -> int:
    """Mark jobs inactive whose ad the source reported withdrawn/expired."""
    if not source_ids:
        return 0
    jobs = session.exec(
        select(Job)
        .join(JobSource, JobSource.job_id == Job.id)
        .where(JobSource.source == source, JobSource.source_id.in_(source_ids), Job.active == True)  # noqa: E712
    ).all()
    for job in jobs:
        job.active = False
        session.add(job)
    return len(jobs)


def expire_jobs(session: Session, now: datetime | None = None) -> int:
    """Active jobs whose `expires_at` has passed become inactive."""
    now = now or datetime.now(UTC)
    count = 0
    for job in session.exec(select(Job).where(Job.active == True, Job.expires_at.is_not(None))):  # noqa: E712
        if _aware(job.expires_at) < now:
            job.active = False
            session.add(job)
            count += 1
    return count


def expire_applications(session: Session, today: date | None = None) -> int:
    """Applications not yet sent whose job deadline (Oslo date) has passed become `utlopt`."""
    today = today or datetime.now(OSLO).date()
    rows = session.exec(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.status.in_(EXPIRABLE_STATUSES), Job.deadline.is_not(None), Job.deadline < today)
    ).all()
    now = datetime.now(UTC)
    for app, _job in rows:
        session.add(ApplicationEvent(application_id=app.id, from_status=app.status, to_status="utlopt", at=now))
        app.status = "utlopt"
        session.add(app)
    return len(rows)


def purge_contacts(session: Session, days: int, now: datetime | None = None) -> int:
    """Delete feed/LLM contacts of jobs inactive for `days` days without an application.

    "Inactive since" is approximated by the later of `last_seen` and `expires_at`.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=days)
    jobs = session.exec(
        select(Job)
        .outerjoin(Application, Application.job_id == Job.id)
        .where(Job.active == False, Application.id.is_(None))  # noqa: E712
    ).all()
    ids = []
    for job in jobs:
        since = max(d for d in (_aware(job.last_seen), _aware(job.expires_at)) if d is not None)
        if since < cutoff:
            ids.append(job.id)
    if not ids:
        return 0
    result = session.exec(delete(JobContact).where(JobContact.job_id.in_(ids)))  # type: ignore[call-overload]
    return result.rowcount or 0


def purge_raw_cache(days: int, today: date | None = None, cache_dir: Path | None = None) -> int:
    """Delete DATA_DIR/cache/<source>/<YYYY-MM-DD> folders older than `days`. Returns folders removed."""
    today = today or config_today()
    cache_dir = cache_dir or env().cache_dir
    if not cache_dir.exists():
        return 0
    cutoff = today - timedelta(days=days)
    removed = 0
    for source_dir in cache_dir.iterdir():
        if not source_dir.is_dir():
            continue
        for day_dir in source_dir.iterdir():
            try:
                day = date.fromisoformat(day_dir.name)
            except ValueError:
                continue
            if day_dir.is_dir() and day < cutoff:
                shutil.rmtree(day_dir, ignore_errors=True)
                removed += 1
    return removed


def run_lifecycle(session: Session, settings: Settings, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    return {
        "jobs_expired": expire_jobs(session, now),
        "applications_expired": expire_applications(session, now.astimezone(OSLO).date()),
        "contacts_deleted": purge_contacts(session, settings.retention.contacts_days_after_inactive, now),
        "cache_dirs_deleted": purge_raw_cache(settings.retention.raw_cache_days, now.date()),
    }
