"""Draft versions and the revision chat (ARCHITECTURE §9.1 "Utkast", "Chat", "Versjoner").

Pure DB helpers; the agents (agents/writer.py, agents/reviser.py) and the API routes call them.
The caller commits.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, col, select

from jobsearcher.db.models import Draft, DraftMessage, utcnow

USER_VERSION_WINDOW = timedelta(minutes=10)
"""Autosave updates the newest user version in place while it is younger than this."""


class DraftNotFound(LookupError):
    pass


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def drafts_of(session: Session, application_id: int) -> list[Draft]:
    return list(
        session.exec(
            select(Draft)
            .where(Draft.application_id == application_id)
            .order_by(col(Draft.version), col(Draft.id))
        ).all()
    )


def latest_draft(session: Session, application_id: int) -> Draft | None:
    return session.exec(
        select(Draft)
        .where(Draft.application_id == application_id)
        .order_by(col(Draft.version).desc(), col(Draft.id).desc())
    ).first()


def has_drafts(session: Session, application_id: int) -> bool:
    return latest_draft(session, application_id) is not None


def draft_for(session: Session, application_id: int, draft_id: int | None) -> Draft:
    """`draft_id` (must belong to the application) or the newest version."""
    if draft_id is None:
        draft = latest_draft(session, application_id)
    else:
        draft = session.get(Draft, draft_id)
        if draft is not None and draft.application_id != application_id:
            draft = None
    if draft is None:
        raise DraftNotFound(draft_id)
    return draft


def add_draft(
    session: Session,
    application_id: int,
    content: str,
    *,
    author: str,
    instruction: str | None = None,
    change_summary: str | None = None,
    claims_to_verify: list[str] | None = None,
    agent_run_id: int | None = None,
) -> Draft:
    top = session.exec(
        select(func.max(Draft.version)).where(Draft.application_id == application_id)
    ).one()
    draft = Draft(
        application_id=application_id,
        version=(top or 0) + 1,
        content=content,
        author=author,
        instruction=instruction,
        change_summary=change_summary,
        claims_to_verify=list(claims_to_verify or []),
        agent_run_id=agent_run_id,
    )
    session.add(draft)
    session.flush()
    return draft


def save_user_version(
    session: Session,
    application_id: int,
    content: str,
    base_draft_id: int | None = None,
    now: datetime | None = None,
) -> Draft:
    """Autosave. Updates the newest version in place if it is a user version younger than
    USER_VERSION_WINDOW, else adds a user version that inherits `claims_to_verify` from the
    base (default: newest). Raises DraftNotFound for an unknown `base_draft_id`."""
    base = draft_for(session, application_id, base_draft_id) if base_draft_id else None
    latest = latest_draft(session, application_id)
    now = now or utcnow()
    if (
        latest is not None
        and latest.author == "user"
        and now - _aware(latest.created_at) < USER_VERSION_WINDOW
    ):
        latest.content = content
        session.add(latest)
        session.flush()
        return latest
    base = base or latest
    return add_draft(
        session,
        application_id,
        content,
        author="user",
        claims_to_verify=list(base.claims_to_verify) if base else [],
    )


def add_message(
    session: Session,
    application_id: int,
    role: str,
    text: str,
    *,
    draft_id: int | None = None,
    agent_run_id: int | None = None,
) -> DraftMessage:
    msg = DraftMessage(
        application_id=application_id,
        role=role,
        text=text,
        draft_id=draft_id,
        agent_run_id=agent_run_id,
    )
    session.add(msg)
    session.flush()
    return msg


def messages_of(session: Session, application_id: int) -> list[DraftMessage]:
    return list(
        session.exec(
            select(DraftMessage)
            .where(DraftMessage.application_id == application_id)
            .order_by(col(DraftMessage.created_at), col(DraftMessage.id))
        ).all()
    )
