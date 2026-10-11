# Spike 05: OpenRouter + DeepSeek V4.1 Flash

**Dato:** 2026-10-11
**Konklusjon:** Brukeren har valgt `deepseek/deepseek-v4.1-flash` via OpenRouter som reserve når `claude -p` feiler, i stedet for Anthropic API. Modellen er billig nok til at kostnadstaket i praksis ikke betyr noe, og har strukturert output hos de fleste leverandørene. Bygget og testet live 2026-10-11 (se Oppdatering nederst): samme rangering som Haiku, men høyere scorer. Designet står i ARCHITECTURE §8.

## Modellen

Kilde: `GET https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints` (lest 2026-10-11) og [modellsiden](https://openrouter.ai/deepseek/deepseek-v4.1-flash).

| Egenskap | Verdi |
|---|---|
| Modell-ID | `deepseek/deepseek-v4.1-flash` |
| Lagt ut på OpenRouter | 2026-09-10 |
| Kontekst | ~1M tokens (1 048 576 hos de fleste) |
| Maks output | 131k–944k avhengig av leverandør |
| Leverandører | 32 endepunkter (DeepSeek selv, DeepInfra, Together, Fireworks m.fl.) |
| Parametre | `response_format`, `structured_outputs`, `tools`, `tool_choice`, `reasoning`, `reasoning_effort` (ikke alle hos alle) |

## Pris (USD per million tokens)

| Leverandør | Input | Output | Cache-lesing |
|---|---|---|---|
| DeepSeek (førstepart) | 0.15 | 0.60 | 0.003 |
| Billigste (Baidu fp8) | 0.035 | 0.14 | 0.0007 |
| Typisk (Together, Fireworks, Parasail) | 0.30 | 1.20 | 0.006 |

Overslag med dagens volum (live Finn-kjøring 2026-10-10: 63 jobber scoret for $0.06 med Haiku): filter-agenten blir godt under $0.01 per dag. Et søknadsutkast med full kontekst (~20k inn, ~2k ut) koster under $0.01. Månedskostnaden blir trolig under $1.

## Fallgruver

| Funn | Konsekvens |
|---|---|
| Ikke alle leverandørene støtter `structured_outputs` (bl.a. DeepSeek selv, Relace, Novita, Alibaba, SiliconFlow mangler det) | Send `provider.require_parameters: true`, så OpenRouter bare ruter til endepunkter som støtter `response_format` med `json_schema`. Valider svaret mot Pydantic-skjemaet uansett, og prøv én gang til ved ugyldig JSON. |
| Leverandørene kjører ulik kvantisering (fp4, fp8, full) | Kvaliteten kan variere mellom kall. Kan låses med `provider.quantizations` hvis scoringen blir ustabil. |
| Annonsetekst og profilutdrag sendes til tredjepartsleverandører, også utenfor EU/EØS | Send `provider.data_collection: "deny"`, så bare leverandører som ikke lagrer eller trener på data brukes. Profilen sendes bare i destillert form (§6). |
| Svaret har `usage.cost` | Kostnaden logges direkte fra svaret, ingen lokal pristabell. |
| Saldoen: `GET /api/v1/credits` krever en management-nøkkel (vanlig nøkkel gir 403). `GET /api/v1/key` virker med vanlig nøkkel og gir `usage`, `usage_daily`, `usage_monthly`, `limit` og `limit_remaining` (null uten kredittgrense). | Kortet bruker `/credits` hvis `OPENROUTER_MANAGEMENT_KEY` finnes, ellers `limit_remaining` fra `/key` (ARCHITECTURE §8.1). |
| Verifisert 2026-10-11 med brukerens nøkler: `/api/v1/key` gir 200 med `limit`/`limit_remaining`/`usage`, `/api/v1/credits` med management-nøkkelen gir 200 med `total_credits`/`total_usage`. | Begge saldokildene virker. |
| Modellen er ikke Claude | Promptene i `context/prompts/` er skrevet for Claude. Filter-promptens scoring må sjekkes mot et utvalg jobber som allerede er scoret av Haiku før byttet. |

## Oppdatering 2026-10-11: DeepSeek mot Haiku på 63 ekte Finn-jobber

Bølge 2b er bygget. Filter-agenten (prompt v0.2, batch 10) ble kjørt på nytt på alle 63 jobbene fra den første live-kjøringen (2026-10-10), én gang med DeepSeek via OpenRouter og én gang med Haiku, mot hver sin kopi av databasen (lagrede scorer ble ikke endret). Haiku-mot-Haiku viser hvor mye scoren varierer fra kjøring til kjøring, så forskjellen til DeepSeek kan vurderes mot det. Brukeren hadde ikke triagert noen jobber ennå, så det finnes ingen fasit utover Haiku.

| Mot lagret Haiku-score | Haiku på nytt | DeepSeek |
|---|---|---|
| Gjennomsnittlig forskjell | +2,7 | **+19,9** |
| Gjennomsnittlig absolutt forskjell | 5,6 | 20,3 |
| Rangkorrelasjon (Spearman) | 0,88 | 0,84 |
| Forskjell ≥ 20 poeng | 4 | 30 |
| Bytter side av 50 / 70 | 6 / 3 | 24 / 16 |
| Snittscore (lagret 38,4) | 41,2 | 58,3 |
| Kostnad / tid for 63 jobber | $0.061 (estimat) / 5,3 min | $0.052 (betalt) / 7,9 min |

Funn:
- **Rangeringen holder:** DeepSeek sorterer jobbene nesten like likt som Haiku gjør med seg selv. Ingen kall feilet, og alle svar fulgte skjemaet.
- **Scoren er ~20 poeng for høy:** DeepSeek ser de samme hindringene som Haiku (krav om 1–3 års erfaring, internship som krever at man fortsatt studerer, feil domene), men trekker lite for dem. De største avvikene var sommerinternships for studenter (30 → 73) og data science-stillinger med erfaringskrav (12 → 55).
- **Kostnad:** ca. $0.0008 per jobb, høyere enn overslaget, men fortsatt under $1/mnd selv om alt går via reserven.

Konsekvens: DeepSeek er brukbar som **reserve**, fordi rekkefølgen i listen blir riktig, men absolutte scorer fra reserven er ikke sammenlignbare med Claude. Mest synlig: grensen `notify_min_score: 70` for digesten ville sluppet gjennom 16 jobber feil. Reservescorer er merket i `agent_runs` (`fallback_from`). Neste tiltak (HANDOVER): score jobber som ble scoret av reserven på nytt med Claude når `claude -p` virker igjen, og eventuelt en strengere vurderingsskala i filter-prompten hvis reserven blir brukt mye.
