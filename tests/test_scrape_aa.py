"""Tests for the AA scraper: slugging, parsing, merge rules, and the write guard.

These use an inline HTML fixture, so they run offline. The <50-row guard is the
only thing standing between an AA redesign and a silently empty dataset, so it
is tested on both sides.
"""

from datetime import datetime, timezone

import pytest

import scrape_aa

HEAD = (
    "<html><body><table>"
    "<tr><th>Model</th><th>Context</th><th>Creator</th><th>AA Index</th></tr>"
)


def row(name, context="1M", creator="Acme", index="50"):
    return (
        f"<tr><td>{name}</td><td>{context}</td>"
        f"<td>{creator}</td><td>{index}</td></tr>"
    )


def page(rows):
    return (HEAD + "".join(rows) + "</table></body></html>").encode()


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Claude Sonnet 4.5", "claude-sonnet-4-5"),
        ("GPT-OSS-20B", "gpt-oss-20b"),
        ("Gemini 4 Carbon (high)", "gemini-4-carbon"),
        ("  Foo__Bar  ", "foo-bar"),
        ("A/B", "a-b"),
    ],
)
def test_slug(name, expected):
    assert scrape_aa.slug(name) == expected


def test_parse_extracts_rows_and_skips_non_numeric():
    html = page(
        [
            row("Alpha (high)", context="1M", creator="Acme", index="70"),
            row("Beta", context="500k", creator="Other", index="42"),
            row("Gamma", index="n/a"),
            "<tr><td>Too few cells</td><td>1M</td></tr>",
        ]
    )
    rows = scrape_aa.parse(html)
    assert len(rows) == 2
    alpha, beta = rows
    assert alpha == {
        "name": "Alpha (high)",
        "slug": "alpha",
        "variant": True,
        "context": "1M",
        "creator": "Acme",
        "aa_index": 70,
    }
    assert beta["slug"] == "beta"
    assert beta["variant"] is False
    assert beta["aa_index"] == 42


def test_parse_without_table_fails_loudly():
    with pytest.raises(ValueError, match="no leaderboard table"):
        scrape_aa.parse(b"<html><body><p>redesigned</p></body></html>")


def test_build_prefers_plain_variant_whichever_comes_first():
    variant = {"name": "X (high)", "slug": "x", "variant": True, "aa_index": 70}
    plain = {"name": "X", "slug": "x", "variant": False, "aa_index": 60}
    assert scrape_aa.build([variant, plain])["x"] is plain
    assert scrape_aa.build([plain, variant])["x"] is plain


def test_build_keeps_distinct_slugs():
    a = {"name": "A", "slug": "a", "variant": False, "aa_index": 10}
    b = {"name": "B", "slug": "b", "variant": False, "aa_index": 20}
    assert set(scrape_aa.build([a, b])) == {"a", "b"}


def test_main_writes_snapshot(monkeypatch, tmp_path, capsys):
    out = tmp_path / "aa_scores.json"
    monkeypatch.setattr(scrape_aa, "OUT", out)
    monkeypatch.setattr(
        scrape_aa, "fetch", lambda *a, **k: page(
            [row(f"Model {i}", index=str(i + 1)) for i in range(60)]
        )
    )

    assert scrape_aa.main() == 0

    payload = scrape_aa.json.loads(out.read_text())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert payload["source"] == scrape_aa.AA_URL
    assert payload["scraped_at"] == today
    assert payload["scraped_rows"] == 60
    assert len(payload["models"]) == 60
    assert "wrote 60 models from 60 rows" in capsys.readouterr().out


def test_main_refuses_thin_page_and_writes_nothing(monkeypatch, tmp_path, capsys):
    out = tmp_path / "aa_scores.json"
    monkeypatch.setattr(scrape_aa, "OUT", out)
    monkeypatch.setattr(
        scrape_aa, "fetch", lambda *a, **k: page([row("Only One")])
    )

    assert scrape_aa.main() == 1
    assert not out.exists()
    assert "refusing to write" in capsys.readouterr().err
