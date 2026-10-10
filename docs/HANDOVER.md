# Handover

> Keep this file short. Update it at the end of every session: status, next task, open questions, and one line in the log.

**Last updated:** 2026-10-10
**Phase:** 0 (design + research) done → **phase 1 (foundation) is next.** No application code exists yet.

## Status

### Done
- Design doc `docs/ARCHITECTURE.md` v0.4: all main decisions made (§2), file tree (§15), roadmap (§17)
- Research notes in `docs/spikes/`:
  - 01 NAV feed
  - 02 Claude subscription: works, must be isolated
  - 03 trainee sources
  - 04 Finn mobile API: use the app's HMAC-signed API via `finnsig`, endpoints reverse-engineered from the APK in project root (gitignored). Replaces the earlier email-alert design.
- User profile filled in `context/profile/` (gitignored, personal data)
- Draft agent prompts in `context/prompts/` (filter, researcher, writer, reviser, distiller, extractor), all v0.1 and untested. The old `enricher` prompt is obsolete — the Finn API returns full ad text.
- `.env` has `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` (now used only for SMTP digest).
- `claude -p` verified on the subscription (~39k tokens overhead per call without isolation, see spike 02)
- Finn APK downloaded to project root (`FINN.no_*.apk`, gitignored via `*.apk`).

### Waiting on the user
- [ ] NAV private token → `NAV_FEED_TOKEN` in `.env`. Blocks live NAV runs only. Development can use the public token from the NAV docs.
- [x] Geography per job type (ARCHITECTURE §5.3) confirmed: permanent = `oslo_omegn`, trainee/graduate/summer = `norge`.
- [ ] Optional: review the company list in `docs/spikes/03-trainee-sources.md`.
- (No longer needed: Finn saved searches, Gmail label `JobSearcher/Finn`, sample `.eml` fixture. The user can delete them.)

## Next task: phase 1 (foundation)
Goal: `jobsearcher run` fills SQLite with normalized, deduplicated, hardfiltered jobs. No LLM yet.

Suggested order:
1. Install `uv`. Add `pyproject.toml` (deps from ARCHITECTURE §16, including `finnsig`) and the `jobsearcher` CLI (typer) with `init-db`, `run`.
2. Config loading: `config/*.yaml` + `.env` via pydantic-settings. Write the first versions of `settings.yaml`, `locations.yaml` (§5.3), `sources.yaml` (§4.2 Finn search table, §4.4), `tech_aliases.yaml`.
3. DB models from §9 (SQLModel) + Alembic initial migration.
4. `sources/http.py` (rate limit, retry, ETag, cache, robots.txt).
5. `sources/nav_feed.py`: cursor in `source_state`, fixtures from the public feed.
6. **Decompile the Finn APK** (apktool + jadx) and document the endpoint table from spike 04 §Reverse engineering (base URL, search + ad endpoints, params, service-header values, static headers, app version). This is a prerequisite for `finn_api.py`.
7. `sources/finn_api.py` + `sources/finn_sig.py`: wrap `finnsig`, implement search → ad flow with cursor, cache raw JSON under `data/cache/finn/`.
8. `pipeline/`: normalize, clean (§4.6), dedupe/repost (§4.5), hardfilter with trust levels (§5.1), lock file, `scrape_runs` health.
9. Tests for each step.

## Open questions and risks (details in ARCHITECTURE §19)
1. **Finn mobile API is a ToS grey area.** Deliberate, informed decision; low-volume, private use. See spike 04.
2. The Finn signature or endpoints may break at any time (key rotation, format changes, detection). Pin app version from APK; fall back to `manual` paste if it dies.
3. Isolation flags for `claude -p` must get the overhead from ~39k down to <2k tokens per call. Verify when building `llm/claude_code.py` (phase 2).
4. Anthropic may change subscription billing for `claude -p`. The `anthropic_api` backend is the fallback.

## Session log
- 2026-10-10: Interviewed the user, wrote ARCHITECTURE v0.1→v0.3, filled the profile from the CV, prior applications and GitHub, ran spikes 01–04, set up and verified Gmail/IMAP + Claude CLI, added AGENTS.md and this handover.
- 2026-10-10: Added documentation rules to AGENTS.md (doc ownership, update triggers, definition of done, versioning). ARCHITECTURE got a change log table.
- 2026-10-10: Added Stop hook `.claude/hooks/docs_check.py` that enforces the HANDOVER update when code changes (tested: 6 cases). Opened the PR for docs + hook.
- 2026-10-10: ARCHITECTURE v0.4. Switched Finn from email alerts to the mobile API (HMAC-signed via `finnsig`, endpoints reverse-engineered from the APK). Dropped the `enricher` agent — API returns full ad text. IMAP removed; Gmail is SMTP-only. Added spike 04, renumbered the earlier spikes, added `*.apk` to `.gitignore`.
