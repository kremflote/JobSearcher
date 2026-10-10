# JobSearcher: frontend-design

> Status: v0.7 (2026-10-10). F0, F1 og F2 er bygget, og F1 og F2 er koblet til ekte API (backend-fase 1–2). Neste bølge: F3 (søknadseditor), bygget rett før backend-fase 3.
> Dokumentet eier UI-designet: skjermer, layout, komponenter, API-kontrakt og frontend-bølger. Resten av systemet står i [ARCHITECTURE.md](ARCHITECTURE.md). Regler for vedlikehold står i `AGENTS.md`.

## Endringslogg

| Versjon | Dato | Endring |
|---|---|---|
| v0.7 | 2026-10-10 | Backend-fase 1–2: ekte API for oversikt, jobber, triage, tracker, tasks og logg (§7.1). F3 og F4 flyttes etter backend-fase 2 (ARCHITECTURE §17 v0.11). |
| v0.6 | 2026-10-10 | F2 (tracker) bygget. Kortet i API-et har `allowed_next` og `previous_status`, så UI-et viser bare lovlige overganger uten egen kopi av tabellen (ARCHITECTURE §9.1). Statusflytt har angre-toast. Avsluttet er sammenlagt som standard. Panelet åpnes med `?app=<id>`. Oppfølginger på Oversikt lenker til Tracker. Status `ny` vises som "Ikke vurdert" og har eget merke i lister og detalj, som alle andre statuser. Merket for ny siden sist heter "Ny" og har samme form som de andre merkene. |
| v0.5 | 2026-10-10 | F1 bygget. Etter brukertilbakemelding: triage i jobbdetaljen går rett til neste jobb, og angre-toasten dekker ikke handlingsraden. Jobber viser `Ny` som standard statusfilter. Triage er bare mellom `ny`/`interessant`/`ikke_aktuell` (ellers 409). `role` i `GET /api/jobs` er en enum. Kildestatus og kostnad på mobil ligger under "Mer". Mock-kjøring tar 6 s. |
| v0.4 | 2026-10-10 | F0 bygget. Appnavn "Jobbsøk". Fixtures er TypeScript med datoer relativt til i dag (§3.2). `/soknader` får en egen listeside (F3). TypeScript låst til 5.9 (§2). Kontrakten dekker alle v0-ruter; mock svarer på lese-endepunktene. |
| v0.3 | 2026-10-10 | Åpne spørsmål avklart og flyttet til §2: ingen triage-lenker i digesten, ingen offline-lesing, forkastede jobber bare i Logg. |
| v0.2 | 2026-10-10 | Frontend først: F0–F4 bygges og brukertestes mot mock før backend-fasene starter (ARCHITECTURE §17). Brukertest etter F1 og F4. |
| v0.1 | 2026-10-10 | Første utkast: React-SPA, PC + mobil, kontrakt-først mot mock, bølger F0–F5 |

---

## 1. Mål

- Dashboardet brukes på **PC** (hovedarbeidsflate: lese, skrive søknader) og **mobil** (triage, frister, status).
- Mobilen når appen via Tailscale på `https://jobb.mariuskristensen.no` når den kjører på hjemmeserveren (ARCHITECTURE §12). Under utvikling kjører alt lokalt på PC-en.
- Frontend bygges **før backend-fasene**: UI-et utvikles mot en API-kontrakt og mock-data, brukes av brukeren, og kobles til ekte backend når endepunktene finnes.

### Hva gjøres hvor

| Oppgave | PC | Mobil |
|---|---|---|
| Triage av nye jobber (Interessant / Ikke aktuell) | ✅ tastatur | ✅ sveip |
| Se frister og oppfølginger | ✅ | ✅ |
| Endre søknadsstatus, neste steg | ✅ kanban | ✅ liste + handlingsark |
| Skrive og revidere søknadsbrev | ✅ hovedflate | Lesbar, enkel redigering |
| Innstillinger, profil, logg | ✅ | Lesbar, enkel redigering |

---

## 2. Beslutninger

| Tema | Beslutning |
|---|---|
| Rammeverk | Vite + React + TypeScript, ren SPA. Ingen Node-server i drift. |
| Servering | `vite build` → `web/dist/`, servert av FastAPI som statiske filer på `/`. API-et ligger under `/api`. Én prosess, én port (8765). |
| Styling | Tailwind CSS + shadcn/ui (Radix). Komponentene kopieres inn og eies av prosjektet. |
| Stil | Ren og tett (Linear/GitHub-aktig). Nøytrale farger; farge brukes bare for score, frist og status. Lys + mørk modus (følger systemet, kan overstyres). |
| Ruting | React Router (library mode) |
| Data | TanStack Query + `openapi-fetch` med typer generert fra OpenAPI (`openapi-typescript`) |
| API-kontrakt | Kontrakt først. Pydantic-modeller i `src/jobsearcher/api/schemas.py` er kilden. OpenAPI eksporteres og TS-typer genereres. |
| Mock | MSW (Mock Service Worker) med anonymiserte fixture-data. Slås på med `VITE_MOCK=1`. |
| Navigasjon | Mobil (< 768 px): bunnfaner. PC (≥ 768 px): sidemeny. Samme ruter. |
| Jobbliste på PC | Master-detalj (liste venstre, detalj høyre) fra ≥ 1024 px. Tastatursnarveier. |
| Triage på mobil | Liste med sveip: høyre = Interessant, venstre = Ikke aktuell. Angre-toast i 5 s. |
| PWA | Installerbar (manifest + ikon, åpner i fullskjerm). Ingen offline-cache eller offline-lesing, ingen push. Krever at Tailscale er oppe. |
| Triage fra e-post | Nei. Digesten har lenker til appen, ikke ett-klikks triage (krever at e-postklienten når appen via Tailscale). |
| Forkastede jobber | Vises bare i Logg (§5.8), ikke i Jobber. |
| Søknadseditor | Markdown-tekstfelt + forhåndsvisning. Samme format som `drafts.content` og `.docx`-eksporten. |
| Språk i UI | Norsk (bokmål). Datoer med `date-fns` og `nb`-locale. |
| Appnavn | "Jobbsøk" i UI og PWA. Kodenavnet er fortsatt JobSearcher. |
| TypeScript | 5.9. TS 7 (native) mangler JS-API-et som `openapi-typescript` trenger. Oppgraderes når den støtter det. |
| Autentisering | Ingen i appen. Tilgang styres av Tailscale (ARCHITECTURE §12). |

---

## 3. Arkitektur

```
 web/ (Vite + React + TS)                       src/jobsearcher/
 ┌──────────────────────────────┐              ┌──────────────────────────────┐
 │ routes/  →  features/*       │   /api/*     │ api/schemas.py  (Pydantic)   │
 │ TanStack Query               │ ───────────► │ web/routes/*    (FastAPI)    │
 │ openapi-fetch + gen. typer   │              │ /  → web/dist (statisk)      │
 └──────────────────────────────┘              └──────────────────────────────┘
          │ VITE_MOCK=1                                  │
          ▼                                              ▼
   MSW + web/src/mocks/fixtures/*.ts             scripts/export_openapi.py
                                                 → web/openapi.json → npm run gen:api
```

### 3.1 Kontraktflyt

1. Endre eller legg til modeller i `api/schemas.py` og rute-signaturer i `web/routes/*` (kan returnere `501` før backend finnes).
2. `uv run python scripts/export_openapi.py` skriver `web/openapi.json` (versjonert i git). `tests/test_api_contract.py` feiler hvis filen er utdatert.
3. `npm run gen:api` genererer `web/src/api/schema.d.ts`.
4. MSW-handlere og fixtures typesjekkes mot de genererte typene (`npm run typecheck`). Brudd i kontrakten gir TypeScript-feil.

### 3.2 Utvikling

| Modus | Kommando | Data |
|---|---|---|
| Bare frontend | `npm run dev:mock` i `web/` | MSW + fixtures |
| Frontend + backend | `jobsearcher serve --reload` og `npm run dev` | Vite (5173) proxyer `/api` til 8765 |
| Test på mobil under utvikling | `npm run dev:mock -- --host` (eller `npm run dev -- --host`), åpne `http://<PC-ens Tailscale-IP>:5173` | Mock eller ekte API |
| Drift | `jobsearcher serve` (container) | Ekte API, `web/dist` |

Fixtures ligger i `web/src/mocks/fixtures/*.ts` og er **oppdiktede** (bedrifter, personer, domener `*.example`). Ekte data går aldri inn i `web/`. Datoene regnes relativt til dagen mock-appen åpnes, så frister og "nye siden sist" alltid er aktuelle. `web/src/mocks/db.ts` bygger en minnedatabase fra dem ved hver sidelasting (endringer som triage forsvinner ved omlasting); `handlers.ts` svarer på kontrakten, og ruter som ikke er mocket ennå gir `501`. UI-et viser et `MOCK`-merke i mock-modus. "Kjør nå" i mock tar 6 s og finner ingen nye jobber; den oppdaterer bare kildestatus.

### 3.3 Bakgrunnsjobber i UI-et

Utdyper ARCHITECTURE §10.1:
- Handlinger som starter en jobb (`Kjør nå`, utkast, revisjon, regenerer profil) får `{task_id}` tilbake.
- `useTask(id)` poller `GET /api/tasks/{id}` hvert 2. sekund til status er `done | failed | cancelled`, og invaliderer berørte queries.
- Aktive jobber vises som en liten indikator i toppen (PC) / over bunnfanene (mobil), med "Avbryt". Indikatoren følger hver jobb den har sett til den er ferdig, og viser en toast med resultatet.

---

## 4. Layout og navigasjon

### 4.1 Brytpunkter

| Bredde | Layout |
|---|---|
| < 768 px (mobil) | Bunnfaner, én kolonne, detalj som egen skjerm, handlingsark (bottom sheet) for valg |
| 768–1023 px (nettbrett / smalt vindu) | Sidemeny (ikoner), én kolonne |
| ≥ 1024 px (PC) | Sidemeny med tekst, master-detalj på Jobber og Tracker |

Testes i Playwright på 390×844 (mobil) og 1440×900 (PC).

### 4.2 Navigasjon

| Mobil bunnfane | PC sidemeny | Rute |
|---|---|---|
| Oversikt | Oversikt | `/` |
| Jobber | Jobber | `/jobber`, `/jobber/:id` |
| Tracker | Tracker | `/tracker` |
| Mer → | Søknader | `/soknader` (søknader med utkast, F3), `/soknader/:applicationId` |
| Mer → | Profil | `/profil`, `/profil/*path` |
| Mer → | Innstillinger | `/innstillinger` |
| Mer → | Logg | `/logg` |

"Mer" er en egen skjerm med liste over de resterende sidene, pluss status for siste kjøring og "Kjør nå".

### 4.3 Skisser

Mobil, Jobber:
```
┌──────────────────────────┐
│ Jobber          ⌕  ☰filt │
│ [Alle][Fast][Trainee][…] │  ← faner per jobbtype, horisontal scroll
├──────────────────────────┤
│ ● Junior utvikler    82  │  ← score-merke
│   Acme AS · Oslo         │
│   Frist om 3 d   NY      │  ← fristfarge
├──────────────────────────┤
│ ← sveip: Ikke aktuell    │
│   sveip: Interessant →   │
├──────────────────────────┤
│ Oversikt Jobber Tracker ⋯│  ← bunnfaner
└──────────────────────────┘
```

PC, Jobber (≥ 1024 px):
```
┌────────┬─────────────────────┬──────────────────────────────────┐
│Oversikt│ [Alle][Fast][Train.]│ Junior utvikler · Acme AS     82 │
│Jobber  │ filtre ▾            │ Frist 14. okt (om 3 d)  [Søk ↗]  │
│Tracker │─────────────────────│ [Interessant i] [Ikke aktuell x] │
│Søknader│▶Junior utv.  82  3d │ [Lag søknadsutkast]              │
│Profil  │ Trainee IT   77 12d │ Hvorfor match · Bekymringer      │
│Innst.  │ Utvikler     64  —  │ Sammendrag · Kontakt · Annonse   │
│Logg    │                     │ Bedriftsnotat                    │
└────────┴─────────────────────┴──────────────────────────────────┘
```

---

## 5. Skjermer

Bølge (§8) står i parentes. Alle skjermer har tilstandene laster (skjelett), tom og feil (med "Prøv igjen").

### 5.1 Oversikt `/` (F1)

| Blokk | Innhold | Mobil | PC |
|---|---|---|---|
| Frister neste 14 dager | Jobber med status Interessant/Utkast og frist ≤ 14 d, sortert på frist | Først, full bredde | Venstre kolonne, øverst |
| Nye siden sist | Antall per jobbtype + topp 5 etter score, lenker til Jobber (status Ikke vurdert, sortert nyeste) | Kort | Høyre kolonne |
| Oppfølginger | Søknader med `follow_up_at` eller `next_step_at` ≤ 7 d | Kort | Venstre kolonne |
| Kildestatus | Siste kjøring per kilde (ok/warn/fail), tidspunkt, "Kjør nå" | Under "Mer" | Høyre kolonne, kompakt |
| Kostnad | Denne måneden mot tak, varsel ved 80 % | Under "Mer" | Høyre kolonne, kompakt |

### 5.2 Jobber `/jobber` (F1)

- **Faner** per jobbtype: Alle, Fast, Trainee, Graduate, Sommerjobb.
- **Filtre:** status (Ikke vurdert / Interessant / Ikke aktuell / Alle; standard Ikke vurdert, siden listen er for triage), min. score, kilde, frist før, rolle, fritekst. På mobil i et handlingsark; på PC som en rad over listen. Filtre lagres i URL-en (`?type=trainee&min_score=60`), så de kan bokmerkes.
- **Sortering:** standard frist, deretter score. Alternativ: score, nyeste.
- **Rad:** tittel, bedrift, sted, score-merke, frist (relativ + farge), merker (`NY`, `Lagt ut på nytt`, `Bare tittel kjent`).
- **Triage mobil:** sveip med terskel 30 % bredde, farget bakgrunn og ikon under sveipet. Angre-toast i 5 s (én toast om gangen; den gjelder siste triage).
- Triage flytter bare mellom Ikke vurdert, Interessant og Ikke aktuell. Jobber med senere status viser status og "Status endres i Tracker".
- **Triage PC:** `j`/`k` = neste/forrige, `i` = Interessant, `x` = Ikke aktuell, `u` = angre, `o` = åpne søknadslenke, `Enter` = åpne detalj (på smale vinduer). Knapper i detaljpanelet gjør det samme.
- Etter triage hoppes det til neste jobb i listen, og raden blir værende som nedtonet med status til listen lastes på nytt (unngår at listen hopper under fingeren).
- Paginering: uendelig scroll med cursor.

### 5.3 Jobbdetalj `/jobber/:id` (F1)

Rekkefølge, øverst først:
1. Tittel, bedrift, sted, jobbtype, score-merke
2. Frist (dato + relativ), søknadslenke, statusknapper
3. "Lag søknadsutkast" (starter bakgrunnsjobb, F3) / "Åpne søknad" hvis den finnes
4. Hvorfor match (`match_reasons`) og bekymringer (`concerns`)
5. Sammendrag og nøkkelkrav
6. Kontaktpersoner (tlf/e-post som lenker)
7. Annonsetekst med kilde, eller "Bare tittel kjent" + lenke
8. Bedriftsnotat (sammenleggbart)
9. Kilder og historikk (først sett, lagt ut på nytt fra)

På mobil: egen skjerm med tilbake-knapp og en fast handlingsrad nederst (Interessant / Ikke aktuell / Søk ↗). Triage går rett videre til neste jobb i listen (samme filtre, laster flere sider ved behov); når listen er tom, tilbake til listen. Tilbake-knappen går til listen, ikke gjennom jobbene som er triagert. "Angre" åpner jobben som ble angret. Mens handlingsraden vises, ligger toasten og jobbindikatoren over den. Under 1024 px er detaljen alltid en egen skjerm; 768–1023 px uten handlingsrad.

"Lag søknadsutkast" er deaktivert til F3.

### 5.4 Tracker `/tracker` (F2)

| | PC (≥ 1024 px) | Mobil og nettbrett (< 1024 px) |
|---|---|---|
| Visning | Kanban: Interessant, Utkast, Søkt, Intervju, Tilbud, Avsluttet. Ikke aktuell, Avslag, Trukket og Utløpt er samlet i "Avsluttet", som er en smal, sammenlagt kolonne til den åpnes. | Liste gruppert som kolonnene, sammenleggbare grupper (Avsluttet lukket som standard). Statuschips (`?vis=<kolonne>`) viser én gruppe. |
| Flytte status | Dra og slipp (`@dnd-kit/core`): under dra er lovlige kolonner markert og ulovlige dempet; slipp på ulovlig kolonne gir en toast. Slipp på Avsluttet med flere lovlige statuser spør hvilken. Statusmeny (⋮) på kortet gjør det samme uten dra. | Trykk kort → handlingsark med lovlige neste statuser, "Neste steg, oppfølging og notater" og "Åpne jobben" |
| Kort | Tittel, bedrift, neste steg + dato, "Følg opp" + dato (rød når forfalt), frist (bare før søkt), kontaktperson, status (i Avsluttet) | Samme |
| Redigere | Sidepanel fra høyre | Fullskjerm-ark |
| Sortering | Aktive: tidligste dato først (neste steg, oppfølging, frist før søkt), udaterte sist. Avsluttet: nyeste først. | Samme |

Panelet (`?app=<id>`, så Tilbake lukker det): bedrift, status, frist, "Åpne jobben", "Flytt til"-knapper, neste steg + dato, oppfølging, notater (lagres med "Lagre", bare endrede felt sendes) og hendelseslogg (nyeste først).

Bare overgangene i kortets `allowed_next` vises; backend validerer også (ARCHITECTURE §9.1). Hver flytting gir en toast med "Angre" (5 s), som sender `status: previous_status` og gjenoppretter `follow_up_at`. Kortet flyttes med en gang (optimistisk) og rulles tilbake ved 409.

Jobbdetaljen lenker til panelet ("Endre status i Tracker") når jobben er forbi triage, og Oppfølginger på Oversikt åpner panelet.

### 5.5 Søknadseditor `/soknader/:applicationId` (F3)

PC (≥ 1024 px), tre soner:
- **Venstre:** Markdown-tekstfelt med fane for forhåndsvisning. Autosave 2 s etter siste tastetrykk → ny versjon (`author=user`). Ordtelling.
- **Høyre:** chat med revisjonsagenten. Instruksjon → bakgrunnsjobb → ny versjon (`author=agent`) med `change_summary`.
- **Over teksten:** `claims_to_verify` som gule advarsler som kan krysses av.
- **Verktøylinje:** versjonsvelger med diff mot forrige eller valgt versjon, "Kopier", "Last ned .docx", status.

Mobil: segmentert kontroll "Utkast | Chat | Versjoner". Redigering er mulig, men skjermen er laget for lesing, kopiering og nedlasting.

### 5.6 Profil `/profil` (F4)

Profilen redigeres i dashboardet når appen kjører på hjemmeserveren (ARCHITECTURE §6.1).
- Venstre/øverst: filtre over profilfilene (`profile.yaml`, `cv.md`, `motivation.md`, `style_overrides.md`, `projects/`, `experience/`, `writing_samples/`). "Ny fil" lager fil fra `_template.md`.
- Editor: samme Markdown-editor som søknader. YAML valideres før lagring.
- Lagring skriver filen og en rad i `profile_revisions` (historikk med diff og gjenoppretting).
- Statuslinje: "Destillert profil er utdatert" når `profile_hash` har endret seg, med "Regenerer" (bakgrunnsjobb) og diff av `derived/`-filene.

### 5.7 Innstillinger `/innstillinger` (F4)

Skjema gruppert i seksjoner: Søk (geo-modus, jobbtyper, ekskluderinger, senioritet), Scoring (terskel, ny scoring med kostnadsestimat), LLM (backend, modeller), Kostnad (tak), Planlegging (klokkeslett), Kilder (helse, aktiv/av), Kontekst (lenke til Profil), Utseende (lys/mørk/system). Lagres i `settings_overrides`. Verdier som kommer fra YAML og ikke er overstyrt vises som standard, med "Tilbakestill".

### 5.8 Logg `/logg` (F4)

Faner: Kjøringer (per kilde, med feil), Agentkall (modell, tokens, kostnad, varighet), Forkastet i dag (hardfilter-regel + detalj, med "Vis jobb").

---

## 6. Visuelt system

| Element | Regel |
|---|---|
| Tetthet | Radhøyde 44 px på mobil (trykkmål), 36 px på PC. Systemfont-stack. |
| Score | ≥ 70 grønn, 50–69 nøytral, < 50 dempet. Viser tallet, aldri bare farge. |
| Frist | ≤ 3 d rød, ≤ 7 d gul, ≤ 14 d nøytral, ukjent "—". Relativ tekst ("om 3 d") + dato i tooltip/detalj. |
| Status | Ett fast fargepar per status, brukt likt i liste, kanban og merker. Alle statuser har merke, også Ikke vurdert. |
| Merker | Alle merker (status, score, frist, "Ny" siden sist, "Lagt ut på nytt", "Bare tittel kjent", jobbtype) har samme form og skriftstørrelse |
| Tema | Farger som CSS-variabler (shadcn-tokens). Mørk modus via `class` på `<html>`. |
| Tilgjengelighet | Alt som kan sveipes eller dras kan også gjøres med knapp/meny. Fokusringer synlige. Kontrast AA. |
| Ikoner | `lucide-react` (følger med shadcn) |

---

## 7. API-kontrakt (v0)

Alle ruter under `/api`. JSON. Datoer i ISO 8601. Feil som `{"detail": "...", "code": "..."}`. Modellene defineres i `src/jobsearcher/api/schemas.py`.

| Metode og sti | Bruk | Bølge |
|---|---|---|
| `GET /api/overview` | Frister, nye, oppfølginger, kildestatus, kostnad | F1 |
| `GET /api/jobs` | Liste. Query: `type`, `status`, `min_score`, `source`, `deadline_before`, `role`, `q`, `sort`, `cursor`, `limit` | F1 |
| `GET /api/jobs/{id}` | Detalj inkl. evaluering, kontakter, kilder, bedriftsnotat, søknad | F1 |
| `PUT /api/jobs/{id}/status` | Triage: `{status: "interessant" \| "ikke_aktuell" \| "ny"}` (`ny` = angre). Oppretter søknadsrad ved behov, `ny` sletter den. Bare fra `ny`/`interessant`/`ikke_aktuell`; ellers 409 `invalid_transition`. | F1 |
| `GET /api/applications` | Tracker. Query: `status`. Hvert kort har `allowed_next` og `previous_status` (ARCHITECTURE §9.1). | F2 |
| `PATCH /api/applications/{id}` | `status`, `next_step`, `next_step_at`, `follow_up_at`, `notes`, `comment` (lagres på statushendelsen). Bare felt som sendes endres. `status: previous_status` = angre. Ugyldig overgang → 409 `invalid_transition`. Returnerer kortet. | F2 |
| `GET /api/applications/{id}/events` | Hendelseslogg | F2 |
| `POST /api/jobs/{id}/draft` | Start research + skriver → `{task_id}` | F3 |
| `GET /api/applications/{id}/drafts` | Versjonsliste | F3 |
| `GET /api/drafts/{id}` | Én versjon med innhold og `claims_to_verify` | F3 |
| `POST /api/applications/{id}/drafts` | Lagre brukerversjon | F3 |
| `POST /api/applications/{id}/revise` | `{instruction}` → `{task_id}` | F3 |
| `GET /api/drafts/{id}/docx` | Last ned `.docx` | F3 |
| `GET /api/profile/files` | Filtre + status (`profile_hash`, destillert utdatert?) | F4 |
| `GET /api/profile/files/{path}` / `PUT` | Les / skriv én profilfil. Sti valideres mot `PROFILE_DIR`. | F4 |
| `GET /api/profile/files/{path}/revisions` | Historikk | F4 |
| `POST /api/profile/distill` | → `{task_id}` | F4 |
| `GET /api/settings` / `PATCH` | Effektive innstillinger (YAML + overstyringer) | F4 |
| `GET /api/logs/runs`, `/agent-runs`, `/discarded` | Logg | F4 |
| `POST /api/runs` | "Kjør nå" → `{task_id}`. 409 `run_active` hvis en kjøring pågår. | F1 |
| `GET /api/tasks/{id}`, `POST /api/tasks/{id}/cancel` | Bakgrunnsjobber | F1 |
| `GET /api/tasks?active=true` | Aktive jobber til indikatoren | F1 |
| `GET /api/health` | Brukes av Docker healthcheck og Uptime Kuma | F5 |

Statusverdier i API-et er snake_case uten norske tegn (`ny`, `interessant`, `utkast`, `sokt`, `intervju`, `tilbud`, `ikke_aktuell`, `avslag`, `trukket`, `utlopt`). Visningsnavn ligger i frontend.

### 7.1 Ekte API (backend-fase 1–2)

Implementert: alle ruter merket F1 og F2, `GET /api/logs/*` og `GET /api/health`. Resten (utkast, profil, innstillinger) svarer `501 not_implemented` til sin fase. Der det ekte API-et oppfører seg annerledes enn MSW-mocken, gjelder dette:

| Tema | Ekte API |
|---|---|
| Skjulte jobber | `GET /api/jobs` viser aldri forkastede jobber (`filtered_out`). Ikke vurderte jobber skjules også når annonsen er inaktiv eller fristen har passert. Vurderte jobber vises, også `ikke_aktuell` uten statusfilter. |
| Søk (`q`) | Tittel, bedrift, sted og annonsetekst |
| `is_new` | Først sett ved eller etter starten av siste fullførte kjøring. `scrape_runs`-rader som starter innen en time fra den nyeste regnes som samme kjøring. `new_since_last.since` er det tidspunktet. |
| Avbryt | En jobb i kø avbrytes med en gang. En jobb som kjører får meldingen "Avbryter …" og status `cancelled` når pipelinen når neste sjekkpunkt. |
| `POST /api/runs` | 409 `run_active` også når en kjøring fra CLI eller planleggeren holder `data/run.lock` |
| Triage | Samme status igjen gjør ingenting. `interessant` ↔ `ikke_aktuell` tilbake til forrige status sletter siste hendelse (angre). Tilbake til `ny` gir 409 hvis søknaden har utkast. |
| Ukjent søknad | `GET /api/applications/{id}/events` gir 404 |
| Ugyldig cursor | `400 invalid_cursor` (ikke deklarert i OpenAPI) |
| Kildestatus | Kildene som er slått på i `config/sources.yaml`, pluss kilder med kjøringer. `manual` vises ikke. |

---

## 8. Bølger

Bølgene F0–F4 bygges før backend-fasene i ARCHITECTURE §17. Hver bølge er ferdig når den fungerer på både 390 px og 1440 px i mock-modus, med Vitest- og Playwright-tester.

| Bølge | Innhold | Ferdig når | Avhenger av backend |
|---|---|---|---|
| ~~F0. Skjelett~~ | `web/` med Vite, TS, Tailwind, shadcn, React Router, TanStack Query, MSW. `api/schemas.py` + `export_openapi.py` + typegenerering. App-skall (sidemeny/bunnfaner), tema, PWA-manifest, fixture-sett. | ✅ 2026-10-10 (PR #4) | Nei |
| ~~F1. Daglig sløyfe~~ | Oversikt, Jobber (faner, filtre, sveip, tastatur), Jobbdetalj, bakgrunnsjobb-indikator, "Kjør nå" | ✅ bygget 2026-10-10; venter på brukertest (triage av en mock-dag < 2 min på mobil) | ✅ Koblet til ekte API i fase 2 |
| ~~F2. Tracker~~ | Kanban (PC), gruppert liste (mobil), statusoverganger, neste steg, hendelseslogg | ✅ 2026-10-10 | ✅ Koblet til ekte API i fase 2 |
| **F3. Søknadseditor** | Editor, forhåndsvisning, autosave/versjoner, diff, revisjonschat, `claims_to_verify`, `.docx` | Brev kan itereres mot mock-agent | Nei. Kobles i fase 3. |
| **F4. Profil, innstillinger, logg** | Profileditor med historikk, innstillingsskjema, loggfaner | Profilen kan redigeres uten filsystemtilgang | Nei. Kobles i fase 4 (destilleren finnes fra fase 2). |
| **F5. Drift** | FastAPI serverer `web/dist`, multi-stage Dockerfile, PWA-ikon, test på mobil via Tailscale | `docker compose up` gir hele appen på én port | Ja: fase 1 (`serve`). `serve` serverer allerede `web/dist`; Dockerfile gjenstår. |

Rekkefølgen er F0 → F1 → brukertest → F2 → backend-fase 1–2 → F3 → fase 3 → F4 → fase 4 (ARCHITECTURE §17). Ved brukertest kjører appen i mock-modus på PC og mobil (`npm run dev:mock -- --host`, §3.2). Funn rettes i dette dokumentet og i kontrakten før neste bølge. Fixture-settet må være realistisk nok til å teste flyten: ~40 jobber over alle jobbtyper, frister, reposts, forkastede jobber og søknader i alle statuser.

---

## 9. Testing

| Nivå | Verktøy | Dekker |
|---|---|---|
| Enhet | Vitest + Testing Library | Hooks (`useTask`), formattering (frist, score), statusoverganger i UI |
| Kontrakt | `tsc` mot genererte typer | At fixtures og komponenter matcher API-et |
| Ende-til-ende | Playwright mot `dev:mock`, to viewporter (390×844, 1440×900) | Navigasjon, tema og manifest (F0); triage med sveip (mobil) og tastatur (PC), filtre, "Kjør nå" (F1); hele statusflyten fra mobil, dra og slipp med ulovlig kolonne og angre, statusmeny og sidepanel (F2); autosave (senere) |

Kommandoer i `web/`: `npm test` (Vitest), `npm run typecheck`, `npm run e2e` (Playwright starter `dev:mock` selv på port 5174). Backend: `uv run pytest`.

