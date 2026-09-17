# Adopt an evidence-first editing pipeline

Antislop started with a stronger canonical rule model than comparable writing
tools, but its executable checker covered only exact words and phrases.
Structural rules were skipped, and the style skill lacked an executable
preservation check.

The review in [`docs/avoid-ai-writing-review.md`](../avoid-ai-writing-review.md)
found a better operating model in `conorbronsdon/avoid-ai-writing`: context and
voice are separate, mechanical checks are executable, edits are checked for
preservation, and claims are tested against human controls.

Adopt that operating model in stages while retaining `rules.json` as the
canonical source and keeping the installable style and audit skills small.

The full decision record is supported by
[`docs/avoid-ai-writing-full-audit.md`](../avoid-ai-writing-full-audit.md),
which audits every tracked upstream and companion MCP file, all 112 replacement
rows, all 69 catalog categories, the five voice profiles, triggers, packaging,
tools, tests, corpus, and cited sources.

The [end-to-end readiness test](../avoid-ai-writing-e2e.md) first found that the
scorer could return 100 while leaving 65 active rules unreported. New
structural and publishing findings were not executable, protected spans
produced false positives, inflections were missed, and voice, context,
preservation, and tool surfaces were absent.

Version 3.0.0 implements the deterministic slice of this decision. One shared
analyzer now backs the CLI and MCP tools. It masks protected Markdown while
preserving offsets and uses separate analyzers for numbered-list repetition,
paragraph connectivity, and adjacent restatement. Voice, context, and mechanics
resolve into explicit rewrite guidance without changing the detector set. The
rewrite review tool blocks candidates that fail literal preservation. The
universal ChatGPT and Codex manifest packages both skills with the read-only
tools.

Adopt these design choices:

- independent voice, context, and mechanics axes, with source samples and
  preservation taking precedence over named profiles;
- explicit rewrite, detect, and edit intent routing while retaining separate
  small-context skills;
- typed replacement, variant, tier, density, scope, evidence, counterexample,
  repair, and detector-status metadata in the registry;
- protected-span masking, source-stable findings, and rewrite-preservation
  validation;
- a generated category coverage contract and client artifacts, including a
  Cursor rule;
- false-positive intake, self-scan budgets, hashed corpus controls, and
  register-specific evaluation;
- a read-only scanner tool with compact and detailed outputs.

The style replacement and structure references retain registry-parity tests.
New deterministic detectors require public-seam fixtures and protected-span
counterexamples before they can affect the score.

The implemented sequence was:

1. build a registry-driven checker for mechanical rules;
2. add protected-span masking and rewrite-preservation checks;
3. add self-scan and human-control corpus gates;
4. add separate context and voice axes;
5. expose scoring, rewrite preparation, preservation, and candidate review
   through one MCP package without forcing every client to load one large skill.

The Formulaic Writing Risk Score remains a style-conformance measure. It must
not produce or imply an authorship classification. A score marked
`manual_review_required` is mechanical evidence, not a complete prose review.
Vocabulary tier changes and new score weights require corpus evidence and a
major-version boundary.

Reject authorship labels and probabilities, detector-evasion loops, injected
disfluency, unmeasured frequency claims, a wholesale 112-term hard-ban import,
and a monolithic combined skill. Client documentation must state which plugin
manifest packages the MCP tools and which surfaces remain skills-only.

ScrutinAIze is the static assurance reference for tool claims. The pinned scan
receipt lives in `docs/assurance/scrutinaize.md`. A static scan
must have no known MCP failures before release. Its runtime-only controls may
remain unknown until an installed host trace exists, and that unknown state
must not be turned into a pass.

This decision does not change the absolute dash house style. It requires copy
to distinguish that preference from evidence about authorship. Model rewrite
quality also remains outside the deterministic implementation until a pinned
model run records inputs, outputs, and results.
