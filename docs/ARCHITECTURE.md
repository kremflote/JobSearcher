# JobSearcher – Design- og arkitekturdokument

> Status: utkast v0.1 (2026-10-09). Ingen kode skrevet ennå.
> Dokumentet er "source of truth" for designet. Oppdater det når beslutninger endres.

---

## 1. Mål

Et frittstående Python-program som kjører lokalt og automatiserer jobbsøkingen for en nyutdannet utvikler i Nittedal:

1. **Henter** relevante stillinger daglig fra Finn.no (hovedkilde), NAV/Arbeidsplassen og kilder for trainee-/graduate-stillinger.
2. **Filtrerer og rangerer** stillingene mot brukerens profil.
3. **Presenterer** resultatene i et lokalt web-dashboard.
4. **Skriver utkast til søknadsbrev** med kontekst om brukeren, stillingen og bedriften. Utkastet kan redigeres manuelt og itereres på med en agent.
5. **Holder oversikt** over søkte jobber og status.
6. **Varsler** på e-post når nye, relevante jobber dukker opp.

**Utenfor scope (foreløpig):** tilpasning av CV, automatisk innsending av søknader, LinkedIn-skraping.

### Designprinsipper

| Prinsipp | Konsekvens |
|---|---|
| **Tilstand ligger i databasen, ikke i agentene** | Agenter er kortlivde og tilstandsløse. De får en ferdig sammensatt kontekstpakke, gjør én jobb, skriver resultatet og avslutter. |
| **Orkestreringen er vanlig kode, ikke en LLM** | Pipelinen er deterministisk Python. LLM brukes bare der det trengs vurdering eller språk. Det er billigere og lettere å feilsøke. |
| **Kontekst er strukturert og budsjettert** | Hver agenttype har et manifest som sier nøyaktig hvilke kontekstbiter den får, og et token-budsjett for dem. |
| **Billig først, dyrt sist** | Deterministiske filtre → billig modell → dyr modell bare på det brukeren har valgt ut. |
| **Alt er konfigurerbart** | Roller, geografi, jobbtyper, modeller og terskler ligger i YAML, ikke i koden. |

---

## 2. Beslutninger så langt

| Tema | Beslutning |
|---|---|
| Språk | Python 3.12+ |
| Kjøremiljø | Lokalt på brukerens Windows-PC |
| Planlegging | Windows Task Scheduler (daglig), og "Kjør nå"-knapp i dashboardet |
| Dashboard | FastAPI + Jinja2-maler + HTMX (ingen JS-build) |
| Database | SQLite (via SQLModel/SQLAlchemy) |
| E-post | Gmail SMTP med app-passord, sendt til brukeren selv |
| LLM | Claude, bak et abstrakt backend-lag (abonnement via Claude Code CLI *eller* API-nøkkel, se §7) |
| Volum | 10–20 søknader per uke |
| Søknadsbrev | Ja: manuell redigering og agent-iterasjon |
| CV-tilpasning | Nei |

---

## 3. Systemoversikt

```
                 ┌───────────────────────────── Windows Task Scheduler (daglig 07:00)
                 │                         ┌─── "Kjør nå" i dashboardet
                 ▼                         ▼
        ┌──────────────────────────────────────────┐
        │           Pipeline-orkestrator (kode)    │   lock-fil hindrer samtidige kjøringer
        └──────────────────────────────────────────┘
          │ 1. hent     │ 2. normaliser  │ 3. hardfilter │ 4. LLM-score   │ 5. varsle
          ▼             ▼                ▼               ▼                ▼
   ┌────────────┐ ┌───────────┐  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │  Kilder    │ │ Normalize │  │ Regelbasert  │ │ Filter-agent │ │ E-post-      │
   │ Finn, NAV, │ │ + dedupe  │  │ filter (geo, │ │ (Haiku)      │ │ digest       │
   │ ATS, ...   │ │           │  │ rolle, type) │ │              │ │              │
   └────────────┘ └───────────┘  └──────────────┘ └──────────────┘ └──────────────┘
          │             │                │               │
          └─────────────┴────────────────┴───────────────┴──────►  SQLite  ◄──────┐
                                                                       ▲           │
        ┌──────────────────────────── Dashboard (FastAPI + HTMX) ──────┘           │
        │  Brukeren velger "Lag søknad" på en jobb                                  │
        ▼                                                                           │
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                          │
   │ Research-    │ ─► │ Skrive-agent │ ─► │ Revisjons-   │ ── nye utkastversjoner ──┘
   │ agent        │    │ (Opus)       │    │ agent (chat) │
   │ (Sonnet+web) │    │              │    │ (Sonnet/Opus)│
   └──────────────┘    └──────────────┘    └──────────────┘
         ▲                    ▲                   ▲
         └──────── Kontekstbygger: setter sammen kontekstpakker etter manifest ────────┘
                   (profil, annonse, bedriftsnotat, stil) innenfor token-budsjett
```

---

## 4. Datakilder

### 4.1 Kildegrensesnitt

Alle kilder implementerer samme grensesnitt, slik at nye kilder kan legges til uten å endre pipelinen:

```python
class JobSource(Protocol):
    name: str
    def search(self, query: SearchQuery) -> Iterable[RawJobRef]: ...   # lister treff (billig)
    def fetch(self, ref: RawJobRef) -> RawJob: ...                     # henter full annonse
```

`SearchQuery` bygges fra `config/settings.yaml` (roller, geografi-modus, jobbtyper). Hver kilde oversetter den til sitt eget format (URL-parametre, API-filtre).

Felles HTTP-lag (`sources/http.py`):
- Rate-limiting per domene (standard: 1 forespørsel per 2–3 sekunder for Finn)
- Disk-cache for annonsesider (en annonse hentes bare én gang med mindre den endres)
- Tydelig User-Agent, retry med backoff, respekt for `robots.txt`
- Lagrer rå HTML/JSON i `data/cache/` slik at parsing kan kjøres på nytt uten ny henting

### 4.2 Finn.no (prioritet 1)

Finn har ikke et åpent jobb-API (partner-API-et krever avtale). Tilnærming:

1. **HTTP + parsing av søkesider** (`finn.no/job/...search`): hent resultatlister med filtre for yrke, sted og ansettelsesform, og parse embedded JSON hvis siden har det, ellers HTML (selectolax).
2. **Annonsesider** hentes enkeltvis for full tekst, frist, kontaktinfo og ansettelsesform.
3. **Fallback: Playwright** (headless browser) bare hvis siden krever JavaScript-rendering.

> ⚠️ **Spike påkrevd (fase 0):** Den faktiske strukturen på Finn sine søkesider (URL-parametre, embedded data, paginering) må undersøkes før implementering. Parseren skrives mot lagrede fixtures, slik at endringer på Finn fanges opp av tester.
>
> ⚠️ **Vilkår:** Finn sine brukervilkår begrenser automatisert innhenting. Programmet er designet for personlig bruk med lavt volum: én kjøring per dag, rate-limiting, caching og ingen videredistribusjon. Brukeren har akseptert denne risikoen. Ikke øk frekvensen uten å vurdere dette på nytt.

### 4.3 NAV / Arbeidsplassen (prioritet 1)

NAV tilbyr en offentlig stillingsfeed (Arbeidsplassen, "pam-stilling-feed"). Den er offisiell og stabil, og mange Finn-annonser finnes der også. Brukes både som egen kilde og som "sikkerhetsnett" hvis Finn-parseren brekker.

> Spike: bekreft endepunkt, autentisering (offentlig token) og filtreringsmuligheter.

### 4.4 Trainee-, graduate- og sommerjobbkilder (prioritet 2)

Disse ligger ofte *ikke* på Finn. Strategi i tre lag:

| Lag | Eksempler | Implementering |
|---|---|---|
| **ATS-adaptere** | Teamtailor, Jobylon, Webcruiter, ReachMee, Greenhouse, Lever, Workday | Generisk adapter per ATS-type. Mange har JSON- eller RSS-endepunkter. Bedrifter konfigureres i `config/sources.yaml` med ATS-type og ID. |
| **Aggregatorer** | Jobbnorge (offentlig sektor), Karrierestart, Graduateland | Egne adaptere ved behov |
| **Karrieresider uten ATS** | Enkelte store selskaper | Valgfri "side-overvåker": hasher siden og varsler ved endring. Kjører LLM-uttrekk *bare* når innholdet har endret seg. |

`config/sources.yaml` holder en kuratert liste over relevante selskaper (bankene, Equinor, Telenor, Statnett, konsulenthusene, offentlige IT-miljøer og så videre). Brukeren kan legge til og fjerne.

### 4.5 Normalisering og deduplisering

- Alle kilder mappes til én `Job`-modell (se §8).
- **Fingerprint** = normalisert (bedrift + tittel + kommune). Fuzzy-match (rapidfuzz) fanger små variasjoner.
- Samme stilling fra flere kilder → én `Job` med flere `JobSource`-rader. Finn-lenken foretrekkes som primærlenke.
- Stillinger som forsvinner fra kilden, eller som har passert fristen, markeres `inactive` (slettes ikke).

---

## 5. Filtrering og rangering

### 5.1 Steg 1: Regelbasert hardfilter (gratis)

Konfigurert i `config/settings.yaml`:

- **Geografi-modus** (se 5.3)
- **Ekskluder-nøkkelord** i tittel/kategori (f.eks. `cybersecurity`, `sikkerhetsanalytiker`, `SOC`, `pentest`)
- **Senioritet**: forkast tydelige seniorroller (`senior`, `lead`, `principal`, `arkitekt`, `"5+ års erfaring"`). Konfigurerbart, siden noen "senior"-annonser er aktuelle likevel.
- **Jobbtyper**: bare typer som er slått på (trainee / graduate / sommerjobb / fast)
- Allerede vurderte stillinger (samme fingerprint og uendret tekst) hoppes over

### 5.2 Steg 2: Filter-agent (billig LLM)

Per stilling som passerer hardfilteret. Får kort profil + annonse, og returnerer strukturert JSON:

```json
{
  "score": 0-100,
  "role_category": "backend|frontend|fullstack|mobile|devops|other",
  "job_type": "trainee|graduate|summer|permanent|unknown",
  "seniority_fit": "good|stretch|too_senior",
  "match_reasons": ["..."],
  "concerns": ["..."],
  "deadline": "YYYY-MM-DD | null",
  "ad_language": "no|en"
}
```

Resultatet lagres i `evaluations` sammen med `prompt_version` og `profile_hash`. Hvis profilen eller prompten endres, kan alt rescores.

### 5.3 Geografi-moduser

Definert i `config/locations.yaml` som kommunelister:

| Modus | Innhold |
|---|---|
| `nittedal` | Nittedal + nabokommuner med kort pendlevei (Oslo nord/Grorud-området kan legges til) |
| `oslo_omegn` | Nittedal, Oslo, Lillestrøm, Lørenskog, Rælingen, Gjerdrum, Bærum, Asker, Nordre Follo m.fl. |
| `norge` | Ingen geografisk begrensning |

Remote/hybrid-stillinger med norsk arbeidsgiver tas med i alle moduser (konfigurerbart). Aktiv modus velges i dashboardet og lagres i innstillingene.

### 5.4 Jobbtyper

Fire separate typer, hver for seg kan slås av og på, og de vises som egne faner/filtre i dashboardet:
`trainee`, `graduate`, `summer`, `permanent`.

Typen settes av kilden når den er kjent (ansettelsesform på Finn, sommerjobb-kategori), ellers av filter-agenten.

---

## 6. Kontekstsystemet

Dette er kjernen i at agentene fungerer godt uten at konteksten vokser ukontrollert.

### 6.1 Tre lag med kontekst

```
context/
├── profile/      LAG 1: Kilde (skrevet av brukeren, versjonert i git)
├── derived/      LAG 2: Destillert (generert av profil-destilleren, cachet på hash)
└── prompts/      LAG 3: Instruksjoner (systemprompter per agent, versjonert)
```

**Lag 1: Kildekontekst** (brukeren eier og vedlikeholder denne)

| Fil | Innhold | Format |
|---|---|---|
| `profile.yaml` | Harde fakta: navn, utdanning, ferdigheter med nivå, språk, førerkort, oppstartsdato, lønnsforventning | YAML (maskinlesbart) |
| `cv.md` | Full CV i tekst | Markdown |
| `motivation.md` | Hva brukeren vil, hva som gir energi, typer team/bedrifter, dealbreakers | Markdown |
| `projects/*.md` | Ett prosjekt per fil. Frontmatter: `tech`, `role`, `link`, `highlight: true/false`. Brødtekst: hva, hvorfor, hva *jeg* gjorde og hva jeg lærte. | Markdown + frontmatter |
| `experience/*.md` | Én jobb/verv per fil, samme struktur | Markdown + frontmatter |
| `writing_samples/*.md` | Tidligere søknader og tekster brukeren har skrevet selv (helst noen som ga intervju) | Markdown |
| `style_overrides.md` | Eksplisitte stilregler ("aldri 'brenner for'", "maks 1 side", "du-form") | Markdown |

**Lag 2: Destillert kontekst** (generert, aldri redigert for hånd)

Profil-destilleren (en agent) kjører når en kildefil endres (hash-sjekk) og lager:

| Fil | Mål-størrelse | Brukes av |
|---|---|---|
| `profile_short.md` | ~500 tokens | Filter-agent |
| `profile_long.md` | ~3 000 tokens | Skrive- og revisjonsagent |
| `voice.md` | ~800 tokens | Skrive- og revisjonsagent: beskrivelse av brukerens skrivestil, med 2–3 korte, representative utdrag |
| `manifest.json` | n/a | Hash av kildene. Avgjør om destillatet er utdatert. |

**Bedriftskontekst:** `data/companies/<slug>.md` lages av research-agenten og caches (TTL 90 dager). Gjenbrukes på tvers av stillinger i samme bedrift.

### 6.2 Kontekstmanifest per agent

`config/agents.yaml` definerer hva hver agent får. Kontekstbyggeren følger manifestet slavisk, og ingen agent får "alt":

```yaml
filter:
  model_tier: fast            # → Haiku
  effort: low
  prompt: prompts/filter.md
  context:
    - { slice: profile_short,     priority: 1 }
    - { slice: job_ad,            priority: 1, max_tokens: 2500 }
    - { slice: search_prefs,      priority: 2 }
  input_budget_tokens: 4000
  output_schema: FilterResult

researcher:
  model_tier: balanced        # → Sonnet
  effort: medium
  tools: [web_search, web_fetch]
  prompt: prompts/researcher.md
  context:
    - { slice: company_name,      priority: 1 }
    - { slice: job_ad,            priority: 1, max_tokens: 2500 }
  input_budget_tokens: 4000
  output: data/companies/<slug>.md

writer:
  model_tier: best            # → Opus
  effort: high
  prompt: prompts/writer.md
  context:
    - { slice: profile_long,      priority: 1 }
    - { slice: voice,             priority: 1 }
    - { slice: style_overrides,   priority: 1 }
    - { slice: job_ad,            priority: 1 }
    - { slice: company_notes,     priority: 2 }
    - { slice: relevant_projects, priority: 2, top_k: 3 }   # valgt ut fra annonsen
    - { slice: evaluation,        priority: 3 }             # match_reasons/concerns fra filteret
  input_budget_tokens: 15000
  output_schema: DraftResult

reviser:
  model_tier: balanced
  effort: medium
  prompt: prompts/reviser.md
  context:
    - { slice: voice,             priority: 1 }
    - { slice: style_overrides,   priority: 1 }
    - { slice: job_ad_summary,    priority: 1 }
    - { slice: current_draft,     priority: 1 }
    - { slice: revision_log,      priority: 2, max_items: 5 }
    - { slice: profile_long,      priority: 3 }
  input_budget_tokens: 12000
```

**Budsjetthåndtering:** Kontekstbyggeren teller tokens før kallet. Går pakken over budsjettet, droppes eller forkortes biter med lavest prioritet først (priority 3 → 2). Priority 1 kuttes aldri. Kommer man likevel over, feiler kallet med en tydelig melding.

### 6.3 Agent-livssyklus: "bytte ut i stedet for å vokse"

| Agent | Livssyklus |
|---|---|
| Filter, researcher, writer, destiller | **Ett kall = én agent.** Ingen historikk. Ny instans for hver stilling. |
| Reviser (chat i editoren) | **Rullerende:** Hver brukermelding starter en *ny* agent med: gjeldende utkast + de siste N instruksjonene som en kompakt revisjonslogg + fast kontekst. Den fulle chathistorikken sendes aldri. Etter hvert svar lagres en ny utkastversjon. Konteksten er derfor like stor på runde 20 som på runde 1. |

Resultatet er at ingen agent noen gang trenger kompaktering eller utskiftning midt i en oppgave, fordi oppgavene er kuttet slik at de aldri blir store.

### 6.4 Valg av relevante prosjekter

For writer-agenten velges de 3 mest relevante prosjektene fra `projects/` ut fra overlapp mellom annonsens teknologier/nøkkelord og prosjektets `tech`-frontmatter (enkel deterministisk scoring, ingen embeddings i v1). Prosjekter med `highlight: true` får bonus.

### 6.5 Sikkerhet: annonser er utrygg input

Annonsetekst og nettsider kan inneholde instruksjoner rettet mot en LLM. Tiltak:
- Ekstern tekst pakkes inn i tydelige skilletegn og merkes som data i promptene.
- Bare research-agenten har verktøy (websøk/-henting), og ingen agent har skrivetilgang til filer, DB eller e-post. All skriving gjøres av pipeline-koden basert på strukturert output.
- Strukturert output (JSON-skjema) valideres før det lagres.

---

## 7. LLM-laget

### 7.1 Backend-abstraksjon

```python
class LLMBackend(Protocol):
    def run(self, req: AgentRequest) -> AgentResponse: ...
    # AgentRequest: system_prompt, messages, model_tier, effort, output_schema, tools
    # AgentResponse: text | parsed, usage (tokens), cost_estimate, model
```

To implementasjoner, valgt i `settings.yaml` (`llm.backend`):

| Backend | Hvordan | Fordel | Ulempe |
|---|---|---|---|
| `claude_code` | Kaller Claude Code CLI headless (`claude -p ... --output-format json`) som subprosess, med brukerens eksisterende innlogging | Bruker eksisterende abonnement, ingen ekstra kostnad | Abonnementets bruksgrenser gjelder, og CLI-flagg kan endre seg. Sjekk Anthropic sine gjeldende vilkår for automatisert bruk av abonnement. |
| `anthropic_api` | Offisiell `anthropic` Python-SDK med API-nøkkel | Stabilt, strukturert output, prompt caching, batch, presis kostnadsmåling | Betales per token |

Det finnes også en `mock`-backend for tester og utvikling av dashboardet uten LLM-kall.

> **Spike (fase 0):** Verifiser at `claude_code`-backenden fungerer for strukturert JSON-output og websøk, og hva som gjelder for bruk av abonnement i automatiserte skript. Hvis det ikke holder, er `anthropic_api` standard.

### 7.2 Modellvalg (konfigurerbart via `model_tier`)

| Tier | Modell | Brukes til |
|---|---|---|
| `fast` | `claude-haiku-5-5` | Filter-agent, enkle uttrekk |
| `balanced` | `claude-sonnet-5-5` | Research, revisjon, profil-destiller |
| `best` | `claude-opus-5-5` | Første søknadsutkast |

### 7.3 Kostnadsestimat (`anthropic_api`-backend)

Priser per oktober 2026 (per million tokens): Haiku 5.5 $0.10 / $0.50, Sonnet 5.5 $2 / $10, Opus 5.5 $4 / $20.

| Operasjon | Volum | Ca. kostnad |
|---|---|---|
| Filtrering (~3k inn / ~400 ut per annonse) | ~100 annonser/dag | ~$0.05/dag |
| Research (Sonnet + websøk) | ~15/uke | ~$0.05–0.10 per bedrift |
| Første utkast (Opus, ~15k inn / ~3k ut inkl. tenking) | 10–20/uke | ~$0.10–0.15 per utkast |
| Revisjoner (Sonnet) | ~3 per søknad | ~$0.03 per runde |
| **Totalt** | | **ca. $15–25/mnd (≈ 150–250 kr)** |

Prompt caching på den faste profilkonteksten reduserer dette ytterligere. Alle kall logges i `agent_runs` med tokens og estimert kostnad, og dashboardet viser forbruk per uke. Et månedlig kostnadstak i `settings.yaml` stopper LLM-kall når taket er nådd.

---

## 8. Datamodell (SQLite)

```
jobs                 id, fingerprint, title, company, company_slug, location, municipality,
                     remote (none|hybrid|full), job_type, description_raw, description_clean,
                     ad_language, published_at, deadline, first_seen, last_seen, active,
                     content_hash

job_sources          id, job_id → jobs, source (finn|nav|teamtailor|...), source_id, url,
                     raw_path (cache-fil), fetched_at

evaluations          id, job_id → jobs, score, role_category, job_type, seniority_fit,
                     match_reasons (json), concerns (json), model, prompt_version,
                     profile_hash, created_at

companies            slug (pk), name, notes_path, researched_at

applications         id, job_id → jobs (unik), status, created_at, applied_at,
                     follow_up_at, notes

application_events   id, application_id, from_status, to_status, at, comment   ← statushistorikk

drafts               id, application_id, version, content, author (agent|user),
                     instruction (hva ble bedt om), agent_run_id, created_at

agent_runs           id, agent, job_id?, application_id?, backend, model, prompt_version,
                     input_tokens, output_tokens, cost_usd, duration_ms, status, error, created_at

scrape_runs          id, trigger (schedule|manual), source, started_at, finished_at,
                     found, new, updated, errors (json)

settings_overrides   key, value    ← det som endres fra dashboardet (f.eks. geo-modus)
```

### 8.1 Søknadsstatus

```
  Ny ──► Interessant ──► Utkast ──► Søkt ──► Intervju ──► Tilbud
   │          │            │         │          │
   └──► Ikke aktuell ◄─────┘         └──────────┴──► Avslag / Trukket
                                                        
  (automatisk) Utløpt: fristen har passert uten at stillingen er søkt
```

- `Ny` og `Ikke aktuell` gjelder jobber (ingen søknadsrad ennå). Når brukeren markerer en jobb som `Interessant`, opprettes en `applications`-rad.
- Hver statusendring logges i `application_events`.
- `follow_up_at` settes automatisk (f.eks. 14 dager etter `Søkt`) og vises i dashboardet og i e-postdigesten.

---

## 9. Dashboard

FastAPI + Jinja2 + HTMX, på `http://localhost:8765`.

| Side | Innhold |
|---|---|
| **Oversikt** | Nye jobber siden sist, toppscorede, frister de neste 7 dagene, oppfølginger som forfaller, status for siste kjøring, "Kjør nå"-knapp |
| **Jobber** | Tabell/kort med filtre: jobbtype (faner), score, kilde, geografi-modus, rolle, frist. Hurtigvalg: Interessant / Ikke aktuell |
| **Jobbdetalj** | Annonsetekst, score med begrunnelse og bekymringer, bedriftsnotat, lenker til alle kilder, knapp "Research bedrift" og "Lag søknadsutkast" |
| **Søknadseditor** | Venstre: redigerbart utkast (textarea, autosave som ny versjon). Høyre: chat med revisjonsagenten. Versjonshistorikk med diff, "Kopier" og eksport til `.docx`/`.md` |
| **Tracker** | Kanban med kolonner per status, dra og slipp for å endre status, notater per søknad |
| **Innstillinger** | Geo-modus, jobbtyper, roller og ekskluderinger, varslingsterskel, modellvalg, kostnadstak. Status for kontekst ("profil_long er utdatert, regenerer") |
| **Logg & kostnader** | Kjøringer per kilde (funnet, nye, feil), agentkall og forbruk per uke |

Lange operasjoner (skraping, utkast) kjører som bakgrunnsjobber. Dashboardet poller status via HTMX.

---

## 10. Planlegging og varsling

### 10.1 Daglig kjøring
- `scripts/install_task_scheduler.ps1` registrerer en oppgave som kjører `jobsearcher run` hver dag kl. 07:00, med "kjør så snart som mulig hvis en planlagt kjøring ble gått glipp av" (PC-en kan ha vært av).
- "Kjør nå" i dashboardet starter den samme pipelinen i bakgrunnen.
- `data/run.lock` hindrer at to kjøringer går samtidig.

### 10.2 E-postdigest
Sendes etter hver daglig kjøring, men bare hvis det er noe å melde:
- Nye jobber med score ≥ terskel (standard 70), gruppert per jobbtype
- Frister de neste 3 dagene for jobber merket Interessant/Utkast
- Oppfølginger som forfaller
- Kildefeil (f.eks. "Finn-parseren fant 0 treff, kanskje har siden endret seg")

Gmail SMTP (`smtp.gmail.com:587`, STARTTLS) med app-passord fra `.env`. HTML-mal med lenker inn i dashboardet.

---

## 11. Konfigurasjon

| Fil | Innhold | I git? |
|---|---|---|
| `config/settings.yaml` | Søk (roller, ekskluderinger, jobbtyper, geo-modus), terskler, planlegging, LLM-backend, kostnadstak | Ja |
| `config/agents.yaml` | Kontekstmanifest, modell-tier og effort per agent | Ja |
| `config/locations.yaml` | Geo-moduser → kommunelister | Ja |
| `config/sources.yaml` | Aktive kilder, Finn-søkeparametre, ATS-bedriftsliste | Ja |
| `.env` | `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `ANTHROPIC_API_KEY` (valgfri) | **Nei** |

Innstillinger endret i dashboardet lagres i `settings_overrides` og overstyrer YAML-verdiene.

---

## 12. Filhierarki

```
JobSearcher/
├── README.md                          Oppsett og bruk
├── pyproject.toml                     Avhengigheter (uv), CLI-entrypoint `jobsearcher`
├── .env.example
├── .gitignore                         data/, .env, context/derived/
│
├── docs/
│   └── ARCHITECTURE.md                Dette dokumentet
│
├── config/
│   ├── settings.yaml
│   ├── agents.yaml
│   ├── locations.yaml
│   └── sources.yaml
│
├── context/
│   ├── README.md                      Guide: hvordan fylle ut profilen
│   ├── profile/                       LAG 1: skrevet av brukeren
│   │   ├── profile.yaml
│   │   ├── cv.md
│   │   ├── motivation.md
│   │   ├── style_overrides.md
│   │   ├── projects/
│   │   │   └── _template.md
│   │   ├── experience/
│   │   │   └── _template.md
│   │   └── writing_samples/
│   ├── derived/                       LAG 2: generert (gitignored)
│   │   ├── profile_short.md
│   │   ├── profile_long.md
│   │   ├── voice.md
│   │   └── manifest.json
│   └── prompts/                       LAG 3: systemprompter (versjonert)
│       ├── filter.md
│       ├── researcher.md
│       ├── writer.md
│       ├── reviser.md
│       └── distiller.md
│
├── src/jobsearcher/
│   ├── __init__.py
│   ├── cli.py                         `jobsearcher run | serve | rescore | distill | init-db`
│   ├── config.py                      Laster YAML + .env + overrides (pydantic-settings)
│   │
│   ├── db/
│   │   ├── models.py                  SQLModel-tabeller (§8)
│   │   ├── session.py
│   │   └── repo.py                    Spørringer brukt av pipeline og web
│   │
│   ├── sources/
│   │   ├── base.py                    JobSource-protokoll, RawJob, SearchQuery
│   │   ├── http.py                    Rate-limit, cache, retry, robots.txt
│   │   ├── finn.py
│   │   ├── nav.py
│   │   ├── jobbnorge.py
│   │   └── ats/
│   │       ├── teamtailor.py
│   │       ├── jobylon.py
│   │       └── webcruiter.py
│   │
│   ├── pipeline/
│   │   ├── run.py                     Orkestrator: hent → normaliser → filtrer → score → varsle
│   │   ├── normalize.py
│   │   ├── dedupe.py
│   │   ├── hardfilter.py
│   │   └── lock.py
│   │
│   ├── context/
│   │   ├── loader.py                  Leser profile/ (yaml + markdown med frontmatter)
│   │   ├── slices.py                  Én funksjon per slice-type (profile_short, job_ad, ...)
│   │   ├── builder.py                 Setter sammen pakker etter agents.yaml
│   │   ├── budget.py                  Token-telling og prioritetsbasert kutting
│   │   └── projects.py                Velger relevante prosjekter for en annonse
│   │
│   ├── agents/
│   │   ├── base.py                    Felles: bygg kontekst → kall backend → valider → logg agent_run
│   │   ├── filter.py
│   │   ├── researcher.py
│   │   ├── writer.py
│   │   ├── reviser.py
│   │   ├── distiller.py
│   │   └── schemas.py                 Pydantic-modeller for strukturert output
│   │
│   ├── llm/
│   │   ├── base.py                    LLMBackend-protokoll, AgentRequest/Response
│   │   ├── claude_code.py             Subprosess mot `claude -p`
│   │   ├── anthropic_api.py           Offisiell SDK
│   │   ├── mock.py
│   │   └── costs.py                   Prisliste og kostnadsberegning, kostnadstak
│   │
│   ├── tracking/
│   │   └── status.py                  Gyldige statusoverganger, oppfølgingslogikk
│   │
│   ├── notify/
│   │   ├── email.py
│   │   └── templates/digest.html
│   │
│   ├── export/
│   │   └── docx.py                    Eksport av søknadsbrev
│   │
│   └── web/
│       ├── app.py                     FastAPI-app, bakgrunnsjobber
│       ├── routes/
│       │   ├── dashboard.py
│       │   ├── jobs.py
│       │   ├── applications.py        Editor, versjoner, revisjonschat
│       │   ├── tracker.py
│       │   ├── settings.py
│       │   └── runs.py
│       ├── templates/                 Jinja2 (base.html + sider + HTMX-partials)
│       └── static/                    CSS, htmx.min.js
│
├── data/                              (gitignored)
│   ├── jobsearcher.db
│   ├── cache/                         Rå HTML/JSON per kilde
│   ├── companies/                     Bedriftsnotater (<slug>.md)
│   ├── exports/
│   ├── logs/
│   └── run.lock
│
├── scripts/
│   └── install_task_scheduler.ps1
│
└── tests/
    ├── fixtures/                      Lagrede Finn-sider, NAV-respons, eksempelprofil
    ├── test_finn_parser.py
    ├── test_nav_source.py
    ├── test_dedupe.py
    ├── test_hardfilter.py
    ├── test_context_builder.py
    ├── test_status_transitions.py
    └── evals/
        └── filter_labeled.jsonl       ~30 manuelt merkede annonser for å måle filter-agenten
```

---

## 13. Teknologivalg

| Behov | Bibliotek |
|---|---|
| Pakke-/miljøhåndtering | `uv` |
| Web | `fastapi`, `uvicorn`, `jinja2`, HTMX (statisk fil) |
| DB | `sqlmodel` (SQLAlchemy + Pydantic), `alembic` ved behov |
| Konfig | `pydantic-settings`, `pyyaml`, `python-frontmatter` |
| HTTP/parsing | `httpx`, `selectolax`, `playwright` (bare som fallback) |
| Fuzzy-match | `rapidfuzz` |
| LLM | `anthropic` (API-backend), Claude Code CLI (abonnement-backend) |
| CLI | `typer` |
| E-post | `smtplib` (stdlib) |
| Eksport | `python-docx` |
| Test | `pytest`, `respx` (mock av httpx) |

---

## 14. Veikart

| Fase | Innhold | Ferdig når |
|---|---|---|
| **0. Spikes** | Undersøk Finn sine søkesider (struktur, paginering, filtre), NAV-feeden og `claude_code`-backenden (JSON-output, websøk, vilkår) | Hvert spørsmål har et kort notat i `docs/spikes/` |
| **1. Fundament** | Repo-oppsett, config, DB-modeller, HTTP-lag, Finn- og NAV-kilde, normalisering, dedupe, `jobsearcher run` uten LLM | Daglig kjøring fyller DB med jobber |
| **2. Filter + dashboard v1** | Hardfilter, kontekstlag 1 og 2 (destiller), filter-agent, jobbliste, jobbdetalj | Rangerte jobber vises i dashboardet |
| **3. Søknader** | Research-agent, writer, editor med versjoner, revisjonschat, eksport | Utkast kan lages, redigeres og eksporteres |
| **4. Tracking + varsling** | Statusflyt, kanban, oppfølging, e-postdigest, Task Scheduler-script | Hele flyten går uten manuelt arbeid |
| **5. Flere kilder** | ATS-adaptere, Jobbnorge, kuratert selskapsliste for trainee/graduate/sommer | Trainee-programmer fanges opp |
| **6. Polering** | Kostnadsside, eval av filter-agenten, prompt-tuning | Filterets presisjon målt og akseptabel |

---

## 15. Kontekst brukeren må samle (før fase 2–3)

- [ ] CV (norsk og/eller engelsk) → `context/profile/cv.md`
- [ ] Utdanning: grad, skole, relevante emner, eventuelle karakterer → `profile.yaml`
- [ ] 3–5 prosjekter, én fil hver: hva, teknologi, din rolle, hva du lærte, lenke → `projects/`
- [ ] Erfaring, også ikke-teknisk (deltid, verv, frivillig) → `experience/`
- [ ] 2–5 søknader eller tekster du har skrevet selv → `writing_samples/`
- [ ] Hva du vil og ikke vil: teknologier, teamtyper, bransjer, dealbreakers → `motivation.md`
- [ ] Stilregler du vet du vil ha → `style_overrides.md`
- [ ] Praktisk: lønnsforventning, oppstartsdato, førerkort, språk → `profile.yaml`
- [ ] Gmail app-passord → `.env`

---

## 16. Åpne spørsmål og risiko

| # | Spørsmål / risiko | Håndtering |
|---|---|---|
| 1 | Finn kan endre sidestruktur eller blokkere automatisert trafikk | Fixtures og tester, varsling ved 0 treff, NAV som sikkerhetsnett, lavt volum |
| 2 | Er abonnementsbruk via `claude -p` stabilt og tillatt for dette formålet? | Spike i fase 0, med API-backend som fallback |
| 3 | Hvor godt klassifiserer filter-agenten trainee vs. graduate vs. fast? | Merket eval-sett (`tests/evals/`), mål og juster i fase 6 |
| 4 | Skal søknadsspråket følge annonsespråket automatisk? | Foreslått standard: ja (norsk annonse → norsk søknad), kan overstyres per søknad |
| 5 | Hvor mange trainee-kilder trengs for god dekning? | Starter med en kuratert liste og utvider etter hva som faktisk dukker opp |
