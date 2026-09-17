# Antislop 3.0.0

Antislop 3.0.0 turns the project into a two-skill plugin and makes the same package usable across the supported agent platforms. This release covers the work merged since 2.0.3.

## Two first-class skills

- `antislop` handles writing, editing, and audit requests.
- `generate-slop` is a separate, explicit-only skill for synthetic demonstrations and evaluation fixtures. It is not loaded for ordinary writing work.
- Claude, Codex, Kiro, Gemini-compatible agents, opencode, and manual installations expose the same two-skill boundary.

## Packaging and platform support

- The portable plugin contains native Claude and Codex manifests, both skills, and the complete Antislop reference tree.
- Kiro discovers both skills while retaining the existing Power for ambient writing and on-demand audits.
- Release validation checks the exact skill roster, plugin manifests, references, and Kiro discovery paths.
- The standalone skill remains available for clients that accept a normal `SKILL.md` archive.

## Release and E2E reliability

- Release CI works on managed Python runners while keeping PyYAML pinned.
- Claude Code E2E imports are deterministic on clean checkouts.
- The E2E driver supports macOS systems without GNU `timeout`.
- Live probes can reuse an explicitly supplied authenticated Claude profile without reading or printing credentials.
- Probes launched from an existing Claude session clear the inherited nested-session marker only inside the child process.

## Downloads

| Asset | Use |
|---|---|
| `antislop-3.0.0.zip` | Standalone Antislop skill |
| `antislop-plugin-3.0.0.zip` | ChatGPT/Codex plugin package with both skills |
| `antislop-kiro-3.0.0.zip` | Kiro Power |
