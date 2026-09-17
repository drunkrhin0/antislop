# Add a Tagore-style substance report

Reviewed `apurvrdx1/tagore` at 1238743 (MIT) and adopted its two-group substance review and its change-contribution contract without importing its 1-10 scoring thresholds or its "sounds human" verdicts. Tagore is already credited for vocabulary and punchy closure; this ticket covers only the incremental substance and contribution mechanisms.

## Problem

A passage can avoid every known mechanical tell while remaining vague, consequence-free, or untrustworthy. Folding that judgment into the Formulaic Writing Risk Score would change the score's meaning and imply precision the evidence does not support. The report that judges substance must stay separate from the scored mechanical tells.

## Decision

Add `substance.py`, an opt-in report that preserves Tagore's two groups:

- **Mechanics**: Directness, Rhythm, Trust, Authenticity, Density.
- **Substance**: Specificity, Restraint, Voice.

Every dimension result cites evidence, carries one of four statuses, and offers a question or repair direction without inventing material:

- **evidenced** — concrete prose evidence shows the dimension is present.
- **unsupported** — concrete prose evidence shows the dimension is absent or thin; the next step fixes it or asks the author.
- **unknown** — author facts or intent are missing, so the review cannot classify and says so instead of guessing. Quoted opinions, samples too short to measure rhythm, and claims with neither a concrete referent nor a vague gesture all stay unknown.
- **not-applicable** — the dimension is not owed by the medium. A specific terse reference entry marks point of view and rhythm not-applicable.

The substance group is never scored and never folded into the Formulaic Writing Risk Score or its score bands. No result labels the text human or AI; authenticity evidence cites detectable correspondence, disclosure, or sycophancy markers and never claims the text sounds human.

Adopt the change-contribution contract from Tagore's contributor guide: evidence of a distinct tell, one narrow rule, before and after text, model and frequency context where known, and paired regression fixtures (a positive case and a clean false-positive case). Tagore's scored examples are candidate cases only; their thresholds are self-defined and are not imported as Antislop targets.

## What was adapted and what was rejected

- Adapted: the two-group structure, the eight dimension questions, the substance statuses, and the change-contribution contract items (distinct tell, one narrow rule, before and after text, model and frequency context, paired regression fixtures).
- Rejected: the 1-10 dimension scores, the 56/80 threshold, the 35/50 and 21/30 subtotal floors, and the "clean but soulless" diagnostic as a score. No reviewed threshold becomes a strict finding without a directly identified source and local fixtures.
- Rejected: any result that labels a passage human or AI. The report records evidence and statuses only, and `unknown` replaces any forced verdict when author facts or intent are missing.
- Rejected: promoting the substance group into the risk score. Combining substance values with formulaic-writing risk requires a separate versioned product decision.

## Consequences

- `rules.json` gains `substance_dimensions`, `substance_statuses`, and `contribution_contract` sections; `validate.py` gates all three schemas and the substance fixture corpus.
- `substance.py` owns the two-group report and the contribution validation; the fixture corpus lives in `skills/antislop/evals/substance-fixtures.json` and runs in CI.
- The substance group never enters the Formulaic Writing Risk Score, and no dimension result labels the text human or AI.