# SpeechMap source review and model map

Status: WIP research, reviewed 17 September 2026. Related: [issue #167](https://git.drunkrhin0.au/drunkrhin0/antislop/issues/167) and [lexical-tells design](llm-lexical-tells.md).

## Recommendation

Use SpeechMap as a source of model-specific lexical observations. Keep a second, independently reviewed assessment of whether each usage is a useful Antislop finding. A high frequency ratio is insufficient grounds for a ban.

This map covers selected versions from the requested model families. It does not reproduce the entire historical catalogue. All treatment decisions below are recommendations for this project, not conclusions made by SpeechMap.

## Source record

| Field | Recorded value |
|---|---|
| Source | [SpeechMap Lexical Fingerprints](https://speechmap.ai/experiments/vocab/) |
| Evidence type | Primary observational corpus analysis |
| Review date | 2026-09-17 |
| Index snapshot | 390 models, 508,422 COMPLETE answers, 2,120 questions |
| Intended use | Candidate discovery and comparison between model versions |
| Production effect | None in this PR |
| Reproduction status | Published pages inspected. Corpus and calculation code not independently rerun |
| Snapshot limitations | Live pages and search caches can represent different comparison-pool revisions |
| Redistribution | Link and summarise selected results. Dataset licence and bulk reuse terms remain unverified |

The index describes a deliberately restricted set of sensitive and controversial prompts. Its rates average within-response word frequencies. The comparison is with other models, not with human prose. These facts limit what Antislop can infer from the numbers. [Index](https://speechmap.ai/experiments/vocab/)

The wider project examines refusal and response behaviour. Its homepage reports roughly 826,000 responses, a different population from the COMPLETE-only vocabulary sample. Do not substitute that larger count in lexical evidence records. [Project description](https://speechmap.ai/)

## What the measurements do and do not establish

The model pages describe matched-question comparison, exclusion of prompt echoes, and screening that requires a candidate to occur in at least 15 answers across six topic domains. These controls are useful: a word repeated from one question is a weaker lead than a preference spread across domains. They are source methodology, not proposed Antislop thresholds. [Fable 5 methodology](https://speechmap.ai/experiments/vocab/m/anthropic-claude-fable-5/)

Our assessment of the remaining limitations:

- COMPLETE-only selection removes refusals from the measured text, but models complete different subsets of questions. Inspect matched coverage before comparing their summary ratios.
- Topic variety within this benchmark does not substitute for technical manuals, ordinary correspondence or human literary writing.
- Per-response averaging gives short and long responses equal response-level influence. It is not pooled token frequency.
- Distinctiveness against other models cannot establish distinctiveness against humans. A preference shared by every model may also disappear from a model-specific ranking.
- A ratio against a small baseline can be large even when few responses contain the word. Record response and domain counts beside it.
- Prompt matching does not control differences in answer genre, reasoning settings or model-generated story content.
- Top-candidate selection creates a discovery set. Use held-out data for validation rather than testing only the selected examples.
- Similarity between models cannot establish training lineage, copying, distillation or the author of an arbitrary passage.
- No calibrated human false-positive rate or uncertainty interval was established in this review.

## Two independent axes

| Axis | Question | Example | Consequence |
|---|---|---|---|
| Lexical preference | Does this exact model use the term more often than its comparison models here? | Fable 5.1 uses roughly at a reported 13.1 times the matched baseline | Record the observation |
| Slop relevance | Does a specific usage introduce a recognisable, unnecessary synthetic pattern? | Several abstract metaphors obscure the actual component interaction | Collect paired examples and review the construction |
| Production suitability | Does a tested detector identify that problematic usage while preserving legitimate prose? | A literal measurement using roughly remains untouched | Requires separate local evidence |

The last two rows describe proposed Antislop decisions. They cannot be computed from the first row alone.

## Model map

N is the number of COMPLETE responses on the inspected model page. Ratios are the site's reported multiples, retained as displayed rather than recalculated from rounded rates. A missing ratio means it was not verified, not that the term is absent. Model identifiers below are SpeechMap identifiers, not a claim about current vendor API availability.

| Model or variant | N | Selected measured preferences | Slop assessment and proposed treatment | Source |
|---|---:|---|---|---|
| Claude Fable 5.1 | 1,535 | roughly 13.1x; completeness 14.1x; dispatch 13.4x; interlocking 9.6x | Strong discovery leads. Review abstract completeness/interlocking constructions. Keep estimates and technical dispatch usage. No standalone flags | [Model page](https://speechmap.ai/experiments/vocab/m/anthropic-claude-fable-5-1/) |
| Claude Fable 5 | 1,374 | dispatch 38.3x; gesturing 12.1x | Compare dispatch senses across versions. Legitimate event dispatch and physical gestures remain clean | [Model page](https://speechmap.ai/experiments/vocab/m/anthropic-claude-fable-5/) |
| Claude Opus 5 | 1,252 | strand 29.2x; roughly 18.0x; tractable 17.0x | Strong lexical preferences, high false-positive risk. Strand metaphors merit usage review. Mathematical tractability does not | [Model page](https://speechmap.ai/experiments/vocab/m/anthropic-claude-opus-5/) |
| Claude Sonnet 5 | Not verified | Lineage endpoint: contested 921/M; comparative 155/M; logic 413/M | These are family-aggregated rates, not matched-baseline ratios for one exact variant. Observe only | [Lineage page](https://speechmap.ai/experiments/vocab/lab/anthropic/) |
| GPT-5.6 Sol | 972 | ordinarily 66.6x; narrower 16.1x; defensible 14.6x | Ordinary qualifiers and analytical terms. Require contextual evidence before any review signal | [Model page](https://speechmap.ai/experiments/vocab/m/openai-gpt-5-6-sol/) |
| GPT-5.6 Terra | 938 | ordinarily 16.9x; ordinary 8.3x; narrower 7.0x | Keep distinct from Sol. No case for treating ordinary as a standalone defect | [Model page](https://speechmap.ai/experiments/vocab/m/openai-gpt-5-6-terra/) |
| GPT-5.6 Luna | 1,111 | objected 56.6x; ordinarily 12.6x | Reporting verbs can reflect answer genre. Observe only, with no global rule | [Model page](https://speechmap.ai/experiments/vocab/m/openai-gpt-5-6-luna/) |
| Astra | Not available | No Astra entry found in the reviewed index | Record coverage gap. Do not transfer GPT-5.6 ratios to Astra | [Index](https://speechmap.ai/experiments/vocab/) |
| Grok 4.6 | 1,773 | analogized 83.3x; recast 37.6x; residual 18.2x | Inspect analogy-heavy passages, but preserve real analogies and statistical residuals | [Model page](https://speechmap.ai/experiments/vocab/m/x-ai-grok-4-6/) |
| GLM 5.3 | 1,515 | interlocking 15.1x; roughly 14.0x; deadpan 49.0x | Shows candidates are not exclusive to Fable. Deadpan is valid in narrative description | [Model page](https://speechmap.ai/experiments/vocab/m/z-ai-glm-5-3/) |
| Qwen 3.8 Flash | Not verified | Index lists conflates among signature terms | Detailed page unavailable to this review. Observe only; do not invent a ratio | [Index](https://speechmap.ai/experiments/vocab/) |
| Qwen 3.8 27B reasoning | Not verified | Index lists legible among signature terms | Keep reasoning variant separate. No numeric strength established here | [Index](https://speechmap.ai/experiments/vocab/) |
| DeepSeek V4.1 Flash | 1,116 | bounded 7.0x; strand 8.3x; strongest 5.4x | Bounded has measured support as a preference here. Technical bounds remain valid. Review metaphorical usage separately | [Model page](https://speechmap.ai/experiments/vocab/m/deepseek-deepseek-v4-1-flash/) |
| Gemini 3.8 Flash | 1,825 | acoustic 15.3x; ambient 14.0x; perimeter 12.1x | Useful counterexamples to automatic promotion: these can be exact domain terms. Observe only | [Model page](https://speechmap.ai/experiments/vocab/m/google-gemini-3-8-flash/) |
| Kimi K3 | 1,398 | completeness 14.1x; roughly 11.8x; canonical 17.5x | Completeness is not exclusive to Fable. Review generic completeness claims; preserve defined acceptance conditions | [Model page](https://speechmap.ai/experiments/vocab/m/moonshotai-kimi-k3/) |
| MiniMax M3 reasoning | 1,071 | conflation 7.4x; strands 7.0x; approximately 5.0x | Distinguish a real conflation from formulaic argument framing. Estimates remain legitimate | [Model page](https://speechmap.ai/experiments/vocab/m/minimax-minimax-m3-reasoning/) |
| Mistral Medium 3.5 2604 | Not verified | Index lists elaboration | Detailed page unavailable. No production recommendation from an index listing | [Index](https://speechmap.ai/experiments/vocab/) |
| Magistral Medium 2506 thinking | Not verified | Index lists boxed and markdown | Formatting and answer-format artifacts are weak prose-quality evidence. Historical comparison only | [Index](https://speechmap.ai/experiments/vocab/) |
| Meta Muse Spark 1.3 | 548 | nodded 15.9x; bravely 9.5x; clarified 6.2x | Muse here means the Meta model identified by SpeechMap. Keep narrative verbs and valid reported speech | [Model page](https://speechmap.ai/experiments/vocab/m/meta-muse-spark-1-3/) |
| Llama 4 Maverick | Not verified | Index lists stalwarts | Additional historical comparator. Detailed page unavailable, no ratio or production claim | [Index](https://speechmap.ai/experiments/vocab/) |

The Qwen, Mistral, Magistral, Sonnet and Llama detail-page requests returned retrieval cache misses. The table preserves the smaller verified claim instead of filling those gaps from memory. Most reasoning siblings are not separately reviewed here.

## Selected observations with denominators

These are transcribed measurements for prioritising follow-up. They are not detector weights.

| Model and term | Model /M | Others /M | Reported multiple | Responses containing term | Topic domains |
|---|---:|---:|---:|---:|---:|
| Fable 5.1: roughly | 404.5 | 30.7 | 13.1x | 453 | 21 |
| Fable 5.1: completeness | 32.9 | 2.1 | 14.1x | 44 | 17 |
| Fable 5.1: dispatch | 63.1 | 4.5 | 13.4x | 72 | 18 |
| Fable 5.1: interlocking | 20.1 | 1.9 | 9.6x | 28 | 13 |

Source: [Fable 5.1 model page](https://speechmap.ai/experiments/vocab/m/anthropic-claude-fable-5-1/). The supplied ChatGPT context gave 13.2x, 14.2x and 9.7x for three of these terms. This review records the currently displayed values. Whether the discrepancy comes from a changed baseline, cached revision or transcription is unresolved.

| Model and term | Model /M | Others /M | Reported multiple | Responses containing term | Topic domains |
|---|---:|---:|---:|---:|---:|
| DeepSeek V4.1 Flash: bounded | 56.8 | 7.9 | 7.0x | 40 | 12 |
| DeepSeek V4.1 Flash: strand | 30.6 | 3.5 | 8.3x | 21 | 12 |

Source: [DeepSeek model page](https://speechmap.ai/experiments/vocab/m/deepseek-deepseek-v4-1-flash/).

The displayed multiples do not always equal the quotient of the rounded rate columns. Record the site's multiple as reported. Verify its precise calculation before using it in an automated import.

## Version drift needs a separate record

The lineage pages average near-simultaneous variants, including reasoning siblings, with equal weight per model. A lineage point must not be represented as a measurement of one exact variant. [Anthropic lineage methodology](https://speechmap.ai/experiments/vocab/lab/anthropic/)

For Sonnet, contested rises from 12 to 921/M between the first and last listed families. Roughly is non-monotonic: 207/M at 4.6, then 98/M at 5. A claim that every newer generation increasingly uses it would be wrong. [Anthropic lineage](https://speechmap.ai/experiments/vocab/lab/anthropic/)

The OpenAI lineage lists ordinary rising from 31/M at GPT-4 to 533/M at 5.6. Framed reaches 1,036/M at 5.2 and falls to 156/M at 5.6. Those are distinct trends, and neither establishes a universal current-model ban. [OpenAI lineage](https://speechmap.ai/experiments/vocab/lab/openai/)

## Slop review priorities

These priorities are project judgments based on the evidence above.

| Priority | Candidate usages | What would justify an Antislop finding | Clean counterexample |
|---|---|---|---|
| Review first | Abstract interlocking, strand, completeness | Repeated generic constructions replace an explainable relationship or add unsupported claims | The two gears have interlocking teeth |
| Review first | Abstract bounded and metaphor clusters | Usage repeatedly suggests a limit without specifying one, obscuring the intended claim | The queue is bounded to 100 items |
| Investigate independently | Seam, gate and spike | Context demonstrates indiscriminate metaphor substitution, supported by attributed technical corpora | The test seam lets us replace the clock |
| Low priority | Roughly, ordinarily, ordinary, approximately | A distinct construction would need evidence beyond the individual word | Roughly 20 minutes |
| Low priority | Recast, conflation, comparative, epistemic | Formulaic deployment where the claimed distinction or reasoning is absent | The proof conflates necessity with sufficiency |
| Reject as global flags | Number words, names, acoustic, perimeter, reporting verbs | No general slop function established | The acoustic sensor measures pressure |

The seam, gate and spike row is an independent research question, not a conclusion from the selected SpeechMap signature tables. Absence from a top-signature list is not a measured zero.

## How this should enter the repository

Add this source review and dated observations as research documentation first. Link the source from the lexical-tells design. Do not mark every matching existing rule as primary-research: a paper or corpus must support that rule's actual detection context.

For a later registry change, associate observations with stable candidate IDs and reuse the existing provenance vocabulary. Keep source ratios, evidence confidence and production scoring weight as separate fields. Record exact model variant, observation date, comparison population, rates, response count, domains, context exclusions and the reviewer's treatment rationale.

Before importing the corpus, verify reuse terms, locate reproducible calculation code, inspect question and completion identifiers, and retain a digest for any authorised snapshot. This PR adds no polling job, model calls, dataset copy or automatic rule promotion.

## Tests and acceptance before promotion

1. Inspect occurrences of each shortlisted term and classify literal, established technical, useful metaphor, unsupported abstraction and ambiguous usage.
2. Use comparable human technical prose as clean controls, with source dates and attribution uncertainty recorded.
3. Separate discovery prompts from held-out evaluation prompts. Compare within genre and exact model variant.
4. Measure precision with counts and uncertainty intervals. Report false positives by register, not only an aggregate.
5. Add paired behavioural fixtures through the public score and staged-scan interfaces. Preserve quotations, code, required terminology, uncertainty and literal meanings.
6. Test overlapping word and construction findings so a cluster does not multiply penalties for the same evidence.
7. Leave unvalidated candidates unscored. Human review decides promotion or retirement.

## Review boundary

This review verifies selected published model-page measurements, inspects lineage methodology and maps their possible use in Antislop. It does not independently reproduce SpeechMap's statistics, inspect every response, establish causal model attribution, or certify a detector. The per-model map is useful as a research index precisely because production suitability remains a separate decision.
