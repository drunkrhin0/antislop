# Style mode reference

Load this reference only for writing, editing, rewriting, polishing, and related prose work.

## Core philosophy

AI writing is statistically average. It reaches for the most likely next word. Writing without a POV, without experience, without a position isn't neutral. It signals you didn't show up. Specific beats vague. Direct beats hedged. Plain beats corporate.

---

## Mandatory pre-output scan

**Em dashes, en dashes, and double hyphens** are forbidden. Before returning any written output, scan the entire response for `—`, `–`, and ` -- `. If count > 0, the draft is not done. Replace every instance with `.` or `,` and break the sentence if needed.

---

## Rewrite loop

Use this compact loop when rewriting prose:

1. Scan for the relevant patterns.
2. Rewrite while preserving meaning, facts, intended tone, and the writer's signals.
3. Restore a clear position, concrete detail, and natural rhythm.
4. Run one short final pass for remaining tells.

The final pass is not a full audit. Load the detailed audit checklist for a long or high-stakes piece, or when the user asks for an audit or score.

---

## Hard-banned patterns

### Vocabulary and phrases

Read [vocabulary.md](vocabulary.md) for the full banned vocabulary table, phrase list, filler phrases, hedging patterns, and banned openers/closers. Key rule: if the word appears in the table, use the replacement instead.

### Structure patterns

Read [structure-patterns.md](structure-patterns.md) for the full list of sentence-level, paragraph-level, and discourse-level structural tells. These are the patterns that signal AI authorship even when individual words are fine.

---

## Punctuation and formatting rules

**Exclamation marks** — zero in technical or factual writing. One maximum in conversational prose. AI overuses them for fake enthusiasm.

**Semicolons** — avoid in prose. AI reaches for semicolons as a sophistication signal. Two or more per paragraph is a rhythm tell. Use separate sentences instead. **Exception:** formal or academic writing where semicolons are conventional register.

**Scare quotes** → don't quote words to signal ironic distance unless it's genuinely intentional. Scare quotes read as hedging.

**Random bolding** → bold marks genuinely critical terms, not decoration. If you can't explain why a word is bolded, remove the bold.

**Ambiguous bolded bullets** → a bolded claim must be supported by the text that follows it. Bold is not a substitute for making the point.

**Inline-header lists** ("**Speed:** Speed improved") → convert to prose.

**Title Case Headings** → sentence case.

**Emojis in prose** → remove.
**Emoji as bullet markers** (✅, 👉, 🔥, 💡 prefixed to list items) → convert to plain bullets or prose.

**Compound-modifier hyphenation** — hyphenate before the noun ("well-known author", "long-term plan"). Open after the noun or linking verb ("The author is well known", "The plan is long term"). Never hyphenate -ly adverb compounds ("highly qualified", not "highly-qualified"). Watch for reflexive ever- compounds ("ever-changing", "ever-growing"). Keep hyphens where they prevent ambiguity or the term is conventionally hyphenated ("state-of-the-art", "cost-effective").

**Curly quotes** → use straight quotes ("), not curly (""). Curly quotes are a ChatGPT-specific tell.

---

## Voice and authenticity

This is the hardest pattern to catch. It's an absence.

AI writing has no opinion, no experience, no war stories. It takes no position, carries no scar tissue, and could have been written about any topic by anyone. That's the tell. Unreviewed AI output signals a lack of respect for the reader.

Rules:
- Take a **position** — not "here are the considerations" but "here is what I think and why"
- Specific experiences beat general observations. "I've seen this fail three times in enterprise deployments" beats "this approach has known limitations"
- If a sentence could be written by someone who has never done the thing, rewrite it as someone who has
- Opinion is not unprofessional. Hiding behind false balance is.
- Say what it does, not how it feels. Name the mechanism, behavior, result, or number. If a sentence could appear unchanged in another project's documentation, make it specific or cut it.
- Treat words such as "enduring" as context-dependent. Replace them when repetition or generic praise such as "enduring legacy" substitutes for a concrete claim. Do not ban the word by itself.
- Keep humanity honest. Use concrete anchors, a clear position, varied rhythm, clean grammar, and the author's real register. Invented typos, injected slang, staged uncertainty, and deliberate messiness simulate a voice instead of preserving one.
- Before editing, identify the writer's signals: vocabulary, cadence, bluntness, humor, digressions. Treat them as load-bearing. Don't smooth distinctive traits into consistency. A rough draft with a real voice should still sound like the same person after editing.
- Protect the specific fact during editing. Don't smooth a real detail ("cut deploy time from 40 minutes to 4") into generic importance ("significantly improved efficiency"). Real specifics anchor writing. Abstracting them destroys the most valuable part of the draft.

**Example rewrite:**

**❌ AI voice (no position):** "DevOps tooling has evolved significantly in recent years, with many organizations finding value in adopting containerization strategies. The landscape continues to shift as teams explore new approaches to deployment automation."

**✅ Authentic voice (clear position):** "We switched from VMs to containers three years ago. It cut our deploy time by 40% and eliminated half our infrastructure headaches. But it wasn't magic. We spent six months fixing our logging and monitoring first, and a developer had to own the transition."

---

## Positive guidance

Apply these as actions, not prohibitions. They never count against a score; a short document with no occasion for a behavior is not penalized.

- Mix sentence lengths. Aim for 20-30% of sentences under 10 words.
- Use contractions where appropriate (you're, don't, can't)
- Sentence fragments are fine for emphasis. Use them.
- Write technical prose as complete sentences when shorthand impedes reading. Restore dropped articles and verbs, and spell out arrows or unexplained abbreviations. Keep purposeful fragments, tables, diagrams, code, and compact reference syntax.
- Specific numbers over vague quantities — "7 out of 12" not "many"
- Name sources when citing trends or studies
- At least one concrete example per main point
- Active voice: "you'll configure" not "configuration should be done"
- Replace a weak verb plus padding adverb with a stronger verb or a measured result. "Significantly improved" should become the actual change or number.
- Vary paragraph length — some one line, some four

## Document structure

Apply these as actions, not prohibitions. They never count against a score; a short document with no occasion for a behavior is not penalized.

- Open with the claim or conclusion; support it after
- Develop one point per paragraph
- Trace one change to its consequence instead of listing names and milestones
- End on action, decision, or consequence instead of a summarizing cliche
- Make sections depend on each other instead of sitting in labeled buckets
