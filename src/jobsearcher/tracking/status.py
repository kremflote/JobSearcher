"""Application status transitions (ARCHITECTURE §9.1).

The transition table is data; the API exposes it per card as `allowed_next`. Going back to
`previous_status` (the `from_status` of the latest event) is always allowed and undoes that
event. The first event (from `ny`) is undone by triage, which deletes the application row.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlmodel import Session, col, delete, select

from jobsearcher.config import today as config_today
from jobsearcher.db.models import Application, ApplicationEvent, Draft, Job, utcnow
from jobsearcher.tracking.drafts import delete_all as delete_all_drafts

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "ny": ("interessant", "ikke_aktuell"),
    "interessant": ("utkast", "sokt", "ikke_aktuell"),
    "utkast": ("sokt", "ikke_aktuell"),
    "sokt": ("intervju", "avslag", "trukket"),
    "intervju": ("tilbud", "avslag", "trukket"),
    "tilbud": ("trukket",),
    "ikke_aktuell": ("interessant",),
    "avslag": (),
    "trukket": (),
    "utlopt": (),  # set automatically, never by hand
}

TRIAGE_STATUSES = ("ny", "interessant", "ikke_aktuell")
CLOSED_STATUSES = ("ikke_aktuell", "avslag", "trukket", "utlopt")
FOLLOW_UP_DAYS = 14


class InvalidTransition(Exception):
    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(f"Kan ikke gå fra {from_status} til {to_status}.")
        self.from_status = from_status
        self.to_status = to_status


def local_today() -> date:
    """Today's date in the machine's local time zone (the user is in Norway)."""
    return config_today()


def allowed_next(status: str) -> list[str]:
    return list(TRANSITIONS.get(status, ()))


def last_event(session: Session, application_id: int) -> ApplicationEvent | None:
    return session.exec(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application_id)
        .order_by(col(ApplicationEvent.at).desc(), col(ApplicationEvent.id).desc())
    ).first()


def previous_status(session: Session, application: Application) -> str | None:
    """Status before the latest event; `None` when that was `ny` (undone by triage instead)."""
    assert application.id is not None
    event = last_event(session, application.id)
    if event is None or event.from_status == "ny":
        return None
    return event.from_status


def apply_transition(
    session: Session,
    application: Application,
    to_status: str,
    comment: str | None = None,
) -> Application:
    """Move `application` to `to_status`, or undo the latest event if `to_status` is its
    `from_status`. Raises InvalidTransition otherwise. Same status is a no-op. The caller
    commits; explicit `follow_up_at` from a request should be applied after this call.
    """
    current = application.status
    if to_status == current:
        return application
    assert application.id is not None
    event = last_event(session, application.id)
    if (
        event is not None
        and event.from_status != "ny"
        and to_status == event.from_status
    ):
        session.delete(event)
        if current == "sokt":
            application.applied_at = None
            application.follow_up_at = None
    elif to_status in TRANSITIONS.get(current, ()):
        if to_status == "ikke_aktuell":
            # Not relevant any more: drop its cover letters. From `utkast` this steps back to
            # `interessant` first, so undo lands there instead of on an empty draft.
            discard_drafts(session, application)
            current = application.status
        session.add(
            ApplicationEvent(
                application_id=application.id,
                from_status=current,
                to_status=to_status,
                at=utcnow(),
                comment=comment,
            )
        )
        if to_status == "sokt":
            application.applied_at = utcnow()
            application.follow_up_at = local_today() + timedelta(days=FOLLOW_UP_DAYS)
    else:
        raise InvalidTransition(current, to_status)
    application.status = to_status
    session.add(application)
    session.flush()
    return application


def discard_drafts(session: Session, application: Application) -> int:
    """Delete the application's drafts and revision chat (ARCHITECTURE §9.1). An application
    at `utkast` goes back to `interessant` by removing the event that moved it to `utkast`.
    Returns how many draft versions were deleted. The caller commits.
    """
    assert application.id is not None
    deleted = delete_all_drafts(session, application.id)
    if application.status == "utkast":
        event = last_event(session, application.id)
        if event is not None and event.to_status == "utkast":
            session.delete(event)
        application.status = "interessant"
        session.add(application)
        session.flush()
    return deleted


def application_for_job(session: Session, job_id: int) -> Application | None:
    return session.exec(select(Application).where(Application.job_id == job_id)).first()


def triage(session: Session, job: Job, to_status: str) -> Application | None:
    """Triage between `ny`, `interessant` and `ikke_aktuell` (FRONTEND §7).

    From `ny` it creates the application row and its first event; back to `ny` deletes the
    row and its events. Jobs past triage raise InvalidTransition. Returns the application
    (None when the job is back at `ny`). The caller commits.
    """
    assert job.id is not None
    if to_status not in TRIAGE_STATUSES:
        raise InvalidTransition("ny", to_status)
    app = application_for_job(session, job.id)
    current = app.status if app else "ny"
    if current not in TRIAGE_STATUSES:
        raise InvalidTransition(current, to_status)
    if to_status == current:
        return app
    if to_status == "ny":
        assert app is not None and app.id is not None
        has_drafts = session.exec(
            select(Draft.id).where(Draft.application_id == app.id)
        ).first()
        if has_drafts is not None:
            raise InvalidTransition(current, to_status)
        session.exec(
            delete(ApplicationEvent).where(
                col(ApplicationEvent.application_id) == app.id
            )
        )
        session.delete(app)
        session.flush()
        return None
    if app is None:
        now = utcnow()
        app = Application(job_id=job.id, status=to_status, created_at=now)
        session.add(app)
        session.flush()
        assert app.id is not None
        session.add(
            ApplicationEvent(
                application_id=app.id, from_status="ny", to_status=to_status, at=now
            )
        )
        session.flush()
        return app
    # interessant <-> ikke_aktuell: both are legal transitions in the table.
    return apply_transition(session, app, to_status)
