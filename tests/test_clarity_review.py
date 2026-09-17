#!/usr/bin/env python3
"""Tests for the Clarity-style review runner (issue #96).

Covers:
  - the five review statuses: keep, revise, ask-author, cut, no-finding
  - review never edits and every finding has exactly one explicit status
  - missing author facts, experience, opinion, and motive become targeted
    '[TK: ...]' questions, never invented content
  - mechanism checks distinguish an unsupported significance claim from an
    evidenced consequence
  - medium routing changes structural expectations without weakening
    absolute rules (zero-em-dash in every medium)
  - clean prose produces no-finding; the system never invents work
  - voice samples transfer style only, never personal facts
  - descriptive statistics stay separate from the risk score
  - the mechanism rules register as advisory, zero-weight signals

Run: python3 -m unittest tests/test_clarity_review.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import mechanism  # noqa: E402
import review  # noqa: E402
import structural  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "clarity-review-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
VALIDATE = os.path.join(ROOT, "tools", "validate.py")
SCORE = os.path.join(ROOT, "tools", "score.py")

STATUSES = ("keep", "revise", "ask-author", "cut", "no-finding")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def make_fixture(rid="review-test", **overrides):
    fixture = {
        "id": rid,
        "medium": "argument",
        "source": "This is a clean sentence that needs no changes.",
        "expected_decision": "no-finding",
    }
    fixture.update(overrides)
    return fixture


def run_score(input_text):
    result = subprocess.run([sys.executable, SCORE, "--profile", "general",
                             "--stdin"], capture_output=True, text=True,
                            cwd=ROOT, input=input_text)
    return json.loads(result.stdout), result.returncode


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestFixtureSchema(unittest.TestCase):
    """The review fixture schema validates mediums, statuses, and questions."""

    def setUp(self):
        self.registry = load_registry()

    def test_valid_fixture_has_no_schema_errors(self):
        errors = review.validate_review_fixture(make_fixture(), set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = review.validate_review_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_medium_must_be_one_of_the_seven(self):
        errors = review.validate_review_fixture(
            make_fixture(medium="essay"), set())
        self.assertTrue(any("medium must be one of" in error
                            for error in errors))

    def test_expected_decision_must_be_a_status(self):
        errors = review.validate_review_fixture(
            make_fixture(expected_decision="reject"), set())
        self.assertTrue(any("expected_decision must be one of" in error
                            for error in errors))

    def test_expected_statuses_must_be_statuses(self):
        errors = review.validate_review_fixture(
            make_fixture(expected_statuses={"vocab-delve": "ban"}), set())
        self.assertTrue(any("expected_statuses['vocab-delve']" in error
                            for error in errors))

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        review.validate_review_fixture(make_fixture(), seen)
        errors = review.validate_review_fixture(make_fixture(), seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))


class TestReviewNeverEdits(unittest.TestCase):
    """Review reports on a single artifact and never produces a rewrite."""

    def setUp(self):
        self.registry = load_registry()

    def test_report_marks_edited_false(self):
        report = review.review_text("We delve into the problem.", "argument",
                                    self.registry)
        self.assertFalse(report["edited"])
        self.assertEqual(report["mode"], "review")
        self.assertIn("Report findings without changing the artifact",
                      report["meta"]["authority"])

    def test_review_takes_no_candidate(self):
        signature = review.review_text.__code__.co_varnames
        self.assertNotIn("candidate", signature)


class TestEveryFindingHasOneStatus(unittest.TestCase):
    """Every finding carries exactly one explicit status."""

    def setUp(self):
        self.registry = load_registry()

    def test_all_findings_have_a_valid_status(self):
        report = review.review_text(
            "In today's fast-paced world, it's worth noting that we delve "
            "into the transformative landscape of groundbreaking synergy.",
            "argument", self.registry)
        self.assertGreater(len(report["findings"]), 0)
        for finding in report["findings"]:
            self.assertIn(finding["status"], STATUSES,
                          finding["rule_id"])

    def test_cut_status_for_ceremony(self):
        report = review.review_text(
            "It's worth noting that we finish here. I hope this helps!",
            "argument", self.registry)
        cut = {f["rule_id"] for f in report["findings"]
               if f["status"] == "cut"}
        self.assertIn("phrase-worth-noting", cut)
        self.assertIn("chatbot-hope-helps", cut)

    def test_revise_status_for_banned_vocabulary(self):
        report = review.review_text(
            "We leverage the synergy of the platform.",
            "argument", self.registry)
        revise = {f["rule_id"] for f in report["findings"]
                  if f["status"] == "revise"}
        self.assertIn("vocab-leverage", revise)
        self.assertIn("vocab-synergy", revise)

    def test_quoted_banned_word_is_kept(self):
        report = review.review_text(
            'The review said "delve into the details", and we agreed.',
            "argument", self.registry)
        kept = {f["rule_id"] for f in report["findings"]
                if f["status"] == "keep"}
        self.assertIn("vocab-delve", kept)


class TestAuthorGapsAndTk(unittest.TestCase):
    """Author-owned gaps become targeted questions, never invented content."""

    def setUp(self):
        self.registry = load_registry()

    def test_vague_example_asks_the_author(self):
        report = review.review_text(
            "A package once caused a security problem, and we improved our "
            "process.",
            "argument", self.registry)
        self.assertEqual(report["decision"], "ask-author")
        self.assertTrue(report["author_questions"])
        for item in report["author_questions"]:
            self.assertTrue(item["tk"].startswith("[TK:"))
            self.assertIn("?", item["tk"])

    def test_empty_lesson_asks_the_author(self):
        report = review.review_text(
            "This taught us to prepare better.", "argument", self.registry)
        self.assertEqual(report["decision"], "ask-author")
        self.assertTrue(any("specifically" in item["tk"]
                            for item in report["author_questions"]))

    def test_tk_is_never_filled_with_a_fact(self):
        report = review.review_text(
            "A customer once reported an incident, and we fixed it quickly.",
            "argument", self.registry)
        for finding in report["findings"]:
            if finding["status"] != "ask-author":
                continue
            self.assertTrue(
                finding["suggestion"].startswith("[TK:")
                or "Ask the author" in finding["suggestion"],
                finding["suggestion"])

    def test_clean_prose_produces_no_finding(self):
        report = review.review_text(
            "We switched from VMs to containers three years ago. It cut our "
            "deploy time by 40% and eliminated half our infrastructure "
            "headaches.",
            "argument", self.registry)
        self.assertEqual(report["decision"], "no-finding")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["author_questions"], [])


class TestMechanismChecks(unittest.TestCase):
    """Mechanism checks separate unsupported significance from evidenced
    consequence."""

    def setUp(self):
        self.registry = load_registry()

    def test_importance_without_mechanism_asks_author(self):
        report = review.review_text(
            "This change is crucial for our team.", "argument",
            self.registry)
        self.assertEqual(report["decision"], "ask-author")
        self.assertEqual(report["mechanism_checks"]["unsupported"][0]["rule_id"],
                         "mechanism-importance")

    def test_importance_with_mechanism_is_kept(self):
        report = review.review_text(
            "This change is crucial: it cut deploy time from 40 minutes to "
            "4, and the caching layer did most of the work.",
            "argument", self.registry)
        self.assertEqual(report["decision"], "keep")
        self.assertEqual(report["mechanism_checks"]["evidenced"][0]["rule_id"],
                         "mechanism-importance")

    def test_causality_unsupported_versus_evidenced(self):
        unsupported = review.review_text(
            "Frequent refactoring causes significantly more bugs.",
            "argument", self.registry)
        self.assertEqual(unsupported["decision"], "ask-author")
        evidenced = review.review_text(
            "Frequent refactoring caused 37% more bugs across our "
            "14-service codebase.", "argument", self.registry)
        self.assertEqual(evidenced["decision"], "keep")

    def test_superiority_unsupported_versus_evidenced(self):
        unsupported = review.review_text(
            "Our solution is the best.", "argument", self.registry)
        self.assertEqual(unsupported["decision"], "ask-author")
        evidenced = review.review_text(
            "Our solution ranked best across all 40 runs of the load test.",
            "argument", self.registry)
        self.assertEqual(evidenced["decision"], "keep")

    def test_mechanism_findings_are_advisory_and_zero_weight(self):
        data, rc = run_score("This change is crucial for our team.")
        self.assertEqual(rc, 0)
        self.assertEqual(data["score"], 100)
        mechanism_findings = [f for f in data["findings"]
                              if f["rule_id"] == "mechanism-importance"]
        self.assertEqual(len(mechanism_findings), 1)
        self.assertEqual(mechanism_findings[0]["signal"], "advisory")
        self.assertEqual(mechanism_findings[0]["weight"], 0)


class TestMediumRouting(unittest.TestCase):
    """Medium routing changes structural expectations without weakening
    absolute rules."""

    def setUp(self):
        self.registry = load_registry()

    HEADERS = ("## Retry limits\n\nThe default retry limit is 3.\n\n"
               "## Timeout\n\nThe default timeout is 30 seconds.")

    def test_reference_earns_restated_heading(self):
        report = review.review_text(self.HEADERS, "reference", self.registry)
        fragmented = [f for f in report["findings"]
                      if f["rule_id"] == "struct-fragmented-headers"]
        self.assertTrue(fragmented)
        for finding in fragmented:
            self.assertEqual(finding["status"], "keep")
        self.assertEqual(report["decision"], "keep")

    def test_argument_flags_restated_heading(self):
        report = review.review_text(self.HEADERS, "argument", self.registry)
        fragmented = [f for f in report["findings"]
                      if f["rule_id"] == "struct-fragmented-headers"]
        self.assertTrue(fragmented)
        for finding in fragmented:
            self.assertEqual(finding["status"], "revise")
        self.assertEqual(report["decision"], "revise")

    def test_medium_check_reports_the_expectation(self):
        reference = review.review_text(self.HEADERS, "reference",
                                       self.registry)
        argument = review.review_text(self.HEADERS, "argument", self.registry)
        ref_expectation = next(c for c in reference["medium_checks"]
                               if c["kind"] == "fragmented_headers")
        arg_expectation = next(c for c in argument["medium_checks"]
                               if c["kind"] == "fragmented_headers")
        self.assertEqual(ref_expectation["expectation"], "earned")
        self.assertEqual(arg_expectation["expectation"], "defect")

    def test_evocation_earns_balanced_sentence(self):
        report = review.review_text(
            "At dusk, the blue pigment almost disappears. Step sideways and "
            "the silver ground catches the room's light, returning the river "
            "a piece at a time.", "evocation", self.registry)
        self.assertEqual(report["decision"], "no-finding")

    def test_reference_earns_definitional_contrast(self):
        report = review.review_text(
            "The API is not a database; it is a query layer over the stored "
            "events.", "reference", self.registry)
        self.assertEqual(report["decision"], "no-finding")

    def test_evocation_keeps_significance_language(self):
        report = review.review_text(
            "The pigment's loss is crucial: at dusk it vanishes, and the "
            "silver ground returns the river a piece at a time.",
            "evocation", self.registry)
        self.assertEqual(report["decision"], "keep")

    def test_em_dash_is_absolute_in_every_medium(self):
        for medium in ("argument", "reference", "evocation", "message",
                       "guide"):
            report = review.review_text(
                "The blue pigment almost disappears — the silver ground "
                "catches it.", medium, self.registry)
            self.assertEqual(report["decision"], "revise", medium)
            self.assertTrue(any(f["rule_id"] == "fmt-em-dash"
                                and f["status"] == "revise"
                                for f in report["findings"]))

    def test_banned_vocabulary_is_absolute_in_every_medium(self):
        for medium in ("evocation", "narrative", "reference"):
            report = review.review_text(
                "The landscape of the mind is a tapestry.", medium,
                self.registry)
            self.assertIn("vocab-tapestry",
                          {f["rule_id"] for f in report["findings"]})


class TestVoiceSample(unittest.TestCase):
    """Voice samples transfer style only, never personal facts."""

    SAMPLE = ("I remember the 2021 outage at 2am. We lost the lease and "
              "paid for it.")
    FACTS = ["I remember the 2021 outage", "We lost the lease"]

    def setUp(self):
        self.registry = load_registry()

    def test_sample_without_leak_is_clean(self):
        report = review.review_text(
            "Logs deserve a second read before you trust a deploy. Errors "
            "hide in the tail of the output.",
            "argument", self.registry, voice_sample=self.SAMPLE,
            sample_facts=self.FACTS)
        self.assertEqual(report["voice_sample"]["style_only"], True)
        self.assertEqual(report["voice_sample"]["leaked_personal_facts"], [])
        self.assertEqual(report["decision"], "no-finding")

    def test_sample_leak_is_flagged(self):
        report = review.review_text(
            "Logs deserve a second read. I remember the 2021 outage at 2am, "
            "and we lost the lease.",
            "argument", self.registry, voice_sample=self.SAMPLE,
            sample_facts=self.FACTS)
        self.assertEqual(report["voice_sample"]["leaked_personal_facts"],
                         self.FACTS)
        self.assertEqual(report["decision"], "revise")
        self.assertTrue(any(f["rule_id"] == "evaluation-voice-sample"
                            and f["status"] == "revise"
                            for f in report["findings"]))


class TestStatsSeparateFromRisk(unittest.TestCase):
    """Descriptive statistics never mix with the advisory risk score."""

    def setUp(self):
        self.registry = load_registry()

    def test_report_has_separate_stats_and_risk_blocks(self):
        report = review.review_text(
            "In today's fast-paced world, we delve into the problem.",
            "argument", self.registry)
        self.assertIn("descriptive_stats", report)
        self.assertIn("risk", report)
        stats = report["descriptive_stats"]
        self.assertNotIn("score", stats)
        self.assertNotIn("band", stats)
        self.assertIn("word_count", stats)
        self.assertIn("by_status", stats)
        self.assertIn("advisory", report["risk"])
        self.assertFalse(report["risk"]["authorship_evidence"])

    def test_risk_score_is_never_a_gate(self):
        report = review.review_text(
            "This change is crucial for our team.", "argument", self.registry)
        self.assertEqual(report["decision"], "ask-author")
        self.assertIn("score", report["risk"])


class TestRegistryWiring(unittest.TestCase):
    """The mechanism rules are registered and never skipped."""

    def setUp(self):
        self.registry = load_registry()

    def test_mechanism_rules_register_detectors(self):
        rules = {r["id"]: r for r in self.registry["rules"]}
        for rid in ("mechanism-importance", "mechanism-impact",
                    "mechanism-causality", "mechanism-superiority"):
            rule = rules.get(rid)
            self.assertIsNotNone(rule, rid)
            self.assertEqual(rule["category"], "mechanism")
            self.assertEqual(rule["semantic_type"], "discouraged")
            self.assertEqual(rule["review_mode"], "advisory")
            self.assertIn(rule["detector"], structural.DETECTORS, rid)

    def test_mechanism_detectors_return_findings_with_span_evidence(self):
        rule = {"id": "mechanism-importance", "category": "mechanism",
                "severity": "medium", "base_weight": 4,
                "detection_class": "structural",
                "detector": "mechanism_importance",
                "review_mode": "advisory"}
        result = mechanism.detect_rule(
            "This change is crucial for our team.", rule, "general")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["evidence"], "span")
        self.assertEqual(result["findings"][0]["signal"], "advisory")
        self.assertEqual(result["findings"][0]["sample"]["kind"], "importance")

    def test_evidenced_claim_produces_no_mechanism_finding(self):
        rule = {"id": "mechanism-importance", "category": "mechanism",
                "severity": "medium", "base_weight": 4,
                "detection_class": "structural",
                "detector": "mechanism_importance",
                "review_mode": "advisory"}
        result = mechanism.detect_rule(
            "This change is crucial: it cut deploy time from 40 minutes to "
            "4.", rule, "general")
        self.assertEqual(result["findings"], [])

    def test_registry_mediums_and_statuses_validate(self):
        self.assertEqual(set(self.registry["review_statuses"]),
                         set(STATUSES) | {"n/a", "over-correction"})
        self.assertEqual(set(self.registry["mediums"]),
                         {"argument", "explanation", "evocation", "narrative",
                          "guide", "reference", "message"})


class TestProductionCorpus(unittest.TestCase):
    """The production clarity-review corpus passes end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = review.run_review_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "review-clean-prose-no-finding",
            "review-ask-author-missing-example",
            "review-mechanism-importance-unsupported",
            "review-mechanism-importance-evidenced",
            "review-medium-reference-restated-heading-earned",
            "review-medium-evocation-balanced-sentence-earned",
            "review-voice-sample-style-only",
            "review-tk-never-invented",
        }
        self.assertEqual(ids & required, required)

    def test_fixtures_cover_every_status(self):
        decisions = {fixture["expected_decision"]
                     for fixture in load_fixtures()}
        self.assertEqual(decisions, set(STATUSES))

    def test_fixtures_cover_every_medium(self):
        mediums = {fixture["medium"] for fixture in load_fixtures()}
        self.assertEqual(mediums,
                         {"argument", "explanation", "evocation", "narrative",
                          "guide", "reference", "message"})

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestBoundaries(unittest.TestCase):
    """Review results never claim authorship or detector immunity."""

    def setUp(self):
        self.registry = load_registry()

    def test_every_report_carries_the_disclaimer(self):
        for fixture in load_fixtures():
            report = review.run_review_fixture(fixture, self.registry)
            self.assertIn("never prove", report["meta"]["disclaimer"])
            self.assertFalse(report["risk"]["authorship_evidence"])
            self.assertTrue(report["risk"]["advisory"])

    def test_taste_is_not_a_scored_defect(self):
        data, rc = run_score("This change is crucial for our team.")
        self.assertEqual(rc, 0)
        self.assertEqual(data["score"], 100)


if __name__ == "__main__":
    unittest.main()