# LLM Spend Auditor

Estimates what your LLM workload costs today and what it would cost on
cheaper models that meet the same needs (coding, long context, benchmarked).

Status: Weekend 1 of 4. Pricing ETL and preset workloads are done; the audit
engine and UI come next.

## Run

    python3 etl.py                      # builds data/prices.db
    uv run --with pytest pytest -q      # tests

Pricing source: aggregated LiteLLM, OpenRouter, and models.dev catalogs
(`llm-leaderboard-aggregate`). Prices are normalized to USD per 1M tokens.

The workloads in `data/presets.json` are illustrative, not client data.
