# Spike 04: Kilder for trainee-, graduate- og sommerjobber

**Dato:** 2026-10-10
**Konklusjon:** Tre lag:
1. NAV-feeden fanger mye allerede (inkluderer ATS-annonser).
2. Teamtailor har offisielle RSS-feeder per karriereside.
3. En kuratert selskapsliste med "sideovervåker" tar resten.

Jobbnorge har ikke et åpent API vi kan bruke.

## Funn

| Kilde | Tilgang | Vurdering |
|---|---|---|
| **NAV stillingsfeed** | Offisielt API | Inneholder annonser fra tredjeparter og ATS-systemer. Trolig den bredeste dekningen av trainee/graduate utenom Finn. |
| **Teamtailor** | Offisiell RSS: `https://<karriereside>/jobs.rss` ([Teamtailor support](https://support.teamtailor.com/en/articles/11171756-rss-feed-how-to-guide)) | Tittel, beskrivelse, URL, sted, remote-status, avdeling. Brukes av mange norske tech-selskaper og konsulenthus. **Prioritet 1.** |
| **Jobbnorge** (offentlig sektor) | API-et krever arbeidsgiver-ID fra arbeidsgiveren selv. Fant ingen åpen RSS. | Ikke egen adapter. Offentlige stillinger kommer trolig via NAV. |
| **Jobylon, Webcruiter, ReachMee, Workday** | Ikke undersøkt | Undersøkes bare hvis et ønsket selskap bruker dem og ikke dukker opp i NAV. |
| **Karriereside uten feed** | Ingen | Sideovervåker: henter én side per selskap per dag, hasher hovedinnholdet og varsler ved endring. LLM-uttrekk bare ved endring. Respekterer `robots.txt` per domene. |
| **LinkedIn** | Forbyr skraping | Utenfor scope |

## Kuratert selskapsliste (startforslag for `config/sources.yaml`)

Kandidater med kjente trainee-, graduate- eller sommerprogrammer i Oslo-området. ATS-type og URL fylles ut ved implementering.

- **Bank/finans:** DNB, SpareBank 1, Storebrand, Gjensidige, Vipps MobilePay
- **Energi/industri:** Equinor, Statnett, Statkraft, Hafslund, Aker BP, Kongsberg
- **Telekom/media:** Telenor, Telia, Schibsted, NRK
- **Offentlig:** NAV IT, Skatteetaten, Statens vegvesen, Avinor, Posten Bring, Vy, Ruter
- **Konsulent:** Bekk, Capgemini, Accenture, Sopra Steria, Knowit, Kantega, Miles, Netcompany, Computas, Itera, Variant, Twoday, Tietoevry
- **Produkt:** Finn/Vend, Kahoot, Visma, Sector Alarm, Oda

Brukeren redigerer listen fritt.

## Konsekvenser for designet
- `TeamtailorSource`: én RSS-URL per selskap i `sources.yaml`.
- `PageWatcherSource`: URL + valgfri CSS-selektor per selskap. Endringshash lagres i DB.
- Dedupe mot NAV på fingerprint, siden samme annonse kan komme fra både ATS og NAV.
- Etter 2–4 uker i drift: sjekk hvilke kilder som faktisk gir unike treff, og fjern de som ikke gjør det.

## Update 2026-10-10
Brukeren har gått gjennom startlisten og godkjent den som den er. Dedupe mot NAV/Finn skjer på normalisert søknads-URL før fingerprint (ARCHITECTURE §4.5).

## Oppdatering 2026-10-11: selskapslisten sjekket live (fase 5)

Hver karriereside ble hentet én gang, og `https://<slug>.teamtailor.com/jobs.rss` ble prøvd per selskap. Resultatet står i `config/sources.yaml`.

| Kilde | Selskaper |
|---|---|
| **Teamtailor-RSS** (9) | Vipps MobilePay (`vipps`), Hafslund, Aker BP, Schibsted, Skatteetaten, Computas, Itera, Twoday, Oda (`careers.oda.com`) |
| **Sideovervåker** (14) | Bekk, Kantega (`jobb.kantega.no`), Variant, Knowit (talentprogram og sommerstudenter), Sopra Steria, Capgemini (studenter og nyutdannede), Netcompany (vacancies), Kongsberg (vacancies), NRK, Statnett (studenter), DNB (studenter og nyutdannede), Gjensidige (student), Telenor, Statens vegvesen (traineeprogram) |
| **Ikke med, dekkes av NAV/Finn** | Equinor, Accenture, Storebrand (Workday); Statkraft (SmartRecruiters); Avinor (Webcruiter); Telia, Posten Bring, Kahoot (listene lastes med JavaScript); Vy (bot-sjekk, svarer 202); Tietoevry (403); Visma (Teamtailor-feeden er tom, karrieresiden samler flere ATS-er); Vend/Finn (stillingene ligger på Finn); Sector Alarm (bare kategorier på siden); SpareBank 1, Miles, Ruter (fant ingen karriereside med liste); NAV IT (i NAV-feeden) |

Funn:
- Mange karrieresider er oversiktssider som bare lenker til en underside. Den første live-kjøringen (18 sider) ga 0 utlysninger på 10 av dem. Listen bruker derfor undersidene for studenter, trainee og ledige stillinger der de finnes.
- Bekk lister stillinger fra Lever (`jobs.lever.co/bekk`), som har et offentlig JSON-API. Ikke brukt: sideovervåkeren fanger dem.
- Sopra Steria pakker hele siden i ett `<form>` (ASP.NET), så sideovervåkeren beholder `<form>` (annonserensingen fjerner den).
- Første live-kjøring mot en DB-kopi (uten scoring): Teamtailor 105 stillinger, 18 etter hardfilteret; karrieresidene 86 utlysninger, 9 etter hardfilteret, blant dem Kantega «Sommerjobb som utvikler 2027», Telenor «summer internship», Computas NXT 2027 (via Teamtailor) og Sopra Steria graduate og sommerjobb. Extractor: 18 kall, $0,036.
