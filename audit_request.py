"""Turn an audit request into a shareable report.

An audit request is a model, two token volumes and an optional requirement.
This script runs the same engine the page runs, against the committed
data/prices.json snapshot, and prints a markdown report ready to paste into an
issue reply.

Usage:
  python3 audit_request.py --model claude-sonnet-5-5 --input 60 --output 6
  python3 audit_request.py --url "https://ons96.github.io/llm-spend-auditor/#model=glm-5-3&input=10&output=1"
  python3 audit_request.py --model gpt-6-astra --input 200 --output 40 --out docs/audits/acme.md

--url accepts the link the page produces, so a request that already carries a
share link needs no retyping. Nothing is uploaded, and the only identity in the
report is the filename you choose.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse

import audit

ROOT = os.path.dirname(os.path.abspath(__file__))
PRICES_JSON = os.path.join(ROOT, "data", "prices.json")
BASE_URL = "https://ons96.github.io/llm-spend-auditor/"


def load_snapshot(path=PRICES_JSON):
    """Return (rows, generated_at) from the committed UI export."""
    with open(path) as f:
        doc = json.load(f)
    rows = [dict(zip(doc["cols"], row)) for row in doc["rows"]]
    return rows, doc.get("generated_at")


def fmt_num(value):
    return f"{value:g}"


def _positive(text, default=0.0):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def workload_from_url(url):
    """Reverse the page's #model=...&input=...&output=...&needs=... format."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.fragment or parsed.query)
    model = (params.get("model") or [""])[0].strip()
    if not model:
        raise ValueError("URL has no model= parameter")
    needs = [n for n in (params.get("needs") or [""])[0].split(",") if n]
    return {
        "current_model": model,
        "monthly_input_m": _positive((params.get("input") or ["0"])[0]),
        "monthly_output_m": _positive((params.get("output") or ["0"])[0]),
        "needs": needs,
    }


def build_url(w):
    params = [
        ("model", w["current_model"]),
        ("input", fmt_num(w["monthly_input_m"])),
        ("output", fmt_num(w["monthly_output_m"])),
    ]
    if w.get("needs"):
        params.append(("needs", ",".join(w["needs"])))
    return BASE_URL + "#" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def _money(value):
    return f"${value:,.2f}"


def _caveats(generated_at):
    date = generated_at or "unknown date"
    return "\n".join([
        "### What this does not prove",
        "",
        "- The AA index is one number per model. It does not measure your specific task.",
        "- Prices are the LiteLLM snapshot of " + date + ", median across providers. "
        "Enterprise discounts, caching and batch pricing change the arithmetic.",
        "- Free tiers are excluded, and a model without an AA score is never listed.",
        "- Every saving is a trade-off: the delta column is the quality you give up.",
    ])


def render(w, result, generated_at=None, link=None, top=6):
    """Markdown report for one workload and one audit() result."""
    link = link or build_url(w)
    needs = w.get("needs") or []
    lines = ["## Audit: `" + w["current_model"] + "`", ""]
    lines.append(
        "Workload: " + fmt_num(w["monthly_input_m"]) + "M input + "
        + fmt_num(w["monthly_output_m"]) + "M output tokens per month."
    )
    if needs:
        lines.append("")
        lines.append("Requirements: " + ", ".join(needs) + ".")
    lines.append("")
    lines.append("Report: " + link)
    lines.append("")

    if not result["quality_verified"]:
        lines.extend([
            "**No AA score for `" + w["current_model"] + "`.** This tool will not "
            "estimate quality it cannot measure, so it makes no recommendation.",
            "",
            "Current spend estimate: **" + _money(result["current_cost"])
            + "/month** at the median of " + str(result["providers"])
            + " provider prices.",
            "",
            _caveats(generated_at),
        ])
        return "\n".join(lines).rstrip() + "\n"

    lines.append("- Current monthly cost: **" + _money(result["current_cost"])
                 + "** (median of " + str(result["providers"]) + " provider prices)")
    lines.append("- Current AA score: **" + str(result["current_score"]) + "**")
    lines.append("")

    alternatives = result["alternatives"][:top]
    if not alternatives:
        lines.append("No cheaper model in this snapshot meets the requirements and "
                     "has an AA score. The current model is the cheapest verified option.")
        lines.append("")
    else:
        lines.append("| Model | Provider | Monthly | Savings | AA | Delta | Verdict |")
        lines.append("|---|---|---|---|---|---|---|")
        for a in alternatives:
            verdict = "same or better" if a["score_delta"] >= 0 else "trade-off"
            lines.append(
                "| `" + a["model_id"] + "` | " + a["provider"]
                + " | " + _money(a["monthly_cost"])
                + " | " + f"{a['savings_pct']:.1f}%"
                + " | " + str(a["score"])
                + " | " + f"{a['score_delta']:+d} pts"
                + " | " + verdict + " |"
            )
        lines.append("")

    safe = result["same_or_better"]
    if safe:
        lines.append("Same or better quality: `" + safe["model_id"] + "` at "
                     + _money(safe["monthly_cost"]) + " ("
                     + f"{safe['score_delta']:+d}" + " pts, "
                     + f"{safe['savings_pct']:.1f}%" + " cheaper).")
    else:
        lines.append("Same or better quality: none. Every cheaper option gives up index points.")
    lines.append("")
    lines.append(_caveats(generated_at))
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run an audit request against the committed price snapshot.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="shareable audit URL from the page")
    source.add_argument("--model", help="current model id, for example claude-sonnet-5-5")
    parser.add_argument("--input", type=float, default=0.0,
                        help="monthly input tokens, in millions")
    parser.add_argument("--output", type=float, default=0.0,
                        help="monthly output tokens, in millions")
    parser.add_argument("--needs", default="",
                        help="comma list of needs: cheap,long_context")
    parser.add_argument("--out", help="write the report to this path")
    parser.add_argument("--top", type=int, default=6,
                        help="rows to show (default 6)")
    parser.add_argument("--prices", default=PRICES_JSON,
                        help="snapshot path (default data/prices.json)")
    args = parser.parse_args(argv)

    if args.model:
        w = {
            "current_model": args.model.strip(),
            "monthly_input_m": max(args.input, 0.0),
            "monthly_output_m": max(args.output, 0.0),
            "needs": [n.strip() for n in args.needs.split(",") if n.strip()],
        }
    else:
        try:
            w = workload_from_url(args.url)
        except ValueError as exc:
            print("error: " + str(exc), file=sys.stderr)
            return 2

    if w["monthly_input_m"] + w["monthly_output_m"] <= 0:
        print("error: token volumes must be greater than zero", file=sys.stderr)
        return 2
    if args.top < 1:
        print("error: --top must be at least 1", file=sys.stderr)
        return 2

    rows, generated_at = load_snapshot(args.prices)
    try:
        result = audit.audit(w, rows, args.top)
    except ValueError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 1

    report = render(w, result, generated_at, top=args.top)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            f.write(report)
        print("wrote " + args.out)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
