# Spike 01: Finn.no

**Dato:** 2026-10-10
**Konklusjon:** Finn forbyr eksplisitt automatisert innhenting. Vi skraper **ikke** Finn. Finn-stillinger hentes via Finn sine egne e-postvarsler (lagrede søk), og annonseteksten hentes automatisk fra andre kilder når samme stilling finnes der.

## Funn

### robots.txt og vilkår
Øverst i `https://www.finn.no/robots.txt` (hentet 2026-10-10):

> Notice: Crawling FINN.no is prohibited unless you have written permission.

Den norske teksten under henviser til vilkårene: bruk av automatiserte tjenester (roboter, spidere, indeksering) og annen systematisk eller regelmessig bruk er ikke tillatt uten eksplisitt samtykke fra FINN.no. Innholdet er også beskyttet etter åndsverksloven.

I tillegg:
- `/job/` er blokkert for GPTBot.
- Flere jobb-søkemønstre er blokkert (`/job*industry=*occupation=*`, `/job/search?*abTestKey=`).
- AI-crawlere (ClaudeBot, anthropic-ai m.fl.) har egne restriksjoner.

En daglig skraper av søkesidene er nettopp "regelmessig bruk av automatiserte tjenester". Arkitekturdokumentet v0.1 forutsatte at dette var en akseptabel risiko ved lavt volum. Med et så eksplisitt forbud forkaster vi den tilnærmingen.

### NAV er ikke et sikkerhetsnett for Finn
NAV sin stillingsfeed (se spike 02) sier eksplisitt at stillinger fra Finn.no **ikke** er med. NAV og Finn er derfor to separate kilder, ikke overlappende.

### Finn sine egne varsler
Finn tilbyr "Lagrede søk" med varsling ([Finn hjelpesenter: Varslinger på e-post](https://hjelpesenter.finn.no/hc/no/articles/22651852160786-Varslinger-p%C3%A5-e-post)):
- Brukeren lagrer et filtrert søk og huker av for varsel.
- Finn sender én daglig e-post med nye treff fra lagrede søk og fulgte bedrifter.
- Dette er en funksjon Finn selv tilbyr til nettopp dette formålet.

## Valgt løsning

```
Finn (lagrede søk, 1 per jobbtype/rolle)
   │  daglig e-post
   ▼
Gmail ── filter → etikett "JobSearcher/Finn"
   │  IMAP (app-passord, samme som SMTP)
   ▼
FinnEmailSource: parser tittel, bedrift, sted, lenke og Finn-kode
   │
   ▼
Pipeline (dedupe, hardfilter, scoring på det som finnes)
   │
   ▼
Automatisk berikelse (ingen manuelle steg):
   1. krysskilde-match mot NAV / ATS / karrieresider
   2. websøk etter annonsen hos arbeidsgiver (finn.no blokkert)
   3. ellers: scoring på tittel/bedrift/sted, confidence: low
```

**Konsekvens:** Finn-stillinger som ikke finnes andre steder, blir bare scoret på tittel, bedrift og sted. Brukeren ønsker ingen manuelle steg. Hvor stor andel dette gjelder, er et åpent spørsmål som måles etter et par ukers drift (ARCHITECTURE §19 #1).

## Åpne punkter
- **Lagrede søk (satt opp 2026-10-10):** IT utvikling Oslo, IT utvikling Norge, Trainee Norge, Graduate Norge, Summer Internship Norge. Alle med Finns filtre for erfaring (ingen/junior) og utdanning (ingen/høyskole lavere nivå). Annonsene regnes derfor som forhåndsfiltrert på nivå.
- **Format på varsel-e-posten:** venter på første varsel (`tests/fixtures/private/finn-varsel-1.eml`). Avklarer også om e-posten viser hvilket lagret søk annonsen kom fra.
- **Skriftlig samtykke:** Brukeren kan be Finn om tillatelse til personlig, lavfrekvent innhenting. Blir svaret ja, kan det legges til en adapter som henter enkeltannonser. Den lages ikke uten samtykke.
- **Uoffisielle mobil-API-er og signaturnøkler fra Finn-appen:** brukes ikke. Det er å omgå Finns tilgangskontroll og strider mot vilkårene.
