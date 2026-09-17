# ADR 0010: Branch-first Forgejo mutations

## Status

Accepted for repository-side agent workflows.

## Decision

Agent-authored Forgejo file mutations must target a newly created task branch,
never `main` or another protected branch. The branch head is recorded and
verified immediately before the mutation batch. `create_file`, `update_file`,
and `delete_file` fail closed when the branch target, branch sequencing, or
head check is missing. Read-only calls and pull-request creation do not grant
file-write authority.

The reusable contract lives in `tools/forgejo_write_policy.py`. Bifrost callers must
apply the same sequence: create the branch from the current protected tip,
verify the returned branch and head, perform file mutations only on that
branch, then open a pull request back to `main`.

## Rationale and limits

The policy makes the mutation target explicit at the MCP boundary and prevents
an accidental protected-branch write caused by a stale ref, tag, or commit
SHA. It is defense in depth. Forgejo branch protection remains authoritative
and must independently require pull requests, checks, and restricted direct
writes. A repository-local helper cannot prevent an administrator, a web/API
write, or a caller that deliberately bypasses the helper.

Fetches, checkouts, ancestry checks, and local branch movement are outside the
file-mutation contract. They do not write repository files through the MCP
surface and therefore must not be treated as proof that a later mutation is
safe.
