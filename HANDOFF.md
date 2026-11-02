# Handoff - LLM Spend Auditor

Last updated 2026-11-02. Weekends 1-3 are complete and deployed. Weekend 4 is
in progress: the self-audit, writeup and CTA are done; the three external
audits need the owner's accounts (see `QUESTIONS.md`).
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

The full history is in git; run `git log --oneline -10` from the repo root
rather than trusting a hash list copied into this file.

35 Python tests pass, plus a committed browser smoke test on three engines.
Run from the repo root:

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
| `tests/` | 35 tests: node parity, request report CLI, AA scraper |
| `requirements.txt`, `requirements-dev.txt` | Python deps: bs4 + lxml, plus pytest |
| `LICENSE` | MIT |
| `docs/self-audit-2026-11.md` | Weekend 4 self-audit on real gateway telemetry |
| `docs/writeup.md` | Portfolio writeup: method, rules, limits |
| `docs/AUDIT_PLAYBOOK.md` | Recruit, run, anonymize and publish external audits |
| `docs/outreach.md` | Reddit/Discord drafts, not posted |
| `audit_request.py` | Request (or share URL) -> markdown report, one command |
| `QUESTIONS.md` | Decisions and the one open item (external audits) |
| `tests/browser/smoke.mjs` | Playwright smoke test for the page |
| `package.json`, `package-lock.json` | Dev-only Playwright dependency |
| `.github/workflows/refresh-data.yml` | Weekly AA + price refresh, tested before commit |
| `.github/workflows/ui-check.yml` | Browser smoke test + pytest on push |
| `.github/ISSUE_TEMPLATE/audit-request.md` | Free-audit intake, token counts only |

`data/prices.db` and `data/litellm_cache.json` are gitignored (regenerated).

### Regenerate everything

Install once in a venv: `uv venv && . .venv/bin/activate && uv pip install -r
requirements-dev.txt`.

```
python3 scrape_aa.py            # writes data/aa_scores.json, refuses if <50 rows
python3 etl.py --refresh        # busts the 24h price cache, writes data/prices.db
python3 audit.py --export       # writes data/prices.json, prints all presets
```

`etl.py --offline` uses the cache only. `scrape_aa.py --self-test` checks the
slug logic. `audit.py --export` also stamps `generated_at` (UTC date) into
`data/prices.json`, which the page shows as the price half of its freshness
line. The weekly workflow runs the same three commands and commits when the
data moved. Verified by manual dispatch on 2026-11-02: every step passed and
no data changed, including the AA scrape from a GitHub runner. A separate
push-triggered workflow (`ui-check.yml`) runs the browser smoke test and
pytest whenever the page, data or tests change.

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

14. **Both dates are shown, and neither is called live.** `scraped_at` (AA) and
    `generated_at` (price export) come from the files, not from `Date.now()`.
    If either is missing the page says "unknown" rather than guessing. A static
    page that implies live data is the same dishonesty as a savings figure with
    no quality delta.

15. **The refresh workflow commits to master, and that redeploys Pages.** It
    scrapes, rebuilds, exports, runs pytest, and only then commits, so bad data
    cannot land silently. `QUESTIONS.md` notes the pull-request alternative if
    review is wanted. Do not add secrets to it: it needs none.

16. **The self-audit publishes its own coverage gap.** The gateway telemetry
    carries tokens for 4.9% of calls and an AA score for 0.011% of measured
    tokens. The writeup says so up front instead of presenting a $0.92/month
    counterfactual as a finding. Do not "clean up" those caveats.

17. **The table hides rate and verdict columns under 720px, never the quality
    delta.** Savings and `score_delta` stay on the phone view; the AA score and
    verdict are redundant there. The honesty rule outranks the column count.

18. **Provider names mean two different things; keep them separate.** The
    self-audit omits the gateway's provider ids on the owner's instruction
    (`QUESTIONS.md`). The UI's Provider column shows LiteLLM catalog providers
    (anthropic, azure_ai, fireworks_ai) because the median price is computed
    across them and the reader needs to see which offer is being quoted. Do not
    "clean up" the UI by removing it, and do not add gateway provider ids to
    the self-audit.

19. **The audit request is prefilled, not just a link to a template.** Model,
    token volumes, needs and the share URL are encoded into the issue body. It
    still requires a GitHub account, and the copy says so after a first draft
    wrongly claimed "no accounts". Keep that claim accurate.

20. **"Show all" is a toggle, default three.** Hiding every option after three
    was an arbitrary limit; `gpt-6-astra` has more than a dozen. All rows carry
    the delta in both states, and the toggle never changes the audit math.

21. **The browser test checks wiring, the node test checks the math.**
    `tests/browser/smoke.mjs` drives real Chromium over all 10 presets, the
    toggle, error paths, hash restore, mobile overflow, dark mode and CTA
    prefill. Do not replace it with a second parity test, and do not let the
    node parity test be deleted because the browser test passes.

22. **Reports are generated from the committed snapshot, not the database or
    the network.** `audit_request.py` reads `data/prices.json`, the exact file
    the page serves, and accepts the page's share URL directly. That is what
    makes a reply match the link. Do not make it fetch live prices: a report
    that disagrees with the link is worse than a dated one.

23. **External audits are opt-in and anonymized.** The playbook requires
    permission before publishing, a label instead of a company name, and no
    prompts or outputs. Three completed rows is the Weekend 4 target; do not
    pad the sample with audits that were never run.

24. **The code is MIT.** The owner approved it on 2026-11-02; without a license
    a public repo is "all rights reserved" and portfolio readers cannot reuse
    anything. Keep the copyright line as `ons96`, and do not relicense without
    the owner.

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
- **Browser coverage is Chromium, Firefox and WebKit in CI only.** The smoke
  test drives all three; `ui-check` installs WebKit's system libraries. Local
  WebKit runs need `npx playwright install --with-deps webkit`, or limit with
  `UI_BROWSERS=chromium,firefox`. The test checks wiring and layout overflow,
  not pixel rendering, so a CSS regression that keeps elements visible can
  still slip through.
- **Playwright is a dev dependency, not part of the site.** `node_modules` is
  gitignored; the deployed page still has no build step. If the browser test
  fails in CI, fix the page, not the test.
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
- **Telemetry coverage is the binding limit on the self-audit.** 95% of gateway
  calls carry no token counts, and the only AA-scored model with measured
  traffic saw 659 tokens. Any future self-audit should state its coverage
  before its numbers; see `docs/self-audit-2026-11.md`.
- **The refresh workflow can fail on AA's side.** If AA blocks the runner or
  changes markup, `scrape_aa.py` exits non-zero and nothing is committed. That
  is the intended failure mode; do not add a fallback that writes stale data.

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

## Weekend 4 (in progress, 2026-11-02)

1. **Self-audit: done.** `docs/self-audit-2026-11.md`, built from the
   `api_calls` telemetry table on VPS-40 (read-only, no prompts). 28,227 calls,
   $0 recorded spend, 4.9% with token counts, 0.011% of measured tokens on a
   scored model. The auditor refuses to recommend for the real top model.
2. **Three external anonymized audits: not done, but the pipeline is ready.**
   `docs/AUDIT_PLAYBOOK.md` is the step-by-step plan (ask, intake, run, reply,
   publish, cadence), `docs/outreach.md` has the copy, the `audit` label marks
   requests, and `audit_request.py` turns a share link into a report in one
   command. Recruiting still needs the owner's account and identity; the CTA
   catches inbound requests without posting. `QUESTIONS.md` is the open item.
3. **Writeup: done.** `docs/writeup.md` is the broader piece (method, three
   rules, self-audit findings, limits); `docs/self-audit-2026-11.md` is the
   data. A comparative writeup still waits for external requests.
4. **"Book a free audit" CTA: live and prefilled.** GitHub issues with model,
   token counts, needs and the share URL in the body; token counts only, no
   keys or prompts. Linked from the page and the README.
5. **Optional polish: done.** Full option list toggle, Open Graph tags,
   axe-core pass (zero violations at desktop, mobile and dark), and the
   browser smoke test committed to CI on Chromium, Firefox and WebKit.

## Style rules for whoever continues

- Free tools only. No paid services, no paid APIs.
- Committed files: plain ASCII, no emoji, no box drawing.
- Conventional commits, subject <= 50 chars.
- Run `python3 -m pytest -q` before committing.
- The repo has a gitleaks pre-push hook; pushes are clean so far.
