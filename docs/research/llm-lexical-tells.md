# LLM lexical tells: design and research WIP

Status: design first. No production rule is proposed for immediate merge.

Date: 2026-09-17

Issue: [Forgejo #167](https://git.drunkrhin0.au/drunkrhin0/antislop/issues/167)

## Decision in one paragraph

Antislop should adopt **LLM lexical tells** as the user facing name. Use
`llm_lexical_tells` as the internal rule family. The name describes a signal
that can make prose sound model shaped. It does not claim that a passage was
written by a model, and it does not turn a vocabulary list into a grammar or
readability checker.

The feature should be an evidence bearing extension of the existing rule
registry. It should not be a second global blacklist. A candidate record needs
the term or construction, its context, the observed model families, the source
and sample size, a first seen date, a review date, a decay policy, a false
positive note, and a treatment. The initial score remains zero for this class.
An experimental report may present contextual candidates after validation.
This WIP activates no findings and changes no score.

That position is deliberate. The evidence currently measures model preference
and corpus association. It does not provide a human baseline or an authorship
test. Both facts must remain visible in the data and in every finding.

## What the evidence actually says

The companion [SpeechMap source review and model map](speechmap-model-map.md)
records dated measurements, sample sizes and source links. It separates model
preferences from our assessment of slop relevance. Its results support a
watchlist and contextual experiments, not immediate production flags.

The [Pydantic linguistic drift report](https://pydantic.dev/articles/linguistic-drift-at-the-frontier)
is a useful independent observation about `seam`. It reports 685,143 GitHub
pull requests mentioning the word in 2026 through 2 September, after about
15,000 before 2026. The report says `Claude Code` appeared in 45% of those
PR bodies versus 12.5% of all 2026 PRs, and `Codex` in 17.5% versus 5.8%.
The author describes the search as an investigation assisted by Fable 5.1.
The counts are not a controlled authorship sample, and the attribution marker
is not proof that a model introduced the word. Treat this as strong drift and
association evidence with a clear methodological limit.

SpeechMap similarity means similar deviations from the corpus average. It does
not establish shared wording, copying, or model lineage.

## Terminology and boundaries

Use these terms consistently.

| Term | Meaning in this design |
| --- | --- |
| LLM lexical tell | A word, phrase, or construction with evidence of model overuse and a context that can make prose sound synthetic. |
| Model preference | A higher rate for one model or family than a matched baseline. |
| Contextual slop relevance | A judgment that a use is an abstract, repeated, or unearned metaphor in this passage. |
| Fingerprint evidence | Measurement of a model's distinctive vocabulary. It is not an authorship classifier. |
| Production treatment | The action allowed by the rule registry: flag, weighted signal, contextual pattern, observe, or reject. |

Among `llm_lexical_tells`, `llm_associated_slop`, `llm_wording_tells`, and
`frontier_drift`, the first is clearest and least likely to imply authorship or
a blacklist. Use it for the rule family.

The detector should require evidence on both axes before it creates a user
facing finding. A high rate for a word such as `said` or `ordinary` has little
slop relevance. A plausible metaphor such as `surface` can have slop relevance
without enough model evidence for production. The two cases belong in
different queues.

## Fit with Antislop 3

The architecture audit uses [revision 6598ff7](https://git.drunkrhin0.au/drunkrhin0/antislop/src/commit/6598ff767fa527da1225e7e3587001dd3d11fc75), inspected through Forgejo. The local checkout predates Antislop 3.
The WIP branch starts at that audited revision.

`rules.json` remains the canonical 3.0.0 registry. Its existing `evidence_meta`
fields and `review_queue` are the right home for candidate provenance. The
provenance validator should reject a candidate that lacks a source, review
date, treatment, or confidence rationale. A candidate can be present in the
queue without being active in production.

The design choices have different costs:

| Option | Assessment |
| --- | --- |
| Append unconditional vocabulary bans | Simple, but cannot express the required technical exceptions. Reject. |
| Add a separately scored category | Makes the feature visible but duplicates overlapping findings and promotes weak evidence too early. Defer. |
| Add candidate observations within the existing registry and provenance system | Recommended. Keeps evidence review separate from active rules and reuses existing validation. |
| Build a separate detector service | Adds deployment and maintenance without demonstrated need. Reject. |

Exact and phrase matchers can retrieve candidate spans. They cannot decide
whether a metaphor is earned merely because context fields exist. A later
implementation must add a tested context evaluator or retain human review.
The schema below is proposed, not currently accepted by the registry validator.
Keep the root review queue separate from individual candidate records.

A conceptual record shape is:

| Field | Purpose |
| --- | --- |
| `id` and `term` | Stable identity and the surface form. |
| `variants` | Inflections such as `seam` and `seams`. |
| `contexts` | Literal exclusions, abstract collocations, and required nearby terms. |
| `model_families` | Exact observed model IDs and variants. Family attribution alone is insufficient. |
| `first_seen` and `observed_at` | Earliest evidenced occurrence and this observation date. Use null when unknown, never infer first occurrence from a release date. |
| `treatment` | `strong_flag`, `weighted_signal`, `contextual_pattern`, `observe`, or `reject`. |
| `weight` | Zero until a calibration run justifies a nonzero value. |
| `evidence_meta` | Class, source, first seen, last reviewed, confidence, sample, and decay. |
| `review_status` | Proposed candidate disposition. Link to the existing root review queue rather than creating a nested queue. |

`score.py` currently forces advisory finding weights to zero and only scans
forbidden or discouraged semantic types. A metadata-only candidate must stay
outside the active rule set. Numeric candidate weights cannot override this
contract. Any future scored treatment requires an explicit rule decision and
calibration, not a silent change to advisory semantics.

`scan.py` routes exact and phrase matches through its lexical stage and
registered structural detectors through its structural stage. A new contextual
matcher therefore needs an explicit integration path. Merely declaring it
`pattern_match` will not make it run in both stages.

`scan.py` masks fenced and inline code before matching. The lexical path should
reuse that code only behavior and retain raw input for excerpts. `score.py`
continues to score raw input. Whether URLs, quotes, or supplied domain terms
receive protection must be established through the current public interface's
tests, not assumed from this design. Lexical findings should not enter the
structural intervention budget. The existing structural detector keeps its
`structural` class and its maximum of two interventions.

The existing `vocab-dispatch` rule is a separate legacy behavior. Keep its
current deterministic behavior until a migration decision is made. Do not
promote `dispatch` into a new global ban. Its high Fable ratio is interesting,
but the word is ordinary in message queues, operating systems, HTTP clients,
and task runners.

The existing `struct-awkward-metaphors` rule is the right secondary review
point for unearned abstractions. A lexical tell may supply candidate context
to that review. It should not duplicate the rule or bypass its technical
exception for real concepts such as substrate and scaffolding.

## Candidate lexicon

The treatment column is a recommendation for this design. Measurements and
source links are in the [model map](speechmap-model-map.md), with aggregate
drift observations from the [index](https://speechmap.ai/experiments/vocab/).
Inflections without their own measurement remain hypotheses. `Established` means
the measured preference recurs across observed releases.
`Emerging` means it is current and plausible but needs another corpus or
release to establish persistence. `Obsolete` requires evidence of disappearance in the relevant corpus. Age alone
does not establish obsolescence. Unmeasured candidates have unknown temporal status.

### Candidate assessments

| Candidate | Associated model or source | Evidence and status | False positive risk | Treatment |
| --- | --- | --- | --- | --- |
| `seam`, `seams` | Claude lineage, Fable, then diffusion | Pydantic GitHub observation. Emerging, strong association. | High for physical, textile, database, and Feathers terminology. | Contextual pattern only. |
| `gate`, `gated`, `gating` | Agent and coding prose; proposal observation | No matched ratio in the anchor sources. Emerging hypothesis. | High in access control, feature flags, and release systems. | Observe until corpus evidence; later contextual pattern. |
| `spike` | Fable and Claude engineering prose; proposal observation | Independent matched measurement not located. Emerging hypothesis. | High in agile work, load tests, and sudden measurements. | Observe only. |
| `roughly` | Fable 5.1 and cross model index | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in honest estimates and scientific prose. | Contextual or cluster signal only. |
| `interlocking` | Fable 5.1 and GLM 5.3 | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | Medium to high in literal mechanisms and institutional analysis. | Observe; pattern only with abstract nounification. |
| `completeness` | Fable 5.1 and Kimi K3 | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in test coverage and formal specifications. | Contextual phrase only, such as unearned completeness claims. |
| `dispatch` | Fable 5 and 5.1; legacy rule | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | Very high in real systems terminology. | Keep legacy rule separate; observe as drift candidate. |
| `bounded` | DeepSeek V4.1 Flash | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in algorithms, resource limits, and formal methods. | Contextual pattern only. |
| `structurally`, `structural` | Cross-model index | Index reports structurally rising from 3 to 20/M. Current corpus drift; generalisation unvalidated. | High in architecture, linguistics, and mathematics. | Contextual or cluster signal only. |
| `epistemic` | Cross-model index | Index reports 3 to 16/M. Current corpus drift, no exact model attribution established here. | High in philosophy, research, and uncertainty discussions. | Observe; pattern only beside meta-analysis. |
| `architecture`, `architectural` | Cross-model index | Index reports architecture rising from 14 to 51/M. No separate architectural measurement. | Very high in actual software architecture. | Contextual pattern only when used as a vague metaphor. |
| `contested` | Current cross model index; Claude proposal | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in law, politics, and factual disputes. | Observe only. |
| `comparative` | Claude Sonnet lineage | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in research writing and comparative analysis. | Observe only. |
| `logic` | Claude Sonnet lineage | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | Very high as a normal noun in programming and argument. | Reject as a lexical flag; retain phrase research. |
| `framed`, `framing` | OpenAI lineage and model map | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in media analysis and ordinary description. | Contextual pattern only. |
| `strongest` | OpenAI lineage and cross model index | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | Very high in normal comparison and optimization. | Reject as a single word; observe collocations. |
| `ordinary` | OpenAI lineage and model map | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | Very high in ordinary English. | Reject as a lexical flag. |
| `clarified`, `clarify` | OpenAI and Qwen model pages | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | Very high in editing and support work. | Observe only. |
| `treat`, `treats` | Cross model index and xAI lineage | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | Very high as a basic verb. | Reject as a single word. |
| `strand` | DeepSeek V4.1 Flash and proposal for newer Claude | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in narrative, biology, cables, and argument threads. | Observe; contextual pattern only in abstract system prose. |
| `legible` | Qwen 3.8 27B reasoning page and proposal | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in typography, access, and real design reviews. | Observe only. |
| `conflates`, `conflation` | Qwen 3.8 and MiniMax M3 reasoning | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in legitimate criticism and analysis. | Observe; phrase pattern only with canned contrast. |
| `recast`, `analogize`, `analogized` | Grok 4.6 | Current corpus preference where measured in the model map; persistence unvalidated. Index-only rows remain provisional. | High in literary and explanatory prose. | Model specific observe only. |

### Contextual and construction candidates

These terms are ordinary words. Their value, if any, comes from a repeated
abstract use that displaces a concrete mechanism. For every row below, model
attribution and emergence date remain unknown, direct lexical evidence is weak,
and false-positive risk is high. Contextual treatment means a research direction,
not an enabled finding. Lack of detail alone is not an LLM-specific defect.

| Candidate | Suspicious context worth testing | Normal use to protect | Treatment |
| --- | --- | --- | --- |
| `surface` | `authorization surface`, `verification surface`, or repeated abstract surfaces | Geometry, materials, APIs, and user interface surfaces | Contextual pattern only. |
| `boundary` | `the boundary of trust` with no actor, data, or operation | Type boundaries, geographic limits, and explicit interfaces | Contextual pattern only. |
| `scaffold`, `scaffolding` | Generic prose scaffold with no temporary mechanism | Construction, test scaffolds, and named technical methods | Route to awkward metaphor review. |
| `invariant` | `preserve the invariant` without stating the invariant | A defined mathematical or program property | Require a nearby definition; otherwise review. |
| `shape` | `failure shape`, `risk shape`, or `the shape of the system` without a measurable property | Data shape, geometry, schema, and API shape | Contextual pattern only. |
| `handoff` | `clean handoff` used as a vague quality claim | A named transfer between owners or systems | Require named sender and receiver. |
| `posture` | `security posture` without controls, threat, or state | A measured security state or organizational stance | Mechanism check plus context. |
| `substrate` | Abstract substrate used as a prestige metaphor | A named runtime, storage, or physical layer | Route to awkward metaphor review with technical exception. |
| `envelope` | `failure envelope` or `capability envelope` without bounds | Statistical, networking, and engineering envelope | Require explicit bounds or observe. |
| `rail` | `guardrail` or `rail` with no constrained action | A real policy, workflow, or physical rail | Require the constrained action. |
| `tripwire` | Generic warning that a tripwire exists | A specific automated check and trigger | Require trigger and consequence. |
| `authority` | Abstract authority boundary without owner or permission | An identified principal or source of authority | Require actor and operation. |
| `contract` | `contract` used as a universal synonym for any relationship | API, schema, or legal contract with terms | Require named parties and terms. |
| `localize`, `mechanical`, `mechanically` | Abstract verbs that hide the operation or actor | A real localization or mechanical procedure | Mechanism check; do not flag alone. |

### Corpus artifacts and false leads

The companion map includes ordinary words as counterexamples to automatic
promotion. Corpus distinctiveness alone does not establish slop relevance.

The current vocabulary registry contains older entries such as `delve`,
`leverage`, `tapestry`, and `dispatch`. Other older terms named in the proposals were not verified against
the current registry here. Keep existing entries under their current rules,
but do not use old-list membership as evidence of frontier drift.

## Model coverage and evidence gaps

The companion [SpeechMap source review and model map](speechmap-model-map.md)
carries the per model table. It covers Claude Opus, Sonnet, Fable, GPT-5.x,
Grok, GLM, Qwen, DeepSeek, Gemini, Mistral, Magistral, Kimi, MiniMax, Meta
Muse Spark, and other current entries. Its gaps are material: no controlled
Astra lexical page was found, and several requested variants have only index
rows. The proposals' Astra guidance is therefore not cited.

Within SpeechMap, `muse-spark-1.1` and `muse-spark-1.3` are Meta model IDs.
Other products use the name Muse, so the registry must record provider and
exact model ID rather than a bare family label. The map records Muse Spark's measured preferences without treating them as bans.

## Phrase and structure detection

The useful unit is often a construction, not a token. Test abstract coupling
(`seam between` two components), control nounification (`gate`, `boundary`,
`rail`, or `tripwire` without a named action), universal abstraction (`system's
surface`, `failure shape`, `security posture` without a property), empty
boundedness (no bound or termination condition), undefined invariant, and
handoff ceremony without sender, receiver, artifact, or acceptance condition.
Also test invented adjective plus noun labels and local clustering. Any window
size or count threshold is an experimental hypothesis until calibrated. The
Astra attribution for compound labels is unverified.

Each pattern needs a literal counterexample fixture. `The two metal surfaces
meet at the seam` must pass. `The parser seam joins the token and AST layers`
may also be valid when the project defines that term. A pattern that cannot
explain its technical exception is too broad for production.

## Proposed initial production set

The new production set is intentionally empty in this WIP. Put all candidates
in `review_queue` with `weight: 0` and treatment `observe` or
`contextual_pattern`. An experiment can report `seam`, `gate`, `surface`,
`boundary`, `shape`, `bounded`, and `handoff` only after it has paired literal
and abstract fixtures. No candidate rewrites text. Keep `dispatch` under its
existing legacy rule and do not duplicate it.

Do not activate `spike`, `roughly`, `interlocking`, `completeness`, or any
model specific candidate globally. Promotion requires measured preference,
slop relevance, human controls, and a calibrated threshold.

## Tests before any score change

The first implementation should reuse paired fixtures through the public scan
and score interfaces. Literal seams and surfaces, network gates, queue
dispatch, and defined invariants must produce no new lexical-tell finding.
The legacy dispatch rule may still fire until a separate migration. Only
validated problematic contexts should report excerpts and source metadata. A single `roughly`,
`structurally`, or `ordinary` must not change a score. Any clustering rule must
remain experimental. Add explicit tests for code masking and separately test
how the current interface handles URLs, quotes, and domain terms. Provenance
must reject missing evidence, while legacy `vocab-dispatch` behavior remains
unchanged.

Before changing a score, collect labelled human passages from software,
research, fiction, support, and correspondence. Stratify literal and abstract
senses, hold out projects and model families, and report precision and false
positive rate by domain. A model corpus cannot stand in for human controls.

## Review and decay policy

Every candidate needs a source, evidence note, measured rate, baseline,
response and domain counts, corpus date, source type, model association, and a
separate prose-context judgment. Unknown rates or dates must remain unknown.
A 30-day emerging-candidate review, extending to 90 days after independent
replication, is a proposed maintenance cadence rather than an empirical threshold.
No automatic monitoring is configured in this PR. When evidence decays,
set its state to `stale` and move it to the review queue. The rule stays active
until a human disables it, and the history is preserved.

The queue asks whether model preference persists, whether the usage obscures a
concrete claim, whether literal and technical exceptions have fixtures, and
whether the least aggressive treatment still works. A candidate that cannot
answer all four stays in observation, even with a dramatic ratio.

## Recommendation

Create `llm_lexical_tells` as a provenance rich, zero weight, context aware
registry extension. Keep old bans and domain exceptions separate. Activate only
after human controls, paired fixtures, and a calibrated threshold exist.

## Sources

- [SpeechMap Lexical Fingerprints index](https://speechmap.ai/experiments/vocab/)
- [SpeechMap Claude Fable 5.1 fingerprint](https://speechmap.ai/experiments/vocab/m/anthropic-claude-fable-5-1/)
- [SpeechMap DeepSeek V4.1 Flash fingerprint](https://speechmap.ai/experiments/vocab/m/deepseek-deepseek-v4-1-flash/)
- [SpeechMap Meta Muse Spark 1.1 fingerprint](https://speechmap.ai/experiments/vocab/m/meta-muse-spark-1-1/)
- [SpeechMap Grok 4.6 fingerprint](https://speechmap.ai/experiments/vocab/m/x-ai-grok-4-6/)
- [Pydantic: Linguistic drift at the frontier](https://pydantic.dev/articles/linguistic-drift-at-the-frontier)
