from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session

from jobsearcher.api.schemas import (
    Draft,
    DraftCreate,
    DraftMessage,
    DraftSummary,
    ReviseRequest,
    TaskRef,
)
from jobsearcher.db import models as m
from jobsearcher.db.session import get_session
from jobsearcher.tracking import drafts
from jobsearcher.web.errors import ApiError
from jobsearcher.web.tasks import TaskCancelled, TaskContext, TaskFailed, get_runner

router = APIRouter(tags=["drafts"])

SessionDep = Annotated[Session, Depends(get_session)]

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _get_application(session: Session, application_id: int) -> m.Application:
    app = session.get(m.Application, application_id)
    if app is None:
        raise ApiError(404, "not_found", "Fant ikke søknaden.")
    return app


def _get_draft(session: Session, draft_id: int) -> m.Draft:
    draft = session.get(m.Draft, draft_id)
    if draft is None:
        raise ApiError(404, "not_found", "Fant ikke utkastet.")
    return draft


def summary_out(d: m.Draft) -> DraftSummary:
    return DraftSummary(
        id=d.id,
        application_id=d.application_id,
        version=d.version,
        author=d.author,
        instruction=d.instruction,
        change_summary=d.change_summary,
        created_at=d.created_at,
    )


def draft_out(d: m.Draft) -> Draft:
    return Draft(
        **summary_out(d).model_dump(), content=d.content, claims_to_verify=list(d.claims_to_verify or [])
    )


def message_out(msg: m.DraftMessage) -> DraftMessage:
    return DraftMessage(
        id=msg.id,
        application_id=msg.application_id,
        role=msg.role,
        text=msg.text,
        draft_id=msg.draft_id,
        created_at=msg.created_at,
    )


def run_agent_task(ctx: TaskContext, fn) -> dict:
    """Run a writer/reviser call as a task; user-facing errors fail the task with their message."""
    from jobsearcher.agents.writer import DraftCancelled, DraftError

    try:
        outcome = fn(ctx)
    except DraftCancelled as e:
        raise TaskCancelled from e
    except DraftError as e:
        raise TaskFailed(str(e)) from e
    return {
        "application_id": outcome.application_id,
        "draft_id": outcome.draft_id,
        "message": outcome.message,
    }


@router.get("/applications/{application_id}/drafts")
def list_drafts(application_id: int, session: SessionDep) -> list[DraftSummary]:
    _get_application(session, application_id)
    return [summary_out(d) for d in drafts.drafts_of(session, application_id)]


@router.post("/applications/{application_id}/drafts", status_code=201)
def create_draft(application_id: int, body: DraftCreate, session: SessionDep) -> Draft:
    _get_application(session, application_id)
    try:
        draft = drafts.save_user_version(session, application_id, body.content, body.base_draft_id)
    except drafts.DraftNotFound as e:
        raise ApiError(404, "not_found", "Fant ikke versjonen.") from e
    session.commit()
    return draft_out(draft)


@router.get("/applications/{application_id}/messages")
def list_messages(application_id: int, session: SessionDep) -> list[DraftMessage]:
    _get_application(session, application_id)
    return [message_out(msg) for msg in drafts.messages_of(session, application_id)]


@router.post("/applications/{application_id}/revise", status_code=202)
def revise_draft(application_id: int, body: ReviseRequest, session: SessionDep) -> TaskRef:
    _get_application(session, application_id)
    if not drafts.has_drafts(session, application_id):
        raise ApiError(409, "no_draft", "Søknaden har ikke noe utkast ennå.")
    try:
        base = drafts.draft_for(session, application_id, body.draft_id)
    except drafts.DraftNotFound as e:
        raise ApiError(404, "not_found", "Fant ikke versjonen.") from e
    instruction = body.instruction.strip()
    message = drafts.add_message(session, application_id, "user", instruction)
    session.commit()

    def task(ctx: TaskContext) -> dict:
        from jobsearcher.agents.reviser import revise

        return run_agent_task(
            ctx,
            lambda c: revise(
                application_id,
                instruction,
                draft_id=base.id,
                user_message_id=message.id,
                progress=c.progress,
            ),
        )

    params = {"application_id": application_id, "draft_id": base.id, "message_id": message.id}
    return TaskRef(task_id=get_runner().submit("revise", params, task))


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: int, session: SessionDep) -> Draft:
    return draft_out(_get_draft(session, draft_id))


@router.get(
    "/drafts/{draft_id}/docx",
    response_class=Response,
    responses={200: {"content": {DOCX: {"schema": {"type": "string", "format": "binary"}}}}},
)
def download_draft_docx(draft_id: int, session: SessionDep) -> Response:
    from jobsearcher.config import today
    from jobsearcher.context.loader import read_profile_file
    from jobsearcher.export.docx import filename, letter_docx, sender_from_profile

    draft = _get_draft(session, draft_id)
    app = _get_application(session, draft.application_id)
    job = session.get(m.Job, app.job_id)
    company = job.company if job else None
    data = letter_docx(
        draft.content,
        sender=sender_from_profile(read_profile_file("profile.yaml")),
        recipient=company,
        on=today(),
        language=(job.ad_language if job and job.ad_language == "en" else "no"),
    )
    name = filename(company, draft.version)
    ascii_name = name.encode("ascii", "replace").decode().replace("?", "_")
    return Response(
        content=data,
        media_type=DOCX,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"
        },
    )
