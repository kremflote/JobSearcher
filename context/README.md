# Kontekst

Alt agentene vet om deg kommer fra denne mappen. Kvaliteten på søknadsutkastene avhenger mer av hva som står her enn av noe annet. Se `docs/ARCHITECTURE.md` §6 for hvordan konteksten brukes.

## Struktur

```
context/
├── profile/      LAG 1: Du skriver og vedlikeholder dette
├── derived/      LAG 2: Generert automatisk fra profile/ (ikke rediger for hånd)
└── prompts/      LAG 3: Systemprompter per agent
```

## Hva du fyller ut i `profile/`

| Fil / mappe | Hva | Prioritet |
|---|---|---|
| `profile.yaml` | Harde fakta: utdanning, ferdigheter, språk, praktisk info | Høy |
| `cv.md` | Hele CV-en din som tekst | Høy |
| `projects/` | Én fil per prosjekt. Kopier `_template.md`. | **Svært høy** |
| `experience/` | Én fil per jobb eller verv. Kopier `_template.md`. | Middels |
| `writing_samples/` | Tekster du har skrevet selv, helst søknader. Kopier `_template.md`. | **Svært høy** |
| `motivation.md` | Hva du vil, hva du ikke vil, hva som gir deg energi | Høy |
| `style_overrides.md` | Eksplisitte regler for hvordan søknadene skal skrives | Middels |

## Regler

- **Filer som starter med `_` ignoreres** av programmet. Det er maler. Kopier dem og gi kopien et beskrivende navn, f.eks. `projects/anime-database.md`.
- **Skriv fakta, ikke ferdig søknadstekst.** Agenten formulerer selv. Det den trenger er konkrete detaljer: tall, teknologier, hva *du* gjorde og hva som var vanskelig.
- **Ærlighet slår polering.** Står det at du "kan Kubernetes" fordi du har fulgt én tutorial, kommer det med i søknader og kan bli spurt om i intervju. Bruk nivåfeltene i `profile.yaml`.
- **Endringer plukkes opp automatisk.** Når en fil endres, regenereres `derived/` ved neste kjøring.
- Alle filer kan redigeres i Obsidian. Frontmatter (`---`-blokken øverst) vises som egenskaper.
