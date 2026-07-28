# AGENTS

## Agent skills

### Issue tracker

Specs and implementation tickets live under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Local tickets use the default Matt Pocock triage roles. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository with a root `CONTEXT.md` and system decisions under `docs/adr/`. See `docs/agents/domain.md`.

## What this project does

Antislop is a pair of AI agent skills that suppress detectable AI writing patterns. **antislop** is an ambient writing style that triggers automatically when asked to write or edit prose. **antislop-audit** scores text 0-100 and returns a violations list with severity and excerpts. Works with any agent supporting the SKILL.md or skills system.

There is also an agent file (`.opencode/agents/antislop.md`) that bundles both modes into a single spawnable agent. The agent file format is opencode-specific, but the rules content works as a system prompt in any LLM.

## How to run and test

```bash
# Full propagation check: generate.py --check + validate.py, one report
bash check.sh

# Unit tests (stdlib unittest, no external deps)
python3 -m unittest discover -s tests

# Structural invariants only
python3 validate.py --skills-dir skills --expect-version 2.0.0

# Committed artifacts match the registry
python3 generate.py --check

# Score arbitrary text against the registry
echo "some text" | python3 score.py --profile general

# Lint via CI (requires Docker)
act push -W .forgejo/workflows/lint-skills.yml

# Test a skill locally — copy to agent skills dir
cp skills/antislop/SKILL.md ~/.claude/skills/antislop/
cp skills/antislop-audit/SKILL.md ~/.claude/skills/antislop-audit/

# Test the agent — copy to global agents dir
cp .opencode/agents/antislop.md ~/.config/opencode/agents/

# Test the Claude Code plugin
claude plugin validate .claude-plugin/plugin.json
claude --plugin-dir .
```

To test repo changes in an agent conversation, copy the updated `SKILL.md` into the agent's skills directory and restart.

### System prompt (any LLM)

For agent frameworks or LLM chats that don't support skills or subagents, use the rules directly as a system prompt:

- **Writing style:** paste `skills/antislop/SKILL.md` at the start of a conversation
- **Audit:** paste `skills/antislop-audit/SKILL.md` and then the text to audit
- **Both modes:** paste `.opencode/agents/antislop.md` (strip the YAML frontmatter) for the combined two-mode system prompt

This works with Claude.ai, ChatGPT, Cursor, Windsurf, Zed, or any tool that accepts a custom system prompt.

## Key architecture decisions

**`rules.json` is the canonical source, not any single SKILL.md.** `generate.py` renders `pattern-reference.md` from it deterministically; `score.py` scores against it directly. `skills/antislop/GEMINI.md` and `.opencode/agents/antislop.md` are hand-maintained derivatives, not generated — when adding a rule, update those alongside the registry. `validate.py` enforces version consistency across all eleven version-bearing files (see Conventions below), not just four — that was the 1.x-era check.

**Structure section is grouped by level.** Sentence-level, Paragraph-level, Discourse-level. This came from the realization that 25+ flat bullet points were unparseable under context pressure. Place new rules in the right sub-group.

**Vocabulary is a table with built-in replacements.** The original design had a comma-separated banned word list plus a separate Emergency Replacements table with significant duplication. The table format eliminates duplication and gives the model the fix alongside the rule.

**Em-dashes are banned absolutely.** The skill instructs models to post-process and replace them. Skill files themselves use em-dashes in rule explanations — this is meta-context, not a violation. The model must distinguish between documenting a rule and violating it.

**Semantic rules require human checking.** Paragraph-level redundancy and triplet overlap can't be pattern-matched. The skill explicitly tells the model these are manual checks.

**GEMINI.md is a two-mode file.** It bundles both Style and Audit modes into one extension file, triggered by intent matching. Style mode outputs exclusively to Canvas. This structure differs from the split SKILL.md / SKILL.md approach for Claude Code.

**Agent file is a hand-maintained derivative.** `.opencode/agents/antislop.md` combines style and audit rules with subagent-specific framing, like GEMINI.md. It has its own two-mode structure and subagent context. When adding a rule, update the agent file alongside the other derivatives.

## Conventions

- Sentence case headings everywhere — no Title Case
- Skill files stay under 500 lines (current: 154 / 383 / 163)
- Version bumps touch eleven files: `metadata.version` and inline `**Version:**` in each SKILL.md, `gemini-extension.json`, `GEMINI.md`, `.opencode/agents/antislop.md`, `rules.json`, both `lint-skills.yml` workflows, the production assertion in `tests/test_validate.py`, and `.claude-plugin/plugin.json`. Nothing checks the plugin manifest automatically, so it drifts silently. `pattern-reference.md` is generated, so regenerate rather than edit it. Verify with `python3 validate.py --skills-dir skills --expect-version <new>` and `bash check.sh`. Test fixtures keep their deliberately wrong versions.
- README follows antislop rules itself: zero em-dashes, no banned vocabulary
- Forgejo is the primary CI. Workflows live in `.forgejo/workflows/`. GitHub is a mirror only.
- When to Use / When NOT to Use sections are mandatory — the lint CI fails without them
- Agent file (`.opencode/agents/antislop.md`) is a derivative synced alongside GEMINI.md and antislop-audit/SKILL.md
- `.claude-plugin/marketplace.json` self-hosts the plugin (`claude plugin marketplace add <repo-url>`). It carries no version field of its own, so it's not part of the eleven-file version-bump list, but its `plugins[].description` should stay in sync with `plugin.json`'s `description` by hand.

## Known gotchas

**Lightweight tags blocked by Forgejo.** Forgejo requires annotated tags (`git tag -a -m "msg"`) for releases. Lightweight tags return HTTP 409 "Release has no Tag." The release workflow converts lightweight tags to annotated automatically, but this requires a PAT stored as `RELEASE_TOKEN` secret — the built-in actions token lacks release permissions.

**Heredocs in YAML `run: |` blocks.** The `|` block scalar strips leading whitespace relative to the first content line, but bash heredoc delimiters must be at column 0. These two requirements conflict. Use `printf` to a file or inline JSON instead.

**Asset upload parameter differs by platform.** Forgejo requires `?name=file.zip` as a query parameter on the asset upload endpoint. GitHub derives the name from the form field.

**`skills/antislop/GEMINI.md` is not a direct port of SKILL.md.** It has audit severity rules inline, a different organizational structure, and Canvas-only output instructions. Don't treat it as a 1:1 mirror when syncing rules.

**`.opencode/agents/antislop.md` is not a direct port of either SKILL.md.** It combines style and audit rules with subagent framing: no Canvas, no skill-specific When to Use sections, intent matching for mode detection. Don't treat it as a 1:1 mirror when syncing rules. The 500-line skill convention does not apply to the agent file.

**Global replacements cause collateral damage.** A `sed 's/—/,/g'` across markdown replaced em-dashes in code spans and explanations, not just prose. Always verify after bulk edits. `validate.py` now checks for this: it rejects the ASCII stand-ins a bulk replace leaves behind (` -- ` for an em dash, `->` for an arrow) outside code spans, and flags a shared line carrying different marks in different artifacts. Marks quoted inside backticks stay exempt, since the files have to name what they ban.

**Forgejo runner can't resolve public hostname.** The Forgejo runner container is on the local Docker network and cannot resolve `git.drunkrhin0.au` (DNS fails). All `git clone` and `curl` calls in Forgejo workflows must use the internal IP `192.168.1.62:3000`. The runner also can't use `actions/checkout` with the default URL — it fails with `Could not resolve host: git.drunkrhin0.au`. Workaround: skip `actions/checkout` entirely and do a manual `git clone` in a custom step using the internal URL.

**Internal Forgejo runs on HTTP, not HTTPS.** Port 3000 serves plain HTTP. Using `https://192.168.1.62:3000` causes `gnutls_handshake() failed: An unexpected TLS packet was received`. Always use `http://` for the internal Forgejo instance.

**Forgejo Actions doesn't support SHA-pinned GitHub actions.** Pinning `actions/checkout@93cb6efe...` (SHA digest) fails on Forgejo 15.0.1. Use tag references like `actions/checkout@v4` instead. GitHub Actions supports SHA pinning natively — keep the GitHub workflows SHA-pinned for security.

**Forgejo's `container:` key with `runs-on: docker` is unreliable.** The runner is registered with label `docker:docker://node:lts` (a Debian-based image). The `container:` field to specify a different image (like `alpine:3.20`) may not override the default. The `apk` package manager fails because the actual container is Debian, not Alpine. Use `runs-on: ubuntu-latest` instead and rely on the runner having standard tools pre-installed.

**Bash parameter expansion `#http://` only strips `http://`, not `https://`.** If `GITHUB_SERVER_URL` is `https://git.drunkrhin0.au`, the expansion `${GITHUB_SERVER_URL#http://}` leaves it unchanged, producing `https://https://...` in the resulting URL. Use a more robust method or hardcode the URL.

**`GITHUB_REPOSITORY` is a full SSH URL on this Forgejo runner, not `owner/repo`.** The runner sets `GITHUB_REPOSITORY=ssh://git@git.drunkrhin0.au/drunkrhin0/antislop` rather than just `drunkrhin0/antislop`. Concatenating it into a URL produces garbage like `http://192.168.1.62:3000/ssh://git@...`. Hardcode the repo path instead, or strip the SSH prefix with parameter expansion.

**`release-skills.yml` auto-tag workflow never fires on Forgejo.** The workflow in `.github/workflows/release-skills.yml` uses `actions/checkout` with SHA pinning, which fails on this Forgejo runner (DNS + SHA pin issues documented above). When a version bump lands on `main`, no tag is created automatically. The GitHub mirror gets the tag only if manually pushed. Fix: after merging a version bump to `main`, create and push both annotated tags manually:

```bash
git fetch origin main
git tag -a antislop-vX.Y.Z -m "antislop vX.Y.Z" origin/main
git tag -a antislop-audit-vX.Y.Z -m "antislop-audit vX.Y.Z" origin/main
git push origin antislop-vX.Y.Z antislop-audit-vX.Y.Z
```

The Forgejo `create-release.yml` workflow picks up the tags and builds release assets automatically. Then push the same tags to GitHub for the mirror release:

```bash
git push git@github.com:drunkrhin0/antislop.git antislop-vX.Y.Z antislop-audit-vX.Y.Z
```

If creating a `.forgejo/workflows/release-skills.yml` Forgejo-native version of the auto-tag workflow, replace `actions/checkout` with a manual `git clone` via the internal HTTP URL and use tag refs only (no SHA pinning).

**GitHub release workflow needs `permissions: contents: write`.** `.github/workflows/release-skills.yml` uses `softprops/action-gh-release@v2` to create releases. The default `GITHUB_TOKEN` cannot create releases — the job-level `permissions:` block is required. Without it, you get `403 Resource not accessible by integration`. Added in commit `f3b7269`.

**Forgejo release workflow ran its release steps on every push to main, not just tag pushes.** Unlike the GitHub version, `.forgejo/workflows/release-skills.yml` triggers on both `push: branches: [main]` (to auto-create the version tag) and `push: tags:` (to build and publish the release). The "Resolve version from tag" / "Build zips" / "Create release" steps had no guard distinguishing the two, so on the raw branch-push trigger `GITHUB_REF_NAME` was `main` itself, not a real tag, producing `Finding release for tag main...` and a 401 from the release-creation call. Fixed by gating those three steps on `if: startsWith(github.ref, 'refs/tags/')`. The workflow also never got the `permissions: contents: write` block the GitHub version has — without it, `git push origin "${TAG}"` in the tag-creation steps most likely fails silently too (no `set -e` in that step), which is why no `antislop-v2.0.0` tag existed on the remote when this surfaced. Separately, the release-creation call still needs a valid `RELEASE_TOKEN` repo secret — a malformed or unset one fails with `token is malformed: token contains an invalid number of segments`, which is a Forgejo repo-settings problem, not a workflow bug.

---

<skills_system priority="1">

## Available Skills

<!-- SKILLS_TABLE_START -->
<usage>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke: `npx openskills read <skill-name>` (run in your shell)
  - For multiple: `npx openskills read skill-one,skill-two`
- The skill content will load with detailed instructions on how to complete the task
- Base directory provided in output for resolving bundled resources (references/, scripts/, assets/)

Usage notes:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already loaded in your context
- Each skill invocation is stateless
</usage>

<available_skills>

<skill>
<name>antislop</name>
<description>Universal writing style that suppresses detectable AI writing patterns across all content types. Apply whenever writing, editing, or reviewing any prose — emails, blog posts, reports, social content, technical writing, sales materials. This is an ambient style, not a task-specific tool. Trigger any time the user asks to write, rewrite, edit, polish, or review text of any kind.</description>
<location>project</location>
</skill>

<skill>
<name>antislop-audit</name>
<description>Audits text for AI slop patterns and returns a slop score (0-100) plus a violations list. Use when the user asks to check, audit, review, grade, or score text for AI patterns, AI slop, or writing quality. Also trigger when the user pastes text and asks "does this pass?", "is this sloppy?", "flag the AI patterns", or similar. Companion to the antislop writing style skill. Zero exceptions — flag every violation regardless of perceived intent or satire.</description>
<location>project</location>
</skill>

</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>
