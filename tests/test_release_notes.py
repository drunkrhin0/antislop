#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestReleaseNotes(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "rules.json"), encoding="utf-8") as handle:
            self.version = json.load(handle)["version"]
        self.notes_path = os.path.join(
            ROOT, "docs", "release-notes-%s.md" % self.version)

    def test_current_version_has_release_notes(self):
        self.assertTrue(os.path.isfile(self.notes_path))
        with open(self.notes_path, encoding="utf-8") as handle:
            notes = handle.read()
        self.assertIn("# Antislop %s" % self.version, notes)
        self.assertIn("## Downloads", notes)

    def test_release_json_uses_versioned_notes(self):
        tag = "antislop-v%s" % self.version
        output = subprocess.check_output(
            [
                sys.executable,
                os.path.join(ROOT, "scripts", "build-release-json.py"),
                tag,
                self.version,
                self.notes_path,
            ],
            cwd=ROOT,
            text=True,
        )
        payload = json.loads(output)
        with open(self.notes_path, encoding="utf-8") as handle:
            notes = handle.read()
        self.assertEqual(payload["tag_name"], tag)
        self.assertEqual(payload["name"], "antislop v%s" % self.version)
        self.assertEqual(payload["body"], notes)
        self.assertFalse(payload["draft"])
        self.assertFalse(payload["prerelease"])

    def test_readme_names_every_release_asset(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
            readme = handle.read()
        for name in (
                "antislop-<version>.zip",
                "antislop-plugin-<version>.zip",
                "antislop-kiro-<version>.zip"):
            self.assertIn(name, readme)


if __name__ == "__main__":
    unittest.main()
