# Preservation contract

Load this reference for drafting with missing author material, revising, transforming, recreating, or running a controlled rewrite.

## Edit operations

Pick the operation the request implies and stay inside its authority:

| Operation | Authority | Boundary |
|---|---|---|
| Draft | Create prose only from supplied facts and allowed research. | A voice sample contributes style traits only (vocabulary, rhythm, punctuation, paragraph shape, formality). It cannot donate claims, memories, preferences, or experiences to the target. |
| Revise | Make the least invasive change that satisfies the request. | Preserve every inventory item below or report an authorized change. Never strengthen causality or certainty beyond the source. |
| Audit | Report findings without changing the artifact. | Produce no rewritten passage or file change unless the user separately requests it. |
| Transform | May change shape while preserving the source inventory. | Disclose structural changes and still pass the fidelity gate. |

Before Revise or Transform, inventory the source: claims, facts, quantities, dates, modality, causality, negation, conditions, attribution, quotes, citations, links, placeholders, markup, accessibility structure, required terminology, and author-owned statements. A voice sample supplies style traits only.

## Author gaps and [TK]

A finished deliverable must not contain model-added generic placeholders or `[TK]` markers. A requested draft with a missing logistical detail is different: draft immediately with a clear bracketed placeholder such as `[new Q3 deadline]`, and tell the author to replace it. Do not stop to ask for a missing logistical detail such as a date, time, name, link, or location. Ask one concise question before drafting and wait only when the missing fact controls the draft's position, safety, legal meaning, or cannot be isolated in a clear bracketed placeholder. Omit an optional unknown field if that stays truthful. `[TK]` markers are allowed only when the user explicitly requests a template, scaffold, or marked-up draft. Never invent missing material.

Specific-looking vagueness ("a package once caused a security problem") is a gap: ask which one, what happened, and how it was caught. Unsupported significance ("This change is crucial") is a gap: ask for the mechanism or the measured result.

## Claim evidence and locale routing

When a repair changes a fact-dependent claim, label or retain its evidence class: source (the claim is present in the supplied source text), logic (it follows from the supplied material), experience (the author's own), inference (a hedge from the supplied material), or unknown (no basis). A required claim whose evidence is unknown stops the rewrite and asks for a source. Protect technical spans (code, URLs, paths, API names, numbers, tags, and supplied terminology) byte for byte, and keep supplied informal voice traits unchanged without adding new slang. The zh-CN locale profile is opt-in: punctuation width, Chinese-Western spacing, and high-confidence translationese are advisory findings that activate only when the locale is selected or the text is reliably routed. A release note uses only supplied change evidence.

## Controlled rewrite

A controlled rewrite is a provider-neutral two-pass contract for revising prose against specific findings. Pass one identifies concrete findings. Pass two rewrites against the selected findings only. The compatible assistant produces the rewrite; Antislop supplies the contract, the protected-span rules, and the acceptance checks. There is no Python CLI, hosted service, or model-specific dependency, and no external project is called.

The seven steps:

1. **Audit** — run the audit over the source and list every concrete finding with its rule, span, and excerpt.
2. **Select** — choose which findings to address. Unselected findings are left as-is.
3. **Protect** — declare the protected regions that must stay byte for byte: facts, numbers, dates, URLs, identifiers, commitments, formatting, code and diagrams (including Mermaid blocks), quoted material, and distinctive voice. Add extra user-declared protected spans, any term or phrase the rewrite must not touch, in addition to the fixed regions.
4. **Rewrite** — produce the revised text, applying only the selected findings and leaving every protected region and every unselected finding unchanged.
5. **Check preservation** — run the fidelity gate over source and candidate. A changed protected value, a dropped fact, or a moved semantic anchor fails the check.
6. **Re-audit** — audit the revised result and report which selected findings cleared, which findings were preserved, which selected findings were left in place, and which findings the rewrite newly introduced.
7. **Accept** — present the preservation report and the re-audit to the author. The final acceptance stays human-controlled; no tool accepts the rewrite on the author's behalf.

Acceptance reporting names four finding classes. Selected findings are the ones the author chose to address. Changed findings no longer fire in the candidate. Preserved findings still fire because they sit inside a protected region or were never selected. Rejected findings are selected findings the rewrite left in place outside any protected region, and they need an author decision before acceptance. Newly introduced findings in the candidate are reported separately and never hidden by a passing preservation check.
