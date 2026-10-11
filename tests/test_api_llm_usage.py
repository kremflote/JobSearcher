"""GET /api/llm/usage (FRONTEND §5.1, §7). Invented data only, balance stubbed."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from jobsearcher.api.schemas import OpenRouterBalance
from jobsearcher.db.models import AgentRun
from jobsearcher.llm import openrouter
from jobsearcher.web.app import create_app
from jobsearcher.web.routes.llm import build_usage

NOW = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
BALANCE = OpenRouterBalance(configured=True, balance_usd=7.4, total_credits_usd=10.0, balance_source="account",
                            fetched_at=NOW)


def _run(session, backend, created_at, *, cost=0.0, tin=100, tout=10, fallback_from=None, status="ok"):
    session.add(AgentRun(agent="filter", backend=backend, model="m", prompt_version="1", cost_usd=cost,
                         input_tokens=tin, output_tokens=tout, fallback_from=fallback_from, status=status,
                         created_at=created_at))


def test_month_aggregation_per_backend(session):
    _run(session, "claude_code", datetime(2026, 10, 2, tzinfo=UTC), cost=1.0)
    _run(session, "claude_code", datetime(2026, 10, 14, tzinfo=UTC), cost=19.0, status="error")
    _run(session, "openrouter", datetime(2026, 10, 14, tzinfo=UTC), cost=0.002, tin=1000, tout=200,
         fallback_from="claude_code")
    _run(session, "openrouter", datetime(2026, 10, 14, 1, tzinfo=UTC), cost=0.001)
    _run(session, "claude_code", datetime(2026, 9, 30, 21, 30, tzinfo=UTC), cost=50.0)  # 23:30 Oslo, Sept.
    session.commit()

    u = build_usage(session, NOW, balance=BALANCE)
    assert u.month_start == date(2026, 10, 1)
    assert u.cap_usd == 25 and u.spent_usd == pytest.approx(20.003) and u.warn is True
    by = {b.backend: b for b in u.by_backend}
    assert list(by) == ["claude_code", "openrouter"]  # no mock calls → no mock row
    assert (by["claude_code"].calls, by["claude_code"].fallback_calls, by["claude_code"].estimated) == (2, 0, True)
    assert by["claude_code"].cost_usd == pytest.approx(20.0)
    o = by["openrouter"]
    assert (o.calls, o.fallback_calls, o.input_tokens, o.output_tokens, o.estimated) == (2, 1, 1100, 210, False)
    assert o.cost_usd == pytest.approx(0.003)
    assert u.openrouter == BALANCE


def test_empty_month_shows_both_backends_and_mock_when_used(session):
    u = build_usage(session, NOW, balance=BALANCE)
    assert [(b.backend, b.calls, b.cost_usd) for b in u.by_backend] == [("claude_code", 0, 0), ("openrouter", 0, 0)]
    assert u.daily == [] and u.spent_usd == 0 and u.warn is False
    _run(session, "mock", datetime(2026, 10, 15, tzinfo=UTC))
    _run(session, "anthropic_api", datetime(2026, 10, 15, tzinfo=UTC), cost=1.0)  # legacy rows count in spent only
    session.commit()
    u = build_usage(session, NOW, balance=BALANCE)
    assert [b.backend for b in u.by_backend] == ["claude_code", "openrouter", "mock"]
    assert u.spent_usd == pytest.approx(1.0)
    assert {d.backend for d in u.daily} == {"mock"}


def test_daily_last_30_oslo_days(session):
    # Oslo is UTC+2 in October (CEST).
    _run(session, "claude_code", datetime(2026, 9, 15, 21, 59, tzinfo=UTC))  # 23:59 Oslo 15.9: outside
    _run(session, "claude_code", datetime(2026, 9, 15, 22, 0, tzinfo=UTC))  # 00:00 Oslo 16.9: first day
    _run(session, "openrouter", datetime(2026, 10, 14, 22, 30, tzinfo=UTC), tin=5, tout=1, cost=0.01)  # 15.10
    _run(session, "claude_code", datetime(2026, 10, 14, 21, 30, tzinfo=UTC), tin=7)  # 23:30 Oslo 14.10
    _run(session, "claude_code", datetime(2026, 10, 14, 8, 0, tzinfo=UTC), tin=3)  # 14.10
    session.commit()
    u = build_usage(session, NOW, balance=BALANCE)
    assert [(d.date, d.backend, d.input_tokens) for d in u.daily] == [
        (date(2026, 9, 16), "claude_code", 100),
        (date(2026, 10, 14), "claude_code", 10),
        (date(2026, 10, 15), "openrouter", 5),
    ]
    assert u.daily[-1].cost_usd == pytest.approx(0.01)


def test_endpoint_uses_balance_function(engine, monkeypatch):
    monkeypatch.setattr(openrouter, "get_balance", lambda: openrouter.Balance(configured=False))
    r = TestClient(create_app(dist=None)).get("/api/llm/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["openrouter"] == {"configured": False, "balance_usd": None, "total_credits_usd": None,
                                  "balance_source": None, "fetched_at": None}
    assert [b["backend"] for b in body["by_backend"]] == ["claude_code", "openrouter"]
