# Development tools

This directory contains Antislop's Python implementation and command-line tools.

Run a tool from the repository root so it can find `rules.json`, fixtures, skills, and other project files. For example:

```bash
python3 tools/score.py --file README.md
python3 tools/validate.py --skills-dir skills --expect-version-from rules.json
```

Use `bash check.sh` to run the standard generated-file and validation checks.
