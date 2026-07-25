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

    def test_production_skills_version(self):
        """The real skills/ directory should be at 2.0.0."""
        rc, stdout, stderr = run_validator("--skills-dir", "skills", "--expect-version", "2.0.0")
        output = stdout + stderr
        self.assertEqual(rc, 0, f"Version check failed on production skills:\n{output}")


class TestVersionChecks(unittest.TestCase):
    """--expect-version flag."""

    def test_catches_wrong_version(self):
        """Version mismatch fixture should fail --expect-version 1.8.0."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "version-mismatch"),
            "--expect-version", "1.8.0",
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("expected 1.8.0", output)


class TestAuditContentChecks(unittest.TestCase):
    """Audit output format and authorship disclaimer."""

    def test_catches_wrong_score_name(self):
        """Audit using 'Slop Score' instead of 'Formulaic Writing Risk Score'."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "bad-score-name"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("Formulaic Writing Risk Score", output)

    def test_catches_missing_disclaimer(self):
        """Audit missing authorship disclaimer."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "no-disclaimer"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("authorship disclaimer", output)

    def test_catches_bad_antithesis_rule(self):
        """Antithesis rule without load-bearing distinction."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "bad-antithesis"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("antithesis", output.lower())
        self.assertIn("load-bearing", output.lower())


class TestDashChecks(unittest.TestCase):
    """ASCII dash substitutes and cross-artifact mark parity."""

    def test_catches_dash_substitute(self):
        """A double hyphen standing in for an em dash outside a code span."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "dash-substitute"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("dash substitute", output)

    def test_allows_marks_inside_code_spans(self):
        """Literal mark references in backticks are meta-context, not usage."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "dash-substitute"),
        )
        output = stdout + stderr
        # Line 17 carries the violation; line 19 backticks the same marks.
        self.assertIn(":17:", output)
        self.assertNotIn(":19:", output)

    def test_catches_dash_drift_between_artifacts(self):
        """The same line carrying different marks in two shipped artifacts."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", os.path.join(FIXTURES, "dash-drift"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("dash drift", output)

    def test_production_artifacts_have_no_substitutes(self):
        """The real artifacts, including the agent file and README."""
        rc, stdout, stderr = run_validator("--skills-dir", "skills")
        output = stdout + stderr
        self.assertEqual(rc, 0, f"Dash checks failed on production:\n{output}")


if __name__ == "__main__":
    unittest.main()
