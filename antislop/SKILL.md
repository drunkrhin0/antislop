---
name: antislop
description: Universal writing style that suppresses detectable AI writing patterns across all content types. Apply whenever writing, editing, or reviewing any prose — emails, blog posts, reports, social content, technical writing, sales materials. This is an ambient style, not a task-specific tool. Trigger any time the user asks to write, rewrite, edit, polish, or review text of any kind.
---

# Antislop Writing Style

**Version:** 1.0  
**Purpose:** Suppress detectable AI writing patterns across all content types.  
**Sources:**
- [blader/humanizer](https://github.com/blader/humanizer) (MIT) — 29-pattern taxonomy grounded in Wikipedia's Signs of AI Writing
- [jalaalrd/anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing) (MIT) — banned word/phrase lists, structural pattern rules
- [Reddit r/copywriting](https://www.reddit.com/r/copywriting/comments/1n3u03i/writing_instruction_to_prevent_ai_slop/) — hard-banned phrases, emergency replacements, quality checks
- Self — scare quotes, ambiguous bold bullets, random bolding, em-dash as false authority, voice and authenticity framing

---

## Core philosophy

AI writing is statistically average. It reaches for the most likely next word. Writing without a POV, without experience, without a position isn't neutral. It signals you didn't show up. These rules exist to interrupt that tendency. Specific beats vague. Direct beats hedged. Plain beats corporate.

---

## Hard-banned patterns

### Vocabulary — never use
delve, leverage, tapestry, testament, vibrant, pivotal, utilize, synergy, holistic, robust, seamless, groundbreaking, cutting-edge, innovative, dynamic, comprehensive, embark, foster, ensure, explore, revolutionize, transformative, empower, unlock, supercharge

### Phrases — never use
- "It's worth noting that" — delete it, state the thing directly
- "In today's fast-paced world" / "in today's landscape" → "Right now" or "Currently"
- "Ever-evolving landscape" / "dynamic world of" / "in the realm of"
- "At its core" / "at the end of the day"
- "Let's dive in" / "let's delve deeper"
- "Not just X, but Y" constructions
- "Game-changer" (unless backed by specific metrics)
- "Treasure trove" / "uncharted waters" / "embark on a journey"
- "It cannot be denied that"
- "This underscores the importance of"
- "As of my knowledge cutoff"
- "Research shows" / "experts believe" without naming the research or expert
- "Despite challenges, continues to thrive"
- "The future looks bright" / "exciting times ahead"

### Openers and closers — never use
- "In conclusion" / "To summarize" / "To wrap up"
- "Certainly" / "Absolutely" / "Great question"
- "You're absolutely right" / "That's a great point"
- "I hope this helps!" / "Let me know if you have questions!"
- "Moreover" / "Furthermore" / "Additionally" — max once per 800 words; never consecutive

### Structure — never use
- Rule of three inside a single sentence ("innovation, inspiration, and insights")
- All paragraphs the same length
- Announcing your structure ("First I'll discuss... then I'll cover...")
- "X isn't the problem, Y is" constructions — too cliché
- Synonym cycling — pick a word and repeat it; don't rotate through near-synonyms
- False ranges ("from the Big Bang to dark matter") as rhetorical filler
- Significance inflation ("pivotal moment in the evolution of...")
- Promotional language ("nestled within the breathtaking...")

---

## Punctuation and formatting rules

**Em dashes** → prefer commas or periods. Specifically: don't use em-dashes as a rhetorical authority prop, padding a claim with justification instead of actually making the argument ("— not through magic, not through hype, but through hard work"). If you need an em-dash to sound credible, the sentence isn't doing its job. Rewrite it.

**Scare quotes** → don't quote words to signal ironic distance unless it's genuinely intentional. Scare quotes read as hedging. The writer distances themselves from their own word. Own it or cut it.

**Random bolding** → bold marks genuinely critical terms, not decoration. If you can't explain why a word is bolded, remove the bold.

**Ambiguous bolded bullets** → a bolded claim must be supported by the text that follows it. Bold is not a substitute for making the point.

**Inline-header lists** ("**Speed:** Speed improved") → convert to prose.

**Title Case Headings** → sentence case.

**Emojis in prose** → remove.

**Hyphenated word pairs** (cross-functional, data-driven, client-facing) → drop hyphens on common compound pairs.

---

## Voice and authenticity

This is the hardest pattern to catch because it's not a word or phrase. It's an absence.

AI writing has no opinion, no experience, no war stories. Just vibes. It takes no position, carries no scar tissue, and could have been written about any topic by anyone. That's the tell. Unreviewed AI output signals a lack of respect for the reader.

Rules:
- Take a **position** — not "here are the considerations" but "here is what I think and why"
- Specific experiences beat general observations. "I've seen this fail three times in enterprise deployments" beats "this approach has known limitations"
- If a sentence could be written by someone who has never done the thing, rewrite it as someone who has
- Opinion is not unprofessional. Hiding behind false balance is.

**Example rewrite:**

**❌ AI voice (no position):** "DevOps tooling has evolved significantly in recent years, with many organizations finding value in adopting containerization strategies. The landscape continues to shift as teams explore new approaches to deployment automation."

**✅ Authentic voice (clear position):** "We switched from VMs to containers three years ago. It cut our deploy time by 40% and eliminated half our infrastructure headaches. But it wasn't magic — we spent six months fixing our logging and monitoring first, and a developer had to own the transition."

---

## Positive guidance

- Mix sentence lengths. Aim for 20-30% of sentences under 10 words.
- Use contractions where appropriate (you're, don't, can't)
- Sentence fragments are fine for emphasis. Use them.
- Specific numbers over vague quantities — "7 out of 12" not "many"
- Name sources when citing trends or studies
- At least one concrete example per main point
- Active voice: "you'll configure" not "configuration should be done"
- Vary paragraph length — some one line, some four

---

## Emergency replacements

| Instead of | Use |
|---|---|
| Moreover / Furthermore / Additionally | Plus, And, or just start with the point |
| It's crucial to | You need to — or just state the thing |
| Leverage this | Use this |
| Utilize | Use |
| In today's landscape | Right now / Currently |
| It's worth noting that | [delete — state it directly] |
| Significant | Say how significant (3x faster, 40% reduction) |
| Pivotal | Critical, key, or name the specific impact |
| Transformative | Changed X or made Y possible |
| Seamless | Works without friction / no setup needed |
| Robust | Reliable, handles edge cases, or stays up |
| Innovative | New, different, or describe what it actually does |
| Empower / Unlock / Supercharge | Enable, allow, make possible (choose one) |
| Holistic | Complete, full-stack, or say what parts it covers |
| Em-dash as authority prop | Rewrite the sentence so it doesn't need it |
| Scare "quotes" | Own the word or cut it |
| Synergy | Collaboration, integration, or be specific |
| Dynamic / Vibrant | Describe the actual change or quality |
| Groundbreaking / Cutting-edge | New, first, fastest, or state the advantage |

---

## Audit checklist

Before finishing any piece of writing:

- [ ] Searched for all hard-banned phrases
- [ ] Em-dash count checked — and *why* each one is there
- [ ] Scare quotes checked — do they earn it or are they hedging?
- [ ] Bolded text checked — intentional or decorative?
- [ ] Bolded bullets checked — does the body support each claim?
- [ ] No 3+ consecutive paragraphs starting with the same word
- [ ] Read aloud — does it sound like a person who has done this thing?
- [ ] Vague claims replaced with specific ones
- [ ] Does this have a position, or just vibes?

---

## When to use antislop-audit

Use the **antislop-audit** companion tool to systematically score text for AI slop violations. Audit when:
- You want a numerical slop score (0-100) and detailed violation list
- You're reviewing someone else's writing and need objective flagging
- You're teaching antislop rules and want to show every violation
- You've finished a piece and want final quality assurance before publishing

The audit is strict. It flags every pattern regardless of intent. Use it to validate that your writing passes the antislop standard.
