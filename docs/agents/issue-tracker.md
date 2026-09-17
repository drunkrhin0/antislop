# Issue tracker: Forgejo

Specs and tickets for this repository are tracked as issues on Forgejo:
https://git.drunkrhin0.au/drunkrhin0/antislop/issues.

## Conventions

- One Forgejo issue per ticket.
- Give the issue a short, descriptive title.
- Structure the body with `## Problem`, `## Done when`, and (once
  discussion starts) `## Comments` headings — this keeps issues
  consistent with the repo's prior local-ticket format.
- For multi-ticket efforts, open a parent/tracking issue and reference
  child issues from it (Forgejo renders `#N` references and task-list
  checkboxes); use "Depends on #N" / "Blocks #N" in issue bodies for
  ordering.
- Apply labels from `docs/agents/triage-labels.md`.
- Drafting a spec locally first (e.g. under `.scratch/<slug>/spec.md`)
  before publishing is fine when a ticket needs iteration, but the
  published record is the Forgejo issue, not the local file.

## Publishing

Create and update issues through Forgejo MCP via Bifrost. Do not use raw HTTP,
the web UI, or a Git/CLI substitute for remote Forgejo operations. Follow
`docs/agents/forgejo-write-policy.md` for branch-first file changes. Never
place a token, credential value, or raw secret in a tracked file or issue
comment. If the configured MCP route is unavailable, report the blocker rather
than silently switching transports.

## Wayfinding

- Issue list: https://git.drunkrhin0.au/drunkrhin0/antislop/issues
- Status is tracked via Forgejo's own open/closed state plus labels
  (`docs/agents/triage-labels.md`), not a local `Status:` line.
- Claim work by assigning yourself (or commenting) before editing
  source files. Resolve work by closing the issue with a comment
  pointing at the resolving commit/PR.
