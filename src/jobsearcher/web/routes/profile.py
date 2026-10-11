"""Profile files, history and the derived profile (FRONTEND §5.6, ARCHITECTURE §6.1)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from jobsearcher.api.schemas import (
    DerivedFile,
    DerivedProfile,
    ProfileFile,
    ProfileFileInfo,
    ProfileFileWrite,
    ProfileRevision,
    ProfileTree,
    TaskRef,
)
from jobsearcher.context import loader, profile_store
from jobsearcher.context.profile_store import ProfileError
from jobsearcher.db import models as m
from jobsearcher.db.session import get_session, session_scope
from jobsearcher.web.errors import ApiError
from jobsearcher.web.tasks import ACTIVE, TaskContext, TaskFailed, get_runner

router = APIRouter(tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]


def _api_error(e: ProfileError) -> ApiError:
    return ApiError(e.status, e.code, e.detail)


def _made_at(manifest: dict | None) -> datetime | None:
    raw = (manifest or {}).get("created_at")
    try:
        return datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None


@router.get("/profile/files")
def list_profile_files() -> ProfileTree:
    return ProfileTree(
        files=[ProfileFileInfo(path=p, size=size, updated_at=at) for p, size, at in profile_store.list_files()],
        folders=profile_store.folders(),
        profile_hash=loader.profile_hash(),
        derived_outdated=loader.derived_outdated(),
        derived_at=_made_at(loader.read_manifest()),
    )


# Declared before the file routes: `{path:path}` would otherwise swallow "/revisions".
@router.get("/profile/files/{path:path}/revisions")
def list_profile_revisions(path: str, session: SessionDep) -> list[ProfileRevision]:
    try:
        rows = profile_store.revisions(session, path)
    except ProfileError as e:
        raise _api_error(e) from e
    return [
        ProfileRevision(id=r.id, path=r.path, content=r.content, content_hash=r.content_hash, created_at=r.created_at)
        for r in rows
    ]


@router.get("/profile/files/{path:path}")
def get_profile_file(path: str) -> ProfileFile:
    try:
        content, digest, at = profile_store.read(path)
    except ProfileError as e:
        raise _api_error(e) from e
    return ProfileFile(path=path, content=content, content_hash=digest, updated_at=at)


@router.put("/profile/files/{path:path}")
def put_profile_file(path: str, body: ProfileFileWrite, session: SessionDep) -> ProfileFile:
    try:
        content, digest, at = profile_store.write(session, path, body.content, body.base_hash)
    except ProfileError as e:
        raise _api_error(e) from e
    session.commit()
    return ProfileFile(path=path, content=content, content_hash=digest, updated_at=at)


@router.get("/profile/derived")
def get_derived_profile() -> DerivedProfile:
    manifest = loader.read_manifest()
    files = []
    for name in loader.DERIVED_FILES:
        content = loader.read_derived(name)
        if content is not None:
            files.append(DerivedFile(name=name, content=content, previous_content=loader.read_previous_derived(name)))
    return DerivedProfile(files=files, made_at=_made_at(manifest), model=(manifest or {}).get("model"))


def _ensure_no_distill() -> None:
    with session_scope() as session:
        active = session.exec(
            select(m.Task.id).where(m.Task.kind == "distill", col(m.Task.status).in_(ACTIVE))
        ).first()
    if active is not None:
        raise ApiError(409, "distill_active", "Profilen destilleres allerede.")


def _distill_task(ctx: TaskContext) -> str:
    from jobsearcher.agents.distiller import DistillError, distill

    ctx.progress(0.1, "Destillerer profilen")
    try:
        distill(force=True)
    except DistillError as e:
        raise TaskFailed(str(e)) from e
    return "Ferdig: profilen er destillert"


@router.post("/profile/distill", status_code=202)
def distill_profile() -> TaskRef:
    return TaskRef(task_id=get_runner().submit("distill", {}, _distill_task, guard=_ensure_no_distill))
