# Kiro Power steering files are generated, not hand-synced

`GEMINI.md` and `.opencode/agents/antislop.md` are hand-maintained derivatives of the antislop rule registry, and each hand-synced surface multiplies the cost of every rule addition.

The Kiro Power's five `steering/*.md` files map cleanly onto files that already exist: the four reference files under `skills/antislop/references/` and the audit `SKILL.md` body. `generate.py` renders them directly, and `generate.py --check` verifies them byte for byte, so a rule addition in `rules.json` propagates to Kiro with no manual step.

`POWER.md` itself stays hand-written. Its always-on core is a curation decision about what belongs in every Kiro session, not a rendering of `rules.json`.
