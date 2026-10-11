"""Shared fixtures. Every test gets its own DATA_DIR so nothing touches data/."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _clear_caches() -> None:
    from jobsearcher import config
    from jobsearcher.db import session
    from jobsearcher.llm import base, openrouter

    config.env.cache_clear()
    session.get_engine.cache_clear()
    base.reset_breaker()
    openrouter.clear_balance_cache()


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(d))
    monkeypatch.setenv("DERIVED_DIR", str(tmp_path / "derived"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    # The real .env holds live OpenRouter keys; env vars beat .env, so blank them. Tests that
    # need a key set one explicitly and stub HTTP with a transport.
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_MANAGEMENT_KEY", "")
    _clear_caches()
    yield d
    from jobsearcher.db import session

    if session.get_engine.cache_info().currsize:
        session.get_engine().dispose()
    _clear_caches()


@pytest.fixture
def engine(data_dir: Path):
    """Migrated empty database in the test's DATA_DIR."""
    from jobsearcher.db.session import get_engine, init_db

    init_db()
    return get_engine()


@pytest.fixture
def session(engine):
    from sqlmodel import Session

    with Session(engine, expire_on_commit=False) as s:
        yield s
