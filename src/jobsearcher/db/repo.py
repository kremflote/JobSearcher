"""Small shared DB queries."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from jobsearcher.config import Settings, load_settings
from jobsearcher.db.models import SettingsOverride


def settings_overrides(session: Session) -> dict[str, Any]:
    return {row.key: row.value for row in session.exec(select(SettingsOverride)).all()}


def effective_settings(session: Session) -> Settings:
    """settings.yaml with the dashboard's `settings_overrides` rows merged on top (§14)."""
    return load_settings(settings_overrides(session))
