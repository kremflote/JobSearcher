"""Cost tracking and the monthly cost cap (ARCHITECTURE §8.3).

The month is the calendar month in Oslo, summed from `agent_runs.cost_usd` (`claude_code` logs
the CLI's `total_cost_usd` estimate, `openrouter` the real `usage.cost`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func
from sqlmodel import Session, select

from jobsearcher.db.models import AgentRun


def month_start(now: datetime | None = None) -> datetime:
    """Start of the calendar month in Oslo, as UTC."""
    from zoneinfo import ZoneInfo

    from jobsearcher.config import TZ

    local = (now or datetime.now(UTC)).astimezone(ZoneInfo(TZ))
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def month_cost_usd(session: Session, now: datetime | None = None) -> float:
    stmt = select(func.coalesce(func.sum(AgentRun.cost_usd), 0.0)).where(AgentRun.created_at >= month_start(now))
    return float(session.exec(stmt).one())


def effective_settings(session: Session):
    """settings.yaml with the dashboard's `settings_overrides` rows merged on top."""
    from jobsearcher.db.repo import effective_settings as _effective

    return _effective(session)


def cost_status(session: Session, now: datetime | None = None) -> tuple[float, float, bool]:
    """(month_usd, cap_usd, warn). `warn` is true from `llm.warn_ratio` of the cap and up."""
    llm = effective_settings(session).llm
    spent = month_cost_usd(session, now)
    return spent, llm.monthly_cap_usd, spent >= llm.monthly_cap_usd * llm.warn_ratio


def cap_reached(session: Session, now: datetime | None = None) -> bool:
    spent, cap, _ = cost_status(session, now)
    return spent >= cap
