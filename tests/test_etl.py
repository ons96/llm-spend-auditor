import json
import os

import etl


def test_tags():
    assert etl.tags_for(0.1, 0, 256000, 60) == "cheap,long_context,scored"
    assert etl.tags_for(5.0, 0, 8000, None) == ""
    assert etl.tags_for(0.0, 1, None, 20) == "free,cheap,scored"


def test_base_model():
    assert etl.base_model("openrouter/anthropic/claude-sonnet-5") == "claude-sonnet-5"
    assert etl.base_model("gpt-4o") == "gpt-4o"


def test_run(tmp_path, monkeypatch):
    feed = {
        "p/m1": {"mode": "chat", "input_cost_per_token": 1e-6,
                 "output_cost_per_token": 2e-6, "max_input_tokens": 128000,
                 "litellm_provider": "p"},
        "p/m2": {"mode": "chat", "input_cost_per_token": 0,
                 "output_cost_per_token": 0, "max_input_tokens": 1000000,
                 "litellm_provider": "p"},
        "p/m3": {"mode": "embedding", "input_cost_per_token": 1e-6,
                 "output_cost_per_token": 0},
        "p/m4": {"mode": "chat"},  # no prices -> dropped
    }
    monkeypatch.setattr(etl, "fetch_prices", lambda *a, **k: feed)
    monkeypatch.setattr(etl, "load_aa", lambda: {"m2": 44})
    monkeypatch.setattr(etl, "OUT_DB", str(tmp_path / "out.db"))

    assert etl.run() == (2, 2, 1)  # embedding and price-less rows excluded, m2 scored

    import sqlite3
    rows = sqlite3.connect(etl.OUT_DB).execute(
        "select model_id, input_per_m, tags from prices order by model_id").fetchall()
    assert rows == [("m1", 1.0, ""), ("m2", 0.0, "free,cheap,long_context,scored")]


def test_presets():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    presets = json.load(open(os.path.join(root, "data", "presets.json")))
    assert len(presets) == 10
    assert len({p["id"] for p in presets}) == 10
    for p in presets:
        assert p["monthly_input_m"] > 0 and p["current_model"]
