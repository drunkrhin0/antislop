# Kiro Power steering files are generated, not hand-synced

`.opencode/agents/antislop.md` is a hand-maintained derivative of the antislop
rule registry, so each rule addition must also be checked against that agent.
The former Gemini extension derivative was removed when Gemini CLI and
Antigravity gained support for standard `SKILL.md` packages.

The Kiro Power's five `steering/*.md` files map cleanly onto files that already exist: the four reference files under `skills/antislop/references/` and the audit `SKILL.md` body. `tools/generate.py` renders them directly, and `generate.py --check` verifies them byte for byte, so a rule addition in `rules.json` propagates to Kiro with no manual step.

`POWER.md` itself stays hand-written. Its always-on core is a curation decision about what belongs in every Kiro session, not a rendering of `rules.json`.
