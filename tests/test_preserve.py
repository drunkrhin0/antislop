#!/usr/bin/env python3
"""Public CLI tests for rewrite preservation."""

import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..")
PRESERVE = os.path.join(ROOT, "preserve.py")

ORIGINAL = """---
title: Q3 migration
owner: platform
---

# Migration Update

Our robust platform cut deploy time from 40 minutes to 4 minutes.

By Sarah Chen. The runbook says "Rollback stays enabled."

Read https://example.com/report?page=2&utm_source=chatgpt.com.

> Keep the old rollback path.

Use `/srv/app/config.yaml`.

```bash
deploy --timeout 40
```

| Metric | Before | After |
|---|---:|---:|
| Deploy time | 40 | 4 |
"""

VALID_REWRITE = """---
title: Q3 migration
owner: platform
---

# Migration Update

The platform cut deploy time from 40 minutes to 4 minutes.

By Sarah Chen. The runbook says "Rollback stays enabled."

Read https://example.com/report?page=2.

> Keep the old rollback path.

Use `/srv/app/config.yaml`.

```bash
deploy --timeout 40
```

| Metric | Before | After |
|---|---:|---:|
| Deploy time | 40 | 4 |
"""


def run_preserve(original, rewrite):
    with tempfile.TemporaryDirectory() as tmp:
        original_path = os.path.join(tmp, "original.md")
        rewrite_path = os.path.join(tmp, "rewrite.md")
        with open(original_path, "w", encoding="utf-8") as f:
            f.write(original)
        with open(rewrite_path, "w", encoding="utf-8") as f:
            f.write(rewrite)
        result = subprocess.run(
            [sys.executable, PRESERVE, original_path, rewrite_path],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        return result.returncode, json.loads(result.stdout)


class TestPreservationCLI(unittest.TestCase):
    def test_valid_rewrite_preserves_literals_and_removes_tracking(self):
        rc, result = run_preserve(ORIGINAL, VALID_REWRITE)

        self.assertEqual(rc, 0)
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["status"], "literal_preservation_passed")
        self.assertTrue(result["semantic_review_required"])

    def test_changed_quote_and_code_are_rejected(self):
        broken = VALID_REWRITE.replace(
            "> Keep the old rollback path.",
            "> Remove the old rollback path.",
        ).replace("deploy --timeout 40", "deploy --timeout 20")

        rc, result = run_preserve(ORIGINAL, broken)

        self.assertEqual(rc, 1)
        self.assertFalse(result["valid"])
        self.assertEqual(
            {error["code"] for error in result["errors"]},
            {"blockquote-modified", "code-block-modified"},
        )

    def test_numbers_quotations_and_attribution_are_preserved(self):
        broken = VALID_REWRITE.replace(
            "40 minutes to 4 minutes",
            "30 minutes to 3 minutes",
        ).replace(
            '"Rollback stays enabled."',
            '"Rollback is disabled."',
        ).replace("By Sarah Chen.", "By Alex Jones.")

        rc, result = run_preserve(ORIGINAL, broken)

        self.assertEqual(rc, 1)
        self.assertEqual(
            {error["code"] for error in result["errors"]},
            {
                "numeric-literal-modified",
                "quotation-modified",
                "attribution-modified",
            },
        )

    def test_invented_source_url_is_rejected(self):
        rewrite = VALID_REWRITE + "\nSee https://example.com/new-source for details.\n"

        rc, result = run_preserve(ORIGINAL, rewrite)

        self.assertEqual(rc, 1)
        self.assertIn(
            "url-modified",
            {item["code"] for item in result["errors"]},
        )

    def test_ftp_and_www_urls_are_preserved(self):
        original = "Download ftp://example.com/file and visit www.example.com."
        rewrite = "Download ftp://mirror.example.com/file and visit www.other.com."
        rc, result = run_preserve(original, rewrite)
        self.assertEqual(rc, 1)
        self.assertIn(
            "url-modified", {item["code"] for item in result["errors"]}
        )

    def test_heading_and_filesystem_path_changes_are_rejected(self):
        rewrite = VALID_REWRITE.replace("# Migration Update\n\n", "").replace(
            "/srv/app/config.yaml",
            "/srv/app/other.yaml",
        )

        rc, result = run_preserve(ORIGINAL, rewrite)

        self.assertEqual(rc, 1)
        self.assertTrue(
            {"heading-modified", "path-modified"}.issubset(
                {item["code"] for item in result["errors"]}
            )
        )

    def test_relative_and_home_path_changes_are_rejected(self):
        original = "Read docs/file and ~/work/config.yaml."
        rewrite = "Read docs/other and ~/work/other.yaml."

        rc, result = run_preserve(original, rewrite)

        self.assertEqual(rc, 1)
        self.assertIn(
            "path-modified", {item["code"] for item in result["errors"]}
        )


if __name__ == "__main__":
    unittest.main()
