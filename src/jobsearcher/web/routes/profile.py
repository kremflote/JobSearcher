from fastapi import APIRouter

from jobsearcher.api.schemas import (
    ProfileFile,
    ProfileFileWrite,
    ProfileRevision,
    ProfileTree,
    TaskRef,
)
from jobsearcher.web.errors import not_implemented

router = APIRouter(tags=["profile"])


@router.get("/profile/files")
def list_profile_files() -> ProfileTree:
    raise not_implemented()


# Declared before the file routes: `{path:path}` would otherwise swallow "/revisions".
@router.get("/profile/files/{path:path}/revisions")
def list_profile_revisions(path: str) -> list[ProfileRevision]:
    raise not_implemented()


@router.get("/profile/files/{path:path}")
def get_profile_file(path: str) -> ProfileFile:
    raise not_implemented()


@router.put("/profile/files/{path:path}")
def put_profile_file(path: str, body: ProfileFileWrite) -> ProfileFile:
    raise not_implemented()


@router.post("/profile/distill", status_code=202)
def distill_profile() -> TaskRef:
    raise not_implemented()
