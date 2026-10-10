# Spike 04: Finn via mobil-API

**Dato:** 2026-10-10
**Status:** Reverse engineering fullført. Jobbsøk-endepunkt, signeringsalgoritme og HMAC-nøkkel er dokumentert i denne spiken. Neste skritt er å verifisere mot et levende kall og implementere `finn_api.py` + `finn_sig.py`.
**Konklusjon:** Finn-stillinger hentes direkte fra Finns mobil-API på `https://appsgw.finn.no/`, det samme API-et Android-appen bruker. Hver forespørsel signeres med HMAC-SHA512 i header `FINN-GW-KEY`. Nøkkel og endepunkter er funnet ved å dekompilere Finns Android-APK (`FINN.no_261006-ec709768_APKPure.apk`, i rot — ikke sjekket inn i git). Signeringsregelen er implementert direkte fra appens `HmacSigningInterceptor` (se §Signering). Varsler via Gmail/IMAP er droppet.

## Hvorfor denne tilnærmingen

Fra spike 01 (nå droppet):
- Finns ToS forbyr automatisert skraping av `finn.no` uten skriftlig samtykke.
- Varsel-e-poster inneholder bare tittel, bedrift og sted — annonseteksten må berikes fra andre kilder.
- IMAP-flyten krever at brukeren setter opp lagrede søk og Gmail-filter manuelt, og at hver søkeendring gjøres i Finns UI.

Mobil-API-tilnærmingen gir:
- **Full annonsetekst og strukturerte felt** i én forespørsel. Ingen separat berikelse for Finn-jobber.
- **Søkeparametere i kode**: roller, geografi, erfaring og utdanning styres fra `config/sources.yaml`, ikke fra Finns UI. Endringer krever ingen manuelle steg.
- **Ingen IMAP-avhengighet**. Gmail trengs fortsatt for SMTP-digest til brukeren selv.

Risikoen er at dette er et uoffisielt API uten publiserte vilkår for tredjepartsbruk. Se §Risiko nedenfor.

## Signering (verifisert mot APK v261006-ec709768)

Finn signerer HTTP-forespørsler med en HMAC-SHA512-signatur i header `FINN-GW-KEY`. Signering gjøres i `OkHttp`-interceptoren `no.finn.android.networking.HmacSigningInterceptor` og kjører kun når forespørselen går mot `appsgw`-vertsnavnet (`isAppBackend(request)`).

**Melding som signeres** (nøyaktig som i `HmacSigningInterceptor.calculateHmac`):

```
<METHOD>;<PATH><QUERY>;<SERVICE>;<BODY>
```

- `METHOD`: forespørselens HTTP-metode i uppercase (`GET`, `POST`, …).
- `PATH`: `request.url().encodedPath()`, men tom streng dersom den er bare `"/"`.
- `QUERY`: `"?" + encodedQuery` dersom det finnes en ikke-tom querystring, ellers tom streng.
- `SERVICE`: verdien av headeren `FINN-GW-SERVICE` (eller tom streng dersom den mangler).
- `BODY`: hele request-body-en (bare `.writeTo(sink)` kalles).

Separatoren er ett semikolon (`;`) mellom hver del. Signaturen er `HMAC-SHA512(key, melding)` **base64**-kodet (standard base64, ikke url-safe), og legges i header `FINN-GW-KEY`.

**HMAC-nøkkel.** Både i prod og dev er `AppEnvironment.hmacKey = "MQD1MzLjZ2ZgLwp4Zl00ATD5YJV5ATRgLzVlBTEvLmNkAzR2"`. Denne går gjennom `SecurePreferences.decode(...)` som er to steg: først ROT13 (kun bokstaver, tall urørt), så standard base64-dekoding av resultatet, så UTF-8-dekoding. Resultatet er en 36-byte ASCII-streng: `d45ff03c-b783-44d9-b94a-bb28dbc016a6`. Nøkkelmaterialet til HMAC er `UTF-8`-bytene av denne strengen (`HmacSigningInterceptorKt.toByteString`).

**Signaturen i Python** (ingen avhengighet av `finnsig` – vi implementerer regelen selv):

```python
import base64, hashlib, hmac

HMAC_KEY = b"d45ff03c-b783-44d9-b94a-bb28dbc016a6"  # ← dekodet fra APK

def finn_gw_key(method: str, encoded_path: str, encoded_query: str,
                service: str, body: bytes = b"") -> str:
    path = "" if encoded_path == "/" else encoded_path
    query = f"?{encoded_query}" if encoded_query else ""
    msg = f"{method.upper()};{path}{query};{service};".encode("utf-8") + body
    mac = hmac.new(HMAC_KEY, msg, hashlib.sha512).digest()
    return base64.b64encode(mac).decode("ascii")
```

Merk: tidligere versjoner av denne spiken antydet at [`finnsig`](https://github.com/newis/finnsig)-biblioteket (`finn_hmac(method, path, query_string, service_header, body)`) ga samme resultat. **Formatet over er det Android-appen faktisk bruker** — hvis `finnsig` har en annen separator eller rekkefølge må vi overstyre eller implementere det selv. Verifiser dette før vi binder oss til biblioteket.

## Reverse engineering av APK-en

APK-en ligger i prosjektrot (`FINN.no_261006-ec709768_APKPure.apk`, ~102 MB) og er **ikke sjekket inn** (lagt til `.gitignore`). Den brukes bare lokalt for å finne endepunkter. **Appversjonen pinnes** mot denne APK-en i `User-Agent`.

Verktøy brukt (2026-10-10):
- **`jadx` 1.5.4** (dekompilering av DEX → Kotlin/Java). Default-heap er for stor; sett `JAVA_TOOL_OPTIONS=-Xmx3g` og bruk `--threads-count 1`. For enkeltklasser er `jadx --single-class <FQN>` raskt og minnevennlig.
- **`androguard`** (Python) for strings- og metodeskanning i DEX når full dekompilering ikke er nødvendig.
- `apktool`/`mitmproxy` ble ikke trengt; APK-en gir alt vi trenger uten emulator.

### Base-URL og miljøvariabler

Fra `no.finn.android.AppEnvironment`:

| Miljø | Gateway-URL (`gwServer`) | Web-URL |
|---|---|---|
| PRODUCTION | `https://appsgw.finn.no/` | `https://www.finn.no/` |
| STAGE | `https://dev.appsgw.finn.no/` | `https://dev.finn.no/` |

Konstantene `COUNTRY_ISO_CODE = "NO"` og `userSdrnPrefix = "sdrn:finn:user:"`. Image-CDN kommer fra `no.finn.environment.BuildConfig` og brukes ikke her.

### Statiske headere (fra `GeneralHeaderInterceptor`)

Settes på alle forespørsler mot `appsgw`:

| Header | Verdi |
|---|---|
| `User-Agent` | `HttpUserAgent.getUserAgent()` — appversjon + Android-info, bygget på klientsiden. Pinnes fra denne APK-en: `261006-ec709768`. |
| `FINN-Device-Info` | `"Android, mobile"` (eller `"Android, tablet"`). |
| `FINN-App-Installation-Id` | Visitor-ID (`SessionInfo.getVisitorId()`), lokalt generert UUID. |
| `Visitor-Id` | Samme UUID som over. |
| `Session-Id` | Session-ID per app-session. |
| `Build-Type` | `release` / `alpha` / `beta` / `debug` / `inhouse`. |
| `Ab-Test-Device-Id` | AB-testing-ID. |
| `VersionCode` | `AppVersion.getVersionCode()` (= APK versionCode `1005273389`). |
| `X-FINN-API-Version` | `"5"` (konstant for denne appversjonen). |
| `X-FINN-API-Feature` | Fra `no.finn.netcommon.Api.apiFeatures()`. |
| `x-finn-apps-adinput-version-name` | `"boatmotor"` (default, hvis ikke overstyrt). |
| `Authorization` | Satt bare når brukeren er logget inn (`SpidInfo.getAuthenticationHeader()`). Ikke nødvendig for jobbsøk. |
| `x-nmp-os-name` | `"Android"`. |
| `x-nmp-os-version` | `Build.VERSION.RELEASE`. |
| `x-nmp-device` | `Build.MODEL`. |
| `x-nmp-app-brand` | `"FINN"`. |
| `x-nmp-app-version-name` | `"261006-ec709768"` for denne APK-en. |
| `x-nmp-app-build-number` | `"1005273389"`. |
| `CMP-Advertising`, `CMP-Analytics`, `CMP-Marketing`, `CMP-Personalisation` | `"1"` eller `"0"` basert på consent. Vi setter `"0"` (ingen samtykke). |

Vi trenger ikke etterligne alle 100 % — minimumsettet som gir OK responser er `User-Agent`, `FINN-Device-Info`, `FINN-App-Installation-Id`, `X-FINN-API-Version` og de to Finn-GW-headerne. Resten legger vi til ved behov.

### Service-ruting (`FINN-GW-SERVICE`)

Appen har 108 distinkte `FINN-GW-Service`-verdier. De er endepunkt-spesifikke og rutes serverside av `appsgw.finn.no` til riktig mikrotjeneste. Full liste ligger i `docs/spikes/04-finn-services.txt` (generert med `jadx` 2026-10-10). De relevante for oss:

| Service | Brukes av |
|---|---|
| `Search-Quest-JB` | Jobbsøk via `SearchQuestClient` (indeks `Index.JOB`). Headeren settes av `okHttpClient("Search-Quest-JB")` i `no.finn.searchdata.SearchDataModuleKt`. |
| `SEARCH-AUTOCOMPLETE` | Autocomplete for søkeord. |
| `SEARCH-SAVEDSEARCH` | CRUD på lagrede søk (`/public/search`). Mest nyttig som fallback. |
| `JOB-SEARCH` | Semantisk/likhetssøk (`/search/similarity`). |
| `JOB-PROFILE` | GraphQL-endepunkt (`/graphql`) for jobbprofil, krever innlogging. |
| `JOB-ITEM`, `JOB-ACTIVITY-API`, `JOB-INSIGHTS`, `JOB-SPOTLIGHT`, `JOB-EASY-APPLY*` | Interne appflater — relevante kun hvis vi senere vil hente søknadsstatus eller full annonsetekst via API. |

### Endepunkter

**Søk** (via `no.finntech.search.quest.SearchQuest`-Retrofit-interface — kalt gjennom `SearchQuestClient`):

```
GET https://appsgw.finn.no/search/{searchkey}
    ?client=android-finn
    &<søkeparametere, QueryMap>
Headers:
    FINN-GW-Service: Search-Quest-JB
    FINN-GW-KEY: <HMAC-SHA512 base64, se signering>
    + alle statiske headere over
```

Hvor `{searchkey}` er `SearchKey.description`:

| SearchKey | Path | searchId |
|---|---|---|
| `SEARCH_ID_JOB_FULLTIME` | `job-fulltime` | 18 |
| `SEARCH_ID_JOB_PARTTIME` | `job-parttime` | 60 |
| `SEARCH_ID_JOB_MANAGEMENT` | `job-management` | 61 |
| `SEARCH_ID_JOB_AGGREGATED` | `job-aggregated` | 62 |

Appen setter alltid `include_filters=true` (eller `include_results=false` når bare filtre skal hentes). Querymap-verdier går 1:1 til URL-querystring.

Beslektede søke-endepunkter samme Retrofit-interface tilbyr (nyttig til helse-sjekk og paginering):

| Metode | Path | Formål |
|---|---|---|
| `GET` | `/count/{searchkey}` | Antall treff for et sett parametere. |
| `GET` | `/get/{searchkey}` | Hent spesifikke annonse-IDer (`?adids=X&adids=Y`). |
| `GET` | `/validate/{searchkey}` | Valider parametere. |
| `GET` | `/sort/{searchkey}` | Tilgjengelige sorteringer. |

**Lagrede søk** (`com.schibsted.nmp.savedsearchdata.data.remote.SavedSearchesService`):

```
GET  https://appsgw.finn.no/public/search?clientId=android-finn[&id=…&type=…&rows=…&vertical=…]
POST https://appsgw.finn.no/public/search?clientId=android-finn   (body = SavedSearchApi)
PUT  https://appsgw.finn.no/public/search?clientId=android-finn   (body = SavedSearchApi)
DELETE https://appsgw.finn.no/public/search?id=<id>&clientId=android-finn
Header: FINN-GW-SERVICE: SEARCH-SAVEDSEARCH
```

**Annonsedetalj.** Det finnes ingen dedikert `JOB-ITEM`-Retrofit-interface i appen; jobbannonser åpnes via WebView på `https://www.finn.no/job/ad/{finnkode}`. Søkeresponsen fra `/search/job-*` inneholder likevel annonseteksten og strukturerte felt (tittel, bedrift, sted, publisert, ad-type, utløpsdato, kontaktpersoner), så for vårt bruk trengs ikke et separat detaljkall. Hvis vi senere ser at felt mangler, er alternativene (i prioritert rekkefølge):

1. Scrape `https://www.finn.no/job/ad/{finnkode}` (offentlig web, ingen HMAC). JSON-LD ligger som regel i `<script type="application/ld+json">`.
2. Prøve generelt `GET adview/{adId}` med `FINN-GW-SERVICE: ADVIEW-PROVIDER-RC` (brukes for recommerce; usikkert om det dekker jobb).

### Query-parametere for jobbsøk

Query-parameterne til `/search/{searchkey}` speiler Finns web-filter 1:1. Vi har ikke verifisert hver enkelt mot APK-en (verdier bygges dynamisk fra `JobLocationPersistenceRepositoryImpl` og filter-UI), men følgende er sikre fra både web og APK-ens parse-logikk:

| Parameter | Verdier (eksempler) |
|---|---|
| `occupation` | ID-er for yrkeskategori (f.eks. `0.23` = IT-utvikling). Finnes i filter-metadata; hent via `GET /search/{searchkey}` med `include_results=false`. |
| `location` | Finn-geografi-ID-er, f.eks. `0.20061` (Oslo) eller `norge`. |
| `experience` | `0`, `1`, `2`, `3`, `4` (ingen, 1–3 år, 3–5, …). |
| `education` | `0`, `1`, `2`, …  (ingen, bachelor, master, …). |
| `extent` | `fulltid` / `deltid`. |
| `published` | `1`, `3`, `7` (dager siden publisert). |
| `page` | `1`, `2`, … |
| `sort` | Hentes dynamisk via `/sort/{searchkey}`. |
| `include_filters` | `true` for å få filter-metadata i responsen. |

Riktig fremgangsmåte for fase 1: lag ett `include_results=false&include_filters=true`-kall per `searchkey`, cache svaret under `data/cache/finn/filters/<searchkey>.json`, og bruk filter-definisjonene til å mappe menneskevennlige verdier (fra `config/sources.yaml`) til Finns ID-er.

### Verifiserings-sjekkliste før `finn_api.py` skrives

Når `curl` ut en kjent-god forespørsel (vi vet nøkkelen stemmer dersom responsen ikke er `403 { "code": "SIGNATURE_INVALID" }`):

```bash
METHOD=GET
PATH="/search/job-fulltime"
QUERY="client=android-finn&location=norge&include_filters=true"
SERVICE="Search-Quest-JB"
BODY=""
MSG=$(printf '%s;%s?%s;%s;%s' "$METHOD" "$PATH" "$QUERY" "$SERVICE" "$BODY")
KEY="d45ff03c-b783-44d9-b94a-bb28dbc016a6"
SIG=$(printf '%s' "$MSG" | openssl dgst -sha512 -hmac "$KEY" -binary | base64 -w0)

curl -sS "https://appsgw.finn.no${PATH}?${QUERY}" \
  -H "FINN-GW-Service: ${SERVICE}" \
  -H "FINN-GW-KEY: ${SIG}" \
  -H "User-Agent: FINN/261006-ec709768 (Android 14; FINN-Device-Info: Android, mobile)" \
  -H "FINN-Device-Info: Android, mobile" \
  -H "X-FINN-API-Version: 5" \
  -H "x-nmp-app-brand: FINN"
```

Dette kallet må testes **før** vi bygger `finn_api.py`. Returnerer serveren 403 på signatur betyr enten (a) separator feil, (b) base64-variant feil, (c) nøkkel feil, eller (d) tomfelt-regelen (`"/"` → `""`) misforstått.

## Tenkt dataflyt (`FinnApiSource`)

```
config/sources.yaml  (søkedefinisjoner: rolle, geo, erfaring, utdanning)
        │
        ▼
  for hver søkedefinisjon:
    GET /search/<searchkey>?client=android-finn&<filtre>&page=N
    Headers: FINN-GW-Service: Search-Quest-JB, FINN-GW-KEY: <HMAC-SHA512 base64>
    ─► full liste med annonser (Finn-kode, tittel, bedrift, sted, publisert, teaser-tekst)
        │
        ▼
  normaliser → RawJob
```

Søkeresponsen inneholder tilstrekkelig data per annonse til at vi ikke trenger et separat detaljkall. Når det likevel mangler felt bruker vi fallbackene i §Reverse engineering → Endepunkter → Annonsedetalj.

- **Cursor:** per søkedefinisjon lagres høyeste sette `publishedAt` i `source_state`. Ved neste kjøring hentes bare nyere annonser.
- **Rate-limit:** ett kall per 2–3 sekunder, bak felles HTTP-lag (§4.1). Håndterer 429 med backoff.
- **Cache:** rå respons i `data/cache/finn/<searchkey>-<cursor>.json` i 30 dager, slik at parsere kan utvikles mot ekte data uten nye kall.
- **Prefiltering:** API-et tar `experience`- og `education`-parametere som speiler Finns egne filtre. Setter vi disse til "ingen erfaring/junior" + "ingen/bachelor" bevarer vi tillitsnivået "forhåndsfiltrert" fra forrige design (§5.1).

## Søk som konfigurasjon

I stedet for 5 lagrede søk på Finn, defineres de samme søkene i `config/sources.yaml`:

```yaml
finn:
  enabled: true
  base_url: https://appsgw.finn.no/
  client: android-finn
  app_version: 261006-ec709768      # pin fra APK
  searches:
    - id: it_oslo
      searchkey: job-fulltime
      service_header: Search-Quest-JB
      params:
        occupation: ["0.23"]           # IT-utvikling (verifiser mot /search/job-fulltime?include_results=false)
        location: ["0.20061"]          # Oslo
        experience: ["0", "1"]         # ingen, 1–3 år
        education: ["0", "1"]          # ingen, bachelor
      job_type_hint: null
      geography: oslo_omegn
    - id: it_norge
      searchkey: job-fulltime
      service_header: Search-Quest-JB
      params: { occupation: ["0.23"], location: ["norge"], experience: ["0","1"], education: ["0","1"] }
      geography: norge
    - id: trainee
      searchkey: job-fulltime
      service_header: Search-Quest-JB
      params: { q: ["trainee"], location: ["norge"] }
      job_type_hint: trainee
      geography: norge
    - id: graduate
      searchkey: job-fulltime
      service_header: Search-Quest-JB
      params: { q: ["graduate"], location: ["norge"] }
      job_type_hint: graduate
      geography: norge
    - id: summer
      searchkey: job-fulltime
      service_header: Search-Quest-JB
      params: { q: ["summer OR sommerjobb OR internship"], location: ["norge"] }
      job_type_hint: summer
      geography: norge
```

Parameterverdiene (`occupation`-ID, `location`-ID, `experience`/`education`-koder) må hentes fra ett `include_results=false&include_filters=true`-kall per `searchkey` — se §Reverse engineering → Query-parametere.

## Risiko

| # | Risiko | Håndtering |
|---|---|---|
| F1 | **Juridisk/ToS:** Finn forbyr automatisert innhenting uten skriftlig samtykke. Mobil-API-et er ikke publisert for tredjepart. Bruken er privat, lokal og lavvolum (1 bruker, ~5 søk per døgn), men ligger likevel i en gråsone. | Lavvolum og rate-limiting. Verktøyet er personlig og ikke publisert. Brukeren tar beslutningen bevisst og er informert. Dette er en bevisst risiko, ikke en forglemmelse. |
| F2 | **Signaturen brytes** når Finn roterer HMAC-nøkkelen eller endrer meldingsformat. | Nøkkelen er en konstant i `finn_sig.py` og kan oppdateres ved å dekompilere ny APK og dekode `AppEnvironment.PRODUCTION_HMAC_KEY` på nytt (ROT13 + base64). Kildehelse-sjekken (§12) oppdager 401/403 raskt. |
| F3 | **Endepunkt endres** mellom app-versjoner. | Lås appversjon i `User-Agent` og `X-FINN-APP-VERSION`. Last ned ny APK og oppdater når det trengs. |
| F4 | **Deteksjon/sperring** ved uvanlig trafikkmønster. | Realistiske headere fra APK-en, rate-limit, retry med backoff, ingen parallelle kall, random jitter. |
| F5 | ~~**Vedlikehold av `finnsig`.**~~ *Ikke lenger relevant: vi implementerer signeringen selv i `finn_sig.py` basert på APK-dekompileringen. Ingen tredjeparts-bibliotek i den varme stien.* |

Fallback om API-et blir ubrukelig: en manuell "lim inn annonsetekst"-flyt i dashboardet (`manual`-kilden er allerede planlagt, §4.1 → `job_sources.source = manual`). Varsel-flyten fra forrige design (IMAP) er droppet og er ikke en lett vei tilbake.

## Hva som er avklart og hva som gjenstår

**Avklart (per 2026-10-10):**
- Base-URL: `https://appsgw.finn.no/` (prod).
- Signeringsalgoritme (HMAC-SHA512, base64) og nøkkel (`d45ff03c-b783-44d9-b94a-bb28dbc016a6`).
- Nøyaktig melding som signeres (`METHOD;PATH?QUERY;SERVICE;BODY`).
- Service-header for jobbsøk (`Search-Quest-JB`).
- Jobbsøk-endepunkt (`GET /search/{job-fulltime|job-parttime|job-management|job-aggregated}`).
- Full liste over `FINN-GW-Service`-verdier (108 stk, lagret i `docs/spikes/04-finn-services.txt`).
- Statiske headere og hvordan de bygges.
- Lagrede søk brukes ikke fra Finn-kontoen; vi bygger søk fra bunnen av via `/search/{searchkey}`.
- Annonsedetaljkall er ikke nødvendig i første omgang — søkeresponsen inneholder annonseteksten.

**Gjenstår (fase 1):**
- Verifisere HMAC-signeringen mot et levende kall (`curl`-oppskriften over).
- Hente filter-metadata (`include_results=false`) per `searchkey` og mappe `config/sources.yaml`-verdier til Finns ID-er for `occupation`, `location`, `experience`, `education`.
- Implementere `src/jobsearcher/sources/finn_api.py` + `finn_sig.py` basert på dette.
- Beslutte paginering: `page=N` vs. cursor. Mest sannsynlig `page` + lokalt `publishedAt`-filter.

## Oppdatering 2026-10-10: fase 0b verifisert mot levende API

Kjørt med et lite Python-skript (stdlib `hmac`/`urllib`, signering nøyaktig som §Signering) fra brukerens maskin. ~12 kall totalt.

**Bekreftet:**
- **Signeringen er riktig.** Usignert kall → `403` (tom body). Signert kall slipper gjennom gatewayen. Ingen innlogging, konto eller brukerspesifikk nøkkel trengs.
- Minimumsheaderne i §Statiske headere holder (`User-Agent`, `FINN-Device-Info`, `X-FINN-API-Version`, `x-nmp-app-brand`, `FINN-App-Installation-Id`/`Visitor-Id` med lokalt generert UUID, `FINN-GW-Service`, `FINN-GW-KEY`).

**Rettelser til spiken over:**

| Antakelse over | Faktisk |
|---|---|
| Path er `/search/job-fulltime` | Path er **enum-navnet**: `/search/SEARCH_ID_JOB_FULLTIME` (også `_PARTTIME`, `_MANAGEMENT`, `_AGGREGATED`). `job-fulltime` gir `400` (Spring kan ikke konvertere til `SearchKey`). |
| Søkeresponsen inneholder annonseteksten | **Nei.** Hver `doc` har `id`/`ad_id`, `heading`, `job_title`, `company_name`, `location`, `locations`, `work_locations`, `coordinates`, `published`/`timestamp` (ms), `deadline` (ms), `no_of_positions`, `extras` (erfaring/utdanning-ID-er), `canonical_url`, `logo`. Ingen beskrivelse eller kontaktpersoner. |
| `/get/{searchkey}?adids=` henter annonser | `404` på `appsgw`. Ikke brukbart. |
| Parameter `experience` | Heter `work_experience`. |
| `location=norge`, `0.20061` = Oslo | Hierarkiske ID-er: `0.20001` = Norge, `1.20001.20061` = Oslo, `1.20001.20003` = Akershus, `2.…` = kommune. |

**Annonsetekst:** den offentlige annonsesiden `https://www.finn.no/job/ad/{id}` (vanlig GET, ingen HMAC) har en `<script type="application/ld+json">` med `{"script:ld+json": {"@type": "JobPosting", ...}}`. Den inneholder `description` (HTML), `title`, `hiringOrganization`, `jobLocation`, `datePosted`, `validThrough`, `employmentType`, `identifier`, `url`. Siden er UTF-8. Dette er det samme som appens WebView viser.

**Filter-ID-er (fra `SEARCH_ID_JOB_FULLTIME`, 2026-10-10):**

| Filter | Verdier |
|---|---|
| `work_experience` | `455` ingen erfaring, `456` junior, `457` erfaren, `458` leder |
| `education` | `459` doktorgrad, `461` fagbrev, `462` fagskole, `463` høyskole/univ. høyere, `464` høyskole/univ. lavere, `465` ingen, `466` vgs studieforb., `467` vgs yrkesfag |
| `job_duration` | `3951` fast, `8098` trainee, `1816` sommer/sesong, `3659` vikariat, `3952` engasjement, `8099` prosjekt, `8900` lærling, `8901` bemanningsbyrå, `3954` selvstendig |
| `extent` | `3947` heltid, `3942` deltid |
| `occupation` | Hierarkisk, f.eks. `0.23` IT utvikling, `0.22` IT drift og vedlikehold |
| `published` | `1` = nye i dag |
| `applicationdeadline` | `1`, `3`, `7` |

Øvrige filtre: `q` (fritekst), `industry`, `job_sector`, `working_language`, `home_office`, `manager_role`, `polylocation`/`radius`/`bbox`. Flere verdier for samme filter sendes som gjentatt parameter (`location=A&location=B`).

**Søk og paginering:**
- `sort=PUBLISHED_DESC` virker (standard er `RELEVANCE`).
- 50 annonser per side. `metadata.paging = {param: "page", current, last}`, `metadata.is_end_of_paging`. `last` er maks 50 (ufiltrert: 28 875 treff, `last: 50`), så dype søk må snevres inn med filtre.
- `metadata.result_size.match_count` teller stillinger, `group_count` teller annonser.
- Testsøk `occupation=0.23` + Oslo + Akershus + `work_experience=455,456` + `PUBLISHED_DESC` → `200`, 66 annonser over 2 sider.
- `include_results=false&include_filters=true` gir bare `filters` + `metadata` (ingen `docs`).

**Fixtures:**
- `tests/fixtures/finn/filters_search_id_job_*.json` (filter-metadata per searchkey, sporet i git, ingen persondata).
- `tests/fixtures/private/finn/search_it_oslo_junior.json` (rå søkerespons med ekte annonser, gitignored).

**Konsekvens for designet:** Finn blir to steg: signert søk (liste) og så detaljhenting fra annonsesiden for nye annonser som har passert hardfilteret. Se ARCHITECTURE §4.2 (v0.9).
