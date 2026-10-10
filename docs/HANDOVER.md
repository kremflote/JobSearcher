# Handover

> Keep this file short. Update it at the end of every session: status, next task, open questions, and one line in the log.

**Last updated:** 2026-10-10
**Phase:** 0 (design + research) done → **phase 1 (foundation) is next.** No application code exists yet.

## Status

### Done
- Design doc `docs/ARCHITECTURE.md` v0.3: all main decisions made (§2), file tree (§15), roadmap (§17)
- Research notes in `docs/spikes/`:
  - 01 Finn: no scraping, use email alerts
  - 02 NAV feed
  - 03 Claude subscription: works, must be isolated
  - 04 trainee sources
- User profile filled in `context/profile/` (gitignored, personal data)
- Draft agent prompts in `context/prompts/` (filter, researcher, writer, reviser, distiller, extractor, enricher), all v0.1 and untested
- `.env` exists with `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`. IMAP login verified.
- `claude -p` verified on the subscription (~39k tokens overhead per call without isolation, see spike 03)
- Finn: 5 saved searches with Finn filters for no experience/junior and education level. Gmail label `JobSearcher/Finn` created.

### Waiting on the user
- [ ] First Finn alert email, saved as `tests/fixtures/private/finn-varsel-1.eml`. Blocks the Finn email parser only.
- [ ] NAV private token → `NAV_FEED_TOKEN` in `.env`. Blocks live NAV runs only. Development can use the public token from the NAV docs.
- [ ] Confirm geography per job type (ARCHITECTURE §5.3): permanent = `oslo_omegn`, trainee/graduate/summer = `norge`. Currently assumed yes.
- [ ] Optional: review the company list in `docs/spikes/04-trainee-sources.md`.

## Next task: phase 1 (foundation)
Goal: `jobsearcher run` fills SQLite with normalized, deduplicated, hardfiltered jobs. No LLM yet.

Suggested order:
1. Install `uv`. Add `pyproject.toml` (deps from ARCHITECTURE §16) and the `jobsearcher` CLI (typer) with `init-db`, `run`.
2. Config loading: `config/*.yaml` + `.env` via pydantic-settings. Write the first versions of `settings.yaml`, `locations.yaml` (§5.3), `sources.yaml` (§4.2 search table, §4.4), `tech_aliases.yaml`.
3. DB models from §9 (SQLModel) + Alembic initial migration.
4. `sources/http.py` (rate limit, retry, ETag, cache, robots.txt).
5. `sources/nav_feed.py`: cursor in `source_state`, fixtures from the public feed.
6. `pipeline/`: normalize, clean (§4.6), dedupe/repost (§4.5), hardfilter with trust levels (§5.1), lock file, `scrape_runs` health.
7. `sources/finn_email.py`: IMAP read of the label. Parser **after** the sample email arrives.
8. Tests for each step.

## Open questions and risks (details in ARCHITECTURE §19)
1. **Open:** How much ad text can be found for Finn jobs without touching finn.no (automatic enrichment, §4.2)? Measure after ~2 weeks of running.
2. Does the Finn alert email include the saved search name? (Unknown until the sample arrives.)
3. Isolation flags for `claude -p` must get the overhead from ~39k down to <2k tokens per call. Verify when building `llm/claude_code.py` (phase 2).
4. Anthropic may change subscription billing for `claude -p`. The `anthropic_api` backend is the fallback.

## Session log
- 2026-10-10: Interviewed the user, wrote ARCHITECTURE v0.1→v0.3, filled the profile from the CV, prior applications and GitHub, ran spikes 01–04, set up and verified Gmail/IMAP + Claude CLI, added AGENTS.md and this handover.
- 2026-10-10: Added documentation rules to AGENTS.md (doc ownership, update triggers, definition of done, versioning). ARCHITECTURE got a change log table.
- 2026-10-10: Added Stop hook `.claude/hooks/docs_check.py` that enforces the HANDOVER update when code changes (tested: 6 cases). Opened the PR for docs + hook.
