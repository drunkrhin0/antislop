# End-to-end test of the proposed adoption

Date: 2026-08-31

## Remediation retest

The deterministic path is now end-to-end ready for its declared scope. The
model-driven rewrite path is not yet fully verified.

The 3.0.0 implementation fixed ten of the eleven failed capabilities recorded
below. Publishing artifacts, real paragraph and list analyzers, protected
spans, word variants, input gates, source offsets, five voices, six contexts,
literal preservation, and read-only MCP tools now have public-seam tests. The
scorer no longer calls an incomplete check a full pass: it returns
`manual_review_required` and lists the active semantic rules that remain.

The final deterministic run contains 167 tests. MCP requests reject any text
field above 250,000 characters. Literal preservation blocks changes to heading
structure and filesystem paths as well as code, tables, quotes, links, numbers,
frontmatter, and attribution.

The registry also carries a typed editing contract and the audited 112-row and
69-category upstream counts. Those category decisions render to a checked
reference, and the canonical style skill renders to a Cursor rule.

The plugin package now uses `.codex-plugin/plugin.json`, points to the single
Antislop skill and `.mcp.json`, and passes the local plugin schema validator. The MCP server
was called through JSON-RPC for tool discovery, scoring, rewrite preparation,
preservation, candidate blocking, and bounded input errors. A ScrutinAIze scan
reports no known static MCP failures,
with 75 percent evidence coverage. Its live-host control remains unknown
because no runtime trace was supplied.

The declared trigger corpus now has an executable runner. All 20 cases pass the
deterministic router, and the runner explicitly reports `model_status` as
`not_run`. No pinned model has produced rewrites in an isolated session, so the
original model-evaluation failure and rewrite-quality uncertainty remain. A
router pass must not be presented as model evidence.

Current verification commands are listed in the pull request and README. The
sections below preserve the original failing run as baseline evidence.

## Baseline verdict at `bd3af7c`

> Historical result before the 3.0.0 remediation. Statements about the
> "current branch" in this baseline refer to that revision, not the final PR
> head.

The proposed Antislop adoption is not end-to-end ready.

The upstream deterministic pipeline works for its implemented subset: it can
analyze rendered Markdown, remove mechanical findings, preserve protected
content, reject a destructive rewrite, and expose two read-only MCP tools.
Antislop's current branch can score exact vocabulary and phrases, select its
two existing scorer profiles, validate manifests, and keep generated artifacts
in sync.

The combined system described by ADR 0004 does not exist yet. Antislop has no
voice axis, context axis, preservation validator, protected-span scanner,
stable finding offsets, tier or density policy, or read-only tool. Its scorer
skips 65 active registry rules. The declared model evaluation fixtures have no
runner or recorded results.

This is a failed readiness test, not a failed repository test. Unit and
generation checks can all pass while the user-facing path remains incomplete.

## Revisions and interfaces

| Component | Revision | Public interface exercised |
|---|---|---|
| Antislop PR branch | `bd3af7c402ca2ab456290ff8eec5e93813694325`, plus the OpenCode parity fix from this test | `tools/score.py`, registry profiles, generator, manifests, OpenCode agent discovery, style and audit skill contracts |
| `avoid-ai-writing` | `58a95fc9971d7af95f1f1324b8a6bc991eb8004d` | `AIDetector.analyzeText`, rendered-Markdown mode, `detector/validate.js`, package tests, sync gates |
| `avoid-ai-writing-mcp` | `125e0818b7e1b88d904c73c7729a5e5c1441f8a6` | MCP client/server tests for `score_text` and `audit_text` |

The rewrite fixture preserves frontmatter, a heading, a blockquote, inline
code, a fenced command, a table, a path, a functional URL parameter, and the
numbers 40 and 4. It removes generic language, a placeholder, a leaked chat
citation, and an AI referrer parameter. A deliberately broken rewrite changes
the blockquote and the fenced command.

## Antislop readiness matrix

| User-visible capability | Result | Evidence |
|---|---|---|
| Plugin manifests point to the single skill | Pass | JSON validation passed and the ChatGPT/Codex skill path exists. |
| OpenCode discovers the packaged agent | Pass | `opencode agent list` returned `antislop (subagent)`. |
| Generated artifact propagation | Pass | `python3 tools/generate.py --check` and `bash check.sh` passed. |
| Exact lexical scoring separates the dirty and cleaned fixtures | Pass, narrow | Original scored 0 with five findings; the supplied clean rewrite scored 100. This tests scoring, not rewrite generation. |
| Existing `general` and `technical` scorer profiles | Pass | Technical mode exempted `robust`; invalid profile input returned a bounded error. |
| Authorship claim boundary | Pass | Antislop output uses Formulaic Writing Risk Score and does not emit authorship classes or probabilities. |
| OpenCode vocabulary and audited structural additions | Pass after repair | The first run found five missing and two extra vocabulary rows plus ten missing structural rules. The agent and regression tests were updated during this test. |
| Publishing artifacts added by this PR | Fail | A 500-word input containing `[Your Name]`, `citeturn0search0`, and `utm_source=chatgpt.com` scored 100 with zero findings. |
| Numbered-list, paragraph-reshuffle, and treadmill findings | Fail | A padded structural fixture scored 100 with zero findings. |
| Protected Markdown spans | Fail | Terms present only in frontmatter, a blockquote, and a fenced block produced four findings and a score of 68. |
| Morphological variants | Fail | Base forms `leverage`, `showcase`, `unpack`, and `navigate` fired. `leverages`, `leveraged`, `leveraging`, `showcases`, `showcasing`, `unpacking`, and `navigating` did not. |
| Short-input gate | Fail | The one-word input `delve` scored 0 and was labelled severe instead of returning an unscored result. |
| Source-stable finding offsets | Fail | Internal positions are calculated, but the public JSON finding omits `position` and `match_length`. |
| Five voice profiles | Fail, not implemented | `casual` is rejected. Only `general` and `technical` exist, and those are scorer profiles rather than voices. |
| Six writing contexts | Fail, not implemented | No `linkedin`, `blog`, `technical-blog`, `investor-email`, `docs`, or `casual` context axis exists. |
| Rewrite preservation gate | Fail, not implemented | Antislop has no prose rewrite validator. `tools/fix.py` repairs generated repository artifacts, not prose. |
| Read-only scanner or MCP tools | Fail, not implemented | The plugin is skills-only. It exposes no score or audit tool. |
| Executed model evaluation suite | Fail | The two `evals.json` files contain prompts and assertions only. No runner, model pin, outputs, judge results, or pass record exists. |
| Model rewrite and trigger behavior | Unverified | The skills are prompt contracts. This run did not use an independent model session, so it cannot make a reproducible claim about activation or rewrite quality. |

Seven capabilities passed, eleven failed, and one remained unverified after
the OpenCode parity repair.

## Antislop scorer results

### Dirty to clean

The original fixture produced:

```json
{
  "score": 0,
  "finding_ids": [
    "vocab-cutting-edge",
    "vocab-robust",
    "vocab-seamless",
    "vocab-transformative",
    "filler-important-note"
  ],
  "skipped_rules": 65
}
```

The supplied rewrite produced:

```json
{
  "score": 100,
  "finding_ids": [],
  "skipped_rules": 65
}
```

The score improved, but this is not proof that the full text passed. The
scorer explicitly skipped 65 active rules and did not check preservation.

### New rules through the public scorer

The publishing-artifact and discourse fixtures both returned:

```json
{
  "score": 100,
  "finding_ids": [],
  "skipped_rules": 65
}
```

The PR registers the new findings and teaches them to model-facing skills, but
does not make them executable in `tools/score.py`.

### Declared audit fixtures

Selected audit fixtures were sent through the public scorer to check whether
the declared expectations match executable behavior:

| Fixture | Declared expectation | Scorer result |
|---|---|---|
| `audit-1` | Seven named findings and score below 40 | Score 0; three named findings found. |
| `audit-4` | Six named findings and score below 40 | Score 0; three named findings found. |
| `audit-5` | Six named findings and score below 40 | Score 0; two named findings found. |
| `audit-9` | Placeholder, citation token, and AI referrer findings | Score 100; no findings. |
| `audit-10` | List inflation, reshuffle, and treadmill findings | Score 100; no findings. |

These files are model evaluation specifications, not scorer tests. The result
still exposes a product split: the numeric CLI cannot produce the findings the
audit skill promises, while both surfaces use the same score name.

### False positives and short input

The protected-span fixture produced:

```json
{
  "score": 68,
  "finding_ids": [
    "vocab-delve",
    "vocab-leverage",
    "vocab-robust",
    "vocab-seamless"
  ],
  "skipped_rules": 65
}
```

All four terms appeared only in frontmatter, quoted material, or code. The
one-word input `delve` produced a normalized penalty of 4000 and a final score
of 0. These results confirm that protected-span masking and a short-input gate
must precede tool packaging.

## Upstream deterministic pipeline

The same original and supplied rewrite were sent through upstream's
rendered-Markdown analyzer.

| Step | Result | Evidence |
|---|---|---|
| Analyze original | Pass | Score 59; eight issues: four Tier 1 terms, filler, placeholder, citation token, and AI referrer. |
| Analyze supplied rewrite | Pass | Score 0; zero issues. Upstream's scale runs in the opposite direction to Antislop's score. |
| Validate supplied rewrite | Pass | No preservation errors; one expected heading-text warning. |
| Validate broken rewrite | Pass | Exit 1 with `code-block-modified` and `blockquote-modified`. |
| Detector and support tests | Pass | Upstream `npm test` passed. |
| Count and claim gates | Pass, limited | The 112-row and 69-category counts matched. These gates do not test semantics or detector parity. |
| Plugin copy sync | Pass | Root and plugin skill copies matched. |
| Cursor generation sync | Pass | The generated Cursor rule matched its source transformation. |
| MCP client/server path | Pass | Five MCP tests called both tools through a connected client/server pair. |

The upstream deterministic path is materially better, but it does not validate
the prompt-only rewrite, voice, context, or trigger behavior. The MCP also pins
detector 3.22.1 while the audited source is 3.28.0 and emits unsupported
authorship classifications and probability fields.

## What the end-to-end run changes

The adoption order in ADR 0004 is confirmed, with a harder release boundary:

1. Do not present PR #85 as an implemented new system. It is an audit, a small
   rule addition, and a design decision.
2. Do not expose Antislop's current scorer as an MCP or plugin tool. A 100 score
   can mean that 65 active rules were skipped.
3. Implement one registry-driven analysis path shared by the CLI, audit skill,
   and future tools before adding voice profiles.
4. Add rendered-Markdown masking, short and long input gates, inflections,
   stable offsets, overlap handling, and preservation validation.
5. Turn evaluation specifications into executed, model-pinned runs. Keep model
   behavior separate from deterministic analyzer tests.
6. Add voice, context, and mechanics as separate axes only after the shared
   analyzer and typed-rule schema exist.
7. Treat generated or parity-checked client artifacts as a release gate. The
   OpenCode drift found here would otherwise ship different rules by client.

## Commands executed

Antislop:

```text
python3 tools/score.py --profile general --file <original>
python3 tools/score.py --profile general --file <rewritten>
python3 tools/score.py --profile casual --stdin
python3 tools/generate.py --check
bash check.sh
opencode agent list
python3 -m unittest tests.test_generate.TestRegistryContent.test_opencode_vocabulary_matches_registry tests.test_generate.TestRegistryContent.test_opencode_has_recent_structural_rules -v
```

Additional scorer calls exercised publishing artifacts, structural prose,
protected Markdown, short input, inflected vocabulary, technical mode, and five
declared audit fixtures.

Upstream:

```text
node detector/validate.js <original> <rewritten>
node detector/validate.js <original> <broken-rewrite>
npm test
npm run self-scan:check
bash scripts/check-pattern-count.sh
bash scripts/sync-plugin-skill.sh
bash scripts/sync-cursor-rules.sh
```

Companion MCP:

```text
npm ci
npm test
npm pack --dry-run
```

Temporary fixtures were kept outside the repository and are not part of the
pull request.
