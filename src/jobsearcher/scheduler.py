"""Daily run inside `serve` (ARCHITECTURE §11).

APScheduler fires at `schedule.daily_at` (Oslo time) and queues a run task after a random
delay of 0 to `schedule.jitter_minutes`, so the sources never see the same start second every
day. At startup a missed run is caught up: if today's run time has passed and no run has
started since then, one is queued right away.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlmodel import Session, col, select

from jobsearcher.config import Settings, env
from jobsearcher.db.models import ScrapeRun

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None
_jitter_minutes: float = 0.0


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


def jitter_delay(jitter_minutes: float, rng: random.Random | None = None) -> timedelta:
    """Random delay in [0, jitter_minutes] for today's scheduled run."""
    if jitter_minutes <= 0:
        return timedelta(0)
    return timedelta(seconds=(rng or random).uniform(0, jitter_minutes * 60))


def _fire_jittered() -> None:
    delay = jitter_delay(_jitter_minutes)
    if delay < timedelta(seconds=1) or _scheduler is None:
        _fire()
        return
    run_at = datetime.now(UTC) + delay
    _scheduler.add_job(
        _fire, DateTrigger(run_date=run_at), id="daily_run_jittered", replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("scheduled run delayed", extra={"data": {"run_at": run_at.isoformat()}})


def start_scheduler() -> None:
    global _scheduler, _jitter_minutes
    if not env().scheduler_enabled or _scheduler is not None:
        return
    from jobsearcher.db.repo import effective_settings
    from jobsearcher.db.session import session_scope

    with session_scope() as session:
        settings = effective_settings(session)
        missed = run_missed(session, settings, datetime.now(ZoneInfo(settings.schedule.timezone)))
    hour, minute = settings.schedule.daily_at.split(":")
    _jitter_minutes = float(settings.schedule.jitter_minutes)
    _scheduler = BackgroundScheduler(timezone=settings.schedule.timezone)
    _scheduler.add_job(
        _fire_jittered,
        CronTrigger(hour=int(hour), minute=int(minute), timezone=settings.schedule.timezone),
        id="daily_run",
        misfire_grace_time=3600,
        coalesce=True,
    )
    _scheduler.start()
    if missed:
        log.info("catching up today's missed run")
        _fire()


def reschedule() -> None:
    """Apply a changed `schedule.daily_at` / `jitter_minutes` from the dashboard to the running
    scheduler. No-op when the scheduler isn't running."""
    global _jitter_minutes
    if _scheduler is None:
        return
    from jobsearcher.db.repo import current_settings

    settings = current_settings()
    hour, minute = settings.schedule.daily_at.split(":")
    _jitter_minutes = float(settings.schedule.jitter_minutes)
    _scheduler.reschedule_job(
        "daily_run",
        trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone=settings.schedule.timezone),
    )
    log.info("schedule changed", extra={"data": {"daily_at": settings.schedule.daily_at}})


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
