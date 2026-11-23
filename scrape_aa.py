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
from datetime import datetime, timezone
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
    """Parse the leaderboard table, tolerating either column order.

    Two layouts exist in the wild: the historical one (Model, Context, Creator,
    AA Index) and the current site (Model, Artificial Analysis Intelligence,
    Cost, Speed, Latency, Context). The current site also renamed the index
    column, so a purely positional parser silently yields zero rows after a
    redesign. Columns are therefore located by header name when the header
    names an intelligence column, and by position otherwise.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        raise ValueError("no leaderboard table found")

    cols: dict[str, int] | None = None
    legacy: dict[str, int] | None = None
    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if cols is None and legacy is None:
            lowered = [c.lower() for c in cells]
            if "model" in lowered:
                found = {"model": lowered.index("model")}
                for i, h in enumerate(lowered):
                    if ("intelligence" in h or "aa index" in h) and "index" not in found:
                        found["index"] = i
                    if "context" in h and "context" not in found:
                        found["context"] = i
                    if "creator" in h and "creator" not in found:
                        found["creator"] = i
                if "index" in found:
                    cols = found
                else:
                    legacy = {"model": 0, "context": 1, "creator": 2, "index": 3}
            continue

        spec = cols or legacy
        if spec is None:
            continue
        def cell(key: str) -> str:
            i = spec.get(key)
            return cells[i] if i is not None and i < len(cells) else ""

        name = cell("model")
        idx_raw = cell("index").replace(",", "")
        if not name or not idx_raw.isdigit():
            continue
        rows.append(
            {
                "name": name,
                "slug": slug(name),
                "variant": bool(re.search(r"\(|,", name)),
                "context": cell("context"),
                "creator": cell("creator"),
                "aa_index": int(idx_raw),
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
        # UTC date: the static UI shows this as the dataset freshness line.
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
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
