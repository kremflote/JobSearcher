# Handover

> Keep this file short. Update it at the end of every session: status, next task, open questions, and one line in the log.

**Last updated:** 2026-10-11
**Phase:** 0, 0b, F0–F2, backend phases 1 + 2, the Finn politeness pass, wave 2b/F2b, the switch to DeepSeek as the only model and **F3 (søknadseditor, mock)** done. Open PRs: #9 (cost-cap commit, `feat/backend-phase1-2`) and the DeepSeek switch (`feat/deepseek-primary`); F3 is on `feat/frontend-f3`, branched from `feat/deepseek-primary`, uncommitted. The user merges. Roadmap (ARCHITECTURE §17): … → F3 → **phase 3 next** → F4 → 4 (ARCHITECTURE v0.18, FRONTEND v0.12).

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

- **Finn politeness pass done** (2026-10-10), see ARCHITECTURE v0.12 §4.2 points 6 + 8, spike 04 §Oppdatering "hensyn til Finn":
  - Ad pages go out as the app's WebView (was `python-httpx`), 5–10 s apart, max 40 per run; 403/429 stops the batch; 404/410 makes the job inactive; retries after 1, 3, 7 days (`job_sources.detail_attempts`/`detail_next_at`, Alembic `0002`).
  - Gateway calls 2–4 s apart; 429 stops all searches. `it_oslo` removed; trainee/graduate/summer run weekly (`every_days`). Filter metadata cached 7 days (`data/finn_filters.json`). Finn is skipped if fetched < 3 h ago (`jobsearcher run --force` overrides). Scheduled run starts 0–40 min after 07:00 (`schedule.jitter_minutes`). App headers gained `x-nmp-os-version`, `x-nmp-device`, `Ab-Test-Device-Id`.
  - Tests: `uv run pytest` 189 (new `tests/test_http.py`). Not run live yet; the real DB migrates to `0002` on the next `serve`/`run`.

- **Wave 2b/F2b done** (2026-10-11), see ARCHITECTURE v0.14 §8.1, FRONTEND v0.9 §5.1, spike 05 §Oppdatering:
  - Backend: `llm/openrouter.py` (DeepSeek V4.1 Flash, json_schema, `require_parameters` + `data_collection: deny`, cost from `usage.cost`, balance via `/credits` or `/key`, cached 10 min). `FallbackBackend` in `llm/base.py`: only `LLMBackendError` switches; 30 min breaker. `agent_runs.fallback_from` (Alembic `0003`). `GET /api/llm/usage`. `anthropic_api` + `anthropic` dependency removed. New keys `llm.fallback`, `llm.openrouter.models.*`, `llm.openrouter.timeout_s`.
  - Frontend: LLM-forbruk card (replaces Kostnad) + detail sheet/panel, six mock states via `?mock_llm=`.
  - Live: with a broken `claude` path, a filter batch completed via OpenRouter and logged both rows; `/api/llm/usage` on a DB copy showed the account balance ($9.98 of $10).
  - DeepSeek vs Haiku on all 63 jobs: same ranking (Spearman 0.84 vs Haiku-with-itself 0.88) but **~20 points higher** scores; 16 jobs would cross the digest threshold 70. Usable as fallback, not as a scorer on the same scale. Cost $0.05 for 63 jobs.
  - User feedback: the cost cap now counts paid calls only ($10/mnd, was $25 including Claude's estimate); at the cap the fallback stops but `claude_code` keeps scoring. The card labels the cap and shows OpenRouter's own total (`used_usd`), which includes calls outside the app (e.g. the comparison above ran on DB copies, so it is in OpenRouter's total but not in the app's per-backend numbers).
  - Tests: pytest 232, Vitest 76, Playwright 23 (+7 skipped), typecheck and build OK.
- **DeepSeek is the only model** (2026-10-11), see ARCHITECTURE v0.16 §2/§8, spike 05 last update:
  - `llm.backend: openrouter`, `llm.fallback: none` (code default for `fallback` is now None). Reason: scores and later cover letters should come from one model. `claude_code` stays available via config.
  - Filter prompt v0.3: stricter scale calibrated to the Haiku scale (mean −1.7 vs Haiku), caps for student-only jobs, start before graduation / part-time while studying (user starts working summer 2027) and analysis/BI roles.
  - New CLI `jobsearcher rescore [--all]`. Ran `--all` live: 63/63 jobs rescored with DeepSeek ($0.07); none left on Haiku. Backup `data/backups/pre-deepseek-2026-10-11.db`.
  - Usage card copy: "OpenRouter ikke satt opp", low balance stops AI scoring.
  - Tests: pytest 235, Vitest 76, LLM e2e 6, typecheck OK.
- **Frontend F3 (søknadseditor) done against mock** (2026-10-11), see FRONTEND v0.11 §5.5/§7, ARCHITECTURE v0.17 §9.1:
  - `features/drafts/`: `/soknader` (drafts, last edited first + "Interessant, uten utkast" with "Lag søknadsutkast"), editor at `/soknader/:id`: Markdown field with preview and word count, autosave 2 s (`useDraftEditor`), revision chat built from the version list, version menu (PC) / Versjoner tab (mobile) with word diff (`diff.ts`, own LCS) against previous or current and "Gjenopprett", claims as tickable warnings (localStorage), Kopier (plain text), `.docx`, "Merk som søkt". Mobile: Utkast | Chat | Versjoner (`?vis=`), `?versjon=<id>` opens a diff.
  - "Lag søknadsutkast" in the job detail is live (task → toast with "Åpne"); the tracker panel links to the draft.
  - Contract: `ApplicationCard.latest_draft_id/latest_draft_at` (backend fills them already, test added), `DraftCreate.base_draft_id`, `ReviseRequest.draft_id`. Autosave updates a user version < 10 min old in place. Draft routes stay 501 in the backend until phase 3.
  - Mock: generic task specs in `handlers.ts` (run/draft/revise), `mocks/drafts.ts` (writer 5 s, reviser 3 s), `mocks/docx.ts` writes a real stored-zip `.docx`.
  - Tests: pytest 236, Vitest 86, Playwright 32 (+8 skipped), typecheck and build OK.
  - After the user's first try (a question about a claim was pasted into the letter by the mock reviser): the chat now separates questions from edits. New table `draft_messages` (model + Alembic `0004`, route `GET /api/applications/{id}/messages` still 501), `RevisionResult.kind/reply` in ARCHITECTURE §7.2, prompt `reviser` v0.2. The mock answers questions without a new version. Tests now: pytest 237, Vitest 89, Playwright 34 (+8 skipped).
- Live Finn check 2026-10-11 after the politeness pass: only `it_norge` ran (weekly searches not due), one gateway call, 0 new ads since the cursor, so ad-page spacing is still unobserved live.

### Waiting on the user
- [ ] (Postponed by the user 2026-10-11) NAV private token → `NAV_FEED_TOKEN` in `.env` (email in ARCHITECTURE §18). `.env` currently has NAV's **public** dev token, which rotates. NAV has not completed a live run yet: its gateway returned 500/504 on 2026-10-10 (spike 01 §Oppdatering). The daily run retries; check `GET /api/logs/runs` or Oversikt › Kildestatus.
- [x] Wave 2b setup: OpenRouter account with $10 credit; `OPENROUTER_API_KEY` (limit $10) and `OPENROUTER_MANAGEMENT_KEY` in `.env`, both verified live 2026-10-11. Still to do at phase 4b: copy them to the Pi's `jobsearcher.env`.
- [ ] Merge PR #9 and the DeepSeek PR, then `git checkout main && git pull` and restart `serve` so it runs with `llm.backend: openrouter` (the 07:00 run otherwise uses the code the process started with). Run `uv sync` once if `anthropic` is still installed.
- [ ] Keep OpenRouter credit topped up: it now pays for all scoring (~$0.001/job). The card warns under $1.
- [ ] NAV now answers **401** (the public dev token expired, run 2026-10-11 07:00), so the private `NAV_FEED_TOKEN` is required.
- [x] Geography per job type (ARCHITECTURE §5.3) confirmed: permanent = `oslo_omegn`, trainee/graduate/summer = `norge`.
- [x] Company list in spike 03 approved as is.
- [x] Open questions in `docs/FRONTEND.md` resolved (preliminary choices accepted, now in §2).
- [x] Cloudflare DNS and NPM proxy host done.
- [x] `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN` in the Pi's `jobsearcher.env` (done, confirmed 2026-10-10).
- (No longer needed: Finn saved searches, Gmail label `JobSearcher/Finn`, sample `.eml` fixture. The user can delete them.)

## Next task
1. **User test of F3** in mock mode (`npm run dev:mock -- --host`): write a letter end to end on PC and phone. Then **backend phase 3** below (writer/reviser on DeepSeek too, tiers `balanced`/`best` all map to it). The UI is ready; phase 3 only has to fill the 501 routes per FRONTEND §7 (incl. the 10-min in-place rule and `draft_exists`/`no_draft`).
2. Collect the user's feedback on the new DeepSeek scores while they triage; check `notify_min_score: 70` against triage before the digest (phase 4). The first Finn run with new ads should show ad pages ~5–10 s apart in the log.
3. NAV: postponed until the user has the private token. Then `uv run jobsearcher run --source nav --no-score` and tune `search.title_require_any` from `GET /api/logs/discarded`.

Known small things: the API's `is_new` groups `scrape_runs` within 1 h as one run (no run id column; add one if it misbehaves). `agents.filter.rescore()` has no UI/CLI yet (F4). Phase-3 context slices are not written. `llm.fallback` is read from `settings.yaml` only (dashboard overrides don't apply). `by_backend.calls` for `claude_code` counts failed attempts too.

The F1 user test (triage a mock day in < 2 min on mobile) has not been reported; the user gave F1 feedback and asked to start F2. Known small things: the main JS chunk is > 500 kB (code-split in F5); the PC filter row on Jobber wraps to three lines.

### Next: backend phase 3 (søknader)
Research, writer and reviser agents, the phase-3 context slices + `context/projects.py`, drafts and chat API (`web/routes/drafts.py` incl. `messages`, `POST /api/jobs/{id}/draft` in `routes/jobs.py`; writer and reviser write `draft_messages`, reviser returns `kind: answer|revision`), `.docx` export with python-docx (`Content-Disposition` filename). Connects F3; the mock in `web/src/mocks/drafts.ts` shows the expected behaviour. Known F3 gaps: the editor only locks the text during a revision it started itself (after a reload mid-revision it is editable); the main JS chunk is still > 500 kB.

## Open questions and risks (details in ARCHITECTURE §19)
1. **Finn mobile API is a ToS grey area.** Deliberate, informed decision; low-volume, private use. See spike 04.
2. The Finn signature or endpoints may break at any time (key rotation, format changes, detection). Pin app version (`261006-ec709768`) in User-Agent; fall back to `manual` paste if it dies. HMAC-nøkkelen må oppdateres fra en ny APK hvis Finn roterer den.
7. Parts of the Finn identity are guesses (app User-Agent format, WebView Chrome version, device build) and the app version ages. Next APK decompile: read `HttpUserAgent` and bump `app_version`/`webview_chrome_version` together (ARCHITECTURE §19 #12).
3. NAV's feed gateway is slow and was failing on 2026-10-10. Requests use a 90 s timeout and no quick retries; a failed run leaves the cursor and tries next day.
4. ~~Anthropic subscription billing for `claude -p`~~: no longer the default backend.
5. `claude -p` inside a Docker container on the Pi (arm64, `CLAUDE_CODE_OAUTH_TOKEN`) is unverified. Check at phase 4b.
8. DeepSeek/OpenRouter (now the only model) sends ad text and the distilled profile to third-party providers (`data_collection: deny`) and needs prepaid credit. Prompt v0.3 is calibrated to the old Haiku scale (spike 05; ARCHITECTURE §19 #13).
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
- 2026-10-10: Reviewed how JobSearcher treats Finn and implemented every improvement: WebView headers for ad pages, jittered spacing, per-run cap, back off on 403/429, gone ads inactive, spaced retries (migration `0002`), 3 h cooldown + `run --force`, weekly type searches, `it_oslo` dropped, cached filter check, scheduler start jitter, fuller app headers. ARCHITECTURE v0.12, spike 04 update, README.
- 2026-10-11: LLM decision baked into docs: `claude_code` stays default, DeepSeek V4.1 Flash via OpenRouter replaces `anthropic_api` as automatic fallback. New wave 2b/F2b before F3, with a usage card (tokens, cost, OpenRouter balance) and `GET /api/llm/usage`. ARCHITECTURE v0.13, FRONTEND v0.8, spike 05, AGENTS. No code yet. Found the 07:00 run failed because `serve` predates migration `0002` (not restarted, per the user). User added both OpenRouter keys; verified live, `.env.example` updated.
- 2026-10-10: Jobber on PC: the filters under the search field now fold out with a "Filtre" toggle (active-filter count badge, open state in localStorage). Mobile sheet unchanged. FRONTEND §Jobber filters line.
- 2026-10-11: Committed the Finn politeness pass; live Finn check OK (only `it_norge`, 0 new). Built wave 2b/F2b with two parallel subagents (backend, frontend) against a contract written first: OpenRouter backend, fallback with breaker, `fallback_from` (0003), `/api/llm/usage`, LLM-forbruk card; `anthropic_api` removed. Verified fallback live and compared DeepSeek with Haiku on 63 jobs (same order, +20 points). ARCHITECTURE v0.14, FRONTEND v0.9, spike 05 update, README. Opened PR to `main`.
- 2026-10-11: User feedback on the usage card: cost cap now counts paid calls only and defaults to $10 (ARCHITECTURE v0.15 §8.3), card labels the cap and shows OpenRouter's total spend (`used_usd`, FRONTEND v0.10). Added a `web-mock` preview config.
- 2026-10-11: Opened PR #9 for the unmerged cost-cap commit (auto-merge needs the user). Switched to DeepSeek via OpenRouter as the only model (no fallback), filter prompt v0.3 calibrated against Haiku over three runs (spike 05), added `jobsearcher rescore [--all]`, rescored all 63 live jobs. User postponed NAV. ARCHITECTURE v0.16, spike 05 update, README, AGENTS.
- 2026-10-11: Built frontend wave F3 (søknadseditor) against mock on `feat/frontend-f3`: `/soknader`, editor with autosave, revision chat, versions with word diff/restore, claims, copy, `.docx`, "Merk som søkt"; "Lag søknadsutkast" live in the job detail. Contract: latest draft on tracker cards (backend filled), `base_draft_id`/`draft_id`, in-place autosave < 10 min. FRONTEND v0.11, ARCHITECTURE v0.17.
- 2026-10-11: User tried F3 in mock mode and asked the chat a question, which the mock pasted into the letter (the letter text is a template, not DeepSeek). Chat now separates questions from edits: `draft_messages` table (`0004`), `GET /api/applications/{id}/messages`, `RevisionResult.kind`, reviser prompt v0.2, mock answers questions. ARCHITECTURE v0.18, FRONTEND v0.12.
