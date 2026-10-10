# Spike 04: Finn via mobil-API

**Dato:** 2026-10-10
**Status:** Beslutning tatt. Erstatter spike 01 (Finn via e-postvarsler).
**Konklusjon:** Finn-stillinger hentes direkte fra Finns mobil-API, det samme API-et Android-appen bruker. Hver forespørsel signeres med en HMAC-signatur (`FINN-GW-KEY`) via biblioteket [`finnsig`](https://github.com/newis/finnsig). Endepunktene reverse-engineeres fra Finns Android-APK (`FINN.no_261006-ec709768_APKPure.apk`, i rot — ikke sjekket inn i git). Varsler via Gmail/IMAP er droppet.

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

## Signering: `finnsig`

Finn signerer HTTP-forespørsler med en HMAC-SHA512-signatur i header `FINN-GW-KEY`. Biblioteket `finnsig` (MIT, Python) implementerer dette:

```python
from finnsig import finn_hmac

finn_gw_key = finn_hmac(
    http_method="GET",
    path="/search/jobs",
    query_string="occupation=it-utvikling&location=norge",
    service_header="APPS-SEARCH",   # eksakt verdi fra APK-en
    body="",
)
# → base64-kodet HMAC-SHA512 over (metode + path + query + service_header + body)
```

Nøkkelen er obfuskert i APK-en og dekodes av biblioteket. Service-headeren er endepunkt-spesifikk — eksakte verdier finnes ved å dekompilere APK-en.

## Reverse engineering av APK-en

APK-en ligger i prosjektrot (`FINN.no_261006-ec709768_APKPure.apk`, ~102 MB) og er **ikke sjekket inn** (lagt til `.gitignore`). Den brukes bare lokalt for å finne endepunkter.

Verktøy:
- **`apktool`** for å pakke ut ressurser og smali.
- **`jadx`** for å dekompilere DEX til lesbar Java/Kotlin.
- **`mitmproxy`** på en Android-emulator med systemsertifikat for å observere faktiske forespørsler (sertifikat-pinning må omgås — ikke nødvendigvis mulig uten Frida; i praksis holder det ofte å finne endepunktene i dekompilert kode).

Mål for utforskningen (ikke gjort ennå; gjøres når fase 1 starter):

| Spørsmål | Hvor det ligger |
|---|---|
| Base-URL for API-et | Strings i dekompilert kode, typisk `https://www.finn.no/api/...` eller `https://api.finn.no/...` |
| Søkeendepunkt for jobbannonser (`job-fulltime` m.fl.) | Retrofit-interfacer i dekompilert kode |
| Detaljendepunkt for enkeltannonse (gitt Finn-kode) | Samme |
| Parametere: `occupation`, `location`, `experience`, `education`, `published`, `page` | Request-byggere eller URL-templates |
| Service-header-verdier per endepunkt (`APPS-SEARCH`, `APPS-ADVIEW`, …) | Konstanter nær HMAC-koden |
| Statiske headere (`User-Agent`, `X-FINN-APP-VERSION`, osv.) | HTTP-interceptor |
| Hvordan "lagrede søk" / varsler er modellert serverside (hvis brukbart) | Søk etter `savedsearch` / `notification` |

Når disse er funnet, dokumenteres de i en kort tabell her og i `config/sources.yaml`.

## Tenkt dataflyt (`FinnApiSource`)

```
config/sources.yaml  (søkedefinisjoner: rolle, geo, erfaring, utdanning)
        │
        ▼
  for hver søkedefinisjon:
    GET /search/jobs?... + FINN-GW-KEY   ─►  liste med annonse-stubs (Finn-kode, tittel, bedrift, sted, publisert)
        │
        ▼
  for hver nye Finn-kode (ikke sett før):
    GET /ad/<finnkode>  + FINN-GW-KEY    ─►  full annonse (tekst, krav, frist, kontakter, søknadslenke)
        │
        ▼
  normaliser → RawJob
```

- **Cursor:** per søkedefinisjon lagres høyeste sette `publishedAt` i `source_state`. Ved neste kjøring hentes bare nyere annonser.
- **Rate-limit:** ett kall per 2–3 sekunder, bak felles HTTP-lag (§4.1). Håndterer 429 med backoff.
- **Cache:** rå respons i `data/cache/finn/<finnkode>.json` i 30 dager, slik at parsere kan utvikles mot ekte data uten nye kall.
- **Prefiltering:** API-et tar `experience`- og `education`-parametere som speiler Finns egne filtre. Setter vi disse til "ingen erfaring/junior" + "ingen/bachelor" bevarer vi tillitsnivået "forhåndsfiltrert" fra forrige design (§5.1).

## Søk som konfigurasjon

I stedet for 5 lagrede søk på Finn, defineres de samme søkene i `config/sources.yaml`:

```yaml
finn:
  enabled: true
  signing:
    service_header: APPS-SEARCH      # ← fylles ut etter APK-dekompilering
  searches:
    - id: it_oslo
      params:
        occupation: it-utvikling
        location: oslo
        experience: ["none", "junior"]
        education: ["none", "bachelor"]
      job_type_hint: null
      geography: oslo_omegn
    - id: it_norge
      params: { occupation: it-utvikling, location: norge, experience: [none, junior], education: [none, bachelor] }
      geography: norge
    - id: trainee
      params: { q: trainee, location: norge }
      job_type_hint: trainee
      geography: norge
    - id: graduate
      params: { q: graduate, location: norge }
      job_type_hint: graduate
      geography: norge
    - id: summer
      params: { q: "summer OR sommerjobb OR internship", location: norge }
      job_type_hint: summer
      geography: norge
```

Parameternavn og verdier er plassholdere — eksakte navn kommer fra APK-en.

## Risiko

| # | Risiko | Håndtering |
|---|---|---|
| F1 | **Juridisk/ToS:** Finn forbyr automatisert innhenting uten skriftlig samtykke. Mobil-API-et er ikke publisert for tredjepart. Bruken er privat, lokal og lavvolum (1 bruker, ~5 søk per døgn), men ligger likevel i en gråsone. | Lavvolum og rate-limiting. Verktøyet er personlig og ikke publisert. Brukeren tar beslutningen bevisst og er informert. Dette er en bevisst risiko, ikke en forglemmelse. |
| F2 | **Signaturen brytes** når Finn roterer HMAC-nøkkelen eller endrer meldingsformat. | `finnsig` oppdateres av vedlikeholderen; vi kan vendre inn fork eller oppdatere nøkkelen selv ved å dekompilere ny APK. Kildehelse-sjekken (§12) oppdager 401/403 raskt. |
| F3 | **Endepunkt endres** mellom app-versjoner. | Lås appversjon i `User-Agent` og `X-FINN-APP-VERSION`. Last ned ny APK og oppdater når det trengs. |
| F4 | **Deteksjon/sperring** ved uvanlig trafikkmønster. | Realistiske headere fra APK-en, rate-limit, retry med backoff, ingen parallelle kall, random jitter. |
| F5 | **Vedlikehold av `finnsig`.** Lite bibliotek, én vedlikeholder. | Pin eksakt versjon. Legg koden under `src/jobsearcher/sources/finn/sig.py` som vendret kopi hvis prosjektet dør. |

Fallback om API-et blir ubrukelig: en manuell "lim inn annonsetekst"-flyt i dashboardet (`manual`-kilden er allerede planlagt, §4.1 → `job_sources.source = manual`). Varsel-flyten fra forrige design (IMAP) er droppet og er ikke en lett vei tilbake.

## Hva som er avklart og hva som gjenstår

**Avklart:**
- Overordnet tilnærming (API + `finnsig`).
- Hvor APK-en ligger (prosjektrot, gitignored).
- Hvilke verktøy som brukes til reverse engineering.
- Hvordan søk flyttes fra Finns UI til `config/sources.yaml`.
- At tillitsnivået "forhåndsfiltrert" (§5.1) kan bevares via API-parametere.

**Gjenstår (fase 1):**
- Dekompilere APK-en og fylle ut tabellen under §Reverse engineering.
- Verifisere `finnsig` mot et eksempel-kall.
- Konkret skjema for `config/sources.yaml` (over er et utkast).
- Avgjøre om "lagrede søk/varsler" i Finn-kontoen kan brukes serverside eller om vi bygger søk fra bunnen av. Rimelig gjetning: fra bunnen av, det er enklere.
