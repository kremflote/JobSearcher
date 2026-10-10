# JobSearcher: design- og arkitekturdokument

> Status: v0.10 (2026-10-10). Fase 0 og 0b (Finn-sjekk) er gjennomført, se `docs/spikes/`. Frontend-bølgene F0–F2 er bygget mot mock; backend-fasene er ikke startet.
> Dokumentet er "source of truth" for designet. UI-designet står i [FRONTEND.md](FRONTEND.md). Regler for vedlikehold står i `AGENTS.md`.

## Endringslogg

| Versjon | Dato       | Endring                                                                                                                                                                                                                                                                           |
| ------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v0.10   | 2026-10-10 | Statusovergangene i §9.1 er en eksplisitt tabell (bygget i F2). Nytt: Interessant → Søkt uten utkast (søkt utenfor appen), Tilbud → Trukket (takket nei), Ikke aktuell → Interessant (gjenåpne). Angre = tilbake til forrige status, som sletter siste hendelse. API-et sender lovlige neste statuser på hvert kort. Status `ny` heter "Ikke vurdert" i UI-et. |
| v0.9    | 2026-10-10 | Fase 0b: Finn-signeringen er verifisert mot levende API. Søkeresponsen har ikke annonsetekst, så Finn blir to steg (§4.2): signert søk, så `JobPosting` JSON-LD fra den offentlige annonsesiden for nye jobber etter hardfilteret. Searchkey er enum-navnet (`SEARCH_ID_JOB_FULLTIME`). Trainee- og sommersøk filtreres serverside med `job_duration`. Se spike 04 §Oppdatering. |
| v0.8    | 2026-10-10 | Veikartet (§17) er snudd til frontend først: F0–F4 bygges mot mock-data og prøves av brukeren før backend-fasene starter, så justeringer oppdages tidlig. Unntak: Finn-signaturen verifiseres først (fase 0b), siden den er største tekniske risiko. |
| v0.7    | 2026-10-10 | Dedupe på tvers av kilder presisert (§4.5): tre nøkler i rekkefølge (kilde-ID, normalisert søknads-URL, bedrift/orgnr + fuzzy tittel + sted). Brukeren har godkjent selskapslisten i spike 03, og Cloudflare-DNS og NPM-proxy er satt opp (§18). |
| v0.6    | 2026-10-10 | Dashboardet blir en React-SPA (Vite + TS + Tailwind/shadcn) over et JSON-API i FastAPI, for PC og mobil. Eget dokument `docs/FRONTEND.md` med skjermer, API-kontrakt og frontend-bølger F0–F5 som går parallelt med backend-fasene. Drift flyttes på sikt til Docker på hjemmeserveren (Raspberry Pi 4, arm64), nådd via Tailscale på `jobb.mariuskristensen.no`; koden er Docker-klar fra fase 1. Windows Task Scheduler erstattes av en planlegger i `serve`-prosessen med innhenting av tapt kjøring. `claude -p` kjører i containeren. Profilen redigeres i dashboardet i drift (ny tabell `profile_revisions`). |
| v0.5    | 2026-10-10 | Finn-APK-en er dekompilert (spike 04). Konkret base-URL, HMAC-nøkkel, signeringsmelding og jobbsøk-endepunkt er dokumentert. `finnsig`-biblioteket er droppet — vi implementerer signeringen selv i `finn_sig.py` (~20 linjer Python). Ingen designendring, bare presisering av implementasjonen. |
| v0.4    | 2026-10-10 | Finn hentes direkte fra mobil-API-et (reverse engineering av Android-APK, HMAC-signering), ikke via e-postvarsler. Søk defineres i `config/sources.yaml`. IMAP for Finn er droppet; Gmail brukes bare til SMTP-digest. Egen `enricher` for Finn-jobber er droppet — API-et gir full annonsetekst. Se spike 04. |
| v0.3    | 2026-10-10 | Finn-varsler er forhåndsfiltrert og regnes som gyldige (to tillitsnivåer i hardfilteret). Automatisk berikelse av Finn-jobber via `enricher` i stedet for manuell import. Ingen manuelle steg. Stillinger uten oppgitt senioritet vises med maks score 65. Geografi per jobbtype. |
| v0.2    | 2026-10-10 | Finn via e-postvarsler i stedet for skraping (spike 01). NAV er egen kilde, ikke fallback (spike 02). `claude_code` er standard backend (spike 03). Strengt senioritetsfilter. Frister og kontakter som egne felt. Konkrete design for agenter, drift og eval.                    |
| v0.1    | 2026-10-09 | Første utkast etter intervju                                                                                                                                                                                                                                                      |

---

## 1. Mål

Et frittstående Python-program som kjører på brukerens egen maskin (PC under utvikling, hjemmeserver i drift) og automatiserer jobbsøkingen for en nyutdannet utvikler i Nittedal:

1. **Samler inn** relevante stillinger daglig: Finn (via varsler), NAV-feeden og kilder for trainee/graduate.
2. **Filtrerer og rangerer** stillingene mot brukerens profil.
3. **Presenterer** resultatene i et web-dashboard for PC og mobil, med søknadsfrister i sentrum.
4. **Skriver utkast til søknadsbrev** ut fra profilen, annonsen og research om bedriften. Utkastet kan redigeres manuelt og itereres med en agent, og eksporteres til `.docx`.
5. **Holder oversikt** over søknader, status og frister.
6. **Varsler** på e-post om nye, relevante jobber og frister som nærmer seg.

**Utenfor scope:**
- Tilpasning av CV
- Automatisk innsending av søknader
- Egen modus for å svare på spørsmål i søknadsskjemaer: brukeren fyller ut skjemaer selv, med søknadsbrevet som grunnlag.
- Læring fra brukerens valg (Interessant / Ikke aktuell) i scoringen
- LinkedIn
- Skraping av Finn

### Designprinsipper

| Prinsipp | Konsekvens |
|---|---|
| **Tilstand i databasen, ikke i agentene** | Agenter er kortlivde og tilstandsløse. De får en ferdig kontekstpakke, gjør én jobb, returnerer strukturert output og avslutter. |
| **Orkestrering er kode, ikke LLM** | Pipelinen er deterministisk Python. LLM brukes bare der det trengs vurdering eller språk. |
| **Kontekst er strukturert og budsjettert** | Hver agent har et manifest med nøyaktig hvilke kontekstbiter den får, og et token-budsjett. |
| **Billig først, dyrt sist** | Deterministiske filtre → billig modell i batch → dyr modell bare på det brukeren velger. |
| **Respekter kildenes vilkår** | Bare offisielle feeder, kildens egne varsler og brukerens egen nettleser. Ingen omgåelse av tilgangskontroll. |
| **Alt er konfigurerbart** | Roller, geografi, jobbtyper, modeller og terskler i YAML |

---

## 2. Beslutninger

| Tema | Beslutning |
|---|---|
| Språk | Python 3.12+ |
| Kjøremiljø | Utvikling: brukerens Windows-PC. Drift (på sikt): Docker Compose på hjemmeserveren (Raspberry Pi 4, arm64). Koden er Docker-klar fra fase 1. |
| Planlegging | Planlegger i `jobsearcher serve`-prosessen (APScheduler, daglig 07:00, tapt kjøring tas igjen ved oppstart) og "Kjør nå" i dashboardet |
| Dashboard | React-SPA (Vite + TS) over JSON-API i FastAPI, én port. For PC og mobil. Se [FRONTEND.md](FRONTEND.md). |
| Tilgang | Utvikling: `127.0.0.1`. Drift: bare via Tailscale på `jobb.mariuskristensen.no`. Ingen innlogging i appen. |
| Database | SQLite via SQLModel, migrasjoner med Alembic |
| E-post | Gmail SMTP for utsending av digest. Ingen IMAP. |
| LLM | Claude. Standard: `claude_code` (abonnement via `claude -p`). Alternativ: `anthropic_api`. |
| Finn | Mobil-API på `https://appsgw.finn.no/` med HMAC-SHA512-signering (egen implementasjon fra spike 04 §Signering, verifisert i fase 0b) for søk. Annonsetekst fra `JobPosting` JSON-LD på den offentlige annonsesiden, bare for nye jobber etter hardfilteret. Søk defineres i `config/sources.yaml`. Endepunkter er reverse-engineert fra Android-APK (v`261006-ec709768`). Se spike 04. |
| NAV | pam-stilling-feed med privat token |
| Trainee/graduate | NAV + Teamtailor-RSS + kuratert selskapsliste med sideovervåker |
| Volum | 10–20 søknader per uke |
| Senioritet | Bare junior, trainee, graduate, nyutdannet, internship og sommerjobb. Krav om 1+ års erfaring forkastes. |
| Geografi | Per jobbtype: fast stilling i `oslo_omegn` (Oslo med nærområder, inkl. Nittedal). Trainee, graduate og sommerjobb i hele `norge`. `nittedal` finnes som alternativ. |
| Kildetillit | Finn-API-kall sendes med `experience`- og `education`-filtre (ingen erfaring/junior, ingen/bachelor) og regnes som forhåndsfiltrert. Andre kilder filtreres med strengmatching + LLM. |
| Søknad | Ett vanlig søknadsbrev per stilling. Eksport til `.docx`. |
| Tracking | Søknadsfrist er viktigst. Kontaktpersoner og nøkkelinfo lagres når de finnes. |
| Kostnad | Tak $25/mnd. E-postvarsel ved score ≥ 70. |
| Reposts | Kobles til opprinnelig jobb via fingerprint og merkes "lagt ut på nytt" |
| Profil i git | Nei. `context/profile/` er gitignored, bare malene versjoneres. I drift ligger profilen i datavolumet og redigeres i dashboardet (§6.1). |

---

## 3. Systemoversikt

```
  Finn mobil-API            NAV pam-stilling-feed      Teamtailor RSS / karrieresider
        │ HMAC-SHA512-signert HTTP   │ API                        │ RSS / sideovervåker
        │ (finn_sig.py)              │                            │
        ▼                            ▼                            ▼
        ┌────────────────────────────────────────────────────────────────┐
        │                Pipeline-orkestrator (kode)                     │ ← planlegger i serve / "Kjør nå"
        │ hent → normaliser → dedupe/repost → hardfilter → score (batch) │   (lock-fil)
        │ → varsle → backup                                              │
        └────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                                SQLite ◄──────────────────────────────┐
                                   ▲                                   │
   ┌──── Dashboard (React-SPA + FastAPI /api, :8765, PC og mobil) ────┘
   │  • Frister og nye jobber   • Triage          • Profil
   │  • "Lag søknad"            • Tracker         • Innstillinger
   ▼
 Research-agent ──► Skrive-agent ──► Revisjonsagent (rullerende) ──► .docx
 (Sonnet + web)     (Opus)           (Sonnet)
        ▲                ▲                 ▲
        └─ Kontekstbygger: pakker etter manifest, innenfor token-budsjett ─┘
```

---

## 4. Datakilder

### 4.1 Kildegrensesnitt

```python
class JobSource(Protocol):
    name: str
    def collect(self, since: Cursor | None) -> CollectResult: ...
    # CollectResult: list[RawJob], ny cursor, helsestatus (antall, feil)
```

- Hver kilde lagrer sin egen cursor i `source_state` (Finn-API: siste `publishedAt` per søk, NAV `next_url`/ETag, RSS ETag, sidehash).
- Kildene returnerer `RawJob` med så mange strukturerte felt som kilden har. Felles normalisering tar resten.
- Felles HTTP-lag (`sources/http.py`):
  - rate-limiting per domene
  - retry med backoff
  - `If-None-Match` og `If-Modified-Since`
  - respekt for `robots.txt`
  - rå respons lagres i `data/cache/`

### 4.2 Finn via mobil-API (spike 04)

Finn har ikke et offisielt tredjeparts-API, men mobilappen snakker med et HMAC-signert HTTP-API på `https://appsgw.finn.no/` som kan brukes direkte. Endepunktene og signeringsregelen er reverse-engineert fra Android-APK-en (`FINN.no_*.apk`, i prosjektrot, gitignored). Forespørsler signeres med `FINN-GW-KEY`-headeren (HMAC-SHA512 → base64) — vi implementerer signeringen selv i `finn_sig.py` (se spike 04 §Signering). Dette er en bevisst gråsone — risikoen og tiltakene står i spike 04.

1. **Søk defineres i `config/sources.yaml`**, ikke i Finns UI. Hvert søk setter Finns egne filtre som API-parametere:
   - *Utdanning (`education`):* ingen utdanning (`465`), høyskole/universitet lavere nivå (`464`)
   - *Arbeidserfaring (`work_experience`):* ingen erfaring (`455`), junior (`456`)

   | Søk-id | `searchkey` | Ekstra filter | Geografi |
   |---|---|---|---|
   | `it_oslo` | `SEARCH_ID_JOB_FULLTIME` | — | `oslo_omegn` |
   | `it_norge` | `SEARCH_ID_JOB_FULLTIME` | — | `norge` |
   | `trainee` | `SEARCH_ID_JOB_FULLTIME` | `job_duration=8098` (trainee) | `norge` |
   | `graduate` | `SEARCH_ID_JOB_FULLTIME` | `q=graduate` | `norge` |
   | `summer` | `SEARCH_ID_JOB_FULLTIME` | `job_duration=1816` (sommer/sesong) | `norge` |

   Alle går mot `GET /search/{searchkey}?client=android-finn&sort=PUBLISHED_DESC&<filtre>` med `FINN-GW-Service: Search-Quest-JB`. Filter-ID-ene (`occupation`, `location`, `work_experience`, `education`, `job_duration`) står i spike 04 §Oppdatering og i fixtures `tests/fixtures/finn/filters_*.json`. De ligger i `config/sources.yaml`; ved kjøring sjekkes de mot ferske filter-metadata (`include_results=false&include_filters=true`), og ukjente ID-er gir en kildehelse-advarsel (§12).
2. **`FinnApiSource`** gjør to steg:
   - **Søk:** `GET /search/{searchkey}?client=android-finn&<filtre>&page=N` (signert) → 50 annonser per side med Finn-kode, tittel, stillingstittel, bedrift, sted, publisert, frist, antall stillinger og erfaring/utdanning-ID-er. **Ingen annonsetekst.** Samme Finn-kode fra flere søk blir én jobb.
   - **Detalj:** for nye jobber som har passert hardfilteret (§5.1) hentes `https://www.finn.no/job/ad/{finnkode}` (vanlig GET, ingen HMAC), og `JobPosting` fra JSON-LD-blokken gir annonsetekst (`description`, HTML), arbeidsgiver, sted og frist. Det er samme side som appens WebView viser. Bare nye jobber hentes, så volumet er lavt (typisk 10–30 per døgn). Feiler detaljhentingen, beholdes jobben med `ad_text_status = missing` og prøves igjen neste kjøring.
3. **Cursor** per søk-id lagres i `source_state` som høyeste sette `published` (ms). Med `sort=PUBLISHED_DESC` blas det side for side til en annonse er eldre enn cursoren. Finn gir maks 50 sider, så søkene må være filtrert. Rate-limit og retry håndteres av det felles HTTP-laget (§4.1).
4. **Finn-annonser er forhåndsfiltrert og regnes som gyldige.** API-kallet filtrerer serverside på erfaring og utdanning, så de slipper senioritetsfilteret (§5.1) og blir aldri skjult på grunn av senioritet. Står det likevel et eksplisitt erfaringskrav i teksten, legges det inn som en `concern`, men jobben vises. Rolle-ekskludering (f.eks. cybersikkerhet) og geografi gjelder fortsatt.
5. Jobben opprettes med `prefiltered = true` og `ad_text_status = present` når detaljhentingen lyktes. Ingen LLM-berikelse trengs.
6. **App-identitet:** `User-Agent`, `x-nmp-app-version-name` og tilhørende headere låses til appversjon `261006-ec709768` (fra APK-en), slik at trafikken ser realistisk ut og endepunkter ikke flyter mellom versjoner.
7. **Fallback om API-et blir ubrukelig** (signaturen brytes, endepunkt forsvinner): brukeren limer inn annonsetekst via `manual`-kilden (§4.1 / §9 `job_sources.source`). IMAP-flyten er ikke en lett vei tilbake.

### 4.3 NAV pam-stilling-feed (spike 01)

- Hendelsesfeed. Leser fra lagret `next_url` med `ETag`, og henter detaljer for nye eller endrede annonser.
- Første kjøring: start 30 dager tilbake i tid.
- Inneholder ca. 1000 nye annonser per dag fra hele landet, uten filtrering på serversiden. Hardfilteret (§5.1) tar bort det meste før LLM.
- Strukturerte felt brukes direkte: kommune, frist, kontakter, arbeidsgiver, ansettelsesform, yrkeskategori.
- Inaktive annonser → `jobs.active = false` (påkrevd etter vilkårene).
- Privat token i `.env` (`NAV_FEED_TOKEN`).

### 4.4 Trainee, graduate og sommerjobb (spike 03)

- **NAV** dekker mange ATS-annonser allerede.
- **`TeamtailorSource`:** `https://<karriereside>/jobs.rss` per selskap i `config/sources.yaml`.
- **`PageWatcherSource`:** for karrieresider uten feed. Henter én side per selskap per dag og hasher hovedinnholdet (valgfri CSS-selektor). Ved endring trekker en billig LLM-modell ut stillinger fra siden. Respekterer `robots.txt`.
- Startliste i spike 03. Kildene evalueres etter 2–4 uker i drift.

### 4.5 Normalisering, dedupe og reposts

- **Fingerprint:** normalisert `bedrift | tittel | kommune` (små bokstaver, uten tegnsetting og vanlige suffiks som "AS"/"ASA").
- **Samme stilling fra flere kilder:** en ny annonse kobles til en eksisterende aktiv `Job` ved første treff i denne rekkefølgen. Treff → én `Job` med flere `job_sources`.

  | # | Nøkkel | Hvorfor |
  |---|---|---|
  | 1 | Samme `source` + `source_id` | Samme annonse hentet på nytt |
  | 2 | Samme normaliserte `application_url` (uten query/fragment, uten `www.`) | NAV og Finn lenker ofte til samme ATS-side (Teamtailor, Webcruiter) som vi også henter direkte |
  | 3 | Samme bedrift + tittel med rapidfuzz `token_set_ratio` ≥ 90 + overlappende sted (eller ett av stedene mangler) | Fanger annonser med ulik URL. Bedrift = `org_number` når kilden har det (NAV), ellers normalisert navn. |

  Kilden med mest strukturert data blir primær (NAV > Finn-API > ATS > sideovervåker). Usikre treff (score 80–89 på #3) slås ikke sammen, men logges, så terskelen kan justeres etter noen uker i drift.
- **Repost:** Samme fingerprint som en inaktiv jobb, eller en jobb eldre enn 30 dager → ny `Job` med `reposted_from_id`. Jobben merkes "lagt ut på nytt", og tidligere status og søknad vises.
- **Frist:** lagres som `deadline` (dato) og/eller `deadline_text` ("snarest", "fortløpende"). Kildens strukturerte felt har forrang. Ellers trekker filteret ut fristen.

### 4.6 Rensing av annonsetekst

- HTML → Markdown (selectolax + markdownify). Skript, navigasjon og "Del annonsen"-tekst fjernes.
- Felles boilerplate fra samme arbeidsgiver (f.eks. "Om oss" som går igjen) kortes ned etter at den er sett i ≥ 3 annonser.
- Hvis `job_ad` overskrider budsjettet (2500 tokens): behold tittel og innledning, prioriter avsnitt med nøkkelord som "kvalifikasjoner", "krav", "arbeidsoppgaver", "vi tilbyr" og "søknad", og kutt resten med en markør.

---

## 5. Filtrering og rangering

### 5.1 Steg 1: regelbasert hardfilter (gratis)

Konfigurert i `config/settings.yaml`. Kildene har to tillitsnivåer:

| Tillit | Kilder | Behandling |
|---|---|---|
| **Forhåndsfiltrert** | Finn-API (serverside-filtre for erfaring og utdanning) | Bare geografi og rolle-ekskludering. Antas å passe på nivå. |
| **Ufiltrert** | NAV, Teamtailor, sideovervåker | Alle regler under, med strengmatching som første ledd og LLM som andre |

Forkaster hvis:

- **Geografi:** kommunen er utenfor modusen for jobbtypen (§5.3). Remote med norsk arbeidsgiver slipper gjennom.
- **Rolle:** tittel eller kategori treffer et ekskluderingsord (`sikkerhet`, `security`, `SOC`, `pentest`, `cyber`, …), eller yrkeskategorien er klart ikke-IT.
- **Senioritet** (bare ufiltrerte kilder), med strengt filter:
  - tittelen inneholder `senior`, `lead`, `principal`, `arkitekt`, `leder`, `head of`, `erfaren`, `experienced`
  - teksten krever erfaring i år: regex for `\b([1-9]\d?)\s*(\+|-\s*\d+)?\s*(års?|years?)\b` i nærheten av `erfaring`/`experience`. Krav på 1 år eller mer forkastes.
- Jobben er allerede vurdert med samme `content_hash`, `profile_hash` og `prompt_version`.

Hardfilteret logger *hvorfor* noe ble forkastet, slik at det kan justeres. Dashboardet har en skjult fane "Forkastet i dag".

### 5.2 Steg 2: filter-agent (Haiku, batch)

- **Batching:** opptil 10 annonser per kall. Felles kontekst (kort profil og preferanser) sendes én gang. Det gir lavere overhead og utnytter prompt caching.
- **Output per annonse:** `FilterResult` (§7.2). Inneholder score, klassifisering, **sammendrag**, frist og kontakter. Sammendraget gjenbrukes senere som `job_ad_summary`, så annonsen ikke må leses på nytt.
- **Senioritet etter LLM** (bare ufiltrerte kilder, siden Finn-jobber alltid regnes som `entry`): `seniority` er `entry | unspecified | experienced`.
  - `experienced` skjules.
  - `unspecified` (ingen krav om erfaring, men heller ikke uttalt junior) **vises med lavere score**: maks 65, altså under e-postterskelen på 70. Disse havner i dashboardet, men utløser ikke varsel.
  - Taket på 65 settes av koden etter LLM-kallet (`search.unspecified_seniority_max_score`), slik at det gjelder uansett hva modellen svarer.
- Finn-jobber får full annonsetekst fra annonsesiden (§4.2), så `confidence: low` er ikke normalt for Finn-jobber. Faller API-et ut og en jobb havner inn via manuell innliming uten tekst, gjelder samme regel som før: `confidence: low` skjules ikke på grunn av lav score alene.

### 5.3 Geografi-moduser (`config/locations.yaml`)

| Modus | Kommuner |
|---|---|
| `nittedal` | Nittedal, Oslo (bydel Grorud, Stovner, Bjerke, Nordre Aker), Lillestrøm, Lørenskog, Gjerdrum |
| `oslo_omegn` **(standard)** | Oslo, Nittedal, Lillestrøm, Lørenskog, Rælingen, Gjerdrum, Bærum, Ullensaker (Gardermoen) |
| `norge` | Alle |

Listene er utgangspunkt og redigeres fritt.

**Modus per jobbtype.** Brukerens Finn-søk for trainee, graduate og sommerjobb gjelder hele landet. Søket for faste IT-jobber gjelder Oslo. Geografi settes derfor per jobbtype, og kan endres i dashboardet:

```yaml
geography:
  permanent: oslo_omegn
  trainee:   norge
  graduate:  norge
  summer:    norge
```

### 5.4 Jobbtyper

`trainee`, `graduate`, `summer` (sommerjobb/internship), `permanent` (fast junior/nyutdannet). Hver type kan slås av og på og vises som egen fane. Typen settes fra kildens felt (ansettelsesform, tittel) og ellers av filteret.

### 5.5 Ny scoring

- **Automatisk:** når `content_hash` endres (annonsen er oppdatert, eller tekst er importert).
- **Profil eller prompt endret:** dashboardet viser "N aktive jobber er scoret med gammel profil, estimert kostnad $X" og en knapp. Bare aktive jobber med status Ikke vurdert eller Interessant, publisert de siste 30 dagene, scores på nytt. Aldri automatisk, for å holde kostnaden nede.

---

## 6. Kontekstsystemet

### 6.1 Tre lag

```
context/
├── profile/   LAG 1: Kilde. Skrevet av brukeren. GITIGNORED (persondata), bare _template.md versjoneres.
├── derived/   LAG 2: Destillert. Generert, cachet på hash. Gitignored.
└── prompts/   LAG 3: Systemprompter per agent. Versjonert i git.
```

**Lag 1: kilde**

| Fil | Innhold |
|---|---|
| `profile.yaml` | Fakta: kontakt, utdanning med karakterer, ferdigheter med nivå 1–3, språk, praktisk |
| `cv.md` | Full CV |
| `motivation.md` | Hva brukeren vil, hvorfor utvikler, egenskaper, dealbreakers |
| `style_overrides.md` | Eksplisitte stilregler. Overstyrer alt annet. |
| `projects/*.md` | Ett prosjekt per fil. Frontmatter: `tech`, `categories`, `role`, `link`, `highlight` |
| `experience/*.md` | Én jobb per fil |
| `writing_samples/*.md` | Egne tekster. Frontmatter `outcome` sier om de ga intervju. |

Filer som starter med `_` ignoreres.

**Plassering:** Lag 1 leses fra `PROFILE_DIR` (standard `context/profile/`). I drift er det `/data/profile/` i containerens datavolum, og profilen redigeres i dashboardet (FRONTEND §5.6). Hver lagring skriver filen og en rad i `profile_revisions`. Appen er uavhengig av Obsidian; enhver editor fungerer under utvikling.

**Lag 2: destillert** (laget av destiller-agenten når hash av lag 1 endres)

| Fil | Mål | Brukes av |
|---|---|---|
| `profile_short.md` | ~500 tokens | Filter |
| `profile_long.md` | ~3000 tokens | Skriver, reviser |
| `voice.md` | ~800 tokens | Skriver, reviser |
| `manifest.json` | Hash per kildefil, `profile_hash`, versjon av destiller-prompten | Kontekstbygger |

**Bedriftskontekst:** `data/companies/<slug>.md`, laget av research-agenten. Cache i 90 dager.

### 6.2 Kontekstmanifest per agent (`config/agents.yaml`)

```yaml
filter:
  model_tier: fast
  effort: low
  prompt: prompts/filter.md
  batch_size: 10
  context:                                    # felles for batchen
    - { slice: profile_short,   priority: 1 }
    - { slice: search_prefs,    priority: 1 }  # roller, jobbtyper, senioritetsregler
  per_item:
    - { slice: job_ad,          priority: 1, max_tokens: 2500 }
    - { slice: job_meta,        priority: 1 }  # kildens strukturerte felt
  input_budget_tokens: 30000
  output_schema: FilterBatchResult

researcher:
  model_tier: balanced
  effort: medium
  tools: [web_search, web_fetch]
  prompt: prompts/researcher.md
  context:
    - { slice: company_meta,    priority: 1 }  # navn, orgnr, hjemmeside, beskrivelse fra NAV
    - { slice: job_ad_summary,  priority: 1 }
  input_budget_tokens: 4000
  output_schema: CompanyNote

writer:
  model_tier: best
  effort: high
  prompt: prompts/writer.md
  context:
    - { slice: style_overrides,   priority: 1 }
    - { slice: voice,             priority: 1 }
    - { slice: profile_long,      priority: 1 }
    - { slice: job_ad,            priority: 1, max_tokens: 3000 }
    - { slice: company_note,      priority: 2 }
    - { slice: relevant_projects, priority: 2, top_k: 3 }
    - { slice: evaluation,        priority: 3 }   # match_reasons / concerns
  input_budget_tokens: 15000
  output_schema: DraftResult

reviser:
  model_tier: balanced
  effort: medium
  prompt: prompts/reviser.md
  context:
    - { slice: style_overrides, priority: 1 }
    - { slice: voice,           priority: 1 }
    - { slice: job_ad_summary,  priority: 1 }
    - { slice: current_draft,   priority: 1 }
    - { slice: user_message,    priority: 1 }
    - { slice: revision_log,    priority: 2, max_items: 5 }
    - { slice: profile_long,    priority: 3 }
  input_budget_tokens: 12000
  output_schema: RevisionResult

distiller:
  model_tier: balanced
  effort: medium
  prompt: prompts/distiller.md
  context:
    - { slice: profile_all,     priority: 1 }  # alle kildefiler i lag 1
  input_budget_tokens: 40000
  output_schema: DistilledProfile
```

**Budsjett:** Kontekstbyggeren teller tokens før hvert kall (estimat: tegn/3.5, med `count_tokens` på API-backend). Over budsjett kuttes biter med prioritet 3, deretter 2. Prioritet 1 kuttes aldri. Går det fortsatt over, feiler kallet med en tydelig melding.

**Kilder for alle slices:**

| Slice | Produseres av |
|---|---|
| `job_ad` | Rensing, §4.6 |
| `job_meta` | Kildens strukturerte felt |
| `job_ad_summary` | Filter-agenten (`summary` + `key_requirements` + `tech`) |
| `company_meta` | Kilde (NAV) eller tittel/bedrift |
| `company_note` | Research-agenten |
| `evaluation` | Filter-agenten |
| `relevant_projects` | §6.4 |
| `current_draft` / `revision_log` | `drafts`-tabellen |

### 6.3 Agentenes livssyklus

| Agent | Livssyklus |
|---|---|
| Filter, researcher, writer, distiller | Ett kall er én agent, uten historikk |
| Reviser | Rullerende: hver brukermelding starter en ny agent med gjeldende utkast, de siste 5 instruksjonene som en kompakt logg og fast kontekst. Konteksten er like stor i runde 20 som i runde 1. |

### 6.4 Valg av relevante prosjekter

1. Filter-agenten gir `tech[]` og `role_category` for annonsen.
2. `config/tech_aliases.yaml` normaliserer synonymer (`react.js`/`reactjs` → `react`, `.net`/`dotnet`/`asp.net core` → `dotnet`, `k8s` → `kubernetes`).
3. Score per prosjekt:
   - +3 per teknologi annonsen og prosjektet har felles
   - +2 hvis `categories` inneholder annonsens `role_category`
   - +2 hvis `highlight: true`
   - +1 hvis `type` er `jobb` eller `personlig` og prosjektet er i bruk (skiller fra rene skoleoppgaver ved lik score)
4. De 3 beste tas med i sin helhet. Resten nevnes med én linje i `profile_long`.

### 6.5 Sikkerhet

- Annonsetekst, e-poster og nettsider er **utrygg input**. De pakkes i `<job_ad>…</job_ad>`-blokker, og promptene sier eksplisitt at innholdet er data, ikke instruksjoner.
- Bare research-agenten har verktøy (websøk/-henting). Ingen agent kan skrive filer, endre DB eller sende e-post. All skriving gjøres av koden ut fra validert, strukturert output.
- `claude_code`-backenden kjører hvert kall i en tom arbeidsmappe med eksplisitt verktøyliste (§8.1).

---

## 7. Agentene

Systemprompter ligger i `context/prompts/*.md`. Hver har en `version` i frontmatter, som lagres på resultatet.

### 7.1 Oversikt

| Agent | Modell | Når | Input | Output |
|---|---|---|---|---|
| Distiller | Sonnet | Profilhash endret | Hele lag 1 | `profile_short`, `profile_long`, `voice` |
| Filter | Haiku | Hver kjøring, i batch | Kort profil + 10 annonser | `FilterResult` × 10 |
| Researcher | Sonnet + web | Første søknad til en bedrift | Bedriftsmeta + sammendrag | `CompanyNote` |
| Writer | Opus | "Lag søknad" | Se §6.2 | `DraftResult` |
| Reviser | Sonnet | Hver chatmelding i editoren | Se §6.2 | `RevisionResult` |
| Extractor | Haiku | Sideovervåker oppdaget endring | Rensket side | Liste over stillinger |

### 7.2 Output-skjemaer (Pydantic, i `agents/schemas.py`)

```python
class Contact(BaseModel):
    name: str; role: str | None; email: str | None; phone: str | None

class FilterResult(BaseModel):
    job_id: str
    score: int                      # 0–100
    confidence: Literal["high", "low"]          # low når annonseteksten mangler
    role_category: Literal["backend","frontend","fullstack","mobile","devops","data","other"]
    job_type: Literal["trainee","graduate","summer","permanent","unknown"]
    seniority: Literal["entry","unspecified","experienced"]
    tech: list[str]
    summary: str                    # 2–4 setninger: hva jobben er
    key_requirements: list[str]     # maks 6
    match_reasons: list[str]        # maks 4
    concerns: list[str]             # maks 4
    deadline: date | None
    deadline_text: str | None       # "snarest", "fortløpende"
    contacts: list[Contact]
    application_url: str | None
    ad_language: Literal["no","en"]

class CompanyNote(BaseModel):
    what_they_do: str
    size_and_locations: str | None
    tech_and_engineering: str | None   # stack, techblogg, open source
    recent_news: list[str]             # maks 3, med dato
    culture_and_values: str | None
    hooks_for_letter: list[str]        # konkrete ting brevet kan koble seg til
    sources: list[str]                 # URL-er

class DraftResult(BaseModel):
    language: Literal["no","en"]
    letter_markdown: str
    used_projects: list[str]
    claims_to_verify: list[str]   # påstander om brukeren som ikke er dekket av profilen
    notes_for_user: str | None    # f.eks. "annonsen ber om attester"

class RevisionResult(BaseModel):
    letter_markdown: str
    change_summary: str           # én linje, går inn i revision_log
    claims_to_verify: list[str]
```

Ugyldig output → ett nytt forsøk med valideringsfeilen i prompten → deretter markeres kallet som feilet.

### 7.3 Research-agenten

- Verktøy: websøk og -henting (`claude_code`: `--allowedTools "WebSearch,WebFetch"`. API: server-verktøyene `web_search`/`web_fetch`).
- Prioriterte kilder: bedriftens nettside (om oss, karriere, techblogg), nyheter siste 12 måneder, Proff/Brønnøysund for størrelse.
- Maks ~8 verktøykall.
- **Fallback uten web:** notatet bygges bare fra arbeidsgiverbeskrivelsen i NAV-annonsen og annonsen selv, og merkes `limited`.
- Cache 90 dager per `company_slug`. Kan oppdateres manuelt i dashboardet.

### 7.4 Skrive-agenten

- Ett vanlig søknadsbrev per stilling, også når stillingen har søknadsskjema. Brevet er da grunnlag for skjemautfyllingen.
- Språket følger `ad_language`, og kan overstyres i dashboardet.
- Lengde og stil fra `style_overrides.md`. Stemme fra `voice.md`.
- **Faktaregel:** Brevet kan bare påstå ting om brukeren som finnes i profilen. Alt annet skal i `claims_to_verify`, og vises som advarsel i editoren.
- Skriveeksemplene ga ikke intervju. De brukes for stemmen, ikke for strukturen (står i `style_overrides.md`).

### 7.5 Destiller

- Kjører når `profile_hash` endres, og ved `jobsearcher distill`.
- `voice.md`: beskriver stilen (setningslengde, tone, humor, typiske uttrykk) med 2–3 korte sitater fra eksemplene. Skrivefeil tas ikke med som stiltrekk.
- Dashboardet viser diff av de destillerte filene, slik at brukeren kan se hva agentene "tror" om hen.

---

## 8. LLM-laget

### 8.1 Backends (spike 02)

```python
class LLMBackend(Protocol):
    def run(self, req: AgentRequest) -> AgentResponse: ...
    # AgentRequest: system_prompt, user_content, model_tier, effort, output_schema, tools, max_budget_usd
    # AgentResponse: parsed | text, usage, cost_usd, model, duration_ms
```

**`claude_code` (standard):** subprosess av `claude -p` med:
- `--output-format json --json-schema <schema>` → `structured_output`
- `--model <alias>`
- `--system-prompt-file <prompt>`, som erstatter Claude Code sin standardprompt
- `--allowedTools` bare for research-agenten. Ellers ingen verktøy.
- `--permission-prompts none`, `--max-budget-usd`
- Arbeidsmappe: `data/llm_sandbox/` (tom). MCP-servere, hooks og brukerinnstillinger isoleres bort. Eksakte flagg verifiseres ved implementering.
- `ANTHROPIC_API_KEY` fjernes fra subprosessens miljø, så abonnementet brukes.
- Kostnad fra `total_cost_usd`.
- **I container:** Claude Code CLI installeres i imaget (linux-arm64). Innlogging på abonnementet gjøres én gang med `claude setup-token`, og tokenet legges i `.env` som `CLAUDE_CODE_OAUTH_TOKEN`. Verifiseres når fase 4b starter.

**`anthropic_api`:** offisiell `anthropic`-SDK med strukturert output, prompt caching på profilkonteksten og server-verktøy for research.

**`mock`:** faste svar for tester og dashboardutvikling.

### 8.2 Modeller (`model_tier`)

| Tier | `claude_code` | `anthropic_api` |
|---|---|---|
| `fast` | `haiku` | `claude-haiku-5-5` |
| `balanced` | `sonnet` | `claude-sonnet-5-5` |
| `best` | `opus` | `claude-opus-5-5` |

### 8.3 Kostnad

Med `anthropic_api` estimeres ca. $15–25/mnd (filter ~$0.05/dag, utkast ~$0.10–0.15 stk, research ~$0.05–0.10). Med `claude_code` trekkes bruken fra abonnementet, men `total_cost_usd` logges likevel.

**Kostnadstak:** $25/mnd (rullerende kalendermåned).
- Ved 80 %: advarsel i dashboardet og digesten.
- Ved 100 %: filter-kall stoppes. Brukerinitierte kall (utkast, revisjon) krever bekreftelse i dashboardet.

---

## 9. Datamodell (SQLite)

```
jobs                 id, fingerprint, title, company, company_slug, location_text, municipality,
                     remote (none|hybrid|full), job_type, seniority, ad_language,
                     description_clean, ad_text_status (present|missing|imported),
                     published_at, expires_at, deadline, deadline_text, application_url,
                     first_seen, last_seen, active, content_hash, reposted_from_id

job_sources          id, job_id, source (finn_api|nav|teamtailor|page_watch|manual),
                     source_id, url, raw_path, fetched_at

job_contacts         id, job_id, name, role, email, phone, source (feed|llm|manual)

evaluations          id, job_id, score, confidence, role_category, job_type, seniority,
                     tech (json), summary, key_requirements (json), match_reasons (json),
                     concerns (json), model, prompt_version, profile_hash, created_at

hardfilter_log       id, job_id, rule, detail, created_at          ← "hvorfor forkastet"

companies            slug, name, org_number, homepage, note_path, note_quality (full|limited),
                     researched_at

applications         id, job_id (unik), status, created_at, applied_at, follow_up_at,
                     next_step, next_step_at, notes

application_events   id, application_id, from_status, to_status, at, comment

drafts               id, application_id, version, content, author (agent|user),
                     instruction, change_summary, claims_to_verify (json), agent_run_id, created_at

agent_runs           id, agent, job_ids (json), application_id, backend, model, prompt_version,
                     input_tokens, output_tokens, cost_usd, duration_ms, status, error, created_at

scrape_runs          id, trigger (schedule|manual), source, started_at, finished_at,
                     found, new, updated, filtered_out, errors (json), health (ok|warn|fail)

source_state         source, key, cursor, etag, last_success_at       ← cursorer per kilde

tasks                id, kind, params (json), status, progress, message, cancel_requested,
                     created_at, finished_at                           ← bakgrunnsjobber

settings_overrides   key, value

profile_revisions    id, path, content, content_hash, created_at        ← historikk for profilredigering
```

### 9.1 Søknadsstatus

```
Ikke vurdert ─► Interessant ─► Utkast ─► Søkt ─► Intervju ─► Tilbud
 │                   │           │         │        │
 └──► Ikke aktuell ◄─────────────┘         └────────┴──► Avslag / Trukket

(automatisk) Utløpt: fristen har passert og stillingen er ikke søkt
```

Hovedflyten over; tabellen er fasit. Backend validerer, ellers 409 `invalid_transition`:

| Fra | Til |
|---|---|
| Ikke vurdert (`ny`) | Interessant, Ikke aktuell (triage, FRONTEND §5.2) |
| Interessant | Utkast, Søkt, Ikke aktuell |
| Utkast | Søkt, Ikke aktuell |
| Søkt | Intervju, Avslag, Trukket |
| Intervju | Tilbud, Avslag, Trukket |
| Tilbud | Trukket (takket nei) |
| Ikke aktuell | Interessant |
| Avslag, Trukket, Utløpt | – |

- Hver overgang lagres i `application_events`. API-et sender lovlige neste statuser (`allowed_next`) og forrige status (`previous_status`, `from_status` i siste hendelse) på hvert kort.
- **Angre:** overgang tilbake til `previous_status` er alltid lov og sletter siste hendelse. Første hendelse (fra Ikke vurdert) angres med triage, som sletter søknadsraden.
- Ved `Søkt` settes `applied_at`, og `follow_up_at` til +14 dager hvis den ikke sendes med. Angre fra Søkt nullstiller `applied_at`.
- `next_step` og `next_step_at` er fritekst og dato ("Intervju 2. runde", "Case-oppgave"). Ingen kalenderintegrasjon.

---

## 10. Dashboard

React-SPA (Vite + TS + Tailwind/shadcn) bygget til `web/dist/` og servert av FastAPI på port 8765, med JSON-API under `/api`. Skjermer, layout for PC og mobil, API-kontrakt og frontend-bølger står i **[FRONTEND.md](FRONTEND.md)**.

Sider: Oversikt, Jobber, Jobbdetalj, Tracker, Søknadseditor, Profil, Innstillinger, Logg.

### 10.1 Bakgrunnsjobber

- Brukerinitierte operasjoner (kjør nå, utkast, research, revisjon, ny scoring, destillering) og den planlagte kjøringen blir rader i `tasks` og kjøres av en `ThreadPoolExecutor` med 2 arbeidere i `serve`-prosessen.
- Frontend poller `GET /api/tasks/{id}` hvert 2. sekund for progresjon (FRONTEND §3.3).
- Avbryt: `cancel_requested` sjekkes mellom steg, f.eks. mellom filter-batcher.
- `jobsearcher run` fra CLI finnes fortsatt for manuell kjøring. `data/run.lock` hindrer overlapp mellom CLI, planlegger og "Kjør nå".

### 10.2 Eksport

`.docx` via `python-docx` fra én mal (`src/jobsearcher/export/template.docx`):
- avsender (fra `profile.yaml`)
- dato
- mottaker (bedrift, kontaktperson hvis kjent)
- tittel ("Søknad på stilling som …")
- brevtekst (Markdown → avsnitt)

Filnavn: `Soknad_<Bedrift>_<Stilling>.docx` i `data/exports/`.

---

## 11. Planlegging og varsling

- **Planlegger:** `jobsearcher serve` starter uvicorn og APScheduler i samme prosess. Klokkeslett i `settings.yaml` (`schedule.daily_at`, standard `07:00`, tidssone `Europe/Oslo`).
  - Ved oppstart sjekkes siste vellykkede kjøring i `scrape_runs`. Er dagens kjøring tapt (maskinen var av), startes den med en gang.
  - I drift holder Docker (`restart: unless-stopped`) prosessen i live. Under utvikling går planleggeren når `serve` kjører.
  - Ingen avhengighet til Windows Task Scheduler eller cron.
- **Rekkefølge i kjøringen:** kilder → normalisering → hardfilter → filter-batcher → utløp/oppfølging → digest → backup.
- **E-postdigest** (bare hvis det er noe å melde), sendt via Gmail SMTP til brukeren selv:
  1. **Frister de neste 3 dagene** for jobber merket Interessant/Utkast
  2. Nye jobber med score ≥ 70, per jobbtype
  3. Oppfølginger som forfaller
  4. Kildehelse (f.eks. "NAV-feeden svarte 401: token utløpt?") og kostnadsvarsel
- **Gmail SMTP** sender digest til brukeren selv. Ingen IMAP — Finn-flyten går via mobil-API-et (§4.2).

---

## 12. Drift

| Område | Løsning |
|---|---|
| Logging | JSON-linjer i `data/logs/jobsearcher-YYYY-MM-DD.log`, 30 dagers rotasjon |
| Kildehelse | Per kilde og kjøring: `ok`, `warn` (0 treff der vi forventer treff, eller > 20 % parsefeil) eller `fail` (unntak, HTTP 4xx/5xx). Vises i dashboardet og digesten. |
| Agentfeil | Logges i `agent_runs`. Tre feil på rad for samme agent → varsel. |
| Migrasjoner | Alembic fra start |
| Backup | Etter hver kjøring: SQLite backup-API → `data/backups/jobsearcher-YYYY-MM-DD.db`, beholder 14. På hjemmeserveren ligger datavolumet under `infra/config/jobsearcher/`, som Pi-ens daglige Restic-backup allerede dekker. Restic tar de konsistente kopiene i `backups/`, ikke den levende DB-filen. |
| Nettverk | Utvikling: uvicorn på `127.0.0.1:8765`. Drift: uvicorn på `0.0.0.0:8765` inne i containeren, ingen publisert port på verten. Nginx Proxy Manager når `jobsearcher:8765` over `shared-network`. Cloudflare DNS `jobb.mariuskristensen.no` → Pi-ens Tailscale-IP (DNS only). |
| Distribusjon | Multi-stage `Dockerfile` (Node bygger `web/dist`, Python-image kjører appen), bygget for `linux/arm64` og `linux/amd64`. Tjenesten `jobsearcher` legges i Pi-ens `infra`-stack, likt Matflote. Volum: `config/jobsearcher/` → `/data` (DB, profil, cache, eksporter, Claude-sandbox). `GET /api/health` brukes av Docker healthcheck og Uptime Kuma. |
| Hemmeligheter | `.env`: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` (bare SMTP), `NAV_FEED_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` (drift, §8.1), valgfri `ANTHROPIC_API_KEY`. På Pi-en ligger filen i `infra/config/jobsearcher/jobsearcher.env`. Finn-HMAC-nøkkelen (`d45ff03c-b783-44d9-b94a-bb28dbc016a6`) er bakt inn i `finn_sig.py` som konstant — den finnes åpent i APK-en og trenger ingen env-variabel, men må oppdateres hvis Finn roterer den. |
| Personvern | Kontaktpersoner fra annonser slettes 90 dager etter at jobben er inaktiv, med mindre det finnes en søknad. Rå cache slettes etter 30 dager. |

---

## 13. Evaluering

- **Filter-agenten:** Brukerens egne valg i dashboardet (Interessant / Ikke aktuell) er etikettene. Det trengs ikke et eget merkesett.
  - Etter 2–3 uker eksporterer `jobsearcher eval filter` dem til `tests/evals/filter_labeled.jsonl` og måler.
  - **Mål:** ≥ 90 % av jobbene brukeren merker Interessant har score ≥ terskel (recall). Presisjonen er sekundær.
  - Brukes ved endring av prompt eller modell, og for å sammenligne backends.
- **Skrive-agenten:** Ingen automatisk eval i v1. `claims_to_verify` og brukerens antall revisjoner per brev logges som indikator.
- **Hardfilteret:** "Forkastet i dag" stikkprøves manuelt de første ukene.

---

## 14. Konfigurasjon

| Fil | Innhold | I git? |
|---|---|---|
| `config/settings.yaml` | Søk (roller, ekskluderinger, jobbtyper, senioritet, geo-modus), terskler, planlegging, LLM-backend, kostnadstak | Ja |
| `config/agents.yaml` | Kontekstmanifest, modell-tier og effort per agent | Ja |
| `config/locations.yaml` | Geo-moduser → kommuner | Ja |
| `config/sources.yaml` | Aktive kilder, Finn-søk (parametere per søk-id), Teamtailor-feeder, sideovervåkede selskaper | Ja |
| `config/tech_aliases.yaml` | Teknologisynonymer | Ja |
| `.env` | Hemmeligheter | **Nei** |

Innstillinger endret i dashboardet lagres i `settings_overrides` og overstyrer YAML.

Stier styres av miljøvariabler, så samme kode kjører på PC og i container:

| Variabel | Standard (utvikling) | Container |
|---|---|---|
| `DATA_DIR` | `data/` | `/data` |
| `PROFILE_DIR` | `context/profile/` | `/data/profile` |
| `DERIVED_DIR` | `context/derived/` | `/data/derived` |

---

## 15. Filhierarki

```
JobSearcher/
├── README.md
├── AGENTS.md                          Regler for AI-agenter, inkl. vedlikehold av dokumentasjon
├── CLAUDE.md                          Importerer AGENTS.md (for Claude Code)
├── .claude/
│   ├── settings.json                  Prosjekt-hooks
│   └── hooks/docs_check.py            Stop-hook: krever oppdatert HANDOVER når kode er endret
├── pyproject.toml                     uv, CLI-entrypoint `jobsearcher`
├── uv.lock, .python-version           Låste Python-avhengigheter, Python 3.12
├── .env.example
├── .gitignore
├── alembic.ini
├── Dockerfile                         Multi-stage: Node bygger web/dist, Python kjører appen
├── docker-compose.yml                 Lokal kjøring i container; Pi-en bruker sin infra-stack
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── FRONTEND.md                    UI-design, API-kontrakt, frontend-bølger
│   ├── HANDOVER.md                    Status og neste steg for neste agent
│   └── spikes/                        01-nav-feed, 02-claude-subscription, 03-trainee-sources, 04-finn-mobile-api
│
├── config/
│   ├── settings.yaml
│   ├── agents.yaml
│   ├── locations.yaml
│   ├── sources.yaml
│   └── tech_aliases.yaml
│
├── context/
│   ├── README.md
│   ├── profile/                       gitignored, bare _template.md versjoneres
│   ├── derived/                       gitignored
│   └── prompts/
│       ├── filter.md
│       ├── researcher.md
│       ├── writer.md
│       ├── reviser.md
│       ├── distiller.md
│       └── extractor.md
│
├── src/jobsearcher/
│   ├── cli.py                         run | serve | distill | rescore | eval | init-db | backup (bare `serve` finnes ennå)
│   ├── config.py
│   ├── scheduler.py                   APScheduler i serve, innhenting av tapt kjøring
│   ├── api/           schemas.py      API-kontrakten (Pydantic), kilde for OpenAPI og TS-typer
│   ├── logging.py
│   ├── db/            models.py, session.py, repo.py, migrations/
│   ├── sources/
│   │   ├── base.py
│   │   ├── http.py
│   │   ├── finn_api.py                Finn: signert søk → RawJob, så annonsetekst fra JSON-LD på annonsesiden
│   │   ├── finn_sig.py                HMAC-SHA512-signering, egen impl. (se spike 04)
│   │   ├── nav_feed.py
│   │   ├── teamtailor.py
│   │   ├── page_watch.py
│   │   └── manual.py                  import av limt inn annonsetekst
│   ├── pipeline/      run.py, normalize.py, clean.py, dedupe.py, hardfilter.py, lifecycle.py, lock.py
│   ├── context/       loader.py, slices.py, builder.py, budget.py, projects.py
│   ├── agents/        base.py, schemas.py, filter.py, researcher.py, writer.py, reviser.py,
│   │                  distiller.py, extractor.py
│   │   (ingen enricher — Finn-annonsesiden gir full annonsetekst)
│   ├── llm/           base.py, claude_code.py, anthropic_api.py, mock.py, costs.py
│   ├── tracking/      status.py
│   ├── notify/        email.py, templates/digest.html
│   ├── export/        docx.py, template.docx
│   └── web/
│       ├── app.py, tasks.py           FastAPI-app, /api-rutere, serverer web/dist
│       ├── errors.py                  Feilformat `{detail, code}`, 501 for ruter uten backend
│       └── routes/    overview.py, jobs.py, applications.py, drafts.py, profile.py,
│                      settings.py, logs.py, tasks.py
│
├── web/                               Frontend (FRONTEND.md)
│   ├── package.json, vite.config.ts, tsconfig*.json, components.json, playwright.config.ts
│   ├── .env.mock                      VITE_MOCK=1 for `npm run dev:mock`
│   ├── openapi.json                   Eksportert kontrakt, versjonert
│   ├── public/                        manifest.webmanifest, ikoner, mockServiceWorker.js (MSW)
│   ├── src/
│   │   ├── api/                       schema.d.ts (generert), types.ts, client.ts, queries.ts
│   │   ├── components/ui/             shadcn-komponenter
│   │   ├── components/                AppShell, badges (score/frist/status), tasks (indikator, Kjør nå), Toaster, Sheet, Markdown
│   │   ├── features/                  overview/, jobs/, tracker/, editor/, profile/, settings/, logs/, more/
│   │   │                              (placeholders.tsx holder skjermene som ikke er bygget ennå)
│   │   ├── mocks/                     MSW: handlers.ts, db.ts, browser.ts, fixtures/*.ts (oppdiktet)
│   │   ├── test/                      Vitest-oppsett
│   │   ├── routes.tsx, main.tsx
│   │   └── lib/                       format (dato, frist), status, tema, useMediaQuery
│   ├── e2e/                           Playwright (390×844 og 1440×900)
│   └── dist/                          gitignored, bygget
│
├── data/                              gitignored (DATA_DIR)
│   ├── jobsearcher.db
│   ├── backups/  cache/  companies/  exports/  logs/  llm_sandbox/
│   └── run.lock
│
├── scripts/
│   └── export_openapi.py              Skriver web/openapi.json fra FastAPI-appen
│
└── tests/
    ├── fixtures/                      Finn-varsel-e-post, NAV-feedside og -annonse, Teamtailor-RSS, eksempelprofil
    ├── test_api_contract.py           501-ruter, feilformat, web/openapi.json er oppdatert
    ├── test_finn_api.py
    ├── test_finn_sig.py
    ├── test_nav_feed.py
    ├── test_teamtailor.py
    ├── test_clean.py
    ├── test_dedupe.py
    ├── test_hardfilter.py
    ├── test_context_builder.py
    ├── test_projects.py
    ├── test_status_transitions.py
    └── evals/
```

---

## 16. Teknologi

| Behov | Bibliotek |
|---|---|
| Pakker og miljø | `uv` |
| Web (backend) | `fastapi`, `uvicorn` |
| Web (frontend) | Vite, React, TypeScript, Tailwind CSS, shadcn/ui, React Router, TanStack Query, `openapi-fetch` + `openapi-typescript`, MSW, `@dnd-kit`, `react-markdown`, `date-fns`. Detaljer i FRONTEND.md. |
| Planlegging | `apscheduler` |
| Container | Docker, multi-stage, `linux/arm64` + `linux/amd64` |
| DB | `sqlmodel`, `alembic` |
| Konfig | `pydantic-settings`, `pyyaml`, `python-frontmatter` |
| HTTP og parsing | `httpx`, `selectolax`, `markdownify`, `feedparser` |
| Finn-signering | Egen impl. i `finn_sig.py` (bruker `hmac` + `hashlib` fra stdlib, se spike 04 §Signering) |
| E-post | `smtplib` + `email` (stdlib). Ingen IMAP. |
| Fuzzy-match | `rapidfuzz` |
| LLM | Claude Code CLI (`claude -p`), `anthropic` |
| CLI | `typer` |
| Eksport | `python-docx` |
| Test | `pytest`, `respx`; frontend: Vitest, Testing Library, Playwright |

---

## 17. Veikart

**Frontend først.** Hele UI-et (bølgene F0–F4 i [FRONTEND.md §8](FRONTEND.md)) bygges mot API-kontrakten og mock-data og brukes av brukeren på PC og mobil før backend bygges. Det som oppdages ved bruk (skjermer, felt, flyt) rettes i kontrakten og i dette dokumentet mens det er billig. Backend-fasene bygger deretter mot en kontrakt som er prøvd i praksis, og hver fase kobler de bølgene den eier til ekte data.

Mock-data kan ikke vise kvaliteten på LLM-output (score, brev). Den vurderes når fase 2 og 3 kobles til.

| Fase | Innhold | Ferdig når |
|---|---|---|
| ~~0. Spikes~~ | Finn, NAV, Claude-abonnement, trainee-kilder | ✅ `docs/spikes/` |
| ~~0b. Finn-sjekk~~ | Verifiser HMAC-signeringen og lagre filter-metadata som fixture. Ingen appkode. | ✅ 2026-10-10, spike 04 §Oppdatering |
| **F0–F4. Frontend mot mock** (F0 ✅, F1 ✅, F2 ✅ 2026-10-10) | Bølgene i FRONTEND §8, med en brukertest etter F1 og etter F4. Funn rettes i FRONTEND, kontrakten (`api/schemas.py`) og her. | Brukeren har brukt hele flyten i mock-modus og godkjent kontrakten |
| **1. Fundament** | Repo-oppsett, config med `DATA_DIR`/`PROFILE_DIR`, DB + Alembic, HTTP-lag, NAV-kilde, Finn-API-kilde (`finn_api.py` + `finn_sig.py`, se spike 04), normalisering, dedupe, hardfilter, `jobsearcher run` uten LLM, `serve` med de første ekte endepunktene. Ingen Windows-spesifikk kode. | Daglig kjøring fyller DB med filtrerte jobber, og dashboardet viser dem |
| **2. Scoring + API v1** | LLM-backends, destiller, filter i batch, `/api` for oversikt, jobber, jobbdetalj, triage og tasks. Kobler F1. | Rangerte jobber med frister i dashboardet |
| **3. Søknader** | Research, writer, revisjon, versjoner, `.docx`-eksport, `/api` for utkast. Kobler F3. | Brev kan lages, itereres og lastes ned |
| **4. Tracking + varsling** | Statusflyt, oppfølging, e-postdigest, planlegger i `serve`, backup, profil-API. Kobler F2 og F4. | Hele flyten går uten manuelt arbeid |
| **4b. Hjemmeserver** | Dockerfile (arm64), tjeneste i Pi-ens `infra`-stack, NPM-proxy, DNS, `claude setup-token`, flytte profil og DB til volumet, healthcheck i Uptime Kuma | Appen kjører på Pi-en og brukes fra mobil via Tailscale |
| **5. Flere kilder** | Teamtailor, sideovervåker + extractor, kuratert selskapsliste | Trainee-programmer fanges opp |
| **6. Polering** | Filter-eval, kostnadsside | Recall ≥ 90 % |

F5 (drift i container) gjøres sammen med fase 4b.

---

## 18. Brukerens oppgaver før/under fase 1

- [x] Installere Claude Code CLI og logge inn (verifisert: v2.1.296, `claude -p` fungerer)
- [x] Laste ned Finns Android-APK og dekompilere den (slettet etterpå; funnene står i spike 04)
- [x] Lage Gmail-app-passord → `.env` (brukes nå bare til SMTP-digest)
- [ ] Bestille privat token for NAV-feeden (e-post til nav.team.arbeidsplassen@nav.no)
- [x] Gå gjennom selskapslisten i spike 03
- [x] Fylle ut kontekstprofilen

Finns lagrede søk og Gmail-etiketten `JobSearcher/Finn` trengs ikke lenger — de kan slettes.

**Før fase 4b (hjemmeserver):**
- [x] Cloudflare: A-post `jobb.mariuskristensen.no` → `100.107.14.101`, DNS only
- [x] Nginx Proxy Manager: proxy host `jobb.mariuskristensen.no` → `http://jobsearcher:8765`, med sertifikat
- [x] Kjøre `claude setup-token` og legge tokenet i Pi-ens `jobsearcher.env`
- [ ] Oppdatere runbooken for hjemmeserveren med den nye tjenesten

---

## 19. Åpne spørsmål og risiko

| #   | Spørsmål / risiko                                                                                                                           | Håndtering                                                                                                                                                                                                               |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Finn-API-et er en gråsone.** Finns ToS forbyr automatisert innhenting uten skriftlig samtykke. Mobil-API-et er uoffisielt for tredjepart. | Bevisst risiko. Privat, lokal, lavvolum (1 bruker, ~5 søk per døgn, annonsesiden bare for nye jobber). Realistiske headere og rate-limit. Verktøyet publiseres ikke. Detaljer i spike 04.                                                                  |
| 2   | **Finn-signaturen eller endepunktene brytes** (nøkkelrotasjon, format- eller endepunktsendring, deteksjon).                                 | Pin appversjon (`261006-ec709768`) fra APK-en i `User-Agent`. Oppdater `finn_sig.py` eller dekompiler ny APK ved behov. Kildehelse (§12) oppdager 401/403 raskt. Manuell innliming (`manual`-kilden) som siste fallback. |
| 3   | Anthropic kan endre vilkår eller fakturering for `claude -p`                                                                                | `anthropic_api` er klar som alternativ. Byttet er én linje i config.                                                                                                                                                     |
| 4   | Strengt senioritetsfilter kan gå glipp av gode stillinger                                                                                   | Stillinger uten oppgitt senioritet vises med maks score 65. Hardfilteret følges opp via "Forkastet i dag".                                                                                                               |
| 5   | NAV-token roterer eller utløper                                                                                                             | Privat token, og kildehelsevarsel ved 401                                                                                                                                                                                |
| 6   | Karrieresider endrer struktur og gir støy i sideovervåkeren                                                                                 | Hash av hovedinnhold med CSS-selektor, og LLM-uttrekk bare ved endring                                                                                                                                                   |
| 7   | Skrive-agenten finner på fakta                                                                                                              | Faktaregel og `claims_to_verify` i editoren                                                                                                                                                                              |
| 8   | `claude -p` i container på arm64: innlogging med `CLAUDE_CODE_OAUTH_TOKEN`, isolasjonsflaggene og tokenets levetid er ikke verifisert       | Verifiseres først i fase 4b. Faller det, brukes `anthropic_api` på Pi-en.                                                                                                                                                |
| 9   | Profilen finnes bare i Pi-ens datavolum i drift. Restic-repoet ligger på samme disk som dataene (runbook §10).                              | `profile_revisions` gir historikk. Mulighet for eksport av profilen fra dashboardet. Følger Pi-ens plan for backup til ekstern disk.                                                                                     |
| 10  | Frontend og backend glir fra hverandre mens frontend bygges mot mock                                                                        | Kontrakten er Pydantic-modellene; TS-typer genereres og fixtures typesjekkes (FRONTEND §3.1)                                                                                                                             |
