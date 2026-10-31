import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import etl  # noqa: E402


def test_tags():
    assert etl.tags_for((1e-7, 4e-7, 0, 256000, 60.0)) == "cheap,long_context,benchmarked,coding"
    assert etl.tags_for((5e-6, 1.5e-5, 0, 8000, None)) == ""
    assert etl.tags_for((0, 0, 1, None, 20.0)) == "free,cheap,benchmarked"


def test_run(tmp_path):
    src = tmp_path / "src.db"
    db = sqlite3.connect(src)
    db.execute("""create table model_providers (model_id, provider_name,
        provider_model_id, input_cost_per_token, output_cost_per_token,
        is_free_tier, context_window_tokens, mode, avg_agentic_coding_score,
        avg_reasoning_chat_score, last_updated)""")
    db.executemany("insert into model_providers values (?,?,?,?,?,?,?,?,?,?,?)", [
        ("m1", "p", "p/m1", 1e-6, 2e-6, 0, 128000, "chat", None, None, "t"),
        ("m2", "p", "p/m2", 0, 0, 1, 1000000, "chat", 70.0, 65.0, "t"),
        ("m3", "p", "p/m3", 1e-6, 2e-6, 0, 128000, "embedding", None, None, "t"),
        ("m4", "p", "p/m4", 0, 0, 0, 128000, "chat", None, None, "t"),
    ])
    db.commit()
    out = tmp_path / "out.db"
    assert etl.run(str(src), str(out)) == (2, 2)
    r = sqlite3.connect(out).execute(
        "select input_per_m, tags from prices where model_id='m1'").fetchone()
    assert r == (1.0, "")


def test_presets():
    presets = json.load(open(os.path.join(ROOT, "data", "presets.json")))
    assert len(presets) == 10
    assert len({p["id"] for p in presets}) == 10
    for p in presets:
        assert p["monthly_input_m"] > 0 and p["current_model"]
