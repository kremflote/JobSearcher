"""Reviser agent: one chat message in the editor (ARCHITECTURE §6.3, §7.2, §9.1 "Chat").

The user's message is stored by the API before the task starts. Each run is a fresh agent with
the current draft, the message and the last chat messages as a compact log. A question gets an
answer only (`kind: answer`); an edit request gets a new agent version that the answer links to.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from jobsearcher.agents.base import run_agent
from jobsearcher.agents.schemas import RevisionResult
from jobsearcher.agents.writer import (
    DraftError,
    DraftOutcome,
    ensure_profile,
    latest_evaluation,
    prepare_backend,
)
from jobsearcher.context.budget import BudgetExceeded
from jobsearcher.context.slices import ContextMissing
from jobsearcher.db.models import Application, Job
from jobsearcher.db.session import session_scope
from jobsearcher.llm.base import LLMBackend
from jobsearcher.tracking import drafts

INSTRUCTIONS = "Avgjør om søkerens melding er et spørsmål eller en endringsbestilling, og svar etter instruksene."


def _revision_has_letter(out: BaseModel) -> str | None:
    if getattr(out, "kind", None) == "revision" and not getattr(out, "letter_markdown", "").strip():
        return "`kind` er `revision`, men `letter_markdown` er tom. Returner hele det reviderte brevet."
    return None


def revise(
    application_id: int,
    instruction: str,
    *,
    draft_id: int | None = None,
    user_message_id: int | None = None,
    backend: LLMBackend | None = None,
    progress: Callable[[float, str], None] | None = None,
) -> DraftOutcome:
    """Answer or revise. `draft_id` is the version to revise (default newest); `user_message_id`
    is the stored message, left out of the log because it is sent as `user_message`."""
    with session_scope() as session:
        backend = prepare_backend(session, backend)
    ensure_profile(backend)
    if progress:
        progress(0.2, "Leser utkastet")

    with session_scope() as session:
        app = session.get(Application, application_id)
        if app is None:
            raise DraftError("Fant ikke søknaden.")
        try:
            base = drafts.draft_for(session, application_id, draft_id)
        except drafts.DraftNotFound as e:
            raise DraftError("Søknaden har ikke noe utkast ennå.") from e
        job = session.get(Job, app.job_id)
        history = [m for m in drafts.messages_of(session, application_id) if m.id != user_message_id]
        if progress:
            progress(0.3, "Svarer")
        try:
            outcome = run_agent(
                "reviser",
                session=session,
                extras={
                    "job": job,
                    "evaluation": latest_evaluation(session, app.job_id),
                    "draft": base,
                    "instruction": instruction,
                    "history": history,
                },
                instructions=INSTRUCTIONS,
                backend=backend,
                job_ids=[app.job_id],
                application_id=application_id,
                check=_revision_has_letter,
            )
        except (ContextMissing, BudgetExceeded) as e:
            raise DraftError(str(e)) from e
        if not outcome.ok or not isinstance(outcome.output, RevisionResult):
            raise DraftError(f"Revisjonen feilet: {outcome.error}")
        out: RevisionResult = outcome.output
        reply = out.reply.strip() or ("Endret." if out.kind == "revision" else "…")
        letter = out.letter_markdown.strip()

        if out.kind == "answer" or letter == base.content.strip():
            drafts.add_message(session, application_id, "agent", reply, agent_run_id=outcome.run_id)
            return DraftOutcome(application_id, None, "Ferdig: svar i chatten")

        draft = drafts.add_draft(
            session,
            application_id,
            letter + "\n",
            author="agent",
            instruction=instruction,
            change_summary=reply,
            claims_to_verify=out.claims_to_verify,
            agent_run_id=outcome.run_id,
        )
        drafts.add_message(
            session, application_id, "agent", reply, draft_id=draft.id, agent_run_id=outcome.run_id
        )
        return DraftOutcome(application_id, draft.id, f"Ferdig: versjon {draft.version}")
