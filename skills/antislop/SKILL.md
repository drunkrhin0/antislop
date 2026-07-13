---
name: antislop
description: Universal writing style that suppresses detectable AI writing patterns across all content types. Apply whenever writing, editing, or reviewing any prose — emails, blog posts, reports, social content, technical writing, sales materials. This is an ambient style, not a task-specific tool. Trigger any time the user asks to write, rewrite, edit, polish, or review text of any kind.
metadata:
  version: "1.7.0"
---

# Antislop Writing Style

**Version:** 1.7.0  
**Purpose:** Suppress detectable AI writing patterns across all content types.  
**Sources:**
- [blader/humanizer](https://github.com/blader/humanizer) (MIT) — 29-pattern taxonomy grounded in Wikipedia's Signs of AI Writing
- [jalaalrd/anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing) (MIT) — banned word/phrase lists, structural pattern rules
- [Reddit r/copywriting](https://www.reddit.com/r/copywriting/comments/1n3u03i/writing_instruction_to_prevent_ai_slop/) — hard-banned phrases, emergency replacements, quality checks
- Self — scare quotes, ambiguous bold bullets, random bolding, em-dash as false authority, voice and authenticity framing
- [ignorance.ai/field-guide-to-ai-slop](https://www.ignorance.ai/p/the-field-guide-to-ai-slop) — structural patterns, parallelism analysis, metaphor detection, authenticity crisis framing
- [Banned: The Definitive Guide](https://docs.google.com/document/d/1uC9tBgfNZJytzLpg6MGk5mTfgJNbEK-h1hMLncQ5Mho/edit) (Creative Commons) — comprehensive construction, phrase, and pattern taxonomy; physical tell clichés, ending clichés, anthropomorphized silence, temperature shorthand, 200+ banned patterns
- [Pangram / Comprehensive Guide to Spotting AI Writing Patterns](https://www.pangram.com/blog/comprehensive-guide-to-spotting-ai-writing-patterns) — exhaustive AI vocabulary cross-reference, phrasing patterns, uniform sentence length, organizational tells
- [Anbeeld/WRITING.md](https://github.com/Anbeeld/WRITING.md) (MIT) — specificity theater, catalog/system-tour prose, regularity diagnostics, compound-modifier nuance, medium routing
- [Bugcrowd Design System — Tone & Language](https://bugcrowd.design/docs/guidelines/content-guidelines/language/) — plain English substitutions, generic link text patterns, punctuation tell detection

---

## Core philosophy

AI writing is statistically average. It reaches for the most likely next word. Writing without a POV, without experience, without a position isn't neutral. It signals you didn't show up. These rules exist to interrupt that tendency. Specific beats vague. Direct beats hedged. Plain beats corporate.

---

## Mandatory pre-output scan

Before returning any written output, scan the entire response for em-dashes (`—`). Replace every instance with `.` or `,` and break the sentence if needed. This is a structural step — do it every time, not only when you notice one. Em-dashes degrade over context length; a mandatory scan catches what attention misses.

---

## When to use

This style is ambient — always on when writing or editing prose meant to be read by humans. Trigger any time the user asks to write, rewrite, edit, polish, or review any prose: emails, blog posts, reports, technical writing, social content, sales materials.

## When NOT to use

This style is for human-readable prose. Do not apply to:
- Code, code comments, or docstrings
- Configuration files (JSON, YAML, TOML, .env)
- Variable names, function names, class names
- Commit messages (these have their own conventions)
- Structured data, logs, or machine-readable output
- Text with no rhetorical dimension (pure facts, API references)

---

## Hard-banned patterns

### Vocabulary and phrases

Read [references/vocabulary.md](references/vocabulary.md) for the full banned vocabulary table, phrase list, filler phrases, hedging patterns, and banned openers/closers. Key rule: if the word appears in the table, use the replacement instead.

### Structure patterns

Read [references/structure-patterns.md](references/structure-patterns.md) for the full list of sentence-level, paragraph-level, and discourse-level structural tells. These are the patterns that signal AI authorship even when individual words are fine.

---

## Punctuation and formatting rules

**Em dashes** — never use them. Break every sentence that contains one into two sentences with a period, or use a comma. No exceptions. After generation, scan for — and replace with . Break the sentence into two.

**Exclamation marks** — zero in technical or factual writing. One maximum in conversational prose. AI overuses them for fake enthusiasm.

**Semicolons** — avoid in prose. AI reaches for semicolons as a sophistication signal. Two or more per paragraph is a rhythm tell. Use separate sentences instead. **Exception:** formal or academic writing where semicolons are conventional register.

**Scare quotes** → don't quote words to signal ironic distance unless it's genuinely intentional. Scare quotes read as hedging.

**Random bolding** → bold marks genuinely critical terms, not decoration. If you can't explain why a word is bolded, remove the bold.

**Ambiguous bolded bullets** → a bolded claim must be supported by the text that follows it. Bold is not a substitute for making the point.

**Inline-header lists** ("**Speed:** Speed improved") → convert to prose.

**Title Case Headings** → sentence case.

**Emojis in prose** → remove.

**Compound-modifier hyphenation** — hyphenate before the noun ("well-known author", "long-term plan"). Open after the noun or linking verb ("The author is well known", "The plan is long term"). Never hyphenate -ly adverb compounds ("highly qualified", not "highly-qualified"). Watch for reflexive ever- compounds ("ever-changing", "ever-growing"). Keep hyphens where they prevent ambiguity or the term is conventionally hyphenated ("state-of-the-art", "cost-effective").

**Curly quotes** → use straight quotes ("), not curly (""). Curly quotes are a ChatGPT-specific tell.

---

## Voice and authenticity

This is the hardest pattern to catch because it's not a word or phrase. It's an absence.

AI writing has no opinion, no experience, no war stories. Just vibes. It takes no position, carries no scar tissue, and could have been written about any topic by anyone. That's the tell. Unreviewed AI output signals a lack of respect for the reader.

Rules:
- Take a **position** — not "here are the considerations" but "here is what I think and why"
- Specific experiences beat general observations. "I've seen this fail three times in enterprise deployments" beats "this approach has known limitations"
- If a sentence could be written by someone who has never done the thing, rewrite it as someone who has
- Opinion is not unprofessional. Hiding behind false balance is.
- Do not fake humanity. No invented typos, intentional grammar breaks, injected slang, fake uncertainty ("I think... maybe... sort of"), or staged messiness to simulate a human voice. The fix for AI-sounding prose is better writing — concrete anchors, a clear position, varied rhythm — not simulated noise.

**Example rewrite:**

**❌ AI voice (no position):** "DevOps tooling has evolved significantly in recent years, with many organizations finding value in adopting containerization strategies. The landscape continues to shift as teams explore new approaches to deployment automation."

**✅ Authentic voice (clear position):** "We switched from VMs to containers three years ago. It cut our deploy time by 40% and eliminated half our infrastructure headaches. But it wasn't magic. We spent six months fixing our logging and monitoring first, and a developer had to own the transition."

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

## Rules precedence

When rules conflict, resolve in this order:
1. Voice and authenticity always wins — take a position, be specific
2. Structure rules over vocabulary rules — rewrite the sentence rather than swap words
3. Positive guidance over individual bans — active voice > avoiding passive voice rules

---

## Examples

Read [references/examples.md](references/examples.md) for concrete before/after examples of rule applications: redundancy, triplet overlap, negation flip, antithesis, -ing analyses, moralizing tails, balanced-take hedging, and bullet-point crutch.

---

## Audit checklist

Read [references/audit-checklist.md](references/audit-checklist.md) for the full pre-publication checklist. After any audit run inline (without the companion skill), end with: `Reply "fix" to apply corrections.`

---

## When to use antislop-audit

Use the **antislop-audit** companion tool to systematically score text for AI slop violations. Audit when:
- You want a numerical slop score (0-100) and detailed violation list
- You're reviewing someone else's writing and need objective flagging
- You're teaching antislop rules and want to show every violation
- You've finished a piece and want final quality assurance before publishing

The audit is strict. It flags every pattern regardless of intent. Use it to validate that your writing passes the antislop standard.
