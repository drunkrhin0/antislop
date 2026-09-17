# Review of avoid-ai-writing

This review compares Antislop with
[conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing)
at commit `58a95fc9971d7af95f1f1324b8a6bc991eb8004d` from 30 August 2026.
The upstream test suite and self-scan passed locally on 31 August 2026.

The exhaustive follow-up is in
[`avoid-ai-writing-full-audit.md`](avoid-ai-writing-full-audit.md). It accounts
for all 112 replacement rows, the ten additional Tier 3 phrases, all 69 pattern
categories, all 50 tracked upstream files, all 11 companion MCP files, voice
and context profiles, triggers, tools, generated ports, tests, corpus evidence,
and credited sources. This document is the executive summary.

The executed readiness test is in
[`avoid-ai-writing-e2e.md`](avoid-ai-writing-e2e.md). It found that the
upstream deterministic subset works, but the proposed combined Antislop system
was not implemented end to end at the baseline revision.

Version 3.0.0 implements the deterministic portion of the recommendation:
shared analysis, independent profile axes, masking, source offsets, input
gates, literal preservation, trigger routing, and read-only MCP tools. The
current ChatGPT and Codex package uses `.codex-plugin/plugin.json`. A
ScrutinAIze scan provides a second, source-linked assurance check for the MCP
surface. It reports no known static failures and leaves live-host behavior
unknown until runtime evidence exists. Model rewrite quality remains
unverified.

## Finding

Antislop should adopt the upstream project's evidence and editing model in
stages. It should not copy the repository wholesale.

The first adaptation did not adopt voice profiles, the full replacement table,
the complete category catalog, the detector, preservation validation, or MCP
tools. The 3.0.0 follow-up adopts the testable subset without importing the
entire replacement table or presenting semantic rules as deterministic.

The upstream project is ahead in five areas:

1. It offers detect, rewrite, and safe in-place edit modes through one user
   entry point.
2. It separates context from voice. A technical document can keep a blunt or
   warm voice without weakening technical exceptions.
3. Its zero-dependency checker covers mechanical patterns, masks source spans,
   and reports stable offsets.
4. Its preservation checker catches changes to code, frontmatter, quotations,
   tables, links, paths, and heading structure.
5. It tests itself against human controls and publishes the poor results as
   well as the good ones.

Antislop is ahead in two areas worth keeping:

1. `rules.json` gives each writing rule one stable identity and one place for
   severity, profiles, overlap, and confidence.
2. The short style and audit skills cost less context than upstream's single
   15,000-word skill. Generated artifacts also reduce hand-sync work.

## Evidence that changes the product claim

The upstream human-control corpus reports paragraph ROC-AUC of 0.501 and
document ROC-AUC of 0.623. Its Tier 1 vocabulary category fired slightly more
often on human documents than machine documents, with a reported lift of 0.9.
Its em-dash category pointed in the opposite direction, with a reported lift
of 0.2.

Those results do not test whether the rules improve prose. They do show that a
style score must not be presented as an authorship classifier. Antislop's
"Formulaic Writing Risk Score" and authorship disclaimer are the right base.
Future work should remove remaining authorship language from rule guidance and
product copy.

## Adopt now

This change takes the parts that fit the current rule and generation model:

- numbered-list inflation;
- paragraph-reshuffle and information-density checks;
- unfilled placeholder, chat citation token, and AI referrer cleanup;
- a rewrite provenance rule that permits subtraction and sharpening but bans
  invented facts, positions, and first-person experience;
- direct credit to the intermediate project and the original sources behind
  the adopted rules.

## Adopt next

The next implementation sequence should be:

1. Replace the current exact-string scorer with a checker for the mechanical
   subset of the registry. Mask code, quotations, tables, and frontmatter.
2. Add a preservation checker before offering in-place edit mode.
3. Add source modes for plain text and rendered Markdown, with stable finding
   offsets.
4. Add a self-scan budget and a regression-only gate for existing documents.
5. Build a hash-based human-control corpus by register before changing weights
   or making detector-performance claims.
6. Add separate context and voice axes. Keep `general` and `technical` as
   context profiles, then add voice profiles without duplicating rules.
7. Offer detect, rewrite, and edit through one invocation contract while
   retaining the two installable skills for small-context clients.

The typed-rule foundation being designed in the parallel Antislop source
review should own profiles, positive guidance, repairs, heuristics,
preservation policies, and tooling metadata. This review should feed that
model rather than create a competing schema.

Vocabulary tiers belong in the same major release as the new checker and
corpus. Moving words from absolute bans to isolated, clustered, and density
rules changes scoring and should not arrive as an unmeasured table rewrite.

## Do not adopt

- Do not add authorship classifications or human, mixed, and AI probabilities.
  The upstream measurements do not support that claim.
- Do not replace the registry with a hand-maintained prose catalog plus a
  separate detector map.
- Do not combine every rule and operating mode into one large skill file.
- Do not inject typos, disfluency, first-person stories, facts, or a stock
  "human" persona.
- Do not change Antislop's absolute dash rule in this change. It is a house
  style decision, though it must not be described as authorship evidence.

## Reference review

The repository references were inspected at these snapshots: `blader/humanizer`
`e2e92e7`, `brandonwise/humanizer` `4b9b9be`, `Aboudjem/humanizer-skill`
`17bb5bb`, `isatimur/de-slop` `4349a8a`, `NulightJens/humanizer-stack`
`13f5c02`, and `harshaneel/humanize` `4ec7973`.

| Reference | Existing Antislop coverage | Decision |
|---|---|---|
| [Pangram Labs](https://www.pangram.com/) | Directly credited | Keep the structural-regularity lesson. Do not repeat model-training claims without a primary methods source. |
| [Wikipedia, Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) | Indirect through `blader/humanizer` | Add to the review trail. Material derived from the page carries CC BY-SA attribution concerns. |
| [blader/humanizer](https://github.com/blader/humanizer/tree/9862685) | Reviewed at Humanizer 3.0.0 revision `9862685` under MIT | Adopt source-fidelity, vague-association, and previous-version guidance with contextual exceptions. Keep Antislop's independent synonym-cycling and false-range rules, and reject a broad exact-match vocabulary import. |
| [brandonwise/humanizer](https://github.com/brandonwise/humanizer) | Not previously credited | Use as a design reference for vocabulary tiers, masking, and regression gates. Its 5 to 20 times vocabulary claim has no published method, so do not repeat it as measured fact. |
| [OpenClaw](https://github.com/openclaw/openclaw) humanizer ecosystem | No exact source artifact named | Treat as distribution context, not a rule source, until a path and commit are identified. |
| [Aboudjem/humanizer-skill](https://github.com/Aboudjem/humanizer-skill) | Several ideas arrived indirectly | Credit directly for placeholder, citation-token, URL-parameter, paragraph-order, and information-density checks. |
| [isatimur/de-slop](https://github.com/isatimur/de-slop) | Not previously credited | Credit directly for rewrite fidelity, smaller edits, and the ban on invented facts or persona. |
| [NulightJens/humanizer-stack](https://github.com/NulightJens/humanizer-stack) and [StoryScope](https://github.com/jenna-russell/storyscope) | Structural rules partly overlap | Use as a reason to test structure separately. StoryScope studied long fiction, so transfer to short factual prose remains an inference. |
| [harshaneel/humanize](https://github.com/harshaneel/humanize) | Many surface rules overlap | Use its literature map as research input only. Detector evasion, disfluency injection, and other fake-human tactics conflict with Antislop's editing contract. |

## Verification boundary

The upstream project's tests verify its software contracts. Its corpus tests
show that the authorship classifier is weak on the measured data. Neither result
proves that a given rule improves prose. Antislop still needs reader-facing
evaluation fixtures and human review for semantic rules.
