from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from jobsearcher.api.schemas import CostStatus, NewSinceLast, Overview, SourceStatus
from jobsearcher.db import models as m
from jobsearcher.db.session import get_session
from jobsearcher.tracking.status import CLOSED_STATUSES, local_today
from jobsearcher.web import queries

router = APIRouter(tags=["overview"])

SessionDep = Annotated[Session, Depends(get_session)]

FOLLOW_UP_DAYS = 7
NEW_TOP_N = 5
SCRAPED_SOURCES = ("finn_api", "nav", "teamtailor", "page_watch")


@router.get("/overview")
def get_overview(session: SessionDep) -> Overview:
    settings = queries.effective_settings(session)
    today = local_today()
    since, last_run_at = queries.latest_run_bounds(session)
    jobs = queries.visible_jobs(session)
    bundle = queries.JobBundle(session, jobs)
    items = {job.id: (job, queries.list_item(job, bundle, since)) for job in jobs}

    # Deadlines: jobs the user marked interesting (or is drafting for) that close soon.
    horizon = today + timedelta(days=settings.thresholds.overview_deadline_days)
    deadlines = sorted(
        (
            item
            for _, item in items.values()
            if item.status in ("interessant", "utkast")
            and item.deadline is not None
            and today <= item.deadline <= horizon
        ),
        key=queries.by_deadline_then_score,
    )

    # New since last run: still open, any status.
    fresh = [
        item
        for job, item in items.values()
        if item.is_new
        and job.active
        and (item.deadline is None or item.deadline >= today)
    ]
    counts: dict[str, int] = {}
    for item in fresh:
        counts[item.job_type] = counts.get(item.job_type, 0) + 1
    top = sorted(fresh, key=lambda i: (-(i.score or 0), i.id))[:NEW_TOP_N]

    return Overview(
        deadlines=deadlines,
        new_since_last=NewSinceLast(since=since, counts_by_type=counts, top=top),
        follow_ups=_follow_ups(session, today),
        sources=_sources(session),
        cost=_cost(session, settings.llm.monthly_cap_usd),
        last_run_at=last_run_at,
    )


def _follow_ups(session: Session, today: date) -> list:
    due_by = today + timedelta(days=FOLLOW_UP_DAYS)
    apps = session.exec(
        select(m.Application).where(col(m.Application.status).not_in(CLOSED_STATUSES))
    ).all()
    due = []
    for app in apps:
        dates = [d for d in (app.follow_up_at, app.next_step_at) if d is not None]
        if dates and min(dates) <= due_by:
            due.append((min(dates), app.id, app))
    due.sort(key=lambda t: (t[0], t[1]))
    return queries.application_cards(session, [app for _, _, app in due])


def _sources(session: Session) -> list[SourceStatus]:
    try:
        configured = [
            k
            for k, v in queries.effective_sources(session).items()
            if isinstance(v, dict) and v.get("enabled")
        ]
    except OSError:
        configured = []
    rows = session.exec(
        select(m.ScrapeRun)
        .order_by(col(m.ScrapeRun.started_at).desc(), col(m.ScrapeRun.id).desc())
        .limit(200)
    ).all()
    latest: dict[str, m.ScrapeRun] = {}
    for row in rows:
        latest.setdefault(row.source, row)
    names = [n for n in SCRAPED_SOURCES if n in configured or n in latest]
    out = []
    for name in names:
        row = latest.get(name)
        if row is None:
            out.append(
                SourceStatus(
                    source=name,
                    health=None,
                    last_run_at=None,
                    found=None,
                    new=None,
                    message=None,
                )
            )
            continue
        out.append(
            SourceStatus(
                source=name,
                health=row.health,
                last_run_at=row.finished_at,
                found=row.found,
                new=row.new,
                message=row.errors[0] if row.errors else None,
            )
        )
    return out


def _cost(session: Session, cap: float) -> CostStatus:
    try:
        from jobsearcher.llm.costs import cost_status
    except ImportError:
        return CostStatus(month_usd=0.0, cap_usd=cap, warn=False)
    month, cap_usd, warn = cost_status(session)
    return CostStatus(month_usd=month, cap_usd=cap_usd, warn=warn)
