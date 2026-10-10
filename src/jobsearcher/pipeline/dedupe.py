"""Matching a new ad to an existing job (ARCHITECTURE §4.5).

Order: (1) same source + source_id, (2) same normalized application URL, (3) same company
+ fuzzy title + overlapping location. Reposts become new jobs with `reposted_from_id`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from rapidfuzz import fuzz
from sqlmodel import Session, select

from jobsearcher.config import Settings
from jobsearcher.db.models import Job, JobSource
from jobsearcher.pipeline import normalize as N
from jobsearcher.sources.base import RawJob

log = logging.getLogger(__name__)

# Higher wins: the most structured source becomes primary and its fields win on merge.
SOURCE_PRIORITY = {"nav": 4, "finn_api": 3, "teamtailor": 2, "page_watch": 1, "manual": 0}

MatchKind = Literal["source_id", "url", "fuzzy"]


@dataclass
class MatchResult:
    job: Job | None = None
    """Existing job to merge into (None → create a new job)."""
    kind: MatchKind | None = None
    repost_of: Job | None = None
    """Set when the new job is a repost of this (older or inactive) job."""
    job_source: JobSource | None = None
    """The existing job_sources row when matched on source + source_id."""


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _same_company(job: Job, org_number: str | None, slug: str) -> bool:
    if job.org_number and org_number:
        return job.org_number == org_number
    return slug != N.UNKNOWN_SLUG and job.company_slug == slug


def _location_overlap(job: Job, municipality: str | None) -> bool:
    if not job.municipality or not municipality:
        return True
    if job.municipality.lower() == municipality.lower():
        return True
    # Multi-location ads: the other job's free text may list this municipality.
    return municipality.lower() in (job.location_text or "").lower()


def title_score(a: str, b: str) -> float:
    """Mean of token_set_ratio and token_sort_ratio.

    token_set_ratio alone scores 100 when one title's words are a subset of the other's, so
    "Utvikler" and "Senior utvikler" at the same company would merge. Averaging with
    token_sort_ratio keeps near-identical titles at ~100 but drops such pairs below the
    merge threshold (they are logged as uncertain instead).
    """
    a, b = N.normalize_text(a), N.normalize_text(b)
    return (fuzz.token_set_ratio(a, b) + fuzz.token_sort_ratio(a, b)) / 2


def _titles(title: str, meta: dict | None) -> list[str]:
    """Headline plus the source's plain position title (Finn: `job_title`), when present.

    Finn headings are often marketing copy ("Vil du være med og forme …"); the position
    title is what matches NAV's title.
    """
    out = [title]
    alt = (meta or {}).get("job_title")
    if alt and alt != title:
        out.append(alt)
    return out


def best_title_score(job: Job, raw: RawJob) -> float:
    return max(
        title_score(a, b) for a in _titles(job.title, job.meta) for b in _titles(raw.title, raw.meta)
    )


def _is_stale(job: Job, raw: RawJob, now: datetime, repost_after_days: int) -> bool:
    """A cross-source match against a job older than `repost_after_days` is a repost."""
    first = _aware(job.published_at) or _aware(job.first_seen)
    if first is None or now - first <= timedelta(days=repost_after_days):
        return False
    published = _aware(raw.published_at)
    return published is None or published > first


def find_match(
    session: Session,
    raw: RawJob,
    *,
    settings: Settings,
    company_slug: str,
    municipality: str | None,
    fingerprint: str,
    application_url_norm: str | None,
    now: datetime | None = None,
) -> MatchResult:
    now = now or datetime.now(UTC)
    repost_days = settings.search.repost_after_days

    # 1. Same ad fetched again (active or not: it is the same ad, not a repost).
    js = session.exec(
        select(JobSource).where(JobSource.source == raw.source, JobSource.source_id == raw.source_id)
    ).first()
    if js is not None:
        job = session.get(Job, js.job_id)
        if job is not None:
            return MatchResult(job=job, kind="source_id", job_source=js)

    candidate: Job | None = None
    kind: MatchKind | None = None

    # 2. Same specific application URL, guarded by same company or similar title so a shared
    #    company-level URL does not merge different positions.
    if application_url_norm and N.is_specific_url(application_url_norm):
        for job in session.exec(
            select(Job).where(Job.application_url_norm == application_url_norm, Job.active == True)  # noqa: E712
        ):
            if _same_company(job, raw.org_number, company_slug) or (
                best_title_score(job, raw) >= settings.dedupe.title_log_threshold
            ):
                candidate, kind = job, "url"
                break

    # 3. Same company + fuzzy title + overlapping location.
    if candidate is None and company_slug != N.UNKNOWN_SLUG:
        stmt = select(Job).where(Job.active == True)  # noqa: E712
        if raw.org_number:
            stmt = stmt.where((Job.org_number == raw.org_number) | (Job.company_slug == company_slug))
        else:
            stmt = stmt.where(Job.company_slug == company_slug)
        best: tuple[float, Job] | None = None
        for job in session.exec(stmt):
            if not _same_company(job, raw.org_number, company_slug):
                continue
            if not _location_overlap(job, municipality):
                continue
            score = best_title_score(job, raw)
            if best is None or score > best[0]:
                best = (score, job)
        if best is not None:
            score, job = best
            if score >= settings.dedupe.title_merge_threshold:
                candidate, kind = job, "fuzzy"
            elif score >= settings.dedupe.title_log_threshold:
                log.warning(
                    "uncertain duplicate not merged",
                    extra={"data": {
                        "score": score, "job_id": job.id, "title": job.title,
                        "new_title": raw.title, "source": raw.source, "source_id": raw.source_id,
                    }},
                )

    if candidate is not None:
        if _is_stale(candidate, raw, now, repost_days):
            return MatchResult(repost_of=candidate)
        return MatchResult(job=candidate, kind=kind)

    # Repost of an inactive job with the same fingerprint.
    old = session.exec(
        select(Job)
        .where(Job.fingerprint == fingerprint, Job.active == False)  # noqa: E712
        .order_by(Job.last_seen.desc())
    ).first()
    if old is not None:
        return MatchResult(repost_of=old)
    return MatchResult()


def primary_priority(session: Session, job: Job) -> int:
    """Priority of the job's current primary source (highest among its job_sources)."""
    if job.id is None:
        return -1
    sources = session.exec(select(JobSource.source).where(JobSource.job_id == job.id)).all()
    return max((SOURCE_PRIORITY.get(s, 0) for s in sources), default=-1)
