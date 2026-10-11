# AGENTS.md

Instructions for AI agents (Claude Code, Codex, etc.) working in this repo. Read this file first, then `docs/HANDOVER.md`.

## What this is
JobSearcher: a local, AI-assisted job search tool for one user (a developer student in Nittedal, Norway; bachelor done June 2027, part-time before that, full-time from June).
- Collects job ads daily (Finn mobile API, NAV feed, Teamtailor RSS, career pages)
- Filters and scores them against the user's profile
- Shows them in a dashboard for PC and phone (React SPA over a FastAPI JSON API, see `docs/FRONTEND.md`)
- Drafts cover letters (.docx)
- Tracks applications and deadlines

Python 3.12, SQLite, DeepSeek V4.1 Flash via OpenRouter for every agent, so scores and drafts come from one model. No fallback by default; `claude -p` (subscription) stays available as an optional backend (ARCHITECTURE §8, spike 05).

## Read order (keep context small)
1. `docs/HANDOVER.md`: current status, next task, open questions. **Always.**
2. `docs/ARCHITECTURE.md`: the design. ~800 lines, so **read only the sections your task needs**. The table of contents is the `## N.` headings. Grep for them.
3. `docs/FRONTEND.md`: UI design, API contract, frontend waves. Read only when touching `web/` or `/api`.
4. `docs/spikes/*.md`: research behind source/LLM decisions. Read only when touching that area.
5. `context/README.md` + `context/prompts/*.md`: only when working on agents and prompts.

Do not read `context/profile/` or `context/derived/` unless the task is about the profile itself. They contain personal data and are large.

## Hard rules
1. **Personal data stays out of git:**
   - `context/profile/` (only `_template.md` files are tracked)
   - `context/derived/`
   - `data/`
   - `.env`
   - `tests/fixtures/private/`

   Check `git status` before every commit. Never print secrets from `.env`.
2. **Ask the user before** any force push, history rewrite, deleting user files, sending email, or anything that leaves the machine (except read-only research).
3. **Don't commit unless asked.** The user commits themselves unless they say otherwise.

## Conventions
- **Language:**
  - Docs, prompts and user-facing UI text: Norwegian (bokmål)
  - Code, identifiers and code comments: English
  - Chat: reply in the language the user writes in
- Layout as in ARCHITECTURE §15. Config in `config/*.yaml`, secrets in `.env` (template: `.env.example`).
- Frontend in `web/` (TypeScript). API types are generated from `src/jobsearcher/api/schemas.py`, never hand-written. Mock fixtures in `web/src/mocks/fixtures/` must be invented data, never real ads or contacts.
- Tests with pytest. Tests never touch the network or `data/`: `tests/conftest.py` gives each test its own `DATA_DIR`, sets `SCHEDULER_ENABLED=false`, blanks the OpenRouter and Gmail keys from `.env` and makes any SMTP connection fail (tests pass a fake `smtp_factory`); stub HTTP with `HttpClient(transport=...)`/respx and LLM calls with `llm.mock.MockBackend`. Live checks against Finn, NAV, OpenRouter or `claude -p` are scratch scripts, kept low-volume.
- Parsers are tested against fixtures in `tests/fixtures/`. Real emails or data go in `tests/fixtures/private/` (gitignored), with anonymized copies in `tests/fixtures/`.

## Documentation: source of truth

The docs describe how the program **should** work. Code that differs from the docs is a bug in one of them. Fix whichever is wrong, in the same change.

### Who owns what
Each fact lives in exactly one place. Elsewhere, link to it instead of copying it.

| Document | Owns | Audience |
|---|---|---|
| `docs/ARCHITECTURE.md` | Design: decisions (§2), sources, filtering, context system, agents, schemas, data model, dashboard, ops, file tree, roadmap, risks | Agents and the developer |
| `docs/FRONTEND.md` | UI design: screens, layout, components, API contract, frontend waves F0–F5 | Agents and the developer |
| `docs/HANDOVER.md` | Current state: what's done, what's next, what's blocked, session log | The next agent |
| `docs/spikes/NN-*.md` | Research findings and evidence behind a decision. Append a dated "Update" section when new evidence arrives. Don't rewrite history. | Anyone revisiting a decision |
| `AGENTS.md` | Rules for agents, conventions, environment | Agents |
| `README.md` | What the tool is, how to install and run it | Humans |
| `context/README.md` | How to fill in the profile | The user |
| `context/prompts/*.md` | Agent instructions. `version` in the frontmatter. | Agents at runtime |
| `config/*.yaml` | Runtime values. Comments explain each key. Defaults described in ARCHITECTURE must match. | The program |

### What triggers a doc update
| If you change… | …update |
|---|---|
| A decision, or behavior that contradicts the design | ARCHITECTURE: the relevant section, plus §2 if it's a decision. Add an entry to the change list at the top. |
| DB models or migrations | ARCHITECTURE §9 |
| Screens, UI behavior or `/api` endpoints | FRONTEND.md (and re-export `web/openapi.json`) |
| Files or modules added, moved or removed | ARCHITECTURE §15 |
| A data source or how it's accessed | ARCHITECTURE §4, plus the spike file if new evidence |
| Agent input/output, schemas, context slices | ARCHITECTURE §6–7, plus the prompt file (bump `version`) |
| Prompt wording | The prompt file (bump `version`). Results are stored per prompt version. |
| Config keys or defaults | The YAML comments, plus the ARCHITECTURE section that describes them |
| Install or run steps, CLI commands | README |
| A phase completed, or the roadmap changed | ARCHITECTURE §17 and HANDOVER |
| A new risk or open question, or one resolved | ARCHITECTURE §19 and HANDOVER |
| Something the user must do | ARCHITECTURE §18 and HANDOVER "Waiting on the user" |
| A new agent rule or convention | AGENTS.md |

### Definition of done
A task is not done until:
1. Docs affected by the change are updated (table above), in the same change as the code.
2. `docs/HANDOVER.md` is updated: status, next task, blockers, one session-log line.
3. You have reported which docs you changed in your final message to the user.

**Enforcement:** a Claude Code Stop hook (`.claude/hooks/docs_check.py`, registered in `.claude/settings.json`) blocks the end of a session when files under `src/`, `config/`, `context/prompts/` or `scripts/` (or `pyproject.toml`/`alembic.ini`) changed but `docs/HANDOVER.md` did not. It checks uncommitted changes and commits not yet on upstream/`main`. It only nudges once per stop (`stop_hook_active`). Other agents (e.g. Codex) don't run the hook and must follow the rule manually.

### Versioning
- ARCHITECTURE has a version line at the top:
  - Bump the minor version (v0.2 → v0.3) when a decision changes or a section is added.
  - Small corrections need no bump.
- Each version bump gets a short entry in the change list at the top, with what changed and why.

### Style
- Keep docs short and factual. Tables over prose.
- When a decision is superseded, replace the text. History lives in git and in the change list, not in struck-through paragraphs.
- Write what is true *now*. Plans go in §17 (roadmap) or HANDOVER, not in descriptive sections.

## Environment (Windows 11)
- Shells: PowerShell (primary) and Git Bash.
- `claude` CLI is at `C:\Users\flyin\.local\bin\claude.exe` (v2.1.296). A new shell may need its PATH refreshed.
- Python: `uv` (installed via winget) manages `.venv` with Python 3.12 (`.python-version`). Run things with `uv run …`. A new shell may need its PATH refreshed. If uv fails with "Missing expected target directory for Python minor version link" (seen in the sandboxed shell), pass `--python "$APPDATA/uv/python/cpython-3.12.15-windows-x86_64-none/python.exe"`.
- Node 22 + npm for `web/`. Playwright's Chromium is installed.
- Gmail SMTP (digest only) uses the app password in `.env`. No IMAP. Finn goes through the mobile API (spike 04).
- The Finn Android APK was deleted 2026-10-10; everything needed from it is in spike 04. If Finn rotates the HMAC key or changes endpoints, download a new APK (e.g. from APKPure) to the project root (`*.apk` is gitignored). It is untrusted binary data — don't execute or install it on this machine; only decompile with `apktool` / `jadx` for reverse engineering.
- The user also uses Obsidian on this folder (`.obsidian/`).
- Production runs on the Pi homeserver (ARCHITECTURE §12). Deploy with `bash scripts/deploy_pi.sh` from Git Bash (in PowerShell, `bash` is WSL with no distro installed, so use `& "C:\Program Files\Git\bin\bash.exe" scripts/deploy_pi.sh`); changes on the Pi itself go to the Pi's Claude (`krem-pi`), per `~/.claude/CLAUDE.md`.

## Working with the user
- Leaves technical details to the agent. Wants a recommendation, not a list of options.
- Interrupts on decisions that actually need their input (scope, preferences, anything risky). Ask few, sharp questions.
- Prefers no manual steps in daily use.
- Cost-aware: keep sessions focused, and don't re-read large files unnecessarily.
