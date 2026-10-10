# Handover

> Keep this file short. Update it at the end of every session: status, next task, open questions, and one line in the log.

**Last updated:** 2026-10-10
**Phase:** 0, 0b and frontend F0 done → **next: frontend F1 (daily loop) against mocks.** Branch `feat/frontend-f0`, PR to main.

## Status

### Done
- Design doc `docs/ARCHITECTURE.md` v0.9: all main decisions made (§2), file tree (§15), roadmap (§17)
- Frontend design `docs/FRONTEND.md` v0.2 (from interview 2026-10-10): React SPA (Vite + TS + Tailwind/shadcn) for PC and phone, contract-first against MSW mocks, screens, API contract v0, waves F0–F5. Long-term hosting on the Raspberry Pi homeserver in Docker via Tailscale (`jobb.mariuskristensen.no`); code must be Docker-ready from phase 1.
- Research notes in `docs/spikes/`:
  - 01 NAV feed
  - 02 Claude subscription: works, must be isolated
  - 03 trainee sources
  - 04 Finn mobile API: APK dekompilert 2026-10-10 (jadx 1.5.4 + androguard). Base-URL (`https://appsgw.finn.no/`), HMAC-nøkkel (`d45ff03c-b783-44d9-b94a-bb28dbc016a6`), signeringsregel, `FINN-GW-Service`-mapping og jobbsøk-endepunkt dokumentert. Full liste over 108 service-headere i `docs/spikes/04-finn-services.txt`. Erstatter tidligere e-postvarsel-design.
- **Phase 0b Finn check done:** HMAC signing verified against the live API (unsigned → 403, signed → 200). Searchkey path is the enum name (`/search/SEARCH_ID_JOB_FULLTIME`). Search results have **no ad text**; it comes from `JobPosting` JSON-LD on `https://www.finn.no/job/ad/{id}` (ARCHITECTURE §4.2 v0.9). Filter IDs in spike 04 §Oppdatering; fixtures in `tests/fixtures/finn/` (+ a raw search in `tests/fixtures/private/finn/`).
- User profile filled in `context/profile/` (gitignored, personal data)
- Draft agent prompts in `context/prompts/` (filter, researcher, writer, reviser, distiller, extractor), all v0.1 and untested. The old `enricher` prompt is obsolete — the Finn API returns full ad text.
- `.env` has `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` (now used only for SMTP digest).
- `claude -p` verified on the subscription (~39k tokens overhead per call without isolation, see spike 02)
- Finn APK downloaded to project root (`FINN.no_*.apk`, gitignored via `*.apk`).

- **Frontend F0 (skeleton) done** (2026-10-10):
  - Backend: `pyproject.toml` (uv, Python 3.12), `api/schemas.py` with the whole v0 contract (FRONTEND §7), FastAPI app where every route returns `501 {detail, code}` except `/api/health`, `jobsearcher serve`, `scripts/export_openapi.py` → `web/openapi.json`. `uv run pytest`: 3 tests, including one that fails when `openapi.json` is stale.
  - `web/`: Vite 8 + React 19 + TS 5.9 + Tailwind 4 + shadcn (button, dropdown-menu, badge, skeleton) + React Router 7 + TanStack Query + `openapi-fetch` + MSW. App shell (bottom tabs < 768, icon sidebar 768–1023, text sidebar ≥ 1024), light/dark/system theme, PWA manifest + icons ("Jobbsøk"), placeholder screens.
  - Invented fixture set in `web/src/mocks/fixtures/*.ts`: 41 jobs over all types, all 10 statuses, reposts, title-only, unknown deadlines, 8 discarded, runs/agent runs, profile files, settings. Dates are relative to today. MSW serves all read endpoints; mutations return 501 until their wave.
  - Tests: Vitest 24 (format, fixtures, shell), Playwright 8 (2 viewports: navigation, layout, theme, manifest). `npm run build` OK.

### Waiting on the user
- [ ] NAV private token → `NAV_FEED_TOKEN` in `.env`. Blocks live NAV runs only. Development can use the public token from the NAV docs.
- [x] Geography per job type (ARCHITECTURE §5.3) confirmed: permanent = `oslo_omegn`, trainee/graduate/summer = `norge`.
- [x] Company list in spike 03 approved as is.
- [x] Open questions in `docs/FRONTEND.md` resolved (preliminary choices accepted, now in §2).
- [x] Cloudflare DNS and NPM proxy host done.
- [ ] Before phase 4b: `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN` in the Pi's `jobsearcher.env` (ARCHITECTURE §18).
- (No longer needed: Finn saved searches, Gmail label `JobSearcher/Finn`, sample `.eml` fixture. The user can delete them.)

## Next task
Frontend first (ARCHITECTURE §17 v0.8): build the whole UI against mocks, let the user try it, then build the backend.

### Frontend wave F1 (daily loop), see FRONTEND §5.1–5.3 and §8
1. Oversikt (§5.1) from `GET /api/overview`, replacing the placeholder in `web/src/features/placeholders.tsx`.
2. Jobber (§5.2): type tabs, filters in the URL, sorting, infinite scroll (cursor), `ScoreBadge`/`DeadlineBadge` (use `lib/format.ts`, `lib/status.ts`), swipe triage on mobile with undo toast, keyboard triage on PC, master-detail ≥ 1024 px.
3. Jobbdetalj (§5.3) incl. the fixed action bar on mobile.
4. Mock mutations: `PUT /api/jobs/{id}/status`, `POST /api/runs` + task progress (`useTask`), active-task indicator.
5. Playwright: triage a mock day by swipe (mobile) and keyboard (PC).

After F1: user test on PC and phone (`npm run dev:mock -- --host`). Fix findings in FRONTEND + the contract before F2.

### Later: backend phase 1 (foundation)
Starts after the F4 user test. `finn_api.py` (search + JSON-LD detail fetch) + `finn_sig.py` (port the signing from spike 04; test against the fixtures), NAV source, pipeline (normalize, clean §4.6, dedupe §4.5, hardfilter §5.1, lock, `scrape_runs`), `serve` with the first real endpoints.

## Open questions and risks (details in ARCHITECTURE §19)
1. **Finn mobile API is a ToS grey area.** Deliberate, informed decision; low-volume, private use. See spike 04.
2. The Finn signature or endpoints may break at any time (key rotation, format changes, detection). Pin app version (`261006-ec709768`) in User-Agent; fall back to `manual` paste if it dies. HMAC-nøkkelen må oppdateres fra en ny APK hvis Finn roterer den.
3. Isolation flags for `claude -p` must get the overhead from ~39k down to <2k tokens per call. Verify when building `llm/claude_code.py` (phase 2).
4. Anthropic may change subscription billing for `claude -p`. The `anthropic_api` backend is the fallback.
5. `claude -p` inside a Docker container on the Pi (arm64, `CLAUDE_CODE_OAUTH_TOKEN`) is unverified. Check at phase 4b.
6. In production the profile lives only in the Pi data volume, edited via the dashboard. Backup relies on the Pi's Restic (same disk as data).

## Session log
- 2026-10-10: Interviewed the user, wrote ARCHITECTURE v0.1→v0.3, filled the profile from the CV, prior applications and GitHub, ran spikes 01–04, set up and verified Gmail/IMAP + Claude CLI, added AGENTS.md and this handover.
- 2026-10-10: Added documentation rules to AGENTS.md (doc ownership, update triggers, definition of done, versioning). ARCHITECTURE got a change log table.
- 2026-10-10: Added Stop hook `.claude/hooks/docs_check.py` that enforces the HANDOVER update when code changes (tested: 6 cases). Opened the PR for docs + hook.
- 2026-10-10: ARCHITECTURE v0.4. Switched Finn from email alerts to the mobile API (HMAC-signed via `finnsig`, endpoints reverse-engineered from the APK). Dropped the `enricher` agent — API returns full ad text. IMAP removed; Gmail is SMTP-only. Added spike 04, renumbered the earlier spikes, added `*.apk` to `.gitignore`.
- 2026-10-10: Dekompilerte Finn-APK-en (jadx + androguard i scratchpad). Fant base-URL (`https://appsgw.finn.no/`), HMAC-nøkkelen (`d45ff03c-b783-44d9-b94a-bb28dbc016a6`, dekodet fra `AppEnvironment.PRODUCTION_HMAC_KEY` via ROT13+base64), nøyaktig signeringsmelding (`METHOD;PATH?QUERY;SERVICE;BODY` → HMAC-SHA512 → base64), service-header for jobbsøk (`Search-Quest-JB`), jobbsøk-endepunkt (`GET /search/{job-fulltime|…}`), full liste over 108 `FINN-GW-Service`-verdier. Oppdaterte spike 04 med konkrete funn, la til `docs/spikes/04-finn-services.txt`, droppet `finnsig`-biblioteket (vi implementerer signeringen selv — ~20 linjer).
- 2026-10-10: Frontend interview. Wrote `docs/FRONTEND.md` v0.1 (React SPA, PC + phone, MSW contract-first, waves F0–F5). ARCHITECTURE v0.6: React instead of HTMX, Docker on the Pi homeserver via Tailscale, scheduler in `serve` replaces Task Scheduler, `claude -p` in the container, profile edited in the dashboard (`profile_revisions`). Updated AGENTS (read order, ownership), README (stack).
- 2026-10-10: ARCHITECTURE v0.7. Cross-source dedupe specified (§4.5: source ID → normalized apply URL → company/orgnr + fuzzy title + location). User approved the spike 03 company list and finished Cloudflare DNS + NPM. Decided against React Native: the PWA covers the phone use case.
- 2026-10-10: Roadmap flipped to frontend first (ARCHITECTURE v0.8, FRONTEND v0.2): F0–F4 against mocks with user tests after F1 and F4, then backend phases. Finn HMAC check kept first as phase 0b (biggest risk).
- 2026-10-10: Phase 0b. Verified Finn HMAC signing live (~12 calls). Fixed spike 04 assumptions: path uses enum searchkey, param is `work_experience`, hierarchical location IDs, no ad text in search (→ fetch JSON-LD from the public ad page for new jobs). Saved filter fixtures. ARCHITECTURE v0.9.
- 2026-10-10: Merged the docs branch to main (PR #3); FRONTEND §10 open questions resolved into §2. Built frontend wave F0 on `feat/frontend-f0`: uv + Python 3.12, API contract v0 with 501 stubs and OpenAPI export, `web/` skeleton (app shell, theme, PWA "Jobbsøk"), MSW + 41 invented jobs, Vitest + Playwright. TS pinned to 5.9 (TS 7 breaks `openapi-typescript`). FRONTEND v0.4.
