# Antislop

Antislop defines an opinionated writing standard and a companion assessment for formulaic writing patterns.

## Language

**Writing rule**:
A named instruction that identifies or corrects a formulaic writing pattern.
_Avoid_: Detector, heuristic

**Finding**:
One observed match between text and a writing rule.
_Avoid_: Detection, hit

**Primary finding**:
The single scored finding assigned to a text span when several writing rules overlap.
_Avoid_: Main violation

**Related finding**:
An overlapping finding reported for context without another score deduction.
_Avoid_: Duplicate violation

**Document-level finding**:
A finding based on a pattern across a document or materially independent section rather than one phrase.
_Avoid_: Global violation

**Formulaic Writing Risk Score**:
A score measuring conformance to the Antislop standard. It does not identify the author or prove AI use.
_Avoid_: AI detector score, authorship score

**Writing profile**:
A named set of writing rules selected for a medium or register.
_Avoid_: Mode, preset

**Rule registry**:
The canonical machine-readable source for writing rule definitions and generation metadata.
_Avoid_: Rules database, config

**Generated artifact**:
A skill or reference file rendered deterministically from the rule registry.
_Avoid_: Derivative copy

**Evaluation fixture**:
An input and observable expectation used to assess skill behavior.
_Avoid_: Unit test

**Edit operation**:
One of Draft, Revise, Audit, or Transform. Each carries a distinct authority over an artifact.
_Avoid_: Mode, editing preset

**Inventory**:
The preserved content and structure of a source that a Revise or Transform must keep: claims, facts, quantities, dates, modality, causality, negation, conditions, attribution, quotes, citations, links, placeholders, markup, accessibility structure, required terminology, and author-owned statements.
_Avoid_: Checklist, metadata

**Review status**:
One of keep, revise, ask-author, cut, or no-finding, assigned to each finding in a review. Review never edits; every finding carries exactly one status.
_Avoid_: Verdict, grade

**[TK] marker**:
A placeholder for author-owned material that the source does not supply, written as `[TK: specific question]`. A marker stays a question; it is never filled with generated content.
_Avoid_: To-do, placeholder-for-AI-fill

**Mechanism check**:
An advisory detector that separates an unsupported significance claim (importance, impact, causality, or superiority without a nearby mechanism, actor, result, or limit) from an evidenced consequence. Mechanism checks never deduct.
_Avoid_: Importance detector

**Medium routing**:
Structural expectations that vary by medium (argument, explanation, evocation, narrative, guide, reference, message) while absolute rules such as the zero-em-dash rule never change.
_Avoid_: Mode, preset

**Calibration experiment**:
A deterministic comparison of a baseline and a candidate implementation over the same frozen labeled fixtures, with an explicit score direction and a non-empty holdout set.
_Avoid_: Benchmark, score comparison

**Clean span**:
A labeled text span that must produce no finding; it drives the false-positive rate.
_Avoid_: Safe region, allowlist

**Holdout fixture**:
A labeled fixture excluded from threshold tuning; thresholds are static configuration values, never derived from fixture data.
_Avoid_: Validation split, test set

**Label provenance**:
The documented origin of a fixture's labels (human hand-labeling, a reference implementation, or a named corpus).
_Avoid_: Ground truth (when the origin is a model or an unlabeled corpus)

**Surface scan**:
The first stage of a staged scan: deterministic lexical checks over prose with fenced and inline code masked, returning strict or advisory findings. Strict findings affect the exit status; advisory findings do not unless configured.
_Avoid_: Lexical pass

**Structural review**:
The second stage of a staged scan: the registered structural detectors recommend at most two high-value interventions per pass, and no change is a valid result. Structural advice never becomes a mandatory recipe.
_Avoid_: Full rewrite recommendation

**Corpus convergence**:
A repeated document shape (hook, reveal, lesson, close) detected across two or more explicitly supplied documents. A single document never triggers a cross-document convergence claim.
_Avoid_: Cross-document similarity score, plagiarism check

**Output-integrity finding**:
A deterministic output defect (leaked citation residue, unresolved placeholder, tracking-only URL, leaked reasoning wrapper, invisible Unicode, or mixed-script homoglyph) reported separately from formulaic-writing risk with an exact span, line, stable ID, and repair guidance.
_Avoid_: Style violation, AI detector flag

**Template mode**:
An output-integrity scan option that treats the input as a documented template, so deliberate placeholder markers are structure rather than findings. Every other integrity check still runs.
_Avoid_: Safe mode, bypass

**Passage density**:
A document-level advisory finding when three or more distinct flagged terms cluster inside one documented passage window; isolated or separated legitimate use never triggers it. It reports the contributing rule IDs and never proves authorship.
_Avoid_: Term frequency count, word cloud

**Unsourced precision**:
An exact percentage, ratio, or count with no nearby source, supplied fact, estimate, or technical-constant framing. The finding is advisory, never declares the number false, and asks the author for the source.
_Avoid_: Fact-check, false-claim detector

**Horoscope test**:
An optional manual specificity question from the reviewed project: pick one random specific detail and ask the author to verify it. It is never scored and never authorship evidence.
_Avoid_: Auto-scored specificity metric

**Evidence class**:
The recorded provenance of a writing rule: project-policy, project-fixture, upstream-evidence, tested-adaptation, primary-research, secondary-claim, maintainer-judgment, or unknown. It records where a rule came from and never proves the rule is correct.
_Avoid_: Source proof, verified finding

**Decay state**:
A rule's provenance freshness: current, review, or stale. Listing a rule as review or stale never disables it automatically; a human changes the rule itself to retire it.
_Avoid_: Expiry, auto-disable flag

**Review queue**:
The registry section that lists stale lexical rules (still active) and fixture-backed candidate metrics. Membership in the queue changes nothing about a rule's behavior.
_Avoid_: Deprecation list, retirement log

**Candidate metric**:
A fixture-backed writing metric proposed for the registry but not yet a rule, always advisory, carrying matched-length and matched-profile clean cases so it cannot be accused of firing on length or profile.
_Avoid_: Pending detector, draft rule

**Repair loop**:
A bounded orchestration over the protected repair interface: detect named rule findings, select the smallest independent source spans, apply registered corrections, verify the named findings are gone, run fidelity and integrity gates, then accept, retry within a strict bound, or roll back. Defect removal with meaning preservation, never detector evasion.
_Avoid_: Detector feedback loop, paraphrase round

**Repair attempt trace**:
The per-attempt record that names input findings, selected spans, correction IDs, output findings, fidelity result, and decision. A trace never reports rhythm statistics as a decision input.
_Avoid_: Log, audit trail

**Changed-character budget**:
The cumulative bound on how many characters a repair loop may change across all attempts. Exceeding it rolls back immediately.
_Avoid_: Token budget, rewrite allowance

**Rhythm diagnostic**:
An advisory statistic such as sentence-length variation or lexical repetition, reported separately by the repair loop and never used to decide whether a passage is human.
_Avoid_: Human detector, authorship score

**n/a**:
A review state meaning a structural feature does not apply to the venue or offers no occasion in the text. No judgment is forced.
_Avoid_: Not scored, skipped

**Over-correction**:
A review state that records where applying a rule would flatten valid voice or structure, such as a formal register, quoted material, or an author's verified habit. It is reported separately and never reinterpreted as an AI-leaning signal.
_Avoid_: False positive, exemption

**Venue routing**:
Structural expectations that vary by venue (ticket, developer-reply, postmortem, technical-article, release-note) while absolute rules such as the zero-em-dash rule never change. A structural feature that does not apply to the venue is n/a.
_Avoid_: Template, preset

**Sepia operation**:
One of Review, Refactor, or Recreate, each with a distinct authority over an artifact on top of the edit operations. Review quotes evidence without rewriting; Refactor lists the full finding set and applies only the accepted minimal edits; Recreate extracts facts, claims, quotes, intent, and constraints before drafting fresh prose and verifies them afterward.
_Avoid_: Mode, editing preset

**Question-under-discussion review**:
A review that asks whether each paragraph advances one implicit question and whether the sequence ends in an unearned reflection tail. The paragraph question check stays human-review structural guidance; the reflection tail has an exact deterministic condition and is a finding.
_Avoid_: Outline check, discourse detector

**Delivery envelope**:
An optional repair record that binds a reviewed source, a revision plan, a delivered body, and a verification result into four separate fields, so findings and verifier commentary stay out of the deliverable and an old verification cannot be mistaken for evidence about a later edit.
_Avoid_: Handoff bundle, metadata wrapper

**Verification record**:
A verification result that records the exact source and body digests it covers. Missing, stale, or mismatched verification returns a typed failure.
_Avoid_: Pass certificate, approval stamp

**Body digest**:
A stable SHA-256 over the UTF-8 body with line endings normalized to LF, so a digest is stable across editors and never proves semantic equivalence.
_Avoid_: Similarity hash, semantic fingerprint

**Canonical serialization**:
A versioned serialization with stable key order, UTF-8 encoding, and normalized line endings, used before hashing a source record so a format change cannot reuse an old digest.
_Avoid_: Pretty-print, formatting

**Claim evidence class**:
The recorded basis of a claim being repaired: source, logic, experience, inference, or unknown. It records where the claim's backing comes from and never proves the claim is true. A required claim whose evidence is unknown stops rewriting and requests a source.
_Avoid_: Provenance label, source proof

**Protected technical span**:
A code, URL, path, API name, number, tag, or supplied-terminology span that a repair must keep byte for byte. It is never rewritten by an evidence-aware repair.
_Avoid_: Technical allowlist, skip region

**Locale profile**:
An opt-in set of locale-aware rules, such as the zh-CN punctuation-width, spacing, and translationese checks, that activate only when selected or reliably routed by the text's script. Locale rules are advisory findings and never auto-apply to prose.
_Avoid_: Language mode, regional preset

**Substance report**:
An opt-in two-group report that judges what a passage actually says: mechanics (directness, rhythm, trust, authenticity, density) and substance (specificity, restraint, voice). It is never scored and never folded into the Formulaic Writing Risk Score or its bands.
_Avoid_: Quality score, human-likeness gauge

**Substance status**:
One of evidenced, unsupported, unknown, or not-applicable, assigned per substance dimension with cited evidence and an author-safe next step. Unknown means author facts or intent are missing; not-applicable means the medium does not owe the dimension. No status labels text human or AI.
_Avoid_: Human/AI verdict, grade

**Contribution contract**:
The change-acceptance rule for proposed rules: evidence of a distinct tell, one narrow rule, before and after text, model and frequency context where known, and paired regression fixtures (a positive case and a clean false-positive case). A proposal missing a paired fixture is rejected.
_Avoid_: PR checklist, style guide

**Social post type**:
A routing class for LinkedIn posts (lesson, case-study, announcement, opinion, practical-guide) that decides which structural elements fit. Post-type routing records whether a fitting element is present or absent; absence is `n/a`, never a defect.
_Avoid_: Social template, post preset

**Optional structural element**:
A LinkedIn post element (call to action, hook, hashtag, short paragraph, or one of the setup-challenge-action-result-lesson steps) that is never forced. A post that omits one passes clean, and the element is profile-local to the opt-in `social-linkedin` profile.
_Avoid_: Required section, post checklist

**Social voice sample**:
A user-supplied example that transfers style signals only (vocabulary, rhythm, paragraph shape, formality) into a LinkedIn post. It cannot donate achievements, metrics, opinions, or experiences to the target; supplied author facts are preserved exactly instead.
_Avoid_: Voice persona, style transplant

**Controlled rewrite**:
A provider-neutral two-pass contract for revising prose against specific findings: audit first, select which findings to address, protect declared regions, rewrite against the selected findings only, check preservation, re-audit the result, and keep final acceptance human-controlled. The compatible assistant produces the rewrite; Antislop supplies the contract, protected-span rules, and acceptance checks.
_Avoid_: Full rewrite, automated rewrite

**Protected region**:
A span a controlled rewrite must keep byte for byte: facts, numbers, dates, URLs, identifiers, commitments, formatting, code and diagrams, quoted material, and distinctive voice, plus any extra user-declared protected span. A changed protected value fails the preservation check.
_Avoid_: Skip region, exception list

**Preservation drift**:
A change to a protected region or a semantic anchor between source and candidate, reported by the fidelity gate as a hard failure. It never lets a lower risk score hide a dropped fact, caveat, condition, or qualifier.
_Avoid_: Edit diff, rewrite summary

**Re-audit**:
The second audit pass over a rewritten candidate that reports which selected findings cleared, which were preserved, which selected findings were left in place, and which findings the rewrite newly introduced.
_Avoid_: Detector recheck, residual scan

**New finding**:
An audit finding present in the rewritten candidate whose rule fired nowhere in the source. It is reported separately and never hidden by a passing preservation check.
_Avoid_: Introduced violation, regression flag

**Human review workflow**:
An optional, local loop that opens a document in a real browser so the author can edit text and leave comments, then applies the returned feedback batch to the source document and re-audits until the human accepts. Human edits are authoritative; Human Review is not a writing rule and normal validation never requires it.
_Avoid_: Approval gate, automated review

**Feedback batch**:
The JSON batch Human Review returns, grouped by page and carrying edits, comments, and an overall note. Every page in the batch must be handled.
_Avoid_: Review message, edit list

**Verbatim edit**:
An edit whose `after` value is user-authored text carried into the source exactly and never reverted. Formatting-only changes arrive as `before_html` and `after_html` and are translated into the source syntax.
_Avoid_: Suggested edit, draft wording

**Localhost route**:
A `kind: "url"` target that names a route served by a local development server, not a writable source file. The assistant locates the matching source and updates that instead of the rendered response.
_Avoid_: Page file, writable endpoint

**Review acceptance**:
The human's decision to accept the revised source after the review and audit loop. A timeout is never acceptance and never approval.
_Avoid_: Poll success, batch approval
