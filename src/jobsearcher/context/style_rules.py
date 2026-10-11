"""Style rules saved from the revision chat ("Lagre som stilregel", ARCHITECTURE §6.1, §7.2).

A rule is appended as a bullet under one heading in `style_overrides.md`, and the new file is
stored in `profile_revisions` like any other profile edit. The caller commits.
"""

from __future__ import annotations

from sqlmodel import Session

from jobsearcher.config import env
from jobsearcher.context import profile_store

STYLE_FILE = "style_overrides.md"
HEADING = "## Fra revisjonschatten"


def with_rule(text: str, rule: str) -> str:
    """`text` with `- rule` as the last bullet under HEADING (added at the end if missing).
    Unchanged if the bullet is already there."""
    bullet = f"- {rule.strip()}"
    lines = text.replace("\r\n", "\n").rstrip("\n").split("\n") if text.strip() else []
    if bullet in (line.strip() for line in lines):
        return text
    if HEADING not in lines:
        lines += ["", HEADING, bullet] if lines else [HEADING, bullet]
        return "\n".join(lines) + "\n"
    start = lines.index(HEADING)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    lines.insert(end, bullet)
    return "\n".join(lines) + "\n"


def add_style_rule(session: Session, rule: str) -> None:
    path = env().profile_dir / STYLE_FILE
    old = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else None
    new = with_rule(old or "", rule)
    if new == old:
        return
    profile_store.write(session, STYLE_FILE, new, profile_store.content_hash(old) if old is not None else None)
