from fastapi import APIRouter
from fastapi.responses import Response

from jobsearcher.api.schemas import (
    Draft,
    DraftCreate,
    DraftSummary,
    ReviseRequest,
    TaskRef,
)
from jobsearcher.web.errors import not_implemented

router = APIRouter(tags=["drafts"])

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/applications/{application_id}/drafts")
def list_drafts(application_id: int) -> list[DraftSummary]:
    raise not_implemented()


@router.post("/applications/{application_id}/drafts", status_code=201)
def create_draft(application_id: int, body: DraftCreate) -> Draft:
    raise not_implemented()


@router.post("/applications/{application_id}/revise", status_code=202)
def revise_draft(application_id: int, body: ReviseRequest) -> TaskRef:
    raise not_implemented()


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: int) -> Draft:
    raise not_implemented()


@router.get(
    "/drafts/{draft_id}/docx",
    response_class=Response,
    responses={200: {"content": {DOCX: {"schema": {"type": "string", "format": "binary"}}}}},
)
def download_draft_docx(draft_id: int) -> Response:
    raise not_implemented()
