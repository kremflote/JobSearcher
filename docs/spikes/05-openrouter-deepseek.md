# Spike 05: OpenRouter + DeepSeek V4.1 Flash

**Dato:** 2026-10-11
**Konklusjon:** Brukeren har valgt `deepseek/deepseek-v4.1-flash` via OpenRouter som reserve når `claude -p` feiler, i stedet for Anthropic API. Modellen er billig nok til at kostnadstaket i praksis ikke betyr noe, og har strukturert output hos de fleste leverandørene. Ikke testet live ennå. Designet står i ARCHITECTURE §8.

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
