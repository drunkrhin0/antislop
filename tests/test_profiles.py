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
        with open(REGISTRY, encoding="utf-8") as f:
            self.registry = json.load(f)

    def test_profiles_section_exists(self):
        self.assertIn("profiles", self.registry)

    def test_has_profiles(self):
        profiles = self.registry["profiles"]
        self.assertIsInstance(profiles, dict)
        self.assertEqual(len(profiles), 5)

    def test_has_required_profiles(self):
        expected = {"general", "technical", "fiction", "social-linkedin", "marketing"}
        self.assertEqual(set(self.registry["profiles"].keys()), expected)

    def test_general_is_default(self):
        general = self.registry["profiles"]["general"]
        self.assertTrue(general.get("default", False))

    def test_social_linkedin_is_not_default(self):
        social = self.registry["profiles"]["social-linkedin"]
        self.assertFalse(social.get("default", False))

    def test_each_profile_has_description(self):
        for name, profile in self.registry["profiles"].items():
            self.assertIn("description", profile,
                          f"Profile '{name}' missing description")


class TestProfileFiltering(unittest.TestCase):
    """Rules activate and deactivate per profile."""

    def setUp(self):
        with open(REGISTRY, encoding="utf-8") as f:
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
        """Structural rules are universal, except opt-in profile guidance."""
        structural = [r for r in self.registry["rules"]
                      if r["category"] == "structural"]
        self.assertGreater(len(structural), 0)
        for rule in structural:
            profiles = set(rule["profiles"])
            self.assertTrue(
                profiles == {"*"} or profiles == {"fiction"}
                or profiles == {"social-linkedin"}
                or profiles == {"marketing"},
                f"Structural rule {rule['id']} not universal or "
                "opt-in-profile-only",
            )

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

    def test_marketing_extends_general(self):
        self.assertEqual(
            self.registry["profiles"]["marketing"].get("extends"),
            ["general"],
        )

    def test_marketing_runtime_includes_inherited_rule(self):
        from score import score_text

        result = score_text(
            "We delve into the details.", self.registry, profile="marketing"
        )
        self.assertIn(
            "vocab-delve", {finding["rule_id"] for finding in result["findings"]}
        )

    def test_marketing_rules_are_scoped_to_marketing(self):
        """Marketing additions do not broaden general scoring."""
        marketing_rules = [r for r in self.registry["rules"]
                           if r["id"].startswith("marketing-")]
        self.assertGreater(len(marketing_rules), 0)
        for rule in marketing_rules:
            self.assertEqual(rule["profiles"], ["marketing"],
                             f"Marketing rule {rule['id']} escaped its profile")

    def test_marketing_rule_set_includes_rhetorical_closer(self):
        ids = [r["id"] for r in self.registry["rules"]]
        self.assertIn("marketing-rhetorical-closer", ids)


class TestGeneratorProfiles(unittest.TestCase):
    """Generator supports profile-aware output."""

    def test_generate_with_profile_flag(self):
        rc, stdout, stderr = run_generate("--check", "--profile", "general")
        self.assertIn(rc, (0, 1))

    def test_generate_technical_profile(self):
        # --check ignores --output-dir, so no path is written here.
        rc, stdout, stderr = run_generate("--check", "--profile", "technical")
        # Should succeed (generate the file)
        self.assertIn(rc, (0, 1))

    def test_different_profiles_produce_different_output(self):
        """General and technical profiles should produce different rule sets."""
        import shutil
        import tempfile
        gen_file = "skills/antislop/references/pattern-reference.md"
        outputs = {}
        dirs = []
        try:
            for p in ("general", "technical"):
                d = tempfile.mkdtemp(prefix=f"antislop-gen-{p}-")
                dirs.append(d)
                run_generate("--output-dir", d, "--profile", p)
                with open(os.path.join(d, gen_file), encoding="utf-8") as f:
                    outputs[p] = f.read()
        finally:
            for d in dirs:
                shutil.rmtree(d, ignore_errors=True)
        # They should differ (technical drops some vocab rules)
        self.assertNotEqual(outputs["general"], outputs["technical"],
                            "General and technical profiles should produce different output")


if __name__ == "__main__":
    unittest.main()
