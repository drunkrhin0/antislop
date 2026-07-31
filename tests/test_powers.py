#!/usr/bin/env python3
"""Tests for validate.py's Kiro Power checks — validate_power_file().

Run: python3 -m unittest tests.test_powers
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

VALIDATOR = os.path.join(os.path.dirname(__file__), "..", "validate.py")
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

sys.path.insert(0, os.path.abspath(REPO_ROOT))
import validate  # noqa: E402 -- import after sys.path setup, reused for direct unit tests


def run_validator(*args):
    """Run validate.py and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, VALIDATOR] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.abspath(REPO_ROOT))
    return result.returncode, result.stdout, result.stderr


def materialize_power_fixture(name):
    """Copy a tests/fixtures/power-<case> dir to a temp location with
    POWER.md.fixture renamed to POWER.md.

    Mirrors test_validate.py's materialize_fixture(): fixture files are
    stored on disk as POWER.md.fixture, not POWER.md, so a repo-wide scanner
    (e.g. openskills, or anything else that walks the filesystem for known
    filenames) doesn't treat these deliberately-broken files as an
    installable Power. validate.py's discovery still needs the real
    filename, so materialize a real copy at test time instead.

    Returns the path to the materialized fixture directory. That directory
    doubles as both the containing directory validate_power_file() checks
    'name' against, and the --powers-dir argument passed to the CLI.
    """
    src = os.path.join(FIXTURES, name)
    tmp = tempfile.mkdtemp(prefix="antislop-power-fixture-")
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)
    dst = os.path.join(tmp, os.path.basename(name))
    shutil.copytree(src, dst)
    for root, _dirs, files in os.walk(dst):
        for f in files:
            if f == "POWER.md.fixture":
                os.rename(os.path.join(root, f), os.path.join(root, "POWER.md"))
    return dst


class TestPowerFrontmatterChecks(unittest.TestCase):
    """Frontmatter schema: five allowed keys, name conventions, displayName,
    description, and keywords."""

    def test_catches_forbidden_frontmatter_key(self):
        """A 'version:' key in frontmatter -- Kiro Powers do not have one."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", "skills",
            "--powers-dir", materialize_power_fixture("power-forbidden-version"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0, "Validator should fail on forbidden frontmatter key")
        self.assertIn(
            "frontmatter key 'version' is not allowed in a Power "
            "(only name, displayName, description, keywords, author)",
            output,
        )

    def test_catches_name_mismatch(self):
        """frontmatter name does not match the containing directory."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", "skills",
            "--powers-dir", materialize_power_fixture("power-name-mismatch"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0, "Validator should fail on name/directory mismatch")
        self.assertIn(
            "frontmatter name 'totally-different-name' does not match "
            "containing directory 'power-name-mismatch'",
            output,
        )

    def test_catches_long_displayname(self):
        """displayName over 5 words."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", "skills",
            "--powers-dir", materialize_power_fixture("power-long-displayname"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0, "Validator should fail on an over-length displayName")
        self.assertIn(
            "displayName 'This Display Name Has Six Words' must be 2 to 5 words",
            output,
        )

    def test_catches_broad_keyword(self):
        """keywords containing a broad, deny-listed term ('help')."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", "skills",
            "--powers-dir", materialize_power_fixture("power-broad-keyword"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0, "Validator should fail on a broad keyword")
        self.assertIn(
            "keyword 'help' is too broad (avoid test, api, data, help, debug)",
            output,
        )


class TestPowerSteeringMapChecks(unittest.TestCase):
    """'When to Load Steering Files' <-> steering/ bidirectional map."""

    def test_catches_missing_steering_file(self):
        """The steering map names a file that does not exist under steering/."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", "skills",
            "--powers-dir", materialize_power_fixture("power-missing-steering"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0, "Validator should fail when the steering map names a ghost file")
        self.assertIn(
            "steering file 'missing.md' is listed in "
            "'## When to Load Steering Files' but does not exist under steering/",
            output,
        )


class TestPowerReviewFixes(unittest.TestCase):
    """Regression tests for the validator edge cases found in review."""

    def test_missing_privacy_is_the_only_fixture_error(self):
        power_dir = materialize_power_fixture("power-missing-privacy")
        errors = validate.validate_power_file(os.path.join(power_dir, "POWER.md"))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("missing privacy statement", errors[0])

    def test_missing_license_support_section_is_the_only_fixture_error(self):
        power_dir = materialize_power_fixture("power-missing-privacy")
        power_path = os.path.join(power_dir, "POWER.md")
        with open(power_path) as f:
            text = f.read()
        text = text[: text.index("## License and support")].rstrip() + "\n"
        with open(power_path, "w") as f:
            f.write(text)
        errors = validate.validate_power_file(power_path)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("missing '## License and support' section", errors[0])

    def test_keyword_parser_preserves_internal_comma(self):
        self.assertEqual(validate.parse_keyword_list('["a, b", "c"]'), ["a, b", "c"])

    def test_keyword_parser_keeps_supported_shapes(self):
        self.assertEqual(validate.parse_keyword_list('["a", "b",]'), ["a", "b"])
        self.assertEqual(validate.parse_keyword_list("[]"), [])
        self.assertEqual(validate.parse_keyword_list("single"), ["single"])
        self.assertEqual(validate.parse_keyword_list(["a", "b"]), ["a", "b"])
        self.assertEqual(validate.parse_keyword_list("a, b"), ["a", "b"])

    def test_title_case_handles_acronyms_minor_words_and_hyphens(self):
        cases = {
            "WRITE WITHOUT AI SLOP": False,
            "Anti-slop Rewriter": False,
            "Write Without a Point": True,
            "Write Without AI Slop": True,
        }
        for display_name, expected_valid in cases.items():
            with self.subTest(display_name=display_name):
                fixture = "---\n" \
                    "name: \"power-missing-privacy\"\n" \
                    f"displayName: \"{display_name}\"\n" \
                    "description: \"One. Two. Three.\"\n" \
                    "keywords: [\"a\", \"b\", \"c\", \"d\", \"e\"]\n" \
                    "---\n**Version:** 1.0.0\n"
                with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                    f.write(fixture)
                    path = f.name
                try:
                    errors = validate.validate_power_file(path)
                    title_errors = [error for error in errors if "not Title Case" in error]
                    self.assertEqual(not title_errors, expected_valid, errors)
                finally:
                    os.unlink(path)

    def test_sentence_count_ignores_lowercase_abbreviation_boundary(self):
        fixture = "---\nname: x\ndisplayName: Test Power\ndescription: \"First e.g. example. Second. Third.\"\nkeywords: [a, b, c, d, e]\n---\n**Version:** 1.0.0\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(fixture)
            path = f.name
        try:
            errors = validate.validate_power_file(path)
            self.assertFalse(any("description has" in error for error in errors), errors)
        finally:
            os.unlink(path)

    def test_sentence_count_rejects_four_sentences(self):
        fixture = "---\nname: x\ndisplayName: Test Power\ndescription: \"One. Two. Three. Four.\"\nkeywords: [a, b, c, d, e]\n---\n**Version:** 1.0.0\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(fixture)
            path = f.name
        try:
            errors = validate.validate_power_file(path)
            self.assertTrue(any("description has 4 sentences" in error for error in errors), errors)
        finally:
            os.unlink(path)

    def test_version_extraction_ignores_internal_dividers(self):
        after = "---\nname: x\n---\n**Version:** 1.0.0\n---\nBody\n"
        before = "---\nname: x\n---\n---\n**Version:** 1.0.0\nBody\n"
        self.assertEqual(validate.extract_version_from_body(after), "1.0.0")
        self.assertEqual(validate.extract_version_from_body(before), "1.0.0")


class TestPowerProductionFile(unittest.TestCase):
    """The real powers/antislop/POWER.md should validate clean."""

    def test_real_power_file_validates_clean(self):
        power_path = os.path.join(os.path.abspath(REPO_ROOT), "powers", "antislop", "POWER.md")
        errors = validate.validate_power_file(power_path)
        self.assertEqual(errors, [], errors)

    def test_cli_passes_on_real_tree(self):
        """Same check through the CLI, exercising --powers-dir's default."""
        rc, stdout, stderr = run_validator("--skills-dir", "skills")
        output = stdout + stderr
        self.assertEqual(rc, 0, f"Validator failed on production skills/powers:\n{output}")


if __name__ == "__main__":
    unittest.main()
