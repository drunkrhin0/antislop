# Claude Code end-to-end acceptance

This runbook checks the Claude Code plugin on the real CLI. It is manual and
opt-in because a live prompt needs an authenticated Claude account and may
consume paid usage.

The acceptance target is one exact Antislop v3 revision. Run the checks against
the release commit or release artifact under test. Do not use a moving branch,
a dirty checkout, or a globally installed copy of the skills.

## What the run proves

A completed run records evidence for each of these claims:

- Claude Code accepts both shipped plugin manifests.
- A fresh profile discovers exactly antislop and generate-slop in the
  antislop namespace.
- A writing request loads antislop in writing mode and produces a rewrite
  consistent with the checked-in rules.
- An audit request loads antislop in audit mode and returns the checked-in
  audit shape.
- An unrelated request loads neither skill.
- A second clean profile gives the same discovery result.
- The receipt contains bounded observations rather than credentials or a raw
  provider transcript.

The repository checks and manifest validator do not prove the last five claims.
Those require an authenticated Claude Code session.

## Prerequisites

Use a shell with:

- Claude Code installed at the version recorded in the receipt.
- An existing Claude Code login that the operator is allowed to use.
- A checkout or extracted release artifact for the exact revision under test.
- No project or global Antislop skill installed outside the checkout.

The runbook never asks for a token. Do not set an API key in a command copied
into a receipt. Do not print files from the Claude configuration directory or
environment variables.

## Pin the input

Set the checkout and the exact revision before running any prompt:

~~~
export ANTISLOP_DIR=/absolute/path/to/antislop
export ANTISLOP_REVISION=<40-character-merge-or-release-commit>

test -d "$ANTISLOP_DIR/.claude-plugin"
test "$(git -C "$ANTISLOP_DIR" rev-parse HEAD)" = "$ANTISLOP_REVISION"
test -z "$(git -C "$ANTISLOP_DIR" status --porcelain)"
~~~

Record the value of ANTISLOP_REVISION. An open PR, moving branch, or unmerged
revision is not behavioral acceptance. Stop and record the exact blocker if no
accepted v3 revision or release artifact exists yet.

Record the CLI version without printing credentials:

~~~
claude --version
~~~

## Validate both manifests

Run the validator against the files in the pinned checkout:

~~~
cd "$ANTISLOP_DIR"
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .claude-plugin/marketplace.json
~~~

Record one pass or blocked result for each command. A validator failure is not a
login failure. Keep the error category and a short first-line observation in the
receipt, then stop before live prompts until the manifest is fixed.

Run the repository checks as a separate result:

~~~
python3 validate.py --skills-dir skills --expect-version-from rules.json
bash check.sh
python3 -m unittest discover -s tests -v
~~~

Use the commands from the pinned checkout. A repository check can pass while
Claude Code behavior remains untested.

## Start a clean local-plugin session

The local plugin check must not use a previously installed copy. Give Claude
Code a new configuration directory for this run:

~~~
umask 077
CLAUDE_E2E_TMP="$(mktemp -d)"
trap 'rm -rf "$CLAUDE_E2E_TMP"' EXIT
mkdir -p "$CLAUDE_E2E_TMP/profile-1"

cd "$ANTISLOP_DIR"
CLAUDE_CONFIG_DIR="$CLAUDE_E2E_TMP/profile-1" \
  claude --plugin-dir "$ANTISLOP_DIR"
~~~

Use the plugin and skills discovery command exposed by the pinned Claude Code
version. In current Claude Code releases, /help and /plugin are the useful
entry points. Record the exact command used. The roster must contain only:

~~~
antislop:antislop
antislop:generate-slop
~~~

A different name, an unnamespaced skill, an extra production skill, or a
fixture skill is a failure. If the CLI does not show a skill roster, record
discovery as unobserved rather than treating successful prompts as proof.

## Check writing activation

In the same fresh session, submit a natural writing request. Do not invoke the
skill by slash command for this case:

~~~
Rewrite this exact sentence as plain technical prose. Preserve every fact and
return only the rewrite: Parser rejects bad date -> exit 2, no write.
~~~

Record:

- whether Claude Code showed antislop as the loaded skill, if the pinned
  version exposes that evidence;
- the bounded result, no more than one sentence;
- whether the result restored grammar and stated the arrow relationship in
  words while keeping rejection, exit code 2, and no write.

Do not paste the chat into the repository. If the result is correct but the
loaded skill cannot be observed, mark activation as unobserved and leave the
case pending.

## Check audit activation

Start a second one-shot session or clear the conversation before this prompt.
Do not invoke the skill by slash command:

~~~
Audit this exact text. Return the formulaic-writing risk score, a violations
list with severity and excerpt, and a short summary. Do not rewrite it:
It is important to note that the deployment was successful.
~~~

Record:

- whether Claude Code showed antislop in audit mode as the loaded skill;
- the score, violation count, and one short finding excerpt;
- whether the response used the checked-in audit terms and did not rewrite the
  source.

An answer without the audit shape is a failure. A correct-looking answer with
no observable activation evidence is pending, not pass.

## Check non-activation

Use a third clean session or clear the conversation. Submit an unrelated
request:

~~~
What is 2 + 2? Reply with only the number.
~~~

Record the answer and whether either `antislop` or `generate-slop` appeared as
loaded. The answer should be 4, and neither skill should appear. A normal
factual answer is not evidence that a writing skill loaded silently.

## Restart check

Exit Claude Code. Create a second empty profile and load the same checkout:

~~~
mkdir -p "$CLAUDE_E2E_TMP/profile-2"
cd "$ANTISLOP_DIR"
CLAUDE_CONFIG_DIR="$CLAUDE_E2E_TMP/profile-2" \
  claude --plugin-dir "$ANTISLOP_DIR"
~~~

Repeat only the discovery command and roster check. It must match profile 1.
A changed roster means the first run depended on cached state or an undeclared
global installation.

## Optional self-hosted marketplace check

This check is separate from the local plugin check. Run it only when the
pinned Claude Code version supports the self-hosted Forgejo route and the
operator accepts the configuration change:

~~~
claude plugin marketplace add https://git.drunkrhin0.au/drunkrhin0/antislop.git
claude plugin install antislop@drunkrhin0
~~~

Use a clean profile for this test too. Record unsupported marketplace behavior
as unsupported, not pass. Do not publish to a third-party marketplace.

## Run the opt-in driver

The driver performs the revision, checkout, CLI, manifest, and repository
preflight checks. It exits 2 for a blocked prerequisite, 1 for a failed
deterministic check, and 0 when the requested checks completed. It does not
decide whether a skill activated correctly.

Run the safe preflight first:

~~~
bash scripts/claude-code-e2e.sh \
  --repo "$ANTISLOP_DIR" \
  --revision "$ANTISLOP_REVISION" \
  --receipt /tmp/antislop-claude-code-e2e.txt
~~~

Live probes require a separate opt-in environment variable. They use three
temporary Claude profiles, each bounded by CLAUDE_E2E_TIMEOUT_SECONDS (default
180 seconds, maximum 900), and discard all provider output. Review the behavior
with this runbook and write only bounded observations into the receipt:

The driver uses GNU `timeout --signal=TERM` when it is available. On systems
such as macOS without it, Python's standard library provides the timeout and
sends `TERM`, escalating only if the process does not exit.
If the temporary profiles report not logged in, rerun the live driver with the
existing authenticated Claude config directory. This keeps credentials outside
the receipt and uses a fresh Claude process for each probe:

~~~
CLAUDE_E2E_ALLOW_LIVE=1 \
  bash scripts/claude-code-e2e.sh \
    --config-dir "$HOME/.claude" \
    --revision "$ANTISLOP_REVISION" \
    --live \
    --receipt /tmp/antislop-claude-code-e2e-live.txt
~~~

The receipt records that an authenticated config directory was used. The
operator must still perform the roster and restart observations described
above.

~~~
CLAUDE_E2E_ALLOW_LIVE=1 \
  bash scripts/claude-code-e2e.sh \
    --repo "$ANTISLOP_DIR" \
    --revision "$ANTISLOP_REVISION" \
    --live \
    --receipt /tmp/antislop-claude-code-e2e-live.txt
~~~

The driver reports successful live commands as
completed_manual_review_required. That status is not a behavioral pass. The
operator must still observe the skill roster and each prompt result in a real
Claude Code session.

## Receipt rules

A receipt records:

- the run date and operator;
- the Claude Code version, or unavailable;
- the Antislop revision or release artifact digest;
- the tested surface, such as local --plugin-dir;
- each check's pass, fail, blocked, pending, or unsupported result;
- short observations and the exact blocker when a check could not run.

Keep the receipt in docs/claude-code-e2e-receipt.md or in a private work log.
Never commit a token, login URL containing a code, environment dump, config file,
or unrestricted transcript.

The repository's acceptance receipt starts in a blocked state when this
environment cannot run Claude Code. Replace only the bounded result fields after
a real authenticated run. A blocked or pending receipt does not authorize a
merge or issue closure.
