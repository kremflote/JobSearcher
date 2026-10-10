from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from jobsearcher.api.schemas import (
    ApplicationCard,
    ApplicationEvent,
    ApplicationList,
    ApplicationPatch,
    ApplicationStatus,
)
from jobsearcher.db import models as m
from jobsearcher.db.session import get_session
from jobsearcher.tracking.status import InvalidTransition, apply_transition
from jobsearcher.web import queries
from jobsearcher.web.errors import ApiError

router = APIRouter(tags=["applications"])

SessionDep = Annotated[Session, Depends(get_session)]

PATCH_FIELDS = ("next_step", "next_step_at", "follow_up_at", "notes")


def _get_application(session: Session, application_id: int) -> m.Application:
    app = session.get(m.Application, application_id)
    if app is None:
        raise ApiError(404, "not_found", "Fant ikke søknaden.")
    return app


@router.get("/applications")
def list_applications(
    session: SessionDep, status: ApplicationStatus | None = None
) -> ApplicationList:
    query = select(m.Application).order_by(col(m.Application.id))
    if status:
        query = query.where(m.Application.status == status)
    return ApplicationList(
        items=queries.application_cards(session, session.exec(query).all())
    )


@router.patch("/applications/{application_id}")
def update_application(
    application_id: int, body: ApplicationPatch, session: SessionDep
) -> ApplicationCard:
    app = _get_application(session, application_id)
    sent = body.model_fields_set
    if body.status is not None:
        try:
            apply_transition(session, app, body.status, body.comment)
        except InvalidTransition as e:
            raise ApiError(409, "invalid_transition", str(e)) from e
    for field in PATCH_FIELDS:
        if field in sent:
            setattr(app, field, getattr(body, field))
    session.add(app)
    session.commit()
    return queries.application_cards(session, [app])[0]


@router.get("/applications/{application_id}/events")
def list_application_events(
    application_id: int, session: SessionDep
) -> list[ApplicationEvent]:
    _get_application(session, application_id)
    events = session.exec(
        select(m.ApplicationEvent)
        .where(m.ApplicationEvent.application_id == application_id)
        .order_by(col(m.ApplicationEvent.at), col(m.ApplicationEvent.id))
    ).all()
    return [queries.event_out(e) for e in events]
