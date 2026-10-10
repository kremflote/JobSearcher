"""Context slices (ARCHITECTURE §6.2 "Kilder for alle slices").

A slice is a function `(SliceContext, spec) -> str | None`. `None` means "nothing to add".
Slices that need a missing derived file raise `ContextMissing`. Slices for later phases
(company_note, relevant_projects, current_draft, ...) are added with their agents.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jobsearcher.context import loader
from jobsearcher.context.budget import truncate


class ContextMissing(RuntimeError):
    pass


class UnknownSlice(KeyError):
    pass


@dataclass
class SliceContext:
    settings: Any = None
    session: Any = None
    job: Any = None
    extras: dict[str, Any] = field(default_factory=dict)


SliceFn = Callable[[SliceContext, dict[str, Any]], str | None]
REGISTRY: dict[str, SliceFn] = {}


def register(name: str) -> Callable[[SliceFn], SliceFn]:
    def deco(fn: SliceFn) -> SliceFn:
        REGISTRY[name] = fn
        return fn

    return deco


def render(name: str, ctx: SliceContext, spec: dict[str, Any]) -> str | None:
    fn = REGISTRY.get(name)
    if fn is None:
        raise UnknownSlice(f"Slice {name!r} er ikke implementert ennå")
    return fn(ctx, spec)


def escape_untrusted(text: str) -> str:
    """Stop untrusted text from closing or opening our wrapper tags."""
    return text.replace("</job_ad", "&lt;/job_ad").replace("<job_ad", "&lt;job_ad")


# --- Profile slices --------------------------------------------------------------------


def _derived(name: str) -> str:
    text = loader.read_derived(name)
    if text is None:
        raise ContextMissing(f"{name}.md mangler i destillert profil. Kjør `jobsearcher distill`.")
    return text.strip()


@register("profile_short")
def profile_short(ctx: SliceContext, spec: dict[str, Any]) -> str:
    return _derived("profile_short")


@register("profile_long")
def profile_long(ctx: SliceContext, spec: dict[str, Any]) -> str:
    return _derived("profile_long")


@register("voice")
def voice(ctx: SliceContext, spec: dict[str, Any]) -> str:
    return _derived("voice")


@register("style_overrides")
def style_overrides(ctx: SliceContext, spec: dict[str, Any]) -> str | None:
    text = loader.read_profile_file("style_overrides.md")
    return text.strip() if text else None


@register("profile_all")
def profile_all(ctx: SliceContext, spec: dict[str, Any]) -> str:
    files = loader.read_profile()
    if not files:
        raise ContextMissing("Profilmappen er tom; det finnes ingenting å destillere.")
    return "\n\n".join(f'<file path="{path}">\n{text.strip()}\n</file>' for path, text in files.items())


JOB_TYPE_NO = {
    "permanent": "fast stilling for junior/nyutdannet",
    "trainee": "traineeprogram",
    "graduate": "graduate-program",
    "summer": "sommerjobb/internship",
}


@register("search_prefs")
def search_prefs(ctx: SliceContext, spec: dict[str, Any]) -> str:
    s = ctx.settings.search
    enabled = [JOB_TYPE_NO.get(t, t) for t, on in s.job_types.items() if on]
    lines = [
        f"- Aktuelle jobbtyper: {', '.join(enabled)}.",
        "- Søkeren er nyutdannet og har ingen relevant arbeidserfaring som utvikler.",
        "- Stillinger som krever ett år eller mer med arbeidserfaring passer ikke (`seniority: experienced`).",
        f"- Uttalt senioritet mangler (`unspecified`): koden setter tak på {s.unspecified_seniority_max_score} på scoren.",
        f"- Uønskede roller (ekskluderes): {', '.join(s.role_exclude)}.",
        "- Geografi er allerede filtrert før du får annonsene; ikke trekk ned for sted.",
    ]
    return "\n".join(lines)


# --- Job slices ------------------------------------------------------------------------

_META_LABELS = {
    "title": "Tittel",
    "company": "Arbeidsgiver",
    "location_text": "Sted",
    "municipality": "Kommune",
    "remote": "Remote",
    "job_type": "Jobbtype (fra kilden)",
    "deadline": "Frist",
    "deadline_text": "Frist (tekst)",
    "published_at": "Publisert",
}


def _sources(ctx: SliceContext) -> list[str]:
    if ctx.session is None or ctx.job is None or ctx.job.id is None:
        return []
    from sqlmodel import select

    from jobsearcher.db.models import JobSource

    rows = ctx.session.exec(select(JobSource.source).where(JobSource.job_id == ctx.job.id)).all()
    return sorted(set(rows))


@register("job_meta")
def job_meta(ctx: SliceContext, spec: dict[str, Any]) -> str:
    job = ctx.job
    lines = []
    for attr, label in _META_LABELS.items():
        value = getattr(job, attr, None)
        if value in (None, "", "unknown"):
            continue
        if hasattr(value, "date") and attr == "published_at":
            value = value.date()
        lines.append(f"{label}: {value}")
    sources = _sources(ctx)
    if sources:
        lines.append(f"Kilde: {', '.join(sources)}")
    for key, value in (job.meta or {}).items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"{key}: {value}")
    return escape_untrusted("\n".join(lines))


@register("job_ad")
def job_ad(ctx: SliceContext, spec: dict[str, Any]) -> str:
    text = (ctx.job.description_clean or "").strip()
    if not text:
        return "(Annonseteksten mangler. Bare tittel, arbeidsgiver og sted er kjent.)"
    max_tokens = spec.get("max_tokens")
    if max_tokens:
        text = truncate(text, int(max_tokens))
    return escape_untrusted(text)
