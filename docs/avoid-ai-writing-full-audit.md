# Full audit of `avoid-ai-writing`

Date: 2026-08-31

## Answer

### Implementation update

Version 3.0.0 implements the deterministic adoption described by this audit.
It adds independent voice, context, and mechanics axes; registered variants;
protected-span masking; stable offsets; input gates; publishing and selected
structural detectors; literal preservation; an executable trigger router; and
a read-only MCP server. The universal package now uses
`.codex-plugin/plugin.json` and includes the single Antislop skill plus the MCP configuration.

The original readiness result below remains the baseline. Ten of its eleven
failed capabilities now have executable public-seam tests. A model-pinned
rewrite and activation run remains unverified, so the repository still does
not claim complete model behavior.

ScrutinAIze was added as an assurance reference after the original source
inventory. Its offline static scan found no known MCP failures after the
protocol declaration was added. Evidence coverage was 75 percent, and the
live-host control remained unknown because static configuration is not runtime
proof. This report keeps that unknown state explicit.

The follow-up [end-to-end test](avoid-ai-writing-e2e.md) confirms that this is
an adoption plan at the baseline revision, not a working replacement system. Seven Antislop capabilities
passed, eleven failed, and model rewrite behavior remained unverified after a
client-parity repair. The upstream deterministic analyzer and preservation
pipeline passed its exercised path.

The existing Antislop adaptation is a useful first pass, not a full adoption. It added six mechanical publishing checks, provenance protection, two structural rewrite tests, credits, evaluation notes, and an architecture decision. It did not adopt voice profiles, the 112-entry replacement system, the complete 69-category catalog, detector or preservation behavior, MCP tools, generated Cursor packaging, or the upstream trigger and context model.

Antislop should adopt parts of the upstream design, but not copy it wholesale. The strongest ideas are the separate voice and context axes, explicit rewrite/detect/edit routing, tier and density metadata, preservation validation, a machine-readable category contract, generated distribution artifacts, and a read-only scanner tool. The weakest parts are the authorship claims. Upstream's own corpus result says its lexical detector is weak: paragraph ROC-AUC is 0.501 and document ROC-AUC is 0.623. Its displayed `human` / `mixed` / `ai` probabilities are heuristic outputs, not calibrated authorship probabilities.

The recommended direction is:

1. Keep Antislop's modular registry and generated references as the canonical architecture.
2. Add voice, replacement, tier, density, scope, variant, and detector-mapping fields to that registry.
3. Import high-confidence clarity and publishing rules first, with tests and exceptions.
4. Add preservation and rendered-Markdown masking before exposing a scanner as a tool.
5. Keep writing guidance and deterministic audit tools separate.
6. Reject authorship classification, detector evasion, and unqualified frequency claims.

Several recommendations depend on the planned typed-rule foundation. Voice profiles, positive instructions, suggested repairs, preservation invariants, density heuristics, and evaluation signals should not be encoded as ordinary prohibitions merely to fit the current registry.

## Scope, pins, and verification

The audit used repository files, code, tests, and primary project documentation. Every tracked file in the two mandatory repositories is accounted for below.

The source review covers every repository named in upstream's Credits section plus the directly linked MCP, Cursor, ClawHub, multilingual, SSOT, repository-audit, voice-profile, guardrail, structural-research, and detector-evasion artifacts that affect an adoption decision. It does not recursively audit every outbound citation found inside those projects. Claims are taken from the projects' own pinned files or tests, not secondary summaries.

| Source | Audited revision | Files | Verification |
|---|---:|---:|---|
| [`conorbronsdon/avoid-ai-writing`](https://github.com/conorbronsdon/avoid-ai-writing/tree/58a95fc9971d7af95f1f1324b8a6bc991eb8004d) | `58a95fc9971d7af95f1f1324b8a6bc991eb8004d` | 50 | `npm test` passed; `npm run self-scan:check` passed |
| [`conorbronsdon/avoid-ai-writing-mcp`](https://github.com/conorbronsdon/avoid-ai-writing-mcp/tree/125e0818b7e1b88d904c73c7729a5e5c1441f8a6) | `125e0818b7e1b88d904c73c7729a5e5c1441f8a6` | 11 | `npm test` passed |
| Antislop baseline branch | `33e7c0594e0b33f34ff4968ad37cf93b3cdfcd13` | original PR worktree | registry and generated references inspected; score behavior exercised |
| [`ScrutinAIze`](https://git.drunkrhin0.au/drunkrhin0/ScrutinAIze) | `c59ba1cff2b36b25d06b4e39bae6e6f501c8312e` | source-linked static assurance scan | known-result score 100, evidence coverage 75, no known failures, one runtime-only unknown |

The task described the MCP repository as ten files. `git ls-files` returns eleven, so this report inventories all eleven.

The parallel Antislop source review underway at the time of this audit is
designing a typed-rule foundation for policy, heuristics, preferences,
structural guidance, evaluation, positive guidance, repairs, profiles, and
tooling. This report does not duplicate that work. Its staged recommendations
identify which upstream concepts require that foundation.

## Decision summary

| Surface | Current Antislop overlap | Decision | Reason |
|---|---|---|---|
| Voice profiles | None | Adopt, adapted | The five profiles are useful, but must be a separate registry axis with provenance and no-fabrication constraints. |
| 112 replacement entries | 33 direct, 13 partial, 66 missing | Adopt in stages | Add metadata and replacements first. Do not turn all terms into unconditional bans. |
| 69 pattern categories | Broad conceptual overlap, incomplete named catalog | Adapt | Keep category IDs distinct from atomic rules and record detector coverage, examples, exceptions, and false-positive risk. |
| Trigger routing | Ambient style plus separate audit skill | Adapt | Retain split skills. Add explicit rewrite, detect, and edit intent routing and negative triggers. |
| Pattern reference | Generated, complete for Antislop's 152 atomic rules | Keep and extend | The existing generated reference is structurally better. It lacks replacement, tier, density, and detector mapping fields. |
| Content patterns | Many covered, several missing | Adopt selectively | Add evidence-backed publishing artifacts now; trial semantic categories with counterexamples. |
| Structure patterns | Strong overlap; some gaps | Adopt selectively | Add missing measurable patterns. Keep semantic checks separate from executable matching. |
| Detector | Antislop executes exact and phrase rules only | Rebuild from registry concepts | Upstream masking, offsets, deduplication, gates, and context exceptions are strong. Its authorship labels are not. |
| Preservation validator | No equivalent | Adopt | This is the largest safety gap in rewriting. |
| Claude plugin | Antislop already has broader packaging | Reference | Upstream plugin contains only the skill. It does not install detector tools. |
| MCP tools | None | Adopt later | Expose read-only style findings only after scorer parity and preservation support. |
| Cursor port | None | Adopt | Generated distribution artifact with drift checks is a good pattern. |
| Multilingual ports | None | Adopt process later | Use native research and native maintainers, not literal translation. |
| Authorship probability | None | Reject | Corpus performance is weak and outputs are uncalibrated. |

## Dependency on a typed rule foundation

The current Antislop registry is strongest at recording things not to do. Upstream mixes at least five different kinds of instruction in one long skill: hard preservation policy, heuristic signals, configurable preferences, structural guidance, and evaluation-only measurements. Importing them all as severity-bearing bans would make the registry less accurate.

The following upstream proposals should wait for, or be implemented with, the typed-rule schema:

| Upstream proposal | Required kind | Why it should not be a plain prohibition |
|---|---|---|
| Preserve quotes, code, tables, URLs, facts, numbers, and attribution | Policy | A rewrite that violates these is invalid, not merely stylistically weak. |
| Tier 1A, Tier 2, Tier 3, uniformity, entropy, and burstiness | Heuristic or evaluation | These are weighted or thresholded signals with false-positive risk, not universal writing errors. |
| Em-dash, quotation, heading, serial-comma, and number conventions | Preference | They depend on house style and explicit user mechanics. |
| Paragraph reshuffle, treadmill, opener runs, triples, and wall-of-text | Structural guidance | Most require paragraph or discourse analysis and often a manual decision. |
| Corpus ROC-AUC, signal lift, and false-positive budgets | Evaluation | These measure the system. They should not emit reader-facing violations. |
| Voice and context profiles | Profile | They select positive behavior and exceptions across many rules. |
| `use`, `state the metric`, `name the actor`, or `cut the clause` | Repair / positive guidance | The replacement is the useful action; storing only a ban loses it. |
| MCP caps, read-only annotations, source modes, and highlighting | Tooling | These govern an interface and runtime, not prose style. |

The adoption sequence should therefore be schema first, then data migration, generated artifacts, executable analyzers, and client packaging. Mechanical rules already represented safely in the current registry can proceed independently. The schema must also preserve the distinction between a style preference, a clarity suggestion, and evidence about provenance.

## What the current PR actually adopted

At `33e7c0594e0b33f34ff4968ad37cf93b3cdfcd13`, the PR adds:

- numbered-list inflation;
- paragraph reshuffle as a structure test;
- paragraph treadmill detection;
- unfilled placeholders;
- chatbot citation-token leakage;
- AI-tool tracking parameters in URLs;
- a provenance rule;
- an ADR, evaluation notes, credits, and a short upstream review.

It does not add:

- any named voice profile;
- the tiered 112-entry replacement table or its suggested replacements;
- the ten Tier 3 phrase rules;
- a 69-category contract;
- context and voice precedence;
- detect/rewrite/edit mode routing;
- detector masking, normalization, density logic, or stable offsets;
- preservation validation;
- an npm detector or MCP server;
- a generated Cursor rule;
- corpus acquisition and hash controls.

Antislop currently has 152 atomic registry rules: 57 structural, 37 vocabulary, 37 phrase, 9 formatting, 7 filler, and 5 chatbot rules. Its executable scorer skips all 57 structural rules and all 8 `pattern` detection rules. It therefore skips 65 registry rules in general scoring and executes only exact and phrase matching. Antislop's `general` and `technical` profiles are scorer profiles, not writing voices.

### Internal drift found during comparison

The upstream count and sync gates exposed two Antislop reference defects:

- `rules.json` had 37 vocabulary rules, while the style replacement table had
  34 rows. Five registered terms were absent (`enhance`, `interplay`,
  `navigate`, `showcase`, and `unpack`), while two unregistered terms appeared
  only in the table (`ensure` and `explore`). `explore` was also recommended as
  a replacement elsewhere.
- `rules.json` had 57 structural rules, while the style structure reference
  listed 47. Ten registered rules were unavailable to a style-mode reader.

This PR aligns both references and adds registry-parity tests. The Kiro copies
remain generated derivatives. This is a direct adoption of upstream's drift
discipline, not an import of its headline counts.

## Voice, context, house style, and triggers

### Voice profiles

Upstream defines five voices in [`SKILL.md`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/SKILL.md):

| Voice | Intended change | Adoption note |
|---|---|---|
| `casual` | conversational contractions, looser cadence | Adopt with controls against invented first-person experience. |
| `professional` | concise, direct, measured | Adopt as the safe default for work prose. |
| `technical` | precise terminology and explicit logic | Adopt, while separating legitimate terms from generic technical theater. |
| `warm` | considerate, approachable language | Adopt with limits on gratitude, empathy, and emotional claims not present in the source. |
| `blunt` | terse, direct, minimal cushioning | Adopt with safeguards for requested register and interpersonal risk. |

These are not present in the current Antislop PR. Upstream also allows calibration from a writing sample. That should take precedence over a named profile, subject to preservation and no-fabrication rules.

### Context profiles

The skill defines six writing contexts: `linkedin`, `blog`, `technical-blog`, `investor-email`, `docs`, and `casual`. The detector defines four scoring contexts: `general`, `technical`, `marketing`, and `personal`. The detector README documents only `general` and `technical`. This is an internal taxonomy mismatch, not a model to copy unchanged.

Antislop should define three explicit axes:

- `voice`: how the author sounds;
- `context`: the publication or audience setting;
- `mechanics`: spelling, punctuation, quotation, heading, and number conventions.

Suggested precedence: source preservation and explicit mechanics, then a supplied voice sample, then an explicit voice, then context defaults. Add cross-product tests for voice and context conflicts.

### House style

Upstream accepts register and mechanics configuration. Its precedence is mechanics over explicit voice, explicit voice over configured register, and register over context. `scripts/check-style.js` can check quotation style and Latin abbreviations. Heading capitalization, dash style, and number spelling are advisory; the serial comma remains an LLM-only instruction.

Adopt the separation of deterministic mechanics from semantic voice. Do not claim a check is enforced when it is only prompt guidance.

### Trigger behavior

The upstream skill routes explicit `rewrite`, `detect`, and `edit` intents, with rewrite as default. It accepts voice, context, and style arguments and limits rewrite convergence to two passes. Its description is narrower than Antislop's ambient trigger. It is aimed at requests such as removing AI-isms, auditing tells, or making prose sound less AI-like.

Keep Antislop's two-skill split:

- ambient `antislop` for writing and editing;
- explicit `antislop` for scores and violations.

Add upstream's intent vocabulary within those skills. Do not combine both into a single 15,000-word skill. Add negative triggers for source code, configuration, generated files, quoted material, and third-party text that should only be analyzed.

## Audit of all 112 replacement entries

### Policy conflict that applies to the whole table

Upstream distinguishes:

- Tier 1A frequency markers, always replaced but based on an inherited and unmeasured `5-20x` claim;
- Tier 1B clarity edits, always replaced but explicitly not authorship evidence;
- Tier 2 terms, flagged only when two or more occur in one paragraph;
- Tier 3 terms, flagged only around three percent density;
- morphological variants, with context-sensitive carve-outs.

Antislop mostly models terms as exact, unconditional severity-bearing bans. That loses inflection handling, density, clustering, replacements, legitimate senses, and the crucial distinction between a writing suggestion and authorship evidence. Every imported row therefore needs a policy adaptation even when the base term already exists.

Coverage across all 112 rows is 33 direct, 13 partial, and 66 missing. `Direct` means the base rule is explicit in Antislop, not that its policy is equivalent.

### Tier 1A: 49 frequency-marker rows

| Upstream entry and suggested action | Antislop | Decision |
|---|---|---|
| delve / delve into -> explore, dig into, look at | Direct | Adapt variants and replacement. |
| landscape, metaphor -> field, space, industry, world | Partial | Add metaphor scope; avoid literal false positives. |
| tapestry -> describe the complexity | Direct | Keep. |
| realm -> area, field, domain | Partial | Add density/context rather than an absolute ban. |
| paradigm -> model, approach, framework | Missing | Trial; common in legitimate academic prose. |
| embark -> start, begin | Direct | Keep. |
| beacon -> rewrite specifically | Missing | Add metaphor-scoped rule. |
| testament to -> shows, proves, demonstrates | Direct | Keep. |
| robust -> strong, reliable, solid | Direct | Preserve legitimate technical/statistical uses. |
| comprehensive -> thorough, complete, full | Direct | Keep as contextual, not authorship evidence. |
| cutting-edge -> latest, newest, advanced | Direct | Keep promotional-language rule. |
| leverage, verb -> use | Direct | Preserve finance and literal leverage senses. |
| pivotal -> important, key, critical | Direct | Keep as inflation check. |
| underscores -> highlights, shows | Partial | Add inflections and sentence-level context. |
| meticulous / meticulously -> careful, detailed, precise | Missing | Trial; ordinary descriptive prose can be valid. |
| seamless / seamlessly -> smooth, easy, without friction | Direct | Keep marketing scope. |
| game-changer / game-changing -> state the change | Direct | Keep variants. |
| hit differently / hits different -> state what changed or cut | Missing | Adopt only for unsupported reaction language. |
| watershed moment -> turning point or specific change | Missing | Adopt as significance inflation. |
| marking a pivotal moment -> state what happened | Partial | Covered pieces, but add construction. |
| the future looks bright -> cut or be specific | Direct | Keep generic closer. |
| only time will tell -> cut or be specific | Missing | Adopt generic closer. |
| nestled -> is located, sits, is in | Missing | Adopt for travel and location promotion, not literal nesting. |
| vibrant -> describe the activity | Direct | Keep promotional-language rule. |
| thriving -> growing, active, or cite a number | Partial | Add evidentiary action. |
| despite challenges, continues to thrive -> name challenge and response | Direct | Keep formula rule. |
| showcasing -> showing, demonstrating, or cut | Partial | Add participle construction. |
| deep dive / dive into -> examine, explore | Partial | Add variants. |
| unpack / unpacking -> explain, break down | Direct | Keep. |
| bustling -> busy, active, or cite evidence | Missing | Adopt for promotional description. |
| intricate / intricacies -> name the detail | Missing | Trial; legitimate artistic and technical use is common. |
| complexities -> name the problems or details | Missing | Trial as vagueness, not lexical authorship. |
| ever-evolving -> describe the change | Direct | Keep. |
| enduring -> lasting, long-running, or cite duration | Missing | Trial as unsupported significance. |
| daunting -> hard, difficult, challenging | Missing | Reject as an automatic replacement; use only when unsupported. |
| holistic / holistically -> describe what is included | Direct | Keep contextual rule. |
| actionable -> practical, useful, concrete | Missing | Add as vague business jargon with exceptions. |
| impactful -> effective, significant, or describe impact | Missing | Add clarity guidance, not authorship signal. |
| learnings -> lessons, findings, takeaways | Missing | Treat as optional house-style rule. |
| thought leader / thought leadership -> substantiate contribution | Missing | Adopt promotional and notability rule. |
| best practices -> specify what works | Missing | Add only when no actual practice follows. |
| at its core -> cut and state the point | Direct | Keep. |
| synergy / synergies -> describe combined effect | Direct | Keep. |
| interplay -> relationship, connection, interaction | Direct | Keep contextual rule. |
| keen as intensifier -> interested, eager, or cut | Missing | Reject automatic ban; strongly register-dependent. |
| genuine / genuinely as intensifier -> cut | Missing | Add intensifier-scoped pattern, not exact ban. |
| symphony as metaphor -> describe coordination | Missing | Add metaphor-scoped rule. |
| embrace as metaphor -> adopt, accept, use | Missing | Add metaphor-scoped rule. |
| load-bearing as metaphor -> essential or state failure mode | Missing | Adopt with upstream's literal construction carve-out. |

`load-bearing` must retain its literal building exceptions. Upstream still has a known false positive for predicative uses such as a wall being load-bearing.

### Tier 1B: 10 clarity rows

| Upstream entry and replacement | Antislop | Decision |
|---|---|---|
| utilize -> use | Direct | Adopt replacement metadata; never authorship evidence. |
| in order to -> to | Direct | Keep. |
| due to the fact that -> because | Direct | Keep. |
| serves as -> is | Direct | Keep with role/function exceptions. |
| features, verb -> has or includes | Direct | Keep only for inflated copula avoidance. |
| boasts -> has | Direct | Keep promotional scope. |
| presents, inflated -> is, shows, gives | Missing | Add scoped construction. |
| commence -> start, begin | Direct | Keep as clarity option. |
| ascertain -> find out, determine, learn | Direct | Keep, but allow legal and technical register. |
| endeavor -> effort, attempt, try | Missing | Add as optional clarity edit, not a ban. |

### Tier 2: 40 cluster-sensitive rows

| Upstream entry and replacement | Antislop | Decision |
|---|---|---|
| harness -> use, take advantage of | Missing | Add to cluster vocabulary. |
| navigate -> work through, handle | Direct | Add variants and cluster semantics. |
| foster -> encourage, support, build | Direct | Add cluster semantics. |
| elevate -> improve, raise, strengthen | Missing | Add promotional cluster rule. |
| unleash -> release, enable, unlock | Missing | Add promotional cluster rule. |
| streamline -> simplify, speed up | Missing | Trial; valid process term. |
| empower -> enable, let, allow | Direct | Add cluster semantics. |
| bolster -> support, strengthen | Missing | Trial. |
| spearhead -> lead, drive, run | Missing | Trial as business jargon. |
| resonate -> connect with, appeal to | Missing | Add when emotion or audience response is unsupported. |
| revolutionize -> describe the change | Direct | Keep promotional rule. |
| facilitate -> enable, help, allow | Direct | Add cluster semantics. |
| underpin -> support, form the basis | Missing | Trial; valid technical and academic term. |
| nuanced -> name the nuance | Partial | Extend from complexity-signaling constructions. |
| crucial -> important, key, necessary | Partial | Keep only as contextual filler/inflation. |
| multifaceted -> name the facets | Missing | Add vagueness rule. |
| ecosystem, metaphor -> system, network, market | Missing | Add metaphor scope and technical exceptions. |
| myriad -> many or a number | Missing | Optional clarity edit. |
| plethora -> many or a number | Missing | Optional clarity edit. |
| encompass -> include, cover, span | Missing | Reject automatic replacement; ordinary precise verb. |
| catalyze -> start, trigger, accelerate | Missing | Trial with chemistry exception. |
| reimagine -> rethink, redesign, rebuild | Missing | Add promotional cluster rule. |
| galvanize -> motivate, rally, push | Missing | Trial with literal exception. |
| augment -> add to, expand | Missing | Reject automatic replacement; normal technical term. |
| cultivate -> build, develop, grow | Missing | Trial as business metaphor. |
| illuminate -> clarify, explain, show | Missing | Trial as metaphor only. |
| elucidate -> explain, clarify | Missing | Treat as register option, not authorship evidence. |
| juxtapose -> compare, contrast | Missing | Reject automatic replacement; established analytical term. |
| paradigm-shifting -> describe the shift | Missing | Adopt promotional inflation rule. |
| transformative / transformation -> describe change | Partial | Add noun and variants. |
| cornerstone -> foundation, basis, key part | Missing | Add metaphor-scoped rule. |
| paramount -> most important | Missing | Trial as significance inflation. |
| poised to -> ready, set, about to | Missing | Add prediction construction. |
| burgeoning -> growing, emerging | Missing | Trial with evidence requirement. |
| nascent -> new, early-stage | Missing | Reject automatic replacement; established domain term. |
| quintessential -> typical, classic, defining | Missing | Treat as register option. |
| overarching -> main, central, broad | Missing | Treat as optional clarity edit. |
| quietly -> cut or name the contrast | Missing | Add only for significance constructions. |
| deeply in significance collocations -> name depth | Missing | Add phrase patterns; preserve literal and emotional uses. |
| underpinning / underpinnings -> basis, foundation | Missing | Trial, sharing exceptions with `underpin`. |

### Tier 3: 13 density-sensitive rows

| Upstream entry and action | Antislop | Decision |
|---|---|---|
| significant / significantly -> add specifics | Partial | Add variants and density; do not ban. |
| innovative / innovation -> state novelty | Partial | Add noun and density. |
| effective / effectively -> state method or metric | Missing | Add only as a density/vagueness rule. |
| dynamic / dynamics -> name forces or changes | Partial | Add noun and density. |
| scalable / scalability -> state what scales and limit | Missing | Add as specificity prompt. |
| compelling -> say why | Missing | Add when unsupported. |
| unprecedented -> name precedent | Missing | Adopt novelty-inflation rule. |
| exceptional / exceptionally -> cite exception | Missing | Add when unsupported. |
| remarkable / remarkably -> state why | Missing | Add when unsupported. |
| sophisticated -> describe mechanism | Missing | Add when unsupported. |
| instrumental -> state role | Missing | Trial as vague causal language. |
| world-class / state-of-the-art / best-in-class -> benchmark | Missing | Adopt promotional rule. |
| verbatim -> cut unless exactness is material | Missing | Adopt with legal, research, and QA exceptions. |

### Ten additional Tier 3 phrase rows

These rows are outside the stated 112 single-entry count. None is directly represented in Antislop today.

| Phrase | Decision |
|---|---|
| emerging sector / space / category | Add only when the thing and evidence are unnamed. |
| the integration of X with Y | Add as a specificity prompt. |
| the intersection of X and Y | Add as a specificity prompt. |
| community-driven | Add when community action is absent. |
| long-term sustainability | Add when time horizon and constraint are absent. |
| user engagement | Add when the user action or metric is absent. |
| decentralized compute | Reference-only unless Antislop needs a Web3 profile. |
| sustainable reward emissions | Reference-only unless Antislop needs a Web3 profile. |
| tokenized incentive structures | Reference-only unless Antislop needs a Web3 profile. |
| designed for long-term X | Add as a `designed for` vagueness construction. |

## Audit of all 69 pattern categories

`README.md` presents only a representative 56-item pattern reference. The full catalog is in `SKILL.md`. [`.ssot.yaml`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/.ssot.yaml) and [`scripts/check-pattern-count.sh`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/scripts/check-pattern-count.sh) make the public claims of 69 categories and 112 replacement rows fail when they drift.

The status below compares category intent, not exact implementation. `Covered` can still mean prompt-only. `Partial` means narrower or materially different behavior. `Missing` means no clear atomic rule.

| # | Upstream category | Antislop status | Decision |
|---:|---|---|---|
| 1 | Formatting | Partial | Keep Antislop rules; resolve dash policy as house style, not authorship evidence. |
| 2 | Sentence structure | Covered | Keep and extend measurable checks. |
| 3 | Words and phrases to replace | Partial | Add tier, replacement, variant, and density metadata. |
| 4 | Template phrases | Partial | Import high-signal constructions with slots. |
| 5 | Transition phrases | Covered | Keep. |
| 6 | Structural issues | Covered | Keep. |
| 7 | Significance inflation | Covered | Keep and add evidence prompts. |
| 8 | Aphorism formulas | Covered | Keep. |
| 9 | Generic future-narrative closers | Partial | Add missing closer formulas. |
| 10 | Hedge-stacked predictions | Covered | Keep. |
| 11 | `real` / `actual` inflation | Partial | Add scoped intensifier patterns. |
| 12 | Moral-adjective category errors | Missing | Trial with examples and counterexamples. |
| 13 | Hashtag stuffing | Missing | Adopt as a measurable publishing rule. |
| 14 | Bullet lists of bare noun phrases | Missing | Adopt as a structural audit, with outline exceptions. |
| 15 | Copula avoidance | Covered | Keep. |
| 16 | Subjectless fragments / agentless passives | Covered | Keep. |
| 17 | Synonym cycling | Covered | Keep semantic/manual classification. |
| 18 | Vague attributions | Covered | Keep. |
| 19 | Filler phrases | Covered | Keep. |
| 20 | Generic conclusions | Covered | Keep. |
| 21 | Chatbot artifacts | Covered | Keep. |
| 22 | `Let's` constructions | Partial | Add intent-sensitive construction. |
| 23 | Notability name-dropping | Covered | Keep. |
| 24 | Vague third-party validation | Covered | Keep under vague attribution. |
| 25 | Superficial `-ing` analyses | Covered | Keep. |
| 26 | Promotional language | Covered | Keep. |
| 27 | Formulaic challenges | Covered | Keep. |
| 28 | Speculative scenario openers | Partial | Add constructions; preserve legitimate scenarios. |
| 29 | False ranges | Covered | Keep. |
| 30 | Inline-header lists | Covered | Keep. |
| 31 | List-label periods | Missing | Adopt as optional mechanics, not universal style. |
| 32 | Title case headings | Covered | Keep as configurable mechanics. |
| 33 | Hyphenated modifier stacking | Partial | Extend structural detection. |
| 34 | Unnecessary hyphenation | Partial | Add only with lexical/mechanical confidence. |
| 35 | Cutoff disclaimers | Covered | Keep. |
| 36 | Speculative gap-filling | Covered | Keep provenance and specification-theater rules. |
| 37 | Unfilled placeholders | Covered by current PR | Keep. |
| 38 | Chatbot citation leaks | Covered by current PR | Keep. |
| 39 | AI tool URL parameters | Covered by current PR | Keep. |
| 40 | Novelty inflation | Missing | Adopt with evidence requirement. |
| 41 | Infomercial engagement hooks | Covered | Keep. |
| 42 | Social endorsement closers | Missing | Adopt for social-content context. |
| 43 | Emotional flatline | Partial | Keep as manual voice review, not deterministic failure. |
| 44 | Lingering-attention claims | Missing | Trial as unsupported emotional claim. |
| 45 | False concession | Partial | Extend construction set. |
| 46 | Invented contrast-pair mirroring | Partial | Extend structural/semantic rule. |
| 47 | Rhetorical-question openers | Covered | Keep. |
| 48 | Parenthetical hedging | Missing | Trial with citation and technical exceptions. |
| 49 | Numbered-list inflation | Covered by current PR | Keep. |
| 50 | Reasoning-chain artifacts | Partial | Extend chatbot artifact patterns. |
| 51 | Sycophantic tone | Covered | Keep. |
| 52 | Narrated candor | Partial | Extend phrase registry. |
| 53 | Acknowledgment loops | Partial | Extend discourse-level manual rule. |
| 54 | Confidence calibration | Partial | Add unsupported-certainty and over-hedging pair. |
| 55 | Self-labeling significance | Partial | Extend significance phrases. |
| 56 | Wall-of-text replies | Missing | Adopt as configurable readability audit. |
| 57 | Recap-flattery opener | Missing | Adopt phrase plus discourse-position rule. |
| 58 | Excessive structure | Covered | Keep. |
| 59 | Diff-anchored writing | Missing | Adopt for code-review and changelog contexts. |
| 60 | Performed-insight phrases | Partial | Extend phrase registry. |
| 61 | Negation chains | Partial | Add measurable sentence pattern and manual check. |
| 62 | Dev-blog boilerplate | Missing | Adopt for technical-blog context. |
| 63 | Stacked rhetorical questions | Partial | Add paragraph-level count. |
| 64 | Same-opener sentence runs | Covered | Keep generic-subject/run detection. |
| 65 | Stranded auxiliary contrast | Missing | Trial with examples and false-positive fixtures. |
| 66 | Colon into a triple | Partial | Add structural detector but do not ban all triples. |
| 67 | Manufactured punchlines / staccato drama | Partial | Extend discourse/manual rule. |
| 68 | Rhythm / uniformity | Covered | Keep, and consider executable measurement. |
| 69 | Vocabulary diversity | Missing | Research first; register and topic strongly affect it. |

The detector implements 51 issue types, not one detector for every catalog heading. [`detector/CATEGORIES.md`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/detector/CATEGORIES.md) explicitly maps direct detections, detector-only signals, and LLM-only checks. Detector-only signals include punctuation distribution, function-word trigram entropy, cross-paragraph burstiness, and a normalization flag. Antislop should adopt that contract pattern, while keeping its own category and rule IDs.

## Pattern reference, content patterns, and structure patterns

### Pattern reference

Antislop's generated
`skills/antislop/references/pattern-reference.md` is the better canonical
shape because it is derived from root `rules.json` and lists all 152 atomic
rules with severity. Upstream's public README list is representative and
incomplete, while its full skill is a large hand-maintained document. The
style-mode vocabulary and structure references are source files copied into
the Kiro Power, not registry-generated artifacts; the drift found above shows
that they need parity tests now and registry generation after the schema can
represent replacements and structural guidance.

Extend the Antislop registry with:

- stable category ID and atomic rule ID;
- replacement or rewrite action;
- tier and threshold;
- variant and inflection behavior;
- lexical, structural, semantic, or preservation classification;
- context inclusions and exclusions;
- detector implementation status;
- example and counterexample fixtures;
- source and evidence strength;
- whether the finding is style advice, clarity advice, or provenance risk.

Then generate the human pattern reference, skill summaries, scorer data, Cursor rule, and coverage matrix. Do not make a duplicated full skill the canonical source.

### Content patterns

Adopt now: hashtag stuffing, social endorsement closers, novelty inflation, recap-flattery openers, dev-blog boilerplate, and unsupported lingering-attention claims. These should be context-aware and fixture-backed.

Trial later: moral-adjective category errors, emotional flatline, parenthetical hedging, confidence calibration, and vocabulary diversity. These are semantic or register-sensitive and likely to produce false positives without examples and counterexamples.

### Structure patterns

The current PR already adopts paragraph reshuffle and treadmill checks. Add bare-noun bullet lists, wall-of-text replies, diff-anchored prose, stacked rhetorical questions, stranded auxiliary contrasts, colon-into-triple counts, and negation chains. Treat them as separate paragraph or discourse analyzers. A lexical regex engine cannot safely stand in for these checks.

Upstream also recommends rewriting from scratch when local substitutions cannot repair repeated structure. Antislop should add that as an explicit escalation condition, not a default behavior, because preservation risk grows sharply with full rewrites.

## Detector behavior

[`detector/patterns.js`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/detector/patterns.js) and [`detector/validate.js`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/detector/validate.js) contain several designs worth adopting:

- `plain` and `rendered-markdown` source modes;
- masking of initial YAML frontmatter and HTML comments in rendered mode;
- protection for code, blockquotes, tables, and attributed material;
- source-stable offsets for highlights;
- zero-width, homoglyph, and roleplay-prefix normalization;
- explicit too-short and too-long gates below 10 and above 10,000 words;
- deduplication by issue type and matched text;
- context exceptions and per-signal weights;
- separation of direct, detector-only, and LLM-only checks.

Its overlap handling is weaker than Antislop's registry model. The current
detector reports both `tier1` and `generic-conclusion` for the same surface
phrase, `The future looks bright`, because deduplication keys on issue type and
matched text. Cross-category matches therefore count twice. A future Antislop
analyzer should retain primary and related findings per span instead.

Do not adopt these outputs as facts about authorship:

- trinary `human`, `mixed`, and `ai` classifications;
- `humanProbability`, `mixedProbability`, and `aiProbability` fields;
- `confidence` presented without calibration data.

The score normalization is heuristic, including a log-base-two component. The corpus does not validate the probability interpretation. Rename any future Antislop tool output to `styleRisk`, `findingDensity`, or similarly bounded language.

Current Antislop scoring has no rendered-Markdown masking, inflection engine, tier or density semantics, length gates, or structural execution. Its 500-word normalization can over-penalize very short input. Scorer parity with the registry is a prerequisite for tool packaging.

## Preservation behavior

The upstream validator treats these as errors:

- changed fenced code blocks;
- changed YAML frontmatter;
- changed blockquotes;
- changed tables;
- changed inline code;
- changed URLs and paths;
- heading-count or nesting changes;
- an increase in residual detector issues.

It emits warnings for changed heading text, missing numbers, and rewrites that shrink the input by more than 40 percent. It has carve-outs for stripping tracking parameters and normalizing heading case.

Antislop should adopt this as a first-class `validate-preservation` layer. Add preservation for citations, named entities, negation, modal strength, units, dates, comparison direction, and attributed claims. Those semantic invariants matter more than style score improvement.

## Tests, corpus, and evidence

### Executed test coverage

Upstream `npm test` passed. The test files contain roughly 228 named checks: 138 detector-pattern checks, five category-contract outputs, 23 preservation checks, 23 corpus-helper checks, and 39 style checks. The exact total is a count of named assertions/subtests, not a coverage percentage.

The 69-category and 112-row gate checks declared counts and copied claims. They
do not validate replacement quality, duplicate semantics, category overlap, or
row-to-detector parity. `detector/categories.test.js` checks that detector types
appear in the prose coverage map and that published count literals stay
current; it does not prove that every vocabulary row is executable.

`npm run self-scan:check` also passed. It checks issue budgets for README, skill, contribution guide, detector docs, category docs, examples, changelog, and proof documentation. Passing means the repository stays within its own configured budgets. It does not prove that the detector distinguishes authorship.

The MCP install and test passed with 95 packages and no reported
vulnerabilities. It verifies two advertised tools, read-only annotations,
deterministic compact scoring, audit highlights, truncation, and too-short
behavior. A package dry run produced six published files. The tests do not
check parity with detector source version 3.28.0, and the installed MCP still
uses detector 3.22.1.

### Corpus controls

[`corpus/manifest.json`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/corpus/manifest.json) contains 38 hashed entries. The corpus cache is ignored, so tracked files contain provenance, retrieval information, and hashes rather than copyrighted text. The register mix is heavily skewed toward blogs:

| Register | Sources |
|---|---:|
| blog | 26 |
| essay-literary | 4 |
| academic | 3 |
| mixed | 2 |
| technical-blog | 1 |
| docs | 1 |
| conversational | 1 |

Thirty-six sources are marked human and pre-LLM. Two are dataset-labelled. Human controls are public-domain or pre-2023 material. Machine-labelled data comes from RAID under MIT and HC3 under CC BY-SA 4.0.

The pinned [`PROOF.md`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/PROOF.md) covers 875 human paragraphs and 779 machine paragraphs. At detector version 3.22.0 it reports:

- paragraph ROC-AUC: 0.501;
- document ROC-AUC: 0.623;
- Tier 1 vocabulary lift: 0.9, meaning it was slightly more common in the human sample;
- dash signal lift: 0.2, also inverted;
- uniformity lift: 11.7.

The source repository is now detector version 3.28.0, while the published corpus measurements remain 3.22-era evidence. The project itself states no tested threshold is useful as a general authorship classifier. Treat the corpus as a good reproducibility start and a negative result that constrains claims.

Adopt the manifest, hashing, source-date controls, register labels, and false-positive budgets. Expand balanced registers and add rewrite-preservation pairs. Do not optimize against proprietary detectors or present style markers as proof of human authorship.

## Plugin, tool, MCP, and installability audit

### Claude plugin

The upstream plugin consists of a marketplace entry, a plugin manifest, and a synchronized copy of the root skill. It is installable as a Claude/Cowork skill plugin, but contains no executable detector tool. The root and plugin `SKILL.md` files are byte-identical generated copies.

The README also documents a pinned `skills` installer, manual Claude installation, ClawHub/OpenClaw, Cursor, Hermes, Codex, and generic system-prompt use. A packaging claim is not the same as behavior parity across clients.

Antislop already distributes to more client formats: Claude, Codex/ChatGPT
plugin metadata, Kiro, and OpenCode, while Gemini consumes the universal
`SKILL.md` packages. Adopt upstream's generated Cursor rule and drift checks.
Do not replace Antislop's modular distribution with a single giant skill.

### MCP companion

The MCP server is a separate npm package and separate install. Installing the Claude plugin does not install tools. Installing the MCP server does not install the rewrite skill or voice profiles.

[`src/server.js`](https://github.com/conorbronsdon/avoid-ai-writing-mcp/blob/125e0818b7e1b88d904c73c7729a5e5c1441f8a6/src/server.js) exposes two tools:

- `score_text`, a compact score and classification result;
- `audit_text`, a detailed issue and highlight result.

Both have MCP annotations `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, and `openWorldHint: false`. Input is capped at 100,000 characters; audit findings and highlights are capped at 100 each. There is deliberately no rewrite tool.

The MCP [`package.json`](https://github.com/conorbronsdon/avoid-ai-writing-mcp/blob/125e0818b7e1b88d904c73c7729a5e5c1441f8a6/package.json) pins `avoid-ai-writing-detector` 3.22.1, while the source [`package.json`](https://github.com/conorbronsdon/avoid-ai-writing/blob/58a95fc9971d7af95f1f1324b8a6bc991eb8004d/package.json) is 3.28.0. It therefore does not expose the current detector behavior. More importantly, it forwards uncalibrated authorship classification and probability fields.

Adopt the separation, read-only annotations, caps, compact/detail split, stdio transport, and no-rewrite boundary. Reject authorship labels and probability fields. Add a dependency-parity test or generate the MCP package from the same monorepo release.

### Cursor and ClawHub

`cursor-rules/avoid-ai-writing.mdc` is generated from the root skill with Cursor frontmatter, prose-file globs, and portability rewrites. The generator fails when expected anchors or path rewrites drift. Adopt this pattern.

The [live ClawHub page](https://clawhub.ai/conorbronsdon/skills/avoid-ai-writing) was available when checked, but its displayed install command, `openclaw skills install @conorbronsdon/avoid-ai-writing`, differs from the README's `clawhub install avoid-ai-writing`. Verify the current client command before adding equivalent Antislop instructions. Treat ClawHub as a distribution target, not a source of rule semantics.

## Direct sources and credits audit

The README credits five sources, but the skill and changelog directly cite additional operative sources. Pins below are necessary because several projects are changing quickly.

| Source | Pin / license | Finding | Decision |
|---|---|---|---|
| [`blader/humanizer`](https://github.com/blader/humanizer/tree/9862685) | `9862685`, MIT | Humanizer 3.0.0 consolidates the earlier taxonomy to 25 patterns and adds explicit vague-association and previous-version guidance, stronger source preservation, voice precedence, and a broader contextual vocabulary list. | Adopt the source-preservation, vague-association, and previous-version guidance with local false-positive boundaries. Adapt taxonomy consolidation and voice precedence to Antislop's registry and operation contracts. Reject a wholesale vocabulary import, synonym-cycling removal, and false-range removal. |
| [`blader/humanizer`](https://github.com/blader/humanizer/tree/e2e92e7b4b8229253ed5c8e81dc65463fdeddda5) | `e2e92e7b4b8229253ed5c8e81dc65463fdeddda5`, MIT | Current source has 35 patterns, not the 29 stated in downstream credits. It gives sample voice precedence over generic style rules. | Use as a taxonomy and voice-precedence reference; correct stale count. |
| [`brandonwise/humanizer`](https://github.com/brandonwise/humanizer/tree/4b9b9bee384aea139f599133d2de1e1ceaee71a3) | `4b9b9bee384aea139f599133d2de1e1ceaee71a3`, MIT | Claims 560+ vocabulary entries, 28 detectors, and `5-20x` frequency without a published measurement method or dataset. Includes CLI, MCP, API, and tests. | Reference packaging; do not import the catalog or repeat statistics without measurement. |
| [`openclaw/openclaw`](https://github.com/openclaw/openclaw/tree/9ac61cdbab71ebba3a2f7ae9ffcbb6834a4afe32) | `9ac61cdbab71ebba3a2f7ae9ffcbb6834a4afe32`, MIT | Current repo contains a code-diff `deslop` skill, not a traceable prose humanizer. | Keep as distribution ecosystem only; clarify credit. |
| [`Aboudjem/humanizer-skill`](https://github.com/Aboudjem/humanizer-skill/tree/17bb5bbd74d4d7c5f3e5e7a93e1b97597eab3cf8) | `17bb5bbd74d4d7c5f3e5e7a93e1b97597eab3cf8`, MIT | Contains 55 patterns and the same five voice profiles. Some personality instructions are more aggressive than its later no-fabrication guardrails. | Credit as the apparent voice-profile source; adopt only with stronger provenance constraints. |
| [`isatimur/de-slop`](https://github.com/isatimur/de-slop/tree/4349a8af4116d6f02b38d62f4b19e66108c4aada) | `4349a8af4116d6f02b38d62f4b19e66108c4aada`, MIT | Strong subtract-and-sharpen, no-new-facts, idempotence, and smaller-edit rules. | Already substantially adopted in the current PR; keep. |
| [`NulightJens/humanizer-stack`](https://github.com/NulightJens/humanizer-stack/tree/13f5c023189d428ffba726c75886ca1fd0dcba65) | `13f5c023189d428ffba726c75886ca1fd0dcba65`, MIT for original work | StoryScope reports strong narrative-feature detection and small degradation after surface rewrite. This is long-fiction evidence, not validated short nonfiction transfer. | Reference for separate structural/aspect passes, not as proof for Antislop prose. |
| [`harshaneel/humanize`](https://github.com/harshaneel/humanize/tree/4ec797314537ec9c2105f276d4561d240a0390ba) | `4ec797314537ec9c2105f276d4561d240a0390ba`, MIT | Uses detector evasion, best-of-N detector scoring, disfluency injection, and hard shape constraints. | Reject adversarial evasion and fake-human disfluency. Research-map only. |
| [`jurigis/avoid-ai-writing-multilingual`](https://github.com/jurigis/avoid-ai-writing-multilingual/tree/4e5aa4c5123061cc7ef6f94147e77182ad8d8e6e) | `4e5aa4c5123061cc7ef6f94147e77182ad8d8e6e` | German, French, Italian, Romanian, and Swedish files with language-specific source notes. It claims native research rather than direct translation. | Adopt the process later with native maintainers, separate registries, and locale-specific evals. |
| [`ssot-check`](https://github.com/conorbronsdon/ssot-check/tree/82063c913e69da840510e475c27dc38e384f729e) | `82063c913e69da840510e475c27dc38e384f729e` | Deterministic copied-fact and documentation-drift checks. | Antislop's generator is better for local derivatives; adapt SSOT checks only for external copied counts and claims. |
| [`repo-audit`](https://github.com/conorbronsdon/repo-audit/tree/ec1b73485c442299f3c189afd4d4dd80b9a413e5) | `ec1b73485c442299f3c189afd4d4dd80b9a413e5`, Apache-2.0 | Useful distinction between enforced and advisory controls, plus self-proof and MCP review patterns. | Adapt audit methodology, not product code. |
| [Wikipedia: Signs of AI writing](https://en.wikipedia.org/w/index.php?oldid=1372013638&title=Wikipedia:Signs_of_AI_writing) | permanent revision `1372013638`, CC BY-SA 4.0 | Wikipedia-specific descriptive guidance, explicitly not proof of AI authorship and not a direction to erase tells mechanically. | Reference with attribution; review share-alike implications before copying expressive catalogs. |
| [Pangram guide](https://www.pangram.com/blog/ai-words) | accessed 2026-08-31, proprietary page | Large term list but no primary method on the page for individual frequency ratios. | Cite as research input only; do not copy catalog or assert thresholds as verified. |

### Licensing and attribution

The two mandatory repositories and most GitHub references use MIT. `repo-audit` uses Apache-2.0. Wikipedia content uses CC BY-SA 4.0. HC3 uses CC BY-SA 4.0, RAID uses MIT, and Gutenberg controls are public domain. Pangram's page is proprietary.

The upstream MIT license does not replace third-party attribution duties. If Antislop copies substantial text, tables, selection, or arrangement, preserve the relevant MIT notices and investigate Wikipedia share-alike obligations. Prefer independently expressed registry records backed by cited concepts and tests. The hash-only corpus design reduces redistribution risk and should be retained.

## Complete 50-file inventory: `avoid-ai-writing`

No tracked file is omitted. `Adopt` means the idea or file shape can be used substantially. `Adapt` means use after changing it for Antislop's architecture or evidence standard. `Reference` means retain as evidence only. `Reject` means do not import.

| File | Decision | Reason |
|---|---|---|
| `.claude-plugin/marketplace.json` | Adapt | Antislop already has marketplace metadata; compare fields and generate where possible. |
| `.gitattributes` | Adopt | Text-normalization control is portable. |
| `.github/FUNDING.yml` | Reject | Project-owner funding metadata is not transferable. |
| `.github/ISSUE_TEMPLATE/false_positive.yml` | Adopt | A structured false-positive intake directly supports rule calibration. Port to the repository's primary Forgejo workflow as appropriate. |
| `.github/PULL_REQUEST_TEMPLATE.md` | Adapt | Useful rule/evidence checklist, but align with Antislop's review gates. |
| `.github/workflows/detector-test.yml` | Adapt | Adopt jobs, not GitHub-only placement; Forgejo is primary. |
| `.github/workflows/plugin-skill-sync.yml` | Adapt | Drift enforcement is valuable, though Antislop should generate from its registry. |
| `.github/workflows/promo-drift.yml` | Reference-only | Only useful if Antislop publishes copied claims in external repositories. |
| `.github/workflows/release.yml` | Adapt | Reference release checks, but use Antislop's Forgejo-first release model. |
| `.gitignore` | Adapt | Adopt corpus-cache and local-output exclusions that match actual Antislop paths. |
| `.ssot.yaml` | Adapt | Use for copied external claims, not as a substitute for the registry generator. |
| `CHANGELOG.md` | Reference-only | Evidence for design evolution and source attribution; do not import history. |
| `CLAUDE.md` | Adapt | Repository instructions contain useful canonical-source and test commands, but client and architecture differ. |
| `CONTRIBUTING.md` | Adapt | Strong rule-addition, false-positive, and evidence workflow. |
| `LICENSE` | Reference-only | Preserve notice for copied MIT material. |
| `PROOF.md` | Adopt | Keep negative results and limitations visible; rerun against Antislop data before making claims. |
| `README.md` | Reference-only | Useful product and install surface, but pattern list is representative and several claims drift. |
| `SKILL.md` | Adapt | Primary rule source; too large and internally duplicated for Antislop's canonical architecture. |
| `corpus/README.md` | Adopt | Good acquisition, provenance, cache, and reproducibility documentation. |
| `corpus/manifest.json` | Adapt | Reuse schema and sources where licenses permit; rebalance registers and pin Antislop eval data. |
| `cursor-rules/README.md` | Adapt | Adopt generated Cursor installation guidance. |
| `cursor-rules/avoid-ai-writing.mdc` | Adapt | Generate an Antislop equivalent from the registry and skill template. |
| `detector/CATEGORIES.md` | Adopt | Strong category-to-engine coverage contract; recreate with Antislop IDs. |
| `detector/README.md` | Reference-only | Documents behavior, but its context list is stale and authorship framing is too strong. |
| `detector/categories.test.js` | Adopt | Coverage-contract test is directly useful. |
| `detector/patterns.js` | Adapt | Reuse masking, offsets, tiers, gates, and issue model concepts; reject authorship outputs. |
| `detector/patterns.test.js` | Adapt | Large fixture base is useful after translating rules and expected policy. |
| `detector/validate.js` | Adopt | Preservation validator fills a major Antislop gap. Extend semantic invariants. |
| `detector/validate.test.js` | Adopt | Port preservation cases and add citations, entities, negation, units, and modality. |
| `docs/demo.gif` | Reference-only | Upstream branding and behavior demonstration, not reusable product media. |
| `docs/social-preview.png` | Reject | Upstream-branded generated media. |
| `examples/README.md` | Adapt | Useful example contract; regenerate examples with Antislop behavior. |
| `examples/prose.json` | Adapt | Fixture shape is useful; expected scores are detector-specific. |
| `examples/technical.json` | Adapt | Useful context fixture; expand legitimate-term counterexamples. |
| `package.json` | Reference-only | Zero-runtime-dependency detector packaging is attractive, but Antislop needs its own package design. |
| `plugins/avoid-ai-writing/.claude-plugin/plugin.json` | Adapt | Antislop has a manifest; compare naming, version, and generated metadata. |
| `plugins/avoid-ai-writing/skills/avoid-ai-writing/SKILL.md` | Reference-only | It is a byte-identical distribution derivative. Generate artifacts instead of hand-maintaining copies. |
| `scripts/check-pattern-count.sh` | Adopt | Small deterministic claim-drift gate; translate counts to registry-derived assertions. |
| `scripts/check-style.js` | Adapt | Keep deterministic mechanics checks and explicit advisory boundaries. |
| `scripts/check-style.test.js` | Adapt | Port fixtures for configured mechanics. |
| `scripts/corpus.js` | Adapt | Useful hashed corpus acquisition and evaluation harness. |
| `scripts/corpus.test.js` | Adapt | Port provenance, hashing, and evaluation helper tests. |
| `scripts/csv-lite.js` | Reference-only | Dependency-free CSV helper is only useful if Antislop adopts the same datasets. |
| `scripts/dataset-hc3.js` | Adapt | Retain attribution and dataset license; reassess relevance and sampling. |
| `scripts/dataset-raid.js` | Adapt | Retain license and sampling controls; use for style evaluation, not evasion. |
| `scripts/fp-measure.js` | Adopt | False-positive measurement should become a required rule gate. |
| `scripts/promo-drift-report.py` | Reference-only | Useful only for cross-repository promotional copies. |
| `scripts/self-scan.js` | Adopt | Repository self-scan budgets expose dogfooding drift. Calibrate against meta-context. |
| `scripts/sync-cursor-rules.sh` | Adopt | Strong generated-port pattern with explicit portability rewrites. |
| `scripts/sync-plugin-skill.sh` | Adapt | Keep synchronization enforcement, but prefer a single generator over full duplicate sources. |

## Complete 11-file inventory: `avoid-ai-writing-mcp`

| File | Decision | Reason |
|---|---|---|
| `.gitattributes` | Adopt | Portable text-normalization control. |
| `.gitignore` | Adapt | Use only paths relevant to Antislop's package layout. |
| `CHANGELOG.md` | Reference-only | Records package behavior and version history. |
| `LICENSE` | Reference-only | Preserve MIT notice if code is copied. |
| `README.md` | Adapt | Good tool-contract documentation, but remove authorship-probability claims and document version parity. |
| `RELEASING.md` | Adapt | Useful manual release checklist if Antislop publishes an npm/MCP package. |
| `package-lock.json` | Adapt | Regenerate this output from Antislop's package and pinned dependency policy. |
| `package.json` | Adapt | Keep Node/MCP packaging shape; do not pin an obsolete detector or inherit authorship schema. |
| `src/index.js` | Adopt | Minimal stdio entry point is appropriate. |
| `src/server.js` | Adapt | Keep read-only tools, caps, annotations, and compact/detail split; remove classification probabilities. |
| `test/server.test.js` | Adapt | Port behavior and annotation tests; add detector-version parity and schema tests. |

## Adoption plan

### Adopt now

1. Land or align with the typed-rule foundation for policy, heuristic, preference, structural guidance, evaluation, positive guidance, repair, profile, and tooling records.
2. Record the five voice profiles and six context profiles as proposed profile axes, with explicit precedence and no-fabrication constraints.
3. Extend the registry schema for replacements, variants, tier, density, scope, evidence, examples, counterexamples, and detector status.
4. Add a 69-category coverage matrix without claiming every category is executable.
5. Add false-positive issue intake and require counterexamples for new lexical rules.
6. Port preservation validation and rendered-Markdown masking before adding rewrite automation.
7. Generate a Cursor rule and enforce derivative drift.
8. Add the strongest missing mechanical categories: hashtag stuffing, bare-noun bullet lists, list-label mechanics, novelty inflation, social closers, wall-of-text, recap-flattery, diff-anchored prose, and dev-blog boilerplate.
9. Reclassify the absolute em-dash rule as Antislop house style. Upstream evidence does not support it as an authorship marker.

### Adopt after evaluation

1. Migrate Tier 1B clarity rows with replacements and register exceptions.
2. Trial Tier 1A, Tier 2, and Tier 3 rows against a balanced Antislop corpus. Require per-rule false-positive budgets.
3. Implement paragraph and discourse analyzers for cluster, density, opener-run, triple, treadmill, and reshuffle behavior.
4. Publish a read-only MCP or local scanner only after registry/scorer parity, preservation tests, input gates, and stable highlighting.
5. Add multilingual variants only with native contributors, language-specific registries, primary sources, and separate evaluations.
6. Add ClawHub packaging only after verifying the live installation command and update path.

### Reject

1. Trinary authorship labels and probability fields.
2. Claims that individual terms are `5-20x` more common without a reproducible measurement.
3. Detector-evasion loops, best-of-N optimization against detectors, and injected disfluency.
4. An unconditional import of all 112 rows as exact bans.
5. A single monolithic combined rewrite-and-audit skill.
6. Treating the 56-item README reference as the full 69-category catalog.
7. Treating plugin installation as tool installation.
8. GitHub-only workflow placement in a Forgejo-primary repository.

## Acceptance criteria for a follow-up implementation

An adoption PR should not be called complete until:

- every imported row has a stable ID, source, action, examples, counterexamples, and scope;
- the registry generates every human and client reference without hand-edited drift;
- all scorer-supported rules appear in a coverage contract and all unsupported semantic rules are labeled manual;
- voice and context are independently selectable and tested in combination;
- preservation failures block rewrite acceptance;
- short, long, quoted, code-heavy, and rendered-Markdown inputs have fixtures;
- false-positive results are reported by register;
- tool outputs avoid authorship claims;
- detector, MCP, and generated client artifacts share a checked version;
- licensing and attribution notices cover copied MIT and CC BY-SA material.

## Bottom line

The upstream repository is better than the current Antislop PR in operational depth: it has voice and context controls, tiered replacements, a full pattern taxonomy, masking, preservation validation, corpus controls, tests, distribution artifacts, and a separate tool server. Antislop is better positioned architecturally because it already has a machine-readable atomic registry and generated reference artifacts.

The right move is to adopt upstream's metadata model, safety boundaries, tests, and packaging patterns into Antislop's registry-first design. Do not adopt its weak authorship inference or flatten context-sensitive terms into absolute bans. The current PR should be described as an initial selective adaptation, with the work above tracked as the full follow-up.
