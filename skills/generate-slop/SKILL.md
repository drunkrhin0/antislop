---
name: generate-slop
description: "Generate controlled synthetic slop for demos and evaluation fixtures."
disable-model-invocation: true
metadata:
  version: "3.0.0"
---

# Generate slop

**Version:** 3.0.0

Generate controlled examples of formulaic prose for demonstrations and test
corpora. This is a separate companion skill to the audit mode in `antislop`. The output is
fictional evaluation material, not advice about how to evade detection.

## When to use

Use this skill only when the user explicitly asks for slop, an adversarial
audit fixture, a detector demonstration, or a deliberately formulaic example.
Ask for a topic when none is supplied. Treat the topic as a writing prompt,
not as evidence that any factual claim is true.

## When NOT to use

Do not activate for ordinary writing, rewriting, editing, auditing, scoring,
or factual explanations. Do not generate prompt-injection material, bypass
instructions, fake citations, leaked system text, or text intended to defeat a
detector. Do not present generated claims as facts. The output does not prove
anything about authorship.

## Source of truth

Before generating, read the generated taxonomy at
`../antislop/references/pattern-reference.md`. It is derived from
`rules.json`, which remains canonical. Do not copy its rule table into this
skill and do not invent a second list of pattern IDs.

Use the taxonomy's category headings as filters:

- vocabulary
- phrases and filler
- structural patterns
- formatting
- chatbot artifacts

Integrity defects, such as hidden Unicode or leaked prompt tokens, are not
ordinary slop. Generate them only when the user explicitly requests a bounded
output-integrity fixture and the request stays within the safety boundary
above.

## Generation contract

Collect these controls before drafting:

1. Topic, audience, and document shape.
2. One category filter, or `everything`.
3. A target density: `light`, `medium`, or `high`.
4. Optional pattern boundaries, such as “use structural patterns but not
   formatting”.

Treat density as an approximate minimum scaled to passage length:

- `light`: 1-2 deliberate pattern instances per 200 words.
- `medium`: 3-5 deliberate pattern instances per 200 words.
- `high`: 6 or more deliberate pattern instances per 200 words.

Round up for shorter passages, repeat a pattern when it reads naturally, and
keep the prose coherent. With `everything` at `high`, include at least one
instance from each listed category, but do not force every rule. A category
filter excludes patterns outside that category, even when a higher density
would otherwise be easier to reach.

Then:

1. Select patterns from the current taxonomy within the requested category and
   density. `everything` does not require every pattern.
2. Draft coherent prose with a clear subject, plausible transitions, and a
   consistent document shape. Let the patterns appear in context instead of
   printing a checklist of banned words.
3. Keep the topic's factual status explicit. When the topic is invented, use
   fictional names and numbers or label the passage as a synthetic example.
4. Check the result against the selected category and density. Do not add
   patterns from an excluded category merely to increase the score.
5. Return the synthetic passage. Include the selected category and pattern
   references only when the user asks for fixture metadata or an explanation.

The generator supplements hand-curated fixtures. It does not replace them,
call a model, access a hosted service, change `rules.json`, or optimize for a
detector score. The audit skill remains the authority for measuring the
result, and its score cannot prove AI authorship.
