#!/usr/bin/env python3
"""Tests for writing profile support.

Run: python3 tests/test_profiles.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
REGISTRY = os.path.join(ROOT, "rules.json")
GENERATE = os.path.join(ROOT, "generate.py")


def run_generate(*args):
    cmd = [sys.executable, GENERATE] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout, result.stderr


class TestProfileDefinitions(unittest.TestCase):
    """Registry defines expected profiles."""

    def setUp(self):
        with open(REGISTRY) as f:
            self.registry = json.load(f)

    def test_profiles_section_exists(self):
        self.assertIn("profiles", self.registry)

    def test_has_seven_profiles(self):
        profiles = self.registry["profiles"]
        self.assertIsInstance(profiles, dict)
        self.assertEqual(len(profiles), 7)

    def test_has_required_profiles(self):
        expected = {"general", "technical", "business", "marketing",
                    "social", "fiction", "academic"}
        self.assertEqual(set(self.registry["profiles"].keys()), expected)

    def test_general_is_default(self):
        general = self.registry["profiles"]["general"]
        self.assertTrue(general.get("default", False))

    def test_each_profile_has_description(self):
        for name, profile in self.registry["profiles"].items():
            self.assertIn("description", profile,
                          f"Profile '{name}' missing description")


class TestProfileFiltering(unittest.TestCase):
    """Rules activate and deactivate per profile."""

    def setUp(self):
        with open(REGISTRY) as f:
            self.registry = json.load(f)
        self.rules = {r["id"]: r for r in self.registry["rules"]}

    def test_chatbot_rules_active_in_every_profile(self):
        """Chatbot artifacts are universal per spec."""
        chatbot = [r for r in self.registry["rules"]
                   if r["category"] == "chatbot"]
        self.assertGreater(len(chatbot), 0)
        for rule in chatbot:
            profiles = set(rule["profiles"])
            self.assertEqual(profiles, {"*"},
                             f"Chatbot rule {rule['id']} not universal")

    def test_formatting_rules_active_in_every_profile(self):
        """Formatting rules (em-dash etc.) are universal per spec."""
        fmt = [r for r in self.registry["rules"]
               if r["category"] == "formatting"]
        self.assertGreater(len(fmt), 0)
        for rule in fmt:
            profiles = set(rule["profiles"])
            self.assertEqual(profiles, {"*"},
                             f"Formatting rule {rule['id']} not universal")

    def test_structural_rules_active_in_every_profile(self):
        """Structural rules are universal."""
        structural = [r for r in self.registry["rules"]
                      if r["category"] == "structural"]
        self.assertGreater(len(structural), 0)
        for rule in structural:
            profiles = set(rule["profiles"])
            self.assertEqual(profiles, {"*"},
                             f"Structural rule {rule['id']} not universal")

    def test_vocab_rules_are_profile_dependent(self):
        """Vocabulary rules should have explicit profile lists (not '*')."""
        vocab = [r for r in self.registry["rules"]
                 if r["category"] == "vocabulary"]
        self.assertGreater(len(vocab), 0)
        for rule in vocab:
            self.assertNotEqual(rule["profiles"], ["*"],
                                f"Vocab rule {rule['id']} should not be universal")

    def test_significant_in_technical_profile(self):
        """'significant' should be allowed in technical writing."""
        rule = self.rules.get("vocab-significant")
        self.assertIsNotNone(rule)
        profiles = set(rule["profiles"])
        self.assertNotIn("technical", profiles,
                         "'significant' should NOT be flagged in technical profile")

    def test_robust_in_technical_profile(self):
        """'robust' should be allowed in technical writing."""
        rule = self.rules.get("vocab-robust")
        self.assertIsNotNone(rule)
        profiles = set(rule["profiles"])
        self.assertNotIn("technical", profiles,
                         "'robust' should NOT be flagged in technical profile")


class TestGeneratorProfiles(unittest.TestCase):
    """Generator supports profile-aware output."""

    def test_generate_with_profile_flag(self):
        rc, stdout, stderr = run_generate("--check", "--profile", "general")
        self.assertIn(rc, (0, 1))

    def test_generate_technical_profile(self):
        rc, stdout, stderr = run_generate(
            "--check", "--profile", "technical",
            "--output-dir", "/tmp/antislop-gen-tech"
        )
        # Should succeed (generate the file)
        self.assertIn(rc, (0, 1))

    def test_different_profiles_produce_different_output(self):
        """General and technical profiles should produce different rule sets."""
        import shutil
        for p in ("general", "technical"):
            d = f"/tmp/antislop-gen-{p}"
            shutil.rmtree(d, ignore_errors=True)
            run_generate("--output-dir", d, "--profile", p)
        # Read the generated pattern references
        gen_file = "skills/antislop-audit/references/pattern-reference.md"
        with open(f"/tmp/antislop-gen-general/{gen_file}") as f:
            general = f.read()
        with open(f"/tmp/antislop-gen-technical/{gen_file}") as f:
            technical = f.read()
        # They should differ (technical drops some vocab rules)
        self.assertNotEqual(general, technical,
                            "General and technical profiles should produce different output")
        # Cleanup
        shutil.rmtree("/tmp/antislop-gen-general", ignore_errors=True)
        shutil.rmtree("/tmp/antislop-gen-technical", ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
