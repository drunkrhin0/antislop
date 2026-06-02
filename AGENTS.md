# AGENTS

## What this project does

Antislop is a pair of AI agent skills that suppress detectable AI writing patterns. **antislop** is an ambient writing style that triggers automatically when asked to write or edit prose. **antislop-audit** scores text 0-100 and returns a violations list with severity and excerpts. Works with any agent supporting the SKILL.md or skills system.

## How to run and test

```bash
# Lint all SKILL.md files
bash /tmp/lint-test.sh

# Lint via CI (requires Docker)
act push -W .forgejo/workflows/lint-skills.yml

# Test a skill locally — copy to agent skills dir
cp antislop/SKILL.md ~/.claude/skills/antislop/
cp antislop-audit/SKILL.md ~/.claude/skills/antislop-audit/
```

To test repo changes in an agent conversation, copy the updated `SKILL.md` into the agent's skills directory and restart.

## Key architecture decisions

**`antislop/SKILL.md` is the canonical source.** `antislop/GEMINI.md` and `antislop-audit/SKILL.md` are synced derivatives. When adding a rule, update all three plus severity categories and pattern references in the audit file. The lint CI enforces version consistency across all four version-bearing files.

**Structure section is grouped by level.** Sentence-level, Paragraph-level, Discourse-level. This came from the realization that 25+ flat bullet points were unparseable under context pressure. Place new rules in the right sub-group.

**Vocabulary is a table with built-in replacements.** The original design had a comma-separated banned word list plus a separate Emergency Replacements table with significant duplication. The table format eliminates duplication and gives the model the fix alongside the rule.

**Em-dashes are banned absolutely.** The skill instructs models to post-process and replace them. Skill files themselves use em-dashes in rule explanations — this is meta-context, not a violation. The model must distinguish between documenting a rule and violating it.

**Semantic rules require human checking.** Paragraph-level redundancy and triplet overlap can't be pattern-matched. The skill explicitly tells the model these are manual checks.

**GEMINI.md is a two-mode file.** It bundles both Style and Audit modes into one extension file, triggered by intent matching. Style mode outputs exclusively to Canvas. This structure differs from the split SKILL.md / SKILL.md approach for Claude Code.

## Conventions

- Sentence case headings everywhere — no Title Case
- Skill files stay under 500 lines (current: 306 / 309 / 243)
- Version bumps touch four places: two frontmatter fields, one inline version, one JSON file
- README follows antislop rules itself: zero em-dashes, no banned vocabulary
- Workflows live in both `.forgejo/workflows/` and `.github/workflows/` — neither directory is the sole source
- When to Use / When NOT to Use sections are mandatory — the lint CI fails without them

## Known gotchas

**Lightweight tags blocked by Forgejo.** Forgejo requires annotated tags (`git tag -a -m "msg"`) for releases. Lightweight tags return HTTP 409 "Release has no Tag." The release workflow converts lightweight tags to annotated automatically, but this requires a PAT stored as `RELEASE_TOKEN` secret — the built-in actions token lacks release permissions.

**Heredocs in YAML `run: |` blocks.** The `|` block scalar strips leading whitespace relative to the first content line, but bash heredoc delimiters must be at column 0. These two requirements conflict. Use `printf` to a file or inline JSON instead.

**Asset upload parameter differs by platform.** Forgejo requires `?name=file.zip` as a query parameter on the asset upload endpoint. GitHub derives the name from the form field.

**`antislop/GEMINI.md` is not a direct port of SKILL.md.** It has audit severity rules inline, a different organizational structure, and Canvas-only output instructions. Don't treat it as a 1:1 mirror when syncing rules.

**Global replacements cause collateral damage.** A `sed 's/—/,/g'` across markdown replaced em-dashes in code spans and explanations, not just prose. Always verify after bulk edits.

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
