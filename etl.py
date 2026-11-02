"""ETL: live pricing (LiteLLM feed) + live quality (AA index) -> data/prices.db.

Two sources, both refreshed automatically:
  prices  : https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
  quality : data/aa_scores.json (written by scrape_aa.py)

Why AA instead of the benchmark averages in llm-leaderboard-aggregate: those
averages mix different benchmark subsets per model, so a model scored only on
LiveCodeBench outranks a model scored on SWE-bench + LiveCodeBench. AA applies
one methodology to every model it lists, which is the only comparison a buyer
should trust.

Usage: python3 etl.py [--offline] [--refresh]
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
OUT_DB = os.path.join(DATA, "prices.db")
AA_JSON = os.path.join(DATA, "aa_scores.json")
CACHE = os.path.join(DATA, "litellm_cache.json")

PRICES_URL = ("https://raw.githubusercontent.com/BerriAI/litellm/main/"
              "model_prices_and_context_window.json")
CHEAP_INPUT_PER_M = 0.5
LONG_CONTEXT = 200_000
CHAT_MODES = {"chat", "responses"}
CACHE_TTL_S = 24 * 3600


def fetch_prices(offline: bool = False, refresh: bool = False) -> dict:
    """Live feed, cached 24h. --offline forces the cache."""
    fresh = os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < CACHE_TTL_S
    if offline or (fresh and not refresh):
        with open(CACHE) as f:
            return json.load(f)
    req = urllib.request.Request(PRICES_URL, headers={"User-Agent": "llm-spend-auditor"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    data = json.loads(raw)
    with open(CACHE, "wb") as f:
        f.write(raw)
    return data


def base_model(key: str) -> str:
    """'openrouter/anthropic/claude-sonnet-5' -> 'claude-sonnet-5'."""
    return key.split("/", 1)[1] if "/" in key else key


def tags_for(inp_m, free, ctx, aa) -> str:
    tags = []
    if free:
        tags.append("free")
    if free or inp_m <= CHEAP_INPUT_PER_M:
        tags.append("cheap")
    if ctx and ctx >= LONG_CONTEXT:
        tags.append("long_context")
    if aa is not None:
        tags.append("scored")
    return ",".join(tags)


def load_aa() -> dict:
    if not os.path.exists(AA_JSON):
        return {}
    with open(AA_JSON) as f:
        return {k: v["aa_index"] for k, v in json.load(f)["models"].items()}


def run(offline: bool = False, refresh: bool = False):
    """Rebuild prices.db. Returns (rows, distinct_models, aa_matched)."""
    feed = fetch_prices(offline, refresh)
    aa = load_aa()
    rows, matched = [], set()
    for key, v in feed.items():
        if v.get("mode") not in CHAT_MODES:
            continue
        inp, outp = v.get("input_cost_per_token"), v.get("output_cost_per_token")
        if inp is None or outp is None:
            continue
        mid = base_model(key)
        inp_m, out_m = round(inp * 1e6, 6), round(outp * 1e6, 6)
        free = 1 if (inp == 0 and outp == 0) else 0
        ctx = v.get("max_input_tokens") or v.get("max_tokens")
        score = aa.get(mid)
        if score is not None:
            matched.add(mid)
        rows.append((mid, v.get("litellm_provider") or "unknown", key, inp_m, out_m,
                     free, ctx, score, tags_for(inp_m, free, ctx, score)))

    tmp = OUT_DB + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.execute("""create table prices (model_id text, provider text, provider_model_id text,
        input_per_m real, output_per_m real, is_free int, context_window int,
        aa_score int, tags text)""")
    db.executemany("insert into prices values (?,?,?,?,?,?,?,?,?)", rows)
    db.execute("create index ix_model on prices(model_id)")
    db.execute("create index ix_score on prices(aa_score)")
    db.commit()
    db.close()
    os.replace(tmp, OUT_DB)
    return len(rows), len({r[0] for r in rows}), len(matched)


if __name__ == "__main__":
    n, m, a = run("--offline" in sys.argv, "--refresh" in sys.argv)
    print(f"prices.db: {n} rows, {m} models, {a} with AA score")
