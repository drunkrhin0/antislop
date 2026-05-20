---
name: antislop-audit
version: "1.0"
description: Audits text for AI slop patterns and returns a slop score (0-100) plus a violations list. Use when the user asks to check, audit, review, grade, or score text for AI patterns, AI slop, or writing quality. Also trigger when the user pastes text and asks "does this pass?", "is this sloppy?", "flag the AI patterns", or similar. Companion to the antislop writing style skill. Zero exceptions — flag every violation regardless of perceived intent or satire.
---

# Antislop Audit

**Version:** 1.0  
**Purpose:** Detect and score AI slop patterns in existing text. Flag every violation. No exceptions for intent.  
**Companion skill:** antislop (writing style)  
**Sources:** Same as antislop writing style: blader/humanizer, jalaalrd/anti-ai-slop-writing, Reddit r/copywriting, self

---

## Core rule

Flag the pattern. Do not reason about whether it was intentional. Intent is not an input. Satire, irony, and deliberate demonstration of a pattern all get flagged the same way. The score reflects what's on the page, not why it's there.

---

## How to run an audit

### Step 1 — Scan for violations

Work through every category below. For each violation found, record:
- **Category** (e.g. Banned vocab, Em-dash)
- **Excerpt** — the exact offending text, quoted
- **Rule breached** — one line description

Do not skip categories. Do not combine violations. One instance = one violation entry.

### Step 2 — Count violations by severity

**High severity** (each = -8 points):
- Banned vocabulary
- Banned phrases
- Em-dash as authority prop ("— not X, not Y, but Z" or similar)
- Scare quotes
- Chatbot artifacts ("I hope this helps", "Great question")
- Vague attribution ("experts believe", "research shows" without source)
- Significance inflation ("pivotal moment", "transformative")

**Medium severity** (each = -4 points):
- Em-dash overuse (any em-dash not in the high severity category)
- Random bolding
- Ambiguous bolded bullet (claim not supported by body text)
- Banned openers/closers (Moreover, Furthermore, In conclusion, etc.)
- Rule of three in a single sentence
- Synonym cycling
- Overlong sentence (3+ ideas, 2+ qualifiers, or 2+ disclaimers in one sentence)
- "X isn't the problem, Y is" construction
- False range ("from X to Y" as rhetorical filler)
- Promotional language ("nestled within the breathtaking...")
- Generic conclusion ("The future looks bright", "Exciting times ahead")

**Low severity** (each = -2 points):
- Title Case Headings (should be sentence case)
- Inline-header lists (**Term:** explanation)
- Hyphenated word pairs that don't need hyphens
- Emojis in prose

### Step 3 — Calculate score

Start at 100. Subtract points per violation. Floor is 0.

**Score bands:**
- **85-100** — Clean. Reads like a person.
- **65-84** — Some slop. Fixable with targeted edits.
- **40-64** — Heavy slop. Significant rewrite needed.
- **0-39** — Severe. This reads like unreviewed AI output.

### Step 4 — Output format

Always output in this exact structure:

---

**Slop Score: [X]/100** — [band label]

**Violations ([N] total):**

| # | Severity | Category | Excerpt | Rule |
|---|---|---|---|---|
| 1 | High | Banned phrase | "it's worth noting that" | Delete — state the thing directly |
| 2 | High | Em-dash authority prop | "— not through magic, not through hype" | Em-dash padding a claim instead of making it |
| 3 | Medium | Overlong sentence | "sentences that packed in three ideas..." | 3+ ideas in one sentence; use a full stop |
...

**Summary:**
[2-3 sentences on the dominant patterns and what to fix first. No softening. No "great work on X". Just the fix.]

---

## Pattern reference

### Banned vocabulary — High severity each
delve, leverage, tapestry, testament, vibrant, pivotal, utilize, synergy, holistic, robust, seamless, groundbreaking, cutting-edge, innovative, dynamic, comprehensive, embark, foster, ensure, explore, revolutionize, transformative, empower, unlock, supercharge

### Banned phrases — High severity each
- "It's worth noting that"
- "In today's fast-paced world" / "in today's landscape" / "ever-evolving landscape"
- "At its core" / "at the end of the day"
- "Let's dive in" / "let's delve deeper"
- "Not just X, but Y"
- "Game-changer" (without specific metrics)
- "Treasure trove" / "uncharted waters" / "embark on a journey"
- "It cannot be denied that"
- "This underscores the importance of"
- "As of my knowledge cutoff"
- "Research shows" / "experts believe" (without named source)
- "Despite challenges, continues to thrive"
- "The future looks bright" / "exciting times ahead"
- "In the realm of" / "dynamic world of"

### Banned openers and closers — Medium severity each
- "In conclusion" / "To summarize" / "To wrap up"
- "Certainly" / "Absolutely" / "Great question"
- "You're absolutely right" / "That's a great point"
- "I hope this helps!" / "Let me know if you have questions!"
- "Moreover" / "Furthermore" / "Additionally" (flag each instance as medium severity)

### Em-dash rules
- Em-dash used as authority prop ("— not X, not Y, but Z" / "— built not on hype but on...") → **High severity**
- Any other em-dash → **Medium severity**
- Flag every instance separately

### Scare quotes — High severity each
Any word in quotes where the quotes signal ironic distance rather than a direct quotation. E.g. you know the "type", "innovative" solution.

### Bolding rules
- Random bolding (word bolded with no clear reason) → **Medium severity** per instance
- Ambiguous bolded bullet (bold claim not supported by following text) → **Medium severity** per instance

### Structural patterns — Medium severity each
- Rule of three in a single sentence
- Overlong sentence (3+ ideas, or 2+ qualifiers/disclaimers crammed in)
- "X isn't the problem, Y is"
- Synonym cycling (protagonist / main character / central figure)
- False range ("from X to Y" as rhetorical filler)
- Significance inflation ("pivotal moment in the evolution of...")
- Promotional language ("nestled within the breathtaking...")
- Formulaic challenge framing ("despite challenges, continues to thrive")
- Announcing structure ("First I'll discuss... then I'll cover...")
- Generic conclusions ("The future looks bright")

### Formatting — Low severity each
- Title Case Headings
- Inline-header lists (**Term:** description)
- Unnecessary hyphenated pairs (cross-functional, data-driven)
- Emojis in prose

### Chatbot artifacts — High severity each
- "I hope this helps!"
- "Let me know if you have questions!"
- "Great question!"
- "Certainly!" / "Absolutely!"
- Cutoff disclaimers ("While details are limited based on available information...")

---

## Notes

- Audit the full text provided. Do not summarise or skip sections.
- If the text is long (1000+ words), note the word count and confirm you've scanned all of it.
- Never compliment the writing. Never soften the findings.
- If score is above 85, say so plainly and stop. No padding.
