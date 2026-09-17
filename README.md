# Antislop

Antislop helps AI agents write less formulaic prose without losing the author's facts, citations, terminology, or voice.

It provides two skills:

- **`antislop`** writes, edits, reviews, and audits prose. It activates when you ask an agent to work on a prose artifact.
- **`generate-slop`** creates deliberately formulaic samples for demos and tests. It must be invoked by name.

## Install

Ask your agent:

```text
Install the antislop and generate-slop skills from https://github.com/drunkrhin0/antislop. Do not install the retired standalone antislop-audit skill.
```

Or use the Skills CLI:

```bash
npx skills@latest add drunkrhin0/antislop
```

You can also download a package from the [latest GitHub release](https://github.com/drunkrhin0/antislop/releases/latest):

- `antislop-<version>.zip` for the standalone skill
- `antislop-plugin-<version>.zip` for ChatGPT and Codex
- `antislop-kiro-<version>.zip` for Kiro

The plugin package also contains a Claude Code manifest, but Claude Code installation has not been verified.

For ChatGPT for Work, import `https://github.com/drunkrhin0/antislop` from **Workspace settings > Plugins > Add > Import marketplace** and leave **Path** empty. Codex reads the package's Codex manifest. For Kiro, import `powers/antislop` as a custom Power.

## Use

| Goal | Ask your agent |
| --- | --- |
| Write or edit | `Rewrite this release note. Keep every version number and compatibility warning unchanged.` |
| Audit without rewriting | `Audit this text for formulaic writing patterns. Do not rewrite it.` |
| Slop generation | `Use generate-slop to create a formulaic marketing sample for an audit test.` |

Audits return exact excerpts, rule IDs, and a Formulaic Writing Risk Score:

- `85-100`: low risk
- `65-84`: moderate risk
- `40-64`: high risk
- `0-39`: very high risk

The score measures patterns in the text. It cannot prove or disprove AI authorship. Use `generate-slop` only for synthetic samples.

## Version 3

Version 3 combines writing and audit mode in `antislop`, expands the registry from 146 to 222 rules, adds five writing profiles, and incorporates 18 reviewed sources. Rewrites now protect facts, citations, links, code, required terms, and the author's voice.

Remove old standalone copies of `antislop-audit` before installing version 3. Leaving both installed can cause ambiguous routing.

See the [release history](https://github.com/drunkrhin0/antislop/releases) for detailed changes and [sources and credits](docs/sources/credits.md) for attribution.

## License

MIT
