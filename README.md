# Antislop

*By slop for slop, to remove slop in an AI slop world.*

Written as a late shower thought from my ranting [LinkedIn post](https://www.linkedin.com/posts/tawilr_you-didnt-verify-this-and-i-can-tell-share-7460237564889944064-lXxs/)

Two skills for writing like a human. Works with Claude Code, opencode, and any agent that supports SKILL.md or AGENTS.md.

- **antislop** — a writing style skill. Ambient, always-on. Suppresses AI writing patterns across everything you write.
- **antislop-audit** — a detection skill. Scores text 0-100 and returns a violations list. Zero exceptions for intent.

---

## What it catches

- Banned vocabulary (delve, leverage, tapestry, pivotal, robust, seamless...)
- Banned phrases ("it's worth noting", "in today's landscape", "at its core"...)
- Em-dashes used as authority props instead of arguments
- Scare quotes used to hedge instead of commit
- Random bolding: decoration, not emphasis
- Ambiguous bolded bullets where the body doesn't support the claim
- Rule of three, synonym cycling, significance inflation, vague attributions
- Chatbot artifacts ("I hope this helps!", "Great question!")
- Writing with no opinion, no experience, no position. Just vibes.

---

## Installation

### Install with openskills

```bash
npx openskills install drunkrhin0/antislop
```

The repo includes an `AGENTS.md` file for automatic skill discovery in supported agents.

### Ask your agent

Just tell your agent to install `drunkrhin0/antislop` from GitHub. Most will figure it out.

### Manual

Copy `antislop/` and `antislop-audit/` into your skills directory:
- Claude Code: `~/.claude/skills/`
- opencode: `~/.config/opencode/skills/`

For AI chats (Claude.ai, ChatGPT, etc.), paste the contents of `antislop/SKILL.md` at the start of a conversation for writing, or `antislop-audit/SKILL.md` to audit text.

---

## Usage

### Writing style (antislop)

Triggers automatically when you ask your agent to write or edit anything. Or invoke `/antislop` directly.

### Audit (antislop-audit)

Paste text and ask your agent to audit it with `/antislop-audit`

Returns a score out of 100, a violations table with severity and excerpt, and a plain-English summary of what to fix first.

**Score bands:**
- 85-100 — Clean. Reads like a person.
- 65-84 — Some slop. Fixable with targeted edits.
- 40-64 — Heavy slop. Significant rewrite needed.
- 0-39 — Severe. This reads like unreviewed AI output.

---

## Credits and inspiration

- [blader/humanizer](https://github.com/blader/humanizer) (MIT) — the primary source. 29-pattern taxonomy grounded in Wikipedia's Signs of AI Writing. The backbone of both skills.
- [jalaalrd/anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing) (MIT) — banned word and phrase lists, structural pattern rules.
- Scoring model concept (0-100, severity tiers, detect/clean split) — inspired by existing audit/linting tools.
- [r/copywriting](https://www.reddit.com/r/copywriting/comments/1n3u03i/writing_instruction_to_prevent_ai_slop/) — hard-banned phrases, emergency replacements, quality checks.
- Self — scare quotes, random bolding, ambiguous bold bullets, em-dash as false authority, voice and authenticity framing.

---

## License

MIT
