#!/usr/bin/env python3
"""Tests for the scoring engine.

Run: python3 tests/test_score.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCORE = os.path.join(ROOT, "score.py")
REGISTRY = os.path.join(ROOT, "rules.json")


def run_score(*args, input_text=None):
    cmd = [sys.executable, SCORE] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                            input=input_text)
    return result.returncode, result.stdout, result.stderr


def load_registry():
    with open(REGISTRY) as f:
        return json.load(f)


class TestScorerCLI(unittest.TestCase):
    """CLI interface."""

    def test_help(self):
        rc, out, err = run_score("--help")
        self.assertEqual(rc, 0)

    def test_scores_from_stdin(self):
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text="This text has no violations at all.")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("score", data)
        self.assertEqual(data["score"], 100)


class TestBaseWeights(unittest.TestCase):
    """Severity to weight mapping."""

    def setUp(self):
        self.registry = load_registry()

    def test_high_weight_is_8(self):
        self.assertEqual(self.registry["base_weights"]["high"], 8)

    def test_medium_weight_is_4(self):
        self.assertEqual(self.registry["base_weights"]["medium"], 4)

    def test_low_weight_is_2(self):
        self.assertEqual(self.registry["base_weights"]["low"], 2)


class TestDiminishingRepetition(unittest.TestCase):
    """Repeated instances of the same rule diminish."""

    def test_first_instance_full_weight(self):
        # Use text long enough that normalization is minimal
        text = "delve " + "ordinary " * 499
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        # 500 words, 1 high-severity finding: 8 * (500/500) = 8 normalized
        self.assertEqual(data["score"], 92)

    def test_second_instance_half_weight(self):
        # Two uses of "delve" in 500-word text
        text = "delve " + "ordinary " * 249 + "delve " + "ordinary " * 249
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        # 8 + 4 = 12 normalized (500 words, no adjustment)
        self.assertEqual(data["score"], 88)

    def test_third_instance_quarter_weight(self):
        # Three uses of "delve" in 750-word text
        text = "delve " + "ordinary " * 249 + "delve " + "ordinary " * 249 + "delve " + "ordinary " * 249
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        # 8 + 4 + 2 = 14 normalized to 500: 14 * (500/750) = 9.33 -> 9
        self.assertEqual(data["score"], 91)


class TestCap(unittest.TestCase):
    """Single rule penalty capped at 3x base weight."""

    def test_cap_at_3x(self):
        # Many uses of "delve" in 500-word text — should cap at 3 * 8 = 24
        text = "delve " * 20 + "ordinary " * 480
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        # Capped at 24 deducted
        self.assertEqual(data["score"], 76)


class TestNormalization(unittest.TestCase):
    """Penalties normalize to 500-word reference length."""

    def test_short_text_penalizes_less(self):
        # 10-word text with one high-severity finding
        short = "delve " + "word " * 9
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=short)
        data = json.loads(out)
        # 8 points * (500/10) = 400 normalized, but capped at 100
        # Score should be 0 (max penalty)
        self.assertEqual(data["score"], 0)

    def test_long_text_penalizes_less_per_word(self):
        # 1000-word text with one high-severity finding
        long_text = "delve " + "word " * 999
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=long_text)
        data = json.loads(out)
        # 8 points * (500/1000) = 4 normalized
        self.assertEqual(data["score"], 96)

    def test_500_words_no_normalization(self):
        # 500-word text with one high-severity finding
        text_500 = "delve " + "word " * 499
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text_500)
        data = json.loads(out)
        # 8 points * (500/500) = 8 normalized
        self.assertEqual(data["score"], 92)


class TestScoreBands(unittest.TestCase):
    """Score bands from the spec."""

    def test_clean_band(self):
        # No violations
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text="Clean text with no issues.")
        data = json.loads(out)
        self.assertGreaterEqual(data["score"], 85)

    def test_severe_band(self):
        # Heavy violations using exact-match vocabulary words in 500-word text
        slop = "delve leverage tapestry testament vibrant pivotal utilize synergy "
        text = slop * 10 + "ordinary " * 420
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        self.assertLessEqual(data["score"], 39)


class TestStructuredOutput(unittest.TestCase):
    """Output format matches the spec."""

    def test_output_has_required_fields(self):
        text = "delve " + "ordinary " * 499
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        required = {"score", "band", "word_count", "findings", "profile",
                     "density", "metadata"}
        self.assertTrue(required.issubset(set(data.keys())),
                        f"Missing fields: {required - set(data.keys())}")

    def test_finding_has_required_fields(self):
        text = "delve " + "ordinary " * 499
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        self.assertGreater(len(data["findings"]), 0)
        finding = data["findings"][0]
        required = {"rule_id", "severity", "weight", "excerpt", "reason",
                     "primary", "related"}
        self.assertTrue(required.issubset(set(finding.keys())),
                        f"Missing finding fields: {required - set(finding.keys())}")

    def test_metadata_has_version(self):
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text="Clean text.")
        data = json.loads(out)
        self.assertIn("version", data["metadata"])

    def test_density_is_per_500_words(self):
        text = "delve " + "ordinary " * 499
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        # 1 finding in 500 words, density should be 1.0
        self.assertEqual(data["density"], 1.0)


class TestOverlapHandling(unittest.TestCase):
    """One primary finding per span, related findings unscored."""

    def test_overlapping_rules_one_primary(self):
        # "In today's fast-paced world" triggers phrase-today-world (high)
        # and could overlap with other phrase rules at same position
        text = "In today's fast-paced world, we must consider the implications."
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        # Should have at least one primary finding
        primaries = [f for f in data["findings"] if f.get("primary")]
        self.assertGreater(len(primaries), 0)
        # Primary should be scored (weight > 0)
        self.assertGreater(primaries[0]["weight"], 0)


class TestProfile(unittest.TestCase):
    """Profile filtering affects scoring."""

    def test_technical_profile_allows_robust(self):
        text = "The system is robust and handles edge cases well."
        rc, out, err = run_score("--profile", "technical", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        # 'robust' should NOT be flagged in technical profile
        rule_ids = [f["rule_id"] for f in data["findings"]]
        self.assertNotIn("vocab-robust", rule_ids)


class TestWorkedExamples(unittest.TestCase):
    """Fixed worked examples from the spec."""

    def test_example_clean_text(self):
        """Clean text should score 85+."""
        text = ("We switched from VMs to containers three years ago. "
                "It cut our deploy time by 40% and eliminated half our "
                "infrastructure headaches. But it wasn't magic. We spent "
                "six months fixing our logging and monitoring first, and a "
                "developer had to own the transition.")
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        self.assertGreaterEqual(data["score"], 85)

    def test_example_heavy_slop(self):
        """Heavy slop text should score 40-64."""
        text = ("In today's fast-paced world, it's worth noting that "
                "delve into the transformative and innovative landscape "
                "of groundbreaking synergy. Let's dive in and leverage "
                "the pivotal tapestry of comprehensive empower unlock.")
        rc, out, err = run_score("--profile", "general", "--stdin",
                                  input_text=text)
        data = json.loads(out)
        self.assertLessEqual(data["score"], 64)


if __name__ == "__main__":
    unittest.main()
