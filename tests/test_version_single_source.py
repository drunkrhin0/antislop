#!/usr/bin/env python3
"""Tests for issue 70: the --expect-version declarations derive from rules.json.

validate.py's --expect-version-from flag reads the expected version out of
rules.json, the canonical source. Both lint-skills.yml workflows pass
--expect-version-from rules.json and the production assertion in
test_validate.py derives its expected version from rules.json, so a version
bump edits the shipped artifacts only. These tests prove the flag, that a
bare --skills-dir run stays version-free, and that a workflow pin disagreeing
with the canonical version fails the guard.
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATOR = os.path.join(ROOT, "validate.py")

sys.path.insert(0, ROOT)
import validate  # noqa: E402 -- import after sys.path setup, for direct unit tests

SKILL_TEMPLATE = """---
name: antislop
description: A minimal skill used by version single-sourcing tests.
metadata:
  version: "%s"
---

# Antislop

**Version:** %s

## When NOT to use
Skip this for code and configuration files.

## Audit mode
Output a Formulaic Writing Risk Score. This score cannot prove AI authorship.

## When to Use
Use this for prose that humans will read.

## Edit operations
- draft: create prose only from supplied facts.
- revise: make the least invasive change.
- audit: report findings without changing the artifact.
- transform: reshape while preserving the source inventory.
"""

POWER_TEMPLATE = """# Antislop Power

**Version:** %s
"""

WORKFLOW_TEMPLATE = """name: Lint Skills
on:
  push:
    branches: [main]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Validate repository invariants
        run: python3 validate.py --skills-dir skills --expect-version %s
"""


def run_validator(*args):
    """Run validate.py and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, VALIDATOR] + list(args),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return result.returncode, result.stdout, result.stderr


def make_repo(rules_version=None, skill_version=None, power_version=None, workflows=None):
    """Build a temp repo root with a valid minimal skill plus optional
    rules.json, POWER.md, and lint workflow files.

    Returns the skills/ dir path, since that is what --skills-dir takes and
    repo_root_for() derives the root from its parent. The temp copy is
    removed when the test process exits.
    """
    tmp = tempfile.mkdtemp(prefix="antislop-single-source-")
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)
    skills_dir = os.path.join(tmp, "skills")
    skill_dir = os.path.join(skills_dir, "antislop")
    os.makedirs(skill_dir)
    if skill_version is not None:
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(SKILL_TEMPLATE % (skill_version, skill_version))
    rules_path = None
    if rules_version is not None:
        rules_path = os.path.join(tmp, "rules.json")
        with open(os.path.join(ROOT, "rules.json"), encoding="utf-8") as f:
            registry = json.load(f)
        registry["version"] = rules_version
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(registry, f)
    if power_version is not None:
        power_dir = os.path.join(tmp, "powers", "antislop")
        os.makedirs(power_dir)
        with open(os.path.join(power_dir, "POWER.md"), "w", encoding="utf-8") as f:
            f.write(POWER_TEMPLATE % power_version)
    for rel, content in (workflows or {}).items():
        path = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    return skills_dir, rules_path


class TestCanonicalVersion(unittest.TestCase):
    """canonical_version() reads the version out of rules.json."""

    def test_canonical_version_reads_rules_json(self):
        with open(os.path.join(ROOT, "rules.json"), encoding="utf-8") as f:
            shipped = json.load(f)["version"]
        self.assertEqual(validate.canonical_version(ROOT), shipped)

    def test_canonical_version_none_without_rules_json(self):
        skills, _ = make_repo(skill_version="2.0.3")
        self.assertIsNone(validate.canonical_version(os.path.dirname(skills)))


class TestExpectVersionFrom(unittest.TestCase):
    """--expect-version-from checks artifacts against a rules.json version."""

    def test_expect_version_from_reads_rules_json(self):
        skills, rules = make_repo(
            rules_version="2.0.3", skill_version="2.0.3", power_version="2.0.3",
        )
        rc, stdout, stderr = run_validator("--skills-dir", skills, "--expect-version-from", rules)
        self.assertEqual(rc, 0, stdout + stderr)

    def test_expect_version_from_detects_drift(self):
        skills, rules = make_repo(
            rules_version="9.9.9", skill_version="2.0.3", power_version="2.0.3",
        )
        rc, stdout, stderr = run_validator("--skills-dir", skills, "--expect-version-from", rules)
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("expected 9.9.9", output)

    def test_bare_invocation_is_version_free(self):
        skills, _ = make_repo(skill_version="9.9.9", power_version="9.9.9")
        rc, stdout, stderr = run_validator("--skills-dir", skills)
        self.assertEqual(rc, 0, stdout + stderr)

    def test_explicit_expect_version_still_wins(self):
        skills, rules = make_repo(
            rules_version="9.9.9", skill_version="2.0.3", power_version="2.0.3",
        )
        self.assertIsNotNone(rules)
        rc, stdout, stderr = run_validator("--skills-dir", skills, "--expect-version", "2.0.3")
        self.assertEqual(rc, 0, stdout + stderr)

    def test_missing_expect_version_from_file_errors(self):
        rc, stdout, stderr = run_validator(
            "--skills-dir", "skills", "--expect-version-from", "/nonexistent/rules.json",
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("--expect-version-from", stdout + stderr)

    def test_expect_version_and_from_are_mutually_exclusive(self):
        rc, stdout, stderr = run_validator(
            "--skills-dir", "skills",
            "--expect-version", "2.0.3",
            "--expect-version-from", os.path.join(ROOT, "rules.json"),
        )
        self.assertNotEqual(rc, 0)


class TestWorkflowDeclarationGuard(unittest.TestCase):
    """check_expect_version_declarations() flags a stale workflow pin."""

    def test_stale_workflow_pin_flagged(self):
        skills, rules = make_repo(
            rules_version="2.0.3",
            skill_version="2.0.3",
            power_version="2.0.3",
            workflows={
                os.path.join(".forgejo", "workflows", "lint-skills.yml"): WORKFLOW_TEMPLATE % "2.0.0",
            },
        )
        errors = validate.check_expect_version_declarations(skills, "2.0.3")
        self.assertTrue(
            any("--expect-version 2.0.0" in e and "canonical version 2.0.3" in e for e in errors),
            errors,
        )

    def test_matching_workflow_pin_clean(self):
        skills, _ = make_repo(
            rules_version="2.0.3",
            skill_version="2.0.3",
            power_version="2.0.3",
            workflows={
                os.path.join(".github", "workflows", "lint-skills.yml"): WORKFLOW_TEMPLATE % "2.0.3",
            },
        )
        self.assertEqual(validate.check_expect_version_declarations(skills, "2.0.3"), [])

    def test_absent_workflows_clean(self):
        skills, _ = make_repo(rules_version="2.0.3", skill_version="2.0.3", power_version="2.0.3")
        self.assertEqual(validate.check_expect_version_declarations(skills, "2.0.3"), [])

    def test_stale_pin_fails_full_validation(self):
        skills, rules = make_repo(
            rules_version="2.0.3",
            skill_version="2.0.3",
            power_version="2.0.3",
            workflows={
                os.path.join(".forgejo", "workflows", "lint-skills.yml"): WORKFLOW_TEMPLATE % "2.0.0",
            },
        )
        rc, stdout, stderr = run_validator("--skills-dir", skills, "--expect-version-from", rules)
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("disagrees with canonical version 2.0.3", output)


class TestProductionDeclarations(unittest.TestCase):
    """The shipped workflows single-source the version from rules.json."""

    def test_production_workflows_single_source_from_rules_json(self):
        for rel in (".forgejo/workflows/lint-skills.yml", ".github/workflows/lint-skills.yml"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("--expect-version-from rules.json", text, rel)
            self.assertNotIn("--expect-version ", text, rel)

    def test_production_guard_is_clean(self):
        skills = os.path.join(ROOT, "skills")
        canonical = validate.canonical_version(ROOT)
        self.assertIsNotNone(canonical)
        self.assertEqual(validate.check_expect_version_declarations(skills, canonical), [])

    def test_production_passes_with_expect_version_from(self):
        rules = os.path.join(ROOT, "rules.json")
        rc, stdout, stderr = run_validator("--skills-dir", "skills", "--expect-version-from", rules)
        self.assertEqual(rc, 0, stdout + stderr)


if __name__ == "__main__":
    unittest.main()