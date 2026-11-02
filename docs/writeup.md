# How to recommend a cheaper LLM without lying about quality

Every "switch to a cheaper model and save 90%" post has the same hole in it.
The price is real; the quality claim usually is not. Models get compared
across benchmark subsets, dated snapshots, or an aggregator's alias merge, and
the reader is left to assume that because the output is fluent, nothing was
lost.

This project is my attempt at the honest version: one normalized quality
index, one public price feed, and a hard rule that a saving is never shown
without the quality it costs. It is live at
https://ons96.github.io/llm-spend-auditor/ and the code is at
https://github.com/ons96/llm-spend-auditor.

## Three rules do most of the work

**One index, applied to everyone.** Quality comes from the Artificial Analysis
Intelligence Index. An earlier version of this project used an aggregate of
chat and coding scores from another database; `gpt-4o` carried 9.7 chat / 13.8
coding in one row while dated siblings carried 63.1 / 49.1 / 47.6. That is an
alias merge across mismatched sources, not a measurement. AA applies one
methodology to every model it lists, which is the only thing that makes two
numbers comparable.

**No quality floor.** The obvious product choice is to hide models below some
score. It hides both good and bad advice. Swapping `minimax-m3` for
`claude-haiku-5-5` is cheaper *and* 17 index points better; swapping
`claude-sonnet-5-5` for the same model saves 95% and gives up 18 points. Both
belong in front of the reader, labelled.

**No score, no claim.** If the current model has no AA score, the audit returns
spend and nothing else. It does not estimate quality, and it does not
recommend. That is why the tool is honest about its own coverage: 17 models
have both an AA score and a published paid price, out of 1,879 model ids in the
price snapshot (1,810 with a paid price). "17 verified" is the real number; a
page that said "1,879 available" would be selling something it cannot measure.

Three smaller decisions follow from the same logic. The current price is the
median across providers, not the cheapest listing, because the cheapest
listing is often a stale reseller discount that understates the bill. Free
tiers are excluded from recommendations because rate limits make them unusable
at business volume. And two models at the same price are one offer, so the
higher scorer survives and the near-duplicate disappears.

## What the page does

Pick one of ten preset workloads or type your own model and monthly token
counts. The page prices the current model at the median provider, finds cheaper
models that meet your requirements and have an AA score, and lists them
cheapest first. Every row carries the monthly cost, the savings, the AA score,
and the score delta. Negative deltas are amber and labelled a trade-off;
non-negative ones are green. Inputs live in the URL hash, so a link reproduces
the audit with no account and no server.

All of it runs in the browser against a committed JSON snapshot. The engine
also exists in Python (`audit.py`), and a node parity test runs both
implementations on the same rows for all ten presets, so the page and the CLI
cannot drift apart silently.

## What auditing my own gateway taught me

Weekend 4 was supposed to be three external audits. The first one, on my own
LLM gateway, turned out to be more interesting than expected: the telemetry has
28,227 calls over three and a half months, $0.00 recorded spend because
everything routes to free tiers, token counts on only 4.9% of calls, and 0.011%
of measured tokens on a model this tool can score.

So the auditor refused to recommend anything for my real top model, and the
honest writeup is mostly about coverage. Read it here:
[`self-audit-2026-11.md`](self-audit-2026-11.md). The short version: at my
volume the counterfactual is $0.92 a month on Claude Sonnet 5.5, which is
noise; the binding constraint is that almost none of my traffic can be
verified. A team with a real bill is the customer for the savings case. I was
the customer for the "what can actually be checked" case.

## Limits

- The AA index is one number per model; it does not capture per-task fit. The
  delta is information, not a verdict.
- Prices are a public feed snapshot, not quotes. Enterprise discounts, caching
  and batch pricing change the arithmetic.
- The refresh runs weekly and commits the new snapshot; the page shows both
  dates rather than calling the data live.
- Coverage is the product's main constraint, not a bug to paper over. Public
  price feeds lag model releases by weeks, and AA retires old models without
  re-scoring them.

## Try it, or ask for an audit

The tool is free and needs no account: https://ons96.github.io/llm-spend-auditor/

If you want your own bill looked at, open an
[audit request](https://github.com/ons96/llm-spend-auditor/issues/new?template=audit-request.md)
with monthly token counts and your current model. Token counts are enough; do
not send keys, prompts or customer data.
