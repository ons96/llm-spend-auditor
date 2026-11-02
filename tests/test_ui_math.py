"""Parity tests for the static UI math.

index.html has no backend, so audit.js is the code users actually run. These
tests execute it under node and compare every preset against audit.audit() on
the same rows, which keeps the browser and the Python engine from drifting.
Skipped when node is absent; the rest of the suite still runs.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

import audit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_JS = os.path.join(ROOT, "audit.js")
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="needs node to run audit.js")

RUNNER = """
const fs = require("fs");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const SpendAudit = require(payload.audit_js);
process.stdout.write(JSON.stringify(payload.workloads.map(function (w) {
  return SpendAudit.audit(w, payload.prices, 3);
})));
"""


def ui_audit(workloads, prices):
    payload = {"audit_js": AUDIT_JS, "prices": prices, "workloads": workloads}
    proc = subprocess.run([NODE, "-e", RUNNER], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def price_rows():
    doc = json.load(open(os.path.join(ROOT, "data", "prices.json")))
    return [dict(zip(doc["cols"], row)) for row in doc["rows"]]


def presets():
    return json.load(open(os.path.join(ROOT, "data", "presets.json")))


def assert_same(js, py):
    """audit.js and audit.py must agree on everything the UI displays."""
    assert js["quality_verified"] == py["quality_verified"]
    assert js["current_score"] == py["current_score"]
    assert js["current_provider"] == py["current_provider"]
    assert js["providers"] == py["providers"]
    assert js["current_cost"] == pytest.approx(py["current_cost"], abs=0.011)
    assert [a["model_id"] for a in js["alternatives"]] == \
           [a["model_id"] for a in py["alternatives"]]
    for ja, pa in zip(js["alternatives"], py["alternatives"]):
        assert ja["provider"] == pa["provider"]
        assert ja["score"] == pa["score"]
        assert ja["score_delta"] == pa["score_delta"]
        assert ja["monthly_cost"] == pytest.approx(pa["monthly_cost"], abs=0.011)
        assert ja["savings_pct"] == pytest.approx(pa["savings_pct"], abs=0.06)
    if py["same_or_better"] is None:
        assert js["same_or_better"] is None
    else:
        assert js["same_or_better"]["model_id"] == py["same_or_better"]["model_id"]
        assert js["same_or_better"]["monthly_cost"] == \
            pytest.approx(py["same_or_better"]["monthly_cost"], abs=0.011)
        assert js["same_or_better"]["score_delta"] == py["same_or_better"]["score_delta"]


def test_all_presets_match_python_engine():
    rows, workloads = price_rows(), presets()
    results = ui_audit(workloads, rows)
    assert len(results) == 10
    for w, js in zip(workloads, results):
        py = audit.audit(w, rows)
        assert_same(js, py)
        assert js["quality_verified"] is True, w["id"]
        # The honesty rule the UI renders: no saving without its quality delta.
        for a in js["alternatives"]:
            assert a["score_delta"] is not None
            assert a["monthly_cost"] < js["current_cost"]


def row(model_id, provider, inp, outp, aa, tags="", free=0):
    return dict(model_id=model_id, provider=provider, input_per_m=inp,
                output_per_m=outp, is_free=free, aa_score=aa, tags=tags)


SMALL = [
    row("cur", "a", 3.0, 15.0, 54),
    row("better", "b", 2.0, 10.0, 58, "cheap"),
    row("weak", "c", 0.1, 0.5, 36, "cheap"),
    row("free", "d", 0.0, 0.0, 90, "free", free=1),
    row("unscored", "e", 0.01, 0.01, None),
    row("twin-a", "f", 0.2, 0.6, 28),
    row("twin-b", "g", 0.2, 0.6, 36),
]


def test_edge_cases_match_python_engine():
    base = dict(monthly_input_m=10, monthly_output_m=2, needs=[],
                current_model="cur")
    cases = [
        base,
        dict(base, monthly_output_m=0),
        dict(base, needs=["long_context"]),
        dict(base, current_model="unscored"),
        dict(base, current_model="nope"),
    ]
    results = ui_audit(cases, SMALL)

    for w, js in zip(cases, results):
        if w["current_model"] == "nope":
            assert js["error"] == "no_paid_rows"
            with pytest.raises(ValueError):
                audit.audit(w, SMALL)
            continue
        assert_same(js, audit.audit(w, SMALL))

    # Cheapest first; identical price is one offer, so the higher scorer wins
    # and free tiers are never recommended.
    assert [a["model_id"] for a in results[0]["alternatives"]] == \
           ["weak", "twin-b", "better"]
    assert results[0]["alternatives"][0]["score_delta"] == -18

    # No AA score means no quality claim and no recommendation, only spend.
    assert results[3]["quality_verified"] is False
    assert results[3]["current_score"] is None
    assert results[3]["alternatives"] == []


def test_static_ui_files_are_ascii_and_wired():
    for name in ("index.html", "audit.js"):
        text = open(os.path.join(ROOT, name), "rb").read().decode("ascii")
        assert text.strip(), name
    html = open(os.path.join(ROOT, "index.html")).read()
    assert "data/prices.json" in html
    assert "data/presets.json" in html
    assert 'src="audit.js"' in html


def test_shipped_export_matches_current_etl():
    """The committed prices.json must come from the current base_model() logic.

    A stale export built before the key-tail fix shipped ids like
    'anthropic/claude-sonnet-5-5', which silently split one model into several
    provider rows and hid three scored models from the UI.
    """
    doc = json.load(open(os.path.join(ROOT, "data", "prices.json")))
    assert doc["cols"] == audit.EXPORT_COLS
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", doc["generated_at"]), doc.get("generated_at")
    assert doc["rows"]
    ids = {row[0] for row in doc["rows"]}
    assert not [i for i in ids if "/" in i]
    aa = json.load(open(os.path.join(ROOT, "data", "aa_scores.json")))["models"]
    scored = {row[0] for row in doc["rows"] if not row[4] and row[6] is not None}
    assert scored <= set(aa), "exported scores must come from the committed AA scrape"
    assert len(scored) >= 10, "scored models vanished from the export"
