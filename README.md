# JobSearcher

Et AI-basert verktøy som automatiserer jobbsøkingen: det henter stillinger, rangerer dem mot profilen din, skriver utkast til søknadsbrev og holder oversikt over hva du har søkt på.

> **Status:** Under utvikling. Innhenting fra Finn (NAV er bygget, men venter på at NAV-feeden svarer), filtrering, AI-scoring, dashboardets daglige visning og søknadstrackeren virker mot ekte data. Søknadsutkast (editor + skrive-agent), profilredigering i dashboardet og e-postdigest gjenstår. Arkitekturen står i [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), UI-et i [docs/FRONTEND.md](docs/FRONTEND.md).

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

Python · FastAPI · React (Vite + TypeScript) · SQLite · Claude (via Claude Code-abonnement eller Anthropic API) · Docker · Tailscale · Gmail SMTP

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

**Fyll inn `.env`** (kopier `.env.example`). `NAV_FEED_TOKEN` trengs for NAV-kilden. Claude brukes via `claude`-CLI-en på abonnementet ditt (logg inn med `claude` først); alternativt `ANTHROPIC_API_KEY` og `llm.backend: anthropic_api` i `config/settings.yaml`.

**Kjør med ekte data:**

```bash
uv run jobsearcher serve
```

```bash
cd web && npm run dev
```

Åpne http://localhost:5173. `serve` starter API-et på port 8765 og kjører innhentingen hver dag kl. 07:00 (og tar igjen en tapt kjøring ved oppstart). "Kjør nå" i dashboardet starter en kjøring med en gang. Etter `npm run build` i `web/` serverer `serve` også dashboardet selv på http://127.0.0.1:8765.

Andre kommandoer:

```bash
uv run jobsearcher run
```

Én kjøring fra terminalen (`--no-score` hopper over AI-scoringen, `--source finn_api` begrenser til én kilde). `uv run jobsearcher distill` destillerer profilen på nytt. Data, logger og backuper ligger i `data/`.

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

Profilen fyller du ut slik:

1. Les [context/README.md](context/README.md).
2. Kopier malene (`_template.md`) i `context/profile/projects/`, `experience/` og `writing_samples/`, og fyll dem ut.
3. Opprett `profile.yaml`, `cv.md`, `motivation.md` og `style_overrides.md` i `context/profile/` (se beskrivelsen i context/README.md).

Profilen inneholder persondata og er derfor ekskludert fra git.

## Merknad om Finn.no

Finn har ikke et offisielt tredjeparts-API. JobSearcher snakker med det samme mobil-API-et som Finns Android-app bruker: forespørsler signeres med en HMAC-nøkkel fra appen, og endepunktene er reverse-engineeret fra appens APK. Bruken er privat, lokal og lavvolum. Det er likevel en bevisst gråsone opp mot Finns ToS, og vurderingen står i [docs/spikes/04-finn-mobile-api.md](docs/spikes/04-finn-mobile-api.md).
