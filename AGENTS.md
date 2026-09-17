# AGENTS

## Agent skills

### Issue tracker

Specs and implementation tickets are tracked as Forgejo issues. See `docs/agents/issue-tracker.md`.

### Protected Forgejo writes

Agent-authored Forgejo file mutations are branch-first and fail closed on
`main`, the resolved default branch, and named protected branches. Use
`docs/agents/forgejo-write-policy.md` and the public
`forgejo_write_policy.py` contract before any mutation. Create and verify a
`codex/` task branch, record its head, mutate only that branch through Forgejo
MCP via Bifrost, verify the head after each mutation batch, and open a PR.
Creating a PR never grants approval or merge authority.

### Triage labels

Issues use the labels configured on this repo's Forgejo instance, not the default Matt Pocock set. See `docs/agents/triage-labels.md` for the live list.

### Domain docs

This is a single-context repository with a root `CONTEXT.md` and system decisions under `docs/adr/`. See `docs/agents/domain.md`.

## What this project does

Antislop ships two AI agent skills. **antislop** is an ambient writing style that triggers automatically when asked to write or edit prose. Its audit mode scores text 0-100 and returns a violations list with severity and excerpts. **generate-slop** creates user-invoked synthetic material for demos and evaluation fixtures and must never be selected by an agent on its own. Works with any agent supporting the SKILL.md or skills system.

There is also an agent file (`.opencode/agents/antislop.md`) that bundles both modes into a single spawnable agent. The agent file format is opencode-specific, but the rules content works as a system prompt in any LLM. `generate-slop` remains a separate first-class skill across plugin surfaces because its explicit inverse purpose must not become a mode of the public `antislop` router.

## How to run and test

```bash
# Full propagation check: generate.py --check + validate.py, one report
bash check.sh

# Unit tests (stdlib unittest, no external deps)
python3 -m unittest discover -s tests

# Structural invariants only (version read from rules.json)
python3 validate.py --skills-dir skills --expect-version-from rules.json

# Committed artifacts match the registry
python3 generate.py --check

# Score arbitrary text against the registry
echo "some text" | python3 score.py --profile general

# Fidelity gate (patina-style, issue #90)
python3 fidelity.py --source-text "before" --candidate-text "after"
python3 fidelity.py --source before.txt --candidate after.txt --authorize number=50

# Semantic drift fixtures (slopkit-style, issue #91)
python3 drift.py

# Clarity-style review (issue #96)
python3 review.py --source-text "..." --medium argument
python3 review.py --fixtures skills/antislop/evals/clarity-review-fixtures.json

# Protected repair (unslop-style, issue #92)
python3 repair.py --file doc.md
cat doc.md | python3 repair.py --format json
python3 repair.py --file doc.md --write --format diff
python3 repair.py --fixtures skills/antislop/evals/repair-fixtures.json

# Bounded repair loop (lynote-style, issue #93)
python3 repair_loop.py --file doc.md
cat doc.md | python3 repair_loop.py
python3 repair_loop.py --file doc.md --max-attempts 2 --char-budget 100
python3 repair_loop.py --fixtures skills/antislop/evals/repair-loop-fixtures.json

# Sepia-style operation and venue routing (sepia-style, issue #94)
python3 sepia.py review --source-text "..." --venue ticket
python3 sepia.py review --source-text "..." --fiction
python3 sepia.py refactor --source-text "..." --venue ticket --accept vocab-utilize=use
python3 sepia.py recreate --source-text "..." --candidate "..." --venue postmortem
python3 sepia.py --fixtures skills/antislop/evals/sepia-routing-fixtures.json

# Evidence-bound delivery envelope (review-write style, issue #95)
python3 delivery.py verify --source-text "..." --body-text "..."
python3 delivery.py envelope --source-text "..." --body-text "..." --medium argument
python3 delivery.py check --envelope envelope.json
python3 delivery.py --fixtures skills/antislop/evals/delivery-envelope-fixtures.json

# Say-It-Human evidence and locale routing (say-it-human style, issue #97)
python3 say_human.py label --source-text "..." --claim "..."
python3 say_human.py repair --source-text "..." --required-claim "..." --locale zh-CN --venue release-note --authorize-delete
python3 say_human.py locale --source-text "..." --locale zh-CN
python3 say_human.py --fixtures skills/antislop/evals/say-human-fixtures.json

# Tagore-style substance report (issue #102)
python3 substance.py --source-text "..." --medium argument
cat doc.md | python3 substance.py --medium reference
python3 substance.py --proposal proposal.json
python3 substance.py --fixtures skills/antislop/evals/substance-fixtures.json

# Staged scan (humanizer-stack style, issue #98)
python3 scan.py --file doc.md
cat doc.md | python3 scan.py
python3 scan.py --doc a.md --doc b.md --doc c.md
python3 scan.py --file doc.md --fail-on-advisory
python3 scan.py --fixtures skills/antislop/evals/staged-scan-fixtures.json

# Lint via CI (requires Docker)
act push -W .forgejo/workflows/lint-skills.yml

# Test a skill locally — copy to agent skills dir
cp skills/antislop/SKILL.md ~/.claude/skills/antislop/
cp skills/generate-slop/SKILL.md ~/.claude/skills/generate-slop/

# Test the agent — copy to global agents dir
cp .opencode/agents/antislop.md ~/.config/opencode/agents/

# Test the Claude Code plugin
claude plugin validate .claude-plugin/plugin.json
claude --plugin-dir .

# Point Kiro at the Power: Powers panel -> Add Custom Power -> Import power from a folder -> absolute path to powers/antislop

# Kiro skills, manual path
cp -r skills/antislop skills/generate-slop ~/.kiro/skills/

# Verify the Kiro workspace exposes both skills
test -f .kiro/skills/antislop/SKILL.md || test -L .kiro/skills/antislop
test -f .kiro/skills/generate-slop/SKILL.md
```

To test repo changes in an agent conversation, copy the updated `SKILL.md` into the agent's skills directory and restart.

### System prompt (any LLM)

For agent frameworks or LLM chats that don't support skills or subagents, use the rules directly as a system prompt:

- **Writing style:** paste `skills/antislop/SKILL.md` at the start of a conversation
- **Audit:** paste `skills/antislop/SKILL.md` and then the text to audit
- **Both modes:** paste `.opencode/agents/antislop.md` (strip the YAML frontmatter) for the combined two-mode system prompt

This works with Claude.ai, ChatGPT, Cursor, Windsurf, Zed, or any tool that accepts a custom system prompt.

## Key architecture decisions

**`rules.json` is the canonical source, not any single SKILL.md.** `generate.py` renders `pattern-reference.md` from it deterministically; `score.py` scores against it directly. `.opencode/agents/antislop.md` is a hand-maintained derivative, not generated, so update it alongside the registry when a rule applies to that surface. `validate.py --expect-version` checks the shipped version-bearing artifacts: both SKILL.md files (metadata and body), `POWER.md`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, the root `plugin.json`, and the opencode agent, eight physical files carrying ten checked values (see Conventions below). Both lint workflows pass `validate.py --expect-version-from rules.json` and the production assertion in `tests/test_validate.py` derives its expected version through `validate.canonical_version()`, so the version is single-sourced in rules.json; a guard flags any workflow that hardcodes a `--expect-version` value disagreeing with the canonical version.

**Structure section is grouped by level.** Sentence-level, Paragraph-level, Discourse-level. This came from the realization that 25+ flat bullet points were unparseable under context pressure. Place new rules in the right sub-group.

**Vocabulary is a table with built-in replacements.** The original design had a comma-separated banned word list plus a separate Emergency Replacements table with significant duplication. The table format eliminates duplication and gives the model the fix alongside the rule.

**Em-dashes are banned absolutely.** The skill instructs models to post-process and replace them. Skill files themselves use em-dashes in rule explanations — this is meta-context, not a violation. The model must distinguish between documenting a rule and violating it.

**Semantic rules require human checking.** Paragraph-level redundancy and triplet overlap can't be pattern-matched. The skill explicitly tells the model these are manual checks.

**Agent file is a hand-maintained derivative.** `.opencode/agents/antislop.md` combines the public skill's writing and audit modes with subagent-specific framing. When adding a rule, update the agent file alongside the skill.

**The review layer reuses edit.py's audit authority and drift.py's fact matching.** `review.py` (issue #96) reports findings on a single artifact and never edits. Its five statuses (keep, revise, ask-author, cut, no-finding), the seven mediums, and the four mechanism rules (importance, impact, causality, superiority) live in rules.json and render into the pattern reference. Mechanism findings are advisory, zero-weight signals: they separate an unsupported significance claim from an evidenced consequence but never deduct. `[TK: ...]` markers are author-owned questions, never generated facts; `edit.py`'s placeholder scanner treats them as unresolved markers.

**The repair interface protects Markdown before it edits.** `repair.py` (issue #92) is an unslop-style, registry-aware repair command. It reuses `fidelity.py`'s protected spans and preservation gate, `score.py`'s `detect_findings`, and the conservative rule authority from `edit.py`. Fenced and indented code, inline code, YAML and JSON blocks, tables, blockquotes, headings, Markdown links, URLs, paths, commands, quoted source, numbers, dates, units, operators, and required terms stay byte-identical. Three deterministic repair classes fire: exact phrase replacement (a forbidden or discouraged deterministic rule whose correction names a literal), the single supported structural split (an overlong sentence at a comma-preceded conjunction), and integrity removal of leaked reasoning or planning wrappers outside quoted or code material. A proposed repair (`--edit`) is gated by the same fidelity check: a number or qualifier change fails, the write is prevented, and the exit is nonzero. The interface is intentionally limited: no detector feedback, surprisal targets, detector bypass, external models, persistent voice facts, or em-dash allowance; numeric style traits are deferred to a later author profile. The repair fixture corpus lives in `skills/antislop/evals/repair-fixtures.json` and `validate.py` runs it.

**The repair loop orchestrates the repair interface with bounded retries.** `repair_loop.py` (issue #93) adapts the control flow Lynote separates (detection, rewriting, post-processing, reassessment) into a loop that only ever repairs named findings on their smallest independent source spans, verified cleared and gated by `fidelity.py` before any accept. Retry count and the cumulative changed-character budget are strict bounds; a fidelity or integrity failure, an exhausted retry budget, or an exceeded character budget rolls back to the source immediately. Every attempt records a trace naming input findings, selected spans, correction IDs, output findings, fidelity result, and decision. Rhythm statistics (sentence length, lexical repetition) are advisory signals reported separately and never decide whether a passage is human. The loop never runs a detector adapter, translation step, model call, or network call; fixture mode only supplies declared deterministic corrections so the retry and rollback paths run entirely from `skills/antislop/evals/repair-loop-fixtures.json`, which `validate.py` runs. Lynote's translation chains, detector-score optimization, random substitutions, broad paraphrase rounds, and em-dash merge behavior are rejected; the adapted goal is defect removal with meaning preservation.

**The staged scan splits lexical cleanup from structural review.** `scan.py` (issue #98) is a two-stage audit over prose with fenced and inline code masked. The surface scan returns strict or advisory findings from the deterministic lexical rules; strict findings set the exit status and advisory findings do not unless `--fail-on-advisory` is set. The structural review runs the registered detectors and recommends at most two high-value interventions per pass, with no change as a valid result; it never turns advice into a mandatory recipe. A corpus comparison detects repeated document shapes (hook, reveal, lesson, close) only across two or more explicitly supplied documents, and a single document never triggers a cross-document convergence claim. Every repair reruns both stages on its candidate and reports residual findings in `repair.py`'s `residual_scan` section. The staged-scan fixture corpus lives in `skills/antislop/evals/staged-scan-fixtures.json` and `validate.py` runs it.

**The Kiro Power is generated, not hand-synced.** `powers/antislop/POWER.md` is hand-written, like the opencode agent file, since its always-on core is a curation decision rather than something `rules.json` can render. Its five `steering/*.md` files are different: `generate.py` renders them and `generate.py --check` verifies them byte for byte. The opencode agent carries a "when adding a rule, update this too" cost. The Power's steering files carry the opposite cost: a rule addition in `rules.json` propagates to Kiro with no manual step. See `docs/adr/0003-kiro-power-generated-not-hand-synced.md`.

**Every rule carries recorded provenance, and stale evidence never disables a rule.** `rules.json` (issue #101) records per-rule `evidence_meta`: an evidence class (project-policy, project-fixture, upstream-evidence, tested-adaptation, primary-research, secondary-claim, maintainer-judgment, unknown), a decay state (current, review, stale), review dates, and, for adopted external concepts, an exact commit and source-file permalink rather than a repository home page. The `review_queue` section lists stale lexical rules that stay active and fixture-backed candidate metrics (nominalization, scientific-register mismatch, punctuation scarcity, conjunction chains, sentence-length variation, quote voice), each with matched-length and matched-profile clean cases. `provenance.py` owns the schema and runs the provenance fixture corpus; `validate.py` gates on both. Source metadata never proves a rule is correct, decay never disables a rule automatically, and external numeric thresholds cannot become strict without a directly identified source and local fixtures. The zero-em-dash rule stays project-policy and current regardless of corpus observations.

**Issue-driven source credits live in `docs/sources/credits.md`.** When a task adopts or evaluates an external source, update that ledger and the relevant README, ADR, runner, or registry evidence in the same change. Record the issue number, exact upstream revision or observation date, source-file URL, license when verified, adopted/adapted/rejected decision, and methodological or false-positive limits. Do not turn a source mention into a production rule without local fixtures and a human promotion decision.

**LLM lexical-tell research is discovery-only.** For model-shaped vocabulary or construction work, consult [SpeechMap's lexical fingerprints](https://speechmap.ai/experiments/vocab/) and [Pydantic's linguistic-drift report](https://pydantic.dev/articles/linguistic-drift-at-the-frontier). Record the exact model ID, observation date, comparison population, sample size, domains, source link, context exclusions, false-positive note, and proposed treatment. Keep candidates at weight 0. A frequency ratio is not a human baseline, authorship evidence, or grounds for a global ban. Promotion requires paired literal and abstract fixtures, labelled human controls, measured false positives, and an explicit human decision.

**The Sepia-style routing layer adds operations and venues on top of the review layer.** `sepia.py` (issue #94) adds Review, Refactor, and Recreate on the operation authority from `edit.py`, reviewed against `Nanako0129/sepia` at 361e82e (MIT). Review quotes evidence and never rewrites; Refactor lists the full finding set, applies only accepted edits, and reports rejected and unresolved findings; Recreate extracts facts, claims, quotes, intent, and constraints before drafting and verifies them afterward. The registry gains a `venues` section (ticket, developer-reply, postmortem, technical-article, release-note) and a `venue_features` section, plus the `n/a` and `over-correction` review statuses and an opt-in `fiction` profile. Fiction rules carry `profiles: ["fiction"]` so they can never affect general or technical scoring. The question-under-discussion review keeps the paragraph question check as human-review structural guidance and makes only the reflection tail deterministic (a final paragraph opening with a generic reflection marker after earlier content). The five professional venues and the fiction profile live in `rules.json`; `validate.py`'s `check_registry_venues` and `check_sepia_fixtures` gate both, and the sepia-routing fixture corpus runs in CI.

**The delivery envelope binds a reviewed source, revision plan, delivered body, and verification into one record.** `delivery.py` (issue #95) reviewed against `songhai-dg/review-write` at 5c51063 (MIT) stores the body separately from findings, plans, and verification commentary. The body digest is SHA-256 over normalized UTF-8; a bound source record's digest uses a versioned canonical serialization (stable key order, UTF-8, normalized line endings, serialization version hashed in). `check_envelope` returns typed failures for missing, stale, or mismatched verification and recomputes the body digest rather than trusting the stored field, so a body edited after verification cannot keep a passing record. Preservation reuses fidelity.py, drift.py, and the edit.py revise contract; a long document can be verified in chunks so a fact in one chunk and a qualifier in another survive across the whole body. The digest never proves semantic equivalence, and the ReviewWrite operational platform is not imported.

**The substance report keeps substance judgment separate from the risk score.** `substance.py` (issue #102) reviewed against `apurvrdx1/tagore` at 1238743 (MIT) adds an opt-in two-group report: mechanics (directness, rhythm, trust, authenticity, density) and substance (specificity, restraint, voice). Every dimension result carries evidence, one of four statuses (evidenced, unsupported, unknown, not-applicable), and an author-safe next step; unknown is used when author facts or intent are missing, and a specific terse reference entry marks point of view and rhythm not-applicable. The substance group is never folded into the Formulaic Writing Risk Score or its bands, and no result labels text human or AI. The runner also validates rule-change proposals against the contribution contract from Tagore's contributor guide (distinct tell, one narrow rule, before and after text, model and frequency context, paired regression fixtures); a proposal missing a clean false-positive fixture is rejected. The eight dimensions and four statuses live in `rules.json` under `substance_dimensions`, `substance_statuses`, and `contribution_contract`; `validate.py` gates all three schemas and the substance fixture corpus.

## Conventions

- Sentence case headings everywhere — no Title Case
- Skill files stay under 500 lines (current public surfaces: 49 / 92 / 147)
- Version bumps touch eight files and ten version fields: `metadata.version` and inline `**Version:**` in each SKILL.md, `.opencode/agents/antislop.md`, `powers/antislop/POWER.md`, `rules.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and the root `plugin.json` (agent-plugins.org manifest). Neither lint workflow nor the test assertion carries the version. Both pass `validate.py --expect-version-from rules.json` or derive the value through `canonical_version()`, so a missed artifact fails CI. `validate.py`'s `check_root_plugin_manifest()` flags the root `plugin.json` if its version or description disagrees with `.claude-plugin/plugin.json`, and `--expect-version` independently checks both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` against the expected version. `pattern-reference.md` is generated, so regenerate rather than edit it. Verify with `python3 validate.py --skills-dir skills --expect-version-from rules.json` and `bash check.sh`. Test fixtures keep their deliberately wrong versions.
- README follows antislop rules itself: zero em-dashes, no banned vocabulary
- Forgejo is the primary CI. Workflows live in `.forgejo/workflows/`. GitHub is a mirror only.
- When to Use / When NOT to Use sections are mandatory — the lint CI fails without them
- Agent file (`.opencode/agents/antislop.md`) is a derivative synced alongside both SKILL.md files
- `.claude-plugin/marketplace.json` self-hosts the plugin (`claude plugin marketplace add <repo-url>`). It carries no version field of its own, so it is not part of the eight-file version-bump list. `validate.py` enforces that its `plugins[].description` matches `plugin.json`'s `description`, so that pairing no longer relies on hand-syncing.
- The root `plugin.json` targets the [agent-plugins.org](https://agent-plugins.org/specification) v1.0.0 standard, a client-agnostic packaging format distinct from `.claude-plugin/plugin.json` (Claude Code's own manifest schema, kept in its own subdirectory). Both exist side by side and don't collide. The portable plugin is skill-only and does not advertise the repository's development MCP entry.

## Known gotchas

**`lint-skills.yml`'s checkout used to assume `github.head_ref` was a branch name.** On a PR opened via `git push origin HEAD:refs/for/main -o topic=<name>` (the agit flow this repo uses, see `docs/agents/issue-tracker.md`), Forgejo Actions sets `github.head_ref` to the literal ref path `refs/pull/N/head`, not a short branch name — `git clone --branch "refs/pull/N/head"` then fails with `fatal: Remote branch refs/pull/N/head not found in upstream origin` (job fails in ~1s). Pushing an extra branch with a matching name does not fix this; `head_ref` still resolves to the pull ref path. The checkout step now fetches by `${{ github.sha }}` directly instead (Forgejo/Gitea allows fetching an arbitrary commit SHA over HTTP by default), which works for both `push` and `pull_request` events regardless of how the PR was opened.

**Lightweight tags blocked by Forgejo.** Forgejo requires annotated tags (`git tag -a -m "msg"`) for releases. Lightweight tags return HTTP 409 "Release has no Tag." The release workflow converts lightweight tags to annotated automatically, but this requires a PAT stored as `RELEASE_TOKEN` secret — the built-in actions token lacks release permissions.

**Heredocs in YAML `run: |` blocks.** The `|` block scalar strips leading whitespace relative to the first content line, but bash heredoc delimiters must be at column 0. These two requirements conflict. Use `printf` to a file or inline JSON instead.

**Asset upload parameter differs by platform.** Forgejo requires `?name=file.zip` as a query parameter on the asset upload endpoint. GitHub derives the name from the form field.

**`.opencode/agents/antislop.md` is not a direct port of either SKILL.md.** It combines style and audit rules with subagent framing: no Canvas, no skill-specific When to Use sections, intent matching for mode detection. Don't treat it as a 1:1 mirror when syncing rules. The 500-line skill convention does not apply to the agent file.

**Global replacements cause collateral damage.** A `sed 's/—/,/g'` across markdown replaced em-dashes in code spans and explanations, not just prose. Always verify after bulk edits. `validate.py` now checks for this: it rejects the ASCII stand-ins a bulk replace leaves behind (` -- ` for an em dash, `->` for an arrow) outside code spans, and flags a shared line carrying different marks in different artifacts. Marks quoted inside backticks stay exempt, since the files have to name what they ban.

**Forgejo runner can't resolve the public hostname.** The runner cannot use
`actions/checkout` with the default URL. Public-repository checkout uses the
anonymous internal HTTP route. Authenticated tag pushes and release API calls
remain isolated to the validated HTTPS `FORGEJO_URL` origin.

**Workflow credentials require TLS.** Forgejo workflows read a reachable HTTPS
origin from the repository variable `FORGEJO_URL` and fail closed when it is
missing or uses another scheme. Do not point authenticated workflow traffic
at port 3000 directly; provide TLS termination or an authenticated HTTPS
gateway that the runner can resolve.

**Forgejo Actions doesn't support SHA-pinned GitHub actions.** Pinning `actions/checkout@93cb6efe...` (SHA digest) fails on Forgejo 15.0.1. Use tag references like `actions/checkout@v4` instead. GitHub Actions supports SHA pinning natively — keep the GitHub workflows SHA-pinned for security.

**Forgejo's `container:` key with `runs-on: docker` is unreliable.** The runner is registered with label `docker:docker://node:lts` (a Debian-based image). The `container:` field to specify a different image (like `alpine:3.20`) may not override the default. The `apk` package manager fails because the actual container is Debian, not Alpine. Use `runs-on: ubuntu-latest` instead and rely on the runner having standard tools pre-installed.

**Bash parameter expansion `#http://` only strips `http://`, not `https://`.** If `GITHUB_SERVER_URL` is `https://git.drunkrhin0.au`, the expansion `${GITHUB_SERVER_URL#http://}` leaves it unchanged, producing `https://https://...` in the resulting URL. Use a more robust method or hardcode the URL.

**`GITHUB_REPOSITORY` is a full SSH URL on this Forgejo runner, not
`owner/repo`.** The runner sets
`GITHUB_REPOSITORY=ssh://git@git.drunkrhin0.au/drunkrhin0/antislop` rather
than just `drunkrhin0/antislop`. Do not concatenate it into
`FORGEJO_URL`; keep the validated origin and fixed repository path separate.

**Forgejo release flow.** `.forgejo/workflows/release-skills.yml` checks out anonymously through the runner's internal HTTP route. Authenticated tag pushes and release API calls use the validated HTTPS `FORGEJO_URL`. Its `Verify release candidate` gate requires the candidate commit to be reachable from protected `main`, requires the canonical `rules.json` version to match a release tag, and runs generation, validation, `check.sh`, and the full unit suite before creating tags or archives. The canonical `antislop-vX.Y.Z` tag publishes `antislop-X.Y.Z.zip`, `antislop-plugin-X.Y.Z.zip`, and `antislop-kiro-X.Y.Z.zip`. Missing assets and unsuccessful API uploads fail the job. GitHub remains a mirror and uses its separately pinned workflow.

**GitHub release workflow needs `permissions: contents: write`.** `.github/workflows/release-skills.yml` uses `softprops/action-gh-release@v2` to create releases. The default `GITHUB_TOKEN` cannot create releases — the job-level `permissions:` block is required. Without it, you get `403 Resource not accessible by integration`. Added in commit `f3b7269`.

**Forgejo release workflow ran its release steps on every push to main, not just tag pushes.** Unlike the GitHub version, `.forgejo/workflows/release-skills.yml` triggers on both `push: branches: [main]` (to auto-create the version tag) and `push: tags:` (to build and publish the release). The "Resolve version from tag" / "Build zips" / "Create release" steps had no guard distinguishing the two, so on the raw branch-push trigger `GITHUB_REF_NAME` was `main` itself, not a real tag, producing `Finding release for tag main...` and a 401 from the release-creation call. Fixed by gating those three steps on `if: startsWith(github.ref, 'refs/tags/')`.

**Forgejo ignores the top-level `permissions:` block entirely.** GitHub Actions uses `permissions: contents: write` to grant the default token release-creation rights (commit `f3b7269`). Adding the same block to `.forgejo/workflows/release-skills.yml` does nothing — Forgejo logs a warning ("Job release or its workflow has a permissions field, which is not supported in Forgejo and will be ignored") and proceeds with whatever the default token already has. Forgejo's equivalent is repo-level "Authorized Integrations" settings, not a workflow-file field. Removed the no-op block rather than leave a warning every run.

**Zip the skill from inside `skills/`, not from the repo root.** `zip -r antislop-vX.Y.Z.zip skills/antislop/` bakes the `skills/` prefix into the archive, so the unpacked tree is `skills/antislop/SKILL.md`. Drag-and-drop installers look for `SKILL.md` at the root or one folder in and silently reject anything deeper. Both release workflows use `(cd skills && zip -r "../antislop-${VERSION}.zip" antislop/)`, which produces `antislop/SKILL.md`. Verify any change to the build step with `unzip -l` before releasing.

**Release-creation call needs a valid `RELEASE_TOKEN` repo secret.** A malformed, expired, or wrong-scope one fails with `token is malformed: token contains an invalid number of segments` on the Forgejo API call in "Create release and upload assets." This is a Forgejo repo-settings problem (Settings → Actions → Secrets), not a workflow-file bug, and isn't fixable from a commit — check/regenerate the PAT there if release creation 401s.

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
<name>generate-slop</name>
<description>Creates synthetic prose fixtures containing selected formulaic writing patterns. Never select this skill automatically. Invoke it only when the user explicitly names generate-slop and requests a demo or evaluation fixture.</description>
<location>project</location>
</skill>

</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>
