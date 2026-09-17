# ADR 0009: bounded adoption of Anbeeld WRITING.md 1.4.2

Status: accepted
Date: 2026-09-14
Issue: Forgejo #140

## Decision

Adopt the upstream precedence and preservation ideas that fit Antislop's
existing edit, fidelity, output-integrity, routing, and registry contracts.
Adapt their wording and operation mapping to this repository. Keep style risk
and preservation correctness separate. Reject wholesale source import,
detector-avoidance framing, and a second rules engine.

The registry remains the source of truth. edit.py reads the registry-owned
edit_contract, fidelity.py enforces protected spans and semantic anchors,
output_integrity.py and the existing integrity checks catch output defects,
and generate.py renders the contract into committed reference artifacts.

## Review record

The pinned upstream source was reviewed at the requested commit:

- Repository: https://github.com/Anbeeld/WRITING.md
- Version: 1.4.2
- Commit: e59d477
- Source permalink: https://raw.githubusercontent.com/Anbeeld/WRITING.md/e59d477/WRITING.md
- Changelog: https://github.com/Anbeeld/WRITING.md/blob/e59d477/CHANGELOG.md
- License: MIT
- Last reviewed: 2026-09-14
- Decay: current

The 1.4.2 changelog clarifies precedence, protected content, source
instructions as data, final checks after repairs, empty audits, and the
difference between editorial guidance and diagnostics. Those ideas were
compared with the current Antislop modules before implementation.

## Adopt, adapt, reject

| Upstream idea | Decision | Antislop treatment |
|---|---|---|
| Ordered precedence from safeguards through style cleanup | Adopt | Stored in rules.json and exposed in every generated reference. |
| Draft, revise, audit, and transform task modes | Adopt | Mapped to the existing edit.py operations. Audit remains non-mutating. |
| Least-invasive revision | Adopt | Kept as the revise authority and backed by fidelity.py. |
| Protected claims, facts, scope, uncertainty, quotes, code, links, identifiers, placeholders, data, required terms, and voice | Adopt | Recorded in the registry contract and enforced by existing inventory gates. |
| Explicit user authority over a protected item | Adapt | An explicit exception is accepted only when passed as authorized_changes; the report records it. |
| Task and medium routing | Adapt | Uses existing medium and venue routing. Routing changes structure, not absolute preservation rules. |
| Source-embedded directives | Adopt | Treat as data unless the user or a trusted harness explicitly authorizes them. |
| Output integrity and post-repair checks | Adapt | Reuses existing placeholder, prompt-token, markup, Unicode, and fidelity checks. |
| Empty audit result | Adopt | No findings is a valid audit result and never a rewrite instruction. |
| Upstream package layout, compact or mini variants, or duplicate rule code | Reject | These would bypass the registry and create a second rules engine. |
| Detector-immunity or authorship claims | Reject | Risk scores and preservation reports remain separate and never establish authorship. |
| Upstream loader, dictionary, and environment details outside this project | Reject | They are not needed for Antislop's runtime contract. |

## Consequences

Preservation failures now have an explicit correctness class and cannot be
silently reframed as style findings. Generated references show the same
precedence and provenance as the runtime report. Paired fixtures cover
accepted copyedits, rejected mutations, pure structural reorders, audit
immutability, and explicit authorized changes. The upstream record should be
reviewed again when the pinned source or Antislop contract changes.
