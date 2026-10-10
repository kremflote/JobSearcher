"""Reading the context layers (ARCHITECTURE §6.1).

Layer 1 (profile) is read from PROFILE_DIR, ignoring files and folders that start with `_` or `.`.
Layer 2 (derived) lives in DERIVED_DIR with a `manifest.json` that records what it was made from.
Layer 3 (prompts) are markdown files with `version` in the frontmatter.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter

from jobsearcher.config import env

PROFILE_SUFFIXES = {".md", ".yaml", ".yml", ".txt"}
DERIVED_FILES = ("profile_short.md", "profile_long.md", "voice.md")
MANIFEST = "manifest.json"
DISTILLER_PROMPT = "distiller.md"


# --- Layer 1 -----------------------------------------------------------------------------


def profile_files(profile_dir: Path | None = None) -> list[Path]:
    """Source files in layer 1, sorted by relative path."""
    root = profile_dir or env().profile_dir
    if not root.is_dir():
        return []
    out = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if not p.is_file() or p.suffix.lower() not in PROFILE_SUFFIXES:
            continue
        if any(part.startswith(("_", ".")) for part in rel.parts):
            continue
        out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _normalized(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def file_hash(path: Path) -> str:
    return hashlib.sha256(_normalized(path.read_bytes())).hexdigest()


def profile_file_hashes(profile_dir: Path | None = None) -> dict[str, str]:
    root = profile_dir or env().profile_dir
    return {p.relative_to(root).as_posix(): file_hash(p) for p in profile_files(root)}


def hash_of(file_hashes: dict[str, str]) -> str:
    joined = "\n".join(f"{k}:{v}" for k, v in sorted(file_hashes.items()))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def profile_hash(profile_dir: Path | None = None) -> str:
    """Hash over all layer-1 files (path + content). Changes when any source file changes."""
    return hash_of(profile_file_hashes(profile_dir))


def read_profile(profile_dir: Path | None = None) -> dict[str, str]:
    """Relative path (forward slashes) → text, for all layer-1 files."""
    root = profile_dir or env().profile_dir
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8").replace("\r\n", "\n")
        for p in profile_files(root)
    }


def read_profile_file(rel: str) -> str | None:
    path = env().profile_dir / rel
    return path.read_text(encoding="utf-8") if path.is_file() else None


# --- Layer 3 -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    body: str


def load_prompt(ref: str) -> Prompt:
    """Load a prompt by manifest reference (`prompts/filter.md`) or file name (`filter.md`)."""
    name = ref.removeprefix("prompts/")
    post = frontmatter.load(str(env().prompts_dir / name))
    return Prompt(name=name, version=str(post.get("version", "0")), body=post.content.strip())


def distiller_prompt_version() -> str:
    return load_prompt(DISTILLER_PROMPT).version


# --- Layer 2 -----------------------------------------------------------------------------


def read_manifest() -> dict[str, Any] | None:
    path = env().derived_dir / MANIFEST
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def read_derived(name: str) -> str | None:
    """A derived file by name, with or without `.md` (`profile_short` / `profile_short.md`)."""
    if not name.endswith(".md"):
        name += ".md"
    path = env().derived_dir / name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def write_derived(files: dict[str, str], manifest: dict[str, Any]) -> None:
    """Write derived files, then the manifest last (so a crash leaves the set outdated)."""
    root = env().derived_dir
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text.rstrip() + "\n", encoding="utf-8")
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def derived_profile_hash() -> str | None:
    """The profile hash the current derived files were made from."""
    manifest = read_manifest()
    return manifest.get("profile_hash") if manifest else None


def derived_outdated() -> bool:
    """True when layer 2 is missing, incomplete, or made from another profile or distiller prompt."""
    manifest = read_manifest()
    if not manifest:
        return True
    root = env().derived_dir
    if any(not (root / name).is_file() for name in DERIVED_FILES):
        return True
    if manifest.get("profile_hash") != profile_hash():
        return True
    return manifest.get("distiller_prompt_version") != distiller_prompt_version()
