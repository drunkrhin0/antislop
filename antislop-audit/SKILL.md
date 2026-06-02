---
name: antislop-audit
version: "1.3"
description: Audits text for AI slop patterns and returns a slop score (0-100) plus a violations list. Use when the user asks to check, audit, review, grade, or score text for AI patterns, AI slop, or writing quality. Also trigger when the user pastes text and asks "does this pass?", "is this sloppy?", "flag the AI patterns", or similar. Companion to the antislop writing style skill. Zero exceptions — flag every violation regardless of perceived intent or satire.
---

# Antislop Audit

**Version:** 1.3  
**Purpose:** Detect and score AI slop patterns in existing text. Flag every violation. No exceptions for intent.  
**Companion skill:** antislop (writing style)  
**Sources:** Same as antislop writing style: blader/humanizer, jalaalrd/anti-ai-slop-writing, Reddit r/copywriting, ignorance.ai/field-guide-to-ai-slop, Banned: The Definitive Guide, Pangram, Anbeeld/WRITING.md, self

---

## When to use

Trigger when the user asks to check, audit, review, grade, or score text for AI patterns, AI slop, or writing quality. Also trigger when the user pastes text and asks "does this pass?", "is this sloppy?", "flag the AI patterns", or similar.

## When NOT to use

This tool is for **self-review** — checking your own or a collaborator's text before publishing. Do not use it to accuse strangers of using AI. Pattern-based detection is probabilistic, not proof. A single flag does not indicate AI authorship; accumulation and pattern density are the tells. Do not run this against unsolicited text from people you are not collaborating with.

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
- Em-dash (any use — never permitted)
- Scare quotes
- Chatbot artifacts ("I hope this helps", "Great question")
- Vague attribution ("experts believe", "research shows" without source)
- Significance inflation ("pivotal moment", "transformative")
- Rhetorical-question hooks ("The kicker?", "The issue?", "Do you know what I learned?")
- Balanced-take hedging ("While X is true, we must also consider Y" formula)
- Specificity theater (unverifiable specifics, decorative factuality, hidden-mechanism narration, synthetic quotes with no named source)

**Medium severity** (each = -4 points):
- Random bolding
- Ambiguous bolded bullet (claim not supported by body text)
- Banned openers/closers (Moreover, Furthermore, In conclusion, etc.)
- Rule of three in a single sentence
- Synonym cycling
- Overlong sentence (3+ ideas, 2+ qualifiers, or 2+ disclaimers in one sentence)
- Negative parallelism / trailing negation ("not just X, but Y", "it's not about X, it's about Y", "X isn't the problem, Y is", "..., no guessing")
- Copula avoidance ("serves as", "boasts", "features", "functions as", "stands as" when "is"/"has" would do)
- Parataxis (3+ consecutive short declarative sentences with no conjunctions or subordination)
- Passive voice / subjectless fragments ("No configuration file needed", "Results are preserved automatically")
- Excessive hedging ("could potentially possibly", "it might have some effect", "it could be argued that")
- Rhetorical emphasis tail / moralizing tail ("..., that's the thing", "..., that's the hard truth", "Why it matters:", "Here's what I learned:", "This shows that...")
- Generic subject loops (3+ sentences opening with the same vague pronoun or impersonal construction)
- False range ("from X to Y" as rhetorical filler)
- Promotional language ("nestled within the breathtaking...")
- Generic conclusion ("The future looks bright", "Exciting times ahead")
- Notability name-dropping (listing media outlets without saying what any of them actually reported)
- Fragmented headers (heading followed by one-line paragraph that just restates it)
- Negation flip ("This isn't X. It's Y." when the negation adds nothing the positive statement doesn't already carry)
- Paragraph-level redundancy (same idea restated across paragraphs or concluding sentence restating the paragraph)
- Triplet overlap (3+ descriptors naming the same quality — "current, documented, and auditable")
- Superficial -ing analyses ("highlighting", "underscoring" tacked onto sentence ends)
- Bullet-point crutch (bullets used to dodge writing full paragraphs)
- Awkward AI metaphors (generic analogies unanchored to specific experience — "learning X is a mirror for learning itself")
- Simile-as-adverb ("with the [noun] of someone [verb]ing" — invents a hypothetical person)
- Hedged reactions ("a laugh that isn't quite a laugh" — contradiction substituting for depth)
- Temperature-as-emotion (hot/cold replacing specific emotional description)
- Physical tell clichés (jaw/throat/breath/hands as interchangeable emotion props)
- Anthropomorphized silence ("the silence stretched" — treating silence as an actor)
- All paragraphs the same length (uniform paragraph length with no variation)
- Uniform sentence length (monotonous same-length sentences with no variation in rhythm)
- Ending clichés ("And for now, that was enough" — summary posing as closure)
- Catalog prose (paragraphs that are only names, dates, features with no material consequence)
- System-tour prose (paragraph-to-category-bucket mapping: background → mechanism → impact → verdict)
- Concession rhythm ("not X, but Y" / "may sound X, but Y" as reflexive paragraph scaffold)
- Type-definition endings ("the kind of X where Y" appearing multiple times as paragraph closure)

**Low severity** (each = -2 points):
- Title Case Headings (should be sentence case)
- Inline-header lists (**Term:** explanation)
- Compound-modifier over-hyphenation (before-noun vs. after-noun, -ly adverb compounds, ever- compounds)
- Curly quotes (“ ”) — should be straight quotes (")
- Filler phrases ("in order to", "due to the fact that", "at this point in time", "the system has the ability to")
- Emojis in prose
- Usage of unicode characters to convey a point, which isn't used in general language (e.g. `→`)
- Artificial line breaks (mid-sentence breaks at terminal width ~80 chars)
- Standalone "Because" fragments ("Because she can't bear to look." — AI sentence rhythm)

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
| 4 | Medium | Negation flip | "This isn't a support desk. The goal is..." | Negation adds nothing the positive statement doesn't carry |
...

**Summary:**
[2-3 sentences on the dominant patterns and what to fix first. No softening. No "great work on X". Just the fix.]

---

## Pattern reference

### Banned vocabulary — High severity each
delve, leverage, tapestry, testament, vibrant, pivotal, utilize, synergy, holistic, robust, seamless, groundbreaking, cutting-edge, innovative, dynamic, comprehensive, embark, foster, ensure, explore, revolutionize, transformative, empower, unlock, supercharge, significant

### Banned phrases — High severity each
- "It's worth noting that"
- "In today's fast-paced world" / "in today's landscape" / "ever-evolving landscape"
- "At its core" / "at the end of the day" / "the real question is" / "what really matters" / "fundamentally" / "in reality" / "the deeper issue is"
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
- Any em-dash → **High severity**. No exceptions.
- Flag every instance separately.

### Scare quotes — High severity each
Any word in quotes where the quotes signal ironic distance rather than a direct quotation. E.g. you know the "type", "innovative" solution.

### Bolding rules
- Random bolding (word bolded with no clear reason) → **Medium severity** per instance
- Ambiguous bolded bullet (bold claim not supported by following text) → **Medium severity** per instance

### Structural patterns — Medium severity each
- Rule of three in a single sentence
- Overlong sentence (3+ ideas, or 2+ qualifiers/disclaimers crammed in)
- Negative parallelism / trailing negation ("not just X, but Y", "it's not about X, it's about Y", "X isn't the problem, Y is", trailing fragments like "..., no guessing")
- Copula avoidance ("serves as", "boasts", "features", "functions as", "stands as" when "is"/"has" would do)
- Parataxis — 3+ consecutive short declarative sentences with no conjunctions or subordination
- Passive voice / subjectless fragments ("No configuration file needed", "Results are preserved automatically")
- Excessive hedging ("could potentially possibly", "it might have some effect", "it could be argued that")
- Rhetorical emphasis tail ("..., that's the thing", "..., that's the hard truth", "..., and that's what matters")
- Moralizing tails — "Why it matters:", "Here's what I learned:", "This shows that..." tacked on without earning the takeaway
- Bullet-point crutch — bullet lists used to dodge writing full paragraphs when prose communicates more clearly
- Awkward AI metaphors — analogies that gesture toward meaning without achieving it. Generic, plausible, unanchored to specific experience. "Learning an instrument is a mirror for learning itself: messy, slow, and quietly addictive" could describe anything. Medium severity each.
- Rhetorical-question hooks — "The kicker?", "The issue?", "The twist?", "Do you know what I realized?" as openers. High severity each.
- Balanced-take hedging — "While X is true, we must also consider Y" as sentence scaffold. High severity each.
- Specificity theater — unverifiable specifics deployed to pass a "be concrete" check. Includes synthetic quotes (invented attribution), suspicious exactness ("47.3%"), decorative factuality (dates/numbers without supporting source), or hidden-mechanism narration (claiming to know internal system behavior without observable evidence). High severity each.
- Generic subject loops (3+ sentences opening with the same vague pronoun or impersonal construction)
- Synonym cycling (protagonist / main character / central figure)
- False range ("from X to Y" as rhetorical filler)
- Significance inflation ("pivotal moment in the evolution of...")
- Superficial -ing analysis ("highlighting", "underscoring", "symbolizing", "reflecting" tacked onto sentence ends to add fake depth)
- Promotional language ("nestled within the breathtaking...")
- Formulaic challenge framing ("despite challenges, continues to thrive")
- Announcing structure ("First I'll discuss... then I'll cover...")
- Generic conclusions ("The future looks bright")
- Notability name-dropping — listing media outlets ("cited in NYT, BBC, FT, and The Hindu") without what any said. Medium severity each.
- Fragmented headers — heading followed by one-line restatement. Medium severity each.
- Negation flip — stating what something isn't immediately before stating what it is, used as rhetorical padding rather than genuine contrast. E.g. "This isn't a support desk. The goal is..." / "These aren't hoops. They're how..." / "This is not discovery — it's logistics." Flag when the negation adds no information the positive statement doesn't already carry on its own.
- Paragraph-level redundancy — same concept restated across paragraphs with different words, or concluding sentence that summarizes the paragraph in different words. Medium severity each.
- Triplet overlap — 3+ descriptors naming the same quality (e.g. "current, documented, and auditable" all mean "reliable for attestation"). Medium severity each.
- Artificial line breaks — prose broken mid-sentence at terminal width (~80 chars). Low severity each.
- All paragraphs the same length — uniform paragraph length with no rhythmic variation. Medium severity each.
- Simile-as-adverb — "with the [noun] of someone [verb]ing" invents a hypothetical person to describe the actual state. Medium severity each.
- Hedged reactions — "a laugh that isn't quite a laugh" creates emotional static through contradiction. Medium severity each.
- Temperature-as-emotion — hot/cold replacing specific emotional description. Medium severity each.
- Physical tell clichés — jaw/throat/breath/hands as interchangeable emotion props. Medium severity each.
- Anthropomorphized silence — "the silence stretched" treats silence as an actor. Medium severity each.
- Ending clichés — "And for now, that was enough" summary posing as closure. Medium severity each.
- Catalog prose — paragraphs that are only names, milestones, feature labels with no material consequence attached. If each paragraph reads as a single category label, flag. Medium severity each.
- System-tour prose — paragraphs mapping one-to-one with predictable category buckets (background, mechanism, impact, verdict). Medium severity each.
- Concession rhythm — "not X, but Y" or "may sound X, but Y" used reflexively as paragraph scaffold across multiple paragraphs. Medium severity each.
- Type-definition endings — "the kind of X where Y" used as default paragraph closure appearing multiple times. Medium severity each.
- Uniform sentence length — monotonous sentences that stay in a narrow length band with no variation. Medium severity each.
- Standalone "Because" fragments — "Because she can't bear to look." AI sentence rhythm. Low severity each.

### Formatting — Low severity each
- Title Case Headings
- Inline-header lists (**Term:** description)
- Compound-modifier over-hyphenation (before-noun vs. after-noun, -ly adverb compounds, ever- compounds)
- Curly quotes (“ ”) — should be straight quotes (")
- Filler phrases ("in order to", "due to the fact that", "at this point in time", "the system has the ability to")
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
- After the summary, add one line: `Reply "fix" to apply corrections.`
