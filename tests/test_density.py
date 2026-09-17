#!/usr/bin/env python3
"""Tests for the density and precision review (issue #100).

Covers the acceptance criteria:
  - density is calculated over a documented passage window and reports the
    contributing rule IDs
  - one legitimate term and two separated terms never trigger a density
    finding; three clustered terms do
  - unsourced precision is advisory and never declares a number false
  - supplied facts, nearby citations, estimates, and technical constants
    have clean fixtures
  - structural candidates (heading hierarchy, engagement openings, template
    headings, self-promotion, 'rather than' comparisons) have load-bearing
    positive cases
  - heading checks preserve intentional accessibility and technical hierarchy
  - no source score band or Horoscope result enters the numeric risk score
    without labeled validation
  - every density and precision finding is advisory with zero weight

Run: python3 -m unittest tests/test_density.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import density  # noqa: E402
import review  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "density-precision-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
VALIDATE = os.path.join(ROOT, "validate.py")
SCORE = os.path.join(ROOT, "score.py")

STATUSES = ("keep", "revise", "ask-author", "cut", "no-finding")

TWO_SEPARATED = (
    "We leverage synergy for the new build. The build pipeline compiles each "
    "commit and runs the test suite before promoting the artifact. The "
    "deployment system writes a manifest, verifies the checksum, and notifies "
    "the on-call engineer when the rollout finishes. Monitoring aggregates the "
    "metrics and pages the owner when latency exceeds the configured budget. "
    "The cache stores recent results so repeated queries return quickly "
    "without touching the database again. Operators rotate credentials on a "
    "schedule and record the rotation in the audit log. The nightly job cleans "
    "expired sessions and compacts the history table. Alert routing checks the "
    "recipient list once per shift and deduplicates pages by incident. The "
    "metrics endpoint returns counts for the last hour and the week before it. "
    "Then we delve into the details."
)

THREE_CLUSTERED = "We leverage synergy to unlock value."

UNSUPPORTED = "75% of organizations fail within a year."


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def rule_by_id(registry, rid):
    for rule in registry["rules"]:
        if rule["id"] == rid:
            return rule
    raise KeyError(rid)


def run_score(input_text):
    result = subprocess.run([sys.executable, SCORE, "--profile", "general",
                             "--stdin"], capture_output=True, text=True,
                            cwd=ROOT, input=input_text)
    return json.loads(result.stdout), result.returncode


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestPassageDensity(unittest.TestCase):
    """Density uses a documented passage window and reports contributing
    rule IDs."""

    def setUp(self):
        self.registry = load_registry()
        self.rule = rule_by_id(self.registry, "struct-passage-density")

    def test_documented_window_and_cluster_min(self):
        self.assertEqual(density.PASSAGE_WINDOW, 100)
        self.assertEqual(density.CLUSTER_MIN, 3)

    def test_one_legitimate_term_does_not_trigger(self):
        result = density.detect_passage_density(
            "We utilize the API for the retry path.", self.rule, "general",
            self.registry)
        self.assertEqual(result["findings"], [])

    def test_two_separated_terms_do_not_trigger(self):
        result = density.detect_passage_density(
            TWO_SEPARATED, self.rule, "general", self.registry)
        self.assertEqual(result["findings"], [])

    def test_three_clustered_terms_trigger_with_contributing_rule_ids(self):
        result = density.detect_passage_density(
            THREE_CLUSTERED, self.rule, "general", self.registry)
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["evidence"], "document")
        self.assertEqual(finding["signal"], "advisory")
        self.assertEqual(finding["sample"]["contributing_rules"],
                         ["vocab-leverage", "vocab-synergy", "vocab-unlock"])
        self.assertEqual(finding["sample"]["distinct_terms"], 3)

    def test_repetition_of_one_term_does_not_trigger(self):
        result = density.detect_passage_density(
            "delve delve delve delve delve", self.rule, "general",
            self.registry)
        self.assertEqual(result["findings"], [])

    def test_density_findings_are_advisory_and_zero_weight(self):
        data, rc = run_score(THREE_CLUSTERED)
        self.assertEqual(rc, 0)
        density_findings = [f for f in data["findings"]
                            if f["rule_id"] == "struct-passage-density"]
        self.assertEqual(len(density_findings), 1)
        self.assertEqual(density_findings[0]["signal"], "advisory")
        self.assertEqual(density_findings[0]["weight"], 0)


class TestUnsourcedPrecision(unittest.TestCase):
    """Unsourced precision is advisory, never declares a number false, and
    exempts sources, supplied facts, estimates, and technical constants."""

    def setUp(self):
        self.registry = load_registry()
        self.rule = rule_by_id(self.registry, "struct-unsourced-precision")

    def test_unsupported_exact_statistic_is_a_finding(self):
        result = density.detect_unsourced_precision(
            UNSUPPORTED, self.rule, "general", self.registry)
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["signal"], "advisory")
        self.assertEqual(finding["sample"]["statistic"], "75%")
        self.assertEqual(finding["sample"]["kind"], "percent")
        self.assertIn("never declares", finding["message"].lower())
        self.assertNotIn(" is false", finding["message"].lower())
        self.assertNotIn(" is wrong", finding["message"].lower())

    def test_finding_never_declares_the_number_false(self):
        for entry in density.precision_entries(UNSUPPORTED, "general",
                                               self.registry):
            self.assertFalse(entry["declared"])

    def test_sourced_statistic_is_clean(self):
        result = density.detect_unsourced_precision(
            "According to a 2024 survey, 75% of organizations fail within a "
            "year.", self.rule, "general", self.registry)
        self.assertEqual(result["findings"], [])

    def test_supplied_fact_is_clean(self):
        result = density.detect_unsourced_precision(
            "Our audit of 40 applications found 75% had default credentials.",
            self.rule, "general", self.registry)
        self.assertEqual(result["findings"], [])

    def test_estimate_is_clean(self):
        result = density.detect_unsourced_precision(
            "Roughly 75% of organizations fail within a year.", self.rule,
            "general", self.registry)
        self.assertEqual(result["findings"], [])

    def test_technical_constant_is_clean(self):
        result = density.detect_unsourced_precision(
            "The SLA guarantees 99.99% availability, and the standard allows "
            "0.1% packet loss on the transit link.", self.rule, "general",
            self.registry)
        self.assertEqual(result["findings"], [])

    def test_measured_result_is_clean(self):
        result = density.detect_unsourced_precision(
            "Frequent refactoring caused 37% more bugs across our 14-service "
            "codebase.", self.rule, "general", self.registry)
        self.assertEqual(result["findings"], [])

    def test_precision_findings_are_advisory_and_zero_weight(self):
        data, rc = run_score(UNSUPPORTED)
        self.assertEqual(rc, 0)
        self.assertEqual(data["score"], 100)
        precision_findings = [f for f in data["findings"]
                              if f["rule_id"] == "struct-unsourced-precision"]
        self.assertEqual(len(precision_findings), 1)
        self.assertEqual(precision_findings[0]["signal"], "advisory")
        self.assertEqual(precision_findings[0]["weight"], 0)

    def test_unsupported_precision_reviews_to_ask_author(self):
        report = review.review_text(UNSUPPORTED, "argument", self.registry)
        self.assertEqual(report["decision"], "ask-author")
        self.assertTrue(any(f["rule_id"] == "struct-unsourced-precision"
                            and f["status"] == "ask-author"
                            for f in report["findings"]))
        self.assertTrue(any("source for this figure" in item["tk"]
                            for item in report["author_questions"]))


class TestStructuralCandidates(unittest.TestCase):
    """Structural candidates have load-bearing positive cases."""

    def setUp(self):
        self.registry = load_registry()

    def detect(self, detector, text):
        rule = next(r for r in self.registry["rules"]
                    if r.get("detector") == detector)
        return density.detect_rule(text, rule, "general", self.registry)

    def test_heading_functional_hierarchy_is_clean(self):
        result = self.detect("heading_hierarchy",
                             "# Deployment notes\n\n## Setup\n\n### "
                             "Configuration\n\n## Rollback\n\nThe prior image "
                             "is restored by the last action in the runbook.")
        self.assertEqual(result["findings"], [])

    def test_heading_anomalous_hierarchy_is_flagged(self):
        result = self.detect("heading_hierarchy",
                             "# Deployment notes\n\n### Setup\n\nThe "
                             "installer runs the agent binary.")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["sample"]["previous_level"], 1)
        self.assertEqual(result["findings"][0]["sample"]["level"], 3)

    def test_engagement_specific_opening_is_clean(self):
        result = self.detect("engagement_bait",
                             "Did the 2021 outage change how you back up your "
                             "databases? We now test restores monthly.")
        self.assertEqual(result["findings"], [])

    def test_engagement_generic_opening_is_flagged(self):
        result = self.detect("engagement_bait",
                             "Have you ever wondered why backups fail at the "
                             "worst moment?")
        self.assertEqual(len(result["findings"]), 1)

    def test_template_heading_argument_is_flagged(self):
        report = review.review_text(
            "## What is leadership\n\nLeadership requires choosing between "
            "competing values every day.", "argument", self.registry)
        template = [f for f in report["findings"]
                    if f["rule_id"] == "struct-template-headings"]
        self.assertTrue(template)
        self.assertEqual(template[0]["status"], "revise")

    def test_template_heading_explanation_is_kept(self):
        report = review.review_text(
            "## What is a lease?\n\nA lease grants one party the right to use "
            "an asset for a fixed term without transferring ownership.",
            "explanation", self.registry)
        template = [f for f in report["findings"]
                    if f["rule_id"] == "struct-template-headings"]
        self.assertTrue(template)
        self.assertEqual(template[0]["status"], "keep")

    def test_self_promotion_flagged(self):
        result = self.detect("self_promotion",
                             "We are proud to announce our industry-leading "
                             "platform.")
        self.assertGreater(len(result["findings"]), 0)

    def test_self_promotion_measured_comparison_is_clean(self):
        result = self.detect("self_promotion",
                             "Our encoder matches the industry-leading "
                             "baseline within 0.3 dB.")
        self.assertEqual(result["findings"], [])

    def test_rather_than_decorative_is_flagged(self):
        result = self.detect("rather_than",
                             "We write for clarity rather than for effect.")
        self.assertEqual(len(result["findings"]), 1)

    def test_rather_than_load_bearing_is_clean(self):
        result = self.detect(
            "rather_than",
            "We use an in-memory retry queue rather than re-reading the "
            "database on every attempt.")
        self.assertEqual(result["findings"], [])

    def test_trailing_affirmation_is_cut(self):
        report = review.review_text(
            "In conclusion, I hope this helps! Let me know if you have "
            "questions!", "message", self.registry)
        self.assertEqual(report["decision"], "cut")
        cut = {f["rule_id"] for f in report["findings"]
               if f["status"] == "cut"}
        self.assertIn("chatbot-hope-helps", cut)
        self.assertIn("chatbot-let-me-know", cut)


class TestRiskScoreBoundaries(unittest.TestCase):
    """No source score band or Horoscope result enters the numeric risk score
    without labeled validation."""

    def setUp(self):
        self.registry = load_registry()

    def test_band_labels_are_the_registry_bands_only(self):
        data, rc = run_score(THREE_CLUSTERED)
        self.assertEqual(rc, 0)
        band_labels = {band["label"] for band in
                       self.registry["score_bands"].values()}
        self.assertIn(data["band"], band_labels)

    def test_no_horoscope_or_source_band_in_score_output(self):
        data, rc = run_score(THREE_CLUSTERED)
        self.assertEqual(rc, 0)
        output = json.dumps(data).lower()
        self.assertNotIn("horoscope", output)
        self.assertNotIn("storyscope", output)

    def test_horoscope_stays_an_optional_manual_question(self):
        report = review.review_text(UNSUPPORTED, "argument", self.registry)
        note = report["meta"]["horoscope_test"]
        self.assertIn("manual", note.lower())
        self.assertIn("optional", note.lower())
        self.assertEqual(report["risk"]["score"], 100)
        self.assertNotIn("storyscope", note.lower())

    def test_density_report_marks_risk_advisory(self):
        report = density.analyze_text(THREE_CLUSTERED, self.registry)
        self.assertFalse(report["risk"]["authorship_evidence"])
        self.assertTrue(report["risk"]["advisory"])
        self.assertIn("never", report["meta"]["disclaimer"])

    def test_density_and_precision_never_deduct(self):
        data, rc = run_score(UNSUPPORTED)
        self.assertEqual(rc, 0)
        self.assertEqual(data["score"], 100)
        data, rc = run_score(THREE_CLUSTERED)
        self.assertEqual(rc, 0)
        for finding in data["findings"]:
            if finding["rule_id"] == "struct-passage-density":
                self.assertEqual(finding["weight"], 0)


class TestFixtureSchema(unittest.TestCase):
    """The density-precision fixture schema validates."""

    def setUp(self):
        self.registry = load_registry()

    def test_valid_fixture_has_no_schema_errors(self):
        fixture = {
            "id": "schema-test",
            "medium": "argument",
            "source": UNSUPPORTED,
            "expected_precision_count": 1,
            "expected_decision": "ask-author",
            "false_positive_rationale": "Rationale.",
            "reviewer_notes": "Notes.",
        }
        errors = density.validate_fixture(fixture, set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = density.validate_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        density.validate_fixture({"id": "dup", "source": "Text."}, seen)
        errors = density.validate_fixture({"id": "dup", "source": "Text."},
                                          seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))

    def test_invalid_decision_is_rejected(self):
        errors = density.validate_fixture(
            {"id": "bad", "source": "Text.", "expected_decision": "rewrite"},
            set())
        self.assertTrue(any("expected_decision must be one of" in error
                            for error in errors))

    def test_invalid_medium_is_rejected(self):
        errors = density.validate_fixture(
            {"id": "bad", "source": "Text.", "medium": "essay"}, set())
        self.assertTrue(any("medium must be one of" in error
                            for error in errors))


class TestProductionCorpus(unittest.TestCase):
    """The production density-precision corpus passes end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = density.run_density_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "density-one-legitimate-term",
            "density-two-separated-terms",
            "density-three-clustered-terms",
            "precision-unsupported-exact-statistic",
            "precision-sourced-statistic",
            "precision-supplied-fact",
            "precision-estimated-statistic",
            "precision-technical-constant",
            "rather-than-decorative",
            "rather-than-load-bearing",
            "heading-functional-hierarchy",
            "heading-anomalous-hierarchy",
            "engagement-specific-opening",
            "engagement-generic-opening",
            "trailing-affirmation-cut",
        }
        self.assertEqual(ids & required, required)

    def test_corpus_covers_both_precision_states(self):
        unsourced = {fixture["id"] for fixture in load_fixtures()
                     if fixture.get("expected_unsourced_statistics")}
        exempt = {fixture["id"] for fixture in load_fixtures()
                  if fixture.get("expected_exempt_statistics")}
        self.assertTrue(unsourced)
        self.assertGreaterEqual(len(exempt), 4)

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)

    def test_every_new_rule_names_a_registered_detector(self):
        rules = {rule["id"]: rule for rule in self.registry["rules"]}
        for rid in ("struct-passage-density", "struct-unsourced-precision",
                    "struct-heading-hierarchy", "struct-engagement-bait",
                    "struct-template-headings", "struct-self-promotion",
                    "struct-rather-than"):
            rule = rules[rid]
            self.assertEqual(rule["detection_class"], "structural")
            self.assertEqual(rule["semantic_type"], "discouraged")
            self.assertIn(rule["detector"], density.DETECTORS, rid)


class TestCliInterface(unittest.TestCase):
    """The command accepts stdin, one file, and the fixture corpus."""

    def test_stdin_accepts_input(self):
        import subprocess as sp
        result = sp.run([sys.executable, os.path.join(ROOT, "density.py"),
                         "--profile", "general", "--medium", "argument"],
                        capture_output=True, text=True, cwd=ROOT,
                        input=UNSUPPORTED)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["precision"]["count"], 1)
        self.assertEqual(report["decision"], "ask-author")

    def test_fixture_corpus_exits_zero(self):
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "density.py"), "--fixtures",
             "skills/antislop/evals/density-precision-fixtures.json"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["gate_pass"])

    def test_missing_file_is_a_usage_error(self):
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "density.py"), "--file",
             os.path.join(ROOT, "nope.md")],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()