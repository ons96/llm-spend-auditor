"""Scrape Artificial Analysis intelligence index into data/aa_scores.json.

AA publishes one normalized index computed the same way for every model, which
makes cross-model quality comparison defensible. Benchmark averages from
llm-leaderboard-aggregate are NOT comparable when models were scored on
different benchmark subsets, so they are kept only as a low-confidence fallback.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

AA_URL = "https://artificialanalysis.ai/leaderboards/models"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
OUT = Path(__file__).parent / "data" / "aa_scores.json"


def slug(name: str) -> str:
    """'Claude Sonnet 4.5' -> 'claude-sonnet-4-5'; drops parenthetical variants."""
    base = re.sub(r"\(.*?\)", "", name)
    base = base.strip().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    return base.strip("-")


def fetch(url: str = AA_URL, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse(html: bytes) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        raise ValueError("no leaderboard table found")
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 4 or cells[0] == "Model":
            continue
        idx = cells[3].replace(",", "")
        if not idx.isdigit():
            continue
        rows.append(
            {
                "name": cells[0],
                "slug": slug(cells[0]),
                "variant": bool(re.search(r"\(", cells[0])),
                "context": cells[1],
                "creator": cells[2],
                "aa_index": int(idx),
            }
        )
    return rows


def build(rows: list[dict]) -> dict:
    """Index by slug. Plain variant wins over parenthetical variants."""
    out: dict[str, dict] = {}
    for r in rows:
        cur = out.get(r["slug"])
        if cur is None or (cur["variant"] and not r["variant"]):
            out[r["slug"]] = r
    return out


def main() -> int:
    html = fetch()
    rows = parse(html)
    if len(rows) < 50:
        print(f"refusing to write: only {len(rows)} rows parsed", file=sys.stderr)
        return 1
    scores = build(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": AA_URL,
        "scraped_rows": len(rows),
        "models": scores,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"wrote {len(scores)} models from {len(rows)} rows -> {OUT}")
    return 0


def demo() -> None:
    assert slug("Claude Sonnet 4.5") == "claude-sonnet-4-5"
    assert slug("GPT-OSS-20B") == "gpt-oss-20b"
    assert slug("Gemini 4 Carbon (high)") == "gemini-4-carbon"
    assert slug("DeepSeek V3.2") == "deepseek-v3-2"
    rows = [
        {"name": "X (high)", "slug": "x", "variant": True, "aa_index": 70},
        {"name": "X", "slug": "x", "variant": False, "aa_index": 60},
        {"name": "Y", "slug": "y", "variant": False, "aa_index": 40},
    ]
    built = build(rows)
    assert built["x"]["aa_index"] == 60, "plain variant must win"
    assert built["y"]["aa_index"] == 40
    print("self-check ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        demo()
    else:
        raise SystemExit(main())
