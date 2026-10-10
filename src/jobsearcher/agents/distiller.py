"""Distiller agent (ARCHITECTURE §6.1 layer 2, §7.5).

Reads all of layer 1 and writes `profile_short.md`, `profile_long.md`, `voice.md` and
`manifest.json` to DERIVED_DIR. Runs when the profile hash or the distiller prompt changes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from jobsearcher.agents.base import run_agent
from jobsearcher.agents.schemas import DistilledProfile
from jobsearcher.context import loader
from jobsearcher.llm.base import LLMBackend

log = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Destiller kildefilene over til `profile_short`, `profile_long` og `voice` etter instruksene. "
    "Hvert felt er et markdown-dokument."
)


class DistillError(RuntimeError):
    pass


def distill(force: bool = False, *, backend: LLMBackend | None = None) -> bool:
    """Regenerate the derived profile. Returns False if it was up to date and not forced."""
    if not force and not loader.derived_outdated():
        return False
    # Hash before the call, so edits made while the agent runs mark the result outdated.
    file_hashes = loader.profile_file_hashes()
    if not file_hashes:
        raise DistillError("Profilmappen er tom; fyll ut context/profile/ først.")

    outcome = run_agent("distiller", instructions=INSTRUCTIONS, backend=backend)
    if outcome.output is None or outcome.error:
        raise DistillError(f"Destilleringen feilet: {outcome.error}")
    out: DistilledProfile = outcome.output  # type: ignore[assignment]

    files = {
        "profile_short.md": out.profile_short,
        "profile_long.md": out.profile_long,
        "voice.md": out.voice,
    }
    manifest = {
        "profile_hash": loader.hash_of(file_hashes),
        "files": file_hashes,
        "distiller_prompt_version": outcome.prompt_version,
        "model": outcome.model,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    loader.write_derived(files, manifest)
    log.info(
        "profile distilled",
        extra={"data": {"profile_hash": manifest["profile_hash"], "cost_usd": outcome.cost_usd}},
    )
    return True
