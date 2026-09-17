# Human Review companion

Load this reference only when the user explicitly asks to use the Human Review browser workflow.

## Human Review companion workflow

Human Review is an optional, local companion workflow for reviewing a document in a real browser. It stays separate from the rule registry: Human Review is not a writing rule, and normal Antislop use and validation never require it. Antislop documents the workflow and the feedback contract; the Human Review tool itself runs locally and is never vendored, copied into the skills tree, or set up automatically. The upstream repository is https://github.com/petergyang/human-review (MIT).

The loop:

1. **Write or update** the Markdown, HTML, or localhost page.
2. **Open for review** — if Human Review is installed, open the target in the browser.
3. **Wait for the feedback batch** — then apply every page's edits and comments.
4. **Edit the source** — apply the edits to the source document, not to a rendered Markdown or localhost response.
5. **Audit** — run Antislop in audit mode against the revised human-readable prose.
6. **Repeat** the review and audit loop until the human accepts the result.

The feedback contract:

- Markdown is rendered for review, and the Markdown source remains the write target.
- `edits[].after` is user-authored text and must be carried across verbatim. Never revert it.
- `before_html` and `after_html` record formatting changes, not new words. Translate them into the source syntax of the document, such as `<strong>` becoming `**` in Markdown.
- Handle every page in the feedback batch, not just the first.
- `kind: "url"` identifies a localhost route, not a writable source file. Locate the matching source and update that instead.
- A timeout is not acceptance and must never be treated as approval.
- Run the final audit after the human edits are applied.

Human edits are authoritative. Preserve the user's exact wording, translate formatting changes into source syntax, and never let a rendered response overwrite the source. The workflow never becomes an automatic approval, publication, merge, or issue closure mechanism.
