# Add Sepia-style operation and venue routing

Reviewed `Nanako0129/sepia` at 361e82e (MIT) and adopted its operation split and venue-matched structural expectations into Antislop without importing its authorship claims.

## Decision

Add three operations on top of the existing operation authority from `edit.py`:

- **Review** quotes evidence and never rewrites. Every finding carries a quoted span, rule, status, and reason. It preserves Sepia's explicit `n/a` and `over-correction` states and maps the remaining outcomes to the Antislop-local `keep`, `revise`, `cut`, and `ask-author` statuses.
- **Refactor** lists the full finding set, then applies only the accepted minimal edits and reports the rejected and unresolved findings.
- **Recreate** extracts facts, claims, quotes, intent, and constraints from the source, drafts fresh prose, then verifies the candidate keeps them.

Add venue routing for tickets, developer replies, postmortems, technical articles, and release notes, each with deterministic structural features that are either kept, missing, or `n/a` in that venue. Add fiction only as an explicit opt-in profile whose guidance cannot affect general or technical scoring. Add a question-under-discussion review whose paragraph question check stays human-review structural guidance and whose reflection tail has an exact deterministic condition.

## Why

Antislop's general and technical profiles do not capture the different jobs performed by review, refactor, recreate, or venue-specific prose. The same advice can damage a postmortem, ticket, developer reply, release note, or work of fiction when applied without task and venue context. Sepia's operation split and venue-matched rules address that gap directly, and its `n/a` and `over-correction` states fit the existing review status model.

## What was adapted and what was rejected

- Adapted: the operation split (review / refactor / recreate), the venue-matched structural expectations for the five professional venues, the `n/a` and `over-correction` states, and the question-under-discussion reflection-tail concern.
- Rejected: Sepia's model fingerprints and StoryScope rate tables as authorship evidence. Antislop's Formulaic Writing Risk Score keeps its disclaimer that it never proves who wrote a document.
- Rejected: fiction architecture as a universal rule set. Fiction guidance exists only under the opt-in `fiction` profile, and fiction rules carry `profiles: ["fiction"]` so the general and technical profiles are unaffected.

## Consequences

- `rules.json` gains a `venues` section, a `venue_features` section, the `n/a` and `over-correction` review statuses, and the `fiction` profile. `validate.py` gates the schema and the fixture corpus.
- `sepia.py` owns the deterministic venue-feature detectors and the QUD reflection-tail condition; `generate.py` renders the venue routing into the pattern reference.
- The zero-em-dash policy stays absolute in every venue and profile.