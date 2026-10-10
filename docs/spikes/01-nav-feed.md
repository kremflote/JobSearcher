# Spike 02: NAV stillingsfeed (pam-stilling-feed)

**Dato:** 2026-10-10
**Konklusjon:** Godt egnet som primærkilde ved siden av Finn-varslene. Den er offisiell, gratis og strukturert, og har frist og kontaktpersoner som egne felt. Den inneholder **ikke** Finn-annonser, men den inneholder annonser fra tredjeparter og ATS-systemer. Den dekker derfor også en del trainee- og graduate-stillinger.

## Funn

- **Gammelt API:** `pam-public-feed` er avviklet (mai 2025, repoet er arkivert). Erstattet av **pam-stilling-feed**. Dokumentasjon: https://navikt.github.io/pam-stilling-feed/
- **Endepunkt:** `https://pam-stilling-feed.nav.no/api/v1/feed`. Hver entry har en `url` til full annonse.
- **Modell:** Hendelsesfeed, ikke søk. Hver endring på en annonse gir en ny entry, og siste entry er gjeldende tilstand. Siden har `next_url`. `ETag` og `If-Modified-Since` gir 304 når ingenting er nytt.
- **Autentisering:** Bearer-JWT.
  - **Offentlig token:** publisert av NAV, roterer uregelmessig. Greit for utvikling.
  - **Privat token:** bestilles på e-post til nav.team.arbeidsplassen@nav.no med skriftlig aksept av vilkårene og kontaktinfo. **Anbefalt for daglig drift.**
- **Ingen filtrering på serversiden** (yrke, sted, nøkkelord). All filtrering skjer hos oss. Det er greit: ca. 1000 nye annonser per dag, og feed-entries er små.
- **Felt i annonsen:**
  - Datoer: `published`, `expires`, `updated`
  - Arbeidssted: land, adresse, by, postnr, fylke, **kommune**
  - **Kontakter:** navn, e-post, telefon, rolle, tittel
  - **Søknadsfrist** og søknads-URL
  - Arbeidsgiver: navn, orgnr, beskrivelse, hjemmeside
  - Yrkeskategorier med koder
  - Stillingstittel, ansettelsesform, omfang, oppstart, antall stillinger, sektor
  - `source` og `sourceurl`
- **Finn er ekskludert:** "Vacancies from Finn.no are not included in the API."

## Vilkår (arbeidsplassen.nav.no/vilkar-api)
- Fri bruk for alle. NAV kan stenge tilgang ved misbruk.
- Annonser som blir inaktive eller slettes, må fjernes umiddelbart fra visningen. Oppdateringer må speiles.
- "Søk"-knappen må lenke direkte til arbeidsgivers eller systemleverandørens søknadsfunksjon.
- Personopplysninger (kontaktpersoner): vi er selvstendig behandlingsansvarlig og må slette data når de ikke lenger trengs.

## Konsekvenser for designet
- `NavFeedSource` lagrer siste `next_url`/`ETag` som cursor i DB, og leser bare nye entries ved hver kjøring.
- Første kjøring: start fra et tidspunkt (f.eks. 30 dager tilbake), ikke fra begynnelsen.
- Inaktive annonser → `jobs.active = false`. Er jobben ikke søkt, skjules den i dashboardet.
- Frist og kontakter hentes direkte fra strukturerte felt. LLM-uttrekk brukes bare som fallback.
- Personvern: kontaktinfo slettes 90 dager etter at en jobb er inaktiv, med mindre det finnes en søknad.

## Åpne punkter
- Bestille privat token (brukerens navn og e-post).
- Sjekke i praksis hvilke `source`-verdier som finnes, og hvor mange trainee/graduate-stillinger som kommer via ATS.
