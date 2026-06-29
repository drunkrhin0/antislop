# Antislop

*By slop for slop, to remove slop in an AI slop world.*

Written as a late shower thought from my ranting [LinkedIn post](https://www.linkedin.com/posts/tawilr_you-didnt-verify-this-and-i-can-tell-share-7460237564889944064-lXxs/)

Two skills for writing like a human. Works with your favourite agent that supports SKILL.md or AGENTS.md.

- **antislop**: a writing style skill. Ambient, always-on. Suppresses AI writing patterns across everything you write.
- **antislop-audit**: a detection skill. Scores text 0-100 and returns a violations list. Zero exceptions for intent.

It catches:

- Banned vocabulary and phrases
- Antithesis as tone management ("not just X but Y" that decorates instead of argues)
- Structural tells (sentence, paragraph, and discourse-level patterns)
- Formatting habits (em-dashes, scare quotes, bolding, title case)
- Rhythmic giveaways (uniform length, parataxis, overlong sentences)
- Voice-level absences (no opinion, no experience, no position)

---

## Installation

### Install with openskills (recommended)

```bash
npx openskills install drunkrhin0/antislop --global
```

This installs to `~/.claude/skills/` so the skills are available across all projects. Leave off `--global` to install in the current directory instead.

### Ask your agent

Just ask your agent to install `drunkrhin0/antislop` from GitHub. Most will figure it out. The repo includes an `AGENTS.md` file for automatic skill discovery.

### Gemini CLI

Copy the `antislop/` folder into your Gemini extensions directory:

```bash
mkdir -p ~/.gemini/extensions/antislop
cp antislop/gemini-extension.json ~/.gemini/extensions/antislop/
cp antislop/GEMINI.md ~/.gemini/extensions/antislop/
```

Gemini CLI picks it up automatically on next launch.

### Gemini web app (gemini.google.com)

Requires Gemini Advanced. Create a Gem:

1. Left sidebar → **Gem manager** → **New Gem**
2. Name it "Antislop"
3. Paste the contents of `antislop/GEMINI.md` into the instructions field
4. Save and use that Gem for writing

Free tier: paste `antislop/GEMINI.md` at the start of any chat instead.

### opencode agent (subagent)

A spawnable opencode subagent with two modes: style (writing) and audit (scoring). Lives in `.opencode/agents/antislop.md` in the repo.

Project-level use works automatically when the repo is cloned. opencode discovers `.opencode/agents/` in project directories. For global install, copy the agent file:

```bash
cp .opencode/agents/antislop.md ~/.config/opencode/agents/
```

Mention `@antislop` in opencode, or let the primary agent spawn it automatically when it detects a writing or auditing task. The agent is read-only: it returns corrected text or audit results, and the primary agent or user writes files.

The agent is a hand-maintained derivative of the canonical SKILL.md files, like GEMINI.md. When adding a rule, update the agent file alongside the other derivatives.

### Manual

Copy `antislop/` and `antislop-audit/` into your skills directory:
- Claude Code: `~/.claude/skills/`
- opencode: `~/.config/opencode/skills/`

For AI chats (Claude.ai, ChatGPT, etc.), paste `antislop/SKILL.md` at the start of a conversation for writing, or `antislop-audit/SKILL.md` to audit text.

---

## Usage

### Writing style (antislop)

Triggers automatically when you ask your agent to write or edit anything.

### Audit (antislop-audit)

Paste text and ask your agent to audit it with `/antislop-audit`

Returns a score out of 100, a violations table with severity and excerpt, and a plain-English summary of what to fix first.

**Score bands:**
- 85-100: Clean. Reads like a person.
- 65-84: Some slop. Fixable with targeted edits.
- 40-64: Heavy slop. Significant rewrite needed.
- 0-39: Severe. This reads like unreviewed AI output.

---

## How to use effectively

**Let it run ambiently.** Both skills trigger automatically when you ask your agent to write, edit, or audit text. They activate on matching intent. No manual invocation needed.

**Audit before sending, not while writing.** Write freely. Let antislop clean up sentence-level patterns in real time. The mandatory pre-output scan catches em-dashes that slip through. Then run antislop-audit as a final gate before publishing. The audit catches what the style misses: paragraph redundancy, triplet overlap, semantic repetition.

**Bring content, not just form.** Antislop catches patterns: sentence structure, banned words, rhythm tells. It does not catch vague ideas or unsupported claims. You still need to bring specific experience, numbers, examples, and a point of view.

**Run the checklist.** The skill includes a 20+ item audit checklist. Run through it before finishing any piece. The items at the bottom matter most: redundancy, triplet overlap, antithesis, metaphors, endings. They catch what pattern matching can't.

**Don't over-apply.** Antislop is for prose meant to be read by humans. Skip it for code, config files, commit messages, structured data, or API docs. Those have their own conventions.

**For Gemini users.** The Gem or GEMINI.md copy approach works best. Style mode outputs to Canvas only. No preamble, no commentary. Audit mode returns the score and violations in chat.

---

## Credits and inspiration

- [blader/humanizer](https://github.com/blader/humanizer) (MIT): 29-pattern taxonomy grounded in Wikipedia's Signs of AI Writing
- [jalaalrd/anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing) (MIT): banned word and phrase lists, structural pattern rules
- [Reddit r/copywriting](https://www.reddit.com/r/copywriting/comments/1n3u03i/writing_instruction_to_prevent_ai_slop/): hard-banned phrases, emergency replacements, quality checks
- [ignorance.ai/field-guide-to-ai-slop](https://www.ignorance.ai/p/the-field-guide-to-ai-slop): structural patterns, parallelism analysis, metaphor detection, authenticity crisis framing
- [Banned: The Definitive Guide](https://docs.google.com/document/d/1uC9tBgfNZJytzLpg6MGk5mTfgJNbEK-h1hMLncQ5Mho/edit) (Creative Commons): comprehensive construction, phrase, and pattern taxonomy
- [Pangram](https://www.pangram.com/blog/comprehensive-guide-to-spotting-ai-writing-patterns): exhaustive AI vocabulary cross-reference, phrasing patterns, uniform sentence length, organizational tells
- [Anbeeld/WRITING.md](https://github.com/Anbeeld/WRITING.md) (MIT): specificity theater, catalog prose, regularity diagnostics, compound-modifier nuance, medium routing
- [Bugcrowd Design System — Tone & Language](https://bugcrowd.design/docs/guidelines/content-guidelines/language/): plain English substitutions, link text semantics, punctuation tell detection
- Self: scare quotes, random bolding, ambiguous bold bullets, em-dash as false authority, voice and authenticity framing

---

## License

MIT
