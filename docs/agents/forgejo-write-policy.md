# Forgejo write policy

This repository uses a branch-first contract for agent-authored Forgejo file
changes. The contract is defense in depth. Forgejo branch protection and the
server-side Bifrost policy remain the enforcement boundary.

## Required workflow

1. Resolve the repository default branch and the current head through Forgejo
   MCP via Bifrost.
2. Create a task branch with a codex name from that head.
3. Verify the new branch and record its head before the first file mutation.
4. Call forgejo_write_policy.authorize_operation for every file mutation
   batch. Pass the task branch, the recorded head, and the freshly observed
   head. A changed head stops the workflow for a fresh read and decision.
5. Mutate only the task branch through Forgejo MCP via Bifrost. Never target
   main, the resolved default branch, a configured protected branch, a tag,
   a commit SHA, or an ambiguous ref.
6. Verify the task branch head after every mutation batch.
7. Open a pull request after the branch is complete. Pull request creation
   does not grant approval or merge authority.

The policy accepts ordinary non-protected branch names and is intended for
codex issue slug task branches. It rejects missing targets, whitespace,
refs and tags, commit SHAs, and protected names.

## Operation classification

The public helper allows only the explicitly classified read-only operations
and pull request creation. Unknown operations, including merge and review
operations, fail closed and cannot be treated as read-only by omission.

## Administrator acceptance check

A maintainer must inspect the Forgejo repository permissions and branch rules
to confirm that the svc-forgejo-agent account cannot push directly to main.
This check must use a harmless permission inspection or dry-run probe; it must
not leave a real commit on main. If server-side enforcement is not available,
record the blocker and owner in Forgejo. Do not treat this local policy as a
replacement for that control.

## Incident record

The triggering incident was the direct main write on 2026-09-14:

- 20d937a recorded the acceptance change.
- 7d70b27 restored the tree 22 seconds later.
- Forgejo workflow runs 8476 and 8477 cover the write and restoration.
- The zero-diff tree verification established that the restored tree matched
  d6d9bc7.

The incident is recorded here without credentials or raw tool payloads.
