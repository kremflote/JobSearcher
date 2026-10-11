"""Extractor agent: postings listed on a career page (ARCHITECTURE §4.4, §7.1).

The page watcher calls it only when a page's content hash changed, so the cost is a few
cheap calls a week. It respects the monthly cost cap like the filter agent: at the cap only
a subscription backend may run it.
"""

from __future__ import annotations

from sqlmodel import Session

from jobsearcher.agents.base import run_agent
from jobsearcher.agents.schemas import ExtractResult
from jobsearcher.llm.base import LLMBackend, get_backend
from jobsearcher.llm.costs import cap_reached, effective_settings, subscription_only

INSTRUCTIONS = "Finn utlysningene på karrieresiden over etter instruksene."


class ExtractError(RuntimeError):
    pass


def extract_postings(
    company: str,
    url: str,
    text: str,
    *,
    session: Session | None = None,
    backend: LLMBackend | None = None,
) -> ExtractResult:
    """Postings on one career page. Raises ExtractError when the call fails or is not allowed."""
    if session is None:
        from jobsearcher.db.session import session_scope

        with session_scope() as s:
            return extract_postings(company, url, text, session=s, backend=backend)
    settings = effective_settings(session)
    backend = backend or get_backend(settings.llm.backend)
    if cap_reached(session):
        backend = subscription_only(backend)
        if backend is None:
            raise ExtractError("kostnadstaket for måneden er nådd")
    outcome = run_agent(
        "extractor",
        session=session,
        extras={"page": {"company": company, "url": url, "text": text}},
        instructions=INSTRUCTIONS,
        backend=backend,
    )
    if not outcome.ok or not isinstance(outcome.output, ExtractResult):
        raise ExtractError(outcome.error or "ugyldig svar fra extractor")
    return outcome.output
