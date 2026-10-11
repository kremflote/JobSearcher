"""Research agent: a short note about the employer (ARCHITECTURE §6.1 "Bedriftskontekst", §7.3).

The note is markdown in `data/companies/<slug>.md`, with a `companies` row pointing to it.
A `full` note (from web research) is reused for 90 days. If research fails, a `limited` note is
written from the employer description in the ad (NAV has one) and research is tried again next
time. Without that description there is no note; the writer works from the ad alone.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session

from jobsearcher.agents.base import run_agent
from jobsearcher.agents.schemas import CompanyNote
from jobsearcher.config import env
from jobsearcher.db.models import Company, Evaluation, Job
from jobsearcher.llm.base import LLMBackend

log = logging.getLogger(__name__)

CACHE_DAYS = 90
INSTRUCTIONS = "Lag et notat om arbeidsgiveren over etter instruksene."


def companies_dir() -> Path:
    return env().data_dir / "companies"


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def note_path(company: Company) -> Path | None:
    if not company.note_path:
        return None
    path = Path(company.note_path)
    return path if path.is_absolute() else env().data_dir / path


def read_note(company: Company | None) -> str | None:
    path = note_path(company) if company else None
    if path is None or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def cached_note(company: Company | None, now: datetime | None = None) -> str | None:
    """The note if it is a full note younger than CACHE_DAYS."""
    if company is None or company.note_quality != "full":
        return None
    researched = _aware(company.researched_at)
    now = now or datetime.now(UTC)
    if researched is None or now - researched > timedelta(days=CACHE_DAYS):
        return None
    return read_note(company)


def render_note(name: str, note: CompanyNote) -> str:
    parts = [f"# {name}", "", note.what_they_do.strip()]

    def section(title: str, body: str | None) -> None:
        if body and body.strip():
            parts.extend(["", f"## {title}", body.strip()])

    def bullets(title: str, items: list[str]) -> None:
        items = [x.strip() for x in items if x and x.strip()]
        if items:
            parts.extend(["", f"## {title}", *[f"- {x}" for x in items]])

    section("Størrelse og kontorer", note.size_and_locations)
    section("Teknologi", note.tech_and_engineering)
    bullets("Nylige nyheter", note.recent_news)
    section("Kultur og verdier", note.culture_and_values)
    bullets("Kroker for brevet", note.hooks_for_letter)
    bullets("Kilder", note.sources)
    return "\n".join(parts) + "\n"


def _limited_note(job: Job) -> str | None:
    description = ((job.meta or {}).get("employer_description") or "").strip()
    if not description:
        return None
    return f"# {job.company}\n\n(Bare fra annonsen, uten websøk.)\n\n{description}\n"


def _save(session: Session, job: Job, company: Company | None, content: str, quality: str) -> Company:
    if company is None:
        company = Company(slug=job.company_slug, name=job.company)
    meta = job.meta or {}
    company.name = job.company or company.name
    company.org_number = company.org_number or job.org_number
    company.homepage = company.homepage or meta.get("employer_homepage")
    folder = companies_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{job.company_slug}.md").write_text(content, encoding="utf-8")
    company.note_path = f"companies/{job.company_slug}.md"
    company.note_quality = quality
    company.researched_at = datetime.now(UTC)
    session.add(company)
    session.flush()
    return company


def ensure_company_note(
    session: Session,
    job: Job,
    *,
    evaluation: Evaluation | None = None,
    backend: LLMBackend | None = None,
    application_id: int | None = None,
) -> str | None:
    """The employer note for `job`: cached, freshly researched, limited, or None.

    Never raises on agent failure; the draft goes on without a note.
    """
    from jobsearcher.pipeline.normalize import UNKNOWN_SLUG

    if not job.company_slug or job.company_slug == UNKNOWN_SLUG:
        return None
    company = session.get(Company, job.company_slug)
    cached = cached_note(company)
    if cached:
        return cached

    outcome = run_agent(
        "researcher",
        session=session,
        extras={"job": job, "company": company, "evaluation": evaluation},
        instructions=INSTRUCTIONS,
        backend=backend,
        job_ids=[job.id] if job.id else [],
        application_id=application_id,
    )
    if outcome.ok and isinstance(outcome.output, CompanyNote):
        content = render_note(job.company, outcome.output)
        _save(session, job, company, content, "full")
        return content

    log.warning("research failed", extra={"data": {"company": job.company_slug, "error": outcome.error}})
    limited = _limited_note(job)
    if limited:
        _save(session, job, company, limited, "limited")
        return limited
    return read_note(company)  # an older note, if any, beats none
