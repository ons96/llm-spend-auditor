# Decisions and open questions

Last updated 2026-11-02.

## Resolved by the owner, 2026-11-02

1. **Provider names stay private.** The self-audit aggregates them out and no
   document names a provider. Keep it that way.
2. **Weekly refresh commits to `master`** and redeploys Pages automatically. A
   pull request is the fallback if review ever becomes necessary.
3. **Contact channel is GitHub issues.** There is no email alias, so the CTA
   stays on the issue template.
4. **The self-audit publishes exact call counts, token volumes and the date
   window** at aggregate level, with no provider names. Keep it.
5. **The broader writeup lives in `docs/writeup.md`** in this repo, not on an
   external blog.
6. **The repository is MIT licensed.** Approved 2026-11-02; see `LICENSE`.
   Copyright stays with `ons96`.

## Open: three external audits

What it means: the plan asks for audits of three other people's workloads, with
identifying details removed, to show the method works beyond my own gateway.
Getting them requires asking in communities (r/LocalLLaMA, dev Discords) from an
account that belongs to the owner. An agent cannot do that without pretending to
be the owner, so it is not done.

What is ready: the free-audit CTA and issue template on the page, the reply
template in `docs/outreach.md`, and the audit itself. Once a request arrives, the
audit is one copied link away.

What is needed: post `docs/outreach.md` from your account, or forward requests
you receive. If an agent should post, it needs an account and an explicit
instruction naming the channel; otherwise intake stays inbound-only.
