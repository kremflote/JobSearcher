from fastapi import APIRouter

from jobsearcher.api.schemas import (
    ApplicationCard,
    ApplicationEvent,
    ApplicationList,
    ApplicationPatch,
    ApplicationStatus,
)
from jobsearcher.web.errors import not_implemented

router = APIRouter(tags=["applications"])


@router.get("/applications")
def list_applications(status: ApplicationStatus | None = None) -> ApplicationList:
    raise not_implemented()


@router.patch("/applications/{application_id}")
def update_application(application_id: int, body: ApplicationPatch) -> ApplicationCard:
    raise not_implemented()


@router.get("/applications/{application_id}/events")
def list_application_events(application_id: int) -> list[ApplicationEvent]:
    raise not_implemented()
