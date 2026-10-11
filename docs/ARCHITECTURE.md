# JobSearcher: design- og arkitekturdokument

> Status: v0.20 (2026-10-11). Fase 0 og 0b (Finn-sjekk) er gjennomført, se `docs/spikes/`. Frontend-bølgene F0–F3, backend-fase 1–3 og bølge 2b/F2b er ferdige: Finn hentes, filtreres og scores (NAV-kilden er bygget, men ikke kjørt live ennå, §19 #11), dashboardets oversikt, jobbliste, tracker og søknadseditor går mot ekte data, og alle LLM-kall går til DeepSeek via `openrouter`. Søknadsutkast er ikke prøvd live med DeepSeek ennå. Neste: F4.
> Dokumentet er "source of truth" for designet. UI-designet står i [FRONTEND.md](FRONTEND.md). Regler for vedlikehold står i `AGENTS.md`.

## Endringslogg

| Versjon | Dato       | Endring                                                                                                                                                                                                                                                                           |
| ------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v0.20   | 2026-10-11 | «Lagre som stilregel»: revisoren foreslår en stilregel (`RevisionResult.style_rule`, §7.2) når chatmeldingen er en generell preferanse, og brukeren lagrer den med én knapp i `style_overrides.md` (§6.1, §7.4). Forslaget lagres på chatmeldingen (migrasjon `0005`, §9). Faktaregelen strammet inn (§7.4): påstander uten dekning i profilen skal ikke stå i brevet, heller ikke oppdiktede koblinger mellom teknologi og prosjekt; `claims_to_verify` er for dekkede, men kanskje for sterke formuleringer. Grunn: første live brev med DeepSeek koblet Azure fra annonsen til hjemmeserveren, og var 325 ord. Prompt `writer` v0.3, `reviser` v0.5. |
| v0.19   | 2026-10-11 | Fase 3 bygget: research-, skrive- og revisjonsagentene, bitene for fase 3 (§6.2), prosjektvalg (§6.4), utkast-API og `.docx`-eksport. Presisert etter implementering: research bruker OpenRouters web-plugin, bare `full`-notater caches og et mislykket søk gir et `limited`-notat fra annonsen (§7.3); skriveren oppretter søknaden først når utkastet finnes (§7.4); utkast og revisjon avvises ved kostnadstaket i stedet for å be om bekreftelse (§8.3); eksporten bruker ingen mal og lagrer ikke fil (§10.2). Prompt `reviser` v0.3, `researcher` v0.2. |
| v0.18   | 2026-10-11 | Revisjonschatten skiller spørsmål fra endringer: revisoren svarer i chatten uten ny versjon når meldingen er et spørsmål (`RevisionResult.kind`, §7.2; prompt `reviser` v0.2). Chatten lagres i ny tabell `draft_messages` (migrasjon `0004`, §9). Grunn: i brukertesten av F3 ble et spørsmål om en påstand limt inn i brevet. |
| v0.17   | 2026-10-11 | F3 bygget mot mock (FRONTEND §5.5, §17). Utkastregler presisert (§9.1): et utkast flytter Interessant → Utkast og oppretter søknaden for en jobb som ikke er vurdert; autosave oppdaterer en brukerversjon yngre enn 10 min på plass i stedet for å lage en ny; brukerversjoner arver `claims_to_verify` fra versjonen de bygger på. Tracker-kortet har nyeste utkast. |
| v0.16   | 2026-10-11 | Én modell for alle agenter: `openrouter` (DeepSeek V4.1 Flash) er standard-backend, og reserven er av som standard (§2, §8). Grunn: scorer og senere søknadsutkast skal være sammenlignbare, og DeepSeek scorer på en annen skala enn Claude (spike 05). `claude_code` finnes fortsatt og kan settes som standard eller reserve. Filter-prompten v0.3 har en strengere skala, så snittet treffer den gamle (terskler som 65 og 70 beholder betydningen). Ny CLI-kommando `jobsearcher rescore [--all]` (§5.5). |
| v0.15   | 2026-10-11 | Kostnadstaket gjelder bare betalte kall (§2, §8.3): `claude_code`-estimatet teller ikke, siden abonnementet betaler. Taket er senket fra $25 til $10/mnd. Nås det, stopper reserven, men `claude_code` scorer videre. Saldoen fra OpenRouter har også totalt forbruk (`used_usd`), så forskjellen mot appens egne tall kan forklares. |
| v0.14   | 2026-10-11 | Bølge 2b bygget. Presisert etter implementering (§8.1): hvilke feil som gir bytte til reserven, en bryter som sender alle kall til reserven i 30 min etter en backendfeil, egen `llm.openrouter.timeout_s`, og saldo uten `usage_monthly`. `anthropic_api` og `anthropic`-pakken er fjernet (§2, §15). Migrasjon `0003` (§9). |
| v0.13   | 2026-10-11 | LLM-reserve: `anthropic_api` erstattes av en ny backend `openrouter` med DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash`). `claude_code` er fortsatt standard; feiler et kall på grunn av backenden (CLI mangler, innlogging, bruksgrense, tidsavbrudd), kjøres det på nytt med `openrouter` (§2, §8.1). Ny kolonne `agent_runs.fallback_from` (§9). Nytt API `GET /api/llm/usage` og et forbrukskort i dashboardet med tokens, kostnad og saldo hos OpenRouter. Bygges i bølge 2b før F3 (§17). Bakgrunn og priser: spike 05. |
| v0.12   | 2026-10-10 | Hensyn til Finn (§4.2 punkt 8): annonsesider hentes som appens WebView (ikke `python-httpx`), tilfeldig avstand per vert (søk 2–4 s, annonsesider 5–10 s), maks 40 annonsesider per kjøring, stopp ved 403/429, 404/410 gjør jobben inaktiv, nye forsøk etter 1, 3 og 7 dager (nye kolonner i `job_sources`, §9), 3 timers pause mellom Finn-hentinger (`run --force` overstyrer), filter-metadata caches i 7 dager. `it_oslo` er fjernet (delmengde av `it_norge`), og typesøkene kjøres ukentlig. Planlagt kjøring starter 0–40 min etter `daily_at` (§11). Appheaderne har enhetsinfo og `Ab-Test-Device-Id`. Bakgrunn: gjennomgang i spike 04 §Oppdatering "Hensyn til Finn". |
| v0.11   | 2026-10-10 | Veikartet (§17): backend-fase 1 og 2 går foran F3 og F4, så de prøvde skjermene får ekte data nå. Fase 1 og 2 er bygget; tracker-API og planlegger er trukket frem fra fase 4. Presisert etter implementering: kildegrensesnitt og cursorer (§4.1), NAV i to steg med tittelregel før detaljhenting (§4.3, §5.1), dedupe-score og repost (§4.5), hva filter-agenten scorer og fyller inn (§5.2), profilhash (§6.1), verifiserte `claude -p`-flagg (§8.1), nye kolonner (§9), planlegger (§11), filhierarki (§15). |
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

Et frittstående Python-program som kjører på brukerens egen maskin (PC under utvikling, hjemmeserver i drift) og automatiserer jobbsøkingen for en utviklerstudent i Nittedal som fullfører bacheloren i juni 2027 (deltid før det, fulltid fra juni):

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
| LLM | Én modell for alle agenter: DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash`) via OpenRouter, backend `openrouter`, så scorer og utkast er sammenlignbare. Ingen reserve som standard; feiler et kall, prøves jobben igjen ved neste kjøring. `claude_code` (abonnement via `claude -p`) finnes og kan settes som standard eller reserve i config (§8.1, spike 05). `anthropic_api` er fjernet (bølge 2b). |
| Finn | Mobil-API på `https://appsgw.finn.no/` med HMAC-SHA512-signering (egen implementasjon fra spike 04 §Signering, verifisert i fase 0b) for søk. Annonsetekst fra `JobPosting` JSON-LD på den offentlige annonsesiden, bare for nye jobber etter hardfilteret. Søk defineres i `config/sources.yaml`. Endepunkter er reverse-engineert fra Android-APK (v`261006-ec709768`). Se spike 04. |
| NAV | pam-stilling-feed med privat token |
| Trainee/graduate | NAV + Teamtailor-RSS + kuratert selskapsliste med sideovervåker |
| Volum | 10–20 søknader per uke |
| Senioritet | Bare junior, trainee, graduate, nyutdannet, internship og sommerjobb. Krav om 1+ års erfaring forkastes. |
| Geografi | Per jobbtype: fast stilling i `oslo_omegn` (Oslo med nærområder, inkl. Nittedal). Trainee, graduate og sommerjobb i hele `norge`. `nittedal` finnes som alternativ. |
| Kildetillit | Finn-API-kall sendes med `experience`- og `education`-filtre (ingen erfaring/junior, ingen/bachelor) og regnes som forhåndsfiltrert. Andre kilder filtreres med strengmatching + LLM. |
| Søknad | Ett vanlig søknadsbrev per stilling. Eksport til `.docx`. |
| Tracking | Søknadsfrist er viktigst. Kontaktpersoner og nøkkelinfo lagres når de finnes. |
| Kostnad | Tak $10/mnd for betalte kall (OpenRouter); `claude_code` teller ikke, siden abonnementet betaler. E-postvarsel ved score ≥ 70. |
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
class JobSource(Protocol):                       # sources/base.py
    name: SourceName
    def collect(self, state: dict[str, CursorState]) -> CollectResult: ...
    # CollectResult: jobs: list[RawJob], state (ny cursor per nøkkel), found, errors, health, message
    def fetch_details(self, jobs: list[RawJob]) -> list[RawJob]: ...
    # Fyller annonsetekst for jobber med needs_detail, bare nye jobber som har passert hardfilteret
```

- Hver kilde lagrer sine egne cursorer i `source_state`, én per nøkkel (Finn-API: høyeste `published` per søk-id, NAV: neste feed-URL + ETag). Nye cursorer lagres bare når kilden ikke feilet (`health != fail`).
- `sources/registry.py` bygger kildene fra `enabled` i `sources.yaml`. Kildene kjøres i rekkefølgen NAV, Finn, så NAV blir primærkilde ved sammenslåing.
- Kildene returnerer `RawJob` med så mange strukturerte felt som kilden har. Felles normalisering tar resten.
- Felles HTTP-lag (`sources/http.py`):
  - rate-limiting per domene
  - retry med backoff
  - `If-None-Match` og `If-Modified-Since`
  - respekt for `robots.txt` (forespørselen etter `robots.txt` sendes med kallerens headere)
  - rå respons lagres i `data/cache/<kilde>/<dato>/`
  - avstand mellom kall per vert, fast eller tilfeldig i `[min, maks]`. Kildene setter avstanden for sine egne verter (`HttpClient.set_interval`); standard er 1 s. Finn: se §4.2 punkt 8.

### 4.2 Finn via mobil-API (spike 04)

Finn har ikke et offisielt tredjeparts-API, men mobilappen snakker med et HMAC-signert HTTP-API på `https://appsgw.finn.no/` som kan brukes direkte. Endepunktene og signeringsregelen er reverse-engineert fra Android-APK-en (`FINN.no_*.apk`, i prosjektrot, gitignored). Forespørsler signeres med `FINN-GW-KEY`-headeren (HMAC-SHA512 → base64) — vi implementerer signeringen selv i `finn_sig.py` (se spike 04 §Signering). Dette er en bevisst gråsone — risikoen og tiltakene står i spike 04.

1. **Søk defineres i `config/sources.yaml`**, ikke i Finns UI. Hvert søk setter Finns egne filtre som API-parametere:
   - *Utdanning (`education`):* ingen utdanning (`465`), høyskole/universitet lavere nivå (`464`)
   - *Arbeidserfaring (`work_experience`):* ingen erfaring (`455`), junior (`456`)

   | Søk-id | `searchkey` | Ekstra filter | Geografi | Hvor ofte |
   |---|---|---|---|---|
   | `it_norge` | `SEARCH_ID_JOB_FULLTIME` | — | `norge` | hver kjøring |
   | `trainee` | `SEARCH_ID_JOB_FULLTIME` | `job_duration=8098` (trainee) | `norge` | ukentlig |
   | `graduate` | `SEARCH_ID_JOB_FULLTIME` | `q=graduate` | `norge` | ukentlig |
   | `summer` | `SEARCH_ID_JOB_FULLTIME` | `job_duration=1816` (sommer/sesong) | `norge` | ukentlig |

   Oslo/Akershus har ikke eget søk: `it_norge` dekker dem, og geografien avgjøres lokalt (§5.1). Typesøkene er delmengder av `it_norge` og gir bare jobbtype-hint (§5.4). Tittelregelen fanger de fleste typene samme dag, så ukentlig (`every_days: 7`) holder.

   Alle går mot `GET /search/{searchkey}?client=android-finn&sort=PUBLISHED_DESC&<filtre>` med `FINN-GW-Service: Search-Quest-JB`. Filter-ID-ene (`occupation`, `location`, `work_experience`, `education`, `job_duration`) står i spike 04 §Oppdatering og i fixtures `tests/fixtures/finn/filters_*.json`. De ligger i `config/sources.yaml` og sjekkes mot Finns filter-metadata (`include_results=false&include_filters=true`, cachet i `DATA_DIR/finn_filters.json` i `filter_check_days`, standard 7). Ukjente ID-er gir en kildehelse-advarsel (§12).
2. **`FinnApiSource`** gjør to steg:
   - **Søk:** `GET /search/{searchkey}?client=android-finn&<filtre>&page=N` (signert) → 50 annonser per side med Finn-kode, tittel, stillingstittel, bedrift, sted, publisert, frist, antall stillinger og erfaring/utdanning-ID-er. **Ingen annonsetekst.** Samme Finn-kode fra flere søk blir én jobb.
   - **Detalj:** for nye jobber som har passert hardfilteret (§5.1) hentes `https://www.finn.no/job/ad/{finnkode}` (vanlig GET, ingen HMAC), og `JobPosting` fra JSON-LD-blokken gir annonsetekst (`description`, HTML), arbeidsgiver, sted og frist. Det er samme side som appens WebView viser. Bare nye jobber hentes, så volumet er lavt (typisk 10–30 per døgn). Feiler detaljhentingen, beholdes jobben med `ad_text_status = missing` og prøves igjen senere (punkt 5).
3. **Cursor** per søk-id lagres i `source_state` som høyeste sette `published` (ms). Med `sort=PUBLISHED_DESC` blas det side for side til en annonse er eldre enn cursoren. Finn gir maks 50 sider, så søkene må være filtrert. Rate-limit og retry håndteres av det felles HTTP-laget (§4.1).
4. **Finn-annonser er forhåndsfiltrert og regnes som gyldige.** API-kallet filtrerer serverside på erfaring og utdanning, så de slipper senioritetsfilteret (§5.1) og blir aldri skjult på grunn av senioritet. Står det likevel et eksplisitt erfaringskrav i teksten, legges det inn som en `concern`, men jobben vises. Rolle-ekskludering (f.eks. cybersikkerhet) og geografi gjelder fortsatt.
5. Jobben opprettes med `prefiltered = true` og `ad_text_status = present` når detaljhentingen lyktes. Ingen LLM-berikelse trengs. Søknadslenken står ikke i JSON-LD, men i annonsesidens søk-knapp (`/job-apply/{id}/apply`, Finns videresending). Mangler teksten, prøves detaljhentingen igjen etter 1, 3 og 7 dager (`job_sources.detail_attempts`/`detail_next_at`, §9), så gis den opp. Maks 30 slike forsøk per kjøring, bare jobber fra de siste 14 dagene. Svarer annonsesiden 404/410, er annonsen borte: jobben blir inaktiv og hentes ikke igjen. Kildehelsen er `warn` så lenge noen mangler tekst.
   - `work_locations` er `[land, fylke, kommune, sted]`; i Oslo er tredje ledd en bydel, så kommunen settes til Oslo.
   - Finn-overskriften (`heading`) er ofte reklametekst. Stillingstittelen (`job_title`) lagres i `meta` og brukes også ved fuzzy-match mot andre kilder (§4.5).
   - Første kjøring per søk henter maks `initial_max_pages` sider, senere maks `max_pages`. Filter-ID-ene sjekkes mot cachede filter-metadata (`validate_filters`, `filter_check_days`).
6. **App-identitet:** `User-Agent`, `x-nmp-app-version-name` og tilhørende headere låses til appversjon `261006-ec709768` (fra APK-en), slik at endepunkter ikke flyter mellom versjoner. Én enhet, lagret i `DATA_DIR/finn_device.json` som en app-installasjon: installasjons-/visitor-ID og `Ab-Test-Device-Id` (UUID-er), og enhetsinfo fra `sources.yaml` (`os_version`, `device_model`) i `x-nmp-os-version`/`x-nmp-device`. Ny `Session-Id` per kjøring. Annonsesidene hentes som appens WebView ville åpnet dem: Android WebView-`User-Agent` for samme enhet (`; wv`), `X-Requested-With: no.finn.android`, vanlige `Accept`/`Accept-Language`/`Sec-Fetch-*`-headere. Formatet på appens egen `User-Agent` og WebView-versjonen er ikke verifisert mot en ekte enhet (§19 #12).
7. **Fallback om API-et blir ubrukelig** (signaturen brytes, endepunkt forsvinner): brukeren limer inn annonsetekst via `manual`-kilden (§4.1 / §9 `job_sources.source`). IMAP-flyten er ikke en lett vei tilbake.
8. **Hensyn til Finn.** Målet er at trafikken er liten og ser ut som én vanlig appbruker. Typisk døgn: 1–4 søkekall, 10–30 annonsesider, én `robots.txt`.

   | Tiltak | Verdi (`sources.yaml` → `finn_api`) |
   |---|---|
   | Tilfeldig avstand mellom søkekall | `gateway_interval_s: [2, 4]` |
   | Tilfeldig avstand mellom annonsesider | `ad_page_interval_s: [5, 10]` |
   | Maks annonsesider per kjøring (resten neste kjøring) | `max_details_per_run: 40` |
   | Pause mellom Finn-hentinger: hentet Finn for under så mange timer siden, hoppes kilden over (ingen kall, ingen kjøringsrad). `jobsearcher run --force` overstyrer. | `min_hours_between_runs: 3` |
   | Filter-metadata caches | `filter_check_days: 7` |
   | Søk som bare gir hint kjøres sjeldnere | `every_days` per søk |
   | Planlagt start varierer (§11) | `settings.yaml` → `schedule.jitter_minutes: 40` |

   Ingen parallelle kall. Søk: 429 eller 401/403 stopper alle gjenstående søk i kjøringen (5xx prøves på nytt med backoff i HTTP-laget). Annonsesider: ingen automatiske nye forsøk; 403/429 stopper resten av annonsesidene i kjøringen og gir kildehelse `warn`.

### 4.3 NAV pam-stilling-feed (spike 01)

- Hendelsesfeed (`GET /api/v1/feed`, `/feed/{side}`, `/feedentry/{uuid}`). Cursor (`source_state` nøkkel `feed`): neste side-URL, eller siste side + `ETag` når feeden er lest ut. Neste kjøring spør siste side med `If-None-Match`; `304` betyr ingenting nytt.
- Første kjøring: `If-Modified-Since` 7 dager tilbake (`initial_days_back`; 30 dager ga 504 fra NAV-gatewayen). Maks `max_pages_per_run` (200) sider per kjøring; resten tas neste kjøring.
- Inneholder ca. 1000 nye annonser per dag fra hele landet, uten filtrering på serversiden. Hardfilteret (§5.1) tar bort det meste før LLM.
- **To steg, som Finn:** feed-elementene er sammendrag (uuid, status, tittel, arbeidsgiver, kommune). `collect` gir `RawJob` med `needs_detail = true`, og `fetch_details` henter hele annonsen fra `feedentry` bare for nye jobber som har passert hardfilteret. Før detaljhenting har filteret bare tittel, arbeidsgiver og kommune; derfor tittelregelen `title_not_it` (§5.1).
- Strukturerte felt fra annonsen brukes direkte: kommune, fylke, frist (dato eller fritekst som "Snarest"), kontakter, arbeidsgiver og orgnr, ansettelsesform, yrkeskategori (nivå 1 og 2), søknads-URL (ellers `sourceurl`).
- NAV-gatewayen er treg (13–60 s per feed-side, spike 01 §Oppdatering). Kallene har eget tidsavbrudd (`timeout_s`, 90 s) og ingen nye forsøk ved 5xx (`retries: 0`): feiler NAV, står cursoren urørt og neste kjøring prøver igjen.
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
  | 2 | Samme normaliserte `application_url` (uten query/fragment, uten `www.`), bare når URL-en peker på én annonse (ikke `/jobs`, `/karriere` eller bare domenet), og samme bedrift eller tittelscore ≥ loggterskelen | NAV og Finn lenker ofte til samme ATS-side (Teamtailor, Webcruiter) som vi også henter direkte |
  | 3 | Samme bedrift + tittelscore ≥ 90 + overlappende sted (eller ett av stedene mangler) | Fanger annonser med ulik URL. Bedrift = `org_number` når kilden har det (NAV), ellers normalisert navn. |

  Tittelscore = snitt av rapidfuzz `token_set_ratio` og `token_sort_ratio`, beste par av overskrift og kildens stillingstittel (Finn `job_title`). `token_set_ratio` alene gir 100 når ett sett ord er delmengde av det andre ("Utvikler" vs. "Senior utvikler").

  Kilden med mest strukturert data blir primær (NAV > Finn-API > ATS > sideovervåker). Usikre treff (score 80–89 på #3) slås ikke sammen, men logges, så terskelen kan justeres etter noen uker i drift.
- **Repost:** Samme fingerprint som en inaktiv jobb, eller treff fra en annen kilde mot en jobb eldre enn `repost_after_days` (30, regnet fra `published_at`, ellers `first_seen`) → ny `Job` med `reposted_from_id`, og den gamle settes inaktiv. Samme kilde + kilde-ID er aldri repost; da oppdateres (eller reaktiveres) jobben. Jobben merkes "lagt ut på nytt", og tidligere status og søknad vises.
- **Oppdatering:** en annonse som hentes på nytt oppdaterer `last_seen` og endrede felt. `content_hash` regnes av hele den rensede teksten før boilerplate-kutt (§4.6) og nøkkelfelt, så bare reelle endringer gir ny scoring.
- **Frist:** lagres som `deadline` (dato) og/eller `deadline_text` ("snarest", "fortløpende"). Kildens strukturerte felt har forrang. Ellers trekker filteret ut fristen.

### 4.6 Rensing av annonsetekst

- HTML → Markdown (selectolax `LexborHTMLParser` + markdownify). Skript, navigasjon og "Del annonsen"-tekst fjernes. `description_clean` lagrer teksten med kortet boilerplate.
- Felles boilerplate fra samme arbeidsgiver (f.eks. "Om oss" som går igjen) kortes ned etter at den er sett i ≥ 3 annonser.
- Hvis `job_ad` overskrider budsjettet (2500 tokens, `pipeline.clean.truncate_for_budget`): behold tittel og innledning, prioriter avsnitt med nøkkelord som "kvalifikasjoner", "krav", "arbeidsoppgaver", "vi tilbyr" og "søknad", og kutt resten med en markør.

---

## 5. Filtrering og rangering

### 5.1 Steg 1: regelbasert hardfilter (gratis)

Konfigurert i `config/settings.yaml`. Kildene har to tillitsnivåer:

| Tillit | Kilder | Behandling |
|---|---|---|
| **Forhåndsfiltrert** | Finn-API (serverside-filtre for erfaring og utdanning) | Bare geografi og rolle-ekskludering. Antas å passe på nivå. |
| **Ufiltrert** | NAV, Teamtailor, sideovervåker | Alle regler under, med strengmatching som første ledd og LLM som andre |

Forkaster hvis:

- **Geografi:** kommunen er utenfor modusen for jobbtypen (§5.3), eller stillingen er i utlandet. Remote med norsk arbeidsgiver slipper gjennom (`allow_remote_norway`).
- **Jobbtype:** typen er slått av i `search.job_types`.
- **Tittel** (bare ufiltrerte kilder uten yrkeskategori, dvs. NAV før detaljhenting): tittelen inneholder ingen av ordene i `search.title_require_any` (IT-ord og trainee/graduate/sommer/intern). Regelen `title_not_it` er svakest og logges bare når ingen annen regel slo til. Etter detaljhenting gjelder yrkeskategorien i stedet.
- **Rolle:** tittel eller kategori treffer et ekskluderingsord (`sikkerhet`, `security`, `SOC`, `pentest`, `cyber`, …), eller yrkeskategorien er klart ikke-IT (ukjent kategori beholdes). Ord på ≤ 3 tegn matcher hele ord; lengre ord matcher som delstreng, så sammensetninger som "informasjonssikkerhet" fanges. En unntaksliste i koden hindrer falske treff ("Cybernetics").
- **Senioritet** (bare ufiltrerte kilder), med strengt filter:
  - tittelen inneholder `senior`, `lead`, `principal`, `arkitekt`, `leder`, `head of`, `erfaren`, `experienced`
  - teksten krever erfaring i år: regex for `\b([1-9]\d?)\s*(\+|-\s*\d+)?\s*(års?|years?)\b` (også tallord som "tre"/"three") i nærheten av `erfaring`/`experience`. Krav på mer enn `max_required_experience_years` (0) forkastes, altså 1 år eller mer. "0–2 år" godtas. Verdier over 15 og bedriftens egen erfaring ("vi har over 20 års erfaring") ignoreres.
- Jobben er allerede vurdert med samme `content_hash`, `profile_hash` og `prompt_version`.

Regler som bare trenger tittel, sted og kategori kjøres før detaljhenting, så Finn-annonser som åpenbart faller bort aldri hentes. Tekstreglene kjøres etter at annonseteksten er hentet. Forkastede jobber får `filtered_out = true`.

Hardfilteret logger *hvorfor* noe ble forkastet (`hardfilter_log.rule`: `geography`, `job_type`, `role`, `occupation`, `title_not_it`, `seniority_title`, `experience_years`, og `llm_seniority` fra filter-agenten), slik at det kan justeres. Loggen vises i `GET /api/logs/discarded`.

### 5.2 Steg 2: filter-agent (tier `fast`, batch)

- **Batching:** opptil 10 annonser per kall. Felles kontekst (kort profil og preferanser) sendes én gang. Det gir lavere overhead og utnytter prompt caching.
- **Output per annonse:** `FilterResult` (§7.2). Inneholder score, klassifisering, **sammendrag**, frist og kontakter. Sammendraget gjenbrukes senere som `job_ad_summary`, så annonsen ikke må leses på nytt.
- **Senioritet etter LLM** (bare ufiltrerte kilder, siden Finn-jobber alltid regnes som `entry`): `seniority` er `entry | unspecified | experienced`.
  - `experienced` skjules.
  - `unspecified` (ingen krav om erfaring, men heller ikke uttalt junior) **vises med lavere score**: maks 65, altså under e-postterskelen på 70. Disse havner i dashboardet, men utløser ikke varsel.
  - Taket på 65 settes av koden etter LLM-kallet (`search.unspecified_seniority_max_score`), slik at det gjelder uansett hva modellen svarer.
- **Hva som scores** (`agents.filter.score_pending`): aktive jobber som ikke er forkastet og mangler en evaluering for gjeldende `content_hash`. Er den destillerte profilen utdatert, kjøres destilleren først. Når kostnadstaket (§8.3) er nådd, stopper scoringen med `openrouter`; jobbene scores når taket er hevet eller ny måned starter. Er `claude_code` standard, scores det videre med den (uten reserve).
- **Koden fyller inn** fra resultatet: `job_type` hvis ukjent, `seniority`, `ad_language`, frist og søknads-URL hvis jobben mangler dem, og kontakter (`source = llm`) hvis kilden ikke hadde noen.
- **Ugyldig output:** skjemafeil eller manglende `job_id` gir ett nytt forsøk. Deretter godtas delvise batcher, og manglende jobber telles som feilet og prøves neste kjøring. Pydantic klemmer score til 0–100, korter lister til maks antall og gjør ugyldige datoer til null.
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
- **Profil eller prompt endret:** dashboardet viser "N aktive jobber er scoret med gammel profil, estimert kostnad $X" og en knapp. Bare aktive jobber med status Ikke vurdert eller Interessant, publisert de siste 30 dagene, scores på nytt. Aldri automatisk, for å holde kostnaden nede. Logikken finnes i `agents.filter.rescore()`; knappen kommer med F4. Fra kommandolinjen: `jobsearcher rescore` (samme utvalg) eller `jobsearcher rescore --all` (alle aktive, scorede jobber uansett alder og status, f.eks. etter bytte av modell).

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
| `style_overrides.md` | Eksplisitte stilregler. Overstyrer alt annet. Regler lagret fra revisjonschatten havner under `## Fra revisjonschatten`. |
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
| `manifest.json` | Hash per kildefil, `profile_hash`, versjon av destiller-prompten, modell, tidspunkt | Kontekstbygger |

`profile_hash` = 16 hex-tegn av sha256 over sorterte `sti:sha256(innhold)` (CRLF → LF). Bare `.md`, `.yaml`, `.yml` og `.txt` leses; filer og mapper som starter med `_` eller `.` ignoreres. Lag 2 er utdatert når `profile_hash` eller destiller-promptens versjon endres, eller en fil mangler. `evaluations.profile_hash` er hashen lag 2 ble laget fra.

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

**Format:** felles biter pakkes som `<slice_navn>…</slice_navn>`. Hver annonse er `<job_ad id=… prefiltered=…><meta>…</meta><text>…</text></job_ad>`, og `<job_ad` inne i annonseteksten escapes. Bitene for fase 3 leser det agenten legger i `extras` (`job`, `evaluation`, `company`, `company_note`, `draft`, `instruction`, `history`). Bruker- og annonsetekst escapes så den ikke kan lukke sin egen tagg. `job_ad_summary` faller tilbake til starten av annonsen når jobben ikke er scoret. `revision_log` er de siste chatmeldingene før den nye, forkortet til 400 tegn.

**Budsjett:** Kontekstbyggeren teller tokens før hvert kall (også systemprompten) (estimat: tegn/3.5, med `count_tokens` på API-backend). Over budsjett kuttes biter med prioritet 3, deretter 2. Prioritet 1 kuttes aldri. En annonseblokk i en batch kuttes som helhet, med laveste prioritet blant bitene sine. Går det fortsatt over, feiler kallet med en tydelig melding.

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
| Reviser | Rullerende: hver brukermelding starter en ny agent med gjeldende utkast, de siste 5 chatmeldingene (`draft_messages`) som en kompakt logg og fast kontekst. Konteksten er like stor i runde 20 som i runde 1. |

### 6.4 Valg av relevante prosjekter

1. Filter-agenten gir `tech[]` og `role_category` for annonsen.
2. `config/tech_aliases.yaml` normaliserer synonymer (`react.js`/`reactjs` → `react`, `.net`/`dotnet`/`asp.net core` → `dotnet`, `k8s` → `kubernetes`).
3. Score per prosjekt:
   - +3 per teknologi annonsen og prosjektet har felles
   - +2 hvis `categories` inneholder annonsens `role_category`
   - +2 hvis `highlight: true`
   - +1 hvis `type` er `jobb` eller `personlig` og prosjektet er i bruk (skiller fra rene skoleoppgaver ved lik score)
4. De 3 beste tas med i sin helhet (`context/projects.py`, fra `PROFILE_DIR/projects/*.md`). Resten nevnes med én linje i `profile_long`. Uten evaluering teller bare `highlight` og `type`.

### 6.5 Sikkerhet

- Annonsetekst, e-poster og nettsider er **utrygg input**. De pakkes i `<job_ad>…</job_ad>`-blokker, og promptene sier eksplisitt at innholdet er data, ikke instruksjoner.
- Bare research-agenten har verktøy (websøk/-henting). Ingen agent kan skrive filer, endre DB eller sende e-post. All skriving gjøres av koden ut fra validert, strukturert output.
- `claude_code`-backenden kjører hvert kall i en tom arbeidsmappe med eksplisitt verktøyliste (§8.1).

---

## 7. Agentene

Systemprompter ligger i `context/prompts/*.md`. Hver har en `version` i frontmatter, som lagres på resultatet.

### 7.1 Oversikt

| Agent | Tier (§8.2) | Når | Input | Output |
|---|---|---|---|---|
| Distiller | `balanced` | Profilhash endret | Hele lag 1 | `profile_short`, `profile_long`, `voice` |
| Filter | `fast` | Hver kjøring, i batch | Kort profil + 10 annonser | `FilterResult` × 10 |
| Researcher | `balanced` + web | Første søknad til en bedrift | Bedriftsmeta + sammendrag | `CompanyNote` |
| Writer | `best` | "Lag søknad" | Se §6.2 | `DraftResult` |
| Reviser | `balanced` | Hver chatmelding i editoren | Se §6.2 | `RevisionResult` |
| Extractor | `fast` | Sideovervåker oppdaget endring | Rensket side | Liste over stillinger |

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
    kind: Literal["revision", "answer"]  # answer = spørsmål besvart, ingen ny versjon
    reply: str                    # chatsvaret; ved revision også change_summary (én linje)
    letter_markdown: str          # tom ved answer
    claims_to_verify: list[str]
    style_rule: str | None        # foreslått stilregel når meldingen gjelder alle brev, ellers null
```

Ugyldig output → ett nytt forsøk med valideringsfeilen i prompten → deretter markeres kallet som feilet.

### 7.3 Research-agenten

- Verktøy: `openrouter` (standard) bruker OpenRouters web-plugin (`plugins: [{id: web}]`), som legger søkeresultater ved meldingen. `claude_code` får `--allowedTools "WebSearch,WebFetch"` (maks ~8 kall).
- Prioriterte kilder: bedriftens nettside (om oss, karriere, techblogg), nyheter siste 12 måneder, Proff/Brønnøysund for størrelse.
- Notatet lagres som Markdown i `data/companies/<slug>.md` med en rad i `companies` (`agents/researcher.py`). Detaljvisningen og skriveren leser det derfra.
- **Cache:** et `full`-notat brukes i 90 dager per `company_slug`. Ukjent bedrift (`ukjent`) får ikke notat.
- **Når research feiler:** notatet bygges fra arbeidsgiverbeskrivelsen i annonsen (NAV har den) og merkes `limited`; neste utkast prøver research på nytt. Uten beskrivelse brukes et eldre notat om det finnes, ellers skriver skriveren uten. Research-feil stopper aldri utkastet.

### 7.4 Skrive-agenten

- Ett vanlig søknadsbrev per stilling, også når stillingen har søknadsskjema. Brevet er da grunnlag for skjemautfyllingen.
- Språket følger `ad_language`, og kan overstyres i dashboardet.
- Lengde og stil fra `style_overrides.md`. Stemme fra `voice.md`.
- **Faktaregel:** Brevet kan bare påstå ting om brukeren som finnes i profilen, også koblinger (at en teknologi er brukt i et bestemt prosjekt). Det som mangler i profilen, utelates eller sies ærlig ("har ikke jobbet med X ennå"), uten oppdiktet bro. `claims_to_verify` er for dekkede formuleringer som kanskje er for sterke, og vises som advarsel i editoren.
- **Oppstart:** søkeren studerer til datoen i profilen (`practical.available_from`, `availability`). Har annonsen oppstart før det eller ingen oppstartsdato, skriver brevet én setning om når søkeren kan begynne (deltid og fulltid). Filteret trekker ikke for uklar oppstart, men noterer den i `concerns`.
- **Lengde:** grensen i `style_overrides.md` er en øvre grense. Prompten ber modellen telle ord og kutte svakeste avsnitt heller enn å korte hver setning.
- Kort form: prosjekter nevnes med én setning (navn, relevant teknologi, resultat), ikke forklart i detalj. Ingen tankestrek (– eller —): prompten forbyr den, og `clean_letter` bytter den ut i alt skriveren og revisoren lagrer (komma, eller bindestrek i tallintervaller og punktlister). Brukerens egne redigeringer røres ikke.
- Skriveeksemplene ga ikke intervju. De brukes for stemmen, ikke for strukturen (står i `style_overrides.md`).
- **Flyt** (`agents/writer.py`, oppgaven `draft`): destiller ved behov → research → skriver. Hvert steg har egen DB-transaksjon, så ingen skrivelås holdes under et LLM-kall. Søknaden opprettes (triage til Interessant) og flyttes til Utkast først når første versjon er lagret, så et mislykket utkast lar jobben være som den var. Agentmeldingen for første utkast nevner prosjektene og `notes_for_user`.
- **Revisjon** (`agents/reviser.py`, oppgaven `revise`): et svar med `kind: revision` uten brevtekst gir ett nytt forsøk; en «revisjon» med uendret tekst lagres som svar.
- **Stilregler fra chatten:** er meldingen en preferanse for alle brev ("aldri tankestrek", "mindre formelt"), foreslår revisoren en kort regel i `style_rule`. Den lagres på agentmeldingen og vises med knappen «Lagre som stilregel» (FRONTEND §5.5). Lagring legger regelen til i `style_overrides.md` (`context/style_rules.py`) og skriver en rad i `profile_revisions`. Ingenting lagres automatisk: brukeren godkjenner hver regel, så listen ikke vokser med motstridende eller stillingsspesifikke regler.

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

**`claude_code` (valgfri, standard til v0.16):** subprosess av `claude -p` (verifisert med CLI v2.1.296, spike 02 §Oppdatering):

```
claude -p --output-format json --json-schema '<schema>' --model <haiku|sonnet|opus>
  --system-prompt-file <tmp-fil> --effort <nivå> --max-budget-usd <n>
  --strict-mcp-config --setting-sources "" --disable-slash-commands --no-session-persistence
  --permission-prompts none --tools ""          # research: --allowedTools WebSearch,WebFetch
```
- Brukerinnholdet sendes på stdin (UTF-8). Arbeidsmappe: `data/llm_sandbox/` (tom).
- Isolasjonen gir ~1,5k tokens overhead per kall (mot ~39k uten). `--bare` brukes ikke, siden det slår av abonnementsinnloggingen.
- `ANTHROPIC_API_KEY` fjernes fra subprosessens miljø, så abonnementet brukes. `CLAUDE_CODE_OAUTH_TOKEN` sendes videre hvis den finnes.
- Kostnad fra `total_cost_usd`. Målt: filter-batch med 3 annonser (Haiku) ~$0.0025, destillering (Sonnet) ~$0.12.
- **I container:** Claude Code CLI installeres i imaget (linux-arm64). Innlogging på abonnementet gjøres én gang med `claude setup-token`, og tokenet legges i `.env` som `CLAUDE_CODE_OAUTH_TOKEN`. Verifiseres når fase 4b starter.

**`openrouter` (standard, spike 05):** OpenRouters OpenAI-kompatible API (`https://openrouter.ai/api/v1/chat/completions`) med `httpx`, nøkkel i `OPENROUTER_API_KEY`. Modell `deepseek/deepseek-v4.1-flash` for alle tiers. Erstatter `anthropic_api` (fjernet i bølge 2b).
- Strukturert output med `response_format: {type: json_schema, json_schema: {strict: true, schema}}`. Svaret valideres mot Pydantic-skjemaet, og ugyldig JSON gir ett nytt forsøk.
- `provider: {require_parameters: true, data_collection: "deny"}`: bare leverandører som støtter skjemaet og ikke lagrer eller trener på data.
- `effort` sendes som `reasoning.effort` (`xhigh`/`max` blir `high`). `max_budget_usd` har ingen motpart hos OpenRouter. Tidsavbrudd: `llm.openrouter.timeout_s` (300 s). Research-agenten bruker OpenRouters websøk (`plugins: [{id: web}]`), de andre ingen verktøy.
- Kostnad fra `usage.cost` i svaret (ekte penger, i motsetning til `claude_code`-estimatet). Systemprompt og profilkontekst først i meldingen, så leverandørenes automatiske prompt-cache treffer.

**Reserve-regel (`llm.fallback`, standard `none`):** av som standard, fordi en annen modell gir scorer på en annen skala (spike 05). Uten reserve blir et kall som feiler stående som feil, og jobbene scores ved neste kjøring. `get_backend()` i `llm/base.py` pakker standard-backenden i `FallbackBackend` når `llm.fallback` er satt til en annen backend og standarden ikke er `mock`; en `openrouter`-reserve krever i tillegg `OPENROUTER_API_KEY`. Reglene under gjelder når reserven er slått på. `llm.fallback` leses fra `settings.yaml`, ikke fra dashboardets overstyringer.

| Feil i `claude_code` (som standard) | Bytter til reserven? |
|---|---|
| CLI ikke funnet, prosessen starter ikke, tidsavbrudd, output som ikke er JSON, `is_error` med annen subtype enn under (innlogging utløpt, bruksgrense, API-feil, `error_during_execution`) | Ja (`LLMBackendError`) |
| `error_max_budget_usd`, `error_max_structured_output_retries`, `error_max_turns`, ingen strukturert output | Nei |
| Ugyldig svar mot Pydantic-skjemaet eller `check` | Nei: ett nytt forsøk på samme backend (`agents/base.py`) |
| Kostnadstaket | Nei: sjekkes før kallet |

- **Bryter:** etter en backendfeil går alle kall rett til reserven i 30 minutter (i prosessen), så en batch med filter-kall ikke venter ut tidsavbruddet ett kall om gangen. Etterpå prøves standarden igjen.
- **Logging:** det feilede forsøket blir en `error`-rad i `agent_runs` med standard-backenden (0 tokens). Svaret fra reserven får reservens `backend` og `fallback_from` satt til standarden. Mens bryteren er åpen skrives bare reserveraden. Feiler reserven også, blir det to feilrader.
- HTTP-feil fra OpenRouter (401, 402 for lite kreditt, 429, 5xx), tidsavbrudd og manglende nøkkel er backendfeil. Ugyldig JSON to ganger er en modellfeil.

**Saldo:** `llm/openrouter.py` leser saldoen til forbrukskortet (FRONTEND §5.1). Med `OPENROUTER_MANAGEMENT_KEY` (valgfri) brukes `GET /api/v1/credits` (`total_credits` − `total_usage` = kontosaldo). Uten den brukes `GET /api/v1/key` med vanlig nøkkel: `limit_remaining` gir det som er igjen hvis nøkkelen har en kredittgrense; uten grense er saldoen ukjent. Totalt forbruk (`used_usd`) kommer fra `total_usage` (konto) eller `usage` (nøkkel) og tar med kall utenfor appen. Svaret caches i 10 minutter, også når hentingen feiler (da er saldoen ukjent). Tidsavbrudd 5 s.

**`mock`:** faste svar for tester og dashboardutvikling.

### 8.2 Modeller (`model_tier`)

| Tier | `openrouter` (standard) | `claude_code` (valgfri) |
|---|---|---|
| `fast` | `deepseek/deepseek-v4.1-flash` | `haiku` |
| `balanced` | `deepseek/deepseek-v4.1-flash` | `sonnet` |
| `best` | `deepseek/deepseek-v4.1-flash` | `opus` |

OpenRouter-modellen per tier settes i `config/settings.yaml` (`llm.openrouter.models`), så modellen kan byttes uten kodeendring.

### 8.3 Kostnad

`openrouter` koster ekte penger fra forhåndsbetalt kreditt: med DeepSeek V4.1 Flash ($0.15/$0.60 per million tokens hos DeepSeek) ca. $0.0009 per scoret jobb (spike 05), anslagsvis $1–2/mnd med søknadsutkast. Med `claude_code` trekkes bruken fra abonnementet, men `total_cost_usd` logges likevel som estimat. Forbrukskortet viser de to hver for seg.

**Kostnadstak:** $10/mnd for **betalte kall** (`llm.monthly_cap_usd`; kalendermåned i Oslo-tid, sum av `agent_runs.cost_usd` for alle backender unntatt `claude_code`, `llm/costs.py`). Estimatet fra `claude_code` teller ikke, siden abonnementet betaler.
- Ved 80 %: advarsel i dashboardet og digesten.
- Ved 100 %: betalte kall stoppes, og med `openrouter` som standard stopper scoringen (`subscription_only` gir ingen backend). Er `claude_code` standard, scorer filter-agenten videre med den uten reserve. Utkast og revisjon feiler med en melding om taket (ingen bekreftelsesdialog ennå; taket heves i innstillingene, F4).
- OpenRouter-nøkkelens egen kredittgrense er en ekstra sperre utenfor appen.

---

## 9. Datamodell (SQLite)

```
jobs                 id, fingerprint, title, company, company_slug, org_number, location_text,
                     municipality, remote (none|hybrid|full), job_type, seniority, ad_language,
                     description_clean, ad_text_status (present|missing|imported), prefiltered,
                     meta (json: kildens strukturerte felt, job_meta-biten), published_at,
                     expires_at, deadline, deadline_text, application_url, application_url_norm,
                     first_seen, last_seen, active, content_hash, reposted_from_id,
                     filtered_out                                  ← skjult av hardfilter/filter-agent

job_sources          id, job_id, source (finn_api|nav|teamtailor|page_watch|manual),
                     source_id, url, raw_path, fetched_at,
                     detail_attempts, detail_next_at              ← mislykkede annonsesideforsøk, neste forsøk (§4.2)

job_contacts         id, job_id, name, role, email, phone, source (feed|llm|manual)

evaluations          id, job_id, score, confidence, role_category, job_type, seniority,
                     tech (json), summary, key_requirements (json), match_reasons (json),
                     concerns (json), model, prompt_version, profile_hash, content_hash, created_at

hardfilter_log       id, job_id, rule, detail, created_at          ← "hvorfor forkastet"

companies            slug, name, org_number, homepage, note_path, note_quality (full|limited),
                     researched_at

applications         id, job_id (unik), status, created_at, applied_at, follow_up_at,
                     next_step, next_step_at, notes

application_events   id, application_id, from_status, to_status, at, comment

drafts               id, application_id, version, content, author (agent|user),
                     instruction, change_summary, claims_to_verify (json), agent_run_id, created_at

draft_messages       id, application_id, role (user|agent), text, draft_id (versjonen svaret laget,
                     null for spørsmål og brukermeldinger), style_rule (foreslått stilregel),
                     style_rule_saved_at, agent_run_id, created_at   ← chatten, migrasjon 0004 og 0005

agent_runs           id, agent, job_ids (json), application_id, backend, model, prompt_version,
                     input_tokens, output_tokens, cost_usd, duration_ms, status, error,
                     fallback_from (backend som feilet, migrasjon 0003), created_at

scrape_runs          id, trigger (schedule|manual), source, started_at, finished_at,
                     found, new, updated, filtered_out, errors (json), health (ok|warn|fail)

source_state         source, key, cursor, etag, last_success_at       ← cursorer per kilde

tasks                id, kind, params (json), status, progress, message, cancel_requested,
                     result (json), created_at, finished_at            ← bakgrunnsjobber

settings_overrides   key, value

profile_revisions    id, path, content, content_hash, created_at        ← historikk for profilredigering
```

Alle tidspunkter lagres som tidssonebevisst UTC. Datoer (frist, oppfølging, "i dag") er Oslo-datoer (`config.today()`). Migrasjoner ligger i `src/jobsearcher/db/migrations/` (Alembic, batch-modus for SQLite); `init_db()` kjører `upgrade head` ved `serve`, `run` og `init-db`.

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

- Overgangstabellen og angre-logikken ligger i `tracking/status.py`. Triage til samme status gjør ingenting. Triage tilbake til Ikke vurdert avvises (409) hvis søknaden har utkast.
- Hver overgang lagres i `application_events`. API-et sender lovlige neste statuser (`allowed_next`) og forrige status (`previous_status`, `from_status` i siste hendelse) på hvert kort.
- **Angre:** overgang tilbake til `previous_status` er alltid lov og sletter siste hendelse. Første hendelse (fra Ikke vurdert) angres med triage, som sletter søknadsraden.
- Ved `Søkt` settes `applied_at`, og `follow_up_at` til +14 dager hvis den ikke sendes med. Angre fra Søkt nullstiller `applied_at`.
- `next_step` og `next_step_at` er fritekst og dato ("Intervju 2. runde", "Case-oppgave"). Ingen kalenderintegrasjon.
- **Utkast:** "Lag søknadsutkast" oppretter søknaden hvis jobben ikke er vurdert, og flytter Interessant → Utkast når første versjon er skrevet (senere statuser endres ikke). Har søknaden utkast fra før, avvises det (409 `draft_exists`).
- **Chat** (`draft_messages`): brukerens melding lagres med en gang. Revisoren svarer med en agentmelding; er meldingen et spørsmål, blir det bare et svar (`kind: answer`), ellers en ny versjon som svaret lenker til. Skriveren legger også inn en agentmelding for første utkast.
- **Versjoner** (`drafts`): agenten lager en ny versjon per utkast og revisjon (ikke for svar). Autosave fra editoren lager en brukerversjon, men oppdaterer nyeste versjon på plass hvis den er en brukerversjon yngre enn 10 minutter, så en redigeringsøkt blir én versjon. Brukerversjoner arver `claims_to_verify` fra versjonen de er redigert fra.

---

## 10. Dashboard

React-SPA (Vite + TS + Tailwind/shadcn) bygget til `web/dist/` og servert av FastAPI på port 8765, med JSON-API under `/api`. Skjermer, layout for PC og mobil, API-kontrakt og frontend-bølger står i **[FRONTEND.md](FRONTEND.md)**.

Sider: Oversikt, Jobber, Jobbdetalj, Tracker, Søknadseditor, Profil, Innstillinger, Logg.

### 10.1 Bakgrunnsjobber

- Brukerinitierte operasjoner (kjør nå, utkast, research, revisjon, ny scoring, destillering) og den planlagte kjøringen blir rader i `tasks` og kjøres av en `ThreadPoolExecutor` med 2 arbeidere i `serve`-prosessen (`web/tasks.py`). Jobber som sto i kø eller kjørte da prosessen stoppet, markeres `failed` ("Avbrutt ved omstart") ved oppstart.
- Frontend poller `GET /api/tasks/{id}` hvert 2. sekund for progresjon (FRONTEND §3.3).
- Avbryt: `cancel_requested` sjekkes mellom steg, f.eks. mellom kilder og filter-batcher. En jobb i kø avbrytes med en gang; en som kjører får status `cancelled` når den når neste sjekk.
- FastAPI serverer `web/dist` på `/` (med `index.html` som fallback for klientruter) når mappen finnes.
- `jobsearcher run` fra CLI finnes fortsatt for manuell kjøring. `data/run.lock` hindrer overlapp mellom CLI, planlegger og "Kjør nå".

### 10.2 Eksport

`GET /api/drafts/{id}/docx` lager filen med `python-docx` (`export/docx.py`), uten mal og uten å lagre den:
- avsender: `name` og kontaktfelt (`email`, `phone`, `location`, `github`, `linkedin` m.fl.) fra `profile.yaml`, på toppnivå eller under `contact`
- mottaker (bedriften)
- dato (Oslo, "11. oktober 2026"; engelsk format når annonsen er engelsk)
- brevtekst: Markdown → avsnitt, linjeskift, overskrifter, punktlister, fet og kursiv

Filnavn i `Content-Disposition`: `Søknad <Bedrift> v<versjon>.docx` (UTF-8, med ASCII-reserve).

---

## 11. Planlegging og varsling

- **Planlegger:** `jobsearcher serve` starter uvicorn og APScheduler i samme prosess (`scheduler.py`, bygget i fase 2). Kjøringen legges i kø som en vanlig `run`-task med `trigger = schedule`. `SCHEDULER_ENABLED=false` slår planleggeren av (brukes i tester). Klokkeslett i `settings.yaml` (`schedule.daily_at`, standard `07:00`, tidssone `Europe/Oslo`). Selve kjøringen starter et tilfeldig antall minutter (0 til `schedule.jitter_minutes`, standard 40) etter klokkeslettet, så kildene ikke ser samme starttid hver dag.
  - Ved oppstart: har dagens klokkeslett passert uten at noen kjøring (planlagt eller manuell) har startet etter det, startes en med en gang.
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
| Hemmeligheter | `.env`: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` (bare SMTP), `NAV_FEED_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` (drift, §8.1), `OPENROUTER_API_KEY` (standard-backend, §8.1), valgfri `OPENROUTER_MANAGEMENT_KEY` (bare saldo). På Pi-en ligger filen i `infra/config/jobsearcher/jobsearcher.env`. Finn-HMAC-nøkkelen (`d45ff03c-b783-44d9-b94a-bb28dbc016a6`) er bakt inn i `finn_sig.py` som konstant — den finnes åpent i APK-en og trenger ingen env-variabel, men må oppdateres hvis Finn roterer den. |
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
| `config/settings.yaml` | Søk (roller, ekskluderinger, jobbtyper, senioritet, geo-modus), terskler, planlegging, LLM-backend, reserve og OpenRouter-modeller, kostnadstak | Ja |
| `config/agents.yaml` | Kontekstmanifest, modell-tier og effort per agent | Ja |
| `config/locations.yaml` | Geo-moduser → kommuner | Ja |
| `config/sources.yaml` | Aktive kilder, Finn-søk (parametere per søk-id), Teamtailor-feeder, sideovervåkede selskaper | Ja |
| `config/tech_aliases.yaml` | Teknologisynonymer | Ja |
| `.env` | Hemmeligheter | **Nei** |

Innstillinger endret i dashboardet lagres i `settings_overrides` og overstyrer YAML (`db/repo.py: effective_settings`).

Stier styres av miljøvariabler, så samme kode kjører på PC og i container:

| Variabel | Standard (utvikling) | Container |
|---|---|---|
| `DATA_DIR` | `data/` | `/data` |
| `PROFILE_DIR` | `context/profile/` | `/data/profile` |
| `DERIVED_DIR` | `context/derived/` | `/data/derived` |
| `SCHEDULER_ENABLED` | `true` | `true` |

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
├── alembic.ini                        Peker på src/jobsearcher/db/migrations; URL fra DATA_DIR
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
│   ├── cli.py                         typer: serve | run | distill | init-db (senere: rescore | eval | backup)
│   ├── config.py                      Env (stier, hemmeligheter), settings.yaml-modeller, YAML-lasting, today()
│   ├── scheduler.py                   APScheduler i serve, innhenting av tapt kjøring
│   ├── api/           schemas.py      API-kontrakten (Pydantic), kilde for OpenAPI og TS-typer
│   ├── logging.py                     JSON-linjer til data/logs/
│   ├── db/            models.py, session.py, repo.py (effective_settings), migrations/
│   ├── sources/
│   │   ├── base.py                    JobSource, RawJob, CursorState, CollectResult
│   │   ├── http.py                    HttpClient (rate-limit med jitter per vert, retry, robots), save_raw
│   │   ├── registry.py                build_sources() fra sources.yaml
│   │   ├── finn_api.py                Finn: signert søk → RawJob, så annonsetekst fra JSON-LD på annonsesiden
│   │   ├── finn_sig.py                HMAC-SHA512-signering, egen impl. (se spike 04)
│   │   ├── nav_feed.py
│   │   ├── teamtailor.py
│   │   ├── page_watch.py
│   │   └── manual.py                  import av limt inn annonsetekst
│   ├── pipeline/      run.py, normalize.py, clean.py, dedupe.py, hardfilter.py, lifecycle.py, lock.py
│   ├── context/       loader.py, slices.py, builder.py, budget.py, projects.py (prosjektvalg §6.4), style_rules.py (§7.4)
│   ├── agents/        base.py, schemas.py, filter.py, distiller.py, researcher.py, writer.py, reviser.py
│   │                  (fase 5: extractor.py)
│   │   (ingen enricher — Finn-annonsesiden gir full annonsetekst)
│   ├── llm/           base.py (protokoll, FallbackBackend, bryter), claude_code.py, openrouter.py (+ saldo), mock.py, costs.py
│   ├── tracking/      status.py       Overgangstabell §9.1, triage, angre
│   │                  drafts.py       Versjoner (autosave-regelen), chatmeldinger
│   ├── notify/        email.py, templates/digest.html
│   ├── export/        docx.py         Brev → .docx (§10.2)
│   └── web/
│       ├── app.py, tasks.py           FastAPI-app med lifespan (DB, task-runner, planlegger), serverer web/dist
│       ├── queries.py                 DB → API-skjema, cursor-paging
│       ├── errors.py                  Feilformat `{detail, code}`, 501 for ruter uten backend
│       └── routes/    overview.py, jobs.py, applications.py, drafts.py, profile.py,
│                      settings.py, logs.py, tasks.py, llm.py (/api/llm/usage)
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
│   │   ├── features/                  overview/, jobs/, tracker/, drafts/ (søknadsliste og editor), profile/, settings/, logs/, more/
│   │   │                              (placeholders.tsx holder skjermene som ikke er bygget ennå)
│   │   ├── mocks/                     MSW: handlers.ts, db.ts, browser.ts, drafts.ts (mock-skriver/-reviser), docx.ts, fixtures/*.ts (oppdiktet)
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
    ├── conftest.py                    Egen DATA_DIR per test, migrert temp-DB, planlegger av
    ├── fixtures/                      finn/ (søk, annonseside, filtre), nav/, profile/ (oppdiktet); private/ er gitignored
    ├── test_api_*.py                  Kontrakt (501, openapi.json oppdatert), jobber, oversikt, tracker, tasks
    ├── test_finn_api.py, test_finn_sig.py, test_nav_feed.py, test_http.py
    ├── test_normalize.py, test_clean.py, test_dedupe.py, test_hardfilter.py, test_pipeline_run.py
    ├── test_llm_backends.py, test_context_builder.py, test_filter_agent.py, test_distiller.py
    ├── test_status_transitions.py, test_scheduler.py, test_db.py
    ├── test_drafts.py                 Fase 3: prosjektvalg, research, skriver, revisjon, utkast-API, .docx
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
| HTTP og parsing | `httpx`, `selectolax` (`lexbor`-parseren), `markdownify`, `feedparser` (fase 5) |
| Tidssoner | `tzdata` (trengs for `Europe/Oslo` på Windows) |
| Finn-signering | Egen impl. i `finn_sig.py` (bruker `hmac` + `hashlib` fra stdlib, se spike 04 §Signering) |
| E-post | `smtplib` + `email` (stdlib). Ingen IMAP. |
| Fuzzy-match | `rapidfuzz` |
| LLM | Claude Code CLI (`claude -p`), OpenRouter (via `httpx`) |
| CLI | `typer` |
| Eksport | `python-docx` |
| Test | `pytest`, `respx`; frontend: Vitest, Testing Library, Playwright |

---

## 17. Veikart

**Frontend først, så backend der den gir verdi.** F0–F2 (daglig sløyfe og tracker) er bygget mot mock og prøvd av brukeren. Fra v0.11 går backend-fasene 1 og 2 foran F3 og F4: de skjermene som allerede er prøvd får ekte data, så verktøyet kan brukes i jobbsøkingen nå. F3 (søknadseditor) bygges rett før fase 3, og F4 (profil, innstillinger, logg) før fase 4, siden kvaliteten på brev og profil bare kan vurderes med ekte LLM-output.

Rekkefølge: fase 1 → fase 2 → 2b/F2b → F3 → fase 3 → F4 → fase 4 → 4b/F5 → 5 → 6.

| Fase | Innhold | Ferdig når |
|---|---|---|
| ~~0. Spikes~~ | Finn, NAV, Claude-abonnement, trainee-kilder | ✅ `docs/spikes/` |
| ~~0b. Finn-sjekk~~ | Verifiser HMAC-signeringen og lagre filter-metadata som fixture. Ingen appkode. | ✅ 2026-10-10, spike 04 §Oppdatering |
| ~~F0–F2. Frontend mot mock~~ | Skjelett, daglig sløyfe og tracker (FRONTEND §8) | ✅ 2026-10-10 |
| ~~1. Fundament~~ | Repo-oppsett, config med `DATA_DIR`/`PROFILE_DIR`, DB + Alembic, HTTP-lag, NAV-kilde, Finn-API-kilde (`finn_api.py` + `finn_sig.py`, se spike 04), normalisering, dedupe, hardfilter, `jobsearcher run` uten LLM, `serve` med de første ekte endepunktene. Ingen Windows-spesifikk kode. | ✅ 2026-10-10 |
| ~~2. Scoring + API v1~~ | LLM-backends, destiller, filter i batch, `/api` for oversikt, jobber, jobbdetalj, triage og tasks. Kobler F1. Trukket frem fra fase 4: tracker-API-et (kobler F2), logg-API-et og planleggeren i `serve`. | ✅ 2026-10-10 |
| ~~2b. OpenRouter-reserve~~ | `llm/openrouter.py`, reserve-regel med bryter (§8.1), `anthropic_api` fjernet, migrasjon `0003`, `GET /api/llm/usage`, forbrukskortet (F2b). Sjekk mot Haiku: spike 05 §Oppdatering. | ✅ 2026-10-11 |
| ~~F3. Søknadseditor~~ | FRONTEND §5.5 mot mock | ✅ 2026-10-11 |
| ~~3. Søknader~~ | Research, writer, revisjon, versjoner, `.docx`-eksport, `/api` for utkast. Kobler F3. | ✅ 2026-10-11 (mock-LLM ende til ende; ikke prøvd live med DeepSeek) |
| **F4. Profil, innstillinger, logg** | FRONTEND §5.6–5.8 mot mock | Profilen kan redigeres uten filsystemtilgang |
| **4. Tracking + varsling** | E-postdigest, profil-API, innstillings-API, "score på nytt"-knapp. Kobler F4. (Statusflyt, oppfølging, planlegger og backup kom i fase 1–2.) | Hele flyten går uten manuelt arbeid |
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
**Bølge 2b (OpenRouter-reserve):**
- [x] Lage konto på openrouter.ai og fylle på kreditt ($10, 2026-10-11)
- [x] Lage API-nøkkel → `OPENROUTER_API_KEY` i `.env`, med kredittgrense $10 (verifisert mot `/api/v1/key`)
- [x] Lage management-nøkkel → `OPENROUTER_MANAGEMENT_KEY` i `.env` (verifisert mot `/api/v1/credits`)
- [ ] Legge begge nøklene i Pi-ens `jobsearcher.env` (fase 4b)

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
| 1   | **Finn-API-et er en gråsone.** Finns ToS forbyr automatisert innhenting uten skriftlig samtykke. Mobil-API-et er uoffisielt for tredjepart. | Bevisst risiko. Privat, lokal, lavvolum (1 bruker, 1–4 søkekall og 10–30 annonsesider per døgn). Tiltakene i §4.2 punkt 8: realistiske app- og WebView-headere, tilfeldig avstand, tak per kjøring, stopp ved 403/429, pause mellom hentinger. `robots.txt` på `www.finn.no` tillater `/job/ad/` for vår agent, men stenger AI-crawlere (GPTBot, ClaudeBot) ute fra `/job/`; vi crawler ikke, men annonseteksten sendes til en LLM for scoring. Verktøyet publiseres ikke. Detaljer i spike 04.                                                                  |
| 2   | **Finn-signaturen eller endepunktene brytes** (nøkkelrotasjon, format- eller endepunktsendring, deteksjon).                                 | Pin appversjon (`261006-ec709768`) fra APK-en i `User-Agent`. Oppdater `finn_sig.py` eller dekompiler ny APK ved behov. Kildehelse (§12) oppdager 401/403 raskt. Manuell innliming (`manual`-kilden) som siste fallback. |
| 3   | Anthropic kan endre vilkår eller fakturering for `claude -p` | Ikke lenger aktuelt som standard: `openrouter` er standard fra v0.16 (§8.1). |
| 4   | Strengt senioritetsfilter kan gå glipp av gode stillinger                                                                                   | Stillinger uten oppgitt senioritet vises med maks score 65. Hardfilteret følges opp via "Forkastet i dag".                                                                                                               |
| 5   | NAV-token roterer eller utløper                                                                                                             | Privat token, og kildehelsevarsel ved 401                                                                                                                                                                                |
| 6   | Karrieresider endrer struktur og gir støy i sideovervåkeren                                                                                 | Hash av hovedinnhold med CSS-selektor, og LLM-uttrekk bare ved endring                                                                                                                                                   |
| 7   | Skrive-agenten finner på fakta                                                                                                              | Faktaregel og `claims_to_verify` i editoren                                                                                                                                                                              |
| 8   | `claude -p` i container på arm64: innlogging med `CLAUDE_CODE_OAUTH_TOKEN`, isolasjonsflaggene og tokenets levetid er ikke verifisert | Verifiseres først i fase 4b. Faller det, settes `llm.backend: openrouter` på Pi-en (bare HTTPS, ingen CLI). |
| 9   | Profilen finnes bare i Pi-ens datavolum i drift. Restic-repoet ligger på samme disk som dataene (runbook §10).                              | `profile_revisions` gir historikk. Mulighet for eksport av profilen fra dashboardet. Følger Pi-ens plan for backup til ekstern disk.                                                                                     |
| 11  | NAV-feeden er treg (13–60 s per side) og svarte 500/504 under første live-forsøk 2026-10-10 | 90 s tidsavbrudd, ingen raske nye forsøk, første vindu 7 dager. Cursoren står urørt ved feil, og neste daglige kjøring prøver igjen. Kildehelsen viser `fail`. |
| 12  | Finn-identiteten er delvis gjettet: formatet på appens `User-Agent` (`HttpUserAgent.getUserAgent()`), WebView-Chrome-versjonen og enhetsbygget er ikke lest fra APK-en eller en ekte enhet, og appversjonen blir gammel over tid | Verdiene står i `sources.yaml` (`os_version`, `device_model`, `device_build`, `webview_chrome_version`, `app_version`). Neste gang en APK dekompileres (spike 04): les `HttpUserAgent` og oppdater appversjon og WebView-versjon samtidig, helst hvert par måneder. |
| 13  | DeepSeek via OpenRouter er eneste modell: annonsetekst og destillert profil går til tredjepartsleverandører, kvaliteten kan variere med leverandør og kvantisering, og den bruker forhåndsbetalt kreditt (tom kreditt = ingen scoring) | `data_collection: deny` og `require_parameters` i hvert kall (§8.1). Filter-prompt v0.3 er kalibrert mot Haiku-skalaen (spike 05: snitt −1,7, Spearman 0,70); terskelen 70 sjekkes mot brukerens triage. Forbrukskortet varsler under $1 saldo. `claude_code` kan settes som standard med én linje i config. |
| 10  | Frontend og backend glir fra hverandre mens frontend bygges mot mock                                                                        | Kontrakten er Pydantic-modellene; TS-typer genereres og fixtures typesjekkes (FRONTEND §3.1)                                                                                                                             |
