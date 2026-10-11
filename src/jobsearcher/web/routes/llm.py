"""GET /api/llm/usage: LLM usage per backend and day, cost cap, OpenRouter balance (FRONTEND §5.1)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, get_args
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, col, select

from jobsearcher.api.schemas import (
    LlmBackendName,
    LlmBackendUsage,
    LlmDailyUsage,
    LlmUsage,
    OpenRouterBalance,
)
from jobsearcher.config import TZ
from jobsearcher.db.models import AgentRun
from jobsearcher.db.session import get_session
from jobsearcher.llm.costs import SUBSCRIPTION_BACKENDS, cost_status, month_start

router = APIRouter(tags=["llm"])

SessionDep = Annotated[Session, Depends(get_session)]

KNOWN_BACKENDS: tuple[str, ...] = get_args(LlmBackendName)
ALWAYS_SHOWN = ("claude_code", "openrouter")
ESTIMATED = set(SUBSCRIPTION_BACKENDS)
DAILY_DAYS = 30


def _balance() -> OpenRouterBalance:
    from dataclasses import asdict

    from jobsearcher.llm.openrouter import get_balance

    return OpenRouterBalance(**asdict(get_balance()))


def build_usage(session: Session, now: datetime | None = None,
                balance: OpenRouterBalance | None = None) -> LlmUsage:
    now = now or datetime.now(UTC)
    tz = ZoneInfo(TZ)
    start = month_start(now)
    spent, cap, warn = cost_status(session, now)

    rows = session.exec(
        select(
            AgentRun.backend,
            func.count(),
            func.count(col(AgentRun.fallback_from)),
            func.coalesce(func.sum(AgentRun.input_tokens), 0),
            func.coalesce(func.sum(AgentRun.output_tokens), 0),
            func.coalesce(func.sum(AgentRun.cost_usd), 0.0),
        )
        .where(AgentRun.created_at >= start)
        .group_by(AgentRun.backend)
    ).all()
    stats = {r[0]: r for r in rows}
    by_backend = []
    for name in KNOWN_BACKENDS:
        r = stats.get(name)
        if r is None and name not in ALWAYS_SHOWN:
            continue
        _, calls, fallback_calls, tin, tout, c = r or (name, 0, 0, 0, 0, 0.0)
        by_backend.append(
            LlmBackendUsage(
                backend=name, calls=calls, fallback_calls=fallback_calls, input_tokens=int(tin),
                output_tokens=int(tout), cost_usd=round(float(c), 6), estimated=name in ESTIMATED,
            )
        )

    today = now.astimezone(tz).date()
    first_day = today - timedelta(days=DAILY_DAYS - 1)
    since = datetime.combine(first_day, datetime.min.time(), tz).astimezone(UTC)
    runs = session.exec(
        select(AgentRun.created_at, AgentRun.backend, AgentRun.input_tokens, AgentRun.output_tokens,
               AgentRun.cost_usd).where(AgentRun.created_at >= since)
    ).all()
    days: dict[tuple, list] = defaultdict(lambda: [0, 0, 0.0])
    for created_at, name, tin, tout, c in runs:
        if name not in KNOWN_BACKENDS:
            continue
        aware = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
        day = aware.astimezone(tz).date()
        if day > today:
            continue
        acc = days[(day, name)]
        acc[0] += tin
        acc[1] += tout
        acc[2] += c
    daily = [
        LlmDailyUsage(date=day, backend=name, input_tokens=v[0], output_tokens=v[1], cost_usd=round(v[2], 6))
        for (day, name), v in sorted(days.items(), key=lambda kv: (kv[0][0], KNOWN_BACKENDS.index(kv[0][1])))
    ]

    return LlmUsage(
        month_start=start.astimezone(tz).date(),
        cap_usd=cap,
        spent_usd=round(spent, 6),
        warn=warn,
        by_backend=by_backend,
        daily=daily,
        openrouter=balance if balance is not None else _balance(),
    )


@router.get("/llm/usage")
def get_llm_usage(session: SessionDep) -> LlmUsage:
    return build_usage(session)
