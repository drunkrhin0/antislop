# RC 3.0.0 examples

Runnable example files that exercise the new additions merged into
`integration/2.1.0-rc1`. Each section shows the command and what to
look for.

## General scoring surface

- `slop-sample.md` — dense AI slop with publishing artifacts. Expect a
  very low score and findings including `vocab-leverage`,
  `phrase-today-world`, `struct-unfilled-placeholders`,
  `struct-chat-citation-leaks`, and `struct-ai-url-parameters`.

    cat examples/slop-sample.md | python3 tools/score.py --stdin

- `clean-sample.md` — specific, factual prose. Expect a clean score
  (85+) and no findings.

    cat examples/clean-sample.md | python3 tools/score.py --stdin

## PR #77: vocabulary additions

- `vocabulary-sample.md` — exercises `vocab-agile`,
  `phrase-constantly-evolving`, and the expanded `phrase-today-world`.

    cat examples/vocabulary-sample.md | python3 tools/score.py --stdin

## PR #82: Cursor structural rules

- `cursor-sample.md` — `struct-numbered-list-inflation` fires as an
  automated finding; `struct-colon-overuse` is a manual-review rule
  and appears in the metadata's `manual_review_rule_ids`.

    cat examples/cursor-sample.md | python3 tools/score.py --stdin

## PR #83: marketing profile

- `marketing-sample.md` — the marketing rules fire only under
  `--profile marketing` and never under general.

    cat examples/marketing-sample.md | python3 tools/score.py --stdin --profile marketing
    cat examples/marketing-sample.md | python3 tools/score.py --stdin --profile general

## PR #85: preservation gate

- `preserve/source.md` + `preserve/faithful-rewrite.md` — the faithful
  rewrite passes (`valid: true`).
- `preserve/source.md` + `preserve/broken-rewrite.md` — the broken
  rewrite (number 40 changed to 50) fails (`valid: false`).

    python3 tools/preserve.py examples/preserve/source.md examples/preserve/faithful-rewrite.md
    python3 tools/preserve.py examples/preserve/source.md examples/preserve/broken-rewrite.md

## PR #85: MCP server

- `mcp/requests.jsonl` — JSON-RPC requests for the MCP server
  (tools/list, score_text, prepare_rewrite, validate_rewrite).

    cat examples/mcp/requests.jsonl | python3 tools/mcp_server.py

## PR #84: rule-content check

Run against the production skills; it verifies every registry rule has
a detectable trace in the style skill:

    python3 tools/validate.py --skills-dir skills --check-rule-content
