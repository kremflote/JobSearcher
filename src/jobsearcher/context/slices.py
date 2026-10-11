"""Context slices (ARCHITECTURE §6.2 "Kilder for alle slices").

A slice is a function `(SliceContext, spec) -> str | None`. `None` means "nothing to add".
Slices that need a missing derived file raise `ContextMissing`.

The phase-3 slices read what the caller puts in `extras` (agents/researcher.py, writer.py,
reviser.py): `evaluation` (latest Evaluation row), `company` (Company row), `company_note`
(markdown), `draft` (Draft row), `instruction` (the user's chat message) and `history`
(earlier DraftMessage rows, oldest first). `extras["job"]` becomes `SliceContext.job`.
The extractor's `career_page` reads `extras["page"]` (`company`, `url`, `text`).
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
        "- Søkeren er student til utdanningen er ferdig (se profilen) og har ingen relevant arbeidserfaring som utvikler.",
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


def escape_tag(text: str, tag: str) -> str:
    """Stop untrusted or user text from closing the `<tag>` wrapper the builder puts around it."""
    return text.replace(f"</{tag}", f"&lt;/{tag}")


# --- Phase 3: applications ---------------------------------------------------------------


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items)


@register("company_meta")
def company_meta(ctx: SliceContext, spec: dict[str, Any]) -> str:
    job = ctx.job
    meta = job.meta or {}
    company = ctx.extras.get("company")
    lines = [f"Navn: {job.company}"]
    org = getattr(company, "org_number", None) or job.org_number
    if org:
        lines.append(f"Organisasjonsnummer: {org}")
    homepage = getattr(company, "homepage", None) or meta.get("employer_homepage")
    if homepage:
        lines.append(f"Hjemmeside: {homepage}")
    if job.location_text:
        lines.append(f"Sted (fra annonsen): {job.location_text}")
    if meta.get("employer_description"):
        lines.append(f"Beskrivelse fra annonsen:\n{meta['employer_description']}")
    return escape_tag(escape_untrusted("\n".join(lines)), "company_meta")


@register("job_ad_summary")
def job_ad_summary(ctx: SliceContext, spec: dict[str, Any]) -> str:
    job = ctx.job
    ev = ctx.extras.get("evaluation")
    lines = [f"Stilling: {job.title}", f"Arbeidsgiver: {job.company}"]
    if job.location_text:
        lines.append(f"Sted: {job.location_text}")
    if ev is None:
        # Not scored (yet): a short cut of the ad itself.
        text = truncate((job.description_clean or "").strip(), int(spec.get("max_tokens") or 600))
        if text:
            lines.append(f"Annonse (forkortet):\n{text}")
    else:
        lines.append(f"Sammendrag: {ev.summary}")
        if ev.key_requirements:
            lines.append("Viktigste krav:\n" + _bullets(ev.key_requirements))
        if ev.tech:
            lines.append(f"Teknologi: {', '.join(ev.tech)}")
    return escape_tag(escape_untrusted("\n".join(lines)), "job_ad_summary")


@register("company_note")
def company_note(ctx: SliceContext, spec: dict[str, Any]) -> str | None:
    note = ctx.extras.get("company_note")
    return escape_tag(escape_untrusted(note.strip()), "company_note") if note else None


@register("evaluation")
def evaluation(ctx: SliceContext, spec: dict[str, Any]) -> str | None:
    ev = ctx.extras.get("evaluation")
    if ev is None:
        return None
    lines = [f"Score: {ev.score}/100 ({ev.role_category})"]
    if ev.match_reasons:
        lines.append("Hvorfor den passer:\n" + _bullets(ev.match_reasons))
    if ev.concerns:
        lines.append("Bekymringer:\n" + _bullets(ev.concerns))
    return "\n".join(lines)


@register("relevant_projects")
def relevant_projects(ctx: SliceContext, spec: dict[str, Any]) -> str | None:
    from jobsearcher.context.projects import rank_projects

    ev = ctx.extras.get("evaluation")
    ranked = rank_projects(list(getattr(ev, "tech", None) or []), getattr(ev, "role_category", None))
    if not ranked:
        return None
    top_k = int(spec.get("top_k") or 3)
    return "\n\n".join(
        f'<project title="{p.title}" match_score="{p.score}">\n{p.body}\n</project>' for p in ranked[:top_k]
    )


@register("current_draft")
def current_draft(ctx: SliceContext, spec: dict[str, Any]) -> str:
    draft = ctx.extras["draft"]
    return escape_tag(draft.content.strip(), "current_draft")


@register("user_message")
def user_message(ctx: SliceContext, spec: dict[str, Any]) -> str:
    return escape_tag(str(ctx.extras["instruction"]).strip(), "user_message")


@register("revision_log")
def revision_log(ctx: SliceContext, spec: dict[str, Any]) -> str | None:
    history = list(ctx.extras.get("history") or [])
    max_items = int(spec.get("max_items") or 5)
    if not history:
        return None
    lines = []
    for msg in history[-max_items:]:
        who = "Søker" if msg.role == "user" else "Du"
        text = " ".join(msg.text.split())
        if len(text) > 400:
            text = text[:400] + " …"
        lines.append(f"- {who}: {text}")
    return escape_tag("\n".join(lines), "revision_log")


@register("career_page")
def career_page(ctx: SliceContext, spec: dict[str, Any]) -> str:
    page = ctx.extras.get("page") or {}
    # A plain cut from the top: a listing page has no "important" paragraphs to keep.
    limit = int(int(spec.get("max_tokens") or 8000) * 3.5)
    text = (page.get("text") or "").strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "\n[… siden er forkortet …]"
    text = escape_tag(escape_tag(escape_untrusted(text), "page"), "career_page")
    head = f"Arbeidsgiver: {page.get('company') or 'ukjent'}\nSide: {page.get('url') or 'ukjent'}"
    return f"{head}\n\n<page>\n{text}\n</page>"
