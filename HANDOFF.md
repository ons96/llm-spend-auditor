# Handoff - LLM Spend Auditor

Last updated 2026-11-02. Weekends 1-3 are complete, pushed and deployed.
Live: https://ons96.github.io/llm-spend-auditor/

Repo: https://github.com/ons96/llm-spend-auditor (public, branch `master`)
Local: `~/CodingProjects/llm-spend-auditor`

## What this is

A portfolio project that audits an LLM bill: given a monthly workload (input
tokens, output tokens, needs), it finds cheaper models and reports exactly how
much quality is given up. Quality comes from the Artificial Analysis
Intelligence Index; prices come from the LiteLLM price feed.

The product thesis: most "switch to a cheaper model" advice is dishonest
because it compares models scored on different benchmarks. This tool uses one
normalized index and shows the quality delta next to every dollar figure.

## Current state

```
17af0fd  feat: static audit UI for GitHub Pages
0470213  fix: regenerate prices.json with key-tail slugs
2e85ab1  docs: add handoff for harness migration
b0f361d  chore: untrack litellm 24h cache
123086e  feat: AA-score audit engine, honest quality deltas
```

The current HANDOFF is itself the latest docs commit. 15 tests pass. Run from
the repo root:

```
python3 -m pytest -q
```

Files:

| File | Role |
|---|---|
| `index.html` | Static UI: inputs, results table, shareable URL hash |
| `audit.js` | Browser port of the audit math (also loadable from node) |
| `scrape_aa.py` | Scrapes AA leaderboard -> `data/aa_scores.json` |
| `etl.py` | Live LiteLLM prices + AA scores -> `data/prices.db` |
| `audit.py` | Audit engine + JSON export -> `data/prices.json` |
| `data/presets.json` | 10 example workloads |
| `data/prices.json` | Exported price table for the UI (committed, 231 KB) |
| `data/aa_scores.json` | Scraped AA index (committed, with `scraped_at`) |
| `tests/` | 15 tests, including a node parity check for the UI math |

`data/prices.db` and `data/litellm_cache.json` are gitignored (regenerated).

### Regenerate everything

```
python3 scrape_aa.py            # writes data/aa_scores.json, refuses if <50 rows
python3 etl.py --refresh        # busts the 24h price cache, writes data/prices.db
python3 audit.py --export       # writes data/prices.json, prints all presets
```

`etl.py --offline` uses the cache only. `scrape_aa.py --self-test` checks the
slug logic.

## Data sources

| Source | URL | Notes |
|---|---|---|
| AA leaderboard | `https://artificialanalysis.ai/leaderboards/models` | One server-rendered `<table>`, 86 rows, 42 models. Plain curl + browser UA + bs4. No JS, no Playwright. |
| LiteLLM prices | `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json` | 4,553 entries, 3,265 `mode='chat'`. Cached 24h at `data/litellm_cache.json`. |

Current output: 3,297 priced rows, 1,879 distinct model ids (1,810 with a paid
price), **17 with an AA score**.

## Schema (do not change casually)

`prices` table, 9 columns:

```
model_id, provider, provider_model_id, input_per_m, output_per_m,
is_free, context_window, aa_score, tags
```

`tags` is a comma string drawn from: `free`, `cheap` (<= 0.5 $/M input),
`long_context` (>= 200k), `scored`.

`EXPORT_COLS` in `audit.py` is the JSON contract for the UI and omits
`provider_model_id`.

## Decisions already made, and why

Do not silently revert these. Each one cost a debugging cycle.

1. **Quality source is AA only.** The earlier aggregate DB
   (`llm-leaderboard-aggregate/db/model_providers.db`) was abandoned. Its row
   for `gpt-4o` carried chat 9.7 / coding 13.8 while dated siblings carried
   63.1 / 49.1 / 47.6 - an alias merge across mismatched sources. AA applies
   one methodology to every model.

2. **No quality floor.** An earlier build dropped anything below an arbitrary
   score. That hid good recommendations (translation: minimax-m3 -> haiku-5-5
   is both cheaper and +17 points) and hid bad ones. Every alternative now
   carries `score_delta` and the reader judges.

3. **Never claim quality without a score.** If the current model has no AA
   score, `audit()` returns `quality_verified=false`, `current_score=null`,
   `alternatives=[]`. It will not guess.

4. **Base price is the median across providers, not the minimum.** The minimum
   picked stale reseller discounts (gpt-4o at 1.25/5 vs the 2.5/10 list price)
   and understated the bill.

5. **Dedupe identical prices, keep the higher scorer.** Two models at the same
   `input_per_m`/`output_per_m` are the same offer. `gpt-6-luna` (28) and
   `claude-haiku-5-5` (36) cost identical $0.10/$0.50; keeping the higher
   score means Luna is never recommended.

6. **`base_model()` takes the key tail**, `key.rsplit("/", 1)[-1]`. LiteLLM
   has multi-hop keys (`openrouter/anthropic/claude-sonnet-5`) and the model
   name is always the last segment. Taking `split("/")[1]` broke matching and
   inflated the model count with duplicates.

7. **Free-tier rows are excluded from alternatives.** They are not
   sustainable offers and they made every preset look 99% cheaper.

8. **Old models cannot be re-scored.** AA retired them: `gpt-4o` reports
   `"intelligenceIndex": null`, `claude-sonnet-4-5` is 404. Any hand-curated
   tier file would be permanently stale, which is why the live feed replaced
   it.

9. **The UI runs a port of the engine, not the engine.** There is no backend,
   so `audit.js` repeats the math in the browser. `tests/test_ui_math.py` runs
   both implementations on the same rows for all 10 presets and the edge cases,
   so a rule changed in `audit.py` without `audit.js` fails a test. Do not
   "simplify" the page by dropping `score_delta` from a row that shows a
   saving.

10. **The URL hash is the report format.**
    `#model=...&input=...&output=...&needs=...` is the whole state: no cookies,
    no local storage, no server. Editing rewrites it, loading restores it, and
    the preset selector is re-matched by exact values, so an edited preset
    reads "Custom" instead of claiming to be the preset.

11. **The committed export was stale and is now regenerated.** The old
    `data/prices.json` predated the `base_model()` key-tail fix: 1,239 ids
    still carried provider prefixes, which split models into several rows and
    hid three scored models (14 verified instead of 17). Preset money numbers
    did not change, only the median provider's name, because provider rows now
    merge under the right model id. Regenerate with `python3 audit.py --export`,
    never by hand.

12. **Freshness comes from the data, not from the page.** `scrape_aa.py` writes
    `scraped_at` (UTC date) into `data/aa_scores.json` and the page renders it.
    Never hardcode a date in `index.html`, and never call the data "live": the
    page serves a committed snapshot.

13. **The page states its coverage.** It shows "17 verified ... out of 1,810
    paid models, from 1,879 distinct model ids", computed from the snapshot,
    instead of hiding the gap. Free-tier-only ids are counted and called out as
    never recommended.

## The 17 scored models (AA index | $/M in | $/M out)

```
claude-opus-5-5          58   4.00   20.00
gpt-6-astra              57  10.00   50.00
claude-sonnet-5-5        54   2.00   10.00
gemini-4-argon           50   2.00   10.00
claude-fable-5-1         50  10.00   50.00
muse-wonder              43   5.40   27.00
claude-haiku-5-5         36   0.10    0.50
deepseek-v4-1-flash-1017 32   0.30    1.20
step-5-preview           29   1.00    2.70
gpt-6-luna               28   0.10    0.50
mistral-large-4          26   1.36    4.18
muse-spark-open          25   1.688   5.738
deepseek-v4-pro-0813     23   1.32    3.96
minimax-m3               19   0.288   1.152
inkling-small            13   (varies)
inkling                  12   (varies)
command-a                 6   (varies)
```

Pareto frontier: `gpt-6-luna` (28) is dominated by `claude-haiku-5-5` (36) at
the same price; `claude-opus-5-5` (58) dominates `gpt-6-astra` (57, 5x the
price). The interesting gap is `sonnet-5-5` (54) to `opus-5-5` (58): 4 index
points for double the price.

## Known limits

- **17 scored models out of 1,879 priced ids** (1,810 with a paid price). 28 of
  AA's 42 frontier models have no published price yet (glm-5-3, grok-4-7,
  gemini-4-carbon, qwen3-8-max, kimi-k3-1-pro, minimax-m3-1-flash). Public
  price feeds lag open-model releases by weeks. This is accepted, not a bug.
  Frame it as "17 verified" rather than "1,879 available".
- **The UI is verified at the math layer, not in a real browser.** jsdom ran
  the page for all 10 presets and the edge paths (hash restore, unscored
  model, unknown model, zero tokens); layout and CSS were inspected by reading
  the file. There is no visual regression test.
- **`index.html` must be served over http(s).** `file://` blocks `fetch` of the
  local JSON. The page catches that and prints the `python3 -m http.server`
  command instead of showing empty results.
- **Scraping is coupled to AA's table markup.** `parse()` expects one table
  with those column headers. If AA redesigns, `scrape_aa.py` fails loudly
  (refuses to write under 50 rows) rather than writing garbage.
- **OpenRouter was evaluated and rejected.** Its `/api/v1/models` matched only
  11 of AA's 42 slugs and none of the open frontier models.
- **`audit.py` must be imported with the repo root on `sys.path`.** `pytest.ini`
  sets `pythonpath = .`; run pytest from the repo root.

## Weekend 3 delivered (2026-11-02)

Live: https://ons96.github.io/llm-spend-auditor/ (Pages: branch `master`, root).

1. `index.html` + `audit.js` at the repo root. Reads `data/prices.json`,
   `data/presets.json` and `data/aa_scores.json`; all math in the browser, no
   backend, no build step, no dependencies.
2. Preset selector (the 10 in `data/presets.json`) plus manual model and token
   inputs, and checkbox needs (`cheap`, `long_context`).
3. Results: three summary cards (current spend, cheapest alternative, same or
   better quality) and a table with $/M in, $/M out, monthly cost, savings and
   the AA score delta in the same row. Negative deltas are amber and labelled
   "trade-off"; non-negative ones are green and labelled "same or better".
4. Freshness line from `scraped_at` in `data/aa_scores.json`, e.g. "Dataset
   last updated 2026-11-02".
5. Shareable report: the URL hash is rewritten on every edit and restored on
   load, which also re-selects the matching preset. No accounts, no server,
   no tracking.
6. Pages enabled via the API, deploy from `master` root.
7. Verified: the URL returns 200, and the deployed HTML, JS and data were
   fetched back and run under jsdom against `audit.py` for all 10 presets plus
   the hash-restore, unscored-model, unknown-model and zero-token paths.

## Next: Weekend 4

1. One real self-audit using `LLM-API-Key-Proxy` telemetry on VPS-40.
2. Three external anonymized audits recruited from r/LocalLLaMA and dev
   Discords.
3. A writeup and a "book a free audit" CTA.

## Style rules for whoever continues

- Free tools only. No paid services, no paid APIs.
- Committed files: plain ASCII, no emoji, no box drawing.
- Conventional commits, subject <= 50 chars.
- Run `python3 -m pytest -q` before committing.
- The repo has a gitleaks pre-push hook; pushes are clean so far.
