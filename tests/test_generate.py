#!/usr/bin/env python3
"""Tests for the rule registry and generator.

Run: python3 -m unittest tests/test_generate.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
GENERATE = os.path.join(ROOT, "generate.py")
REGISTRY = os.path.join(ROOT, "rules.json")

sys.path.insert(0, os.path.abspath(ROOT))
import generate  # noqa: E402 -- import after sys.path setup, reused for direct unit tests
from registry import load_registry  # noqa: E402


def run_generate(*args):
    cmd = [sys.executable, GENERATE] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout, result.stderr


STEERING_COPY_SOURCES = (
    "vocabulary.md",
    "structure-patterns.md",
    "examples.md",
    "audit-checklist.md",
)


def _copy_reference_sources(repo_root):
    """Copy generate_all()'s non-registry sources into a fake repo root.

    generate_all() reads the skills/antislop/references/*.md files (for the
    verbatim-copy steering outputs) and skills/antislop-audit/SKILL.md (for
    the composed audit-mode.md) unconditionally, so any --registry pointed
    at a tmpdir needs them present or generation itself raises instead of
    reporting a diff.
    """
    import shutil
    refs_src = os.path.join(ROOT, "skills", "antislop", "references")
    refs_dst = os.path.join(repo_root, "skills", "antislop", "references")
    os.makedirs(refs_dst, exist_ok=True)
    for name in STEERING_COPY_SOURCES:
        shutil.copy(os.path.join(refs_src, name), os.path.join(refs_dst, name))

    audit_skill_dst = os.path.join(repo_root, "skills", "antislop-audit")
    os.makedirs(audit_skill_dst, exist_ok=True)
    shutil.copy(
        os.path.join(ROOT, "skills", "antislop-audit", "SKILL.md"),
        os.path.join(audit_skill_dst, "SKILL.md"),
    )


class TestRegistrySchema(unittest.TestCase):
    """Rule registry structure and required fields."""

    def setUp(self):
        with open(REGISTRY) as f:
            self.registry = json.load(f)

    def test_registry_has_version(self):
        self.assertIn("version", self.registry)

    def test_registry_has_rules_array(self):
        self.assertIn("rules", self.registry)
        self.assertIsInstance(self.registry["rules"], list)

    def test_registry_has_rules(self):
        self.assertGreater(len(self.registry["rules"]), 0)

    def test_each_rule_has_required_fields(self):
        required = {"id", "text", "category", "severity", "base_weight",
                     "detection_class", "profiles", "confidence"}
        for rule in self.registry["rules"]:
            missing = required - set(rule.keys())
            self.assertFalse(missing, f"Rule {rule.get('id', '?')} missing: {missing}")

    def test_rule_ids_are_unique(self):
        ids = [r["id"] for r in self.registry["rules"]]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate rule IDs found")

    def test_severity_values(self):
        valid = {"high", "medium", "low"}
        for rule in self.registry["rules"]:
            self.assertIn(rule["severity"], valid,
                          f"Rule {rule['id']}: invalid severity '{rule['severity']}'")

    def test_base_weight_matches_severity(self):
        weight_map = {"high": 8, "medium": 4, "low": 2}
        for rule in self.registry["rules"]:
            expected = weight_map[rule["severity"]]
            self.assertEqual(rule["base_weight"], expected,
                             f"Rule {rule['id']}: base_weight should be {expected}")

    def test_detection_class_values(self):
        valid = {"exact_match", "phrase_match", "pattern_match", "structural"}
        for rule in self.registry["rules"]:
            self.assertIn(rule["detection_class"], valid,
                          f"Rule {rule['id']}: invalid detection_class '{rule['detection_class']}'")

    def test_profiles_are_lists(self):
        for rule in self.registry["rules"]:
            self.assertIsInstance(rule["profiles"], list,
                                  f"Rule {rule['id']}: profiles must be a list")


class TestGenerator(unittest.TestCase):
    """Generator produces deterministic output."""

    def test_generate_runs(self):
        rc, stdout, stderr = run_generate("--check")
        # Should exit 0 (generated matches committed) or 1 (mismatch)
        self.assertIn(rc, (0, 1), f"Generator failed: {stderr}")

    def test_generate_check_mode_exits_nonzero_on_drift(self):
        """Check mode detects drift when generated content differs from committed."""
        import shutil
        import tempfile
        tmpdir = tempfile.mkdtemp()
        try:
            # Create a drifted pattern-reference.md
            drift_dir = os.path.join(tmpdir, "skills", "antislop-audit", "references")
            os.makedirs(drift_dir)
            with open(os.path.join(drift_dir, "pattern-reference.md"), "w") as f:
                f.write("# DRIFTED CONTENT\n")
            # generate_all() also reads the verbatim-copy sources under
            # skills/antislop/references/ relative to repo_root, so those
            # need to exist in the tmpdir too or generation itself errors.
            _copy_reference_sources(tmpdir)
            # Run check mode against a registry that points to the tmpdir
            registry_copy = os.path.join(tmpdir, "rules.json")
            shutil.copy(REGISTRY, registry_copy)
            rc, stdout, stderr = run_generate("--check", "--registry", registry_copy)
            self.assertEqual(rc, 1, f"Check mode should fail on drifted content: {stdout} {stderr}")
        finally:
            shutil.rmtree(tmpdir)

    def test_generate_check_mode_detects_steering_drift(self):
        """Check mode detects drift in a Power steering file (ticket 02)."""
        import shutil
        import tempfile
        tmpdir = tempfile.mkdtemp()
        try:
            _copy_reference_sources(tmpdir)
            registry_copy = os.path.join(tmpdir, "rules.json")
            shutil.copy(REGISTRY, registry_copy)
            # Write a drifted steering file (the other steering outputs and
            # pattern-reference.md are simply MISSING, which check_mode
            # also reports, but the drift assertion below is the point).
            steering_dir = os.path.join(tmpdir, "powers", "antislop", "steering")
            os.makedirs(steering_dir)
            with open(os.path.join(steering_dir, "vocabulary.md"), "w") as f:
                f.write("# DRIFTED STEERING CONTENT\n")
            rc, stdout, stderr = run_generate("--check", "--registry", registry_copy)
            self.assertEqual(rc, 1, f"Check mode should fail on drifted steering content: {stdout} {stderr}")
            self.assertIn("DRIFT: powers/antislop/steering/vocabulary.md", stdout)
        finally:
            shutil.rmtree(tmpdir)

    def test_generate_help(self):
        rc, stdout, stderr = run_generate("--help")
        self.assertEqual(rc, 0)

    def test_generate_produces_deterministic_output(self):
        """Running generate twice produces identical output."""
        rc1, out1, _ = run_generate("--output-dir", "/tmp/antislop-gen-test-1")
        rc2, out2, _ = run_generate("--output-dir", "/tmp/antislop-gen-test-2")
        # Read the generated files and compare
        for root, dirs, files in os.walk("/tmp/antislop-gen-test-1"):
            for f in files:
                path1 = os.path.join(root, f)
                path2 = path1.replace("antislop-gen-test-1", "antislop-gen-test-2")
                if os.path.exists(path2):
                    with open(path1) as a, open(path2) as b:
                        self.assertEqual(a.read(), b.read(),
                                         f"Non-deterministic output: {f}")
        # Cleanup
        import shutil
        shutil.rmtree("/tmp/antislop-gen-test-1", ignore_errors=True)
        shutil.rmtree("/tmp/antislop-gen-test-2", ignore_errors=True)


class TestGenerateAllSteeringOutputs(unittest.TestCase):
    """generate_all() covers the antislop Power's steering files (ticket 02)."""

    STEERING_PATHS = {
        "powers/antislop/steering/vocabulary.md": "skills/antislop/references/vocabulary.md",
        "powers/antislop/steering/structure-patterns.md": "skills/antislop/references/structure-patterns.md",
        "powers/antislop/steering/examples.md": "skills/antislop/references/examples.md",
        "powers/antislop/steering/audit-checklist.md": "skills/antislop/references/audit-checklist.md",
    }

    def setUp(self):
        self.repo_root = os.path.abspath(ROOT)
        self.registry = load_registry(os.path.join(self.repo_root, "rules.json"))

    def test_generate_all_returns_six_entries(self):
        """The existing pattern-reference.md plus the five steering files."""
        result = generate.generate_all(self.registry, self.repo_root)
        self.assertEqual(len(result), 6, f"Expected 6 artifacts, got: {sorted(result)}")
        expected_paths = {"skills/antislop-audit/references/pattern-reference.md",
                           "powers/antislop/steering/audit-mode.md"}
        expected_paths |= set(self.STEERING_PATHS)
        self.assertEqual(set(result), expected_paths)

    def test_steering_copies_are_byte_identical_to_sources(self):
        """Each verbatim-copy steering output matches its source exactly."""
        result = generate.generate_all(self.registry, self.repo_root)
        for steering_path, source_path in self.STEERING_PATHS.items():
            with open(os.path.join(self.repo_root, source_path)) as f:
                expected = f.read()
            self.assertEqual(
                result[steering_path], expected,
                f"{steering_path} is not byte-identical to {source_path}"
            )

    def test_audit_mode_carries_scoring_method_and_disclaimer(self):
        """audit-mode.md must carry the scoring method and authorship disclaimer.

        The original ticket 02 pointed audit-mode.md at
        render_pattern_reference() alone, which is just the rules table and
        severity weights — no scoring method, no output format, no
        disclaimer. validate.py's checks 8 and 9 exist precisely to keep an
        audit surface from shipping without those two things, so audit-mode
        must carry both: the antislop-audit SKILL.md body (frontmatter
        stripped) composed with the pattern reference below it.
        """
        result = generate.generate_all(self.registry, self.repo_root, profile="general")
        audit_mode = result["powers/antislop/steering/audit-mode.md"]
        pattern_reference = result["skills/antislop-audit/references/pattern-reference.md"]

        self.assertIn("Formulaic Writing Risk Score", audit_mode)
        self.assertIn("cannot prove", audit_mode.lower())
        # Still carries the pattern reference content (rules table etc.),
        # just no longer *as* the whole file.
        self.assertIn("## Vocabulary", audit_mode)
        self.assertIn("## Severity weights", audit_mode)
        # It must not have regressed back to being just the rendering —
        # that was the bug this composition fixes.
        self.assertNotEqual(audit_mode, pattern_reference)

    def test_strip_frontmatter_removes_only_the_leading_block(self):
        """strip_frontmatter() removes the YAML block but keeps body '---' rules.

        skills/antislop-audit/SKILL.md's body uses '---' as a markdown
        horizontal rule several times after the frontmatter closes, so a
        naive split on '---' would cut the body short. This asserts the
        real source file survives that trap intact.
        """
        skill_text = generate.read_source_file(
            self.repo_root, "skills/antislop-audit/SKILL.md"
        )
        body = generate.strip_frontmatter(skill_text)
        self.assertNotIn("name: antislop-audit", body)
        self.assertTrue(body.startswith("# Antislop Audit"))
        # Content past the body's own '---' dividers must survive.
        self.assertIn("## How to run an audit", body)
        self.assertIn("## Notes", body)


class TestRegistryContent(unittest.TestCase):
    """Registry contains expected rules from the 1.8 content."""

    def setUp(self):
        with open(REGISTRY) as f:
            self.registry = json.load(f)
        self.rules_by_id = {r["id"]: r for r in self.registry["rules"]}

    def test_has_vocabulary_rules(self):
        vocab = [r for r in self.registry["rules"] if r["category"] == "vocabulary"]
        self.assertGreater(len(vocab), 0, "No vocabulary rules found")

    def test_has_phrase_rules(self):
        phrases = [r for r in self.registry["rules"] if r["category"] == "phrase"]
        self.assertGreater(len(phrases), 0, "No phrase rules found")

    def test_has_structural_rules(self):
        structural = [r for r in self.registry["rules"] if r["category"] == "structural"]
        self.assertGreater(len(structural), 0, "No structural rules found")

    def test_has_formatting_rules(self):
        formatting = [r for r in self.registry["rules"] if r["category"] == "formatting"]
        self.assertGreater(len(formatting), 0, "No formatting rules found")

    def test_delve_rule_exists(self):
        self.assertIn("vocab-delve", self.rules_by_id)
        rule = self.rules_by_id["vocab-delve"]
        self.assertEqual(rule["severity"], "high")
        self.assertEqual(rule["detection_class"], "exact_match")

    def test_em_dash_rule_exists(self):
        self.assertIn("fmt-em-dash", self.rules_by_id)
        rule = self.rules_by_id["fmt-em-dash"]
        self.assertEqual(rule["severity"], "high")

    def test_antithesis_rule_exists(self):
        self.assertIn("struct-antithesis", self.rules_by_id)
        rule = self.rules_by_id["struct-antithesis"]
        self.assertIn("load-bearing", rule.get("text", "").lower() +
                       " ".join(rule.get("exceptions", [])))

    def test_overlap_references_are_valid(self):
        """Every ID in an overlaps array must exist in the registry."""
        ids = set(self.rules_by_id.keys())
        for rule in self.registry["rules"]:
            for ref in rule.get("overlaps", []):
                self.assertIn(ref, ids,
                              f"Rule {rule['id']}: overlaps reference '{ref}' not found")


if __name__ == "__main__":
    unittest.main()
