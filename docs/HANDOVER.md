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
  - 04 Finn mobile API: APK dekompilert 2026-10-10 (jadx 1.5.4 + androguard). Base-URL (`https://appsgw.finn.no/`), HMAC-nøkkel (`d45ff03c-b783-44d9-b94a-bb28dbc016a6`), signeringsregel, `FINN-GW-Service`-mapping og jobbsøk-endepunkt dokumentert. Full liste over 108 service-headere i `docs/spikes/04-finn-services.txt`. Erstatter tidligere e-postvarsel-design.
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
1. Install `uv`. Add `pyproject.toml` (deps from ARCHITECTURE §16) and the `jobsearcher` CLI (typer) with `init-db`, `run`. `finnsig` droppes — vi implementerer signeringen selv (se spike 04 §Signering), det er ~20 linjer Python og lar oss unngå dependency-risiko F5.
2. Config loading: `config/*.yaml` + `.env` via pydantic-settings. Write the first versions of `settings.yaml`, `locations.yaml` (§5.3), `sources.yaml` (§4.2 Finn search table, §4.4), `tech_aliases.yaml`.
3. DB models from §9 (SQLModel) + Alembic initial migration.
4. `sources/http.py` (rate limit, retry, ETag, cache, robots.txt).
5. `sources/nav_feed.py`: cursor in `source_state`, fixtures from the public feed.
6. **Verifiser HMAC-signeringen** med `curl`-oppskriften i spike 04 §Verifiserings-sjekkliste før kode skrives. Hent også filter-metadata (`include_results=false&include_filters=true`) per `searchkey` og lagre som fixture — denne gir mapping fra lesbare `occupation`/`location`/`experience`/`education`-navn til Finns ID-er.
7. `sources/finn_api.py` + `sources/finn_sig.py`: HMAC-signering fra spike 04, search-flyt (`/search/job-fulltime` m.fl.) med `page`-paginering og `publishedAt`-cursor, cache rå JSON under `data/cache/finn/`.
8. `pipeline/`: normalize, clean (§4.6), dedupe/repost (§4.5), hardfilter with trust levels (§5.1), lock file, `scrape_runs` health.
9. Tests for each step.

## Open questions and risks (details in ARCHITECTURE §19)
1. **Finn mobile API is a ToS grey area.** Deliberate, informed decision; low-volume, private use. See spike 04.
2. The Finn signature or endpoints may break at any time (key rotation, format changes, detection). Pin app version (`261006-ec709768`) in User-Agent; fall back to `manual` paste if it dies. HMAC-nøkkelen må oppdateres fra en ny APK hvis Finn roterer den.
3. Isolation flags for `claude -p` must get the overhead from ~39k down to <2k tokens per call. Verify when building `llm/claude_code.py` (phase 2).
4. Anthropic may change subscription billing for `claude -p`. The `anthropic_api` backend is the fallback.

## Session log
- 2026-10-10: Interviewed the user, wrote ARCHITECTURE v0.1→v0.3, filled the profile from the CV, prior applications and GitHub, ran spikes 01–04, set up and verified Gmail/IMAP + Claude CLI, added AGENTS.md and this handover.
- 2026-10-10: Added documentation rules to AGENTS.md (doc ownership, update triggers, definition of done, versioning). ARCHITECTURE got a change log table.
- 2026-10-10: Added Stop hook `.claude/hooks/docs_check.py` that enforces the HANDOVER update when code changes (tested: 6 cases). Opened the PR for docs + hook.
- 2026-10-10: ARCHITECTURE v0.4. Switched Finn from email alerts to the mobile API (HMAC-signed via `finnsig`, endpoints reverse-engineered from the APK). Dropped the `enricher` agent — API returns full ad text. IMAP removed; Gmail is SMTP-only. Added spike 04, renumbered the earlier spikes, added `*.apk` to `.gitignore`.
- 2026-10-10: Dekompilerte Finn-APK-en (jadx + androguard i scratchpad). Fant base-URL (`https://appsgw.finn.no/`), HMAC-nøkkelen (`d45ff03c-b783-44d9-b94a-bb28dbc016a6`, dekodet fra `AppEnvironment.PRODUCTION_HMAC_KEY` via ROT13+base64), nøyaktig signeringsmelding (`METHOD;PATH?QUERY;SERVICE;BODY` → HMAC-SHA512 → base64), service-header for jobbsøk (`Search-Quest-JB`), jobbsøk-endepunkt (`GET /search/{job-fulltime|…}`), full liste over 108 `FINN-GW-Service`-verdier. Oppdaterte spike 04 med konkrete funn, la til `docs/spikes/04-finn-services.txt`, droppet `finnsig`-biblioteket (vi implementerer signeringen selv — ~20 linjer).
