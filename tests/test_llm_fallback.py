"""Fallback from the primary backend to OpenRouter (ARCHITECTURE §8.1). No network."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlmodel import select

from jobsearcher.agents.distiller import distill
from jobsearcher.agents.filter import score_pending
from jobsearcher.config import env
from jobsearcher.db.models import AgentRun, Evaluation, Job
from jobsearcher.llm import base
from jobsearcher.llm.base import AgentRequest, FallbackBackend, FallbackError, LLMBackendError, LLMError, get_backend
from jobsearcher.llm.mock import MockBackend

FIXTURE_PROFILE = Path(__file__).parent / "fixtures" / "profile"


class Primary:
    """Stands in for claude_code: raises the given error, or answers like the mock."""

    name = "claude_code"

    def __init__(self, error: Exception | None = None, responder=None):
        self.error = error
        self.mock = MockBackend(responder=responder)
        self.calls = 0

    def run(self, req):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.mock.run(req)


def _fallback(**kw) -> MockBackend:
    fb = MockBackend(cost_usd=0.0003, **kw)
    fb.name = "openrouter"
    return fb


def _req() -> AgentRequest:
    return AgentRequest(agent="x", system_prompt="s", user_content="u")


# --- FallbackBackend ------------------------------------------------------------------------


def test_backend_error_switches_and_opens_breaker(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(base.time, "monotonic", lambda: clock[0])
    primary, fb = Primary(LLMBackendError("Claude AI usage limit reached")), _fallback()
    wrapper = FallbackBackend(primary, fb)
    resp = wrapper.run(_req())
    assert (resp.backend, resp.fallback_from) == ("openrouter", "claude_code")
    assert "usage limit" in resp.primary_error
    assert wrapper.name == "claude_code"

    # Breaker open: the primary is skipped for 30 minutes.
    primary.error = None
    clock[0] += 29 * 60
    resp = wrapper.run(_req())
    assert primary.calls == 1 and len(fb.requests) == 2
    assert (resp.backend, resp.fallback_from, resp.primary_error) == ("openrouter", "claude_code", None)

    # After 30 minutes the primary is tried again.
    clock[0] += 2 * 60
    resp = wrapper.run(_req())
    assert primary.calls == 2 and resp.backend == "claude_code" and resp.fallback_from is None


def test_model_error_does_not_switch():
    primary, fb = Primary(LLMError("claude -p feilet: error_max_budget_usd")), _fallback()
    with pytest.raises(LLMError) as exc:
        FallbackBackend(primary, fb).run(_req())
    assert not isinstance(exc.value, FallbackError)
    assert fb.requests == [] and not base.breaker_open("claude_code")


def test_fallback_failure_raises_fallback_error():
    class Broken:
        name = "openrouter"

        def run(self, req):
            raise LLMBackendError("OpenRouter: for lite kreditt (402).")

    with pytest.raises(FallbackError) as exc:
        FallbackBackend(Primary(LLMBackendError("timeout")), Broken()).run(_req())
    e = exc.value
    assert (e.backend, e.fallback_from, e.primary_error) == ("openrouter", "claude_code", "timeout")
    assert "402" in str(e)


# --- get_backend --------------------------------------------------------------------------


def _set_key(monkeypatch, key: str) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", key)
    env.cache_clear()


def _set_fallback(monkeypatch, value):
    from jobsearcher import config

    real = config.load_settings
    monkeypatch.setattr(config, "load_settings", lambda overrides=None: real({"llm.fallback": value}))


def test_get_backend_wraps_only_with_key(monkeypatch):
    _set_fallback(monkeypatch, "openrouter")
    assert not isinstance(get_backend("claude_code"), FallbackBackend)  # conftest blanks the key
    _set_key(monkeypatch, "sk-or-test-not-real")
    wrapped = get_backend("claude_code")
    assert isinstance(wrapped, FallbackBackend) and wrapped.fallback.name == "openrouter"
    assert wrapped.name == "claude_code"
    assert not isinstance(get_backend("openrouter"), FallbackBackend)  # same as the fallback
    assert not isinstance(get_backend("mock"), FallbackBackend)
    assert not isinstance(get_backend("claude_code", fallback=False), FallbackBackend)


def test_get_backend_openrouter_primary_with_claude_fallback(monkeypatch):
    _set_fallback(monkeypatch, "claude_code")
    wrapped = get_backend("openrouter")
    assert isinstance(wrapped, FallbackBackend) and wrapped.fallback.name == "claude_code"


def test_default_settings_use_openrouter_without_fallback():
    from jobsearcher.config import load_settings

    llm = load_settings().llm
    assert llm.backend == "openrouter" and llm.fallback_backend is None


@pytest.mark.parametrize("value", ["none", None])
def test_get_backend_fallback_disabled(monkeypatch, value):
    _set_key(monkeypatch, "sk-or-test-not-real")
    _set_fallback(monkeypatch, value)
    assert not isinstance(get_backend("claude_code"), FallbackBackend)


# --- agent_runs bookkeeping ---------------------------------------------------------------


@pytest.fixture
def distilled(tmp_path, monkeypatch, engine):
    d = tmp_path / "profile"
    shutil.copytree(FIXTURE_PROFILE, d)
    monkeypatch.setenv("PROFILE_DIR", str(d))
    env.cache_clear()
    distill(backend=MockBackend())
    return d


def _jobs(session, n=2):
    for i in range(n):
        session.add(Job(fingerprint=f"fp{i}", title=f"Utvikler {i}", company="Eksempel AS",
                        company_slug="eksempel-as", description_clean="Junior utvikler.", content_hash=f"h{i}"))
    session.commit()


def test_agent_runs_record_both_attempts(distilled, session):
    _jobs(session)
    backend = FallbackBackend(Primary(LLMBackendError("claude -p brukte mer enn 600 s")), _fallback())
    summary = score_pending(session, backend=backend)
    assert summary.scored == 2
    runs = session.exec(select(AgentRun).where(AgentRun.agent == "filter").order_by(AgentRun.id)).all()
    assert [(r.backend, r.status, r.fallback_from) for r in runs] == [
        ("claude_code", "error", None),
        ("openrouter", "ok", "claude_code"),
    ]
    assert "600 s" in runs[0].error and runs[0].cost_usd == 0
    assert runs[1].cost_usd == pytest.approx(0.0003)
    assert {ev.model for ev in session.exec(select(Evaluation)).all()} == {"mock-fast"}


def test_invalid_output_retries_on_primary_without_fallback(distilled, session):
    _jobs(session)
    primary = Primary(responder=lambda req: {"results": "ugyldig"})
    fb = _fallback()
    summary = score_pending(session, backend=FallbackBackend(primary, fb))
    assert summary.failed == 2
    assert primary.calls == 2 and fb.requests == []
    run = session.exec(select(AgentRun).where(AgentRun.agent == "filter")).one()
    assert (run.backend, run.status, run.fallback_from) == ("claude_code", "error", None)


def test_both_backends_failing_records_two_error_rows(distilled, session):
    class Broken:
        name = "openrouter"

        def run(self, req):
            raise LLMBackendError("OpenRouter svarte 503: nede")

    _jobs(session)
    summary = score_pending(session, backend=FallbackBackend(Primary(LLMBackendError("login")), Broken()))
    assert summary.failed == 2
    runs = session.exec(select(AgentRun).where(AgentRun.agent == "filter").order_by(AgentRun.id)).all()
    assert [(r.backend, r.status, r.fallback_from, r.error) for r in runs] == [
        ("claude_code", "error", None, "login"),
        ("openrouter", "error", "claude_code", "OpenRouter svarte 503: nede"),
    ]
