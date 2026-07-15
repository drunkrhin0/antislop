#!/usr/bin/env python3
"""Tests for validate.py — the repository invariant checker.

Run: python3 tests/test_validate.py
"""

import os
import subprocess
import sys
import unittest

VALIDATOR = os.path.join(os.path.dirname(__file__), "..", "validate.py")
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def run_validator(*args):
    """Run validate.py and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, VALIDATOR] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(__file__) + "/..")
    return result.returncode, result.stdout, result.stderr


class TestValidatorCLI(unittest.TestCase):
    """Validate that validate.py runs as a CLI tool."""

    def test_runs_without_error_on_clean_args(self):
        rc, stdout, stderr = run_validator("--help")
        self.assertEqual(rc, 0)

    def test_exits_nonzero_on_bad_path(self):
        rc, stdout, stderr = run_validator("--skills-dir", "/nonexistent")
        self.assertNotEqual(rc, 0)


class TestMetadataChecks(unittest.TestCase):
    """Frontmatter and metadata validation."""

    def test_catches_version_mismatch(self):
        """Pre-1.8 contradiction fixture: metadata says 1.6.0, body says 1.7.0."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "version-mismatch"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0, "Validator should fail on version mismatch fixture")
        self.assertIn("version mismatch", output.lower())

    def test_catches_missing_metadata_version(self):
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "missing-metadata"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("missing metadata.version", output)

    def test_catches_missing_required_section(self):
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "missing-section"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("When NOT to use", output)


class TestCrossFileChecks(unittest.TestCase):
    """Cross-artifact version consistency."""

    def test_detects_skill_vs_gemini_drift(self):
        """SKILL.md says 1.7.0 but gemini-extension.json says 1.6.0."""
        drift_fixture = os.path.join(FIXTURES, "cross-file-drift")
        rc, stdout, stderr = run_validator("--skills-dir", drift_fixture)
        output = stdout + stderr
        self.assertNotEqual(rc, 0, "Validator should fail on cross-file drift fixture")
        self.assertIn("cross-file", output.lower())


class TestProductionChecks(unittest.TestCase):
    """Run against the actual skills/ directory."""

    def test_production_skills_pass(self):
        """The real skills/ directory should pass all checks."""
        rc, stdout, stderr = run_validator("--skills-dir", "skills")
        output = stdout + stderr
        self.assertEqual(rc, 0, f"Validator failed on production skills:\n{output}")


if __name__ == "__main__":
    unittest.main()
