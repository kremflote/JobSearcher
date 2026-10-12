"""Distiller agent (ARCHITECTURE §6.1 layer 2, §7.5).

Reads all of layer 1 and writes `profile_short.md`, `profile_long.md`, `voice.md` and
`manifest.json` to DERIVED_DIR. Runs when the profile hash or the distiller prompt changes.

When only voice-only files changed (writing samples, style rules), just `voice.md` is replaced and
the scoring hash is carried over, so the jobs are not marked for rescoring (§5.5).
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

    previous = loader.read_manifest()
    voice_only = (
        previous is not None
        and previous.get("distiller_prompt_version") == loader.distiller_prompt_version()
        and all(loader.read_derived(name) is not None for name in loader.DERIVED_FILES)
        and loader.voice_only_change(previous.get("files") or {}, file_hashes)
    )

    outcome = run_agent("distiller", instructions=INSTRUCTIONS, backend=backend)
    if outcome.output is None or outcome.error:
        raise DistillError(f"Destilleringen feilet: {outcome.error}")
    out: DistilledProfile = outcome.output  # type: ignore[assignment]

    if voice_only:
        files = {"voice.md": out.voice}
    else:
        files = {
            "profile_short.md": out.profile_short,
            "profile_long.md": out.profile_long,
            "voice.md": out.voice,
        }
    profile_hash = loader.hash_of(file_hashes)
    manifest = {
        "profile_hash": profile_hash,
        "scoring_hash": loader.scoring_hash() if voice_only else profile_hash,
        "files": file_hashes,
        "distiller_prompt_version": outcome.prompt_version,
        "model": outcome.model,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    loader.write_derived(files, manifest)
    log.info(
        "profile distilled",
        extra={"data": {"profile_hash": profile_hash, "voice_only": voice_only, "cost_usd": outcome.cost_usd}},
    )
    return True
