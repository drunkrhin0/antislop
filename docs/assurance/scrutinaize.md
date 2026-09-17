# ScrutinAIze assurance receipt

Date: 2026-08-31

This receipt records a static scan of the clean implementation commit before
the receipt itself was added.

| Field | Value |
|---|---|
| Antislop commit | `bb10878c1432d729ec68886187e1d29beb2771a8` |
| ScrutinAIze commit | `c59ba1cff2b36b25d06b4e39bae6e6f501c8312e` |
| Target digest | `d27b99c76d1930cd7ef4f51d9ed0cb45b9cd0b64599612fac1f520e3735fc988` |
| Known-result score | 100 |
| Evidence coverage | 75% |
| Verdicts | 3 pass, 0 fail, 1 unknown, 10 not applicable |

The scan command was:

```sh
node /home/agent/workspaces/ScrutinAIze/packages/cli/dist/index.js scan \
  /tmp/antislop-avoid-ai-writing --format json --fail-on never
```

`MCP-004` is unknown because live MCP host behavior needs a runtime trace.
ScrutinAIze did not convert that missing evidence into a pass. The diagnostics
also recorded skipped symlinks, binary Python cache files, and unsupported
Python source parsing. No known control failed.
