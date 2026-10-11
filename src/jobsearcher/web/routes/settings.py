"""Settings form (FRONTEND §5.7, ARCHITECTURE §14).

Only the keys in `FIELDS` can be changed from the dashboard. Changes are rows in
`settings_overrides` on top of config/settings.yaml (and sources.yaml for `sources.*`).
A value equal to the YAML value removes the override.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlmodel import Session

from jobsearcher.api.schemas import SettingItem, Settings, SettingsPatch
from jobsearcher.config import load_locations, load_settings, load_sources, settings_defaults
from jobsearcher.db import models as m
from jobsearcher.db.repo import SOURCES_PREFIX, settings_overrides
from jobsearcher.db.session import get_session
from jobsearcher.web.errors import ApiError

router = APIRouter(tags=["settings"])

SessionDep = Annotated[Session, Depends(get_session)]


@dataclass(frozen=True)
class Field:
    key: str
    section: str
    label: str
    kind: str
    help: str | None = None
    options: tuple[str, ...] | None = None
    min: float | None = None
    max: float | None = None


JOB_TYPES = (("permanent", "fast stilling"), ("trainee", "trainee"), ("graduate", "graduate"), ("summer", "sommerjobb"))
GEO = "geo"  # options filled from config/locations.yaml

FIELDS: tuple[Field, ...] = (
    *(Field(f"search.job_types.{t}", "search", f"Samle inn {name}", "bool") for t, name in JOB_TYPES),
    *(
        Field(f"search.geography.{t}", "search", f"Geografi for {name}", "enum", options=(GEO,))
        for t, name in JOB_TYPES
    ),
    Field("search.allow_remote_norway", "search", "Ta med fjernarbeid hos norsk arbeidsgiver", "bool"),
    Field(
        "search.role_exclude", "search", "Ekskluderte roller", "string_list",
        "Tittel eller kategori med et av ordene forkastes.",
    ),
    Field(
        "search.seniority_title_exclude", "search", "Senioritetsord i tittel", "string_list",
        "Gjelder kilder uten senioritetsfilter (NAV).",
    ),
    Field(
        "search.title_require_any", "search", "Tittelen må inneholde ett av", "string_list",
        "Gjelder NAV før annonsen hentes. Tom liste slår regelen av.",
    ),
    Field(
        "search.max_required_experience_years", "search", "Maks krav til erfaring (år)", "int",
        "0 betyr at krav på 1 år eller mer forkastes.", min=0, max=10,
    ),
    Field(
        "search.unspecified_seniority_max_score", "search", "Maks score uten oppgitt senioritet", "int",
        min=0, max=100,
    ),
    Field("thresholds.overview_deadline_days", "scoring", "Frister på Oversikt (dager)", "int", min=1, max=60),
    Field("notify.digest", "notify", "Send e-postdigest", "bool", "Etter den daglige kjøringen, bare når det er noe å melde."),
    Field(
        "thresholds.notify_min_score", "notify", "Score for nye jobber i digesten", "int",
        "Nye jobber med minst denne scoren kommer med.", min=0, max=100,
    ),
    Field("notify.deadline_days", "notify", "Frister i digesten (dager)", "int", min=1, max=14),
    Field(
        "llm.backend", "llm", "Modell-backend", "enum",
        "openrouter er DeepSeek med betalt kreditt; claude_code bruker Claude-abonnementet.",
        options=("openrouter", "claude_code"),
    ),
    Field(
        "llm.fallback", "llm", "Reserve", "enum",
        "Brukes når backenden feiler. En annen modell gir scorer på en annen skala.",
        options=("none", "claude_code", "openrouter"),
    ),
    Field("llm.openrouter.models.fast", "llm", "OpenRouter-modell (fast)", "string", "Brukes til scoring."),
    Field("llm.openrouter.models.balanced", "llm", "OpenRouter-modell (balanced)", "string"),
    Field("llm.openrouter.models.best", "llm", "OpenRouter-modell (best)", "string", "Brukes til søknadsbrev."),
    Field(
        "llm.monthly_cap_usd", "cost", "Kostnadstak per måned (USD)", "number",
        "Gjelder betalte kall. Nås taket, stopper scoringen.", min=0, max=1000,
    ),
    Field("llm.warn_ratio", "cost", "Varsle ved andel av taket", "number", "0,8 = varsel ved 80 %.", min=0.1, max=1),
    Field("schedule.daily_at", "schedule", "Daglig kjøring", "time", "Tidssone Europe/Oslo."),
    Field(
        "schedule.jitter_minutes", "schedule", "Tilfeldig utsettelse (minutter)", "int",
        "Kjøringen starter 0 til så mange minutter etter klokkeslettet.", min=0, max=180,
    ),
    Field(f"{SOURCES_PREFIX}finn_api.enabled", "sources", "Finn", "bool"),
    Field(f"{SOURCES_PREFIX}nav.enabled", "sources", "NAV", "bool", "Krever NAV_FEED_TOKEN i .env."),
)
BY_KEY = {f.key: f for f in FIELDS}
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _lookup(tree: dict[str, Any], dotted: str) -> Any:
    node: Any = tree
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _default(field: Field) -> Any:
    if field.key.startswith(SOURCES_PREFIX):
        return _lookup(load_sources(), field.key.removeprefix(SOURCES_PREFIX))
    value = _lookup(settings_defaults(), field.key)
    if field.key == "llm.fallback" and value is None:
        return "none"
    return value


def _options(field: Field) -> list[str] | None:
    if field.options == (GEO,):
        return sorted(load_locations().modes)
    return list(field.options) if field.options else None


def _items(session: Session) -> Settings:
    overrides = settings_overrides(session)
    items = []
    for f in FIELDS:
        default = _default(f)
        overridden = f.key in overrides
        items.append(
            SettingItem(
                key=f.key, section=f.section, label=f.label, help=f.help, kind=f.kind,
                options=_options(f), min=f.min, max=f.max,
                value=overrides[f.key] if overridden else default, default=default, overridden=overridden,
            )
        )
    return Settings(items=items)


def _num(n: float | None) -> str:
    return f"{n:g}".replace(".", ",")


def _invalid(field: Field, why: str) -> ApiError:
    return ApiError(422, "invalid_setting", f"{field.label}: {why}")


def _coerce(field: Field, value: Any) -> Any:
    kind = field.kind
    if kind == "bool":
        if not isinstance(value, bool):
            raise _invalid(field, "må være av eller på.")
        return value
    if kind in ("int", "number"):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise _invalid(field, "må være et tall.")
        if kind == "int":
            if value != int(value):
                raise _invalid(field, "må være et heltall.")
            value = int(value)
        if (field.min is not None and value < field.min) or (field.max is not None and value > field.max):
            raise _invalid(field, f"må være mellom {_num(field.min)} og {_num(field.max)}.")
        return value
    if kind == "string_list":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise _invalid(field, "må være en liste med ord.")
        out: list[str] = []
        for v in (v.strip() for v in value):
            if v and v not in out:
                out.append(v)
        return out
    if not isinstance(value, str) or not value.strip():
        raise _invalid(field, "kan ikke være tom.")
    value = value.strip()
    if kind == "time" and not TIME_RE.match(value):
        raise _invalid(field, "må være et klokkeslett (TT:MM).")
    if kind == "enum" and value not in (_options(field) or []):
        raise _invalid(field, f"ukjent verdi «{value}».")
    return value


@router.get("/settings")
def get_settings(session: SessionDep) -> Settings:
    return _items(session)


@router.patch("/settings")
def update_settings(body: SettingsPatch, session: SessionDep) -> Settings:
    unknown = [k for k in body.values if k not in BY_KEY]
    if unknown:
        raise ApiError(422, "unknown_setting", f"Kan ikke endres i dashboardet: {', '.join(unknown)}")
    overrides = settings_overrides(session)
    for key, raw in body.values.items():
        field = BY_KEY[key]
        value = None if raw is None else _coerce(field, raw)
        if value is None or value == _default(field):
            overrides.pop(key, None)
        else:
            overrides[key] = value
    try:
        load_settings({k: v for k, v in overrides.items() if not k.startswith(SOURCES_PREFIX)})
    except ValidationError as e:
        raise ApiError(422, "invalid_setting", f"Ugyldige innstillinger: {e.errors()[0]['msg']}") from e

    for key in body.values:
        row = session.get(m.SettingsOverride, key)
        if key in overrides:
            if row is None:
                row = m.SettingsOverride(key=key)
            row.value = overrides[key]
            session.add(row)
        elif row is not None:
            session.delete(row)
    session.commit()

    if any(k.startswith("schedule.") for k in body.values):
        from jobsearcher.scheduler import reschedule

        reschedule()
    return _items(session)
