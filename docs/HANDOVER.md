# Handover

> Keep this file short. Update it at the end of every session: status, next task, open questions, and one line in the log.

**Last updated:** 2026-10-10
**Phase:** 0, 0b, F0–F2 and **backend phases 1 + 2 done** (on `feat/backend-phase1-2`, uncommitted; branched from `feat/frontend-f1`, which has F2 as `d40e121`). Roadmap (ARCHITECTURE §17 v0.11): phase 1 → 2 → **F3 next** → 3 → F4 → 4.

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

- **Frontend F0 (skeleton) done** (2026-10-10):
  - Backend: `pyproject.toml` (uv, Python 3.12), `api/schemas.py` with the whole v0 contract (FRONTEND §7), FastAPI app where every route returns `501 {detail, code}` except `/api/health`, `jobsearcher serve`, `scripts/export_openapi.py` → `web/openapi.json`. `uv run pytest`: 3 tests, including one that fails when `openapi.json` is stale.
  - `web/`: Vite 8 + React 19 + TS 5.9 + Tailwind 4 + shadcn (button, dropdown-menu, badge, skeleton) + React Router 7 + TanStack Query + `openapi-fetch` + MSW. App shell (bottom tabs < 768, icon sidebar 768–1023, text sidebar ≥ 1024), light/dark/system theme, PWA manifest + icons ("Jobbsøk"), placeholder screens.
  - Invented fixture set in `web/src/mocks/fixtures/*.ts`: 41 jobs over all types, all 10 statuses, reposts, title-only, unknown deadlines, 8 discarded, runs/agent runs, profile files, settings. Dates are relative to today. MSW serves all read endpoints; mutations return 501 until their wave.
  - Tests: Vitest 24 (format, fixtures, shell), Playwright 8 (2 viewports: navigation, layout, theme, manifest). `npm run build` OK.

- **Frontend F1 (daily loop) done** (2026-10-10), see FRONTEND v0.5:
  - Oversikt (`features/overview/`): frister ≤ 14 d, nye siden sist, oppfølginger, kildestatus + kostnad (PC; under "Mer" på mobil).
  - Jobber (`features/jobs/`): typefaner, filtre i URL-en (rad på PC, handlingsark på mobil), cursor-paging med uendelig scroll, sveip-triage (< 768 px), tastatur (`j/k/i/x/u/o/Enter`), angre-toast, master-detalj ≥ 1024 px, egen detaljskjerm med fast handlingsrad på mobil.
  - Bakgrunnsjobber: `useTask`/`useActiveTasks`, indikator med "Avbryt", "Kjør nå". Mock: `PUT /api/jobs/{id}/status`, `POST /api/runs`, `GET /api/tasks?active`, `POST /api/tasks/{id}/cancel`.
  - Contract: `role` in `GET /api/jobs` is now `RoleCategory` (openapi.json re-exported).
  - Tests: Vitest 34, Playwright 13 (+3 skipped per viewport). `npm run build` and `uv run pytest` OK.

- **Frontend F2 (tracker) done** (2026-10-10), see FRONTEND v0.6 §5.4 and ARCHITECTURE v0.10 §9.1:
  - `features/tracker/`: kanban ≥ 1024 px with `@dnd-kit/core` (legal columns lit, illegal dimmed + toast, Avsluttet collapsed, chooser when several closed statuses fit), status menu on each card; grouped list < 1024 px with chips (`?vis=`) and an action sheet; panel at `?app=<id>` (right side panel / full screen) with next step, follow-up, notes and event log. Undo toast on every move.
  - Contract: `ApplicationCard.allowed_next` + `previous_status` (backend owns the transition table; undo = PATCH back to `previous_status`, deletes the last event). Mock `PATCH /api/applications/{id}` with 409 `invalid_transition`. openapi.json re-exported.
  - Oversikt follow-ups and the job detail ("Endre status i Tracker") link to the panel.
  - Tests: Vitest 44, Playwright 17 (+7 skipped across viewports). `npm run build` and `uv run pytest` OK.

- **Backend phases 1 + 2 done** (2026-10-10), see ARCHITECTURE v0.11 §4–§11, FRONTEND §7.1:
  - Foundation: `config.py` (env paths, `settings.yaml` models, overrides via `db/repo.py`, `today()` in Oslo), `config/*.yaml`, all §9 tables (`db/models.py`, aware UTC datetimes) + Alembic `0001`, JSON logging, typer CLI `serve | run | distill | init-db`.
  - Sources: `finn_sig.py` + `finn_api.py` (search → JSON-LD detail, cursor per search, device id in `data/finn_device.json`), `nav_feed.py` (feed summaries → `feedentry` detail after hard filter), `http.py` (rate limit, retry, robots, per-request timeout/retries), `registry.py`.
  - Pipeline: normalize, clean, dedupe (incl. Finn `job_title`), hardfilter (incl. NAV title rule `title_not_it`), lifecycle, lock, run (+ daily DB backup).
  - LLM: `claude_code` (isolated, ~1.5k overhead/call), `anthropic_api` (mock-tested only), `mock`; context loader/builder/budget; filter agent (batch 10, Haiku) and distiller (Sonnet); prompts filter/distiller v0.2; cost cap per Oslo month.
  - API: overview, jobs, job detail, triage, tracker (pulled forward from phase 4), runs/tasks, logs. `serve` serves `web/dist`, runs a task runner and the daily 07:00 scheduler with catch-up (pulled forward from phase 4).
  - Live (2026-10-10, Finn only): 108 ads → 45 hard-filtered → 63 detail fetches → 63 scored in 6 min for $0.06. Dashboard on :8765 shows them; triage/tracker/undo verified against the real API.
  - Tests: `uv run pytest` 168, web Vitest 44, typecheck OK, openapi.json unchanged.
  - Local data: `data/jobsearcher.db` is the live run above; the earlier dev DB is in `data/old/`.

### Waiting on the user
- [ ] NAV private token → `NAV_FEED_TOKEN` in `.env` (email in ARCHITECTURE §18). `.env` currently has NAV's **public** dev token, which rotates. NAV has not completed a live run yet: its gateway returned 500/504 on 2026-10-10 (spike 01 §Oppdatering). The daily run retries; check `GET /api/logs/runs` or Oversikt › Kildestatus.
- [x] Geography per job type (ARCHITECTURE §5.3) confirmed: permanent = `oslo_omegn`, trainee/graduate/summer = `norge`.
- [x] Company list in spike 03 approved as is.
- [x] Open questions in `docs/FRONTEND.md` resolved (preliminary choices accepted, now in §2).
- [x] Cloudflare DNS and NPM proxy host done.
- [x] `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN` in the Pi's `jobsearcher.env` (done, confirmed 2026-10-10).
- (No longer needed: Finn saved searches, Gmail label `JobSearcher/Finn`, sample `.eml` fixture. The user can delete them.)

## Next task
1. **First:** confirm NAV works once its gateway recovers (`uv run jobsearcher run --source nav --no-score`). First run asks 7 days back; expect several runs to catch up. Watch how many NAV ads pass the title rule and get detail-fetched; tune `search.title_require_any` from `GET /api/logs/discarded`.
2. Let the user use the real dashboard for a few days (`uv run jobsearcher serve` + `npm run dev`, or `npm run build` and just `serve`). Collect feedback on scores and the hard filter.
3. Then F3 below, then backend phase 3.

Known small things: the API's `is_new` groups `scrape_runs` within 1 h as one run (no run id column; add one if it misbehaves). `agents.filter.rescore()` has no UI/CLI yet (F4). Phase-3 context slices are not written.

### Frontend wave F3 (søknadseditor), see FRONTEND §5.5
Editor with Markdown preview, autosave 2 s → new version (`author=user`), version picker with diff, revision chat against a mock agent (background task → new version with `change_summary`), `claims_to_verify` as checkable warnings, copy and `.docx` download. Mock: `POST /api/jobs/{id}/draft`, `POST /api/applications/{id}/drafts`, `POST /api/applications/{id}/revise`, `GET /api/drafts/{id}/docx`; "Lag søknadsutkast" in the job detail and `/soknader` list page. Creating a draft should move the application to `utkast` (ARCHITECTURE §9.1).

The F1 user test (triage a mock day in < 2 min on mobile) has not been reported; the user gave F1 feedback and asked to start F2. Known small things: the main JS chunk is > 500 kB (code-split in F5); the PC filter row on Jobber wraps to three lines.

### Later: backend phase 3 (søknader)
Research, writer and reviser agents, the phase-3 context slices + `context/projects.py`, drafts API, `.docx` export. Connects F3.

## Open questions and risks (details in ARCHITECTURE §19)
1. **Finn mobile API is a ToS grey area.** Deliberate, informed decision; low-volume, private use. See spike 04.
2. The Finn signature or endpoints may break at any time (key rotation, format changes, detection). Pin app version (`261006-ec709768`) in User-Agent; fall back to `manual` paste if it dies. HMAC-nøkkelen må oppdateres fra en ny APK hvis Finn roterer den.
3. NAV's feed gateway is slow and was failing on 2026-10-10. Requests use a 90 s timeout and no quick retries; a failed run leaves the cursor and tries next day.
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
- 2026-10-10: User merged F0 to main (PR #4) and deleted the Finn APK (no longer needed; re-download if the key rotates). Removed APK location references from AGENTS, ARCHITECTURE §18 and spike 04 (update note).
- 2026-10-10: Built frontend wave F1 against mocks: Oversikt, Jobber (tabs, URL filters, swipe + keyboard triage with undo, master-detail), Jobbdetalj with mobile action bar, task indicator and "Kjør nå", mock mutations. `role` query param typed. FRONTEND v0.5.
- 2026-10-10: F1 feedback from the user: triage in the job detail now moves straight to the next job (not back to the list), and the undo toast/task indicator sit above the mobile action bar. E2E covers both.
- 2026-10-10: Built frontend wave F2 (tracker) against mocks: kanban with drag and drop + status menu (PC), grouped list + action sheet (mobile), panel with next step/follow-up/notes/event log, undo. Contract: `allowed_next`/`previous_status` on the card. ARCHITECTURE v0.10 (§9.1 transition table: + Interessant → Søkt, Tilbud → Trukket, Ikke aktuell → Interessant), FRONTEND v0.6.
- 2026-10-10: User feedback: untriaged status `ny` is now labelled "Ikke vurdert" in the UI (was "Ny", which clashed with the NY tag for new since last run). API value unchanged. The pre-marked Interessant jobs the user saw are mock fixtures. Then: untriaged jobs get an "Ikke vurdert" pill, and the new-since-last tag ("Ny") uses the same pill style as the rest.
- 2026-10-10: Started backend phases 1+2 (user chose real data before F3/F4). Built the foundation; roadmap reordered (ARCHITECTURE v0.11 §17); `claude setup-token` confirmed done.
- 2026-10-10: Built backend phases 1+2 with 5 parallel subagents (Finn, NAV, pipeline, LLM/agents, API) + foundation/integration. Pulled tracker API and scheduler forward. Live Finn run scored 63 jobs for $0.06; NAV untested live (gateway 500/504), made gentler (7-day first window, no quick retries, title pre-filter). ARCHITECTURE v0.11, FRONTEND v0.7.
