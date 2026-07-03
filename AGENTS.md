# AGENTS

## What this project does

Antislop is a pair of AI agent skills that suppress detectable AI writing patterns. **antislop** is an ambient writing style that triggers automatically when asked to write or edit prose. **antislop-audit** scores text 0-100 and returns a violations list with severity and excerpts. Works with any agent supporting the SKILL.md or skills system.

There is also an agent file (`.opencode/agents/antislop.md`) that bundles both modes into a single spawnable agent. The agent file format is opencode-specific, but the rules content works as a system prompt in any LLM.

## How to run and test

```bash
# Lint all SKILL.md files
bash /tmp/lint-test.sh

# Lint via CI (requires Docker)
act push -W .forgejo/workflows/lint-skills.yml

# Test a skill locally — copy to agent skills dir
cp antislop/SKILL.md ~/.claude/skills/antislop/
cp antislop-audit/SKILL.md ~/.claude/skills/antislop-audit/

# Test the agent — copy to global agents dir
cp .opencode/agents/antislop.md ~/.config/opencode/agents/
```

To test repo changes in an agent conversation, copy the updated `SKILL.md` into the agent's skills directory and restart.

### System prompt (any LLM)

For agent frameworks or LLM chats that don't support skills or subagents, use the rules directly as a system prompt:

- **Writing style:** paste `antislop/SKILL.md` at the start of a conversation
- **Audit:** paste `antislop-audit/SKILL.md` and then the text to audit
- **Both modes:** paste `.opencode/agents/antislop.md` (strip the YAML frontmatter) for the combined two-mode system prompt

This works with Claude.ai, ChatGPT, Cursor, Windsurf, Zed, or any tool that accepts a custom system prompt.

## Key architecture decisions

**`antislop/SKILL.md` is the canonical source.** `antislop/GEMINI.md` and `antislop-audit/SKILL.md` are synced derivatives. When adding a rule, update all three plus severity categories and pattern references in the audit file. The lint CI enforces version consistency across all four version-bearing files.

**Structure section is grouped by level.** Sentence-level, Paragraph-level, Discourse-level. This came from the realization that 25+ flat bullet points were unparseable under context pressure. Place new rules in the right sub-group.

**Vocabulary is a table with built-in replacements.** The original design had a comma-separated banned word list plus a separate Emergency Replacements table with significant duplication. The table format eliminates duplication and gives the model the fix alongside the rule.

**Em-dashes are banned absolutely.** The skill instructs models to post-process and replace them. Skill files themselves use em-dashes in rule explanations — this is meta-context, not a violation. The model must distinguish between documenting a rule and violating it.

**Semantic rules require human checking.** Paragraph-level redundancy and triplet overlap can't be pattern-matched. The skill explicitly tells the model these are manual checks.

**GEMINI.md is a two-mode file.** It bundles both Style and Audit modes into one extension file, triggered by intent matching. Style mode outputs exclusively to Canvas. This structure differs from the split SKILL.md / SKILL.md approach for Claude Code.

**Agent file is a hand-maintained derivative.** `.opencode/agents/antislop.md` combines style and audit rules with subagent-specific framing, like GEMINI.md. It has its own two-mode structure and subagent context. When adding a rule, update the agent file alongside the other derivatives.

## Conventions

- Sentence case headings everywhere — no Title Case
- Skill files stay under 500 lines (current: 306 / 309 / 243)
- Version bumps touch five places: two frontmatter fields, one inline version, one JSON file, and the agent file's inline version
- README follows antislop rules itself: zero em-dashes, no banned vocabulary
- Forgejo is the primary CI. Workflows live in `.forgejo/workflows/`. GitHub is a mirror only.
- When to Use / When NOT to Use sections are mandatory — the lint CI fails without them
- Agent file (`.opencode/agents/antislop.md`) is a derivative synced alongside GEMINI.md and antislop-audit/SKILL.md

## Known gotchas

**Lightweight tags blocked by Forgejo.** Forgejo requires annotated tags (`git tag -a -m "msg"`) for releases. Lightweight tags return HTTP 409 "Release has no Tag." The release workflow converts lightweight tags to annotated automatically, but this requires a PAT stored as `RELEASE_TOKEN` secret — the built-in actions token lacks release permissions.

**Heredocs in YAML `run: |` blocks.** The `|` block scalar strips leading whitespace relative to the first content line, but bash heredoc delimiters must be at column 0. These two requirements conflict. Use `printf` to a file or inline JSON instead.

**Asset upload parameter differs by platform.** Forgejo requires `?name=file.zip` as a query parameter on the asset upload endpoint. GitHub derives the name from the form field.

**`antislop/GEMINI.md` is not a direct port of SKILL.md.** It has audit severity rules inline, a different organizational structure, and Canvas-only output instructions. Don't treat it as a 1:1 mirror when syncing rules.

**`.opencode/agents/antislop.md` is not a direct port of either SKILL.md.** It combines style and audit rules with subagent framing: no Canvas, no skill-specific When to Use sections, intent matching for mode detection. Don't treat it as a 1:1 mirror when syncing rules. The 500-line skill convention does not apply to the agent file.

**Global replacements cause collateral damage.** A `sed 's/—/,/g'` across markdown replaced em-dashes in code spans and explanations, not just prose. Always verify after bulk edits.

**Forgejo runner can't resolve public hostname.** The Forgejo runner container is on the local Docker network and cannot resolve `git.drunkrhin0.au` (DNS fails). All `git clone` and `curl` calls in Forgejo workflows must use the internal IP `192.168.1.62:3000`. The runner also can't use `actions/checkout` with the default URL — it fails with `Could not resolve host: git.drunkrhin0.au`. Workaround: skip `actions/checkout` entirely and do a manual `git clone` in a custom step using the internal URL.

**Internal Forgejo runs on HTTP, not HTTPS.** Port 3000 serves plain HTTP. Using `https://192.168.1.62:3000` causes `gnutls_handshake() failed: An unexpected TLS packet was received`. Always use `http://` for the internal Forgejo instance.

**Forgejo Actions doesn't support SHA-pinned GitHub actions.** Pinning `actions/checkout@93cb6efe...` (SHA digest) fails on Forgejo 15.0.1. Use tag references like `actions/checkout@v4` instead. GitHub Actions supports SHA pinning natively — keep the GitHub workflows SHA-pinned for security.

**Forgejo's `container:` key with `runs-on: docker` is unreliable.** The runner is registered with label `docker:docker://node:lts` (a Debian-based image). The `container:` field to specify a different image (like `alpine:3.20`) may not override the default. The `apk` package manager fails because the actual container is Debian, not Alpine. Use `runs-on: ubuntu-latest` instead and rely on the runner having standard tools pre-installed.

**Bash parameter expansion `#http://` only strips `http://`, not `https://`.** If `GITHUB_SERVER_URL` is `https://git.drunkrhin0.au`, the expansion `${GITHUB_SERVER_URL#http://}` leaves it unchanged, producing `https://https://...` in the resulting URL. Use a more robust method or hardcode the URL.

**`/tmp/lint-test.sh` doesn't exist.** The AGENTS.md references it but the script was never created. Use `act push -W .forgejo/workflows/lint-skills.yml` instead (requires Docker).

**`GITHUB_REPOSITORY` is a full SSH URL on this Forgejo runner, not `owner/repo`.** The runner sets `GITHUB_REPOSITORY=ssh://git@git.drunkrhin0.au/drunkrhin0/antislop` rather than just `drunkrhin0/antislop`. Concatenating it into a URL produces garbage like `http://192.168.1.62:3000/ssh://git@...`. Hardcode the repo path instead, or strip the SSH prefix with parameter expansion.

**`rstrip('.0')` in lint workflow breaks versions ending in `.0`.** The lint check at `.forgejo/workflows/lint-skills.yml:90` uses `python3 -c "version.rstrip('.0')"` to normalize the JSON version before comparing. For versions like `1.4.0`, this strips to `1.4`, causing a false version-drift failure. The version is actually consistent — the check is broken. Fix: use `re.sub(r'\.0+$', '', v)` or don't normalize at all.

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
