# Antislop

*By slop for slop, to remove slop in an AI slop world.*

Written as a late shower thought from my ranting [LinkedIn post](https://www.linkedin.com/posts/tawilr_you-didnt-verify-this-and-i-can-tell-share-7460237564889944064-lXxs/)

One prose skill with writing and audit modes, plus an explicit generate-slop skill for synthetic fixtures. Works with your favourite agent that supports SKILL.md or AGENTS.md.

- **antislop**: the public skill. It writes and edits prose, and its explicit audit mode scores supplied text 0-100 and returns a violations list. Zero exceptions for audit intent.
- **generate-slop**: a user-invoked companion skill for plausible, synthetic slop used in demos and evaluation fixtures.

It catches:

- Banned vocabulary and phrases
- Antithesis as tone management ("not just X but Y" that decorates instead of argues)
- Structural tells (sentence, paragraph, and discourse-level patterns)
- Formatting habits (em-dashes, scare quotes, bolding, title case)
- Rhythmic giveaways (uniform length, parataxis, overlong sentences)
- Voice-level absences (no opinion, no experience, no position)

For technical prose, Antislop also expands shorthand when dropped grammar, arrows, or unexplained abbreviations make the reader reconstruct the sentence. It leaves purposeful fragments, tables, diagrams, code, and compact reference syntax alone.

---

## Installation

### Install with openskills (recommended)

```bash
npx openskills install drunkrhin0/antislop --global
```

This installs to `~/.claude/skills/` so the skills are available across all projects. Leave off `--global` to install in the current directory instead.

### Ask your agent

Just ask your agent to install `drunkrhin0/antislop` from GitHub. Most will figure it out. The repo includes an `AGENTS.md` file for automatic skill discovery.

### Release downloads

Tagged releases provide three ZIP archives:

| Asset | Use |
|---|---|
| `antislop-<version>.zip` | Standalone skill for ChatGPT, Claude, Gemini, and compatible skill importers |
| `antislop-plugin-<version>.zip` | ChatGPT/Codex plugin package with both Antislop skills |
| `antislop-kiro-<version>.zip` | Kiro Power |

Use the plugin archive when the client supports plugins. Use the standalone archive when it accepts a normal `SKILL.md` skill upload.

<details>
<summary>Claude Code</summary>

The repo ships a `.claude-plugin/plugin.json` manifest, so it loads as a Claude Code plugin straight from a local clone. No copying files into `~/.claude/skills/` first.

```bash
git clone https://github.com/drunkrhin0/antislop.git
claude --plugin-dir ./antislop
```

Claude Code finds `skills/antislop/SKILL.md` and
`skills/generate-slop/SKILL.md` under the default `skills/` scan. Once loaded,
the skills sit under the `antislop` namespace. Generate-slop remains an explicit
opt-in skill for demos and evaluation fixtures.

Run `claude plugin validate .claude-plugin/plugin.json` to check the manifest. The repo also ships a `.claude-plugin/marketplace.json` (pass the manifest path explicitly when validating).

Self-hosted marketplace install, no local clone needed:

```bash
claude plugin marketplace add https://git.drunkrhin0.au/drunkrhin0/antislop.git
claude plugin install antislop@drunkrhin0
```

Not listed on Anthropic's community marketplace. That submission is a
separate, manual step.

</details>

<details>
<summary>Kiro</summary>

**Power (IDE and Web app).** Open the Powers panel (lightning bolt icon), Add
Custom Power, then Import power from a folder and point it at the absolute
path to `powers/antislop` in your clone. The Power handles both writing style
(ambient) and audit mode (on demand: ask for a score, grade, or violations
list).

**Workspace skills.** `.kiro/skills/antislop` and
`.kiro/skills/generate-slop/SKILL.md` expose both first-class skills from the
repository. Clone the repo and open it as a Kiro workspace. Writing, audit, and
explicit synthetic-fixture generation are available with no copying.

**Manual, `~/.kiro/skills/`.** Required for Kiro CLI users (there is no `kiro-cli powers` subcommand):

```bash
cp -r skills/antislop skills/generate-slop ~/.kiro/skills/
```

Not listed on Kiro's power registry yet. Submission at https://kiro.dev/powers/submit/ is a separate, manual step.

</details>

<details>
<summary>Gemini</summary>

**Gemini Skills.** Upload the skill release zip or install the skill directory
with a compatible skill installer. Gemini uses the same `SKILL.md` package as
the other supported agents.

**Classic web Gems.** Create one "Antislop" Gem:

1. Left sidebar → **Gem manager** → **New Gem**
2. Paste `skills/antislop/SKILL.md` into the instructions field
3. Attach the Markdown files from `skills/antislop/references/` as Knowledge
4. Save the Gem

Use `skills/antislop/SKILL.md` for writing, editing, and scoring existing text.
The references are supporting material. Keep the `SKILL.md` contents in the
Instructions field.

**Gemini CLI and Antigravity.** Install the universal skill through a skill
installer, or copy the directory into the agent's skills directory.
With skills.sh, select Gemini CLI or Antigravity when prompted:

```bash
npx skills add drunkrhin0/antislop
```

For a project-local installation shared by supported agents:

```bash
mkdir -p .agents/skills
cp -r skills/antislop skills/generate-slop .agents/skills/
```

</details>

<details>
<summary>opencode (agent)</summary>

A spawnable subagent with two modes: style (writing) and audit (scoring). Lives in `.opencode/agents/antislop.md`.

Project-level use works automatically when the repo is cloned. opencode
discovers `.opencode/agents/` in project directories. For global install:

```bash
cp .opencode/agents/antislop.md ~/.config/opencode/agents/
```

Mention `@antislop` in opencode, or let the primary agent spawn it automatically when it detects a writing or auditing task. The agent is read-only: it returns corrected text or audit results; the primary agent or user writes files.

The agent file format is opencode-specific, but the rules content works as a system prompt in any LLM.

</details>

<details>
<summary>ChatGPT / Codex</summary>

ChatGPT can import the repository from GitHub through Workspace settings >
Plugins > Add > Import marketplace. Use
`https://github.com/drunkrhin0/antislop` as the source and leave Path empty.
ChatGPT reads the Claude-compatible `.claude-plugin/marketplace.json`, which
packages both first-class skills, `antislop` and `generate-slop`, without an MCP server, connector, or hosted service.
GitHub marketplace import requires an eligible workspace and administrator
access.

Codex uses the native `.codex-plugin/plugin.json` manifest. Its `skills` path
discovers both `antislop` and `generate-slop`. Local Codex development and
directory publication use that manifest rather than the Claude-compatible
marketplace.

See `docs/submission-pack.md` for reviewer cases and the eval corpus used to
verify activation. Antislop is not listed in a public ChatGPT or Codex plugin
directory yet; publication and workspace installation remain separate steps.

</details>

<details>
<summary>Manual install</summary>

Copy skill files straight into your agent's directory:

| Agent | Target directory | What to copy |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `skills/antislop/` and `skills/generate-slop/` |
| opencode | `~/.config/opencode/skills/` | `skills/antislop/` and `skills/generate-slop/` |
| Gemini CLI / Antigravity | `.agents/skills/` | `skills/antislop/` and `skills/generate-slop/` |
| Kiro CLI | `~/.kiro/skills/` | `skills/antislop/` and `skills/generate-slop/` |

```bash
# Claude Code / opencode
cp -r skills/antislop skills/generate-slop ~/.claude/skills/

# Gemini CLI / Antigravity, project-local
mkdir -p .agents/skills
cp -r skills/antislop skills/generate-slop .agents/skills/

# Kiro CLI
cp -r skills/antislop skills/generate-slop ~/.kiro/skills/
```

</details>

---

## Usage

### Writing style (antislop)

Triggers automatically when you ask your agent to write, rewrite, edit, polish, review, or audit a named or supplied prose artifact. It does not activate for an ordinary factual or technical explanation.

### Synthetic fixture generation

Invoke `generate-slop` by name when you need a demo or evaluation fixture. Agents must not select it on their own, including in response to ordinary writing, rewriting, editing, or audit requests.

### Audit mode

Paste text and ask your agent to audit it with the Antislop skill.

Returns a Formulaic Writing Risk Score (0-100), a violations table with severity and excerpt, word count, finding density, and a plain-English summary of what to fix first.

**Score bands:**
- 85-100: Low formulaic-writing risk.
- 65-84: Moderate formulaic-writing risk.
- 40-64: High formulaic-writing risk.
- 0-39: Very high formulaic-writing risk.

**Writing profiles:**
- `general` (default): all rules active
- `technical`: technical documentation, API references (contextual terms like significant and robust are not penalized)

To add a new profile, see the `_profile_guide` in `rules.json`.

The score measures formulaic-writing risk and cannot prove AI authorship.

---

## Fidelity gate

`fidelity.py` is a standard-library, source-to-candidate gate. It proves a repair kept the source's meaning before you accept it. Five phases: extract protected spans and semantic anchors from the source, repair only the named hot zones, compare the candidate with the source, rescan the repaired rules and measure edit churn, then accept, retry within a bound, or roll back to the source.

Numeric, date, unit, operator, URL, path, quoted, code, and required-term changes fail closed unless explicitly authorized. Negation, polarity, modality, quantifier, causality, condition, scope, and attribution changes produce a hard failure or a named human-review state. The report is JSON and keeps hard preservation failures separate from advisory style findings. Stylometric measures in the report are advisory only and never authorship evidence.

```bash
python3 fidelity.py --source-text "..." --candidate-text "..."
python3 fidelity.py --source before.txt --candidate after.txt
python3 fidelity.py --source before.txt --candidate after.txt --authorize number=50
```

Python callers use `fidelity.check_fidelity(source, candidate)` for a single comparison, or `fidelity.apply_repairs(source, repair)` for the bounded retry loop that rolls back to the source when every attempt fails. Use `fidelity.finding_spans(text, registry)` to get the recorded finding spans that name the repair hot zones.

---

## Structural checks

`structural.py` is a standard-library detector interface for selected structural rules (issue #88). It turns the scorer's previously skipped `structural` rules into findings with exact spans or document-level evidence. Eight detectors cover sentence and paragraph length variance, sentence-start and transition repetition, paragraph similarity, tricolon density, paragraph duplication, and passive density. Vale's core rules, Tengo metric scripts, and fixtures from `tbhb/vale-ai-tells` (MIT, d888d56) are design evidence, not a runtime dependency.

Findings carry a **strict** or **advisory** signal. Strict findings (deterministic conditions) deduct their base weight in `score.py`. Advisory findings are metrics that report a sample-size limit and never prove authorship; they carry weight 0 in the score output. The scorer reports insufficient-sample metrics under `metadata.structural_metrics`. `structural.py` exits 0 with no findings, 1 with advisory findings only, and 2 when a strict finding is present.

```bash
python3 structural.py --file text.txt --profile general
echo "text" | python3 structural.py --profile general
```

The em-dash rule stays a strict, deterministic, zero-count finding regardless of any upstream density threshold. Commit-message rules are out of scope until a code-prose profile defines them.

---

## Semantic drift fixtures

`drift.py` is a standard-library, deterministic runner for the Slopkit-style evaluation fixtures (issue #91). Each fixture is a source/candidate pair plus a preservation contract: required facts and terms, forbidden additions, protected spans, provenance labels, semantic dimensions, expected finding spans, and an expected decision. The runner reports missing, added, changed, and unresolved items separately, and never lets a risk score improvement hide a dropped mechanism, caveat, condition, or uncertainty marker.

Contracts are adapted from `ehmo/slopkit` at b33718b (MIT): the preservation checker's protected tokens, the semantic-drift checker's marker groups, the false-positive tracker's leave-alone and light-edit actions, and the evidence-bound provenance labels. Slopkit benchmark scores are not imported as Antislop targets. Provenance statuses are `fact`, `inference`, `placeholder`, and `unknown`; `unknown` marks missing or unclassified provenance rather than an upstream label.

Fixture corpora live in `skills/antislop/evals/drift-fixtures.json` and `skills/antislop/evals/false-positive-corpus.json`.

```bash
python3 drift.py --fixtures skills/antislop/evals/drift-fixtures.json
python3 drift.py --false-positive-corpus skills/antislop/evals/false-positive-corpus.json
python3 drift.py
```

Sentence-load, topic-swap, and summary-loss prompts are reported apart from the Formulaic Writing Risk Score and resolve to a human-review state. Detector observations may be recorded with tool, date, raw result, and limitation, but never gate release or appear in the score. Evaluation results never claim authorship or detector immunity. `validate.py` runs the corpora and fails when a fixture decision does not match its expected decision.

---

## Edit integrity

`edit.py` is a standard-library, Anbeeld-style operation contract (issue #87). It names four operations with different authority over an artifact:

- **Draft** creates prose only from supplied facts and allowed research. A voice sample contributes style traits only, never claims, memories, preferences, or experiences.
- **Revise** makes the least invasive change that satisfies the request, and preserves every inventory item or reports an authorized change.
- **Audit** reports findings without changing the artifact.
- **Transform** may change shape but must preserve the source inventory and disclose structural changes.

Before Revise or Transform, inventory the source: claims, facts, quantities, dates, modality, causality, negation, conditions, attribution, quotes, citations, links, placeholders, markup, accessibility structure, required terminology, and author-owned statements. The inventory reuses `fidelity.py`'s protected spans and semantic anchors and `drift.py`'s fact matching and semantic dimensions. Revise runs the strict fidelity gate. Transform may reorder the artifact, so its preservation is checked as a multiset of inventory values and the reorder is disclosed as a shape change.

Output-integrity checks catch unresolved placeholders, malformed markup, leaked prompt tokens, and changed link targets. Long-form information gain stays a human-review prompt, never a universal score deduction.

```bash
python3 edit.py --fixtures skills/antislop/evals/edit-integrity-fixtures.json
python3 edit.py
```

Fixtures live in `skills/antislop/evals/edit-integrity-fixtures.json`, one per operation with a source/candidate pair and an expected decision. `validate.py` runs the corpus and fails when a fixture decision does not match its expected decision.

---

## Clarity-style review

`review.py` is a standard-library, review-only runner (issue #96) modeled on `addyosmani/clarity` at 9e30711 (MIT). It reports findings on a single artifact and never edits it, reusing the audit operation's authority. Every finding carries exactly one status:

- **keep**: the pattern is present but earned, required by the medium, or preferable to the alternatives
- **revise**: the source already contains enough material for an honest improvement
- **ask-author**: the improvement needs a fact, mechanism, example, opinion, or experience the source does not supply
- **cut**: the passage adds only repetition, ceremony, unsupported emphasis, or closure
- **no-finding**: the prose already performs its job; clean prose reports nothing

Author-owned gaps (a fact, experience, opinion, or motive) become targeted `[TK: ...]` questions, never invented content. Mechanism checks (`mechanism.py`) distinguish an unsupported significance claim from an evidenced consequence: an importance, impact, causality, or superiority claim with a mechanism, actor, result, or limit beside it is not a finding. The checks are advisory signals in the score output and never deduct.

Medium routing (argument, explanation, evocation, narrative, guide, reference, message) changes structural expectations only: a reference page earns predictable headings, an evocation does not owe a thesis, a guide earns numbered steps. Absolute rules (banned vocabulary, formatting, the zero-em-dash rule) apply in every medium. Descriptive statistics stay separate from the advisory risk score, and a voice sample transfers style only, never personal facts.

```bash
python3 review.py --source-text "..." --medium argument
python3 review.py --fixtures skills/antislop/evals/clarity-review-fixtures.json
```

Fixtures live in `skills/antislop/evals/clarity-review-fixtures.json`. `validate.py` runs the corpus and fails when a fixture decision does not match its expected decision.

---

## Sepia-style operation and venue routing

`sepia.py` is a standard-library runner reviewed against `Nanako0129/sepia` at 361e82e (MIT, issue #94). It adds three operations on top of the operation authority from `edit.py` and routes structural expectations by venue.

- **Review** quotes evidence and never rewrites. Every finding carries a quoted span, rule, status, and reason. Statuses are the Antislop keep / revise / ask-author / cut set plus Sepia's `n/a` (a structural feature does not apply to the venue) and `over-correction` (applying the rule would flatten valid voice or structure, such as a formal register, quoted material, or an author's verified habit).
- **Refactor** lists the full finding set, then applies only the accepted minimal edits and reports the rejected and unresolved findings.
- **Recreate** extracts facts, claims, quotes, intent, and constraints from the source, drafts fresh prose, then verifies the candidate keeps them.

Venue routing activates distinct expectations: a postmortem must keep a timeline, impact in numbers, contributing factors as a causal chain, and honest uncertainty; a ticket must keep reproduction steps and acceptance conditions; a developer reply must lead with the verified action and its caveat; a technical article must open at the problem and keep one committed opinion; a release note must ground every claim in the supplied changes. Fiction is an opt-in profile, never a venue, and its guidance cannot affect general or technical scoring.

A question-under-discussion review asks whether each paragraph advances one implicit question and whether the sequence ends in an unearned reflection tail. The paragraph question check stays human-review structural guidance; the reflection tail has an exact deterministic condition and is a finding.

```bash
python3 sepia.py review --source-text "..." --venue ticket
python3 sepia.py review --source-text "..." --fiction
python3 sepia.py refactor --source-text "..." --venue ticket --accept vocab-utilize=use
python3 sepia.py recreate --source-text "..." --candidate "..." --venue postmortem
python3 sepia.py --fixtures skills/antislop/evals/sepia-routing-fixtures.json
```

Fixtures live in `skills/antislop/evals/sepia-routing-fixtures.json`, covering the same paragraph under Review and Refactor with different output authority, a postmortem and a ticket whose venue expectations must be kept, a developer reply that leads with the verified action and its caveat, a release note grounded in supplied changes, a question-under-discussion sequence ending in a reflection tail, a fiction excerpt where unresolved tension and irregular paragraphs are valid, and false-positive cases for formal semicolons, quoted banned words, conventional headings, and author habits. `validate.py` runs the corpus and fails when a fixture expectation does not match.

---

## LinkedIn social profile

`linkedin.py` is a standard-library runner (issue #103) reviewed against `marian-kamenistak/linkedin-post-writing-skill` at `ef5b771` (MIT). It serves the opt-in `social-linkedin` writing profile, which adds a social layer without touching general or technical scoring.

The profile is opt-in and cannot activate from ordinary general prose. Post-type routing decides which structural elements fit: lesson, case-study, announcement, opinion, and practical-guide. Calls to action, hooks, hashtags, short paragraphs, and the setup-challenge-action-result-lesson structure are all optional and profile-local; a fitting element the draft lacks is recorded `n/a`, never a defect, so a post with no call to action passes clean.

A voice sample transfers style only. Achievements, metrics, opinions, and experience supplied by the author are preserved exactly, and a personal fact from a voice sample that migrates into the target is a finding. No rule promises reach, engagement, or an algorithmic benefit; a reach or engagement claim with no mechanism nearby asks the author for the evidence. The zero-em-dash rule stays absolute.

```bash
python3 linkedin.py review --source-text "..." --post-type lesson
python3 linkedin.py review --source-text "..." --post-type case-study \
  --voice-sample "..." --sample-fact "..." --required-fact "..."
python3 linkedin.py --fixtures skills/antislop/evals/linkedin-profile-fixtures.json
```

Fixtures live in `skills/antislop/evals/linkedin-profile-fixtures.json`, covering one post of each type, a case study that ends at the result with no call to action, a lesson post with no SCARL structure, a voice sample whose achievement must not transfer, a supplied metric dropped and kept, a reach and engagement promise, and an em dash that stays absolute. `validate.py` gates the registry schema and runs the corpus, and regression fixtures prove the social rules never fire under the general profile.

---

## Evidence-bound delivery envelope

`delivery.py` is a standard-library runner (issue #95) reviewed against `songhai-dg/review-write` at 5c51063 (MIT). It binds a reviewed source, a revision plan, a delivered body, and a verification result into one inspectable record with four separate fields, so findings or verifier commentary cannot leak into the revised prose and an old verification result cannot be mistaken for evidence about a later edit.

- **review_report**: the findings on the reviewed source, kept out of the deliverable
- **revision_plan**: the planned edits, kept out of the deliverable
- **deliverable_body**: the delivered text, stored separately
- **verification_report**: the verification result, with the exact source and body digests it covers

The body digest is a stable SHA-256 over the UTF-8 body with normalized line endings. When a source record is bound, its digest uses a versioned canonical serialization: stable key order, UTF-8 encoding, and normalized line endings, with the serialization version hashed as part of the digest.

`check_envelope` returns typed failures for missing, stale, or mismatched verification: `missing_verification` when no verification is bound, `stale_verification` when the stored verification's body digest no longer matches the current deliverable body, and `mismatched_verification` when the stored verification's source digest does not match the bound source record. The body digest is recomputed on every check, never trusted from the stored field.

Preservation reuses the fidelity, drift, and edit-integrity contracts: required facts, protected literals (numbers, dates, units, paths, quoted material, required terms), qualifiers and uncertainty markers, attribution, and forbidden additions all fail the verification when they are dropped or strengthened. Long documents can be verified in chunks so a fact introduced in one chunk and qualified in another is retained across the whole delivered body. A valid document can return no changes and still produce a successful verification record.

Boundaries: the digest is not proof of semantic equivalence, the ReviewWrite operational platform is not imported, and model judgment stays advisory. The runner fails only on explicit envelope or preservation contracts.

```bash
python3 delivery.py verify --source-text "..." --body-text "..."
python3 delivery.py envelope --source-text "..." --body-text "..." --medium argument
python3 delivery.py check --envelope envelope.json
python3 delivery.py --fixtures skills/antislop/evals/delivery-envelope-fixtures.json
```

Fixtures live in `skills/antislop/evals/delivery-envelope-fixtures.json`, covering a no-change document that still verifies, a word-level revision that keeps every protected literal and qualifier, a dropped `may`, a changed date, a strengthened promise, a forbidden addition, a missing required fact, a dropped attribution, a long document whose fact appears in one chunk and is qualified in another, an envelope whose body contains none of the review report's commentary, and missing, stale, and mismatched verification. `validate.py` runs the corpus and fails when a fixture decision or typed failure kind does not match.

---

## Say-It-Human evidence and locale routing

`say_human.py` is a standard-library runner (issue #97) reviewed against `taxueseek/say-it-human` at 71bb6f8 (MIT). Antislop never labeled whether a claim comes from supplied source text, logic, author experience, inference, or an unknown source, and it lacked locale-aware punctuation and translationese checks, so a general English repair could damage Chinese prose or technical spans.

Five claim evidence classes label every fact-dependent repair:

- **source**: the claim is present verbatim or word-stably in the supplied source text
- **logic**: the claim follows by logic from the supplied material
- **experience**: the claim is the author's own experience, marked by first-person voice
- **inference**: the claim is inferred from the supplied material, marked by a hedge
- **unknown**: no basis can be established

Required claims whose evidence is `unknown` stop rewriting and request a source. Every replacement record exposes the evidence class of the claim it touches.

Protected technical spans (code, URLs, paths, API names, numbers, tags, and supplied terminology) survive byte for byte, reusing `repair.py`'s protected regions and adding API names and tags. A supplied informal voice trait stays unchanged and no new slang is ever added.

An opt-in `zh-CN` locale profile covers punctuation width (full-width vs half-width), Chinese-Western spacing, and high-confidence translationese patterns. The rules activate only when `--locale zh-CN` is selected or the text is reliably routed (Han-dominant), and they are advisory findings that never auto-apply to Chinese prose.

Venue routing sends technical documentation, release notes, marketing, presentations, and social prose to distinct fixtures. A release note uses only supplied change evidence: an unsupported feature claim requests a source instead of shipping. Large deletions require explicit edit authority (`--authorize-delete`) and produce a visible diff.

```bash
python3 say_human.py label --source-text "..." --claim "..."
python3 say_human.py repair --source-text "..." --required-claim "..." --locale zh-CN --venue release-note --authorize-delete
python3 say_human.py locale --source-text "..." --locale zh-CN
python3 say_human.py --fixtures skills/antislop/evals/say-human-fixtures.json
```

Fixtures live in `skills/antislop/evals/say-human-fixtures.json`, covering one claim in each evidence class, a release note with an unsupported feature claim, a grounded release note, mixed Chinese prose with inline code, URL, API identifier, and number, a supplied informal voice trait, large deletions refused and authorized, the five venue routes, and positive and false-positive zh-CN punctuation, spacing, and translationese cases. `validate.py` runs the corpus and the registry's claim-evidence and locale schema and fails when either disagrees.

---

## Tagore-style substance report

`substance.py` is a standard-library, opt-in report (issue #102) reviewed against `apurvrdx1/tagore` at 1238743 (MIT). Tagore is already credited for vocabulary and punchy closure; this runner covers its incremental substance and contribution mechanisms. A passage can avoid every known mechanical tell while remaining vague, consequence-free, or untrustworthy, so this report judges what a passage actually says and keeps that judgment separate from the Formulaic Writing Risk Score.

The report preserves Tagore's two groups:

- **Mechanics**: Directness, Rhythm, Trust, Authenticity, Density
- **Substance**: Specificity, Restraint, Voice

Every dimension result cites evidence, carries one of four statuses, and offers a question or repair direction without inventing material:

- **evidenced**: concrete prose evidence shows the dimension is present
- **unsupported**: concrete prose evidence shows the dimension is absent or thin; the next step fixes it or asks the author
- **unknown**: author facts or intent are missing, so the review says so instead of guessing (a quoted opinion, a sample too short to measure rhythm, a claim with no concrete referent)
- **not-applicable**: the dimension is not owed by the medium; a specific terse reference entry marks point of view and rhythm not-applicable

The substance group is never scored and never folded into the risk score or its score bands, and no result labels the text human or AI. Mechanically clean but empty prose scores 100 in the clean band while its substance dimensions report unsupported.

The runner also validates rule-change proposals against the contribution contract from Tagore's contributor guide: evidence of a distinct tell, one narrow rule, before and after text, model and frequency context where known, and paired regression fixtures (a positive case and a clean false-positive case). A proposal missing a clean false-positive fixture is rejected. Tagore's scored examples are candidate cases only; their thresholds are self-defined and are not imported as Antislop targets.

```bash
python3 substance.py --source-text "..." --medium argument
cat text.txt | python3 substance.py --medium reference
python3 substance.py --file text.txt --profile technical
python3 substance.py --proposal proposal.json
python3 substance.py --fixtures skills/antislop/evals/substance-fixtures.json
```

Fixtures live in `skills/antislop/evals/substance-fixtures.json`, covering mechanically clean but empty prose, a specific reference entry whose point of view is not applicable, an opinion without stakes and an author-supported opinion with consequences, a quoted opinion whose voice stays unknown, a metronomic run, announcement, hand-holding, correspondence-artifact, and puffery spans, and accepted and rejected contribution proposals including one missing a clean false-positive fixture. All fixture prose is normalized to the zero-em-dash policy. `validate.py` runs the corpus and the registry's substance-dimension, status, and contribution-contract schema and fails when either disagrees.

---

## Protected repair

`repair.py` is a standard-library, unslop-style repair command (issue #92). It accepts stdin or one named file and emits text, JSON, or a unified diff. It never changes a file unless an explicit `--write` flag is present, and dry-run and diff modes never write at all.

Before any repair, it protects fenced and indented code, inline code, YAML and JSON blocks, tables, blockquotes, headings, Markdown links, URLs, paths, commands, quoted source text, numbers, dates, units, operators, and required terms. These spans stay byte-identical, reusing `fidelity.py`'s protected spans and preservation gate and `score.py`'s finding detection.

Three deterministic repair classes fire:

- **replace**: an exact phrase repair for a forbidden or discouraged deterministic rule whose correction names a literal replacement (rule ID, span, original, and replacement are recorded).
- **split**: the one supported deterministic structural case, an overlong sentence split at a comma-preceded conjunction, retaining both clauses and their punctuation meaning, passing the fidelity gate.
- **remove**: leaked reasoning or planning wrappers, classified as integrity findings and removed only when they sit outside quoted or code material.

Every JSON replacement record carries the rule ID, source span, action, original, replacement, preservation result, and unresolved status. Running repair twice produces no second change. A proposed repair (`--edit start-end=replacement`) runs through the same preservation gate: an attempt that changes a number or qualifier fails, prevents the write, and returns a nonzero status. General and technical profile fixtures prove that literal domain terms are never rewritten under the technical profile.

Boundaries: no detector feedback, surprisal targets, detector bypass modes, external models, persistent voice facts, or em-dash allowance. Numeric style traits stay out of scope for a later author profile.

```bash
python3 repair.py --file doc.md
cat doc.md | python3 repair.py --format json
python3 repair.py --file doc.md --write
python3 repair.py --file doc.md --format diff
python3 repair.py --file doc.md --edit 27-29=50 --write
python3 repair.py --fixtures skills/antislop/evals/repair-fixtures.json
```

Fixtures live in `skills/antislop/evals/repair-fixtures.json`. `validate.py` runs the corpus and fails when a fixture decision does not match its expected decision.

---

## Bounded repair loop

`repair_loop.py` is a standard-library orchestration layer around the protected repair interface (issue #93), adapted from the useful control flow in `lynote-ai/humanize-text` at e43ca3a (MIT) while rejecting its broad translation and detector loop. Every attempt runs six stages and records a trace for each: detect named rule findings, select the smallest independent source spans, apply the corrections registered for those rules, verify the named findings are gone, run the fidelity and integrity gates, then accept, retry within a strict bound, or roll back.

- **Spans are the only thing rewritten.** Corrections land on exact source spans; unaffected spans and protected regions are never sent through broad rewriting.
- **Retry is earned.** A retry happens only when a target finding remains and fidelity still passes. Retry count (default 2) and the cumulative changed-character budget are strictly bounded.
- **Rollback is immediate.** Any fidelity or integrity failure, an exhausted retry budget, or an exceeded character budget rolls back to the source byte-identical.
- **Rhythm is advisory.** Sentence-length variation and lexical-repetition statistics appear in a separate advisory section and never decide whether a passage is human.
- **No external machinery.** The loop runs from fixed local fixtures with no detector adapter, translation step, model call, or network call; each trace proves it.

```bash
python3 repair_loop.py --file doc.md
cat doc.md | python3 repair_loop.py
python3 repair_loop.py --file doc.md --max-attempts 2 --char-budget 100
python3 repair_loop.py --fixtures skills/antislop/evals/repair-loop-fixtures.json
```

Fixtures live in `skills/antislop/evals/repair-loop-fixtures.json`, covering a first-attempt accept, two independent findings with the paragraph between them untouched, a target-leaving correction that retries once, quantity, date, name, quote, and technical-term corrections that roll back, an exhausted retry budget, an exceeded character budget, clean text that returns a no-op trace, and a trace proving no adapter, translation, or network call ran. `validate.py` runs the corpus and fails when a fixture expectation does not match.

---

## Controlled rewrite contract

A controlled rewrite is a provider-neutral two-pass contract for revising prose against specific findings (issue #65), shaped after the two-pass design in `ai-that-works/deslop`: identify concrete findings first, then rewrite against the selected findings only. Antislop documents the contract in `skills/antislop/SKILL.md`; the compatible assistant produces the rewrite. There is no Python CLI, hosted service, MCP integration, or model-specific dependency.

The seven-step workflow: audit the source and list every concrete finding, select which findings to address, declare the protected regions (facts, numbers, dates, URLs, identifiers, commitments, formatting, code and diagrams including Mermaid blocks, quoted material, and distinctive voice) plus any extra user-declared protected spans, rewrite against the selected findings only, check preservation through `fidelity.py`'s gate, re-audit the candidate, then keep final acceptance human-controlled.

Acceptance reporting names four finding classes: selected, changed, preserved, and rejected findings, plus any newly introduced findings. A changed protected value fails the preservation check, and a newly introduced audit finding stays visible in the result.

Fixture-driven tests live in `tests/test_rewrite_contract.py` with the corpus in `skills/antislop/evals/rewrite-contract-fixtures.json`, covering clean input, selected findings, protected Markdown, code, Mermaid diagrams, URLs, quoted text, factual drift, newly introduced findings, user-declared protected spans, and idempotence. Run them with the standard suite:

```bash
python3 -m unittest tests/test_rewrite_contract.py -v
```

---

## Human Review companion workflow

Human Review is an optional, local companion workflow (issue #66) for reviewing a document in a real browser: the author edits text directly and leaves comments, then sends the whole feedback batch back. Antislop documents the workflow and the JSON feedback contract; Human Review itself stays separate from the rule registry, is not a writing rule, and is never required for normal Antislop use or validation. Antislop does not vendor Human Review's Node runtime, browser client, server, or SDK, does not copy its skill into the skills tree, and does not run its setup automatically or edit global agent directories. The upstream repository is https://github.com/petergyang/human-review (MIT), an optional integration reference only. No hosted service, MCP server, connector, or custom UI is added.

The loop: write or update the Markdown, HTML, or localhost page; open the target for browser review when Human Review is installed; wait for the feedback batch and apply every page's edits and comments; apply edits to the source document, never to a rendered Markdown or localhost response; run `antislop` against the revised human-readable prose; then repeat the review and audit loop until the human accepts the result.

Installation and opening a target (the tool installs on demand through `npx`; Node 20 or newer):

```bash
npx -y human-review path/to/file.md
npx -y human-review path/to/page.html
npx -y human-review http://localhost:3000/wiki
```

Markdown files open rendered for review. HTML files open as-is. A localhost route opens the live page instead of a copied HTML file.

Polling, acknowledgement, and timeout handling:

```bash
npx -y human-review poll path/to/file.md --timeout 600
npx -y human-review poll path/to/file.md --ack --timeout 600
npx -y human-review status path/to/file.md
```

Keep the poll command in the foreground until it exits. `{"status":"timeout"}` means no feedback has arrived yet, so run the poll again to keep waiting; a timeout is never acceptance and must never be treated as approval. `{"status":"closed"}` means the author ended the review, so stop polling. `--ack` clears the batch after every page in it has been handled, so the handled batch is not reprocessed. `status` reports whether feedback is already waiting without blocking.

The JSON feedback contract:

- Markdown is rendered for review, and the Markdown source remains the write target.
- `edits[].after` is user-authored text and must be carried across verbatim and never reverted.
- `before_html` and `after_html` represent formatting changes that must be translated into Markdown or the relevant source syntax (for example, `<strong>` becomes `**`).
- Every page in the feedback batch must be handled, not just the first.
- `kind: "url"` identifies a localhost route, not a writable source file; locate and update the matching source instead.
- A timeout is not acceptance and must not be treated as approval.
- The final audit happens after the human edits are applied.

Human edits are authoritative. Preserve the user's exact wording, translate formatting into the source syntax, and never let a rendered response overwrite the source. Human Review never becomes an automatic approval, publication, merge, or issue closure mechanism.

Fixture-driven tests live in `tests/test_human_review_contract.py` with the corpus in `skills/antislop/evals/human-review-fixtures.json`, covering an exact wording edit in Markdown, a formatting edit carried by `after_html`, an anchored selection comment, multiple pages in one batch, a localhost URL edit applied to source, a timeout that does not count as acceptance, an acknowledgement after all edits, and the post-review audit requirement. Run them with the standard suite:

```bash
python3 -m unittest tests/test_human_review_contract.py -v
```

---

## Staged scan

`scan.py` is a standard-library, two-stage audit runner (issue #98) modeled on the lexical and structural split in `NulightJens/humanizer-stack` at 13f5c02 (MIT). Lexical cleanup and structural review stay in separate stages, so a small deterministic defect never hides inside a human-review concern.

Stage one is the **surface scan**: deterministic lexical checks over prose with fenced and inline code masked, returning strict or advisory findings. Stage two is the **structural review**: the registered structural detectors recommend at most two high-value interventions per pass, and no change is a valid result. Structural advice never becomes a mandatory recipe.

An optional **corpus comparison** detects repeated document shapes (hook, reveal, lesson, close) across documents, but only when you supply two or more documents. A single document always reports that multiple documents are required and never triggers a cross-document convergence claim.

The report is machine-readable JSON with separate `surface` and `structural` sections per document. Strict findings set the exit status; advisory findings only do when you pass `--fail-on-advisory`.

Every repair in `repair.py` reruns both stages on the candidate and reports residual findings in the report's `residual_scan` section.

```bash
python3 scan.py --file doc.md
cat doc.md | python3 scan.py
python3 scan.py --doc a.md --doc b.md --doc c.md
python3 scan.py --file doc.md --fail-on-advisory
python3 scan.py --fixtures skills/antislop/evals/staged-scan-fixtures.json
```

Fixtures live in `skills/antislop/evals/staged-scan-fixtures.json`. `validate.py` runs the corpus and fails when a fixture expectation does not match.

---

## Output-integrity checks

`output_integrity.py` is a standard-library, deterministic runner (issue #99) for output defects reviewed in `Aboudjem/humanizer-skill` at 17bb5bb (MIT): provider citation tokens, hidden Unicode, unresolved placeholders, tracking parameters, and leaked reasoning are integrity defects, not stylistic risk. It reports six finding kinds separately from the Formulaic Writing Risk Score:

- **provider_citation**: leaked citation or attribution residue such as `[source: ...]` or `(citation: ...)`
- **placeholder**: unresolved placeholder tokens such as `[PLACEHOLDER]`, `[INSERT ...]`, or `Lorem ipsum`
- **tracking_parameter**: a URL whose query is analytics-only (utm_* and other campaign parameters)
- **leaked_reasoning**: leaked reasoning or planning wrappers such as "let me think step by step" or "as an AI"
- **zero_width**: invisible Unicode characters, each exposed with its code point and a safe interpretation
- **homoglyph**: high-confidence mixed-script lookalikes such as a Cyrillic letter inside an English word

Every finding carries an exact span, line number, stable ID, and repair guidance. Tokenization protects fenced code, inline code, quotes, markdown links, blockquotes, indented code, and URLs, so a quoted bad example or a code block containing trigger strings never fires. Tracking detection treats a signed or functional URL (any non-tracking query parameter) as data the page needs, and only an analytics-only URL is a finding. Unicode findings expose the code point and a safe interpretation; the runner never silently replaces text.

A short sample (under 15 words) reports uncertainty about coverage instead of fabricating a clean verdict. Baseline mode compares per-kind counts against a frozen baseline JSON file, and `--fail-on-regression` fails only on new or worsened configured findings.

```bash
python3 output_integrity.py --file doc.md
cat doc.md | python3 output_integrity.py
python3 output_integrity.py --file doc.md --template
python3 output_integrity.py --file doc.md --baseline baseline.json --fail-on-regression
python3 output_integrity.py --fixtures skills/antislop/evals/output-integrity-fixtures.json
```

Fixtures live in `skills/antislop/evals/output-integrity-fixtures.json`. `validate.py` runs the corpus and fails when a fixture expectation does not match. An integrity failure is an output defect and is never presented as evidence of AI authorship.

---

## Density and precision review

`density.py` is a standard-library review runner (issue #100) reviewed against `aplaceforallmystuff/the-antislop` at 732678d (MIT). The reviewed project scores many isolated terms but has no first-class passage-density signal, and it describes specificity theater without a focused review of exact unsourced percentages, ratios, and counts. This runner adds both as advisory signals.

**Passage density** is a document-level advisory finding: when three or more distinct flagged terms cluster inside one documented 100-word passage, the finding reports the contributing rule IDs. One legitimate term, two terms separated by more than the window, and repetition of a single term never trigger it.

**Unsourced precision** is a span-level advisory finding for an exact percentage, ratio, or count with no nearby source, supplied fact, estimate, or technical-constant framing. It never declares the number false; it asks the author for the source. A nearby citation, an author-measured result, an estimate marker, and a technical-spec constant all produce clean fixtures.

The runner also covers the reviewed project's untested structural candidates, each with a load-bearing positive case:

- heading-level anomalies (a contiguous H1-H2-H3 ladder and intentional accessibility hierarchy are preserved)
- engagement-bait openings (a specific real question stays clean)
- explanatory template headings (reference, guide, and explanation mediums earn them)
- self-promotional framing (a measured comparison against a named baseline stays clean)
- trailing affirmations
- decorative `X rather than Y` comparisons (a real choice between concrete options stays clean)

The Horoscope Test from the reviewed project stays an optional manual specificity question: pick one random specific detail and ask the author to verify it. It is never scored, and no reviewed score band enters the Formulaic Writing Risk Score. Density and precision findings are advisory with zero weight and never change the numeric score.

```bash
python3 density.py --file doc.md --medium argument
cat doc.md | python3 density.py
python3 density.py --fixtures skills/antislop/evals/density-precision-fixtures.json
```

Fixtures live in `skills/antislop/evals/density-precision-fixtures.json`. `validate.py` runs the corpus and fails when a fixture expectation does not match.

---

## Rule provenance and decay

`provenance.py` is a standard-library review of the rule registry's evidence metadata (issue #101), reviewed against `ama-zingco/anti-ai-writing-skill` at a0571d7 (MIT). Every rule carries an `evidence_meta` block recording its evidence class, decay state, review dates, and, for adopted external concepts, an exact commit and a source-file permalink instead of a repository home page.

Eight evidence classes distinguish stable house rules from dated observations:

- **project-policy**: a house rule this project owns on its own authority; no external study or fixture is needed
- **project-fixture**: a rule whose executable behavior is pinned by local fixtures; any upstream source is design evidence
- **upstream-evidence**: a concept adopted from an executable upstream source, pinned to an exact commit and permalink
- **tested-adaptation**: a local adaptation of an upstream concept, tested against this project's own fixtures
- **primary-research**: a rule backed by primary research this project performed or reproduced
- **secondary-claim**: a rule supported only by a written guide this project did not reproduce
- **maintainer-judgment**: a rule recorded on maintainer judgment with no external study or fixture
- **unknown**: the origin of a rule is not recorded or cannot be classified

Each rule also records a decay state (current, review, stale), a last-reviewed date, and an optional source date. Listing a rule in the review queue never disables it: the rule stays active until a human changes its review mode or semantic type. The zero-em-dash rule stays project-policy and current regardless of changing corpus observations, and an external numeric threshold cannot become a strict finding without a directly identified source and local fixtures.

The `review_queue` section of `rules.json` holds stale lexical rules (still active) and six fixture-backed candidate metrics adapted from the reviewed project: nominalization, scientific-register mismatch, punctuation scarcity, conjunction chains, sentence-length variation, and quote voice. Every candidate names matched-length and matched-profile clean cases, so a candidate cannot be accused of firing on text length or on a writing profile before it ships.

```bash
python3 provenance.py --fixtures skills/antislop/evals/provenance-fixtures.json
python3 provenance.py
```

Fixtures live in `skills/antislop/evals/provenance-fixtures.json`, covering a project house rule with no external study, a dated lexical heuristic marked for review, a structural rule with local executable fixtures, scientific terms in research prose and in empty marketing copy, and a conjunction chain versus a grammatical enumeration. `validate.py` runs the evidence schema and the corpus and fails when either disagrees. Source metadata records where a rule came from and when it was reviewed; it never proves the rule is correct.

---

## Labeled calibration harness

`calibration.py` is a standard-library, deterministic evaluation command (issue #89). It runs frozen labeled fixtures against a baseline implementation and a candidate implementation and stores the experiment configuration and results as reviewable JSON artifacts.

Each fixture records its profile, genre, locale, source, and label provenance and carries four kinds of labels: expected findings, clean spans, preservation obligations, and forbidden additions. Numeric targets and ranked findings drive calibration metrics. The report covers category recall, false-positive rate, exact-span agreement, preservation failures, integrity failures, score delta, score stability, per-profile results, mean absolute error for numeric targets, and rank correlation where ordering is meaningful. Per-category results are reported separately so a candidate with better aggregate recall but worse technical false positives shows up instead of hiding behind one average.

Missing labels stay missing and never become zero: a category with no labeled expected findings reports an explicit unlabeled state rather than a zero recall. The experiment requires a non-empty holdout set and an explicit score direction. Holdout fixtures are never used to tune thresholds, because thresholds are static configuration values. The gate can fail on configured false-positive, recall, or preservation regressions.

```bash
python3 calibration.py --experiment-config skills/antislop/evals/calibration-experiment.json
python3 calibration.py --experiment-config skills/antislop/evals/calibration-experiment.json --output results.json
```

The shipped experiment compares the full 3.0.0 scorer with a forbidden-only detector set, so the per-category recall regressions the candidate produces on mechanism and structural findings stay visible in the report. Fixtures live in `skills/antislop/evals/calibration-fixtures.json`. The evaluation fixtures prove a rewrite that lowers risk while dropping a qualifier, an unlabeled category whose missing values stay unknown, and a repeated run whose output is byte-identical; the fail-on false-positive path for a candidate with better aggregate recall but worse technical false positives is proven in `tests/test_calibration.py`. `validate.py` runs the experiment and fails when the configured gate fails.

---

## How to use effectively

**Let the matching skill activate.** Antislop triggers for explicit prose-artifact work, while antislop triggers when you ask for a score or violation review. Once activated, the relevant guidance stays in effect for that task.

**Audit before sending, not while writing.** Write freely. Let antislop clean up sentence-level patterns in real time. The mandatory pre-output scan catches em-dashes that slip through. Then run antislop as a final gate before publishing. The audit catches what the style misses: paragraph redundancy, triplet overlap, semantic repetition.

**Bring content, not just form.** Antislop catches patterns: sentence structure, banned words, rhythm tells. It does not catch vague ideas or unsupported claims. You still need to bring specific experience, numbers, examples, and a point of view.

**Run the checklist.** The skill includes a 20+ item audit checklist. Run through it before finishing any piece. The items at the bottom matter most: redundancy, triplet overlap, antithesis, metaphors, endings. They catch what pattern matching can't.

**Don't over-apply.** Antislop is for prose meant to be read by humans. Skip it for code, config files, commit messages, structured data, and machine-oriented API reference entries. Technical explanations and narrative API documentation remain in scope when the request explicitly asks to write or edit them.

**For Gemini users.** Install the universal skills in Gemini CLI, Antigravity,
or Gemini Skills. For classic web Gems, put the relevant `SKILL.md` in the
Instructions field and attach its reference Markdown files as Knowledge.

---

## Version history

### Version 3.0

Version 3.0 changes the score contract through new rule classifications and calibration. Scores from 2.x and 3.x are not directly comparable. The registry, generated references, runtime metadata, examples, and version-sensitive tests now share the 3.0.0 version.

### Version 2.0

Version 2.0 introduced the rule registry (`rules.json`) as the single source of truth for all writing rules. Each rule has a stable ID, severity, detection class, profile set, and overlap relationships. The generator (`generate.py`) renders pattern reference files from the registry, and the scorer (`score.py`) calculates scores using the registry metadata.

**What changed from 1.7:**
- Score renamed from "Slop Score" to "Formulaic Writing Risk Score"
- Authorship disclaimer added: score cannot prove AI authorship
- Writing profiles: general and technical (extensible via rules.json)
- Diminishing repetition: repeated instances of one rule diminish (100%, 50%, 25%), capped at 3x base weight
- 500-word normalization: comparable scores across different text lengths
- Overlap handling: one primary finding per text span, related findings unscored
- Rule registry: 146 rules with stable IDs, severity weights, and profile assignments

**Compatibility boundary:** 2.0.0 ships directly from 1.7.0. A 1.8 compatibility release was planned to correct contradictions and overlap handling while preserving the 1.7 score formula, but no 1.8.0 tag was ever cut (see `docs/adr/0002`); those corrections landed directly in 2.0 instead. The 1.7 score formula is not preserved in 2.0.

### Version 2.1 score contract

Version 2.1 reclassifies mechanism findings as advisory and therefore changes
scores for existing input. The version increase is intentional: consumers
that compare stored scores must not treat 2.0.x and 2.1.x results as the same
calibration. Reports continue to identify the scoring version, and
`rules.json` remains the single source for the shipped version.

---

## Sources and credits

Runtime skill files omit attribution lists so the agent loads only execution guidance. The complete source and credit record lives in
[docs/sources/credits.md](docs/sources/credits.md). It includes baseline
inspiration, issue-driven references, pinned revisions, adoption decisions,
licenses, and methodological limits.

---

## License

MIT

## Edit preservation provenance

Issue #140 records the bounded review of Anbeeld WRITING.md 1.4.2 at commit
e59d477. Antislop adopts its precedence and preservation ideas through the
registry, edit, fidelity, output-integrity, and generation contracts. The
pinned upstream source is MIT licensed. See
docs/adr/0009-anbeeld-writing-1-4-2.md for the adopt, adapt, and reject record.
