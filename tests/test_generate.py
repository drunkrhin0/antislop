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


def run_generate(*args):
    cmd = [sys.executable, GENERATE] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout, result.stderr


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
                     "detection_class", "profiles"}
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
            # Run check mode against a registry that points to the tmpdir
            registry_copy = os.path.join(tmpdir, "rules.json")
            shutil.copy(REGISTRY, registry_copy)
            rc, stdout, stderr = run_generate("--check", "--registry", registry_copy)
            self.assertEqual(rc, 1, f"Check mode should fail on drifted content: {stdout} {stderr}")
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
