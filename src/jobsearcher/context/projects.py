"""Choosing the projects a cover letter should use (ARCHITECTURE §6.4).

Projects are the files in `PROFILE_DIR/projects/*.md` (files starting with `_` are templates).
Each is scored against the job's `tech[]` and `role_category` from the filter agent:
+3 per shared technology, +2 if `categories` has the role, +2 for `highlight: true`,
+1 for work or personal projects (breaks ties against plain school assignments).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

from jobsearcher.config import env, load_tech_aliases

REAL_WORLD_TYPES = ("jobb", "personlig")


@dataclass
class Project:
    path: str
    title: str
    body: str
    tech: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    type: str = ""
    highlight: bool = False
    score: int = 0


def normalize_tech(names: list[str]) -> set[str]:
    table = load_tech_aliases()
    out = set()
    for name in names or []:
        key = str(name).strip().lower()
        if key:
            out.add(table.get(key, key))
    return out


def _as_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v) for v in value]  # type: ignore[union-attr]


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or None
    return None


def load_projects(profile_dir: Path | None = None) -> list[Project]:
    root = (profile_dir or env().profile_dir) / "projects"
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.glob("*.md")):
        if p.name.startswith(("_", ".")):
            continue
        post = frontmatter.loads(p.read_text(encoding="utf-8").replace("\r\n", "\n"))
        meta = post.metadata
        out.append(
            Project(
                path=f"projects/{p.name}",
                title=str(meta.get("title") or _first_heading(post.content) or p.stem),
                body=post.content.strip(),
                tech=_as_list(meta.get("tech")),
                categories=[c.lower() for c in _as_list(meta.get("categories"))],
                type=str(meta.get("type") or "").lower(),
                highlight=bool(meta.get("highlight")),
            )
        )
    return out


def score_project(project: Project, job_tech: set[str], role_category: str | None) -> int:
    score = 3 * len(normalize_tech(project.tech) & job_tech)
    if role_category and role_category.lower() in project.categories:
        score += 2
    if project.highlight:
        score += 2
    if project.type in REAL_WORLD_TYPES:
        score += 1
    return score


def rank_projects(
    job_tech: list[str], role_category: str | None, profile_dir: Path | None = None
) -> list[Project]:
    """All projects, best first (stable on ties: file order)."""
    tech = normalize_tech(job_tech)
    projects = load_projects(profile_dir)
    for p in projects:
        p.score = score_project(p, tech, role_category)
    return sorted(projects, key=lambda p: -p.score)
