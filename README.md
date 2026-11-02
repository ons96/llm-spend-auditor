# LLM Spend Auditor

Estimate what an LLM workload costs today, which cheaper models meet the same
needs, and exactly how much quality each saving costs.

Live: https://ons96.github.io/llm-spend-auditor/

## Why another cost calculator

Most "switch to a cheaper model" advice compares models scored on different
benchmarks. This tool uses one normalized quality signal, the Artificial
Analysis Intelligence Index, and the LiteLLM public price feed. Every savings
figure sits next to the AA score delta it costs, so "95% cheaper" is never
shown without the index points you give up.

A model without an AA score is never recommended and never compared. Free
tiers are excluded from recommendations because rate limits make them unusable
at business volume. The current model is priced at the median across providers,
not the cheapest listing, because cheap listings are often stale reseller
discounts that understate the bill.

## What is here

| Path | Role |
|---|---|
| `index.html`, `audit.js` | Static UI, all math in the browser, no build step |
| `audit.py` | Audit engine and JSON export (same math as `audit.js`) |
| `etl.py` | LiteLLM prices + AA scores -> `data/prices.db` |
| `scrape_aa.py` | Artificial Analysis leaderboard -> `data/aa_scores.json` |
| `data/presets.json` | 10 example workloads |
| `data/prices.json` | Exported price table the UI reads (committed) |
| `tests/` | Engine tests plus node parity tests for the UI math |

## Run

    python3 -m http.server 8000     # open http://localhost:8000/
    python3 -m pytest -q

Opening `index.html` from the filesystem fails because browsers block `fetch`
of local JSON; serve the folder instead. Node is only needed for the UI parity
tests, and they skip when it is absent.

## Regenerate the dataset

    python3 scrape_aa.py            # refuses to write under 50 rows
    python3 etl.py --refresh        # busts the 24h price cache
    python3 audit.py --export       # writes data/prices.json

## Coverage

17 models have both an AA score and a published paid price, out of 1,879
distinct model ids (1,810 with a paid price). Public price feeds lag model
releases by weeks, so the page says "17 verified" rather than "1,879
available". See `HANDOFF.md` for the schema, decisions and their rationale.

The workloads in `data/presets.json` are illustrative, not client data.
