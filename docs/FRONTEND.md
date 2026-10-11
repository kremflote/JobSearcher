# JobSearcher: frontend-design

> Status: v0.16 (2026-10-11). F0–F5 og F2b er bygget og koblet til ekte API (backend-fase 1–4, 2b og 4b). Alle planlagte bølger er bygget.
> Dokumentet eier UI-designet: skjermer, layout, komponenter, API-kontrakt og frontend-bølger. Resten av systemet står i [ARCHITECTURE.md](ARCHITECTURE.md). Regler for vedlikehold står i `AGENTS.md`.

## Endringslogg

| Versjon | Dato | Endring |
|---|---|---|
| v0.16 | 2026-10-11 | F5 bygget (§8): skjermene utenom Oversikt og Jobber lastes ved første besøk, så hovedbunten er under Vites grense på 500 kB. Dockerfile og deploy står i ARCHITECTURE §12. |
| v0.15 | 2026-10-11 | F4 bygget og koblet (§5.6–5.8). Kontrakt (§7): `SettingItem` har `label`, `help`, `kind`, `options`, `min`, `max`, så skjemaet lages fra API-et; ny seksjon `notify`. `ProfileTree` har `folders` og `derived_at`; `base_hash: null` lager en ny fil (409 `file_exists`), feil hash gir 409 `conflict`, ugyldig YAML 422 `invalid_yaml`, ugyldig sti 400 `invalid_path`. Nye ruter: `GET /api/profile/derived`, `GET/POST /api/rescore`. Logg-fanen heter «Forkastet» og viser alle nylige, gruppert per dag. Mocken følger de samme reglene (`mocks/system.ts`). |
| v0.14 | 2026-10-11 | «Lagre som stilregel» i revisjonschatten (§5.5): når meldingen er en preferanse for alle brev, viser agentsvaret en foreslått regel med knapp som legger den til i `style_overrides.md`. Kontrakt (§7): `DraftMessage.style_rule`/`style_rule_saved`, nytt `POST /api/applications/{id}/messages/{message_id}/style-rule`. Mock-revisoren foreslår en regel for meldinger som starter med «aldri»/«alltid»/«unngå». |
| v0.13 | 2026-10-11 | Backend-fase 3 kobler F3: alle utkast-ruter er ekte (§7.1). Avvik fra mocken står i §7.1. |
| v0.12 | 2026-10-11 | Etter brukertest av F3: chatten skiller spørsmål fra endringer. Et spørsmål får et svar i chatten uten ny versjon. Historikken kommer fra nytt endepunkt `GET /api/applications/{id}/messages` i stedet for versjonslisten (§5.5, §7). Mock-revisoren svarer på spørsmål (§3.2). |
| v0.11 | 2026-10-11 | F3 bygget mot mock (§5.5): editor med autosave, revisjonschat, versjoner med ord-diff og "Gjenopprett", påstander som krysses av, "Kopier" (ren tekst), `.docx` og "Merk som søkt". `/soknader` lister utkast og interessante jobber uten utkast. Kontrakt (§7): kortet har `latest_draft_id`/`latest_draft_at`; autosave oppdaterer en fersk brukerversjon (< 10 min) i stedet for å lage en ny; `base_draft_id` og `draft_id` velger versjonen det bygges på; 409 `draft_exists` og `no_draft`. |
| v0.10 | 2026-10-11 | Kostnadstaket gjelder bare betalte kall, og kortet sier det. Saldodelen viser totalt forbruk hos OpenRouter (`used_usd`, også kall utenfor appen). |
| v0.9 | 2026-10-11 | F2b bygget: LLM-forbruk-kortet ligger under Kildestatus (PC: høyre kolonne, mobil: "Mer") og åpner detaljen i sidepanel ≥ 1024 px, ellers handlingsark. Varselet sier "Nærmer seg kostnadstaket" (terskelen kan endres). Mock-tilstand for saldoen velges med `?mock_llm=` (§3.2). `GET /api/llm/usage` er ekte (§7.1). |
| v0.8 | 2026-10-11 | Ny bølge F2b: kortet Kostnad på Oversikt blir LLM-forbruk, med tokens og kostnad per backend denne måneden, OpenRouter-saldo og tokens per dag (§5.1). Nytt endepunkt `GET /api/llm/usage` (§7). Bygges sammen med backend-bølge 2b (ARCHITECTURE §17). |
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

Fixtures ligger i `web/src/mocks/fixtures/*.ts` og er **oppdiktede** (bedrifter, personer, domener `*.example`). Ekte data går aldri inn i `web/`. Datoene regnes relativt til dagen mock-appen åpnes, så frister og "nye siden sist" alltid er aktuelle. `web/src/mocks/db.ts` bygger en minnedatabase fra dem ved hver sidelasting (endringer som triage forsvinner ved omlasting); `handlers.ts` svarer på kontrakten, og ruter som ikke er mocket ennå gir `501`. UI-et viser et `MOCK`-merke i mock-modus. "Kjør nå" i mock tar 6 s og finner ingen nye jobber; den oppdaterer bare kildestatus. LLM-forbruket har seks mock-tilstander som velges med `?mock_llm=<tilstand>` i URL-en appen lastes med: `account` (standard), `key_limit`, `unknown`, `unset`, `low`, `warn`. I Vitest: `createMockDb(now, { llmState })`. Søknadsutkast i mock tar 5 s og revisjon 3 s (`mocks/drafts.ts`). Destillering tar 4 s og "Score på nytt" 5 s; mocken starter med utdatert destillert profil og 12 jobber scoret med gammel profil. Profil, innstillinger og score på nytt følger API-ets regler (`mocks/system.ts`); YAML-sjekken i mocken er grov (ubalanserte klammer, tab-innrykk). Mock-revisjonen kutter siste setning i lengste avsnitt når instruksjonen inneholder "kort", "stram" eller "kutt", ellers legger den til en merket setning. Et spørsmål (slutter på "?" eller starter med et spørreord som "hvorfor", "hva", "er") får et fast mock-svar uten ny versjon. `.docx` fra mock er en ekte, enkel Word-fil (`mocks/docx.ts`).

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
| LLM-forbruk (F2b) | Se under | Under "Mer" | Høyre kolonne, kompakt; klikk åpner detaljen |

**LLM-forbruk** (erstatter kortet Kostnad, data fra `GET /api/llm/usage`):

| Del | Innhold |
|---|---|
| Kompakt | Månedens betalte kostnad mot taket med stolpe (varsel ved 80 %), merket "Kostnadstak for betalte kall (Claude-abonnementet teller ikke)", OpenRouter-saldo ("$7,40 igjen av $10"), antall reservekall denne måneden (0 så lenge reserven er av, ARCHITECTURE §8.1) |
| Per backend | Claude-abonnement og OpenRouter hver for seg: kall, tokens inn/ut, kostnad. Claude merkes "estimat, fra abonnementet", OpenRouter "betalt". |
| Per dag | Stablede søyler for tokens siste 30 dager, farget per backend. Trykk på en søyle viser tall for dagen. |
| Saldo | Kilde (`account` med management-nøkkel, `key_limit` med kredittgrense på nøkkelen), tidspunkt for siste henting, totalt brukt hos OpenRouter (også kall utenfor appen, så tallet kan være høyere enn per backend). Under $1: advarsel ("ellers stopper AI-scoringen"). Ingen nøkkel: "OpenRouter ikke satt opp" (da scores ingen jobber, med mindre `llm.backend` er `claude_code`). Saldo ukjent (nøkkel uten grense, ingen management-nøkkel): bare forbruket vises, med en tekst om hvordan saldoen slås på. |

Kortet ligger under Kildestatus. Fra 1024 px åpner det detaljen i et sidepanel til høyre, under det i et handlingsark. Søylene er knapper; i dag er valgt fra start. Varselet ved `warn` sier "Nærmer seg kostnadstaket", siden terskelen (`llm.warn_ratio`) kan endres. `overview.cost` finnes fortsatt i API-et, men brukes ikke av UI-et.

### 5.2 Jobber `/jobber` (F1)

- **Faner** per jobbtype: Alle, Fast, Trainee, Graduate, Sommerjobb.
- **Filtre:** status (Ikke vurdert / Interessant / Ikke aktuell / Alle; standard Ikke vurdert, siden listen er for triage), min. score, kilde, frist før, rolle, fritekst. På mobil i et handlingsark; på PC (≥ 768 px) står søkefeltet over listen, og de andre filtrene foldes ut under det med en "Filtre"-knapp (viser antall aktive filtre; åpen/lukket huskes i nettleseren). Filtre lagres i URL-en (`?type=trainee&min_score=60`), så de kan bokmerkes.
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

"Lag søknadsutkast" starter bakgrunnsjobben og viser "Skriver utkast …" til den er ferdig; da blir knappen "Åpne søknad", og toasten fra jobbindikatoren har "Åpne" til editoren. Jobben flyttes til Utkast (ARCHITECTURE §9.1).

### 5.4 Tracker `/tracker` (F2)

| | PC (≥ 1024 px) | Mobil og nettbrett (< 1024 px) |
|---|---|---|
| Visning | Kanban: Interessant, Utkast, Søkt, Intervju, Tilbud, Avsluttet. Ikke aktuell, Avslag, Trukket og Utløpt er samlet i "Avsluttet", som er en smal, sammenlagt kolonne til den åpnes. | Liste gruppert som kolonnene, sammenleggbare grupper (Avsluttet lukket som standard). Statuschips (`?vis=<kolonne>`) viser én gruppe. |
| Flytte status | Dra og slipp (`@dnd-kit/core`): under dra er lovlige kolonner markert og ulovlige dempet; slipp på ulovlig kolonne gir en toast. Slipp på Avsluttet med flere lovlige statuser spør hvilken. Statusmeny (⋮) på kortet gjør det samme uten dra. | Trykk kort → handlingsark med lovlige neste statuser, "Neste steg, oppfølging og notater" og "Åpne jobben" |
| Kort | Tittel, bedrift, neste steg + dato, "Følg opp" + dato (rød når forfalt), frist (bare før søkt), kontaktperson, status (i Avsluttet) | Samme |
| Redigere | Sidepanel fra høyre | Fullskjerm-ark |
| Sortering | Aktive: tidligste dato først (neste steg, oppfølging, frist før søkt), udaterte sist. Avsluttet: nyeste først. | Samme |

Panelet (`?app=<id>`, så Tilbake lukker det): bedrift, status, frist, "Åpne jobben", "Åpne søknadsutkastet" (når det finnes), "Flytt til"-knapper, neste steg + dato, oppfølging, notater (lagres med "Lagre", bare endrede felt sendes) og hendelseslogg (nyeste først).

Bare overgangene i kortets `allowed_next` vises; backend validerer også (ARCHITECTURE §9.1). Hver flytting gir en toast med "Angre" (5 s), som sender `status: previous_status` og gjenoppretter `follow_up_at`. Kortet flyttes med en gang (optimistisk) og rulles tilbake ved 409.

Jobbdetaljen lenker til panelet ("Endre status i Tracker") når jobben er forbi triage, og Oppfølginger på Oversikt åpner panelet.

### 5.5 Søknadseditor `/soknader/:applicationId` (F3)

PC (≥ 1024 px), tre soner:
- **Venstre:** Markdown-tekstfelt med fanene "Rediger | Forhåndsvis" og ordtelling. Autosave 2 s etter siste tastetrykk → brukerversjon (`author=user`). En brukerversjon yngre enn 10 min oppdateres på plass, så en redigeringsøkt blir én versjon. Lagringsstatus ("Lagret", "Ikke lagret", "Lagrer …", "Kunne ikke lagre") står i tittellinjen. Teksten følger nyeste versjon så lenge det ikke finnes ulagrede endringer. Lukkes fanen med ulagret tekst, spør nettleseren først.
- **Høyre:** chat med revisjonsagenten, alltid synlig (fast høyde). Historikken er de lagrede meldingene (`GET /api/applications/{id}/messages`): brukerens meldinger og agentens svar. Et svar som laget en versjon lenker til den; et svar på et spørsmål står alene, og brevet er uendret. Brukerversjoner flettes inn som "Du redigerte · versjon N". Er meldingen en preferanse for alle brev ("aldri tankestrek"), har agentsvaret en boks "Stilregel for alle brev: …" med knappen "Lagre som stilregel"; etter lagring står det "Lagret" og en toast bekrefter. Forslagsknapper: "Gjør den kortere", "Mer formell tone", "Mer konkret om prosjektene mine". Enter sender, Shift+Enter gir ny linje. Sending lagrer først, starter en bakgrunnsjobb mot gjeldende versjon og låser tekstfeltet til agenten har svart (og en eventuell ny versjon er lastet).
- **Over teksten:** `claims_to_verify` fra gjeldende versjon som gule advarsler som kan krysses av. Avkryssingen huskes i nettleseren (localStorage) per søknad og påstand.
- **Verktøylinje:** bedrift, status, frist (før søkt), lenke til jobben; versjonsmeny, "Kopier" (ren tekst uten Markdown-tegn), ".docx" (lagrer først) og "Merk som søkt" (når overgangen er lovlig, med angre-toast som i Tracker).

Versjoner: valgt versjon (`?versjon=<id>`) vises i stedet for tekstfeltet som ord-diff (lagt til grønt, fjernet rødt og gjennomstreket) mot forrige versjon eller mot gjeldende, med antall ord lagt til og fjernet. "Gjenopprett" lagrer den som ny brukerversjon.

Mobil: segmentert kontroll "Utkast | Chat | Versjoner" (`?vis=`). Versjoner er en liste; trykk viser diffen i samme fane. Redigering er mulig, men skjermen er laget for lesing, kopiering og nedlasting. Chatfeltet ligger over bunnfanene.

`/soknader`: "Utkast" (søknader med utkast, sist endret først, med status og frist) og "Interessant, uten utkast" med "Lag søknadsutkast" på hver rad.

### 5.6 Profil `/profil` (F4)

Profilen redigeres i dashboardet når appen kjører på hjemmeserveren (ARCHITECTURE §6.1).
- **Statuslinje** øverst: "Destillert profil er utdatert" (gul) når `profile_hash` har endret seg, med "Regenerer" (bakgrunnsjobb); ellers når den ble laget. "Vis destillert" åpner `/profil?vis=destillert`. Er profilen oppdatert og jobber scoret med gammel profil, vises kortet "Score på nytt" (§5.7) under.
- **Filliste:** filene i rotmappen (med en kort forklaring for standardfilene), så én gruppe per mappe (`projects/`, `experience/`, `writing_samples/`) med "+" (Ny fil): navnet blir et filnavn (`Min app` → `projects/min-app.md`), og filen lages fra mappens `_template.md`. Nederst "Destillert profil".
- **Editor** (`/profil/<sti>`): tekstfelt med "Rediger | Forhåndsvis" og ordtelling for Markdown; YAML vises i monospace uten forhåndsvisning. Lagres med "Lagre" eller Ctrl+S (ikke autosave: profilen styrer alle agentene). Status "Lagret"/"Ikke lagret". Ugyldig YAML eller en fil endret et annet sted gir en feilboks og teksten beholdes; ved konflikt kan filen lastes inn på nytt. Ulagret tekst gir spørsmål før man går fra filen, i appen og i nettleseren.
- **Historikk** (`?historikk=1`): lagrede versjoner, nyeste først (den eldste er originalen fra før første lagring). Valgt versjon vises som ord-diff mot teksten nå, med "Gjenopprett", som lagrer den som ny versjon.
- **Destillert profil:** de tre filene, hver med "Tekst | Endringer" (diff mot versjonen før siste regenerering) og antall ord lagt til og fjernet.
- PC (≥ 1024 px): fillisten til venstre (256 px), filen til høyre. Under det er lista og filen egne skjermer med tilbakeknapp.

### 5.7 Innstillinger `/innstillinger` (F4)

Ett skjema med seksjoner: Søk (jobbtyper, geografi per jobbtype, fjernarbeid, ekskluderinger, senioritet, erfaringskrav), Scoring (frister på Oversikt, "Score på nytt"), E-postdigest (av/på, score, frister), LLM (backend, reserve, modeller), Kostnad (tak, varselgrense), Planlegging (klokkeslett, tilfeldig utsettelse), Kilder (Finn og NAV av/på), Kontekst (lenke til Profil), Utseende (lys/mørk/system). Feltene kommer fra `GET /api/settings` og vises etter `kind`: bryter (`bool`), meny (`enum`), tall (`int`/`number`, desimalkomma), klokkeslett (`time`), tekst (`string`) og ordliste (`string_list`, brikker med × og et felt som legger til ved Enter eller komma). Hvert felt lagres for seg: brytere og menyer med en gang, tekst og tall ved Enter eller når feltet forlates (Escape angrer). Ugyldige verdier gir en toast og feltet går tilbake. Overstyrte felt viser "Standard: …" og "Tilbakestill".

**Score på nytt** (ARCHITECTURE §5.5): "N aktive jobber er scoret med gammel profil eller prompt. Estimert kostnad $X" og knappen, som starter en bakgrunnsjobb. Uten slike jobber står det at alle er scoret med gjeldende profil.

### 5.8 Logg `/logg` (F4)

Faner (`?fane=`): Kjøringer (per kilde: tid, helse, manuell, funnet/nye/oppdatert/forkastet, feilmeldinger i rødt), Agentkall (agent, modell, prompt-versjon, tokens inn/ut, kostnad, varighet, feil), Forkastet (tittel, bedrift, regel og detalj; raden åpner jobben). Alle gruppert per dag, nyeste først, de siste 200 radene.

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
| `GET /api/llm/usage` | LLM-forbruk denne måneden: `cap_usd`, `spent_usd`, `by_backend[]` (`backend`, `calls`, `fallback_calls`, `input_tokens`, `output_tokens`, `cost_usd`, `estimated`), `daily[]` siste 30 dager (`date`, `backend`, tokens, `cost_usd`), `openrouter` (`configured`, `balance_usd`, `total_credits_usd`, `used_usd`, `balance_source`: `account` \| `key_limit` \| `null`, `fetched_at`). Saldoen caches 10 min i backend (ARCHITECTURE §8.1). | F2b |
| `GET /api/jobs` | Liste. Query: `type`, `status`, `min_score`, `source`, `deadline_before`, `role`, `q`, `sort`, `cursor`, `limit` | F1 |
| `GET /api/jobs/{id}` | Detalj inkl. evaluering, kontakter, kilder, bedriftsnotat, søknad | F1 |
| `PUT /api/jobs/{id}/status` | Triage: `{status: "interessant" \| "ikke_aktuell" \| "ny"}` (`ny` = angre). Oppretter søknadsrad ved behov, `ny` sletter den. Bare fra `ny`/`interessant`/`ikke_aktuell`; ellers 409 `invalid_transition`. | F1 |
| `GET /api/applications` | Tracker. Query: `status`. Hvert kort har `allowed_next` og `previous_status` (ARCHITECTURE §9.1), og `latest_draft_id`/`latest_draft_at` (null uten utkast). | F2, F3 |
| `PATCH /api/applications/{id}` | `status`, `next_step`, `next_step_at`, `follow_up_at`, `notes`, `comment` (lagres på statushendelsen). Bare felt som sendes endres. `status: previous_status` = angre. Ugyldig overgang → 409 `invalid_transition`. Returnerer kortet. | F2 |
| `GET /api/applications/{id}/events` | Hendelseslogg | F2 |
| `POST /api/jobs/{id}/draft` | Start research + skriver → `{task_id}`. Oppretter søknaden om nødvendig og flytter Interessant → Utkast når jobben er ferdig. `result` har `application_id` og `draft_id`. 409 `draft_exists` hvis søknaden har utkast. | F3 |
| `GET /api/applications/{id}/drafts` | Versjonsliste | F3 |
| `GET /api/drafts/{id}` | Én versjon med innhold og `claims_to_verify` | F3 |
| `POST /api/applications/{id}/drafts` | Autosave: `{content, base_draft_id?}` → versjonen. Er nyeste versjon en brukerversjon yngre enn 10 min, oppdateres den på plass; ellers ny versjon. Brukerversjoner arver `claims_to_verify` fra `base_draft_id` (standard: nyeste). | F3 |
| `POST /api/applications/{id}/revise` | Chatmelding `{instruction, draft_id?}` → `{task_id}`. Meldingen lagres med en gang. Jobben svarer med en agentmelding: på et spørsmål bare svar (`result.draft_id` null), ellers en ny agentversjon av `draft_id` (standard: nyeste). 409 `no_draft` uten utkast. | F3 |
| `GET /api/applications/{id}/messages` | Chathistorikk: `role` (`user` \| `agent`), `text`, `draft_id` (versjonen svaret laget), `style_rule` (foreslått stilregel, agentmeldinger), `style_rule_saved`, `created_at`, eldste først | F3 |
| `POST /api/applications/{id}/messages/{message_id}/style-rule` | Legger meldingens `style_rule` til i `style_overrides.md` → oppdatert melding. To ganger er en no-op. 404 ukjent melding, 409 `no_style_rule` uten forslag. | F3 |
| `GET /api/drafts/{id}/docx` | Last ned `.docx`. Filnavnet kommer i `Content-Disposition`. | F3 |
| `GET /api/profile/files` | Filer (`path`, `size`, `updated_at`), `folders` (mapper for "Ny fil"), `profile_hash`, `derived_outdated`, `derived_at` | F4 |
| `GET /api/profile/files/{path}` / `PUT` | Les / skriv én profilfil (`content`, `content_hash`). `PUT {content, base_hash}`: `base_hash` er hashen redigeringen startet fra (feil → 409 `conflict`); `null` lager en ny fil (409 `file_exists` hvis den finnes). Ugyldig YAML → 422 `invalid_yaml`. Sti utenfor `PROFILE_DIR`, skjult, med ukjent filtype eller `_` i navnet → 400 `invalid_path`; `<mappe>/_template.md` kan leses. | F4 |
| `GET /api/profile/files/{path}/revisions` | Historikk, nyeste først. Første lagring tar med originalen. | F4 |
| `GET /api/profile/derived` | Destillerte filer: `name`, `content`, `previous_content` (før siste regenerering, null uten), `made_at`, `model` | F4 |
| `POST /api/profile/distill` | → `{task_id}`. Destillerer alltid. 409 `distill_active` hvis en pågår. | F4 |
| `GET /api/settings` / `PATCH` | Redigerbare innstillinger: `key`, `section` (`search`, `scoring`, `notify`, `llm`, `cost`, `schedule`, `sources`), `label`, `help`, `kind` (`bool`, `int`, `number`, `string`, `time`, `enum`, `string_list`), `options`, `min`, `max`, `value`, `default` (YAML), `overridden`. `PATCH {values: {key: verdi}}`, `null` = tilbakestill; verdi lik standard fjerner overstyringen. 422 `unknown_setting` / `invalid_setting`. Returnerer hele listen. | F4 |
| `GET /api/rescore` | `stale_jobs`, `estimated_cost_usd`, `cost_per_job_usd` (ARCHITECTURE §5.5) | F4 |
| `POST /api/rescore` | "Score på nytt" → `{task_id}`. 409 `rescore_active` under en annen scoring eller kjøring. | F4 |
| `GET /api/logs/runs`, `/agent-runs`, `/discarded` | Logg, siste 200 rader hver | F4 |
| `POST /api/runs` | "Kjør nå" → `{task_id}`. 409 `run_active` hvis en kjøring pågår. | F1 |
| `GET /api/tasks/{id}`, `POST /api/tasks/{id}/cancel` | Bakgrunnsjobber | F1 |
| `GET /api/tasks?active=true` | Aktive jobber til indikatoren | F1 |
| `GET /api/health` | Brukes av Docker healthcheck og Uptime Kuma | F5 |

Statusverdier i API-et er snake_case uten norske tegn (`ny`, `interessant`, `utkast`, `sokt`, `intervju`, `tilbud`, `ikke_aktuell`, `avslag`, `trukket`, `utlopt`). Visningsnavn ligger i frontend.

### 7.1 Ekte API (backend-fase 1–2)

Implementert: alle ruter i §7. Mocken svarer `501 not_implemented` på ruter utenfor kontrakten. Der det ekte API-et oppfører seg annerledes enn MSW-mocken, gjelder dette:

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
| `GET /api/llm/usage` | `by_backend` har alltid `claude_code` og `openrouter` (nuller uten kall). `daily` har én rad per Oslo-dag og backend med kall. `spent_usd` er summen av betalte `agent_runs` (alle backender unntatt `claude_code`), også rader fra fjernede backender, som ikke vises per backend. Saldoen caches 10 min; feiler hentingen, er `balance_usd` og `balance_source` null. |
| Kildestatus | Kildene som er slått på i `config/sources.yaml`, pluss kilder med kjøringer. `manual` vises ikke. |
| `POST /api/jobs/{id}/draft` | 404 for ukjent jobb. 409 `draft_exists` også når et utkast til samme jobb allerede lages. Søknaden opprettes først når utkastet er skrevet; feiler oppgaven, er jobben uendret. Oppgavemeldingen er "Ferdig: versjon N", progresjonen "Sjekker profilen" → "Researcher <bedrift>" → "Skriver utkast". |
| Utkast-feil | Ukjent søknad eller versjon gir 404 `not_found` (også `base_draft_id`/`draft_id` som tilhører en annen søknad). Ved kostnadstaket, manglende destillert profil eller ugyldig svar to ganger feiler oppgaven med en norsk melding. |
| `POST /api/applications/{id}/revise` | Revisjonen bygger på versjonen som var nyeste (eller `draft_id`) da meldingen ble sendt. En revisjon med uendret tekst blir et svar uten versjon. |
| `.docx` | Avsender fra `profile.yaml`, bedrift og dato over brevet (ARCHITECTURE §10.2). |

---

## 8. Bølger

Bølgene F0–F4 bygges før backend-fasene i ARCHITECTURE §17. Hver bølge er ferdig når den fungerer på både 390 px og 1440 px i mock-modus, med Vitest- og Playwright-tester.

| Bølge | Innhold | Ferdig når | Avhenger av backend |
|---|---|---|---|
| ~~F0. Skjelett~~ | `web/` med Vite, TS, Tailwind, shadcn, React Router, TanStack Query, MSW. `api/schemas.py` + `export_openapi.py` + typegenerering. App-skall (sidemeny/bunnfaner), tema, PWA-manifest, fixture-sett. | ✅ 2026-10-10 (PR #4) | Nei |
| ~~F1. Daglig sløyfe~~ | Oversikt, Jobber (faner, filtre, sveip, tastatur), Jobbdetalj, bakgrunnsjobb-indikator, "Kjør nå" | ✅ bygget 2026-10-10; venter på brukertest (triage av en mock-dag < 2 min på mobil) | ✅ Koblet til ekte API i fase 2 |
| ~~F2. Tracker~~ | Kanban (PC), gruppert liste (mobil), statusoverganger, neste steg, hendelseslogg | ✅ 2026-10-10 | ✅ Koblet til ekte API i fase 2 |
| ~~F2b. LLM-forbruk~~ | Kortet LLM-forbruk med detaljpanel (§5.1), mock-fixtures for alle saldotilstander (konto, nøkkelgrense, ukjent, ikke satt opp, lav) | ✅ 2026-10-11 | ✅ Koblet i backend-bølge 2b |
| ~~F3. Søknadseditor~~ | Editor, forhåndsvisning, autosave/versjoner, diff, revisjonschat, `claims_to_verify`, `.docx`, `/soknader` | ✅ 2026-10-11 | ✅ Koblet til ekte API i fase 3 |
| ~~F4. Profil, innstillinger, logg~~ | Profileditor med historikk, innstillingsskjema, loggfaner, "Score på nytt" | ✅ 2026-10-11 | ✅ Koblet i fase 4 |
| **F5. Drift** | FastAPI serverer `web/dist`, multi-stage Dockerfile, PWA-ikon, test på mobil via Tailscale. Kodesplitting: Oversikt og Jobber ligger i hovedbunten, resten av skjermene lastes ved første besøk (`lazy` i `routes.tsx`); hovedbunten gikk fra 693 til 304 kB. | `docker compose up` gir hele appen på én port | Bygget 2026-10-11 sammen med fase 4b (ARCHITECTURE §12) |

Rekkefølgen er F0 → F1 → brukertest → F2 → backend-fase 1–2 → 2b/F2b → F3 → fase 3 → F4 → fase 4 (ARCHITECTURE §17). Ved brukertest kjører appen i mock-modus på PC og mobil (`npm run dev:mock -- --host`, §3.2). Funn rettes i dette dokumentet og i kontrakten før neste bølge. Fixture-settet må være realistisk nok til å teste flyten: ~40 jobber over alle jobbtyper, frister, reposts, forkastede jobber og søknader i alle statuser.

---

## 9. Testing

| Nivå | Verktøy | Dekker |
|---|---|---|
| Enhet | Vitest + Testing Library | Hooks (`useTask`), formattering (frist, score), statusoverganger i UI, ord-diff, mock-agentene og `.docx`-zip |
| Kontrakt | `tsc` mot genererte typer | At fixtures og komponenter matcher API-et |
| Ende-til-ende | Playwright mot `dev:mock`, to viewporter (390×844, 1440×900) | Navigasjon, tema og manifest (F0); triage med sveip (mobil) og tastatur (PC), filtre, "Kjør nå" (F1); hele statusflyten fra mobil, dra og slipp med ulovlig kolonne og angre, statusmeny og sidepanel (F2); forbrukskortet → detalj, trykk på søyle, "OpenRouter ikke satt opp" (F2b); autosave, revisjon via chat, diff og gjenoppretting, påstander, kopier og `.docx`, "Lag søknadsutkast" → toast → editor (F3); profil: lagre, historikk og gjenoppretting, ugyldig YAML, ny fil fra mal, regenerer og diff; innstillinger: overstyr, validering, tilbakestill, bryter, ordliste, score på nytt; logg: faner og "Vis jobb" (F4) |

Kommandoer i `web/`: `npm test` (Vitest), `npm run typecheck`, `npm run e2e` (Playwright starter `dev:mock` selv på port 5174). Backend: `uv run pytest`.

