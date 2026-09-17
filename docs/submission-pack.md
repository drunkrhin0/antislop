# Antislop 3.0.0: ChatGPT/Codex plugin submission pack

## Listing copy

**Plugin name:** Antislop

**Short description:**
Two prose skills for writing, audit, and controlled synthetic fixture generation.

**Full description:**
Antislop is a skills-only plugin that brings two first-class prose skills to ChatGPT and Codex. `antislop` routes writing and audit work. `generate-slop` creates controlled synthetic material only when explicitly requested.

**Writing skill (antislop):** An ambient style that triggers automatically when you write, rewrite, edit, polish, or review any prose. It suppresses banned vocabulary, structural tells, formatting habits (em-dashes, scare quotes, title case), rhythmic giveaways, and voice-level absences. Every rule is documented with replacements and examples.

**Audit mode (antislop):** Scores text 0-100 and returns a structured violations table. Only primary deterministic forbidden or discouraged findings deduct; advisory, human-review, and related findings carry zero points. Repeated instances use diminishing weights, and the total is normalized to a 500-word reference length. Score bands describe low, moderate, high, or very high formulaic-writing risk. The score cannot prove AI authorship.

**Synthetic fixture skill (generate-slop):** Produces deliberately formulaic, fictional evaluation material for demos and test corpora. It is independently discoverable, requires explicit intent, and is not a mode of the `antislop` router.

Both skills are installed as one plugin. No hosted service is required.

**Category:** Productivity

**Capabilities:**
- Apply the Antislop writing style to any prose request
- Audit text for AI slop patterns with scoring
- Activate only on prose, not on code or configuration
- Report findings with severity, excerpt, and rule description
- Include the authorship disclaimer in every audit
- Generate controlled synthetic fixtures only when `generate-slop` is explicitly requested

**Starter prompts:**
- "Write an email to a customer about delayed delivery without sounding like AI"
- "Edit this paragraph to remove AI writing patterns: [paste text]"
- "Audit this text for slop: [paste text]"
- "Does this pass the Antislop check? [paste text]"
- "Rewrite this LinkedIn post so it sounds like a person wrote it"
- "Generate a synthetic high-density slop fixture about a fictional product launch"

---

## What shipped

- **Historical provenance:** Introduced in `7ae4abd`, the retired ChatGPT manifest is no longer shipped. The current stack version is 3.0.0 and uses the Claude-compatible marketplace import route.
- ChatGPT imports the GitHub repository through the Claude-compatible `.claude-plugin/marketplace.json`. The marketplace packages both skills without a connector or hosted service.
- Codex uses the native `.codex-plugin/plugin.json` manifest with the same stable `antislop` identity.
- The plugin installs two first-class skills. Fresh sessions expose `antislop` with writing and audit modes, plus the separately invoked `generate-slop` skill.
- Cross-manifest version and description drift guards (root `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `.codex-plugin/plugin.json`) shipped separately in #64 and #62/#68.
- Publication prerequisites documented but not shipped as complete (see below).

**The original manifest change made no changes to:**
- Writing rules, scoring behavior, profiles, rule registry, or generated artifacts
- The existing Claude Code plugin or marketplace
- The routed `antislop` boundary introduced by #149

Introduced in `7ae4abd`; the current stack version is 3.0.0. Later work updated the score contract and acceptance regressions. Those changes are not attributed to the manifest's introduction commit.

---

## Publication prerequisites (not complete in this pack)

Before listing in the OpenAI GPT store or universal plugin directory, the maintainer must complete:

1. Verified OpenAI developer or business identity
2. Apps Management write access
3. Logo and brand assets (not included in this pack)
4. Category selection (draft: Productivity)
5. Website (https://github.com/drunkrhin0/antislop)
6. Support URL (https://github.com/drunkrhin0/antislop/issues)
7. Privacy policy URL (not drafted, legal requirement)
8. Terms of service URL (not drafted, legal requirement)
9. Country availability settings
10. Policy attestations
11. Human release approval

No privacy policy, terms, logo, portal draft, or publication action is presented as complete in this pack.

---

## Reviewer cases

### Positive cases (a matching skill activates)

| # | Surface | Prompt | Expected skill | Expected result shape | Fixture text |
|---|---|---|---|---|---|
| P1 | Codex CLI, Codex desktop, ChatGPT Work | "Write a short email to my team about the Q3 deadline change" | antislop (writing) | Email draft with no em-dashes, no banned vocabulary, clear position | None |
| P2 | Same | "Edit this to sound less like AI: The platform leverages cutting-edge technology to drive transformative outcomes." | antislop (writing) | Edited version with replacements for "leverages", "cutting-edge", "transformative" | None |
| P3 | Same | "Audit this text: Furthermore, it is important to note that the threat landscape is constantly evolving." | antislop | Score below 40, violations for "furthermore", "it is important to note", "constantly evolving" | None |
| P4 | Same | "Does this pass? We ran 12 hosts against CVE-2024-3094. Three are internet-facing. Patches queued." | antislop | Score above 85 (clean), no violations for technical specificity | None |
| P5 | Same | "Help me polish this blog intro: In today's rapidly changing world, businesses must be agile and innovative." | antislop (writing) | Rewrite without "in today's rapidly changing world", "agile", "innovative" | None |
| P6 | Same | "Generate a synthetic high-density slop fixture about a fictional product launch" | generate-slop | Clearly synthetic, coherent fixture using the requested density without detector-bypass advice | None |

### Negative cases (prose-only boundary and authorship-disclaimer boundary)

#### Non-activation (skill does not activate)

| # | Surface | Prompt | Expected behavior | Expected result shape | Fixture text |
|---|---|---|---|---|---|
| N1 | All | "Write a Python function that sorts a list of dictionaries by a key" | No skill activation | Code response, not prose editing | None |
| N2 | All | "What is the capital of France?" | No skill activation | Factual answer, not audit | None |
| N3 | All | "Explain how CVE scoring works" | No skill activation | Explanation, not audit or style rewrite | None |

#### Authorship-disclaimer boundary (skill activates, but must not overclaim)

| # | Surface | Prompt | Expected behavior | Expected result shape | Fixture text |
|---|---|---|---|---|---|
| N4 | All | "Audit this email and tell me whether its score proves it was written by AI: Furthermore, it is important to note that the threat landscape is constantly evolving." | antislop activates but declines to assert proof | Score + violations table, plus an explicit statement that the score measures formulaic-writing risk and cannot prove AI authorship | The email text embedded in the prompt |

### Verification notes

- Before prompting, confirm the plugin skill roster contains exactly `antislop` and `generate-slop`. P1-P5 activate `antislop`; P6 activates only `generate-slop`.
- N1-N3 (non-activation): confirm no skill activates and the response is appropriate for the domain.
- N4 (authorship-disclaimer boundary): use the self-contained prompt above. Confirm `antislop` activates in audit mode and produces a score, but the response explicitly declines to assert the score proves AI authorship. A challenge with no source text must request the text instead of inventing a score.
- The authorship disclaimer ("This score measures formulaic-writing risk and cannot prove AI authorship") must appear in every audit output.
- The corpus of existing evaluations at `skills/antislop/evals/evals.json` and `skills/antislop/evals/audit-evals.json` provides additional coverage. This pack references those collections rather than duplicating the rule corpus.

---

## Accepted plugin identity

- Name: `antislop`
- Display name: Antislop
- Author: Rami Tawil
- GitHub publisher: https://github.com/drunkrhin0
- GitHub repository: https://github.com/drunkrhin0/antislop
- License: MIT
- Skills: exactly two, `skills/antislop/SKILL.md` with writing and audit modes, and the independently discoverable `skills/generate-slop/SKILL.md`
- Version: 3.0.0 (aligned with all canonical version-bearing locations)
