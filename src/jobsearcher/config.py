"""Configuration: paths and secrets from the environment, runtime values from config/*.yaml.

ARCHITECTURE §14. Dashboard overrides (`settings_overrides`) are dotted keys merged on top of
settings.yaml by `load_settings(overrides)`.
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Env(BaseSettings):
    """Paths and secrets. Relative paths resolve against the repo root."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = Path("data")
    profile_dir: Path = Path("context/profile")
    derived_dir: Path = Path("context/derived")
    config_dir: Path = Path("config")
    prompts_dir: Path = Path("context/prompts")

    scheduler_enabled: bool = True
    """Daily run inside `serve` (§11). Tests turn it off."""

    nav_feed_token: str = ""
    anthropic_api_key: str = ""
    claude_code_oauth_token: str = ""
    gmail_address: str = ""
    gmail_app_password: str = ""

    def model_post_init(self, _: Any) -> None:
        for name in ("data_dir", "profile_dir", "derived_dir", "config_dir", "prompts_dir"):
            p = getattr(self, name)
            if not p.is_absolute():
                setattr(self, name, ROOT / p)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobsearcher.db"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def llm_sandbox_dir(self) -> Path:
        return self.data_dir / "llm_sandbox"

    @property
    def lock_path(self) -> Path:
        return self.data_dir / "run.lock"


# --- settings.yaml -------------------------------------------------------------


class SearchSettings(BaseModel):
    job_types: dict[str, bool]
    geography: dict[str, str]
    allow_remote_norway: bool
    role_exclude: list[str]
    seniority_title_exclude: list[str]
    title_require_any: list[str] = []
    max_required_experience_years: int
    unspecified_seniority_max_score: int
    repost_after_days: int


class DedupeSettings(BaseModel):
    title_merge_threshold: int
    title_log_threshold: int


class CleanSettings(BaseModel):
    job_ad_max_tokens: int
    boilerplate_min_ads: int


class Thresholds(BaseModel):
    notify_min_score: int
    overview_deadline_days: int


class ScheduleSettings(BaseModel):
    daily_at: str
    timezone: str


class LlmSettings(BaseModel):
    backend: str
    monthly_cap_usd: float
    warn_ratio: float
    max_budget_usd_per_call: float
    timeout_s: int


class RetentionSettings(BaseModel):
    raw_cache_days: int
    contacts_days_after_inactive: int
    backups_keep: int


class Settings(BaseModel):
    search: SearchSettings
    dedupe: DedupeSettings
    clean: CleanSettings
    thresholds: Thresholds
    schedule: ScheduleSettings
    llm: LlmSettings
    retention: RetentionSettings


class LocationMode(BaseModel):
    municipalities: list[str] = Field(default_factory=list)
    oslo_bydeler: list[str] = Field(default_factory=list)
    all: bool = False


class Locations(BaseModel):
    modes: dict[str, LocationMode]


# --- Loading -------------------------------------------------------------------


TZ = "Europe/Oslo"


def today() -> date:
    """Today's date in Oslo (deadlines, follow-ups and expiry are Oslo dates)."""
    return datetime.now(ZoneInfo(TZ)).date()


@lru_cache
def env() -> Env:
    return Env()


def read_yaml(name: str) -> dict[str, Any]:
    path = env().config_dir / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def settings_defaults() -> dict[str, Any]:
    return read_yaml("settings.yaml")


def apply_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge dotted-key overrides into a nested dict (copy)."""
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        node = merged
        *parents, leaf = key.split(".")
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return merged


def load_settings(overrides: dict[str, Any] | None = None) -> Settings:
    return Settings.model_validate(apply_overrides(settings_defaults(), overrides or {}))


def load_locations() -> Locations:
    return Locations.model_validate(read_yaml("locations.yaml"))


def load_sources() -> dict[str, Any]:
    return read_yaml("sources.yaml")


def load_agents() -> dict[str, Any]:
    return read_yaml("agents.yaml")


def load_tech_aliases() -> dict[str, str]:
    """Alias (lower case) → canonical name, including canonical → itself."""
    out: dict[str, str] = {}
    for canonical, aliases in read_yaml("tech_aliases.yaml").items():
        out[str(canonical).lower()] = str(canonical).lower()
        for alias in aliases or []:
            out[str(alias).lower()] = str(canonical).lower()
    return out
