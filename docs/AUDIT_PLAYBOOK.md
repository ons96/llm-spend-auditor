# Audit acquisition playbook

Goal: three anonymized audits of other people's workloads, to test the savings
case on something bigger than my own free-tier gateway. The page CTA is the
inbound path; this is the outbound one.

An audit needs four things: monthly input tokens (millions), monthly output
tokens (millions), the current model id, and any requirement (long context,
cheap input). Nothing else. No keys, prompts, invoices or customer data.

## 1. Ask

Order by hit rate, not reach:

1. **Warm contacts.** One sentence in a DM to people who already run LLM
   workloads. Highest response rate by far.
2. **Discords where you are active.** General or tools channel, not support
   threads. Ask once.
3. **r/LocalLLaMA.** Read the self-promotion rule first; some weeks require
   flair or mod approval. Post once, do not cross-post the same text to several
   subs on one day.

Copy is in `docs/outreach.md`. Disclose that it is your project, that it is
free, and that the report is a public URL unless they ask otherwise.

## 2. Intake

If they open a GitHub issue, the `audit` label marks it. If they send numbers
in a DM, copy them into an issue yourself (with permission) so the audit has a
permalink.

Record only: label, model, input millions, output millions, needs, permission
to publish an anonymized version. Do not ask for company name, spend, keys or
sample prompts.

## 3. Run

One command, no network:

    # from a share link they sent
    python3 audit_request.py --url "https://ons96.github.io/llm-spend-auditor/#model=...&input=...&output=..."

    # from numbers
    python3 audit_request.py --model claude-sonnet-5-5 --input 60 --output 6 \
        --out docs/audits/<label>.md

The script reads the committed `data/prices.json`, the same snapshot the page
serves, so the report matches the link. It prints markdown ready to paste.

If the current model has no AA score, the report says so and gives spend only.
That is the correct answer, not a failure. Say what data would change it (a
scored model, or a paid bill with a scored model), and stop there.

## 4. Reply

Paste the generated markdown. Add one sentence about task fit only if you have
real evidence (sample outputs, a benchmark on their data). Otherwise do not
speculate.

The reply must keep: the score delta next to the saving, the free-tier
exclusion, the median-price note, and the "what this does not prove" section.
If a request cannot be answered honestly, say that.

## 5. Publish and log

Anonymize before anything goes public:

- replace the company with a label (`case-a`, `retail-bot`, etc.)
- keep model ids and token volumes; drop provider account names
- get explicit permission for the writeup, not just the audit
- never quote prompts or outputs

Save the report under `docs/audits/<label>.md` and add a row:

| Case | Date | Model | Monthly | Cheapest | Delta | Published |
|---|---|---|---|---|---|---|
| | | | | | | |

Three completed rows is the Weekend 4 target. One is enough to write the
comparative piece; two more make it evidence rather than an anecdote.

## Cadence

Post once, wait 48 hours, follow up once in the same thread, then stop. No
mass DMs, no reposting the same text, no paid promotion. If outbound produces
nothing, the CTA still catches inbound requests and the self-audit still
demonstrates the method.

## Do not

- ask for API keys, prompts, invoices or customer data
- publish an audit without permission
- call two models equivalent without an AA score
- show a saving without its delta
- pad the sample with friendly audits that were never run
