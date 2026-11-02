from audit import audit

P = [
    dict(model_id="cur", provider="a", input_per_m=3.0, output_per_m=15.0, is_free=0, coding_score=55.0, tags="coding"),
    dict(model_id="good", provider="b", input_per_m=0.5, output_per_m=2.0, is_free=0, coding_score=60.0, coverage=2, tags="coding,cheap"),
    dict(model_id="weak", provider="c", input_per_m=0.1, output_per_m=0.2, is_free=0, coding_score=20.0, coverage=3, tags="coding,cheap"),
    dict(model_id="free", provider="d", input_per_m=0.0, output_per_m=0.0, is_free=1, coding_score=90.0, tags="coding,free"),
]
W = dict(monthly_input_m=10, monthly_output_m=2, needs=["coding"], current_model="cur")

def test_picks_cheaper_model_above_floor():
    r = audit(W, P)
    assert r["current_cost"] == 60.0
    assert [a["model_id"] for a in r["alternatives"]] == ["good"]  # weak below floor, free excluded
    assert r["alternatives"][0]["savings_pct"] == 85.0

def test_low_coverage_excluded():
    q = [dict(P[1], coverage=1)] + [P[0]]
    assert audit(W, q)["alternatives"] == []


def test_needs_filter():
    assert audit(dict(W, needs=["long_context"]), P)["alternatives"] == []


def test_all_presets_run():
    import json, os
    from audit import load_prices, PRESETS, PRICES_DB
    if not os.path.exists(PRICES_DB):
        return  # ponytail: needs etl.py output; skip in clean checkout
    prices = load_prices()
    for w in json.load(open(PRESETS)):
        r = audit(w, prices)
        assert r["current_cost"] > 0
        for a in r["alternatives"]:
            assert a["monthly_cost"] < r["current_cost"]
