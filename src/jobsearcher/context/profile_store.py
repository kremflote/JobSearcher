"""Reading and writing layer-1 profile files from the dashboard (ARCHITECTURE §6.1, FRONTEND §5.6).

Every write stores the new content in `profile_revisions`. The first write to a file that has
no revisions also stores the content it replaces, so the original can always be restored.
The caller commits.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml
from sqlmodel import Session, col, select

from jobsearcher.config import env
from jobsearcher.context.loader import PROFILE_SUFFIXES, profile_files
from jobsearcher.db.models import ProfileRevision

TEMPLATE = "_template.md"
YAML_SUFFIXES = {".yaml", ".yml"}


class ProfileError(Exception):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


def content_hash(text: str) -> str:
    """Same hash as `loader.file_hash` for the file this text would be written to."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def resolve(rel: str, *, allow_template: bool = False) -> Path:
    """`rel` (forward slashes, relative to PROFILE_DIR) as a path inside PROFILE_DIR.

    Rejects absolute paths, `..`, hidden parts, unknown suffixes and, unless `allow_template`,
    names starting with `_` (templates and ignored files are not part of the profile)."""
    p = PurePosixPath(rel.replace("\\", "/"))
    bad = (
        not rel
        or p.is_absolute()
        or ":" in rel
        or any(part in ("", ".", "..") or part.startswith(".") for part in p.parts)
        or p.suffix.lower() not in PROFILE_SUFFIXES
    )
    underscore = any(part.startswith("_") for part in p.parts)
    if bad or (underscore and not (allow_template and p.name == TEMPLATE)):
        raise ProfileError(400, "invalid_path", f"Ugyldig filsti: {rel}")
    root = env().profile_dir.resolve()
    path = (root / Path(*p.parts)).resolve()
    if root not in path.parents:
        raise ProfileError(400, "invalid_path", f"Ugyldig filsti: {rel}")
    return path


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC)


def list_files() -> list[tuple[str, int, datetime]]:
    """(path, size, updated_at) for every layer-1 file."""
    root = env().profile_dir
    return [(p.relative_to(root).as_posix(), p.stat().st_size, _mtime(p)) for p in profile_files(root)]


def folders() -> list[str]:
    """Visible subfolders of PROFILE_DIR, where "Ny fil" can create files."""
    root = env().profile_dir
    if not root.is_dir():
        return []
    return sorted(
        d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(("_", "."))
    )


def read(rel: str) -> tuple[str, str, datetime]:
    """(content, hash, updated_at). `_template.md` in a folder can be read too."""
    path = resolve(rel, allow_template=True)
    if not path.is_file():
        raise ProfileError(404, "not_found", "Fant ikke filen.")
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return text, content_hash(text), _mtime(path)


def validate(rel: str, content: str) -> None:
    if PurePosixPath(rel).suffix.lower() in YAML_SUFFIXES:
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            where = f" (linje {mark.line + 1})" if mark is not None else ""
            raise ProfileError(422, "invalid_yaml", f"Ugyldig YAML{where}: {getattr(e, 'problem', e)}") from e


def write(session: Session, rel: str, content: str, base_hash: str | None) -> tuple[str, str, datetime]:
    """Write a profile file. `base_hash` must match the current file; None creates a new file."""
    path = resolve(rel)
    content = content.replace("\r\n", "\n")
    validate(rel, content)
    exists = path.is_file()
    if base_hash is None and exists:
        raise ProfileError(409, "file_exists", "Filen finnes allerede.")
    old = path.read_text(encoding="utf-8").replace("\r\n", "\n") if exists else None
    if base_hash is not None:
        if old is None:
            raise ProfileError(404, "not_found", "Fant ikke filen.")
        if content_hash(old) != base_hash:
            raise ProfileError(409, "conflict", "Filen er endret et annet sted. Last inn på nytt.")
    new_hash = content_hash(content)
    if old is not None and content_hash(old) == new_hash:
        return content, new_hash, _mtime(path)
    if old is not None and not _has_revisions(session, rel):
        session.add(ProfileRevision(path=rel, content=old, content_hash=content_hash(old), created_at=_mtime(path)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    session.add(ProfileRevision(path=rel, content=content, content_hash=new_hash))
    return content, new_hash, _mtime(path)


def _has_revisions(session: Session, rel: str) -> bool:
    return session.exec(select(ProfileRevision.id).where(ProfileRevision.path == rel).limit(1)).first() is not None


def revisions(session: Session, rel: str) -> list[ProfileRevision]:
    """Newest first."""
    resolve(rel)
    return list(
        session.exec(
            select(ProfileRevision)
            .where(ProfileRevision.path == rel)
            .order_by(col(ProfileRevision.created_at).desc(), col(ProfileRevision.id).desc())
        ).all()
    )
