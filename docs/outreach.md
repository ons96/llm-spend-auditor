# Outreach drafts (not posted)

Operating plan (where to ask, intake, running the audit, publishing, cadence):
[`AUDIT_PLAYBOOK.md`](AUDIT_PLAYBOOK.md).

These are drafts for the owner to post. Do not automate posting: it needs a
real account, and communities treat drive-by tool links as spam. Read each
community's self-promotion rules first; some require flair or mod approval.

Goal: three anonymized audits. A useful request is three numbers (monthly
input tokens in millions, monthly output tokens in millions, current model) and
one sentence about the workload. No keys, prompts or customer data.

## r/LocalLLaMA post

Title:

    I built a free LLM cost auditor that refuses to recommend a cheaper model without a benchmark delta

Body:

    Most "switch to a cheaper model" advice compares prices and hand-waves the
    quality part. I wanted a version that shows the quality cost next to the
    saving, so I built one as a static page.

    It uses one normalized quality signal (Artificial Analysis Intelligence
    Index) and the LiteLLM public price feed. The rules I settled on:

    - no quality floor: every cheaper option is shown with its AA score delta
    - no score, no claim: models without an AA score are never recommended
    - median provider price, not the cheapest reseller listing
    - free tiers excluded: rate limits make them unusable at business volume

    Live: https://ons96.github.io/llm-spend-auditor/
    Code: https://github.com/ons96/llm-spend-auditor

    Month one of real data: 17 of the 1,879 priced model ids have both an AA
    score and a published price, so the tool says "17 verified" rather than
    "1,879 available". That gap is the interesting part, not a bug.

    I also audited my own gateway. The short version: it routes to free tiers,
    so the bill is $0, and 99.99% of the tokens I actually moved are on models
    the tool cannot score. It refused to recommend anything for my real top
    model instead of guessing. Full writeup in the repo.

    If anyone wants an anonymized audit, I need monthly input/output tokens in
    millions, your current model, and whether you need long context. Don't send
    keys, prompts or customer data. I'll reply with a link and a short note on
    what it does and does not prove. Disclosure: this is my project, free, no
    signup.

## Discord message (dev / LLM servers)

    Built a small free tool that audits an LLM bill and puts the quality delta
    next to every saving: https://ons96.github.io/llm-spend-auditor/

    It uses the Artificial Analysis index for quality and LiteLLM prices, and
    it refuses to recommend a model with no AA score. Looking for 2-3
    anonymized workloads to audit (monthly input/output tokens in millions +
    current model). No keys or prompts needed. Happy to remove the link if
    self-promo isn't welcome here.

## Reply template for an audit request

    Thanks - I ran it with {input}M input and {output}M output per month on
    {model}. Link: {share url}

    Headline: {current cost} per month at the median provider price. The
    cheapest option that meets your needs is {cheapest} at {cost}, which is
    {savings}% cheaper and {delta} AA points {lower/higher}. Same-or-better
    option: {safe or "none"}.

    What this does not tell you: the AA index is one number per model and does
    not measure your specific task, and {n} of the price rows in the snapshot
    have no score at all, so they are not listed. If you can share a few sample
    outputs I can say more about fit, but I will not claim quality equivalence
    without a benchmark.

## Where to ask

- r/LocalLLaMA: good for open-model users, but check the self-promotion rule
  and avoid cross-posting the same text to several subs on one day.
- Dev Discords: ask in a general or tools channel, not in support threads.
- Existing contacts: the highest hit rate. The CTA on the page already handles
  inbound requests without any posting.
