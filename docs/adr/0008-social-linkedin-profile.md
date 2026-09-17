# Add the opt-in social-linkedin profile

Reviewed `marian-kamenistak/linkedin-post-writing-skill` at `ef5b771` (MIT) and adopted its post-type and mobile-first concerns into Antislop without importing its engagement promises, algorithm claims, or example facts.

## Decision

Add an opt-in `social-linkedin` writing profile with its own post-type routing:

- Post types route which structural elements fit: lesson, case-study, announcement, opinion, and practical-guide. The routing records a fitting element as `keep` when present and `n/a` when absent; absence is never a defect.
- Calls to action, hooks, hashtags, short paragraphs, and the setup-challenge-action-result-lesson (SCARL) structure are optional and profile-local. A post with no call to action passes clean.
- A voice sample transfers style only: vocabulary, rhythm, paragraph shape, and formality. Achievements, metrics, opinions, and experience supplied by the author are preserved exactly.
- No rule promises reach, engagement, or an algorithmic benefit. A reach or engagement claim with no mechanism or measured result nearby asks the author for the evidence.
- The zero-em-dash rule stays absolute. No rule asks for deliberate errors or invented roughness.
- Social rules carry `profiles: ["social-linkedin"]`, so no social rule can fire under the general or technical profiles. Regression fixtures prove the profile stays inactive for ordinary technical prose.

## Why

Antislop had no social-platform profile. Applying long-form paragraph, heading, or conclusion expectations to LinkedIn can be as damaging as applying LinkedIn hooks and calls to action to general prose. The reviewed skill provided post-type routing, mobile-readable paragraph guidance, and optional structure, but also promised reach and engagement outcomes and leaned on example facts; those were rejected.

## What was adapted and what was rejected

- Adapted: the post-type split (lesson, case-study, announcement, opinion, practical-guide), mobile-readable paragraph guidance, optional SCARL structure, and optional calls to action.
- Rejected: reach and engagement promises, claims about opening weight, saves, dwell time, or any algorithmic benefit. The social rule `social-reach-promise` flags such promises and asks for a mechanism instead.
- Rejected: copying facts from examples, forcing a hook, adding personal experience the author did not supply, and relaxing the zero-em-dash rule.
- Rejected: treating optional structure as a requirement. Absence of a fitting element is `n/a`, reusing the existing review status that forces no judgment.

## Consequences

- `rules.json` gains a `social-linkedin` profile, a `social_post_features` section, a `social_post_types` section, and six social rules scoped to the profile. `validate.py` gates the schema, the fixture corpus, and the no-leakage invariant.
- `linkedin.py` owns the deterministic social feature detectors and the post review; `generate.py` renders the post-type routing for the social-linkedin profile only.
- The general profile's generated artifacts are unchanged: social rules render only under the social-linkedin profile.