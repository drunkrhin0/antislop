#!/usr/bin/env python3
"""Tests for the Slopkit-style semantic drift fixtures (issue #91).

Covers:
  - fixture schema: required facts, forbidden additions, protected spans,
    provenance labels, semantic dimensions, and false-positive rationale
  - the deterministic runner: missing, added, changed, and unresolved items
    are reported separately
  - span stability: declared protected spans and expected finding spans match
    exact character offsets against the input
  - the false-positive corpus: all six categories, leave-alone and light-edit
    actions, and a rationale on every entry
  - review separation: sentence-load, topic-swap, and summary-loss prompts
    stay apart from the Formulaic Writing Risk Score and resolve to a
    human-review result
  - boundaries: results never claim authorship or detector immunity

Run: python3 -m unittest tests/test_drift_fixtures.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import drift  # noqa: E402 -- import after sys.path setup

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "drift-fixtures.json")
FP_CORPUS = os.path.join(ROOT, "skills", "antislop", "evals",
                         "false-positive-corpus.json")
REGISTRY = os.path.join(ROOT, "rules.json")
VALIDATE = os.path.join(ROOT, "validate.py")

FP_CATEGORIES = {"technical_term", "literal_metaphor", "necessary_repetition",
                 "formal_register", "quotation", "author_supplied"}


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def load_fp_corpus():
    with open(FP_CORPUS, encoding="utf-8") as f:
        return json.load(f)["evals"]


def make_fixture(rid="drift-test", **overrides):
    """A schema-valid drift fixture with per-test overrides."""
    fixture = {
        "id": rid,
        "source": "The feature may cause data loss, so test it first.",
        "candidate": "The feature may cause data loss, so test it first.",
        "expected_decision": "accept",
    }
    fixture.update(overrides)
    return fixture


def make_fp_entry(eid="fp-test", **overrides):
    """A schema-valid false-positive entry with per-test overrides."""
    entry = {
        "id": eid,
        "category": "technical_term",
        "source": "The model reports statistical significance.",
        "candidate": "The model reports statistical significance.",
        "expected_action": "leave_alone",
        "why_keep": "Precise domain terms are not targets.",
    }
    entry.update(overrides)
    return entry


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestFixtureSchema(unittest.TestCase):
    """The fixture schema validates the full preservation contract."""

    def setUp(self):
        self.registry = load_registry()

    def test_valid_fixture_has_no_schema_errors(self):
        errors = drift.validate_drift_fixture(make_fixture(), set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = drift.validate_drift_fixture(fixture, seen)
            self.assertEqual(errors, [],
                             f"{fixture['id']}: {errors}")

    def test_requires_source_candidate_and_expected_decision(self):
        errors = drift.validate_drift_fixture(
            make_fixture(source="", candidate="", expected_decision="maybe"),
            set())
        joined = "\n".join(errors)
        for message in ("'source' must be a non-empty string",
                        "'candidate' must be a non-empty string",
                        "expected_decision"):
            self.assertIn(message, joined)

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        drift.validate_drift_fixture(make_fixture(), seen)
        errors = drift.validate_drift_fixture(make_fixture(), seen)
        self.assertTrue(any("duplicate fixture id" in error for error in errors))

    def test_required_facts_must_be_strings(self):
        errors = drift.validate_drift_fixture(
            make_fixture(required_facts=[42]), set())
        self.assertTrue(any("required_facts[0]" in error for error in errors))

    def test_forbidden_additions_must_be_strings(self):
        errors = drift.validate_drift_fixture(
            make_fixture(forbidden_additions=["ok", 42]), set())
        self.assertTrue(any("forbidden_additions[1]" in error
                            for error in errors))

    def test_protected_spans_validate_category_and_offsets(self):
        errors = drift.validate_drift_fixture(
            make_fixture(protected_spans=[
                {"category": "not_a_category", "start": 0, "end": 2},
                {"category": "number", "start": 5, "end": 5},
            ]), set())
        joined = "\n".join(errors)
        self.assertIn("unknown category", joined)
        self.assertIn("start and end ints", joined)

    def test_provenance_labels_are_limited(self):
        errors = drift.validate_drift_fixture(
            make_fixture(provenance=[
                {"text": "something", "label": "bogus"},
            ]), set())
        self.assertTrue(any("label must be one of" in error
                            for error in errors))

    def test_semantic_dimensions_validate_key_and_mode(self):
        errors = drift.validate_drift_fixture(
            make_fixture(semantic_dimensions={
                "not_a_dimension": "preserve",
                "negation": "maybe",
            }), set())
        joined = "\n".join(errors)
        self.assertIn("unknown semantic dimension", joined)
        self.assertIn("must be preserve or refuse", joined)

    def test_expected_findings_validate_target_span_and_risk_class(self):
        errors = drift.validate_drift_fixture(
            make_fixture(expected_findings=[
                {"target": "elsewhere", "rule_id": "x", "span": [1, 1],
                 "risk_class": "banana"},
            ]), set())
        joined = "\n".join(errors)
        self.assertIn("target must be source or candidate", joined)
        self.assertIn("[start, end] int pair", joined)
        self.assertIn("risk_class must be one of", joined)

    def test_false_positive_rationale_when_present_is_non_empty(self):
        errors = drift.validate_drift_fixture(
            make_fixture(false_positive_rationale="  "), set())
        self.assertTrue(any("false_positive_rationale" in error
                            for error in errors))

    def test_review_prompts_are_limited_keys(self):
        errors = drift.validate_drift_fixture(
            make_fixture(review_prompts={"not_a_prompt": "check this"}),
            set())
        self.assertTrue(any("unknown review prompt" in error
                            for error in errors))

    def test_detector_observations_validate_but_never_gate(self):
        errors = drift.validate_drift_fixture(
            make_fixture(detector_observations=[
                {"tool": "example-detector", "date": "2026-09-01",
                 "result": "flagged", "limitation": "advisory"},
                {"tool": "", "date": "", "result": "", "limitation": ""},
            ]), set())
        joined = "\n".join(errors)
        self.assertNotIn("example-detector", joined)
        self.assertIn("detector_observations[1].tool", joined)


class TestFalsePositiveSchema(unittest.TestCase):
    """False-positive corpus entries carry a rationale and valid actions."""

    def test_valid_entry_has_no_schema_errors(self):
        errors = drift.validate_false_positive_entry(make_fp_entry(), set())
        self.assertEqual(errors, [])

    def test_production_corpus_validates(self):
        seen = set()
        for entry in load_fp_corpus():
            errors = drift.validate_false_positive_entry(entry, seen)
            self.assertEqual(errors, [], f"{entry['id']}: {errors}")

    def test_why_keep_rationale_is_required(self):
        errors = drift.validate_false_positive_entry(
            make_fp_entry(why_keep=""), set())
        self.assertTrue(any("'why_keep' must be a non-empty string" in error
                            for error in errors))

    def test_category_must_be_one_of_the_six(self):
        errors = drift.validate_false_positive_entry(
            make_fp_entry(category="wrong"), set())
        self.assertTrue(any("category must be one of" in error
                            for error in errors))

    def test_action_must_be_leave_alone_or_light_copyedit(self):
        errors = drift.validate_false_positive_entry(
            make_fp_entry(expected_action="heavy_rewrite"), set())
        self.assertTrue(any("expected_action" in error for error in errors))


class TestRunnerBuckets(unittest.TestCase):
    """The runner reports missing, added, changed, and unresolved separately."""

    def setUp(self):
        self.registry = load_registry()

    def _run(self, fixture):
        return drift.run_drift_fixture(fixture, self.registry)

    def test_buckets_are_reported_separately(self):
        report = self._run(make_fixture(
            required_facts=["a fact that is absent"],
            forbidden_additions=["seamless"],
            required_terms=["lease"],
            provenance=[{"text": "a fact that is absent",
                         "label": "unknown"}],
            source=("The system may hold a lease, so test it first. "
                    "The source of the trend is not yet identified."),
            candidate=("The system may hold a lease, so test it first. "
                       "The source of the trend is not yet identified, "
                       "and seamless is now guaranteed."),
            expected_decision="reject",
        ))
        self.assertTrue(any(i["kind"] == "required_fact"
                            for i in report["items"]["missing"]))
        self.assertTrue(any(i["kind"] == "forbidden_addition"
                            for i in report["items"]["added"]))
        self.assertTrue(report["items"]["unresolved"])
        self.assertEqual(report["decision"], "reject")
        for bucket in ("missing", "added", "changed", "unresolved"):
            self.assertIn(bucket, report["items"])

    def test_unchanged_preserved_source_is_accepted(self):
        report = self._run(make_fixture(
            required_facts=["the queue worker lost its lease"],
            source=("The incident happened because the queue worker lost "
                    "its lease."),
            candidate=("The incident happened because the queue worker lost "
                       "its lease."),
        ))
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["items"]["missing"], [])
        self.assertEqual(report["items"]["changed"], [])

    def test_negation_reversal_is_rejected(self):
        report = self._run(make_fixture(
            source="The access token is not required for read-only API calls.",
            candidate="The access token is required for read-only API calls.",
            semantic_dimensions={"negation": "preserve"},
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(i["kind"] == "semantic_anchor_removed"
                            for i in report["items"]["changed"]))
        self.assertEqual(report["semantic_dimensions"]["verdicts"]
                         ["negation"], "missing_group")

    def test_obligation_strengthening_is_rejected(self):
        report = self._run(make_fixture(
            source="Contractors may request read-only access to staging.",
            candidate="Contractors must request read-only access to staging.",
            semantic_dimensions={"obligation": "preserve"},
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["semantic_dimensions"]["verdicts"]
                         ["obligation"], "changed_terms")
        self.assertEqual(report["semantic_dimensions"]["changed_groups"]
                         ["obligation"]["missing_terms"], ["may"])

    def test_scope_expansion_is_rejected(self):
        report = self._run(make_fixture(
            source="Contractors have read-only access to the staging "
                   "environment.",
            candidate="Contractors have full access to the staging "
                      "environment.",
            semantic_dimensions={"scope": "preserve"},
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["semantic_dimensions"]["verdicts"]["scope"],
                         "changed_terms")

    def test_condition_removal_is_rejected(self):
        report = self._run(make_fixture(
            source="Access expires after 24 hours if the incident remains "
                   "open.",
            candidate="Access expires after 24 hours.",
            semantic_dimensions={"temporal_condition": "preserve"},
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["semantic_dimensions"]["verdicts"]
                         ["temporal_condition"], "changed_terms")

    def test_causal_strengthening_is_rejected(self):
        report = self._run(make_fixture(
            source="The delay was probably caused by the lease loss.",
            candidate="The delay was caused by the lease loss.",
            semantic_dimensions={"causality": "preserve",
                                 "uncertainty": "preserve"},
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["semantic_dimensions"]["verdicts"]
                         ["uncertainty"], "missing_group")

    def test_uncertainty_removal_is_rejected(self):
        report = self._run(make_fixture(
            source="The feature may cause data loss, so test it first.",
            candidate="The feature causes data loss, so test it first.",
            semantic_dimensions={"uncertainty": "preserve"},
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["semantic_dimensions"]["verdicts"]
                         ["uncertainty"], "missing_group")

    def test_promise_inflation_is_rejected(self):
        report = self._run(make_fixture(
            source="The tool helps reduce deployment time.",
            candidate="The tool guarantees a seamless deployment every time.",
            semantic_dimensions={"promise_intensity": "refuse"},
            forbidden_additions=["guarantees a seamless deployment"],
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["semantic_dimensions"]["verdicts"]
                         ["promise_intensity"], "added_group")
        self.assertEqual(report["forbidden_additions"],
                         ["guarantees a seamless deployment"])


class TestProvenance(unittest.TestCase):
    """Provenance labels survive the rewrite or stay unresolved."""

    def setUp(self):
        self.registry = load_registry()

    def _run(self, fixture):
        return drift.run_drift_fixture(fixture, self.registry)

    def test_fact_retained_as_fact_is_accepted(self):
        report = self._run(make_fixture(
            provenance=[{"text": "The report covers the 2026 threat "
                                "landscape", "label": "fact"}],
            source=("The report covers the 2026 threat landscape and the "
                    "Q1 rollout."),
            candidate=("The report covers the 2026 threat landscape and the "
                       "Q1 rollout."),
        ))
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["provenance"]["items"]["fact"][0]["state"],
                         "kept")

    def test_missing_fact_is_rejected(self):
        report = self._run(make_fixture(
            provenance=[{"text": "The report covers the 2026 threat "
                                "landscape", "label": "fact"}],
            source=("The report covers the 2026 threat landscape and the "
                    "Q1 rollout."),
            candidate="The report covers the Q1 rollout.",
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(i["kind"] == "provenance_fact"
                            for i in report["items"]["missing"]))

    def test_inference_retained_as_inference_is_accepted(self):
        report = self._run(make_fixture(
            provenance=[{"text": "phishing is rising among finance teams",
                         "label": "inference", "hedge": "suggest"}],
            source=("The findings suggest phishing is rising among finance "
                    "teams."),
            candidate=("The findings suggest phishing is rising among finance "
                       "teams."),
        ))
        self.assertEqual(report["decision"], "accept")
        state = report["provenance"]["items"]["inference"][0]["state"]
        self.assertEqual(state, "kept")

    def test_inference_with_dropped_hedge_is_rejected(self):
        report = self._run(make_fixture(
            provenance=[{"text": "phishing is rising among finance teams",
                         "label": "inference", "hedge": "suggest"}],
            source=("The findings suggest phishing is rising among finance "
                    "teams."),
            candidate="Phishing is rising among finance teams.",
            expected_decision="reject",
        ))
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["provenance"]["items"]["inference"][0]
                         ["state"], "hedge_dropped")

    def test_unknown_left_unresolved_reports_an_unresolved_item(self):
        report = self._run(make_fixture(
            provenance=[{"text": "the source of those numbers is not yet "
                                "identified", "label": "unknown"}],
            source=("Plans call for a dashboard to surface adoption trends, "
                    "though the source of those numbers is not yet "
                    "identified."),
            candidate=("Plans call for a dashboard to surface adoption "
                       "trends, though the source of those numbers is not "
                       "yet identified."),
        ))
        self.assertEqual(report["decision"], "accept")
        self.assertTrue(report["items"]["unresolved"])
        self.assertEqual(report["items"]["unresolved"][0]["label"], "unknown")


class TestSpanStability(unittest.TestCase):
    """Exact expected spans are stable against the input's character offsets."""

    def setUp(self):
        self.registry = load_registry()

    def test_declared_protected_span_offsets_match_the_extractor(self):
        source = "Access expires after 24 hours if the incident remains open."
        fixture = make_fixture(
            source=source,
            candidate="Access expires after 24 hours.",
            protected_spans=[{"category": "number", "start": 21, "end": 23}],
            semantic_dimensions={"temporal_condition": "preserve"},
            expected_decision="reject",
        )
        report = drift.run_drift_fixture(fixture, self.registry)
        self.assertEqual(report["protected_spans"]["offset_drift"], [])
        extracted = [s for s in
                     drift.fidelity.extract_anchors(source, ())["protected_spans"]
                     if s["category"] == "number"]
        self.assertEqual(extracted[0]["start"], 21)
        self.assertEqual(extracted[0]["end"], 23)
        self.assertEqual(source[21:23], "24")

    def test_stale_protected_span_offsets_are_rejected(self):
        fixture = make_fixture(
            source="Access expires after 24 hours.",
            candidate="Access expires after 24 hours.",
            protected_spans=[{"category": "number", "start": 3, "end": 4}],
            expected_decision="reject",
        )
        report = drift.run_drift_fixture(fixture, self.registry)
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["protected_spans"]["offset_drift"][0]
                         ["category"], "number")

    def test_expected_finding_span_is_exact(self):
        fixture = make_fixture(
            source=("We delve into the incident because the queue worker "
                    "lost its lease."),
            candidate=("The incident happened because the queue worker lost "
                       "its lease."),
            expected_findings=[
                {"target": "source", "rule_id": "vocab-delve",
                 "span": [3, 8], "risk_class": "forbidden"},
            ],
            absent_findings=[
                {"target": "candidate", "rule_id": "vocab-delve"},
            ],
        )
        report = drift.run_drift_fixture(fixture, self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["findings"]["mismatches"], [])

    def test_mismatched_finding_span_is_rejected(self):
        fixture = make_fixture(
            source="We delve into the incident.",
            candidate="We delve into the incident.",
            expected_findings=[
                {"target": "source", "rule_id": "vocab-delve",
                 "span": [9, 14], "risk_class": "forbidden"},
            ],
            expected_decision="reject",
        )
        report = drift.run_drift_fixture(fixture, self.registry)
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["findings"]["mismatches"][0]["kind"],
                         "expected_finding_missing")

    def test_absent_finding_that_fires_is_rejected(self):
        fixture = make_fixture(
            source="The incident happened because the queue worker lost "
                   "its lease.",
            candidate="We delve into the incident because the queue worker "
                      "lost its lease.",
            absent_findings=[
                {"target": "candidate", "rule_id": "vocab-delve"},
            ],
            expected_decision="reject",
        )
        report = drift.run_drift_fixture(fixture, self.registry)
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["findings"]["mismatches"][0]["kind"],
                         "absent_finding_present")


class TestRiskSeparation(unittest.TestCase):
    """A candidate cannot pass on a lower risk score, and review stays apart."""

    def setUp(self):
        self.registry = load_registry()

    def test_concise_rewrite_fails_despite_lower_risk(self):
        fixture = make_fixture(
            source=("We delve into the failure because the queue worker "
                    "lost its lease."),
            candidate="The team investigated the failure.",
            required_facts=["the queue worker lost its lease"],
            semantic_dimensions={"causality": "preserve"},
            expected_decision="reject",
        )
        report = drift.run_drift_fixture(fixture, self.registry)
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(report["risk"]["improved"])
        self.assertGreater(report["risk"]["candidate_score"],
                           report["risk"]["source_score"])

    def test_correct_rewrite_that_removes_a_formula_is_accepted(self):
        fixture = make_fixture(
            source=("We delve into the incident because the queue worker "
                    "lost its lease, and only three merchants were "
                    "affected."),
            candidate=("The incident happened because the queue worker lost "
                       "its lease, and only three merchants were affected."),
            required_facts=["the queue worker lost its lease",
                            "only three merchants were affected"],
            required_terms=["lease"],
            semantic_dimensions={"causality": "preserve",
                                 "scope": "preserve"},
            expected_findings=[
                {"target": "source", "rule_id": "vocab-delve",
                 "span": [3, 8], "risk_class": "forbidden"},
            ],
            absent_findings=[
                {"target": "candidate", "rule_id": "vocab-delve"},
            ],
        )
        report = drift.run_drift_fixture(fixture, self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertTrue(report["risk"]["improved"])

    def test_review_prompts_stay_separate_from_the_risk_score(self):
        fixture = make_fixture(
            source=("We delve into the incident because the queue worker "
                    "lost its lease, and only three merchants were "
                    "affected."),
            candidate=("The incident happened because the queue worker lost "
                       "its lease, and only three merchants were affected."),
            review_prompts={
                "sentence_load": "Check no sentence was dropped.",
                "topic_swap": "Check the topic is unchanged.",
                "summary_loss": "Check the mechanism and scope survive.",
            },
            expected_decision="review",
        )
        report = drift.run_drift_fixture(fixture, self.registry)
        self.assertEqual(report["decision"], "review")
        self.assertEqual(report["review"]["status"], "unresolved")
        keys = {item["kind"] for item in report["review"]["items"]}
        self.assertEqual(keys, {"sentence_load", "topic_swap", "summary_loss"})
        self.assertIsNotNone(report["risk"]["source_score"])
        self.assertIsNotNone(report["risk"]["candidate_score"])

    def test_detector_observations_never_change_the_decision(self):
        base = make_fixture(
            source="The feature may cause data loss.",
            candidate="The feature may cause data loss.",
            detector_observations=[
                {"tool": "example-detector", "date": "2026-09-01",
                 "result": "flagged as human", "limitation": "advisory"},
            ],
        )
        without_observations = drift.run_drift_fixture(base, self.registry)
        with_observations = drift.run_drift_fixture(
            dict(base, detector_observations=[
                {"tool": "example-detector", "date": "2026-09-01",
                 "result": "flagged as AI", "limitation": "advisory"},
            ]), self.registry)
        self.assertEqual(with_observations["decision"],
                         without_observations["decision"])
        self.assertEqual(with_observations["risk"]["source_score"],
                         without_observations["risk"]["source_score"])
        self.assertEqual(with_observations["meta"]["detector_observations"][0]
                         ["result"], "flagged as AI")


class TestAuthorshipBoundaries(unittest.TestCase):
    """Evaluation results never claim authorship or detector immunity."""

    def setUp(self):
        self.registry = load_registry()

    def test_every_report_carries_the_disclaimer(self):
        for fixture in load_fixtures():
            report = drift.run_drift_fixture(fixture, self.registry)
            self.assertIn("never prove", report["meta"]["disclaimer"])
            self.assertFalse(report["risk"]["authorship_evidence"])
            self.assertTrue(report["risk"]["advisory"])

    def test_false_positive_entries_carry_the_disclaimer(self):
        for entry in load_fp_corpus():
            report = drift.run_false_positive_entry(entry, self.registry)
            self.assertIn("never prove", report["meta"]["disclaimer"])
            self.assertFalse(report["risk"]["authorship_evidence"])

    def test_corpus_report_carries_the_disclaimer(self):
        report = drift.run_drift_corpus(load_fixtures(), self.registry)
        self.assertIn("never prove", report["disclaimer"])


class TestFalsePositiveCorpus(unittest.TestCase):
    """The compact false-positive corpus covers all six categories."""

    def setUp(self):
        self.registry = load_registry()

    def test_production_corpus_passes(self):
        report = drift.run_false_positive_corpus(load_fp_corpus(),
                                                 self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["corpus_failures"], [])
        self.assertEqual(report["failed"], 0)

    def test_all_six_categories_are_covered(self):
        entries = load_fp_corpus()
        categories = {entry["category"] for entry in entries}
        self.assertEqual(categories, FP_CATEGORIES)

    def test_both_actions_are_represented(self):
        entries = load_fp_corpus()
        actions = {entry["expected_action"] for entry in entries}
        self.assertEqual(actions, {"leave_alone", "light_copyedit"})

    def test_leave_alone_entries_are_unchanged(self):
        for entry in load_fp_corpus():
            if entry["expected_action"] != "leave_alone":
                continue
            report = drift.run_false_positive_entry(entry, self.registry)
            self.assertTrue(report["passed"], f"{entry['id']}: "
                            f"{report['failures']}")
            self.assertEqual(entry["source"], entry["candidate"])

    def test_light_copyedit_entries_do_not_grow_past_the_bound(self):
        for entry in load_fp_corpus():
            if entry["expected_action"] != "light_copyedit":
                continue
            report = drift.run_false_positive_entry(entry, self.registry)
            self.assertTrue(report["passed"], f"{entry['id']}: "
                            f"{report['failures']}")
            self.assertLessEqual(report["growth_ratio"], 1.15)

    def test_technical_term_that_resembles_a_banned_word_remains(self):
        entries = {entry["id"]: entry for entry in load_fp_corpus()}
        entry = entries["fp-technical-term"]
        report = drift.run_false_positive_entry(entry, self.registry)
        self.assertTrue(report["passed"])
        self.assertEqual(entry["source"], entry["candidate"])
        self.assertIn("financial leverage ratio", entry["candidate"])
        self.assertIn("statistical significance", entry["candidate"])

    def test_quotation_is_not_a_target(self):
        entries = {entry["id"]: entry for entry in load_fp_corpus()}
        entry = entries["fp-quotation"]
        report = drift.run_false_positive_entry(entry, self.registry)
        self.assertTrue(report["passed"])
        self.assertIn("reported speech", report["why_keep"].lower())

    def test_necessary_repetition_is_not_corrected(self):
        entries = {entry["id"]: entry for entry in load_fp_corpus()}
        entry = entries["fp-necessary-repetition"]
        report = drift.run_false_positive_entry(entry, self.registry)
        self.assertTrue(report["passed"])
        self.assertEqual(entry["source"].lower().count("fail closed"), 2)
        self.assertIn("repeating the boundary", report["why_keep"].lower())


class TestProductionCorpora(unittest.TestCase):
    """Both production corpora pass end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_drift_fixture_corpus_passes(self):
        report = drift.run_drift_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["fixture_count"], 16)

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "drift-negation-reversal", "drift-obligation-strengthening",
            "drift-scope-expansion", "drift-condition-removal",
            "drift-causal-strengthening", "drift-uncertainty-removal",
            "drift-promise-inflation", "drift-provenance-fact",
            "drift-provenance-inference", "drift-provenance-unknown-unresolved",
            "drift-technical-term-resembling-banned-word",
            "drift-necessary-repetition-kept",
            "drift-concise-rewrite-loses-mechanism",
            "drift-correct-rewrite-removes-formula",
            "drift-review-summary-loss",
        }
        self.assertEqual(ids & required, required)

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


if __name__ == "__main__":
    unittest.main()