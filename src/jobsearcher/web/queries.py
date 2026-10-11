"""DB rows → API schemas (docs/FRONTEND.md §7). Shared by the route modules."""

from __future__ import annotations

import base64
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, col, select

from jobsearcher.api import schemas as s
from jobsearcher.config import Settings, env, load_settings
from jobsearcher.db import models as m
from jobsearcher.tracking.status import allowed_next, previous_status
from jobsearcher.web.errors import ApiError

# scrape_runs has one row per source per run and no run id. Rows that start within this
# window of the latest one belong to the same run.
RUN_GROUP_WINDOW = timedelta(hours=1)


# --- Settings ------------------------------------------------------------------


from jobsearcher.db.repo import effective_settings, settings_overrides  # noqa: E402,F401


# --- Runs ----------------------------------------------------------------------


def latest_run_bounds(session: Session) -> tuple[datetime | None, datetime | None]:
    """(start, end) of the latest completed run, grouping per-source rows by start time."""
    rows = session.exec(
        select(m.ScrapeRun)
        .where(col(m.ScrapeRun.finished_at).is_not(None))
        .order_by(col(m.ScrapeRun.started_at).desc())
        .limit(50)
    ).all()
    if not rows:
        return None, None
    latest = rows[0].started_at
    group = [r for r in rows if r.started_at >= latest - RUN_GROUP_WINDOW]
    start = min(r.started_at for r in group)
    end = max(r.finished_at for r in rows if r.finished_at is not None)
    return start, end


def new_since(session: Session) -> datetime | None:
    """Jobs first seen at or after this are `is_new`: found by the latest completed run
    (or by one still running)."""
    return latest_run_bounds(session)[0]


# --- Jobs ----------------------------------------------------------------------


def _by_job(rows: Iterable, key: str = "job_id") -> dict[int, list]:
    out: dict[int, list] = defaultdict(list)
    for r in rows:
        out[getattr(r, key)].append(r)
    return out


class JobBundle:
    """Related rows for a set of jobs, loaded in a few bulk queries."""

    def __init__(self, session: Session, jobs: Sequence[m.Job]) -> None:
        ids = [j.id for j in jobs]
        self.apps: dict[int, m.Application] = {}
        self.evals: dict[int, m.Evaluation] = {}
        self.sources: dict[int, list[m.JobSource]] = {}
        if not ids:
            return
        for app in session.exec(
            select(m.Application).where(col(m.Application.job_id).in_(ids))
        ):
            self.apps[app.job_id] = app
        evals = session.exec(
            select(m.Evaluation)
            .where(col(m.Evaluation.job_id).in_(ids))
            .order_by(col(m.Evaluation.created_at), col(m.Evaluation.id))
        )
        for ev in evals:
            self.evals[ev.job_id] = ev  # last one wins = latest
        self.sources = _by_job(
            session.exec(
                select(m.JobSource)
                .where(col(m.JobSource.job_id).in_(ids))
                .order_by(col(m.JobSource.fetched_at), col(m.JobSource.id))
            )
        )

    def status(self, job: m.Job) -> str:
        app = self.apps.get(job.id)
        return app.status if app else "ny"


def list_item(job: m.Job, bundle: JobBundle, since: datetime | None) -> s.JobListItem:
    ev = bundle.evals.get(job.id)
    sources: list[str] = []
    for src in bundle.sources.get(job.id, []):
        if src.source not in sources:
            sources.append(src.source)
    return s.JobListItem(
        id=job.id,
        title=job.title,
        company=job.company,
        location_text=job.location_text,
        job_type=job.job_type,
        role_category=ev.role_category if ev else None,
        status=bundle.status(job),
        score=ev.score if ev else None,
        deadline=job.deadline,
        deadline_text=job.deadline_text,
        application_url=job.application_url,
        sources=sources,
        first_seen=job.first_seen,
        is_new=since is not None and job.first_seen >= since,
        reposted=job.reposted_from_id is not None,
        ad_text_status=job.ad_text_status,
    )


def list_items(
    session: Session, jobs: Sequence[m.Job], since: datetime | None
) -> list[s.JobListItem]:
    bundle = JobBundle(session, jobs)
    return [list_item(j, bundle, since) for j in jobs]


def visible_jobs(session: Session) -> list[m.Job]:
    """Jobs the job list can show: not hidden by the filters (§5.1)."""
    return list(
        session.exec(select(m.Job).where(col(m.Job.filtered_out).is_(False))).all()
    )


def hidden_as_stale(job: m.Job, item: s.JobListItem, today: date) -> bool:
    """Untriaged jobs whose ad is gone or whose deadline has passed are hidden."""
    if item.status != "ny":
        return False
    return not job.active or (job.deadline is not None and job.deadline < today)


def by_deadline_then_score(item: s.JobListItem) -> tuple:
    return (
        item.deadline is None,
        item.deadline or date.max,
        -(item.score if item.score is not None else -1),
        item.id,
    )


def sort_items(items: list[s.JobListItem], sort: str) -> list[s.JobListItem]:
    if sort == "score":
        return sorted(
            items, key=lambda i: (-(i.score if i.score is not None else -1), i.id)
        )
    if sort == "newest":
        return sorted(items, key=lambda i: (i.first_seen, i.id), reverse=True)
    return sorted(items, key=by_deadline_then_score)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        kind, value = raw.split(":", 1)
        offset = int(value)
        if kind != "o" or offset < 0:
            raise ValueError
        return offset
    except ValueError as e:
        raise ApiError(400, "invalid_cursor", "Ugyldig cursor.") from e


def _company_note(session: Session, job: m.Job) -> s.CompanyNote | None:
    company = session.get(m.Company, job.company_slug)
    if company is None or not company.note_path or company.researched_at is None:
        return None
    path = Path(company.note_path)
    if not path.is_absolute():
        path = env().data_dir / path
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return s.CompanyNote(
        name=company.name,
        content=content,
        quality=company.note_quality or "limited",
        researched_at=company.researched_at,
    )


def job_detail(session: Session, job: m.Job, since: datetime | None) -> s.JobDetail:
    bundle = JobBundle(session, [job])
    item = list_item(job, bundle, since)
    ev = bundle.evals.get(job.id)
    contacts = session.exec(
        select(m.JobContact)
        .where(m.JobContact.job_id == job.id)
        .order_by(col(m.JobContact.id))
    ).all()
    app = bundle.apps.get(job.id)
    application = None
    if app is not None:
        latest_draft = session.exec(
            select(m.Draft.id)
            .where(m.Draft.application_id == app.id)
            .order_by(col(m.Draft.version).desc(), col(m.Draft.id).desc())
        ).first()
        application = s.ApplicationSummary(
            id=app.id, status=app.status, latest_draft_id=latest_draft
        )
    return s.JobDetail(
        **item.model_dump(),
        municipality=job.municipality,
        remote=job.remote,
        seniority=job.seniority,
        ad_language=job.ad_language,
        description=job.description_clean,
        published_at=job.published_at,
        expires_at=job.expires_at,
        last_seen=job.last_seen,
        reposted_from_id=job.reposted_from_id,
        evaluation=_evaluation(ev) if ev else None,
        contacts=[
            s.Contact(
                name=c.name, role=c.role, email=c.email, phone=c.phone, source=c.source
            )
            for c in contacts
        ],
        source_refs=[
            s.JobSourceRef(
                source=r.source,
                source_id=r.source_id,
                url=r.url,
                fetched_at=r.fetched_at,
            )
            for r in bundle.sources.get(job.id, [])
        ],
        company_note=_company_note(session, job),
        application=application,
    )


def _evaluation(ev: m.Evaluation) -> s.Evaluation:
    return s.Evaluation(
        score=ev.score,
        confidence=ev.confidence,
        role_category=ev.role_category,
        seniority=ev.seniority,
        tech=ev.tech,
        summary=ev.summary,
        key_requirements=ev.key_requirements,
        match_reasons=ev.match_reasons,
        concerns=ev.concerns,
        model=ev.model,
        prompt_version=ev.prompt_version,
        created_at=ev.created_at,
    )


# --- Applications ----------------------------------------------------------------


def application_cards(
    session: Session, apps: Sequence[m.Application]
) -> list[s.ApplicationCard]:
    if not apps:
        return []
    job_ids = [a.job_id for a in apps]
    jobs = {
        j.id: j for j in session.exec(select(m.Job).where(col(m.Job.id).in_(job_ids)))
    }
    first_contact: dict[int, str] = {}
    for c in session.exec(
        select(m.JobContact)
        .where(col(m.JobContact.job_id).in_(job_ids))
        .order_by(col(m.JobContact.id).desc())
    ):
        first_contact[c.job_id] = (
            c.name
        )  # descending ids: the first contact is written last
    latest_draft: dict[int, tuple[int, datetime]] = {}
    for d in session.exec(
        select(m.Draft)
        .where(col(m.Draft.application_id).in_([a.id for a in apps]))
        .order_by(col(m.Draft.version), col(m.Draft.id))
    ):
        latest_draft[d.application_id] = (d.id, d.created_at)  # ascending: newest wins
    cards = []
    for app in apps:
        job = jobs[app.job_id]
        cards.append(
            s.ApplicationCard(
                id=app.id,
                job_id=app.job_id,
                status=app.status,
                job_title=job.title,
                company=job.company,
                deadline=job.deadline,
                applied_at=app.applied_at,
                follow_up_at=app.follow_up_at,
                next_step=app.next_step,
                next_step_at=app.next_step_at,
                contact_name=first_contact.get(app.job_id),
                notes=app.notes,
                created_at=app.created_at,
                allowed_next=allowed_next(app.status),
                previous_status=previous_status(session, app),
                latest_draft_id=latest_draft.get(app.id, (None,))[0],
                latest_draft_at=latest_draft.get(app.id, (None, None))[1],
            )
        )
    return cards


def event_out(ev: m.ApplicationEvent) -> s.ApplicationEvent:
    return s.ApplicationEvent(
        id=ev.id,
        from_status=ev.from_status,
        to_status=ev.to_status,
        at=ev.at,
        comment=ev.comment,
    )


# --- Tasks -----------------------------------------------------------------------


def task_out(task: m.Task) -> s.Task:
    result = None
    if task.result:
        result = s.TaskResult(
            application_id=task.result.get("application_id"),
            draft_id=task.result.get("draft_id"),
        )
    return s.Task(
        id=task.id,
        kind=task.kind,
        status=task.status,
        progress=task.progress,
        message=task.message,
        created_at=task.created_at,
        finished_at=task.finished_at,
        result=result,
    )
