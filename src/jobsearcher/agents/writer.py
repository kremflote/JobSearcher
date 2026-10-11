"""Writer agent: the first cover letter draft for a job (ARCHITECTURE §7.4, §9.1 "Utkast").

`write_first_draft` is what the `draft` task runs: employer research, then the writer, then the
application bookkeeping. Each step commits on its own, so no write lock is held during a call.
The application is created (or moved Interessant → Utkast) only once the draft exists, so a
failed draft leaves the job as it was.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel
from sqlmodel import Session

from jobsearcher.agents.base import run_agent
from jobsearcher.agents.schemas import DraftResult
from jobsearcher.context import loader
from jobsearcher.context.budget import BudgetExceeded
from jobsearcher.context.slices import ContextMissing
from jobsearcher.db.models import AgentRun, Evaluation, Job
from jobsearcher.db.session import session_scope
from jobsearcher.llm.base import LLMBackend, get_backend
from jobsearcher.llm.costs import cap_reached, effective_settings, subscription_only
from jobsearcher.tracking import drafts
from jobsearcher.tracking.status import apply_transition, application_for_job, triage

log = logging.getLogger(__name__)

LANGUAGE_INSTRUCTION = {
    "no": "Skriv brevet på norsk (bokmål).",
    "en": "Skriv brevet på engelsk, siden annonsen er på engelsk.",
}


class DraftError(RuntimeError):
    """A draft or revision that cannot be made. The message is for the user (Norwegian)."""


class DraftExists(DraftError):
    pass


class DraftCancelled(Exception):
    pass


@dataclass
class DraftOutcome:
    application_id: int
    draft_id: int | None
    message: str


def latest_evaluation(session: Session, job_id: int) -> Evaluation | None:
    from jobsearcher.agents.filter import _latest_evaluations

    return _latest_evaluations(session, [job_id]).get(job_id)


def prepare_backend(session: Session, backend: LLMBackend | None) -> LLMBackend:
    """The backend for a user-initiated call, honouring the monthly cost cap (ARCHITECTURE §8.3)."""
    backend = backend or get_backend(effective_settings(session).llm.backend)
    if cap_reached(session):
        backend = subscription_only(backend)
        if backend is None:
            raise DraftError(
                "Kostnadstaket for LLM denne måneden er nådd. Øk `llm.monthly_cap_usd` for å fortsette."
            )
    return backend


def ensure_profile(backend: LLMBackend) -> None:
    """Distill if the derived profile is outdated; an old derived profile is good enough."""
    if not loader.derived_outdated():
        return
    from jobsearcher.agents.distiller import distill

    try:
        distill(backend=backend)
    except Exception as e:
        if loader.read_derived("profile_long") is None:
            raise DraftError(f"Profilen er ikke destillert, og destilleringen feilet: {e}") from e
        log.warning("distill failed, drafting with the old derived profile", extra={"data": {"error": str(e)}})


def _non_empty_letter(out: BaseModel) -> str | None:
    if not getattr(out, "letter_markdown", "").strip():
        return "`letter_markdown` er tom. Skriv hele brevet."
    return None


def _first_message(out: DraftResult) -> str:
    text = "Første utkast."
    if out.used_projects:
        text += f" Bygger på {', '.join(out.used_projects)}."
    if out.claims_to_verify:
        text += " Sjekk påstandene som er merket."
    if out.notes_for_user:
        text += f"\n\n{out.notes_for_user.strip()}"
    return text


def check_can_draft(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise LookupError(job_id)
    app = application_for_job(session, job_id)
    if app is not None and drafts.has_drafts(session, app.id):  # type: ignore[arg-type]
        raise DraftExists("Søknaden har allerede et utkast.")
    return job


def write_first_draft(
    job_id: int,
    *,
    backend: LLMBackend | None = None,
    progress: Callable[[float, str], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> DraftOutcome:
    def step(fraction: float, message: str) -> None:
        if progress:
            progress(fraction, message)

    with session_scope() as session:
        job = check_can_draft(session, job_id)
        backend = prepare_backend(session, backend)
        company = job.company
    step(0.05, "Sjekker profilen")
    ensure_profile(backend)

    if should_cancel and should_cancel():
        raise DraftCancelled
    step(0.15, f"Researcher {company}")
    from jobsearcher.agents.researcher import ensure_company_note

    with session_scope() as session:
        job = session.get(Job, job_id)
        evaluation = latest_evaluation(session, job_id)
        note = ensure_company_note(session, job, evaluation=evaluation, backend=backend)

    if should_cancel and should_cancel():
        raise DraftCancelled
    step(0.45, "Skriver utkast")
    with session_scope() as session:
        job = session.get(Job, job_id)
        evaluation = latest_evaluation(session, job_id)
        language = job.ad_language if job.ad_language in LANGUAGE_INSTRUCTION else "no"
        try:
            outcome = run_agent(
                "writer",
                session=session,
                extras={"job": job, "evaluation": evaluation, "company_note": note},
                instructions=LANGUAGE_INSTRUCTION[language] + " Følg instruksene og returner utkastet.",
                backend=backend,
                job_ids=[job_id],
                check=_non_empty_letter,
            )
        except (ContextMissing, BudgetExceeded) as e:
            raise DraftError(str(e)) from e
        if not outcome.ok or not isinstance(outcome.output, DraftResult):
            raise DraftError(f"Skriveagenten feilet: {outcome.error}")
        out: DraftResult = outcome.output
        session.commit()  # keep the agent_runs row even if the bookkeeping below fails

        # A draft may have appeared while the writer ran (another tab): keep both, newest last.
        app = application_for_job(session, job_id)
        if app is None:
            app = triage(session, job, "interessant")
        assert app is not None and app.id is not None
        draft = drafts.add_draft(
            session,
            app.id,
            out.letter_markdown.strip() + "\n",
            author="agent",
            change_summary="Første utkast.",
            claims_to_verify=out.claims_to_verify,
            agent_run_id=outcome.run_id,
        )
        drafts.add_message(
            session, app.id, "agent", _first_message(out), draft_id=draft.id, agent_run_id=outcome.run_id
        )
        if app.status == "interessant":
            apply_transition(session, app, "utkast")
        _link_runs(session, job_id, app.id)
        return DraftOutcome(app.id, draft.id, f"Ferdig: versjon {draft.version}")


def _link_runs(session: Session, job_id: int, application_id: int) -> None:
    """Researcher and writer ran before the application existed: attach their runs to it."""
    from sqlmodel import select

    for run in session.exec(
        select(AgentRun).where(
            AgentRun.application_id == None,  # noqa: E711
            AgentRun.agent.in_(("researcher", "writer")),  # type: ignore[attr-defined]
        )
    ):
        if job_id in (run.job_ids or []):
            run.application_id = application_id
            session.add(run)

