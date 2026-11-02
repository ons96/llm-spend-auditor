# LLM Spend Auditor

Estimate what an LLM workload costs today, which cheaper models meet the same
needs, and exactly how much quality each saving costs.

Live: https://ons96.github.io/llm-spend-auditor/

Status: Weekend 4 in progress. The static UI is live, the first real
self-audit is published in `docs/self-audit-2026-11.md`, the writeup is in
`docs/writeup.md`, and the free-audit CTA is open. External audits are pending
(see `QUESTIONS.md`).

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

## Setup

    uv venv && . .venv/bin/activate
    uv pip install -r requirements-dev.txt

`requirements.txt` is the runtime set (the AA scraper needs bs4 and lxml);
`requirements-dev.txt` adds pytest.

## Run

    python3 -m http.server 8000     # open http://localhost:8000/
    python3 -m pytest -q

Opening `index.html` from the filesystem fails because browsers block `fetch`
of local JSON; serve the folder instead. Node is only needed for the tests: the
Python parity test skips without it, and the browser smoke test is dev-only.

    npm ci
    npx playwright install chromium firefox webkit
    npm run test:ui                 # presets, toggle, hash, mobile, dark, CTA

The smoke test runs on Chromium, Firefox and WebKit. On Linux, WebKit needs
system libraries: use `npx playwright install --with-deps webkit` (as CI does)
or limit the run with `UI_BROWSERS=chromium,firefox npm run test:ui`.

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
The data refresh runs weekly via `.github/workflows/refresh-data.yml`, which
scrapes AA, rebuilds the export, tests, and commits only when something moved.

## Get an audit

Free: open an [audit
request](https://github.com/ons96/llm-spend-auditor/issues/new?template=audit-request.md)
with monthly token counts and your current model. Requests use GitHub issues, so
you need a free GitHub account to open one; the auditor itself needs none. Do
not send API keys, prompts or customer data; the numbers are enough.

Background on the method and its limits: [`docs/writeup.md`](docs/writeup.md).
The intake and reply flow is in [`docs/AUDIT_PLAYBOOK.md`](docs/AUDIT_PLAYBOOK.md);
a request is answered with `python3 audit_request.py --url "<share link>"`.

## License

MIT, see [`LICENSE`](LICENSE).
