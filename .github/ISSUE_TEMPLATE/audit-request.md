---
name: Free audit request
about: Ask for a free LLM spend audit using public price and quality data
title: "Audit request: "
---

## Workload

- Monthly input tokens (millions):
- Monthly output tokens (millions):
- Current model id (find it at https://ons96.github.io/llm-spend-auditor/):
- Requirements: long context (200k or more), cheap input (0.50 USD or less
  per 1M), neither, or something else:

## Context

- What the workload does (one sentence):
- Is usage steady across the month (yes / no / unknown):
- Models or providers that must not be recommended (latency, compliance,
  region), if any:

## Privacy

Do not paste API keys, prompts, customer data, invoices or account ids.
Token counts and a model name are enough. The audit uses the public LiteLLM
price feed and the Artificial Analysis Intelligence Index; nothing is uploaded
anywhere and the report is a URL you can share or discard.

## What you get back

A comment with a link to the audit (inputs encoded in the URL hash), the
cheapest options, and the AA score delta for each one. If the current model has
no AA score, the answer will say so instead of guessing.
