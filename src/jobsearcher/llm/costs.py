"""Cost tracking and the monthly cost cap (ARCHITECTURE §8.3).

The month is the calendar month in Oslo, summed from `agent_runs.cost_usd` (both backends log
`total_cost_usd` or the API price estimate).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func
from sqlmodel import Session, select

from jobsearcher.db.models import AgentRun

# USD per million tokens: (input, output). Cache write = 1.25 x input, cache read = 0.1 x input.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def api_cost_usd(model: str, uncached_in: int, cache_write: int, cache_read: int, output: int) -> float:
    price_in, price_out = PRICES.get(model, PRICES["claude-sonnet-5-5"])
    total = (uncached_in + 1.25 * cache_write + 0.1 * cache_read) * price_in + output * price_out
    return round(total / 1_000_000, 6)


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
