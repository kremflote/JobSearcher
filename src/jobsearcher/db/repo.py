"""Small shared DB queries."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from jobsearcher.config import Settings, apply_overrides, load_settings, load_sources
from jobsearcher.db.models import SettingsOverride


SOURCES_PREFIX = "sources."


def settings_overrides(session: Session) -> dict[str, Any]:
    """All override rows. Keys under `sources.` belong to sources.yaml, the rest to settings.yaml."""
    return {row.key: row.value for row in session.exec(select(SettingsOverride)).all()}


def effective_settings(session: Session) -> Settings:
    """settings.yaml with the dashboard's `settings_overrides` rows merged on top (§14)."""
    overrides = settings_overrides(session)
    return load_settings({k: v for k, v in overrides.items() if not k.startswith(SOURCES_PREFIX)})


def effective_sources(session: Session) -> dict[str, Any]:
    """sources.yaml with `sources.*` overrides (e.g. `sources.nav.enabled`) merged on top."""
    overrides = {
        k.removeprefix(SOURCES_PREFIX): v
        for k, v in settings_overrides(session).items()
        if k.startswith(SOURCES_PREFIX)
    }
    return apply_overrides(load_sources(), overrides)


def current_settings() -> Settings:
    """Effective settings for code without a session (LLM backends). Falls back to plain
    settings.yaml when the DB isn't set up yet."""
    from jobsearcher.db.session import session_scope

    try:
        with session_scope() as s:
            return effective_settings(s)
    except Exception:
        return load_settings()


def current_sources() -> dict[str, Any]:
    from jobsearcher.db.session import session_scope

    try:
        with session_scope() as s:
            return effective_sources(s)
    except Exception:
        return load_sources()
