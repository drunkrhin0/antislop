# Add Say-It-Human claim evidence and locale routing

Reviewed `taxueseek/say-it-human` at 71bb6f8 (MIT) and adopted its claim-evidence labeling, technical-span protection, locale-aware punctuation and translationese checks, and scene-fit venue routing into Antislop without importing its concentration grading or its voice-simulation guidance.

## Decision

Add a `tools/say_human.py` runner with five claim evidence classes: `source`, `logic`, `experience`, `inference`, and `unknown`. Every fact-dependent repair retains or exposes the evidence class of the claim it touches, and a required claim whose evidence is `unknown` stops rewriting and requests a source.

Add protected technical spans for code, URLs, paths, API names, numbers, tags, and supplied terminology, reused from `tools/repair.py`'s protected regions and extended with API names and tags. These spans survive byte for byte.

Add an opt-in `zh-CN` locale profile covering punctuation width (full-width vs half-width), Chinese-Western spacing, and high-confidence translationese patterns. The rules activate only when `--locale zh-CN` is selected or the text is reliably routed as Han-dominant, and they are advisory findings that never auto-apply to Chinese prose.

Add venue routing for technical documentation, release notes, marketing, presentations, and social prose, each sent to distinct fixtures. A release note uses only supplied change evidence: an unsupported feature claim requests a source instead of shipping. Large deletions require explicit edit authority and emit a visible diff.

## Why

Antislop never labeled whether a claim comes from supplied source text, logic, author experience, inference, or an unknown source, and it lacked locale-aware punctuation and translationese checks. A general English repair could damage Chinese prose or technical spans. Say-It-Human's claim-evidence map, protected technical spans, punctuation profile, and scene-fit venue routing address that gap directly.

## What was adapted and what was rejected

- Adapted: the claim evidence classes, the protected technical spans, the zh-CN punctuation and translationese checks, the venue routing to distinct fixtures, and the release-note grounding in supplied change evidence.
- Rejected: concentration grading as a score, detector-evasion framing, and any instruction to add emotion, mess, slang, errors, or first-person experience to simulate humanity. The runner never adds invented humanity.
- Rejected: promoting archived or provisional Chinese rules without independent positive and false-positive fixtures. Every zh-CN rule ships with both.

## Consequences

- `rules.json` gains a `claim_evidence_classes` section and a `locales` section. `tools/validate.py` gates both schemas.
- `tools/say_human.py` owns the claim evidence classification, the protected technical spans, the zh-CN locale checks, the venue routing, and the fixture corpus; `tools/validate.py` runs the corpus and fails when a fixture decision or evidence class does not match.
- The zero-em-dash policy and general English repairs stay absolute; zh-CN locale rules are opt-in and advisory and never change the Formulaic Writing Risk Score.