"""Weekend 1 ETL: pricing rows from llm-leaderboard-aggregate -> data/prices.db.

Usage: python3 etl.py [SRC_DB] [OUT_DB]
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.expanduser(
    os.environ.get("LSA_SRC_DB", "~/CodingProjects/llm-leaderboard-aggregate/db/model_providers.db"))
DEFAULT_OUT = os.path.join(ROOT, "data", "prices.db")

CHEAP_INPUT_PER_M = 0.5    # USD per 1M input tokens
LONG_CONTEXT = 200_000     # tokens
CODING_SCORE = 50.0        # avg_agentic_coding_score threshold

SELECT = """select model_id, provider_name, provider_model_id,
    input_cost_per_token, output_cost_per_token, is_free_tier,
    context_window_tokens, avg_agentic_coding_score, avg_reasoning_chat_score, last_updated
    from model_providers where mode = 'chat'"""


def tags_for(row):
    """row = (input_cost_per_token, output_cost_per_token, is_free, ctx, coding_score)."""
    inp, _out, free, ctx, score = row
    tags = []
    if free:
        tags.append("free")
    if free or (inp or 0) * 1e6 <= CHEAP_INPUT_PER_M:
        tags.append("cheap")
    if ctx and ctx >= LONG_CONTEXT:
        tags.append("long_context")
    if score is not None:
        tags.append("benchmarked")
        if score >= CODING_SCORE:
            tags.append("coding")
    return ",".join(tags)


def run(src=DEFAULT_SRC, out=DEFAULT_OUT):
    """Rebuild out DB. Returns (price_rows, distinct_models)."""
    rows = sqlite3.connect(src).execute(SELECT).fetchall()
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.execute("""create table prices (model_id text, provider text,
        provider_model_id text, input_per_m real, output_per_m real,
        is_free int, context_window int, coding_score real, chat_score real, tags text,
        last_updated text)""")
    keep = []
    for mid, prov, pmid, inp, outp, free, ctx, score, chat, upd in rows:
        # ponytail: zero cost without free flag = unknown pricing, dropped
        if inp is None or outp is None or (not free and inp == 0 and outp == 0):
            continue
        keep.append((mid, prov, pmid, round(inp * 1e6, 6), round(outp * 1e6, 6),
                     1 if free else 0, ctx, score, chat,
                     tags_for((inp, outp, free, ctx, score)), upd))
    db.executemany("insert into prices values (?,?,?,?,?,?,?,?,?,?,?)", keep)
    db.execute("create index ix_model on prices(model_id)")
    db.commit()
    db.close()
    os.replace(tmp, out)
    return len(keep), len({k[0] for k in keep})


if __name__ == "__main__":
    n, m = run(*sys.argv[1:3])
    print(f"prices.db: {n} rows, {m} models")
