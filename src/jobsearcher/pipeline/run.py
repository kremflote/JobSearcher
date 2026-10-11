"""One collection run (ARCHITECTURE §11): sources → normalize → dedupe → hard filter →
details → clean → lifecycle → filter agent → digest (scheduled runs) → backup.

Each source runs in its own transaction; one failing source does not stop the others.
Cursors are persisted only after the source's jobs are stored and its health is not `fail`.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, or_, select

from jobsearcher.api.schemas import Health
from jobsearcher.config import Locations, Settings, env, load_locations, load_settings
from jobsearcher.db.models import Job, JobContact, JobSource, ScrapeRun, SettingsOverride, SourceState
from jobsearcher.db.session import get_engine, session_scope
from jobsearcher.pipeline import clean as C
from jobsearcher.pipeline import hardfilter as H
from jobsearcher.pipeline import normalize as N
from jobsearcher.pipeline.dedupe import SOURCE_PRIORITY, find_match, primary_priority
from jobsearcher.pipeline.lifecycle import deactivate_sources_reported_inactive, run_lifecycle
from jobsearcher.pipeline.lock import RunLock
from jobsearcher.sources.base import CursorState, JobSource as SourceProtocol, RawJob

log = logging.getLogger(__name__)

Progress = Callable[[float, str], None]
Cancel = Callable[[], bool]

OSLO = ZoneInfo("Europe/Oslo")
DETAIL_RETRY_DAYS = 14
"""Jobs still missing ad text are retried by `fetch_details` for this many days."""
DETAIL_RETRY_MAX = 30
DETAIL_RETRY_DELAYS_DAYS = (1, 3, 7)
"""Wait after the 1st, 2nd, 3rd failed ad-page attempt; after that the job is not retried.
Counts only attempts the source reports (`RawJob.detail_attempted`)."""
DETAIL_RETRY_SLACK = timedelta(hours=2)
"""Retries fall due a little early, so the daily start jitter never pushes them a day."""
BOILERPLATE_SAMPLE = 50
"""Max other ads from the same employer compared for boilerplate."""


class SourceSummary(BaseModel):
    source: str
    found: int = 0
    new: int = 0
    updated: int = 0
    filtered_out: int = 0
    details_fetched: int = 0
    health: Health = "ok"
    errors: list[str] = Field(default_factory=list)
    message: str | None = None
    skipped: bool = False
    """The source declined to run (cooldown); see `message`."""


class RunSummary(BaseModel):
    trigger: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_s: float = 0.0
    sources: list[SourceSummary] = Field(default_factory=list)
    lifecycle: dict[str, int] = Field(default_factory=dict)
    scored: int = 0
    score_failed: int = 0
    score_skipped_reason: str | None = None
    backup_path: str | None = None
    digest: str | None = None
    """What happened to the e-mail digest (scheduled runs only)."""
    cancelled: bool = False


# --- Helpers ------------------------------------------------------------------------


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def load_effective_settings(session: Session) -> Settings:
    """settings.yaml with the dashboard's `settings_overrides` on top."""
    from jobsearcher.db.repo import effective_settings

    return effective_settings(session)


def _load_state(session: Session, source: str) -> dict[str, CursorState]:
    rows = session.exec(select(SourceState).where(SourceState.source == source))
    return {
        r.key: CursorState(cursor=r.cursor, etag=r.etag, last_success_at=_aware(r.last_success_at))
        for r in rows
    }


def _save_state(session: Session, source: str, state: dict[str, CursorState], now: datetime) -> None:
    for key, cs in state.items():
        row = session.get(SourceState, (source, key)) or SourceState(source=source, key=key)
        row.cursor, row.etag, row.last_success_at = cs.cursor, cs.etag, now
        session.add(row)


# --- Upsert -------------------------------------------------------------------------


@dataclass
class Upserted:
    job: Job
    raw: RawJob
    is_new: bool
    content_changed: bool


_MERGE_FIELDS = (
    "org_number", "location_text", "published_at", "expires_at", "deadline", "deadline_text",
    "application_url",
)


def _set_text(session: Session, job: Job, full_text: str, settings: Settings) -> None:
    """Store cleaned text (employer boilerplate shortened) and its hash in meta."""
    stmt = select(Job.description_clean).where(
        Job.company_slug == job.company_slug, Job.description_clean.is_not(None)
    )
    if job.id is not None:
        stmt = stmt.where(Job.id != job.id)
    others: list[str] = []
    if job.company_slug != N.UNKNOWN_SLUG:
        others = [t for t in session.exec(stmt.order_by(Job.id.desc()).limit(BOILERPLATE_SAMPLE)) if t]
    job.description_clean = C.shorten_boilerplate(full_text, others, settings.clean.boilerplate_min_ads)
    job.ad_text_status = "present"
    job.meta = {**(job.meta or {}), "text_hash": N.text_hash(full_text)}
    job.ad_language = N.ad_language(job.title, full_text)
    if job.remote is None:
        job.remote = N.detect_remote(None, job.title, job.location_text, full_text)


def apply_raw(session: Session, job: Job, raw: RawJob, settings: Settings, *, overwrite: bool) -> None:
    """Copy a RawJob onto a Job. `overwrite=False` (lower-priority source) only fills gaps."""

    def put(field: str, value: Any) -> None:
        if value is None or value == "" or value == []:
            return
        if overwrite or getattr(job, field) in (None, ""):
            setattr(job, field, value)

    if overwrite or not job.title:
        job.title = raw.title.strip()
    if raw.company and (overwrite or not job.company or job.company == N.UNKNOWN_COMPANY):
        job.company = raw.company.strip()
    if not job.company:
        job.company = N.UNKNOWN_COMPANY
    for field in _MERGE_FIELDS:
        put(field, getattr(raw, field))
    put("municipality", N.municipality(raw.municipality, raw.location_text))
    put("application_url_norm", N.normalize_url(raw.application_url))
    put("remote", raw.remote)
    jt = N.job_type(raw.job_type_hint, raw.title, raw.employment_type)
    if jt != "unknown" and (overwrite or job.job_type in (None, "unknown")):
        job.job_type = jt
    job.prefiltered = bool(job.prefiltered) or raw.prefiltered

    extra = dict(raw.meta)
    if raw.employment_type:
        extra["employment_type"] = raw.employment_type
    if raw.occupation:
        extra["occupation"] = raw.occupation
    if raw.country:
        extra["country"] = raw.country
    if raw.county:
        extra["county"] = raw.county
    meta = dict(job.meta or {})
    for k, v in extra.items():
        if overwrite or k not in meta:
            meta[k] = v
    job.meta = meta

    full_text = C.html_to_markdown(raw.description_html)
    if full_text and (overwrite or not job.description_clean):
        _set_text(session, job, full_text, settings)
    if job.remote is None:
        job.remote = N.detect_remote(None, job.title, job.location_text, None)

    job.company_slug = N.company_slug(None if job.company == N.UNKNOWN_COMPANY else job.company)
    job.fingerprint = N.fingerprint(job.company, job.title, job.municipality)
    job.content_hash = N.content_hash(
        title=job.title,
        company=job.company,
        location_text=job.location_text,
        deadline=job.deadline,
        deadline_text=job.deadline_text,
        application_url=job.application_url,
        text_digest=(job.meta or {}).get("text_hash"),
    )


def _add_contacts(session: Session, job: Job, raw: RawJob) -> None:
    if not raw.contacts:
        return
    existing = session.exec(select(JobContact).where(JobContact.job_id == job.id)).all()
    seen = {(c.name.strip().lower(), (c.email or "").lower()) for c in existing}
    for c in raw.contacts:
        key = (c.name.strip().lower(), (c.email or "").lower())
        if not c.name.strip() or key in seen:
            continue
        seen.add(key)
        session.add(JobContact(job_id=job.id, name=c.name.strip(), role=c.role, email=c.email, phone=c.phone, source="feed"))


def upsert_raw(session: Session, raw: RawJob, settings: Settings, now: datetime) -> Upserted:
    """Match a RawJob to an existing job (§4.5) and merge, or create a new job."""
    company = raw.company.strip() if raw.company else None
    municipality = N.municipality(raw.municipality, raw.location_text)
    match = find_match(
        session,
        raw,
        settings=settings,
        company_slug=N.company_slug(company),
        municipality=municipality,
        fingerprint=N.fingerprint(company or N.UNKNOWN_COMPANY, raw.title, municipality),
        application_url_norm=N.normalize_url(raw.application_url),
        now=now,
    )

    if match.job is not None:
        job = match.job
        before = job.content_hash
        overwrite = SOURCE_PRIORITY.get(raw.source, 0) >= primary_priority(session, job)
        apply_raw(session, job, raw, settings, overwrite=overwrite)
        reactivated = match.kind == "source_id" and not job.active
        job.active = True
        job.last_seen = now
        session.add(job)
        js = match.job_source
        new_source = js is None
        if js is None:
            js = JobSource(job_id=job.id, source=raw.source, source_id=raw.source_id)
        js.url = raw.url or js.url
        js.raw_path = raw.raw_path or js.raw_path
        js.fetched_at = now
        session.add(js)
        session.flush()
        _add_contacts(session, job, raw)
        changed = before != job.content_hash
        return Upserted(job, raw, is_new=False, content_changed=changed or reactivated or new_source)

    job = Job(fingerprint="", title=raw.title, company="", company_slug="", first_seen=now, last_seen=now)
    apply_raw(session, job, raw, settings, overwrite=True)
    if match.repost_of is not None:
        job.reposted_from_id = match.repost_of.id
        if match.repost_of.active:
            match.repost_of.active = False
            session.add(match.repost_of)
    session.add(job)
    session.flush()
    session.add(JobSource(job_id=job.id, source=raw.source, source_id=raw.source_id, url=raw.url, raw_path=raw.raw_path, fetched_at=now))
    session.flush()
    _add_contacts(session, job, raw)
    return Upserted(job, raw, is_new=True, content_changed=True)


# --- Per source ---------------------------------------------------------------------


def _retry_stubs(session: Session, source: str, exclude: set[str], now: datetime) -> list[tuple[Job, RawJob]]:
    """Recent active jobs of this source still missing ad text, as RawJob stubs for fetch_details."""
    since = now - timedelta(days=DETAIL_RETRY_DAYS)
    rows = session.exec(
        select(Job, JobSource)
        .join(JobSource, JobSource.job_id == Job.id)
        .where(
            JobSource.source == source,
            Job.active == True,  # noqa: E712
            Job.filtered_out == False,  # noqa: E712
            Job.description_clean.is_(None),
            Job.first_seen >= since,
            JobSource.detail_attempts <= len(DETAIL_RETRY_DELAYS_DAYS),
            or_(JobSource.detail_next_at.is_(None), JobSource.detail_next_at <= now),
        )
        .order_by(JobSource.detail_attempts, Job.first_seen)
        .limit(DETAIL_RETRY_MAX)
    ).all()
    out = []
    for job, js in rows:
        if not js.source_id or js.source_id in exclude:
            continue
        stub = RawJob(
            source=source, source_id=js.source_id, url=js.url, title=job.title,
            company=None if job.company == N.UNKNOWN_COMPANY else job.company,
            prefiltered=job.prefiltered, needs_detail=True,
        )
        out.append((job, stub))
    return out


def _filter(session: Session, job: Job, hits: list[H.Hit], summary: SourceSummary) -> bool:
    if hits:
        H.discard(session, job, hits)
        summary.filtered_out += 1
        return True
    return False


def process_jobs(
    session: Session,
    source: SourceProtocol,
    raws: list[RawJob],
    settings: Settings,
    locations: Locations,
    summary: SourceSummary,
    now: datetime,
    should_cancel: Cancel | None = None,
) -> None:
    """Store a source's RawJobs: upsert, hard filter, fetch details, post-detail rules."""
    upserts: list[Upserted] = []
    inactive: list[str] = []
    seen: set[str] = set()
    for raw in raws:
        if raw.source_id in seen:
            continue
        seen.add(raw.source_id)
        if not raw.active:
            inactive.append(raw.source_id)
            continue
        try:
            upserts.append(upsert_raw(session, raw, settings, now))
        except SQLAlchemyError:
            raise
        except Exception as e:  # noqa: BLE001 — one bad ad must not stop the source
            log.exception("upsert failed", extra={"data": {"source": raw.source, "source_id": raw.source_id}})
            summary.errors.append(f"{raw.source_id}: {e}")
    summary.updated += deactivate_sources_reported_inactive(session, source.name, inactive)
    for u in upserts:
        if u.is_new:
            summary.new += 1
        elif u.content_changed:
            summary.updated += 1

    # Pre-detail rules on new or changed jobs; text rules right away when text is present.
    for u in upserts:
        if not (u.is_new or u.content_changed) or u.job.filtered_out:
            continue
        hits = H.pre_detail_rules(u.job, settings, locations)
        if not hits and u.job.description_clean:
            hits = H.post_detail_rules(u.job, settings)
        _filter(session, u.job, hits, summary)
    session.flush()

    if should_cancel and should_cancel():
        return

    # Details for jobs that passed and still lack text, plus recent retries.
    pending: list[tuple[Job, RawJob]] = [
        (u.job, u.raw)
        for u in upserts
        if u.raw.needs_detail and u.raw.description_html is None and u.job.active
        and not u.job.filtered_out and not u.job.description_clean
    ]
    pending += _retry_stubs(session, source.name, {r.source_id for _, r in pending} | seen, now)
    if not pending:
        return
    try:
        detailed = source.fetch_details([r for _, r in pending])
    except Exception as e:  # noqa: BLE001
        log.exception("fetch_details failed", extra={"data": {"source": source.name}})
        summary.errors.append(f"fetch_details: {e}")
        return
    jobs_by_id = {r.source_id: j for j, r in pending}
    for raw in detailed:
        job = jobs_by_id.get(raw.source_id)
        if job is None:
            continue
        js = session.exec(
            select(JobSource).where(JobSource.source == raw.source, JobSource.source_id == raw.source_id)
        ).first()
        if not raw.active:
            # The ad page is gone (Finn 404/410): stop asking for it.
            job.active = False
            session.add(job)
            summary.updated += 1
            continue
        if not raw.description_html:
            if raw.detail_attempted and js is not None:
                js.detail_attempts += 1
                n = js.detail_attempts
                js.detail_next_at = (
                    now + timedelta(days=DETAIL_RETRY_DELAYS_DAYS[n - 1]) - DETAIL_RETRY_SLACK
                    if n <= len(DETAIL_RETRY_DELAYS_DAYS) else None
                )
                session.add(js)
            continue
        overwrite = SOURCE_PRIORITY.get(raw.source, 0) >= primary_priority(session, job)
        apply_raw(session, job, raw, settings, overwrite=overwrite)
        session.add(job)
        _add_contacts(session, job, raw)
        if js is not None:
            js.raw_path = raw.raw_path or js.raw_path
            js.detail_next_at = None
            session.add(js)
        summary.details_fetched += 1
        hits = H.pre_detail_rules(job, settings, locations) + H.post_detail_rules(job, settings)
        _filter(session, job, hits, summary)
    detail_message = getattr(source, "detail_message", None)
    if detail_message:
        summary.errors.append(detail_message)
    missing = sum(1 for j, _ in pending if j.active and not j.description_clean)
    if missing:
        summary.errors.append(f"{missing} annonser mangler fortsatt tekst")


def run_source(
    source: SourceProtocol,
    *,
    trigger: str,
    settings: Settings,
    locations: Locations,
    engine: Engine,
    should_cancel: Cancel | None = None,
) -> SourceSummary:
    summary = SourceSummary(source=source.name)
    started = datetime.now(UTC)
    log.info("source start: %s", source.name)
    result = None
    try:
        with session_scope(engine) as session:
            state = _load_state(session, source.name)
        result = source.collect(state)
    except Exception as e:  # noqa: BLE001
        log.exception("collect failed", extra={"data": {"source": source.name}})
        summary.health = "fail"
        summary.errors.append(f"collect: {e}")

    if result is not None and result.skipped:
        # The source declined to run (e.g. Finn cooldown): no jobs, no retries, no run row.
        summary.message, summary.skipped = result.message, True
        log.info("source skipped", extra={"data": {"source": source.name, "message": result.message}})
        return summary

    if result is not None:
        summary.found = result.found or len(result.jobs)
        summary.errors.extend(result.errors)
        summary.health = result.health
        summary.message = result.message
        try:
            with session_scope(engine) as session:
                process_jobs(session, source, result.jobs, settings, locations, summary, started, should_cancel)
        except Exception as e:  # noqa: BLE001
            log.exception("storing jobs failed", extra={"data": {"source": source.name}})
            summary.health = "fail"
            summary.errors.append(f"lagring: {e}")
            summary.new = summary.updated = summary.filtered_out = summary.details_fetched = 0
        if summary.health == "ok" and summary.errors:
            summary.health = "warn"

    with session_scope(engine) as session:
        session.add(ScrapeRun(
            trigger=trigger, source=source.name, started_at=started, finished_at=datetime.now(UTC),
            found=summary.found, new=summary.new, updated=summary.updated,
            filtered_out=summary.filtered_out, errors=summary.errors, health=summary.health,
        ))
        if result is not None and summary.health != "fail":
            _save_state(session, source.name, result.state, datetime.now(UTC))
    log.info("source done", extra={"data": summary.model_dump()})
    return summary


# --- Backup -------------------------------------------------------------------------


def backup_db(db_path: Path, backups_dir: Path, keep: int, today: date | None = None) -> Path:
    """Copy the DB with SQLite's backup API to backups_dir/jobsearcher-YYYY-MM-DD.db; keep `keep`."""
    today = today or datetime.now(OSLO).date()
    backups_dir.mkdir(parents=True, exist_ok=True)
    dest = backups_dir / f"jobsearcher-{today.isoformat()}.db"
    tmp = dest.with_suffix(".db.tmp")
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    tmp.replace(dest)
    backups = sorted(backups_dir.glob("jobsearcher-*.db"))
    for old in backups[: max(0, len(backups) - keep)]:
        old.unlink(missing_ok=True)
    return dest


# --- Run ------------------------------------------------------------------------------


def run_pipeline(
    trigger: str = "manual",
    *,
    score: bool = True,
    sources: list[str] | None = None,
    progress: Progress | None = None,
    should_cancel: Cancel | None = None,
    source_objects: list[SourceProtocol] | None = None,
    engine: Engine | None = None,
    force: bool = False,
) -> RunSummary:
    """Run the daily pipeline once. Raises `RunLockedError` if another run holds the lock.

    `source_objects` replaces the configured sources (tests). `force` skips source cooldowns
    and weekly schedules (Finn, §4.2).
    """
    engine = engine or get_engine()
    t0 = time.monotonic()
    summary = RunSummary(trigger=trigger, started_at=datetime.now(UTC))

    def report(frac: float, msg: str) -> None:
        if progress:
            try:
                progress(frac, msg)
            except Exception:  # noqa: BLE001
                log.exception("progress callback failed")

    def cancelled() -> bool:
        if should_cancel and should_cancel():
            summary.cancelled = True
            return True
        return False

    with RunLock():
        with session_scope(engine) as session:
            settings = load_effective_settings(session)
        locations = load_locations()

        http = None
        if source_objects is None:
            from jobsearcher.sources.http import HttpClient
            from jobsearcher.sources.registry import build_sources

            http = HttpClient()  # sources set the spacing for their own hosts
            source_objects = build_sources(http, sources, force=force)
        try:
            n = max(1, len(source_objects))
            for i, source in enumerate(source_objects):
                if cancelled():
                    break
                report(0.7 * i / n, f"Henter fra {source.name}")
                summary.sources.append(run_source(
                    source, trigger=trigger, settings=settings, locations=locations,
                    engine=engine, should_cancel=should_cancel,
                ))
        finally:
            if http is not None:
                http.close()

        if not cancelled():
            report(0.7, "Oppdaterer utløp og frister")
            try:
                with session_scope(engine) as session:
                    summary.lifecycle = run_lifecycle(session, settings)
            except Exception:  # noqa: BLE001
                log.exception("lifecycle failed")

        if score and not cancelled():
            report(0.75, "Vurderer nye jobber")
            _score(summary, engine, should_cancel, report)

        if trigger == "schedule" and settings.notify.digest and not cancelled():
            report(0.95, "Sender e-postdigest")
            try:
                from jobsearcher.notify.digest import send_digest

                with session_scope(engine) as session:
                    summary.digest = send_digest(session, settings, summary=summary)
                log.info("digest", extra={"data": {"result": summary.digest}})
            except Exception as e:  # noqa: BLE001
                summary.digest = f"feil: {e}"
                log.exception("digest failed")

        if not cancelled():
            report(0.97, "Tar backup")
            try:
                db_path = Path(engine.url.database or env().db_path)
                summary.backup_path = str(backup_db(db_path, env().backups_dir, settings.retention.backups_keep))
            except Exception:  # noqa: BLE001
                log.exception("backup failed")

    summary.finished_at = datetime.now(UTC)
    summary.duration_s = round(time.monotonic() - t0, 2)
    report(1.0, "Avbrutt" if summary.cancelled else "Ferdig")
    return summary


def _score(summary: RunSummary, engine: Engine, should_cancel: Cancel | None, report: Progress) -> None:
    try:
        from jobsearcher.agents.filter import score_pending
    except ImportError:
        summary.score_skipped_reason = "filter-agenten er ikke installert"
        return

    def scaled(frac: float, msg: str) -> None:
        report(0.75 + 0.2 * max(0.0, min(1.0, frac)), msg)

    try:
        with session_scope(engine) as session:
            res = score_pending(session, should_cancel=should_cancel, progress=scaled)
        summary.scored = res.scored
        summary.score_failed = res.failed
        summary.score_skipped_reason = res.skipped_reason
    except Exception as e:  # noqa: BLE001
        log.exception("scoring failed")
        summary.score_skipped_reason = f"feil: {e}"
