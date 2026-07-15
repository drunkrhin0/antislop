# Issue tracker: local Markdown

Specs and tickets for this repository live as Markdown files under `.scratch/`.

## Conventions

- Store each effort under `.scratch/<feature-slug>/`.
- Store its spec at `.scratch/<feature-slug>/spec.md`.
- Store one ticket per file under `.scratch/<feature-slug>/issues/NN-<slug>.md`.
- Number tickets in dependency order.
- Record triage state with a `Status:` line near the top of each ticket.
- Append discussion under a `## Comments` heading.

## Publishing

When a skill says to publish a spec or issue, write the corresponding local file. Do not create a Forgejo or GitHub issue unless the user explicitly changes this configuration.

## Wayfinding

- The map is `.scratch/<effort>/map.md`.
- Child tickets are stored in `.scratch/<effort>/issues/`.
- `Blocked by:` lists ticket numbers that must be resolved first.
- The frontier contains tickets that are open, unblocked, and unclaimed.
- Claim work by changing `Status:` to `claimed` before editing source files.
- Resolve work by adding an `## Answer`, changing `Status:` to `resolved`, and updating the map.
