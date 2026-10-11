# JobSearcher

Et AI-basert verktøy som automatiserer jobbsøkingen: det henter stillinger, rangerer dem mot profilen din, skriver utkast til søknadsbrev og holder oversikt over hva du har søkt på.

> **Status:** Under utvikling. Innhenting fra Finn (NAV er bygget, men venter på at NAV-feeden svarer), filtrering, AI-scoring, hele dashboardet (oversikt, jobber, tracker, søknadsutkast, profil, innstillinger og logg) og e-postdigesten virker mot ekte data. Drift på hjemmeserveren gjenstår. Arkitekturen står i [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), UI-et i [docs/FRONTEND.md](docs/FRONTEND.md).

## Hva det gjør

- **Samler inn stillinger daglig** fra Finn.no (via Finns mobil-API, HMAC-signert), NAVs stillingsfeed og kilder for trainee-, graduate- og sommerjobber.
- **Filtrerer og rangerer** hver stilling mot profilen din. Først gratis regelbaserte filtre (geografi, rolle, senioritet), deretter en billig AI-modell som gir en score fra 0–100 med begrunnelse.
- **Viser alt i et dashboard for PC og mobil** med filtre for jobbtype, score, kilde og geografi.
- **Skriver søknadsutkast** ut fra din profil, stillingsannonsen og research om bedriften. Utkastet kan redigeres manuelt eller forbedres i en chat med en AI-agent, med versjonshistorikk.
- **Holder oversikt over søknader** med status (Interessant → Utkast → Søkt → Intervju → Tilbud/Avslag), frister og påminnelser om oppfølging.
- **Sender e-postvarsel** når nye, relevante stillinger dukker opp.

Alt er konfigurerbart: roller, geografi (Nittedal / Oslo og omegn / hele landet), jobbtyper (trainee, graduate, sommerjobb, fast) og hvilke AI-modeller som brukes.

## Hvordan det fungerer

```
Finn / NAV / trainee-kilder
        │
        ▼
  Henting → normalisering → duplikatfjerning → regelfilter → AI-scoring
        │
        ▼
     SQLite  ◄──►  Dashboard (React + FastAPI, PC og mobil)
                        │
                        ▼
          Research-agent → skrive-agent → revisjonsagent
```

Kjernen er et **kontekstsystem** som gir hver AI-agent nøyaktig den informasjonen den trenger, og ikke mer:

- Profilen din ligger i strukturerte filer (CV, prosjekter, erfaring, skriveeksempler, motivasjon).
- Den destilleres automatisk til en kort og en lang versjon, pluss en beskrivelse av skrivestilen din.
- Hver agent har et manifest som sier hvilke kontekstbiter den får og hvor stort token-budsjettet er.
- Agentene lever bare for én oppgave. All tilstand ligger i databasen, så konteksten vokser aldri ukontrollert.

Se [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detaljer.

## Teknologi

Python · FastAPI · React (Vite + TypeScript) · SQLite · DeepSeek via OpenRouter (Claude Code-abonnementet som valg) · Docker · Tailscale · Gmail SMTP

## Prosjektstruktur

```
docs/            Arkitektur og designbeslutninger
context/
  profile/       Din personlige profil (ikke i git, bare malene versjoneres)
  derived/       Automatisk destillert kontekst (ikke i git)
  prompts/       Systemprompter for hver agent
config/          Innstillinger, agentmanifest, geografi og kilder
src/jobsearcher/ Backend: kilder, pipeline, LLM-agenter, FastAPI-API, planlegger
web/             Dashboard (React + Vite + TypeScript)
scripts/         Hjelpeskript, f.eks. eksport av API-kontrakten
```

## Kom i gang

Krever [uv](https://docs.astral.sh/uv/) og Node 22.

```bash
uv sync
cd web && npm install
```

**Fyll inn `.env`** (kopier `.env.example`). `NAV_FEED_TOKEN` trengs for NAV-kilden. `OPENROUTER_API_KEY` trengs for AI-scoring og søknadsutkast (DeepSeek via OpenRouter, forhåndsbetalt kreditt). `OPENROUTER_MANAGEMENT_KEY` (valgfri) viser kontosaldoen i forbrukskortet. `llm.backend: claude_code` i `config/settings.yaml` bruker heller `claude`-CLI-en på Claude-abonnementet (logg inn med `claude` først).

**Kjør med ekte data:**

```bash
uv run jobsearcher serve
```

```bash
cd web && npm run dev
```

Åpne http://localhost:5173. `serve` starter API-et på port 8765 og kjører innhentingen hver dag mellom kl. 07:00 og 07:40 (tilfeldig starttid, og tar igjen en tapt kjøring ved oppstart). "Kjør nå" i dashboardet starter en kjøring med en gang. `serve` serverer også dashboardet selv på http://127.0.0.1:8765, og bygger det på nytt ved oppstart hvis frontenden er endret siden forrige build (slå av med `--no-build`). Etter en frontend-endring holder det å starte `serve` på nytt.

Andre kommandoer:

```bash
uv run jobsearcher run
```

Én kjøring fra terminalen (`--no-score` hopper over AI-scoringen, `--source finn_api` begrenser til én kilde). Finn hoppes over hvis den ble hentet for under 3 timer siden, også fra "Kjør nå"; `--force` overstyrer pausen og kjører de ukentlige Finn-søkene med en gang. Bruk det sjelden. Selskapene for trainee-, graduate- og sommerjobber står i `config/sources.yaml`: Teamtailor-feeder (`teamtailor.feeds`) og karrieresider uten feed (`page_watch.companies`). Karrieresidene sjekkes maks én gang per 20 timer, og AI leser en side bare når den har endret seg. `uv run jobsearcher distill` destillerer profilen på nytt. `uv run jobsearcher rescore` scorer jobber på nytt etter endret profil eller prompt; `--all` tar alle scorede jobber, f.eks. etter bytte av modell. `uv run jobsearcher digest` skriver en forhåndsvisning av e-postdigesten til `data/exports/digest-preview.html`; `--send` sender den til `GMAIL_ADDRESS` med en gang (ellers sendes den automatisk etter den planlagte kjøringen kl. 07). Data, logger og backuper ligger i `data/`.

**Prøv dashboardet med oppdiktede data** (ingen backend nødvendig):

```bash
cd web && npm run dev:mock
```

Åpne http://localhost:5173. For å prøve på mobilen: `npm run dev:mock -- --host` og åpne `http://<PC-ens Tailscale-IP>:5173`.

**Når API-kontrakten endres** (`src/jobsearcher/api/schemas.py`):

```bash
uv run python scripts/export_openapi.py
cd web && npm run gen:api
```

**Tester:** `uv run pytest` (backend), og i `web/`: `npm test`, `npm run typecheck`, `npm run e2e`.

**Drift på hjemmeserveren** (Raspberry Pi, ARCHITECTURE §12). Appen kjører som tjenesten `jobsearcher` i Pi-ens `infra`-stack og nås på https://jobb.mariuskristensen.no over Tailscale. Etter en endring, fra PC-en:

```bash
bash scripts/deploy_pi.sh
```

Fra PowerShell peker `bash` på WSL, så bruk Git Bash direkte:

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/deploy_pi.sh
```

Skriptet sender koden til Pi-en (`ssh pi`), bygger imaget der og starter containeren på nytt. Hemmelighetene ligger i `~/infra/config/jobsearcher/jobsearcher.env` på Pi-en, og data og profil i `~/infra/config/jobsearcher/data/`. Når appen kjører på Pi-en, er PC-ens `data/` og `context/profile/` bare en utviklingskopi.

Profilen fyller du ut slik:

1. Les [context/README.md](context/README.md).
2. Kopier malene (`_template.md`) i `context/profile/projects/`, `experience/` og `writing_samples/`, og fyll dem ut.
3. Opprett `profile.yaml`, `cv.md`, `motivation.md` og `style_overrides.md` i `context/profile/` (se beskrivelsen i context/README.md).

Profilen inneholder persondata og er derfor ekskludert fra git.

## Merknad om Finn.no

Finn har ikke et offisielt tredjeparts-API. JobSearcher snakker med det samme mobil-API-et som Finns Android-app bruker: forespørsler signeres med en HMAC-nøkkel fra appen, og endepunktene er reverse-engineeret fra appens APK. Bruken er privat, lokal og lavvolum. Det er likevel en bevisst gråsone opp mot Finns ToS, og vurderingen står i [docs/spikes/04-finn-mobile-api.md](docs/spikes/04-finn-mobile-api.md).
