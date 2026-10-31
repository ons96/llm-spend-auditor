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

MIN_QUALITY = 50.0  # absolute coding_score floor; below this a swap is not a credible claim
QUALITY_SLACK = 0.0 # alternatives must score >= current model


def load_prices(db=PRICES_DB):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute("select * from prices")]


def cost(row, w):
    return row["input_per_m"] * w["monthly_input_m"] + row["output_per_m"] * w["monthly_output_m"]


def audit(w, prices, top=3):
    """Return dict(current_cost, current_provider, floor, alternatives=[...]).

    Free-tier rows are excluded: rate limits make them unusable at business volume.
    """
    paid = [p for p in prices if not p["is_free"]]
    cur = [p for p in paid if p["model_id"] == w["current_model"]]
    if not cur:
        raise ValueError(f"no paid price rows for {w['current_model']!r}")
    # ponytail: cheapest provider for current model = conservative savings claim
    base = min(cur, key=lambda p: cost(p, w))
    scores = [p["coding_score"] for p in cur if p["coding_score"] is not None]
    floor = max((max(scores) - QUALITY_SLACK) if scores else 0.0, MIN_QUALITY)
    best = {}
    for p in paid:
        tags = set((p["tags"] or "").split(","))
        if p["model_id"] == w["current_model"] or p["coding_score"] is None:
            continue
        if p["coding_score"] < floor or not set(w["needs"]) <= tags:
            continue
        c = cost(p, w)
        if p["model_id"] not in best or c < best[p["model_id"]][0]:
            best[p["model_id"]] = (c, p)
    base_cost = cost(base, w)
    alts = sorted(best.values(), key=lambda t: t[0])[:top]
    return {
        "current_cost": round(base_cost, 2),
        "current_provider": base["provider"],
        "quality_floor": round(floor, 1),
        "alternatives": [{
            "model_id": p["model_id"], "provider": p["provider"],
            "monthly_cost": round(c, 2), "coding_score": p["coding_score"],
            "savings_pct": round(100 * (1 - c / base_cost), 1) if base_cost else 0.0,
        } for c, p in alts if c < base_cost],
    }


def export_json(prices, path=PRICES_JSON):
    cols = ["model_id", "provider", "input_per_m", "output_per_m",
            "is_free", "context_window", "coding_score", "tags"]
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
        a = r["alternatives"][0] if r["alternatives"] else None
        alt = f"{a['model_id']} ${a['monthly_cost']} (-{a['savings_pct']}%)" if a else "none"
        print(f"{w['id']:22} {w['current_model']:18} ${r['current_cost']:>9} -> {alt}")
