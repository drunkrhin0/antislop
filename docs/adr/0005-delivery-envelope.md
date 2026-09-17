# Add the ReviewWrite-style evidence-bound delivery envelope

Reviewed `songhai-dg/review-write` at 5c51063 (MIT) and adopted its evidence-bound delivery shape into Antislop without importing its operational platform.

## Decision

Add an optional repair envelope in `delivery.py` (issue #95) with four separate fields: `review_report`, `revision_plan`, `deliverable_body`, and `verification_report`. The deliverable body is stored and emitted separately from findings, plans, and verification commentary. Compute a stable body digest (SHA-256 over the UTF-8 body with line endings normalized to LF). When a source record is bound, its digest uses a versioned canonical serialization with stable key order, UTF-8 encoding, and normalized line endings, with the serialization version hashed as part of the digest.

`check_envelope` rejects missing, stale, or mismatched verification with typed failures: `missing_verification` when no verification is bound, `stale_verification` when the stored verification's body digest no longer matches the current deliverable body, and `mismatched_verification` when the stored verification's source digest does not match the bound source record. The body digest is recomputed on every check, never trusted from the stored field.

## Why

Antislop never bound a reviewed source, a revision plan, a delivered body, and a verification result into one inspectable record. Without the binding, findings or verifier commentary could leak into the revised prose, and an old verification result could be mistaken for evidence about a later edit. The envelope makes the covered source and body digests explicit and makes a body edited after verification detectable as stale.

## What was adapted and what was rejected

- Adapted: the four-field evidence-bound envelope, the stable body digest, the exact source and body digests inside the verification record, and the typed rejection of missing, stale, or mismatched verification.
- Rejected: the ReviewWrite operational platform (planning UI, credit budgets, multi-model orchestration). `delivery.py` is a standard-library runner like the other Antislop commands.
- Rejected: using the digest as proof of semantic equivalence. The digest binds the exact bytes; meaning preservation stays with the existing fidelity, drift, and edit-integrity contracts, which `verify_delivery` reuses for required facts, protected literals, qualifiers, uncertainty, attribution, and forbidden additions.

## Consequences

- `delivery.py` owns the canonical serialization, the digests, the typed envelope failures, and the chunked verification mode.
- The fixture corpus lives in `skills/antislop/evals/delivery-envelope-fixtures.json`; `validate.py`'s `check_delivery_fixtures` runs it.
- Long documents can be verified in chunks so a fact introduced in one chunk and qualified in another is retained across the whole delivered body.
- The digest is not semantic proof, and model judgment stays advisory; the runner fails only on explicit envelope or preservation contracts.