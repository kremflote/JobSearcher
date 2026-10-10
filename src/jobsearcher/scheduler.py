"""Daily run inside `serve` (ARCHITECTURE §11).

APScheduler fires at `schedule.daily_at` (Oslo time) and queues a run task. At startup a
missed run is caught up: if today's run time has passed and no run has started since then,
one is queued right away.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, col, select

from jobsearcher.config import Settings, env
from jobsearcher.db.models import ScrapeRun

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def scheduled_time_today(settings: Settings, now: datetime) -> datetime:
    tz = ZoneInfo(settings.schedule.timezone)
    hour, minute = (int(x) for x in settings.schedule.daily_at.split(":"))
    return datetime.combine(now.astimezone(tz).date(), time(hour, minute), tzinfo=tz)


def run_missed(session: Session, settings: Settings, now: datetime) -> bool:
    """True when today's run time has passed and no run (any trigger) started after it."""
    due = scheduled_time_today(settings, now)
    if now < due:
        return False
    started = session.exec(
        select(ScrapeRun.started_at).where(col(ScrapeRun.started_at) >= due).limit(1)
    ).first()
    return started is None


def _fire(trigger: str = "schedule") -> None:
    from jobsearcher.web.errors import ApiError
    from jobsearcher.web.routes.tasks import submit_run

    try:
        task_id = submit_run(trigger)
        log.info("scheduled run queued", extra={"data": {"task_id": task_id}})
    except ApiError:
        log.info("scheduled run skipped: a run is already active")


def start_scheduler() -> None:
    global _scheduler
    if not env().scheduler_enabled or _scheduler is not None:
        return
    from jobsearcher.db.repo import effective_settings
    from jobsearcher.db.session import session_scope

    with session_scope() as session:
        settings = effective_settings(session)
        missed = run_missed(session, settings, datetime.now(ZoneInfo(settings.schedule.timezone)))
    hour, minute = settings.schedule.daily_at.split(":")
    _scheduler = BackgroundScheduler(timezone=settings.schedule.timezone)
    _scheduler.add_job(
        _fire,
        CronTrigger(hour=int(hour), minute=int(minute), timezone=settings.schedule.timezone),
        id="daily_run",
        misfire_grace_time=3600,
        coalesce=True,
    )
    _scheduler.start()
    if missed:
        log.info("catching up today's missed run")
        _fire()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
