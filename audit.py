"""Weekend 2 audit engine: workload -> current monthly cost + cheaper alternatives.

Usage:
  python3 audit.py                 # audit all presets, print table
  python3 audit.py --export        # also write data/prices.json for the static UI
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PRICES_DB = os.path.join(ROOT, "data", "prices.db")
PRESETS = os.path.join(ROOT, "data", "presets.json")
PRICES_JSON = os.path.join(ROOT, "data", "prices.json")

MIN_FLOOR = 50.0  # absolute score floor (coding or chat); below this a swap is not a credible claim
MIN_COVERAGE = 2    # alternatives need >=2 benchmarks; single-benchmark scores are noise
QUALITY_SLACK = 0.0 # alternatives must score >= current model
MIN_COVERAGE = 2   # benchmarks behind a score; 1-benchmark scores are noise, not a claim


def load_prices(db=PRICES_DB):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute("select * from prices")]


def cost(row, w):
    return row["input_per_m"] * w["monthly_input_m"] + row["output_per_m"] * w["monthly_output_m"]


def score_col(w):
    """Coding presets judged on coding score, everything else on reasoning/chat score."""
    return "coding_score" if "coding" in w["needs"] else "chat_score"


def audit(w, prices, top=3):
    """Return dict(current_cost, current_provider, score_col, current_score, quality_floor,
    alternatives=[cheapest models above floor], same_or_better=cheapest model scoring >= current).

    Free-tier rows are excluded: rate limits make them unusable at business volume.
    """
    col = score_col(w)
    paid = [p for p in prices if not p["is_free"]]
    cur = [p for p in paid if p["model_id"] == w["current_model"]]
    if not cur:
        raise ValueError(f"no paid price rows for {w['current_model']!r}")
    # median provider price = what a typical buyer pays; min() picked stale discount rows
    # (e.g. gpt-4o at half list price on one reseller) and understated current spend.
    cur.sort(key=lambda p: cost(p, w))
    base = cur[len(cur) // 2]
    base_cost = cost(base, w)
    scores = [p[col] for p in cur if p.get(col) is not None]
    cur_score = max(scores) if scores else None
    floor = max(MIN_FLOOR, (cur_score or 0) - QUALITY_SLACK)
    strict = max(MIN_FLOOR, cur_score or 0)
    best = {}
    for p in paid:
        s = p.get(col)
        if p["model_id"] == w["current_model"] or s is None or s < floor \
                or (p.get("coverage") or 0) < MIN_COVERAGE:
            continue
        if not set(w["needs"]) <= set((p["tags"] or "").split(",")):
            continue
        c = cost(p, w)
        if c < base_cost and (p["model_id"] not in best or c < best[p["model_id"]][0]):
            best[p["model_id"]] = (c, p)
    ranked = sorted(best.values(), key=lambda t: t[0])

    def fmt(c, p):
        return {"model_id": p["model_id"], "provider": p["provider"],
                "monthly_cost": round(c, 2), "score": round(p[col], 1),
                "savings_pct": round(100 * (1 - c / base_cost), 1) if base_cost else 0.0}

    safe = next(((c, p) for c, p in ranked if p[col] >= strict), None)
    return {
        "current_cost": round(base_cost, 2),
        "current_provider": base["provider"],
        "score_col": col,
        "current_score": round(cur_score, 1) if cur_score is not None else None,
        "quality_floor": round(floor, 1),
        "alternatives": [fmt(c, p) for c, p in ranked[:top]],
        "same_or_better": fmt(*safe) if safe else None,
    }


def export_json(prices, path=PRICES_JSON):
    cols = ["model_id", "provider", "input_per_m", "output_per_m",
            "is_free", "context_window", "coding_score", "chat_score", "coverage", "tags"]
    with open(path, "w") as f:
        json.dump({"cols": cols, "rows": [[p[c] for c in cols] for p in prices]},
                  f, separators=(",", ":"))


if __name__ == "__main__":
    prices = load_prices()
    if "--export" in sys.argv:
        export_json(prices)
        print(f"wrote {PRICES_JSON} ({os.path.getsize(PRICES_JSON) // 1024} KB)")
    for w in json.load(open(PRESETS)):
        r = audit(w, prices)
        f = lambda a: f"{a['model_id']} ${a['monthly_cost']} (-{a['savings_pct']}%, {a['score']})" if a else "none"
        a = r["alternatives"][0] if r["alternatives"] else None
        print(f"{w['id']:21} {w['current_model']:17} ${r['current_cost']:>8} "
              f"[{r['current_score']}] cheapest: {f(a)} | same+: {f(r['same_or_better'])}")
