# JobSearcher

Et AI-basert verktøy som automatiserer jobbsøkingen: det henter stillinger, rangerer dem mot profilen din, skriver utkast til søknadsbrev og holder oversikt over hva du har søkt på.

> **Status:** Under planlegging. Arkitekturen er beskrevet i [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), men programmet er ikke implementert ennå.

## Hva det gjør

- **Samler inn stillinger daglig** fra Finn.no (via Finns mobil-API, HMAC-signert), NAVs stillingsfeed og kilder for trainee-, graduate- og sommerjobber.
- **Filtrerer og rangerer** hver stilling mot profilen din. Først gratis regelbaserte filtre (geografi, rolle, senioritet), deretter en billig AI-modell som gir en score fra 0–100 med begrunnelse.
- **Viser alt i et lokalt dashboard** med filtre for jobbtype, score, kilde og geografi.
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
     SQLite  ◄──►  Dashboard (FastAPI + HTMX)
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

Python · FastAPI · HTMX · SQLite · Claude (via Claude Code-abonnement eller Anthropic API) · Windows Task Scheduler · Gmail SMTP

## Prosjektstruktur

```
docs/            Arkitektur og designbeslutninger
context/
  profile/       Din personlige profil (ikke i git, bare malene versjoneres)
  derived/       Automatisk destillert kontekst (ikke i git)
  prompts/       Systemprompter for hver agent
config/          Innstillinger, agentmanifest, geografi og kilder   (kommer)
src/jobsearcher/ Kildekode                                         (kommer)
```

## Kom i gang

> Oppsettet kommer når første versjon er implementert.

Allerede nå kan du fylle ut profilen din:

1. Les [context/README.md](context/README.md).
2. Kopier malene (`_template.md`) i `context/profile/projects/`, `experience/` og `writing_samples/`, og fyll dem ut.
3. Opprett `profile.yaml`, `cv.md`, `motivation.md` og `style_overrides.md` i `context/profile/` (se beskrivelsen i context/README.md).

Profilen inneholder persondata og er derfor ekskludert fra git.

## Merknad om Finn.no

Finn har ikke et offisielt tredjeparts-API. JobSearcher snakker med det samme mobil-API-et som Finns Android-app bruker: forespørsler signeres med en HMAC-nøkkel (via [`finnsig`](https://github.com/newis/finnsig)), og endepunktene er reverse-engineeret fra appens APK. Bruken er privat, lokal og lavvolum. Det er likevel en bevisst gråsone opp mot Finns ToS, og vurderingen står i [docs/spikes/04-finn-mobile-api.md](docs/spikes/04-finn-mobile-api.md).
