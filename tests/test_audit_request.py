"""Tests for audit_request.py: URL roundtrip, report honesty, CLI paths."""
import pytest

import audit
import audit_request as ar


def row(model_id, provider, inp, outp, aa, tags="", free=0):
    return dict(model_id=model_id, provider=provider, input_per_m=inp,
                output_per_m=outp, is_free=free, aa_score=aa, tags=tags)


SMALL = [
    row("cur", "a", 3.0, 15.0, 54),
    row("better", "b", 2.0, 10.0, 58, "cheap"),
    row("weak", "c", 0.1, 0.5, 36, "cheap"),
    row("free", "d", 0.0, 0.0, 90, "free", free=1),
    row("unscored", "e", 0.01, 0.01, None),
]
W = dict(current_model="cur", monthly_input_m=10, monthly_output_m=2, needs=[])


def test_url_roundtrip():
    w = dict(current_model="claude-sonnet-5-5", monthly_input_m=60,
             monthly_output_m=6, needs=["long_context"])
    url = ar.build_url(w)
    assert url.startswith(ar.BASE_URL + "#model=claude-sonnet-5-5&input=60&output=6")
    assert ar.workload_from_url(url) == w


def test_url_requires_model():
    with pytest.raises(ValueError):
        ar.workload_from_url("https://example.com/#input=1")


def test_render_shows_savings_with_delta():
    text = ar.render(W, audit.audit(W, SMALL, 6), "2026-11-02")
    assert "## Audit: `cur`" in text
    assert "$60.00" in text
    assert "96.7%" in text
    assert "-18 pts" in text
    assert "trade-off" in text
    assert "Same or better quality: `better` at $40.00 (+4 pts, 33.3% cheaper)." in text
    assert "Report: https://ons96.github.io/llm-spend-auditor/#" in text
    assert "What this does not prove" in text


def test_render_refuses_without_score():
    w = dict(W, current_model="unscored")
    text = ar.render(w, audit.audit(w, SMALL, 6), "2026-11-02")
    assert "No AA score" in text
    assert "no recommendation" in text
    assert "| Model |" not in text
    assert "$0.12" in text


def test_render_needs_filter():
    w = dict(W, needs=["long_context"])
    text = ar.render(w, audit.audit(w, SMALL, 6))
    assert "No cheaper model" in text


def test_cli_writes_report(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "load_snapshot", lambda path: (SMALL, "2026-11-02"))
    out = tmp_path / "report.md"
    assert ar.main(["--model", "cur", "--input", "10", "--output", "2",
                    "--out", str(out)]) == 0
    text = out.read_text()
    assert "## Audit: `cur`" in text
    assert "$60.00" in text


def test_cli_reads_a_share_url(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ar, "load_snapshot", lambda path: (SMALL, "2026-11-02"))
    assert ar.main(["--url", ar.build_url(W)]) == 0
    assert "## Audit: `cur`" in capsys.readouterr().out


def test_cli_rejects_unknown_model(monkeypatch, capsys):
    monkeypatch.setattr(ar, "load_snapshot", lambda path: (SMALL, "2026-11-02"))
    assert ar.main(["--model", "nope", "--input", "1"]) == 1
    assert "no paid price rows" in capsys.readouterr().err


def test_cli_rejects_zero_tokens(monkeypatch):
    monkeypatch.setattr(ar, "load_snapshot", lambda path: (SMALL, "2026-11-02"))
    assert ar.main(["--model", "cur", "--input", "0", "--output", "0"]) == 2
