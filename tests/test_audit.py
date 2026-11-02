import json
import os

import pytest

from audit import audit, load_prices, PRESETS, PRICES_DB


def row(model_id, provider, inp, outp, aa, tags="", free=0):
    return dict(model_id=model_id, provider=provider, input_per_m=inp,
                output_per_m=outp, is_free=free, aa_score=aa, tags=tags)


P = [
    row("cur", "a", 3.0, 15.0, 54),
    row("better", "b", 2.0, 10.0, 58, "cheap"),
    row("weak", "c", 0.1, 0.5, 36, "cheap"),
    row("free", "d", 0.0, 0.0, 90, "free", free=1),
    row("unscored", "e", 0.01, 0.01, None),
]
W = dict(monthly_input_m=10, monthly_output_m=2, needs=[], current_model="cur")


def test_picks_cheaper_and_flags_quality_delta():
    r = audit(W, P)
    assert r["current_cost"] == 60.0
    assert r["current_score"] == 54
    # ranked cheapest first; free and unscored models are never recommended
    assert [a["model_id"] for a in r["alternatives"]] == ["weak", "better"]
    assert r["alternatives"][0]["score_delta"] == -18
    assert r["alternatives"][0]["savings_pct"] == 96.7


def test_same_or_better_is_separate():
    r = audit(W, P)
    assert r["same_or_better"]["model_id"] == "better"
    assert r["same_or_better"]["score_delta"] == 4


def test_needs_filter():
    assert audit(dict(W, needs=["long_context"]), P)["alternatives"] == []


def test_model_without_score_makes_no_claim():
    r = audit(dict(W, current_model="unscored"), P)
    assert r["quality_verified"] is False
    assert r["current_score"] is None
    assert r["alternatives"] == []


def test_identical_price_keeps_best_scorer():
    same_px = [P[0], row("low", "x", 0.1, 0.5, 28), row("high", "y", 0.1, 0.5, 36)]
    assert [a["model_id"] for a in audit(W, same_px)["alternatives"]] == ["high"]


def test_missing_current_model_raises():
    with pytest.raises(ValueError):
        audit(dict(W, current_model="nope"), P)


def test_all_presets_run():
    if not os.path.exists(PRICES_DB):
        pytest.skip("needs etl.py output")
    prices = load_prices()
    for w in json.load(open(PRESETS)):
        r = audit(w, prices)
        assert r["current_cost"] > 0
        assert r["quality_verified"] is True
        for a in r["alternatives"]:
            assert a["monthly_cost"] < r["current_cost"]
            assert a["score_delta"] is not None
