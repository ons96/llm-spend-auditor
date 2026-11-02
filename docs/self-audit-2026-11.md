# Self-audit: my own LLM gateway, July-October 2026

The first real audit on this project's own infrastructure. It is a useful
result precisely because it is small and incomplete: the tool refused to score
almost all of my traffic, and that refusal is the product working as intended.

Short version:

- 28,227 calls, 310 model ids, 76 providers, **$0.00 recorded cost** (free tiers).
- Only 1,370 calls (4.9%) carry token counts: 5,667,007 input, 395,944 output.
- 659 measured tokens (0.011%) went to a model the auditor can score.
- The real workload's top model has no AA score, so the auditor returns spend
  only and recommends nothing.
- If the same October volume had been bought at Claude Sonnet 5.5 list price it
  would cost **$0.92 per month**; Haiku 5.5 would be $0.05 at **-18 AA points**.

## Method

Source: the `api_calls` table in `LLM-API-Key-Proxy`'s SQLite telemetry, read
read-only over SSH. Columns used: `timestamp`, `model`, `provider`, `success`,
`input_tokens`, `output_tokens`, `cost_estimate_usd`. The table has no prompt
or response columns, so no message content was read.

Window: 2026-07-22 02:52 to 2026-10-31 02:35, the full history in the DB.
"October" means 2026-10-01 through 2026-10-31.

The same audit engine that powers the site (`audit.py`, ported to `audit.js`)
was run over the exported price table, with token volumes converted to millions.

## Coverage, before any conclusions

| Metric | Value |
|---|---|
| Calls | 28,227 |
| Calls that succeeded | 5,026 (17.8%) |
| Calls with token usage | 1,370 (4.9%) |
| Measured input tokens | 5,667,007 |
| Measured output tokens | 395,944 |
| Recorded cost | $0.00 |
| Distinct model ids | 310 |
| Distinct providers | 76 |

Two limits follow directly:

1. **The token numbers are a floor, not a bill.** Most providers in this gateway
   do not return usage, and most calls are probes and routing tests. A 4.9%
   sample cannot stand in for total usage.
2. **The bill is real but zero.** Every non-null cost estimate in the table is
   $0.00 because the gateway routes to free tiers. Free tiers are excluded from
   recommendations by design, so there is nothing for the auditor to save here.

## What the auditor says about the real workload

October 2026, the last full month:

| Metric | Value |
|---|---|
| Calls | 1,413 |
| Calls with usage | 363 |
| Measured input | 378,019 |
| Measured output | 15,913 |
| Top model by tokens | `gemini-2.5-flash` (475 calls, 239,504 in, 4,736 out) |

Running the top model with that volume:

```
current_cost      $0.15 / month (median of 5 provider prices)
current_score     null
quality_verified  false
alternatives      []
```

The tool will not recommend a replacement for `gemini-2.5-flash` because the
Artificial Analysis scrape has no score for it. That is decision 3 in HANDOFF:
no benchmark, no quality claim. A cheaper-looking swap would be a guess, and
this project exists to avoid those.

Across the whole history, exactly one AA-scored id saw token traffic:
`minimax-m3`, with 618 input and 41 output tokens. Everything else that moved
real volume is unscored. So the honest coverage statement is:

> 99.99% of the tokens I actually moved cannot be judged for quality by this
> tool. 17 scored models is enough to audit a paid bill, not enough to audit a
> free-tier model lab.

## Counterfactual: what the same volume would cost at list price

This is explicitly a counterfactual, not a bill: the gateway never paid these
prices. It answers "what would this shape of work cost on a paid model, and
what quality would I be buying".

October volume (0.378019M input, 0.015913M output) on Claude Sonnet 5.5
($2 / $10 per million, AA 54):

| Model | Monthly | Savings | AA delta | Verdict |
|---|---|---|---|---|
| `claude-sonnet-5-5` | $0.92 | - | 0 | current |
| `claude-haiku-5-5` | $0.05 | 95.0% | -18 pts | trade-off |
| `minimax-m3` | $0.13 | 86.1% | -35 pts | trade-off |
| `deepseek-v4-1-flash-1017` | $0.13 | 85.5% | -22 pts | trade-off |

Same volume on other paid models:

| Current model | AA | Monthly | Cheapest alternative |
|---|---|---|---|
| `claude-opus-5-5` | 58 | $1.83 | Haiku, $0.05, -22 pts |
| `gpt-6-astra` | 57 | $4.58 | Haiku, $0.05, -21 pts |
| `gemini-4-argon` | 50 | $0.92 | Haiku, $0.05, -14 pts |

The whole measured history (5.667M input, 0.396M output over 3.3 months) would
be **$15.29** on Sonnet 5.5 or **$30.59** on Opus 5.5 at list price, against
$0.00 actually spent.

At my volume, the dollar differences are cents. That is the point: for this
workload, price is not the constraint; knowing whether the output is any good
is. A team with 500M tokens a month is the customer for the savings case; I am
the customer for the "what can be verified" case.

## What this audit proves and does not

Proves:

- The engine runs end to end on real telemetry, not just presets.
- The no-score refusal fires on the user's own top model, and the UI shows
  spend without inventing a recommendation.
- Savings and score deltas stay attached to each other in a real report.

Does not prove:

- That any saving is available on my bill. There is no bill.
- That the measured token volume is complete. It is 4.9% of calls.
- That free-tier routing is cheap in practice. Rate limits and retries are not
  modeled, and 82% of calls in this table are marked failed; those calls often
  carry no usage either.

## Reproduce

```sql
-- coverage
select count(*) as calls,
       sum(case when input_tokens > 0 or output_tokens > 0 then 1 else 0 end) as with_usage,
       sum(input_tokens) as input_tokens,
       sum(output_tokens) as output_tokens,
       round(sum(coalesce(cost_estimate_usd, 0)), 2) as cost
from api_calls;

-- last full month
select count(*), sum(input_tokens), sum(output_tokens)
from api_calls
where timestamp >= '2026-10-01' and timestamp < '2026-11-01';

-- the only scored id with token traffic
select model, sum(input_tokens), sum(output_tokens)
from api_calls
where model = 'minimax-m3'
group by model;
```

In the UI:

- Real top model, spend only:
  `https://ons96.github.io/llm-spend-auditor/#model=gemini-2.5-flash&input=0.378019&output=0.015913&needs=`
- Sonnet counterfactual:
  `https://ons96.github.io/llm-spend-auditor/#model=claude-sonnet-5-5&input=0.378019&output=0.015913&needs=`

## Limitations

- One user, one gateway, four months. Not a market sample.
- Token counts come from provider responses; providers that omit usage are
  invisible. Treat every volume here as a lower bound.
- Provider names are aggregated out on purpose; they are private free-tier
  services and not relevant to the audit.
- Counterfactual prices are list prices from the committed LiteLLM snapshot,
  not quotes. Enterprise discounts, caching and batch pricing would change them.
- The AA index is one number per model. It does not capture per-task fit, which
  is why the page shows the delta instead of declaring a winner.
