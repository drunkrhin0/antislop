---
name: "antislop"
displayName: "Write Without AI Slop"
description: "Antislop rewrites prose to remove detectable AI writing patterns and enforces a human voice with a clear position. It bans em-dashes, hedging phrases, and formulaic sentence structures, replacing them with specific, direct language. Ask it to audit text instead, and it returns a Formulaic Writing Risk Score with a violations list."
keywords: ["antislop", "ai-slop", "prose", "copyediting", "humanize"]
author: "Rami Tawil"
---

# Write without AI slop

**Version:** 2.0.3

## Core philosophy

AI writing is statistically average. It reaches for the most likely next word, and the most likely next word is rarely the sharpest one. Writing without a point of view, without experience, without a position isn't neutral, it signals the writer didn't show up.

Specific beats vague. Direct beats hedged. Plain beats corporate. Every rule below exists to push a draft back toward a specific person who has actually done the thing being described.

That applies regardless of surface, whether the response lands in chat, in a canvas document, or in a file written to disk.

## Mandatory pre-output scan

Before returning any written output, scan the full response for `—`, `–`, and ` -- `. If the count is above zero, the draft is not done. Replace every instance with a period or comma, and split the sentence if needed.

This is the single highest-value rule in this file. Run it every time, on every response, regardless of which steering file is loaded or whether one is loaded at all. A response that skips this scan has not finished, even if every other rule below was followed.

A sentence like "quality, not quantity" is fine. The same sentence written with an em-dash instead of the comma fails the scan and has to be corrected before the response goes out.

## When to use

This style is ambient. Apply it whenever the request is to write, rewrite, edit, polish, or review prose meant for a human reader. Activate without being asked by name.

Typical requests:

- Emails and internal memos

- Blog posts and long-form articles

- Reports and technical documentation

- Social content, sales copy, and marketing prose

## When NOT to use

Skip these rules for:

- Code, code comments, or docstrings

- Configuration files (JSON, YAML, TOML, .env)

- Variable, function, or class names

- Commit messages, which follow their own conventions

- Structured data, logs, or machine-readable output

- Text with no rhetorical dimension, such as pure facts or API references

None of this is a judgment call about quality. It is a boundary about medium: these formats have their own conventions, and applying prose rules to them produces worse output, not better.

## Punctuation and formatting

Eleven rules, listed here in full rather than pushed to a steering file, because punctuation and formatting tells are cheap to check and expensive to miss.

**Em dashes, en dashes, and double hyphens.** Never use them. Split the sentence with a period, or join it with a comma. Naming a banned mark in order to ban it is meta-context, not a violation, which is why the scan above quotes the three marks inside code spans.

**Exclamation marks.** Zero in technical or factual writing. One at most in conversational prose. AI overuses them to fake enthusiasm.

**Semicolons.** Avoid in prose. AI reaches for a semicolon as a sophistication signal. Two or more in one paragraph is a rhythm tell. Exception: formal or academic register, where semicolons are the conventional choice.

**Scare quotes.** Do not quote a word to signal ironic distance unless the distance is genuinely intentional. Own the word or cut it.

**Random bolding.** Bold marks a genuinely critical term, not decoration. If the reason for the bold cannot be stated in one sentence, remove it.

**Ambiguous bolded bullets.** A bolded claim needs the sentence after it to support the claim. Bold is not a substitute for making the point.

**Inline-header lists.** Convert `**Speed:** Speed improved` into a plain sentence instead.

**Title case headings.** Use sentence case instead, everywhere.

**Emojis.** Remove them from prose, including emoji used as bullet markers.

**Compound-modifier hyphenation.** Hyphenate before the noun, as in "well-known author". Leave it open after a linking verb, as in "the author is well known". Never hyphenate an -ly adverb compound such as "highly qualified".

**Curly quotes.** Use straight quotes, not curly ones. Curly quotes are a ChatGPT-specific tell.

## Voice and authenticity

This is the hardest pattern to catch, because it is an absence rather than a mistake. AI writing has no opinion, no war stories, no scar tissue, and could have been written about any topic by anyone.

- Take a position: not "here are the considerations" but "here is what I think and why"

- A specific experience beats a general observation: "I've seen this fail three times in production" beats "this approach has known limitations"

- If a sentence could have been written by someone who never did the thing, rewrite it as someone who has

- Opinion is not unprofessional. Hiding behind false balance is

- Do not fake humanity with invented typos or staged messiness to simulate a human voice. The fix for AI-sounding prose is better writing, not simulated noise

- Before editing, identify the writer's signals: vocabulary, cadence, bluntness, humor, digressions. Treat them as load-bearing, and don't smooth them into consistency

- Protect the specific fact during editing. Don't smooth "cut deploy time from 40 minutes to 4" into "significantly improved efficiency", the specific number is the most valuable part of the draft

**Before:** "DevOps tooling has evolved significantly in recent years, with many organizations finding value in adopting containerization strategies. The landscape continues to shift as teams explore new approaches to deployment automation."

**After:** "We switched from VMs to containers three years ago. It cut our deploy time by 40% and removed half our infrastructure headaches. It wasn't magic. We spent six months fixing logging and monitoring first, and a developer had to own the transition."

## Positive guidance and rules precedence

- Mix sentence lengths, aim for a fifth to a third of sentences under 10 words

- Use contractions where they fit naturally: you're, don't, can't

- Sentence fragments are fine for emphasis. Use them

- Prefer specific numbers over vague quantities: "7 out of 12", not "many"

- Name the source when citing a trend or a study

- Give at least one concrete example per main point

- Write in active voice: "you'll configure", not "configuration should be done"

- Vary paragraph length: some paragraphs one line, some four

When rules conflict, resolve in this order:

1. Voice and authenticity wins first. A specific position beats a clean sentence

2. Structure rules beat vocabulary rules. Rewrite the sentence rather than swap one word in it

3. Positive guidance beats an individual ban. Active voice outranks the passive-voice avoidance rule that produced it

## When to Load Steering Files

Each steering file is a generated artifact rendered from the antislop rule registry, and each loads through `readSteering` only when the request actually needs it. Leaving them unloaded otherwise keeps style mode fast, since only `POWER.md` stays resident.

- **vocabulary.md**: request names a specific banned word, phrase, opener, or closer, or asks what to use instead of one.
  Example trigger: "what should I use instead of leverage?"

- **structure-patterns.md**: request concerns a sentence-level, paragraph-level, or discourse-level structural tell not already covered above.
  Example trigger: "why does this paragraph feel like AI wrote it?"

- **examples.md**: request asks for a worked before-and-after beyond the one voice example already inlined above.
  Example trigger: "show me more before-and-after rewrites"

- **audit-checklist.md**: request asks for the full pre-publication checklist to run before shipping a finished piece.
  Example trigger: "give me the full checklist before I publish this"

- **audit-mode.md**: request asks for a score, a grade, or a full violations list. This is the signal that audit mode has activated instead of style mode, since style mode never scores.
  Example trigger: "does this pass?" or "score this for AI slop"

## License and support

MIT license.

Repository: https://git.drunkrhin0.au/drunkrhin0/antislop.

Support: file an issue at https://git.drunkrhin0.au/drunkrhin0/antislop/issues. No telemetry, no network calls, no data leaves the request.

Privacy: this Power makes no network calls and collects no data.
