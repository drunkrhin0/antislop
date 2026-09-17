#!/usr/bin/env python3
"""Tests for the opt-in LinkedIn social profile (issue #103).

Covers the acceptance criteria:
  - the social-linkedin profile is opt-in and cannot activate from ordinary
    general prose
  - user-supplied examples transfer style signals only, never achievements,
    metrics, opinions, or experience
  - post type controls which structural elements are applicable
  - calls to action, hooks, hashtags, and short paragraphs stay optional and
    profile-local, so a post with no call to action passes clean
  - the general profile has regression fixtures proving no LinkedIn
    formatting leakage
  - supplied achievements, metrics, opinions, and experience are preserved
    exactly
  - no rule asks for deliberate errors or invented roughness, and the
    zero-em-dash rule stays absolute

Run: python3 -m unittest tests/test_linkedin_profile.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import linkedin  # noqa: E402
from registry import filter_rules_by_profile  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "linkedin-profile-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
LINKEDIN = os.path.join(ROOT, "tools", "linkedin.py")
SCORE = os.path.join(ROOT, "tools", "score.py")

SOCIAL_RULES = {
    "social-reach-promise", "social-mobile-paragraphs",
    "social-optional-cta", "social-optional-hook",
    "social-optional-hashtags", "social-scarl-optional",
}

POST_TYPES = ("lesson", "case-study", "announcement", "opinion",
              "practical-guide")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def run_score(input_text, profile="general"):
    result = subprocess.run([sys.executable, SCORE, "--profile", profile,
                             "--stdin"], capture_output=True, text=True,
                            cwd=ROOT, input=input_text)
    return json.loads(result.stdout), result.returncode


class TestProfileDefinition(unittest.TestCase):
    """The social-linkedin profile is opt-in and scoped."""

    def setUp(self):
        self.registry = load_registry()

    def test_profile_exists_and_is_opt_in(self):
        social = self.registry["profiles"]["social-linkedin"]
        self.assertFalse(social.get("default", False))
        self.assertIn("description", social)

    def test_post_types_present(self):
        self.assertEqual(
            set(self.registry["social_post_types"].keys()), set(POST_TYPES))

    def test_features_present(self):
        features = self.registry["social_post_features"]
        for feature in ("setup", "challenge", "action", "result", "lesson",
                        "position", "announcement", "steps"):
            self.assertIn(feature, features)
            self.assertIn("deterministic", features[feature])

    def test_each_post_type_lists_applicable_and_not_applicable(self):
        known = set(self.registry["social_post_features"].keys())
        for name, post_type in self.registry["social_post_types"].items():
            applicable = set(post_type["applicable"])
            not_applicable = set(post_type["not_applicable"])
            self.assertTrue(applicable & known)
            self.assertTrue(not_applicable & known)
            self.assertTrue(applicable.isdisjoint(not_applicable),
                            "%s overlaps" % name)


class TestNoLeakageRegression(unittest.TestCase):
    """Social rules never fire under the general or technical profiles."""

    def setUp(self):
        self.registry = load_registry()

    def test_social_rules_excluded_from_general_and_technical(self):
        for profile in ("general", "technical"):
            active = {rule["id"] for rule in
                      filter_rules_by_profile(self.registry["rules"], profile)}
            self.assertTrue(SOCIAL_RULES.isdisjoint(active),
                            "social rules leaked into %s" % profile)

    def test_general_prose_produces_no_social_finding(self):
        text = ("The cache evicts entries after they expire. Run `fetch` "
                "with version 2.4. When the cache is cold, then one record "
                "should come back instead of three.")
        result, _rc = run_score(text, "general")
        fired = {finding["rule_id"] for finding in result["findings"]}
        self.assertTrue(SOCIAL_RULES.isdisjoint(fired))

    def test_social_profile_activates_social_rules(self):
        active = {rule["id"] for rule in
                  filter_rules_by_profile(self.registry["rules"],
                                          "social-linkedin")}
        self.assertTrue(SOCIAL_RULES.issubset(active))

    def test_reviewer_requires_explicit_post_type(self):
        """There is no way to run the runner without naming a post type."""
        with self.assertRaises(ValueError):
            linkedin.review_post("We shipped the retry queue today.",
                                 "novel", self.registry)


class TestPostTypeRouting(unittest.TestCase):
    """Post type controls which structural elements are applicable."""

    def setUp(self):
        self.registry = load_registry()

    def test_lesson_routes_scarl_keep_and_story_elements_na(self):
        report = linkedin.review_post(
            "We cut our cold start from 1.8s to 0.4s by switching caches. "
            "The worker kept losing its lease at 02:14. We replaced the "
            "scheduler. The error rate dropped to 3%. The lesson: move the "
            "lease check before the dispatch.", "lesson", self.registry)
        route = {row["feature"]: row["status"] for row in report["route"]}
        self.assertEqual(route["lesson"], "keep")
        self.assertEqual(route["setup"], "keep")
        self.assertEqual(route["steps"], "n/a")

    def test_announcement_routes_only_announcement(self):
        report = linkedin.review_post(
            "We shipped the retry queue today. It stops jobs from dropping "
            "when the lease expires. Version 2.4 is live.",
            "announcement", self.registry)
        route = {row["feature"]: row["status"] for row in report["route"]}
        self.assertEqual(route["announcement"], "keep")
        for feature in ("setup", "challenge", "action", "result", "lesson"):
            self.assertEqual(route[feature], "n/a")

    def test_opinion_routes_only_position(self):
        report = linkedin.review_post(
            "I think code reviews should happen before the merge. The "
            "review finds the mistake while it is cheap to fix.",
            "opinion", self.registry)
        route = {row["feature"]: row["status"] for row in report["route"]}
        self.assertEqual(route["position"], "keep")
        self.assertEqual(route["steps"], "n/a")

    def test_practical_guide_routes_only_steps(self):
        report = linkedin.review_post(
            "How to make deploys boring. First, pin every dependency. "
            "Second, run the smoke test in CI.", "practical-guide",
            self.registry)
        route = {row["feature"]: row["status"] for row in report["route"]}
        self.assertEqual(route["steps"], "keep")
        self.assertEqual(route["lesson"], "n/a")


class TestOptionalElements(unittest.TestCase):
    """CTAs, hooks, hashtags, and SCARL are optional everywhere."""

    def setUp(self):
        self.registry = load_registry()

    def test_post_with_no_cta_passes_clean(self):
        report = linkedin.review_post(
            "We ran two schedulers side by side. The old one failed "
            "whenever the lease expired. We switched the lease check before "
            "the dispatch. Downtime fell from 40 minutes to 4.",
            "case-study", self.registry)
        self.assertEqual(report["decision"], "no-finding")

    def test_post_with_no_scarl_structure_passes_clean(self):
        report = linkedin.review_post(
            "A lease that outlives the worker timeout lets a crashed worker "
            "hold the queue. Keep the lease shorter than the worker "
            "timeout.", "lesson", self.registry)
        self.assertEqual(report["decision"], "no-finding")
        statuses = {row["feature"]: row["status"] for row in report["route"]}
        self.assertTrue(all(status == "n/a" for status in statuses.values()))

    def test_absent_optional_feature_is_never_missing(self):
        report = linkedin.review_post(
            "We shipped the retry queue today. Version 2.4 is live.",
            "announcement", self.registry)
        route = {row["feature"]: row["status"] for row in report["route"]}
        self.assertNotIn("missing", route.values())


class TestVoiceSample(unittest.TestCase):
    """A voice sample transfers style only, never personal facts."""

    def setUp(self):
        self.registry = load_registry()

    def test_achievement_from_sample_does_not_transfer(self):
        report = linkedin.review_post(
            "Our 200-person team shipped the new scheduler in a month.",
            "case-study", self.registry,
            voice_sample="A sample written by the author.",
            sample_facts=("200-person team",))
        self.assertEqual(report["decision"], "revise")
        self.assertIn("200-person team",
                      report["voice_sample"]["leaked_personal_facts"])
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("evaluation-voice-sample"), "revise")

    def test_clean_target_does_not_leak_sample_facts(self):
        report = linkedin.review_post(
            "We switched the lease check before the dispatch. Downtime fell "
            "from 40 minutes to 4.", "case-study", self.registry,
            voice_sample="A sample with a 200-person team.",
            sample_facts=("200-person team",))
        self.assertEqual(report["decision"], "no-finding")
        self.assertEqual(report["voice_sample"]["leaked_personal_facts"], [])


class TestPreservation(unittest.TestCase):
    """Supplied achievements, metrics, opinions, and experience are kept."""

    def setUp(self):
        self.registry = load_registry()

    def test_supplied_metric_kept_exactly(self):
        report = linkedin.review_post(
            "We shipped the retry queue today. It doubled throughput for "
            "cold starts.", "announcement", self.registry,
            required_facts=("doubled throughput",))
        self.assertEqual(report["decision"], "no-finding")
        self.assertEqual(report["preservation"]["missing"], [])

    def test_supplied_metric_dropped_is_a_finding(self):
        report = linkedin.review_post(
            "We shipped the retry queue today.", "announcement",
            self.registry, required_facts=("it doubled throughput",))
        self.assertEqual(report["decision"], "revise")
        self.assertEqual(report["preservation"]["missing"],
                         ["it doubled throughput"])


class TestReachPromise(unittest.TestCase):
    """No reach, engagement, or algorithmic benefit is promised."""

    def setUp(self):
        self.registry = load_registry()

    def test_reach_promise_asks_for_mechanism(self):
        report = linkedin.review_post(
            "Posting this will boost your reach and engagement. We switched "
            "caches.", "lesson", self.registry)
        self.assertEqual(report["decision"], "ask-author")
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("social-reach-promise"), "ask-author")

    def test_supplied_metric_with_evidence_is_not_a_promise(self):
        report = linkedin.review_post(
            "We cut cold start from 1.8s to 0.4s, which grew engagement for "
            "our users by 40%.", "case-study", self.registry)
        self.assertEqual(report["decision"], "no-finding")


class TestAbsoluteRules(unittest.TestCase):
    """The zero-em-dash rule stays absolute in the social profile."""

    def setUp(self):
        self.registry = load_registry()

    def test_em_dash_is_a_finding(self):
        report = linkedin.review_post(
            "We cut the deploy time \u2014 from 40 minutes to 4. We switched "
            "caches.", "lesson", self.registry)
        self.assertEqual(report["decision"], "revise")
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("fmt-em-dash"), "revise")


class TestCorpus(unittest.TestCase):
    """The shipped fixture corpus validates and passes."""

    def test_corpus_gate_passes(self):
        fixtures = load_fixtures()
        report = linkedin.run_corpus(fixtures, load_registry(), REGISTRY)
        self.assertEqual(report["schema_errors"], [])
        self.assertTrue(report["gate_pass"],
                        "failing: %s" % report["failing_ids"])
        self.assertEqual(report["failed"], 0)


class TestCli(unittest.TestCase):
    """The CLI entry point exercises the review."""

    def test_cli_review(self):
        result = subprocess.run(
            [sys.executable, LINKEDIN, "review", "--source-text",
             "We shipped the retry queue today. Version 2.4 is live.",
             "--post-type", "announcement"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["profile"], "social-linkedin")
        self.assertEqual(report["post_type"], "announcement")

    def test_cli_fixture_corpus(self):
        result = subprocess.run(
            [sys.executable, LINKEDIN, "--fixtures", FIXTURES],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["gate_pass"])


if __name__ == "__main__":
    unittest.main()