"""Builds the configured sources from `config/sources.yaml` (ARCHITECTURE §4, §14)."""

from __future__ import annotations

import logging

from jobsearcher.config import env, load_sources
from jobsearcher.sources.base import JobSource
from jobsearcher.sources.http import HttpClient

log = logging.getLogger(__name__)

# Order sources run in: the most structured source first, so it becomes primary (§4.5).
SOURCE_ORDER = ("nav", "finn_api", "teamtailor", "page_watch")


def _build(name: str, http: HttpClient, config: dict) -> JobSource | None:
    # Imported lazily: a broken or missing source must not stop the others.
    if name == "finn_api":
        from jobsearcher.sources.finn_api import FinnApiSource

        return FinnApiSource(http, config)
    if name == "nav":
        from jobsearcher.sources.nav_feed import NavFeedSource

        return NavFeedSource(http, config, env().nav_feed_token)
    return None


def build_sources(http: HttpClient, names: list[str] | None = None, *, force: bool = False) -> list[JobSource]:
    """Enabled sources, or exactly `names` when given (an explicit name runs even if disabled).

    `force` is passed to each source's config: it skips cooldowns and weekly schedules (§4.2)."""
    config = load_sources()
    wanted = list(names) if names else [n for n in SOURCE_ORDER if (config.get(n) or {}).get("enabled")]
    unknown = [n for n in wanted if n not in SOURCE_ORDER]
    if unknown:
        raise ValueError(f"Ukjent kilde: {', '.join(unknown)}")
    out: list[JobSource] = []
    for name in SOURCE_ORDER:
        if name not in wanted:
            continue
        try:
            source_config = dict(config.get(name) or {})
            if force:
                source_config["force"] = True
            source = _build(name, http, source_config)
        except ImportError as e:
            log.warning("source not available", extra={"data": {"source": name, "error": str(e)}})
            continue
        if source is None:
            log.warning("source not implemented", extra={"data": {"source": name}})
            continue
        out.append(source)
    return out
