"""Rebuild `web/dist/` on `serve` start when the frontend sources are newer than the build.

`serve` serves the built SPA, so without this a frontend change stays invisible until someone
runs `npm run build`. Failures only log: the server still starts with the old build (or none).
"""

import logging
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

from jobsearcher.config import ROOT

log = logging.getLogger(__name__)

WEB = ROOT / "web"

# Everything under web/ that ends up in the build. Tests, e2e and mocks only live in src/.
_SOURCE_DIRS = ("src", "public")
_SOURCE_FILES = (
    "index.html",
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
)

Runner = Callable[..., subprocess.CompletedProcess]


def _sources(web: Path) -> Iterator[Path]:
    for name in _SOURCE_DIRS:
        folder = web / name
        if folder.is_dir():
            yield from (p for p in folder.rglob("*") if p.is_file())
    for name in _SOURCE_FILES:
        path = web / name
        if path.is_file():
            yield path


def is_stale(web: Path = WEB) -> bool:
    """True when web/dist is missing or older than any frontend source."""
    built = web / "dist" / "index.html"
    if not built.is_file():
        return True
    stamp = built.stat().st_mtime
    return any(p.stat().st_mtime > stamp for p in _sources(web))


def ensure_built(web: Path = WEB, run: Runner = subprocess.run) -> bool:
    """Build the frontend if stale. Returns True when a build ran and succeeded."""
    if not (web / "src").is_dir():
        return False  # e.g. a container that ships only dist/
    if not is_stale(web):
        return False
    npm = shutil.which("npm")
    if npm is None:
        log.warning("web/dist er utdatert, men npm finnes ikke; serverer gammel build")
        return False
    if not (web / "node_modules").is_dir():
        log.info("Installerer frontend-avhengigheter (npm ci)")
        if run([npm, "ci"], cwd=web).returncode != 0:
            log.error("npm ci feilet; serverer gammel build")
            return False
    log.info("Frontend er endret siden siste build; kjører npm run build")
    if run([npm, "run", "build"], cwd=web).returncode != 0:
        log.error("npm run build feilet; serverer gammel build")
        return False
    return True
