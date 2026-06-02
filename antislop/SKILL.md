---
name: antislop
version: "1.3"
description: Universal writing style that suppresses detectable AI writing patterns across all content types. Apply whenever writing, editing, or reviewing any prose — emails, blog posts, reports, social content, technical writing, sales materials. This is an ambient style, not a task-specific tool. Trigger any time the user asks to write, rewrite, edit, polish, or review text of any kind.
---

# Antislop Writing Style

**Version:** 1.3  
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

---

## Core philosophy

AI writing is statistically average. It reaches for the most likely next word. Writing without a POV, without experience, without a position isn't neutral. It signals you didn't show up. These rules exist to interrupt that tendency. Specific beats vague. Direct beats hedged. Plain beats corporate.

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

## Hard-banned patterns

### Vocabulary — never use

| Word | Replace with |
|---|---|
| delve | dig into, explore, research |
| leverage | use, tap, make the most of |
| tapestry | mix, range, collection |
| testament | proof, sign, evidence |
| vibrant | lively, busy, active, growing |
| pivotal | key, critical, central |
| utilize | use |
| synergy | collaboration, integration, or be specific |
| holistic | complete, full-stack, or say what parts it covers |
| robust | reliable, handles edge cases, or stays up |
| seamless | works without friction, no setup needed |
| groundbreaking | new, first, fastest, or state the advantage |
| cutting-edge | new, first, fastest, or state the advantage |
| innovative | new, different, or describe what it actually does |
| dynamic | describe the actual change or quality |
| comprehensive | full, complete, thorough |
| embark | start, begin |
| foster | support, encourage, build |
| ensure | make sure (or restructure the sentence) |
| explore | look into, try, study, test |
| revolutionize | change, overhaul, replace |
| transformative | changed X, made Y possible |
| empower | enable, allow, make possible |
| unlock | enable, allow, make possible |
| supercharge | speed up, boost, improve |
| significant | say how significant (3x faster, 40% reduction) |

### Phrases — never use
- "It's worth noting that" — delete it, state the thing directly
- "In today's fast-paced world" / "in today's landscape" → "Right now" or "Currently"
- "Ever-evolving landscape" / "dynamic world of" / "in the realm of"
- "At its core" / "at the end of the day" / "the real question is" / "what really matters" / "fundamentally" / "in reality" / "the deeper issue is" — rhetorical cut-to-the-chase that adds ceremony without substance
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

### Filler phrases — never use
- "In order to" → "To"
- "Due to the fact that" → "Because"
- "At this point in time" → "Now"
- "The system has the ability to" → "The system can"
- "It is important to note that" → Drop it, state the thing
- "It's crucial to" → "You need to" or just state the thing

### Hedging — never use
- "Could potentially possibly" / "it might have some effect" / "it could be argued that" — one qualifier is fine. Three is a tell.

### Openers and closers — never use
- "In conclusion" / "To summarize" / "To wrap up"
- "Certainly" / "Absolutely" / "Great question"
- "You're absolutely right" / "That's a great point"
- "I hope this helps!" / "Let me know if you have questions!"
- "Moreover" / "Furthermore" / "Additionally" — max once per 800 words; never consecutive

### Structure — never use

**Sentence-level:**

- Rule of three inside a single sentence ("innovation, inspiration, and insights")
- Synonym cycling — pick a word and repeat it; don't rotate through near-synonyms
- Copula avoidance — "serves as", "boasts", "features", "functions as", "stands as" when "is" or "has" would do the same job with half the ceremony
- Superficial -ing analyses — "highlighting", "underscoring", "symbolizing", "reflecting", "contributing to" tacked onto sentence ends to add fake depth. Say what actually happened.
- Significance inflation ("pivotal moment in the evolution of...")
- Passive voice / subjectless fragments ("No configuration file needed", "Results are preserved automatically") — use active voice
- Rhetorical emphasis tails — ending sentences with "..., that's the thing", "..., and that's what matters", "..., that's the hard truth". Also moralizing tails tacked on whether the text earned it or not: "Why it matters:", "Here's what I learned:", "This shows that...". If the sentence needs a punchline, rewrite it so the whole thing lands. If the takeaway isn't earned by the preceding content, cut it.
- Rhetorical-question hooks — "The kicker?", "The issue?", "The twist?", "Do you know what I realized?", "And do you know what I learned from all this?". Fake conversational drama as openers. Lead with the point instead.
- Balanced-take hedging — "While X is true, we must also consider Y" as a sentence scaffold. Related to false-balance in Voice. If you have a real contrast to make, make it with specifics. If not, state your position and move on.
- Simile-as-adverb — "with the [noun] of someone [verb]ing." "With the weariness of someone who had explained this before", "with the caution of someone approaching a wild animal." Invents a hypothetical person to describe the actual person's state. Just describe what they're actually doing or feeling.
- Hedged reactions — "a laugh that isn't quite a laugh", "a smile that isn't quite a smile", "a sigh that isn't quite a sigh." Substitutes contradiction for depth. Creates emotional static where the reader can't visualize what's happening. Describe the actual gesture.
- Standalone "Because" fragments — "Because she can't bear to look." "Because it's easier than lying." An AI sentence rhythm that imitates intimacy but signals shorthand thinking. Integrate the reason into the preceding sentence or show the cause through action.
- Temperature-as-emotion — "cold gaze", "warmth spread through her", "ice in his veins", "heat pooled low." Binary hot/cold replacing specificity. Every emotion narrows to the same two options. Name the actual feeling or show the behavior.
- Physical tell clichés — jaw tightening, throat bobbing, breath catching, hands curling into fists, spine stiffening. Interchangeable body language that flattens distinct characters into identical nervous systems. Replace with character-specific responses.
- Uniform sentence length — monotonous sentences that don't vary in length or rhythm. AI stays in a narrow band of 15-25 words per sentence, every sentence. Human writing mixes short and long. Aim for 20-30% of sentences under 10 words, some over 25.
- Overlong sentences — 5+ commas, nested clauses, 3+ ideas in one sentence. AI refuses to end it because it keeps qualifying, hedging, and adding detail. Break into two or three. Periods are free.

**Paragraph-level:**

- All paragraphs the same length
- Parataxis — 3+ consecutive short declarative sentences with no connective tissue. It reads like a poem. It signals AI authorship. Merge or subordinate.
- Generic subject loops — 3+ sentences opening with the same vague pronoun ("They get... They ask... They want...") or the same impersonal construction ("You're going to... You're here to..."). Name the actual subject and vary openers.
- Fragmented headers — a heading followed by a one-line paragraph that just restates the heading before the real content begins. Let the heading stand.
- Anthropomorphized silence — "the silence stretched between them", "deafening silence", "the silence hung thick and suffocating." Treating silence as an actor rather than showing its effect on people. Silence doesn't do things. Show who breaks it, who endures it, what it costs.
- Paragraph-level redundancy — when paragraph 2 opens by restating paragraph 1's conclusion, or the same concept appears twice across paragraphs with different supporting details. Also intra-paragraph restatement — the concluding sentence that just summarizes the paragraph in different words. Consolidate or cut the weaker version. Antislop catches sentence-level patterns. This is a manual content/logic check.
- Artificial line breaks — prose broken mid-sentence at terminal width (~80 chars) is an LLM artifact. Humans write continuous paragraphs. Break only for new thoughts.
- Bullet-point crutch — using bullet lists to dodge writing full paragraphs when prose would communicate more clearly. Bullets are for breakdowns, not paragraph avoidance.
- Concession rhythm — "not X, but Y" / "may sound X, but Y" used reflexively as a paragraph scaffold. Concede, then correct. When multiple paragraphs follow this arc, the rhythm becomes the tell. Break at least one occurrence with a direct statement or a different move.
- Type-definition endings — "the kind of X where Y" used as a default paragraph closure. If multiple paragraphs end with this classifying shape, rewrite the closers to carry forward rather than categorize.

**Discourse-level:**

- Announcing your structure ("First I'll discuss... then I'll cover...")
- Negative parallelisms and trailing negations — "not just X, but Y", "it's not about X, it's about Y", "X isn't the problem, Y is", and trailing fragments like "..., no guessing" or "..., no exceptions". Define the thing by what it is, not what it isn't.
- Negation flip — stating what something isn't immediately before stating what it is, used as rhetorical padding rather than genuine contrast. "This isn't a support desk. The goal is..." / "These aren't hoops. They're how..." / "This is not discovery — it's logistics." If the negation adds no information the positive statement doesn't already carry on its own, cut it and lead with the positive statement.
- False ranges ("from the Big Bang to dark matter") as rhetorical filler
- Promotional language ("nestled within the breathtaking...")
- Notability name-dropping — listing media outlets without context for what each said ("cited in NYT, BBC, FT, and The Hindu"). Either cite what a specific source actually reported or cut the name-drop.
- Triplet overlap — when 3+ descriptors name the same underlying quality rather than distinct things, consolidate to one descriptor or one phrase. "Current, documented, and auditable" all mean "reliable for attestation." Valid triplets name distinct categories: "policies, controls, and exceptions." Antislop catches form. Only a human can judge whether the meaning is distinct.
- Awkward AI metaphors — metaphors that gesture toward meaning without achieving it. Generic, plausible, but unanchored to specific experience. "Learning an instrument is a mirror for learning itself: messy, slow, and quietly addictive" could describe anything. Human metaphors are rooted: "Our deploy pipeline was like a Jenga tower — every sprint we'd pull one block and hope nothing fell." If the metaphor applies equally well to any topic, cut it.
- Ending clichés — "And for now, that was enough", "It was a start", "They would figure it out. Somehow.", "Nothing would ever be the same." Summary posing as closure. Labels emotional meaning rather than letting it emerge from action. End on action, decision, or consequence instead.
- Specificity theater — invented specifics deployed to pass a "be concrete" check. Includes synthetic quotes, suspicious decimal precision ("47.3%"), decorative factuality (dates/numbers added that weren't in source material), and hidden-mechanism narration (claiming to know what a system "really" does under the hood without observable evidence). If you cannot verify a claim, attribute it, soften it, or cut it. An invented number is worse than "many" because it reads authoritative while being fabricated.
- Catalog prose — a paragraph that is mainly names, milestones, categories, feature nouns, or system labels with no material consequence attached. If each paragraph can be summarized with a single label ("background", "mechanism", "impact"), the piece is a catalog, not an argument. Pick one change and trace its consequence.
- System-tour prose — paragraphs that map one-to-one with predictable category buckets. Background paragraph, mechanism paragraph, impact paragraph, verdict paragraph. Cross-wire the piece so paragraphs depend on each other rather than sitting like labeled boxes.

---

## Punctuation and formatting rules

**Em dashes** — never use them. Break every sentence that contains one into two sentences with a period, or use a comma. No exceptions. After generation, scan for — and replace with . Break the sentence into two. Em-dashes as a rhetorical authority prop ("— not through magic, not through hype, but through hard work") are the worst offender — if the em-dash is padding a claim instead of making the argument, the sentence wasn't doing its job. Rewrite it.

**Scare quotes** → don't quote words to signal ironic distance unless it's genuinely intentional. Scare quotes read as hedging. The writer distances themselves from their own word. Own it or cut it.

**Random bolding** → bold marks genuinely critical terms, not decoration. If you can't explain why a word is bolded, remove the bold.

**Ambiguous bolded bullets** → a bolded claim must be supported by the text that follows it. Bold is not a substitute for making the point.

**Inline-header lists** ("**Speed:** Speed improved") → convert to prose.

**Title Case Headings** → sentence case.

**Emojis in prose** → remove.

**Compound-modifier hyphenation** — hyphenate before the noun ("well-known author", "long-term plan"). Open after the noun or linking verb ("The author is well known", "The plan is long term"). Never hyphenate -ly adverb compounds ("highly qualified", not "highly-qualified"). Watch for reflexive ever- compounds ("ever-changing", "ever-growing"). Keep hyphens where they prevent ambiguity or the term is conventionally hyphenated ("state-of-the-art", "cost-effective"). The problem is the reflex, not the mark.

**Curly quotes** → use straight quotes ("), not curly (“”). Curly quotes are a ChatGPT-specific tell.

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

## Rules precedence

When rules conflict, resolve in this order:
1. Voice and authenticity always wins — take a position, be specific
2. Structure rules over vocabulary rules — rewrite the sentence rather than swap words
3. Positive guidance over individual bans — active voice > avoiding passive voice rules

---

## Examples — hard rules

**Paragraph-level redundancy (inter-paragraph):**
❌ "The new pipeline cut deploy time by 40%. Teams went from 20-minute deploys to under 12. This reduction in deploy time means teams ship faster and get feedback sooner."
✅ "The new pipeline cut deploy time by 40%. Teams went from 20-minute deploys to under 12. Engineers stopped context-switching while waiting for builds, and the QA team cleared their backlog in a week."

**Paragraph-level redundancy (intra-paragraph restatement):**
❌ "We migrated to the new API in Q2. The migration took three weeks and involved updating 12 services. Overall, this was a significant migration that required substantial effort."
✅ "We migrated to the new API in Q2. The move took three weeks, touched 12 services, and broke billing twice before we got it right."

**Triplet overlap:**
❌ "The system must be current, documented, and auditable." (all three mean "reliable for attestation")
✅ "The system must be auditable." (or pick the one that matters)

**Negation flip:**
❌ "This isn't a support desk. The goal is to give engineers a self-service debugging toolkit."
✅ "Engineers get a self-service debugging toolkit instead of filing tickets."

**Superficial -ing analyses:**
❌ "Response times dropped 30% last quarter, highlighting the effectiveness of the new caching layer."
✅ "Response times dropped 30% last quarter. The new caching layer was responsible — it moved the 95th percentile from 800ms to 120ms."

**Moralizing tails:**
❌ "We shut down the legacy monolith in March. Two years of planning, six months of migration, one outage. Why it matters: teams now own their own deployments end to end."
✅ "We shut down the legacy monolith in March. Two years of planning, six months of migration, one outage. Teams now own their own deployments end to end."

**Balanced-take hedging:**
❌ "While microservices offer flexibility, we must also consider that monoliths are simpler to operate."
✅ "Microservices solved our scaling problem but gave us a debugging problem. For teams under 10 engineers, a monolith is still the right call."

**Bullet-point crutch:**
❌ "The new onboarding flow improves the experience. • Welcome email with clear CTA. • Guided setup wizard with tooltips. • Personalized dashboard with relevant widgets. • Achievement badges for completing milestones."
✅ "The new onboarding flow drops you into a guided setup wizard. You get a welcome email, sure, but the real work happens in the wizard. Tooltips walk you through each step. By the time you reach the dashboard, it's already populated with your actual data, not placeholder widgets."

---

## Audit checklist

Before finishing any piece of writing. After any audit run inline (without the companion skill), end with: `Reply "fix" to apply corrections.`

- [ ] Searched for all hard-banned phrases
- [ ] Em-dash count checked — zero permitted. Scan and replace any — with . or ,
- [ ] Scare quotes checked — do they earn it or are they hedging?
- [ ] Bolded text checked — intentional or decorative?
- [ ] Bolded bullets checked — does the body support each claim?
- [ ] No 3+ consecutive paragraphs starting with the same word
- [ ] Read aloud — does it sound like a person who has done this thing?
- [ ] Vague claims replaced with specific ones
- [ ] Does this have a position, or just vibes?
- [ ] Paragraph-level check — any paragraph restating another paragraph's idea in different words? Consolidate or cut.
- [ ] Triplet check — any 3+ descriptor cluster where items describe the same quality? Consolidate to one.
- [ ] Line-break check — any mid-sentence breaks that exist only to fit terminal width? Join into continuous paragraphs.
- [ ] Rhetorical-question hooks — any "The kicker?" / "The issue?" style openers? Lead with the point.
- [ ] Balanced-take check — any "While X is true, we must also consider Y" hedging? State your position or cut.
- [ ] Bullet-point check — are bullets used as a crutch to dodge writing paragraphs? Convert to prose where stronger.
- [ ] Metaphor check — any analogies that feel generic and could apply to any topic? Root them in specifics or cut.
- [ ] Simile check — any "with the [noun] of someone [verb]ing" constructions? Describe the actual behavior.
- [ ] Hedged reaction check — any "a [reaction] that isn't quite a [reaction]"? Describe the actual gesture.
- [ ] "Because" fragment check — any standalone "Because [X]" sentences? Integrate or show through action.
- [ ] Temperature check — any hot/cold as emotion shorthand? Name the feeling or show the behavior.
- [ ] Physical tell check — any jaw/throat/breath/hands as emotion props? Replace with character-specific responses.
- [ ] Sentence-length check — any monotonous run of same-length sentences? Vary: some under 10 words, some over 25.
- [ ] Overlong-sentence check — any sentence with 5+ commas and nested clauses? Break into two or three.
- [ ] Silence check — any silence "stretching" or "hanging"? Show effect on people instead.
- [ ] Ending check — any "And for now, that was enough" style closure? End on action, decision, or consequence.
- [ ] Specificity check — any unverifiable claims, invented specifics, or hidden-mechanism narration? Attribute, soften, or cut.
- [ ] Catalog check — any paragraphs that are only names/dates/features with no material consequence? Trace one consequence.
- [ ] Concession rhythm check — any "not X, but Y" used reflexively across multiple paragraphs? Break at least one.
- [ ] Type-definition check — any "the kind of X where Y" endings used repeatedly? Rewrite the closers.
- [ ] Overcorrection check — any fake-human moves (invented typos, slang, staged messiness) added to break a pattern? Cut them — fix the prose instead.

---

## When to use antislop-audit

Use the **antislop-audit** companion tool to systematically score text for AI slop violations. Audit when:
- You want a numerical slop score (0-100) and detailed violation list
- You're reviewing someone else's writing and need objective flagging
- You're teaching antislop rules and want to show every violation
- You've finished a piece and want final quality assurance before publishing

The audit is strict. It flags every pattern regardless of intent. Use it to validate that your writing passes the antislop standard.
