"""Filter agent: scores jobs in batches (ARCHITECTURE §5.2, §5.5, §7.1).

The model scores and classifies; the rules that must hold regardless of the answer are applied
here in code:
- prefiltered jobs (Finn) are always `entry`
- `experienced` (non-prefiltered) → job.filtered_out = True, logged in hardfilter_log
- `unspecified` → score capped at search.unspecified_seniority_max_score
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from jobsearcher.agents.base import run_agent
from jobsearcher.agents.schemas import FilterBatchResult, FilterResult
from jobsearcher.context import loader
from jobsearcher.context.builder import load_manifest
from jobsearcher.db.models import Application, Evaluation, HardfilterLog, Job, JobContact
from jobsearcher.llm.base import LLMBackend, get_backend
from jobsearcher.llm.costs import cap_reached, effective_settings

log = logging.getLogger(__name__)

INSTRUCTIONS = "Vurder hver annonse over. Returner ett resultat per <job_ad>, med `job_id` lik id-attributtet."

RESCORE_STATUSES = ("ny", "interessant")
RESCORE_MAX_AGE_DAYS = 30


class ScoreSummary(BaseModel):
    scored: int = 0
    failed: int = 0
    skipped_reason: str | None = None


# --- Selecting jobs ----------------------------------------------------------------------


def _latest_evaluations(session: Session, job_ids: Iterable[int] | None = None) -> dict[int, Evaluation]:
    latest = select(Evaluation.job_id, func.max(Evaluation.id).label("max_id")).group_by(Evaluation.job_id)
    if job_ids is not None:
        latest = latest.where(Evaluation.job_id.in_(list(job_ids)))
    sub = latest.subquery()
    rows = session.exec(select(Evaluation).join(sub, Evaluation.id == sub.c.max_id)).all()
    return {ev.job_id: ev for ev in rows}


def pending_jobs(session: Session) -> list[Job]:
    """Active, not filtered out, and never scored or scored on other content (§5.5)."""
    jobs = session.exec(
        select(Job).where(Job.active == True, Job.filtered_out == False).order_by(Job.id)  # noqa: E712
    ).all()
    latest = _latest_evaluations(session, [j.id for j in jobs])
    return [j for j in jobs if j.id not in latest or latest[j.id].content_hash != j.content_hash]


def stale_jobs(session: Session) -> list[Job]:
    """Jobs scored with another profile or prompt version that are worth rescoring (§5.5).

    Active, published (or first seen) in the last 30 days, application status none, "ny" or
    "interessant".
    """
    profile_hash = loader.derived_profile_hash()
    prompt_version = loader.load_prompt(load_manifest("filter").prompt).version
    since = datetime.now(UTC) - timedelta(days=RESCORE_MAX_AGE_DAYS)
    jobs = session.exec(
        select(Job).where(Job.active == True, Job.filtered_out == False).order_by(Job.id)  # noqa: E712
    ).all()
    statuses = dict(session.exec(select(Application.job_id, Application.status)).all())
    latest = _latest_evaluations(session, [j.id for j in jobs])
    out = []
    for job in jobs:
        ev = latest.get(job.id)
        if ev is None or (ev.profile_hash == profile_hash and ev.prompt_version == prompt_version):
            continue
        if statuses.get(job.id, "ny") not in RESCORE_STATUSES:
            continue
        seen = _aware(job.published_at or job.first_seen)
        if seen and seen < since:
            continue
        out.append(job)
    return out


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# --- Applying results --------------------------------------------------------------------


def apply_result(session: Session, job: Job, r: FilterResult, *, settings, model: str, prompt_version: str,
                 profile_hash: str) -> Evaluation:
    """Write the evaluation and apply the §5.2 rules to the job."""
    seniority = "entry" if job.prefiltered else r.seniority
    score = r.score
    if seniority == "unspecified":
        score = min(score, settings.search.unspecified_seniority_max_score)
    ev = Evaluation(
        job_id=job.id,
        score=score,
        confidence=r.confidence,
        role_category=r.role_category,
        job_type=r.job_type,
        seniority=seniority,
        tech=list(r.tech),
        summary=r.summary,
        key_requirements=list(r.key_requirements),
        match_reasons=list(r.match_reasons),
        concerns=list(r.concerns),
        model=model,
        prompt_version=prompt_version,
        profile_hash=profile_hash,
        content_hash=job.content_hash,
    )
    session.add(ev)

    job.seniority = seniority
    if seniority == "experienced":
        job.filtered_out = True
        session.add(HardfilterLog(job_id=job.id, rule="llm_seniority", detail="Filter-agenten: krever erfaring"))
    if job.job_type == "unknown" and r.job_type != "unknown":
        job.job_type = r.job_type
    if not job.ad_language:
        job.ad_language = r.ad_language
    if job.deadline is None and r.deadline is not None:
        job.deadline = r.deadline
    if not job.deadline_text and r.deadline_text:
        job.deadline_text = r.deadline_text
    if not job.application_url and r.application_url:
        job.application_url = r.application_url
    if r.contacts:
        has_contacts = session.exec(select(JobContact.id).where(JobContact.job_id == job.id).limit(1)).first()
        if has_contacts is None:
            for c in r.contacts:
                session.add(
                    JobContact(job_id=job.id, name=c.name, role=c.role, email=c.email, phone=c.phone, source="llm")
                )
    session.add(job)
    return ev


def _ids_check(batch: list[Job]) -> Callable[[BaseModel], str | None]:
    expected = {str(j.id) for j in batch}

    def check(out: BaseModel) -> str | None:
        got = {r.job_id for r in out.results}  # type: ignore[attr-defined]
        missing = expected - got
        if missing:
            return f"Mangler resultat for job_id: {', '.join(sorted(missing))}"
        return None

    return check


# --- Public API ----------------------------------------------------------------------------


def _ensure_profile(backend: LLMBackend) -> str | None:
    """Distill if outdated. Returns a skip reason if scoring cannot proceed."""
    if not loader.derived_outdated():
        return None
    from jobsearcher.agents.distiller import distill

    try:
        distill(backend=backend)
    except Exception as e:
        if loader.read_derived("profile_short") is None:
            log.error("distill failed and no derived profile exists", extra={"data": {"error": str(e)}})
            return "distill_failed"
        log.warning("distill failed, scoring with the old derived profile", extra={"data": {"error": str(e)}})
    return None


def score_jobs(
    session: Session,
    jobs: list[Job],
    *,
    should_cancel: Callable[[], bool] | None = None,
    progress: Callable[[float, str], None] | None = None,
    backend: LLMBackend | None = None,
) -> ScoreSummary:
    """Score the given jobs in batches. Commits after each batch."""
    summary = ScoreSummary()
    if not jobs:
        return summary
    settings = effective_settings(session)
    backend = backend or get_backend(settings.llm.backend)
    if cap_reached(session):
        summary.skipped_reason = "cost_cap"
        return summary
    reason = _ensure_profile(backend)
    if reason:
        summary.skipped_reason = reason
        return summary

    manifest = load_manifest("filter")
    profile_hash = loader.derived_profile_hash() or loader.profile_hash()
    size = max(1, manifest.batch_size)
    batches = [jobs[i : i + size] for i in range(0, len(jobs), size)]
    for n, batch in enumerate(batches):
        if should_cancel and should_cancel():
            summary.skipped_reason = "cancelled"
            break
        if cap_reached(session):
            summary.skipped_reason = "cost_cap"
            break
        if progress:
            progress(n / len(batches), f"Scorer annonser {n * size + 1}–{n * size + len(batch)} av {len(jobs)}")
        outcome = run_agent(
            "filter",
            session=session,
            items=batch,
            instructions=INSTRUCTIONS,
            backend=backend,
            job_ids=[j.id for j in batch],
            check=_ids_check(batch),
            manifest=manifest,
        )
        by_id: dict[str, FilterResult] = {}
        if isinstance(outcome.output, FilterBatchResult):
            by_id = {r.job_id: r for r in outcome.output.results}
        for job in batch:
            r = by_id.get(str(job.id))
            if r is None:
                summary.failed += 1
                continue
            apply_result(
                session, job, r, settings=settings, model=outcome.model,
                prompt_version=outcome.prompt_version, profile_hash=profile_hash,
            )
            summary.scored += 1
        session.commit()
    if progress:
        progress(1.0, f"Scoret {summary.scored} annonser")
    return summary


def score_pending(
    session: Session,
    *,
    should_cancel: Callable[[], bool] | None = None,
    progress: Callable[[float, str], None] | None = None,
    backend: LLMBackend | None = None,
) -> ScoreSummary:
    """Score new jobs and jobs whose content changed since the last evaluation (§5.5)."""
    return score_jobs(session, pending_jobs(session), should_cancel=should_cancel, progress=progress,
                      backend=backend)


def rescore(
    session: Session,
    job_ids: list[int] | None = None,
    *,
    should_cancel: Callable[[], bool] | None = None,
    progress: Callable[[float, str], None] | None = None,
    backend: LLMBackend | None = None,
) -> ScoreSummary:
    """Rescore after a profile or prompt change (user-triggered, §5.5).

    With `job_ids`, those jobs are rescored unconditionally; otherwise `stale_jobs()`.
    """
    if job_ids is None:
        jobs = stale_jobs(session)
    else:
        jobs = list(session.exec(select(Job).where(Job.id.in_(job_ids)).order_by(Job.id)).all())
    return score_jobs(session, jobs, should_cancel=should_cancel, progress=progress, backend=backend)
