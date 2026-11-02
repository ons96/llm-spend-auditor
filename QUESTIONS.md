# Open questions

Choices I made autonomously are noted with their default. These need the
owner's identity, accounts, or preference.

## 1. External audits (Weekend 4, items 2-3)

Recruiting three anonymized audits from r/LocalLLaMA and dev Discords requires
posting from your accounts and answering replies as you. That is not something
an agent should do on your behalf, so it is not done.

Default taken: the free-audit CTA and the issue template are live, so requests
can arrive without any posting. If you want proactive recruitment, post the
self-audit link yourself and point people at the audit request template.

## 2. Provider names in the self-audit

`docs/self-audit-2026-11.md` aggregates by model and omits the 76 provider ids,
which include private free-tier services. Publishing them could expose your
routing setup.

Default taken: omitted. If you are fine publishing them, the writeup can name
the top three providers, but nothing in the argument needs it.

## 3. Weekly refresh commits straight to master

`.github/workflows/refresh-data.yml` runs weekly, tests, and pushes data
changes to `master`, which redeploys Pages. That is the no-review option.

Default taken: direct commit. Switch to a pull request if you would rather
approve price/quality changes before they go live.

## 4. Contact channel for the CTA

The CTA uses GitHub issues because they are free, public and need no server or
email address from me.

Default taken: issues. If you have an audit alias, add it to the CTA and the
issue template so non-GitHub users can reach you.

## 5. Publishing self-audit volume numbers

The writeup publishes your own call counts, token volumes and model ids. They
describe your infrastructure usage, not customer data, and no prompts were read.

Default taken: published at aggregate level. Say if you want the exact counts
rounded or the date window shortened.
