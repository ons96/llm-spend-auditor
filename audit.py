"""Weekend 2 audit engine: workload -> current monthly cost + cheaper alternatives.

Quality comes from one column: aa_score (Artificial Analysis Intelligence Index),
a single methodology applied to every model. That is what makes two models comparable.

Usage:
  python3 audit.py                 # audit all presets, print table
  python3 audit.py --export        # also write data/prices.json for the static UI
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
PRICES_DB = os.path.join(ROOT, "data", "prices.db")
PRESETS = os.path.join(ROOT, "data", "presets.json")
PRICES_JSON = os.path.join(ROOT, "data", "prices.json")

EXPORT_COLS = ["model_id", "provider", "input_per_m", "output_per_m",
               "is_free", "context_window", "aa_score", "tags"]


def load_prices(db=PRICES_DB):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute("select * from prices")]


def cost(row, w):
    return row["input_per_m"] * w["monthly_input_m"] + row["output_per_m"] * w["monthly_output_m"]


def audit(w, prices, top=3):
    """Return current monthly cost, its AA score, and cheaper paid models.

    Every alternative carries score_delta (AA points gained or lost). Showing the
    delta is more honest than filtering on an arbitrary quality floor: the reader
    decides whether 18 points are worth a 95% bill cut.

    Free tiers are excluded: rate limits make them unusable at business volume.
    """
    paid = [p for p in prices if not p["is_free"]]
    cur = [p for p in paid if p["model_id"] == w["current_model"]]
    if not cur:
        raise ValueError(f"no paid price rows for {w['current_model']!r}")

    # Median provider price = what a typical buyer pays. min() picked stale reseller
    # discounts (e.g. gpt-4o at half list) and understated current spend.
    cur.sort(key=lambda p: cost(p, w))
    base = cur[len(cur) // 2]
    base_cost = cost(base, w)

    scores = [p["aa_score"] for p in cur if p["aa_score"] is not None]
    cur_score = max(scores) if scores else None
    if cur_score is None:
        # No benchmark = no quality claim. Report spend, recommend nothing.
        return {"current_cost": round(base_cost, 2), "current_provider": base["provider"],
                "current_score": None, "quality_verified": False, "providers": len(cur),
                "alternatives": [], "same_or_better": None}

    best = {}
    for p in paid:
        if p["model_id"] == w["current_model"] or p["aa_score"] is None:
            continue
        if not set(w.get("needs") or []) <= set((p["tags"] or "").split(",")):
            continue
        c = cost(p, w)
        if c < base_cost and (p["model_id"] not in best or c < best[p["model_id"]][0]):
            best[p["model_id"]] = (c, p)
    ranked = sorted(best.values(), key=lambda t: (t[0], -t[1]["aa_score"]))
    # Two models at the same input/output price are the same offer; keep the better
    # scorer so the list shows distinct tradeoffs instead of near-duplicates.
    seen_px, deduped = set(), []
    for c, p in ranked:
        px = (p["input_per_m"], p["output_per_m"])
        if px in seen_px:
            continue
        seen_px.add(px)
        deduped.append((c, p))
    ranked = deduped

    def fmt(c, p):
        return {"model_id": p["model_id"], "provider": p["provider"],
                "monthly_cost": round(c, 2), "score": p["aa_score"],
                "score_delta": p["aa_score"] - cur_score,
                "savings_pct": round(100 * (1 - c / base_cost), 1) if base_cost else 0.0}

    safe = next(((c, p) for c, p in ranked if p["aa_score"] >= cur_score), None)
    return {"current_cost": round(base_cost, 2), "current_provider": base["provider"],
            "current_score": cur_score, "quality_verified": True, "providers": len(cur),
            "alternatives": [fmt(c, p) for c, p in ranked[:top]],
            "same_or_better": fmt(*safe) if safe else None}


def export_json(prices, path=PRICES_JSON):
    """Write the UI contract: cols, rows, plus the UTC date of this export.

    generated_at is additive metadata, not a price column: the page shows it as
    the price half of its freshness line, next to the AA scrape date.
    """
    with open(path, "w") as f:
        json.dump({"cols": EXPORT_COLS,
                   "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                   "rows": [[p[c] for c in EXPORT_COLS] for p in prices]},
                  f, separators=(",", ":"))


if __name__ == "__main__":
    prices = load_prices()
    if "--export" in sys.argv:
        export_json(prices)
        print(f"wrote {PRICES_JSON} ({os.path.getsize(PRICES_JSON) // 1024} KB)")

    def f(a):
        if not a:
            return "-"
        return f"{a['model_id']} ${a['monthly_cost']} (-{a['savings_pct']}%, {a['score_delta']:+d}pts)"

    for w in json.load(open(PRESETS)):
        r = audit(w, prices)
        print(f"{w['id']:21} {w['current_model']:22} ${r['current_cost']:>9} [{r['current_score']}]")
        if not r["alternatives"]:
            print(f"{'':21} already cheapest benchmarked model")
        for a in r["alternatives"]:
            print(f"{'':21} -> {f(a)}")
