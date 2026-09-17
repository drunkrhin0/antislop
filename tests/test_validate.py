#!/usr/bin/env python3
"""Tests for validate.py — the repository invariant checker.

Run: python3 tests/test_validate.py
"""

import atexit
import json
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
import validate  # noqa: E402 -- import after sys.path setup, for direct unit tests


def run_validator(*args):
    """Run validate.py and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, VALIDATOR] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(__file__) + "/..")
    return result.returncode, result.stdout, result.stderr


def materialize_fixture(name):
    """Copy a fixture dir to a temp location with SKILL.md.fixture renamed to SKILL.md.

    Fixture files are stored on disk as SKILL.md.fixture, not SKILL.md, so that
    tools which walk the repo looking for real skills (e.g. openskills) don't
    pick up these deliberately-broken files as installable skills. validate.py's
    discovery still needs the real filename to exercise the actual code path,
    so materialize a real copy at test time instead of keeping SKILL.md on disk
    permanently. The temp copy is removed when the test process exits.
    """
    src = os.path.join(FIXTURES, name)
    tmp = tempfile.mkdtemp(prefix="antislop-fixture-")
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)
    dst = os.path.join(tmp, os.path.basename(name))
    shutil.copytree(src, dst)
    for root, _dirs, files in os.walk(dst):
        for f in files:
            if f == "SKILL.md.fixture":
                os.rename(os.path.join(root, f), os.path.join(root, "SKILL.md"))
    return dst


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
            "--skills-dir", materialize_fixture("version-mismatch"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0, "Validator should fail on version mismatch fixture")
        self.assertIn("version mismatch", output.lower())

    def test_catches_missing_metadata_version(self):
        rc, stdout, stderr = run_validator(
            "--skills-dir", materialize_fixture("missing-metadata"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("missing metadata.version", output)

    def test_catches_missing_required_section(self):
        rc, stdout, stderr = run_validator(
            "--skills-dir", materialize_fixture("missing-section"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("When NOT to use", output)

    def test_catches_unquoted_colon_in_frontmatter_scalar(self):
        text = """---
name: broken
description: Writing intent: edit prose.
metadata:
  version: "3.0.0"
---
"""
        self.assertTrue(validate.validate_frontmatter_yaml_scalars(text))


class TestProductionChecks(unittest.TestCase):
    """Run against the actual skills/ directory."""

    def test_production_skills_pass(self):
        """The real skills/ directory should pass all checks."""
        rc, stdout, stderr = run_validator("--skills-dir", "skills")
        output = stdout + stderr
        self.assertEqual(rc, 0, f"Validator failed on production skills:\n{output}")

    def test_production_skills_version(self):
        """The real skills/ directory should be at the canonical version."""
        expected = validate.canonical_version(REPO_ROOT)
        rc, stdout, stderr = run_validator("--skills-dir", "skills", "--expect-version", expected)
        output = stdout + stderr
        self.assertEqual(rc, 0, f"Version check failed on production skills:\n{output}")


def make_manifest_root(
    root_manifest=None,
    claude_manifest=None,
    codex_manifest=None,
    power_version=None,
):
    """Build a temp repo root with an empty skills/ dir plus optional manifests.

    Returns the skills/ dir path, since that's what --skills-dir takes and
    repo_root_for() derives the root from its parent.
    """
    tmp = tempfile.mkdtemp(prefix="antislop-manifest-")
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)
    skills_dir = os.path.join(tmp, "skills")
    os.makedirs(skills_dir)
    if root_manifest is not None:
        with open(os.path.join(tmp, "plugin.json"), "w") as f:
            json.dump(root_manifest, f)
    if claude_manifest is not None:
        claude_dir = os.path.join(tmp, ".claude-plugin")
        os.makedirs(claude_dir)
        with open(os.path.join(claude_dir, "plugin.json"), "w") as f:
            json.dump(claude_manifest, f)
    if codex_manifest is not None:
        codex_dir = os.path.join(tmp, ".codex-plugin")
        os.makedirs(codex_dir)
        with open(os.path.join(codex_dir, "plugin.json"), "w") as f:
            json.dump(codex_manifest, f)
    if power_version is not None:
        power_dir = os.path.join(tmp, "powers", "antislop")
        os.makedirs(power_dir)
        with open(os.path.join(power_dir, "POWER.md"), "w") as f:
            f.write(f"# Antislop Power\n**Version:** {power_version}\n")
    return skills_dir


class TestRootPluginManifestChecks(unittest.TestCase):
    """Root plugin.json (agent-plugins.org) vs .claude-plugin/plugin.json."""

    def test_absent_root_manifest_is_not_an_error(self):
        skills_dir = make_manifest_root(
            claude_manifest={"name": "antislop", "version": "2.0.3"},
        )
        rc, stdout, stderr = run_validator("--skills-dir", skills_dir)
        self.assertEqual(rc, 0, f"Absent root plugin.json should not fail:\n{stdout + stderr}")

    def test_catches_version_drift_against_claude_plugin(self):
        skills_dir = make_manifest_root(
            root_manifest={"name": "antislop", "version": "9.9.9", "description": "x"},
            claude_manifest={"name": "antislop", "version": "1.0.0", "description": "x"},
        )
        rc, stdout, stderr = run_validator("--skills-dir", skills_dir)
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("disagrees with", output)

    def test_catches_description_drift_against_claude_plugin(self):
        skills_dir = make_manifest_root(
            root_manifest={"name": "antislop", "version": "1.0.0", "description": "one thing"},
            claude_manifest={"name": "antislop", "version": "1.0.0", "description": "another thing"},
        )
        rc, stdout, stderr = run_validator("--skills-dir", skills_dir)
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("description disagrees with", output)

    def test_matching_manifests_pass(self):
        skills_dir = make_manifest_root(
            root_manifest={"name": "antislop", "version": "1.0.0", "description": "same"},
            claude_manifest={"name": "antislop", "version": "1.0.0", "description": "same"},
        )
        rc, stdout, stderr = run_validator("--skills-dir", skills_dir)
        self.assertEqual(rc, 0, f"Matching manifests should pass:\n{stdout + stderr}")

    def test_catches_wrong_version_via_expect_version(self):
        skills_dir = make_manifest_root(
            root_manifest={"name": "antislop", "version": "1.0.0"},
        )
        rc, stdout, stderr = run_validator(
            "--skills-dir", skills_dir, "--expect-version", "2.0.0",
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("plugin.json: version=1.0.0, expected 2.0.0", output)

    def test_catches_missing_version_via_expect_version(self):
        skills_dir = make_manifest_root(
            root_manifest={"name": "antislop"},
        )
        rc, stdout, stderr = run_validator(
            "--skills-dir", skills_dir, "--expect-version", "2.0.0",
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("missing 'version' field, expected 2.0.0", output)

    def test_catches_missing_version_drift_against_claude_plugin(self):
        skills_dir = make_manifest_root(
            root_manifest={"name": "antislop"},
            claude_manifest={"name": "antislop", "version": "1.0.0"},
        )
        rc, stdout, stderr = run_validator("--skills-dir", skills_dir)
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("version=(missing) disagrees with", output)


class TestPluginManifestExpectVersionChecks(unittest.TestCase):
    """--expect-version against the supported Claude and Codex plugin manifests.

    Independent of TestRootPluginManifestChecks: those tests exercise
    check_root_plugin_manifest(), which only fires when a root
    agent-plugins.org plugin.json exists. These exercise
    check_expected_version()'s own read of each plugin manifest, so a repo
    with no root manifest still gets caught if a plugin manifest drifts.
    """

    def test_catches_claude_plugin_manifest_drift(self):
        skills_dir = make_manifest_root(
            claude_manifest={"name": "antislop", "version": "1.0.0"},
        )
        rc, stdout, stderr = run_validator(
            "--skills-dir", skills_dir, "--expect-version", "2.0.0",
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn(os.path.join(".claude-plugin", "plugin.json") + ": version=1.0.0, expected 2.0.0", output)
        self.assertEqual(output.count(os.path.join(".claude-plugin", "plugin.json") + ": version=1.0.0, expected 2.0.0"), 1)

    def test_catches_codex_plugin_manifest_drift(self):
        skills_dir = make_manifest_root(
            codex_manifest={"name": "antislop", "version": "1.0.0"},
        )
        rc, stdout, stderr = run_validator(
            "--skills-dir", skills_dir, "--expect-version", "2.0.0",
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn(os.path.join(".codex-plugin", "plugin.json") + ": version=1.0.0, expected 2.0.0", output)

    def test_matching_plugin_manifest_versions_pass(self):
        skills_dir = make_manifest_root(
            claude_manifest={"name": "antislop", "version": "2.0.0"},
            codex_manifest={"name": "antislop", "version": "2.0.0"},
            power_version="2.0.0",
        )
        rc, stdout, stderr = run_validator(
            "--skills-dir", skills_dir, "--expect-version", "2.0.0",
        )
        output = stdout + stderr
        self.assertNotIn(".claude-plugin/plugin.json", output)

    def test_absent_plugin_manifests_are_not_an_error(self):
        skills_dir = make_manifest_root()
        rc, stdout, stderr = run_validator(
            "--skills-dir", skills_dir, "--expect-version", "2.0.0",
        )
        output = stdout + stderr
        self.assertNotIn("plugin.json", output)


class TestVersionChecks(unittest.TestCase):
    """--expect-version flag."""

    def test_catches_wrong_version(self):
        """Version mismatch fixture should fail --expect-version 1.8.0."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", materialize_fixture("version-mismatch"),
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
            "--skills-dir", materialize_fixture("bad-score-name"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("Formulaic Writing Risk Score", output)

    def test_catches_missing_disclaimer(self):
        """Audit missing authorship disclaimer."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", materialize_fixture("no-disclaimer"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("authorship disclaimer", output)

    def test_catches_bad_antithesis_rule(self):
        """Antithesis rule without load-bearing distinction."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", materialize_fixture("bad-antithesis"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("antithesis", output.lower())
        self.assertIn("load-bearing", output.lower())


class TestRuleContentChecks(unittest.TestCase):
    """The opt-in CLI check compares registry rules with the style skill."""

    def _make_repo(self, rules, skill_body="", vocabulary_body=""):
        tmp = tempfile.mkdtemp(prefix="antislop-rule-content-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        skill_dir = os.path.join(tmp, "skills", "antislop")
        references_dir = os.path.join(skill_dir, "references")
        os.makedirs(references_dir)
        repo_root = os.path.dirname(os.path.abspath(validate.__file__))
        with open(os.path.join(repo_root, "rules.json"), encoding="utf-8") as f:
            registry = json.load(f)
        social_rules = [
            r for r in registry["rules"] if r.get("id", "").startswith("social-")
        ]
        registry["rules"] = rules + social_rules
        with open(os.path.join(tmp, "rules.json"), "w", encoding="utf-8") as f:
            json.dump(registry, f)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "name: antislop\n"
                "description: Rule-content fixture\n"
                "metadata:\n"
                '  version: "2.0.3"\n'
                "---\n\n"
                "# Antislop\n\n"
                "**Version:** 2.0.3\n\n"
                f"{skill_body}\n\n"
                "## Edit operations\n\n"
                "draft, revise, audit, transform\n\n"
                "## Audit mode\n\n"
                "Output a Formulaic Writing Risk Score. This score cannot prove AI authorship.\n\n"
                "## When NOT to use\n\n"
                "Skip code.\n"
            )
        with open(
            os.path.join(references_dir, "vocabulary.md"), "w", encoding="utf-8"
        ) as f:
            f.write(vocabulary_body)
        return os.path.join(tmp, "skills")

    @staticmethod
    def _rule(rule_id, text, category):
        with open(
            os.path.join(
                os.path.dirname(os.path.abspath(validate.__file__)), "rules.json"
            ),
            encoding="utf-8",
        ) as f:
            registry = json.load(f)
        template = next(
            r for r in registry["rules"] if r.get("category") == "filler"
        )
        rule = dict(template)
        rule["id"] = rule_id
        rule["text"] = text
        rule["category"] = category
        return rule

    def test_cli_accepts_rules_in_skill_or_vocabulary_reference(self):
        skills = self._make_repo(
            [
                self._rule("vocab-delve", "delve", "vocabulary"),
                self._rule(
                    "chatbot-certainly-absolutely",
                    "Certainly! / Absolutely!",
                    "chatbot",
                ),
                self._rule("struct-rule-of-three", "Rule of three", "structural"),
            ],
            skill_body="Never use DELVE in prose.",
            vocabulary_body="Avoid absolutely as a stock opener.\n",
        )

        rc, stdout, stderr = run_validator(
            "--skills-dir", skills, "--check-rule-content"
        )

        self.assertEqual(rc, 0, stdout + stderr)

    def test_cli_reports_a_missing_rule_as_rule_content_failure(self):
        skills = self._make_repo(
            [self._rule("filler-in-order", "In order to", "filler")]
        )

        rc, stdout, stderr = run_validator(
            "--skills-dir", skills, "--check-rule-content"
        )
        output = stdout + stderr

        self.assertEqual(rc, 1, output)
        self.assertIn("rule-content", output)
        self.assertIn("filler-in-order", output)
        self.assertIn("In order to", output)

    def test_cli_normalizes_dash_commentary_and_edge_punctuation(self):
        skills = self._make_repo(
            [
                self._rule(
                    "phrase-make-no-mistake",
                    '"Make no mistake!" — cut the setup.',
                    "phrase",
                )
            ],
            skill_body="Avoid MAKE NO MISTAKE as an opener.",
        )

        rc, stdout, stderr = run_validator(
            "--skills-dir", skills, "--check-rule-content"
        )

        self.assertEqual(rc, 0, stdout + stderr)

    def test_rule_content_check_is_opt_in(self):
        skills = self._make_repo(
            [self._rule("filler-in-order", "In order to", "filler")]
        )

        rc, stdout, stderr = run_validator("--skills-dir", skills)

        self.assertEqual(rc, 0, stdout + stderr)


class TestDashChecks(unittest.TestCase):
    """ASCII dash substitutes and cross-artifact mark parity."""

    def test_catches_dash_substitute(self):
        """A double hyphen standing in for an em dash outside a code span."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", materialize_fixture("dash-substitute"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("dash substitute", output)

    def test_allows_marks_inside_code_spans(self):
        """Literal mark references in backticks are meta-context, not usage."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", materialize_fixture("dash-substitute"),
        )
        output = stdout + stderr
        # Line 17 carries the violation; line 19 backticks the same marks.
        self.assertIn(":17:", output)
        self.assertNotIn(":19:", output)

    def test_catches_dash_drift_between_artifacts(self):
        """The same line carrying different marks in two shipped artifacts."""
        rc, stdout, stderr = run_validator(
            "--skills-dir", materialize_fixture("dash-drift"),
        )
        output = stdout + stderr
        self.assertNotEqual(rc, 0)
        self.assertIn("dash drift", output)

    def test_production_artifacts_have_no_substitutes(self):
        """The real artifacts, including the agent file and README."""
        rc, stdout, stderr = run_validator("--skills-dir", "skills")
        output = stdout + stderr
        self.assertEqual(rc, 0, f"Dash checks failed on production:\n{output}")


class TestSkillFileDiscovery(unittest.TestCase):
    """Regression test: the public package exposes two discoverable skills."""

    def test_only_the_public_skills_are_named_skill_md(self):
        found = []
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d != ".git"]
            if "SKILL.md" in files:
                found.append(os.path.relpath(os.path.join(root, "SKILL.md"), REPO_ROOT))
        expected = {
            os.path.join("skills", "antislop", "SKILL.md"),
            os.path.join("skills", "generate-slop", "SKILL.md"),
            os.path.join(".kiro", "skills", "generate-slop", "SKILL.md"),
        }
        self.assertEqual(
            set(found), expected,
            "Only the canonical public skills and the Kiro generate-slop forwarding entry may be named "
            "SKILL.md in this repo. If a new fixture needs one, name it SKILL.md.fixture and materialize "
            "it at test time -- see materialize_fixture() above.",
        )


class TestPluginManifestChecks(unittest.TestCase):
    """check_plugin_manifest() guards .claude-plugin/{plugin,marketplace}.json
    against the silent version and description drift AGENTS.md documents."""

    def _make_repo(self, plugin, marketplace=None):
        tmp = tempfile.mkdtemp(prefix="antislop-plugin-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, "skills"))
        os.makedirs(os.path.join(tmp, ".claude-plugin"))
        with open(os.path.join(tmp, ".claude-plugin", "plugin.json"), "w", encoding="utf-8") as f:
            json.dump(plugin, f)
        if marketplace is not None:
            with open(os.path.join(tmp, ".claude-plugin", "marketplace.json"), "w", encoding="utf-8") as f:
                json.dump(marketplace, f)
        return os.path.join(tmp, "skills")

    def test_absent_manifest_is_skipped(self):
        tmp = tempfile.mkdtemp(prefix="antislop-plugin-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, "skills"))
        self.assertEqual(validate.check_plugin_manifest(os.path.join(tmp, "skills"), "2.0.3"), [])

    def test_matching_manifest_is_clean(self):
        skills = self._make_repo(
            {"name": "antislop", "version": "2.0.3", "description": "Same words."},
            {"plugins": [{"name": "antislop", "description": "Same words."}]},
        )
        self.assertEqual(validate.check_plugin_manifest(skills, "2.0.3"), [])

    def test_version_mismatch_flagged(self):
        skills = self._make_repo(
            {"name": "antislop", "version": "9.9.9", "description": "Same words."},
            {"plugins": [{"name": "antislop", "description": "Same words."}]},
        )
        errors = validate.check_plugin_manifest(skills, "2.0.3")
        self.assertTrue(any("expected 2.0.3" in e for e in errors), errors)

    def test_version_not_checked_without_expected(self):
        skills = self._make_repo(
            {"name": "antislop", "version": "9.9.9", "description": "Same words."},
            {"plugins": [{"name": "antislop", "description": "Same words."}]},
        )
        self.assertEqual(validate.check_plugin_manifest(skills, None), [])

    def test_description_drift_flagged(self):
        skills = self._make_repo(
            {"name": "antislop", "version": "2.0.3", "description": "Plugin words."},
            {"plugins": [{"name": "antislop", "description": "Marketplace words."}]},
        )
        errors = validate.check_plugin_manifest(skills, "2.0.3")
        self.assertTrue(any("description does not match" in e for e in errors), errors)

    def test_missing_marketplace_entry_flagged(self):
        skills = self._make_repo(
            {"name": "antislop", "version": "2.0.3", "description": "Words."},
            {"plugins": [{"name": "something-else", "description": "Words."}]},
        )
        errors = validate.check_plugin_manifest(skills, "2.0.3")
        self.assertTrue(any("no plugins[] entry" in e for e in errors), errors)


class TestDerivativeVersionChecks(unittest.TestCase):
    """check_derivative_versions() catches a version bump that misses the
    hand-maintained opencode agent derivative (ADR 0002)."""

    def _make_repo(self, agent_version=None):
        tmp = tempfile.mkdtemp(prefix="antislop-deriv-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, "skills"))
        if agent_version is not None:
            d = os.path.join(tmp, ".opencode", "agents")
            os.makedirs(d)
            with open(os.path.join(d, "antislop.md"), "w", encoding="utf-8") as f:
                f.write(f"---\nname: antislop\n---\n**Version:** {agent_version}\n")
        return os.path.join(tmp, "skills")

    def test_absent_derivatives_skipped(self):
        skills = self._make_repo()
        self.assertEqual(validate.check_derivative_versions(skills, "2.0.3"), [])

    def test_matching_versions_clean(self):
        skills = self._make_repo(agent_version="2.0.3")
        self.assertEqual(validate.check_derivative_versions(skills, "2.0.3"), [])

    def test_agent_drift_flagged(self):
        skills = self._make_repo(agent_version="9.9.9")
        errors = validate.check_derivative_versions(skills, "2.0.3")
        self.assertTrue(any("antislop.md" in e and "expected 2.0.3" in e for e in errors), errors)

    def test_no_expected_version_skips(self):
        skills = self._make_repo(agent_version="9.9.9")
        self.assertEqual(validate.check_derivative_versions(skills, None), [])

class TestAuditContractChecks(unittest.TestCase):
    def test_catches_missing_audit_mode_contract(self):
        tmp = tempfile.mkdtemp(prefix="antislop-audit-contract-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        skill_dir = os.path.join(tmp, "antislop")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("# Antislop" + chr(10) + chr(10) + "## When NOT to use" + chr(10) + chr(10) + "Skip code." + chr(10))
        errors = validate.check_audit_output_format(tmp)
        self.assertTrue(any("missing audit mode contract" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
