#!/usr/bin/env python3
"""Tests for the labeled calibration harness (issue #89).

Covers:
  - fixture schema: profile, genre, locale, source, and label provenance are
    required; expected findings, clean spans, preservation obligations, and
    forbidden additions validate
  - experiment config: explicit score direction, non-empty holdout set, and
    the frozen fixture revision hash are required
  - metrics: per-category recall, false-positive rate, exact-span agreement,
    mean absolute error, rank correlation, score delta, and score stability
  - missing labels stay missing and never become zero
  - baseline versus candidate: a candidate with better aggregate recall but
    worse technical false positives surfaces per-category, and the gate fails
    on configured false-positive, recall, or preservation regressions
  - determinism: repeated runs produce byte-identical reports

Run: python3 -m unittest tests/test_calibration.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import calibration  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "calibration-fixtures.json")
CONFIG = os.path.join(ROOT, "skills", "antislop", "evals",
                      "calibration-experiment.json")
REGISTRY = os.path.join(ROOT, "rules.json")
VALIDATE = os.path.join(ROOT, "tools", "validate.py")
CALIBRATION = os.path.join(ROOT, "tools", "calibration.py")

PROBE_TEXT = "We leverage the API for the rollout."


class TestBoundedCalibrationInputs(unittest.TestCase):
    def test_oversized_experiment_config_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "oversized.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"padding": "x" * 1_000_001}, handle)
            result = subprocess.run(
                [sys.executable, CALIBRATION, "--experiment-config", path],
                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("exceeds", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_non_object_experiment_config_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "array.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump([], handle)
            result = subprocess.run(
                [sys.executable, CALIBRATION, "--experiment-config", path],
                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be a JSON object", result.stdout)
        self.assertNotIn("Traceback", result.stderr)


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def make_fixture(fid="cal-test", **overrides):
    """A schema-valid detection fixture with per-test overrides."""
    fixture = {
        "id": fid,
        "profile": "general",
        "genre": "argument",
        "locale": "en-US",
        "source": "test fixture",
        "label_provenance": "test-hand-labeled",
        "holdout": False,
        "text": "We leverage the API for the rollout.",
        "expected_findings": [
            {"target": "text", "rule_id": "vocab-leverage",
             "category": "vocabulary", "span": [3, 11]},
        ],
    }
    fixture.update(overrides)
    return fixture


def make_config(**overrides):
    """A schema-valid experiment config with per-test overrides."""
    config = {
        "schema": "calibration-experiment-1",
        "fixture_revision": "calibration-test-1",
        "score_direction": "higher_is_better",
        "baseline": {"name": "base", "kind": "antislop-score",
                     "registry": "rules.json", "categories": None},
        "candidate": {"name": "candidate", "kind": "antislop-score",
                      "registry": "rules.json", "categories": None},
        "holdout_ids": ["cal-holdout"],
        "fail_on_false_positive_regression": False,
        "fail_on_recall_regression": False,
        "fail_on_preservation_regression": False,
        "max_false_positive_rate": None,
        "max_preservation_failures": None,
        "max_recall_regression": None,
        "max_mae": None,
    }
    config.update(overrides)
    return config


def run_experiment(fixtures, config, baseline=None, candidate=None):
    """Run a full experiment with the reference implementations by default."""
    if baseline is None:
        baseline = calibration.antislop_implementation("base", REGISTRY)
    if candidate is None:
        candidate = calibration.antislop_implementation("candidate", REGISTRY)
    return calibration.run_experiment(fixtures, baseline, candidate, config,
                                      registry_path=REGISTRY)


def single_run(fixture, baseline=None, candidate=None, **config_overrides):
    """Run one fixture as its own holdout so no shared holdout id is needed."""
    fixture = json.loads(json.dumps(fixture))
    fixture["holdout"] = True
    config = make_config(holdout_ids=[])
    config.update(config_overrides)
    return run_experiment([fixture], config, baseline, candidate)


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


def run_calibration_cli(*args):
    result = subprocess.run([sys.executable, CALIBRATION] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout, result.stderr


def stub_impl(name, fire_structural=False, fire_clean_spans=False,
              fire_banned=True):
    """A deterministic stub scorer for fail-on-regression tests.

    fire_banned finds labeled vocabulary findings. fire_structural finds the
    passive-density structural finding. fire_clean_spans fires a structural-
    category finding inside clean spans, the worse-technical-false-positives
    behavior.
    """
    def impl(text, profile):
        findings = []
        low = text.lower()
        if fire_banned:
            if "leverage" in low:
                idx = low.find("leverage")
                findings.append({
                    "rule_id": "vocab-leverage", "category": "vocabulary",
                    "severity": "high", "base_weight": 8, "signal": "strict",
                    "primary": True, "span": [idx, idx + 8]})
        if fire_structural and "deployed" in low:
            findings.append({
                "rule_id": "struct-passive-density", "category": "structural",
                "severity": "medium", "base_weight": 4, "signal": "strict",
                "primary": True, "span": [0, len(text)]})
        if fire_clean_spans and "significance" in low:
            idx = low.find("significance")
            findings.append({
                "rule_id": "struct-clean-hit", "category": "structural",
                "severity": "medium", "base_weight": 4, "signal": "advisory",
                "primary": True, "span": [max(0, idx - 4), idx + 13]})
        score = max(0, 100 - 8 * len([f for f in findings
                                      if f["signal"] == "strict"]))
        return {"name": name, "version": "stub", "score": score,
                "findings": findings}
    impl.name = name
    return impl


PASSIVE_TEXT = ("The fix was deployed by the team. The incident was logged "
                "by the operator. The root cause was identified by the "
                "engineer. The patch was tested by the QA lead. The rollout "
                "was approved by the manager. The data was verified by the "
                "analyst. The result was confirmed by the vendor.")

REG_TEST_FIXTURES = [
    {
        "id": "f-vocab",
        "profile": "general", "genre": "argument", "locale": "en-US",
        "source": "test fixture", "label_provenance": "test-hand-labeled",
        "holdout": False,
        "text": "We leverage the API.",
        "expected_findings": [
            {"target": "text", "rule_id": "vocab-leverage",
             "category": "vocabulary", "span": [3, 11]},
        ],
    },
    {
        "id": "f-structural",
        "profile": "general", "genre": "narrative", "locale": "en-US",
        "source": "test fixture", "label_provenance": "test-hand-labeled",
        "holdout": False,
        "text": PASSIVE_TEXT,
        "expected_findings": [
            {"target": "text", "rule_id": "struct-passive-density",
             "category": "structural", "span": [0, len(PASSIVE_TEXT)]},
        ],
    },
    {
        "id": "f-clean",
        "profile": "general", "genre": "argument", "locale": "en-US",
        "source": "test fixture", "label_provenance": "test-hand-labeled",
        "holdout": False,
        "text": "The statistical significance threshold is 0.05.",
        "clean_spans": [
            {"target": "text", "span": [4, 55], "category": "structural",
             "note": "technical term that must not fire"},
        ],
    },
    {
        "id": "cal-holdout",
        "profile": "general", "genre": "guide", "locale": "en-US",
        "source": "test fixture", "label_provenance": "test-hand-labeled",
        "holdout": True,
        "source_text": "The queue worker lost its lease, and the fix is "
                       "robust in about 40 ms.",
        "candidate_text": "The queue worker lost its lease, and the fix is "
                          "reliable in 40 ms.",
        "preservation": [{"kind": "term", "value": "about"}],
    },
]


class TestFixtureSchema(unittest.TestCase):
    """The fixture schema requires provenance and validates the four labels."""

    def test_valid_fixture_has_no_schema_errors(self):
        errors = calibration.validate_calibration_fixture(make_fixture(), set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = calibration.validate_calibration_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_provenance_fields_are_required(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(profile="essay", genre="", locale="", source="",
                         label_provenance=""), set())
        joined = "\n".join(errors)
        for message in ("profile must be one of", "genre must be one of",
                        "'locale' must be a non-empty string",
                        "'source' must be a non-empty string",
                        "label_provenance"):
            self.assertIn(message, joined)

    def test_requires_text_or_source_candidate_pair(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(text=""), set())
        self.assertTrue(any("needs 'text' or a 'source_text'" in error
                            for error in errors))

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        calibration.validate_calibration_fixture(make_fixture(), seen)
        errors = calibration.validate_calibration_fixture(make_fixture(), seen)
        self.assertTrue(any("duplicate fixture id" in error for error in errors))

    def test_expected_findings_validate_target_rule_category_and_span(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(expected_findings=[
                {"target": "elsewhere", "rule_id": "", "category": "",
                 "span": [1, 1]},
            ]), set())
        joined = "\n".join(errors)
        self.assertIn("target must be one of", joined)
        self.assertIn("needs a non-empty 'rule_id'", joined)
        self.assertIn("needs a non-empty 'category'", joined)
        self.assertIn("[start, end] int pair", joined)

    def test_clean_spans_validate_target_span_note_and_optional_category(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(clean_spans=[
                {"target": "text", "span": [5, 2], "note": ""},
                {"target": "text", "span": [0, 3], "note": "ok",
                 "category": 42},
            ]), set())
        joined = "\n".join(errors)
        self.assertIn("clean_spans[0].span", joined)
        self.assertIn("clean_spans[0] needs a non-empty 'note'", joined)
        self.assertIn("clean_spans[1].category", joined)

    def test_ranked_findings_validate(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(ranked_findings=[
                {"target": "elsewhere", "rule_id": ""},
            ]), set())
        joined = "\n".join(errors)
        self.assertIn("ranked_findings[0].target", joined)
        self.assertIn("ranked_findings[0] needs a non-empty 'rule_id'", joined)

    def test_score_target_validate(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(score_target={"target": "text", "value": "high",
                                       "label_provenance": ""}), set())
        joined = "\n".join(errors)
        self.assertIn("score_target.value must be a number", joined)
        self.assertIn("score_target.label_provenance", joined)

    def test_preservation_obligations_validate_kind_and_value(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(preservation=[{"kind": "span", "value": ""}]),
            set())
        joined = "\n".join(errors)
        self.assertIn("preservation[0].kind must be one of", joined)
        self.assertIn("preservation[0] needs a non-empty 'value'", joined)

    def test_forbidden_additions_must_be_strings(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(forbidden_additions=["ok", 42]), set())
        self.assertTrue(any("forbidden_additions[1]" in error
                            for error in errors))

    def test_detection_fixture_targets_must_be_text(self):
        errors = calibration.validate_calibration_fixture(
            make_fixture(expected_findings=[
                {"target": "candidate", "rule_id": "vocab-leverage",
                 "category": "vocabulary", "span": [3, 11]},
            ], clean_spans=[
                {"target": "source", "span": [0, 3], "note": "must not fire"},
            ]), set())
        joined = "\n".join(errors)
        self.assertIn("expected_findings[0].target must be one of text", joined)
        self.assertIn("clean_spans[0].target must be one of text", joined)

    def test_rewrite_fixture_allows_source_and_candidate_targets(self):
        fixture = make_fixture(
            source_text="The fix is robust in about 40 ms.",
            candidate_text="The fix is reliable in 40 ms.",
            expected_findings=[
                {"target": "source", "rule_id": "vocab-robust",
                 "category": "vocabulary", "span": [12, 18]},
            ])
        errors = calibration.validate_calibration_fixture(fixture, set())
        self.assertEqual(errors, [])


class TestExperimentConfig(unittest.TestCase):
    """The experiment requires a holdout set, direction, and frozen hash."""

    def test_valid_config_has_no_schema_errors(self):
        errors = calibration.validate_experiment_config(make_config())
        self.assertEqual(errors, [])

    def test_production_config_validates(self):
        errors = calibration.validate_experiment_config(load_config())
        self.assertEqual(errors, [])

    def test_score_direction_is_required_and_limited(self):
        errors = calibration.validate_experiment_config(
            make_config(score_direction="sideways"))
        self.assertTrue(any("score_direction" in error for error in errors))

    def test_holdout_set_is_required(self):
        fixtures = json.loads(json.dumps(REG_TEST_FIXTURES))
        for fixture in fixtures:
            fixture["holdout"] = False
        config = make_config(holdout_ids=[])
        with self.assertRaises(ValueError) as ctx:
            run_experiment(fixtures, config)
        self.assertIn("non-empty holdout set", str(ctx.exception))

    def test_unknown_holdout_ids_are_rejected(self):
        fixtures = json.loads(json.dumps(REG_TEST_FIXTURES))
        config = make_config(holdout_ids=["not-a-fixture"])
        with self.assertRaises(ValueError) as ctx:
            run_experiment(fixtures, config)
        self.assertIn("unknown fixtures", str(ctx.exception))

    def test_fixture_revision_hash_is_frozen(self):
        fixtures = json.loads(json.dumps(REG_TEST_FIXTURES))
        fixtures[0]["genre"] = "guide"
        config = make_config(expected_fixture_hash="0" * 64)
        with self.assertRaises(ValueError) as ctx:
            run_experiment(fixtures, config)
        self.assertIn("fixture revision changed", str(ctx.exception))

    def test_holdout_fixtures_are_never_used_to_tune_thresholds(self):
        config = make_config()
        fixtures = json.loads(json.dumps(REG_TEST_FIXTURES))
        report = run_experiment(fixtures, config)
        self.assertFalse(report["holdout_used_for_tuning"])
        self.assertEqual(report["holdout_ids"], ["cal-holdout"])


class TestRecallAndExactSpan(unittest.TestCase):
    """Recall, exact-span agreement, and per-category pooling."""

    def setUp(self):
        self.report = run_experiment(REG_TEST_FIXTURES, make_config())
        self.aggregate = self.report["aggregate"]["baseline"]

    def test_overall_recall_pools_found_over_expected(self):
        bucket = self.aggregate["recall"]["overall"]
        self.assertEqual(bucket["state"], "ok")
        self.assertEqual(bucket["found"], 2)
        self.assertEqual(bucket["expected"], 2)
        self.assertEqual(bucket["rate"], 1.0)

    def test_per_category_recall_is_reported(self):
        by_category = self.aggregate["recall"]["by_category"]
        self.assertEqual(by_category["vocabulary"]["rate"], 1.0)
        self.assertEqual(by_category["structural"]["rate"], 1.0)

    def test_exact_span_agreement_counts_only_exact_matches(self):
        bucket = self.aggregate["exact_span_agreement"]
        self.assertEqual(bucket["exact"], 2)
        self.assertEqual(bucket["expected"], 2)
        self.assertEqual(bucket["rate"], 1.0)

    def test_wrong_span_counts_as_found_but_not_exact(self):
        fixture = make_fixture(
            expected_findings=[
                {"target": "text", "rule_id": "vocab-leverage",
                 "category": "vocabulary", "span": [9, 11]},
            ])
        report = single_run(fixture)
        entry = report["fixtures"][0]
        self.assertEqual(entry["baseline"]["recall"]["found"], 1)
        self.assertEqual(entry["baseline"]["exact_span_agreement"]["exact"], 0)
        label = entry["baseline"]["label_results"][0]
        self.assertTrue(label["found"])
        self.assertFalse(label["exact"])


class TestMissingLabelsStayMissing(unittest.TestCase):
    """Unlabeled categories report an explicit unknown state, never zero."""

    def test_unlabeled_category_recall_is_null_not_zero(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        by_category = report["aggregate"]["baseline"]["recall"]["by_category"]
        for category in ("filler", "formatting", "integrity", "preferred",
                         "evaluation"):
            bucket = by_category[category]
            self.assertEqual(bucket["state"], "unlabeled")
            self.assertIsNone(bucket["rate"])
            self.assertEqual(bucket["found"], 0)

    def test_unlabeled_finding_inside_a_fixture_stays_unknown(self):
        fixture = make_fixture(
            text="Great question! The fix is ready.",
            expected_findings=[
                {"target": "text", "rule_id": "chatbot-great-question",
                 "category": "chatbot", "span": [0, 15]},
            ],
            clean_spans=[
                {"target": "text", "span": [16, 33],
                 "note": "clean prose; the phrase finding beside it is "
                         "unlabeled"},
            ])
        report = single_run(fixture)
        entry = report["fixtures"][0]
        labels = entry["baseline"]["label_results"]
        self.assertEqual(len(labels), 1)
        self.assertTrue(labels[0]["found"])
        phrase_findings = [f for f in entry["baseline"]["label_results"]
                           if f["rule_id"] != "chatbot-great-question"]
        self.assertEqual(phrase_findings, [])
        self.assertEqual(entry["baseline"]["false_positives"]["spans_hit"], 0)


class TestFalsePositives(unittest.TestCase):
    """Clean spans drive the false-positive rate by labeled category."""

    def test_clean_span_without_findings_has_zero_fp_rate(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        bucket = report["aggregate"]["baseline"]["false_positive_rate"]["overall"]
        self.assertEqual(bucket["clean_spans"], 1)
        self.assertEqual(bucket["spans_hit"], 0)
        self.assertEqual(bucket["rate"], 0.0)

    def test_finding_in_clean_span_counts_as_false_positive(self):
        fixture = make_fixture(
            text="The statistical significance threshold is 0.05.",
            clean_spans=[
                {"target": "text", "span": [4, 55], "category": "structural",
                 "note": "must not fire"},
            ])
        baseline = calibration.antislop_implementation("base", REGISTRY)
        candidate = stub_impl("sloppy", fire_clean_spans=True)
        report = single_run(fixture, baseline=baseline, candidate=candidate)
        fp = report["aggregate"]["candidate"]["false_positive_rate"]
        self.assertEqual(fp["overall"]["rate"], 1.0)
        self.assertEqual(fp["by_category"]["structural"]["rate"], 1.0)
        self.assertEqual(fp["by_category"]["structural"]["spans_hit"], 1)


class TestNumericCalibration(unittest.TestCase):
    """Numeric targets report MAE with explicit denominators."""

    def test_mae_is_computed_from_absolute_error(self):
        fixture = make_fixture(
            score_target={"target": "text", "value": 92,
                          "label_provenance": "test-reference"})
        report = single_run(fixture)
        entry = report["fixtures"][0]
        self.assertEqual(entry["baseline"]["mae"]["labeled_value"], 92)
        self.assertEqual(entry["baseline"]["mae"]["error"], 92 - 0)
        mae = report["aggregate"]["baseline"]["mae"]
        self.assertEqual(mae["state"], "ok")
        self.assertEqual(mae["n"], 1)
        self.assertEqual(mae["mae"], 92.0)

    def test_mae_pools_over_fixtures(self):
        first = make_fixture(
            fid="cal-1",
            score_target={"target": "text", "value": 0,
                          "label_provenance": "test-reference"})
        second = make_fixture(
            fid="cal-2",
            text="Delve into the report.",
            score_target={"target": "text", "value": 100,
                          "label_provenance": "test-reference"})
        first["holdout"] = True
        report = run_experiment([first, second], make_config(holdout_ids=[]))
        mae = report["aggregate"]["baseline"]["mae"]
        self.assertEqual(mae["n"], 2)
        self.assertEqual(mae["mae"], 50.0)

    def test_no_numeric_targets_is_an_insufficient_state(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        self.assertEqual(report["aggregate"]["baseline"]["mae"]["state"],
                         "insufficient")


class TestRankCorrelation(unittest.TestCase):
    """Rank correlation is reported where severity ordering is meaningful."""

    def test_expected_severity_order_agrees_with_the_implementation(self):
        fixture = make_fixture(
            text="It's worth noting that the result is significant for the "
                 "rollout.",
            expected_findings=[
                {"target": "text", "rule_id": "phrase-worth-noting",
                 "category": "phrase", "span": [0, 22]},
                {"target": "text", "rule_id": "vocab-significant",
                 "category": "vocabulary", "span": [37, 48]},
                {"target": "text", "rule_id": "mechanism-importance",
                 "category": "mechanism", "span": [37, 48]},
            ],
            ranked_findings=[
                {"target": "text", "rule_id": "vocab-significant"},
                {"target": "text", "rule_id": "mechanism-importance"},
            ])
        report = single_run(fixture)
        rank = report["fixtures"][0]["baseline"]["rank"]
        self.assertEqual(rank["state"], "ok")
        self.assertEqual(rank["spearman"], 1.0)

    def test_reversed_order_reports_negative_correlation(self):
        fixture = make_fixture(
            text="It's worth noting that the result is significant for the "
                 "rollout.",
            ranked_findings=[
                {"target": "text", "rule_id": "mechanism-importance"},
                {"target": "text", "rule_id": "vocab-significant"},
            ])
        report = single_run(fixture)
        rank = report["fixtures"][0]["baseline"]["rank"]
        self.assertEqual(rank["state"], "ok")
        self.assertEqual(rank["spearman"], -1.0)

    def test_insufficient_ranked_findings_is_an_explicit_state(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        self.assertEqual(report["aggregate"]["baseline"]["rank_correlation"]
                         ["state"], "insufficient")


class TestRewriteMetrics(unittest.TestCase):
    """Rewrite fixtures report score delta and preservation failures."""

    def setUp(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        self.entry = next(entry for entry in report["fixtures"]
                          if entry["id"] == "cal-holdout")

    def test_score_delta_is_reported_with_direction(self):
        delta = self.entry["baseline"]["score_delta"]
        self.assertEqual(delta["source"], 0)
        self.assertEqual(delta["candidate"], 100)
        self.assertEqual(delta["delta"], 100)
        self.assertTrue(delta["direction_improvement"])

    def test_dropped_qualifier_is_a_preservation_failure(self):
        self.assertEqual(self.entry["preservation"]["obligation_failures"],
                         [{"kind": "term", "value": "about"}])
        self.assertTrue(self.entry["preservation"]["fidelity_hard_failures"])
        self.assertEqual(self.entry["preservation"]["total"], 2)

    def test_risk_improvement_does_not_hide_the_qualifier_loss(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        aggregate = report["aggregate"]["baseline"]
        self.assertEqual(aggregate["preservation_failures"]["total"], 2)
        self.assertEqual(aggregate["score_delta"]["mean"], 100.0)


class TestScoreStability(unittest.TestCase):
    """A repeated run proves deterministic results."""

    def test_every_fixture_reports_stable_scores(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        self.assertEqual(
            report["aggregate"]["baseline"]["score_stability"],
            {"stable_fixtures": 4, "checked_fixtures": 4, "stable": True})

    def test_repeated_experiments_are_byte_identical(self):
        first = json.dumps(run_experiment(REG_TEST_FIXTURES, make_config()),
                           sort_keys=True)
        second = json.dumps(run_experiment(REG_TEST_FIXTURES, make_config()),
                            sort_keys=True)
        self.assertEqual(first, second)


class TestFailOnRegressions(unittest.TestCase):
    """The harness fails on configured false-positive, recall, or preservation
    regressions."""

    def _regression_fixtures(self):
        return json.loads(json.dumps(REG_TEST_FIXTURES))

    def test_better_aggregate_recall_with_worse_technical_fp_fails(self):
        fixtures = self._regression_fixtures()
        precise = stub_impl("precise", fire_structural=False)
        sloppy = stub_impl("sloppy", fire_structural=True,
                           fire_clean_spans=True)
        config = make_config(fail_on_false_positive_regression=True)
        report = run_experiment(fixtures, config, precise, sloppy)
        candidate = report["aggregate"]["candidate"]["recall"]["overall"]["rate"]
        baseline = report["aggregate"]["baseline"]["recall"]["overall"]["rate"]
        self.assertGreater(candidate, baseline)
        candidate_fp = report["aggregate"]["candidate"]["false_positive_rate"]
        baseline_fp = report["aggregate"]["baseline"]["false_positive_rate"]
        self.assertGreater(candidate_fp["overall"]["rate"],
                           baseline_fp["overall"]["rate"])
        self.assertEqual(candidate_fp["by_category"]["structural"]["rate"], 1.0)
        regression = next(reg for reg in report["regressions"]
                          if reg["kind"] == "false_positive")
        self.assertEqual(regression["category"], "structural")
        self.assertFalse(report["gate"]["passed"])
        self.assertTrue(any("false-positive regression" in failure
                            for failure in report["gate"]["failures"]))

    def test_recall_regression_fails(self):
        fixtures = self._regression_fixtures()
        full = stub_impl("full", fire_structural=True)
        dropped = stub_impl("dropped", fire_structural=False)
        config = make_config(fail_on_recall_regression=True)
        report = run_experiment(fixtures, config, full, dropped)
        regression = next(reg for reg in report["regressions"]
                          if reg["kind"] == "recall")
        self.assertEqual(regression["category"], "structural")
        self.assertEqual(regression["baseline"], 1.0)
        self.assertEqual(regression["candidate"], 0.0)
        self.assertFalse(report["gate"]["passed"])
        self.assertTrue(any("recall regression" in failure
                            for failure in report["gate"]["failures"]))

    def test_preservation_regression_fails(self):
        fixtures = self._regression_fixtures()
        full = stub_impl("full", fire_structural=True)
        config = make_config(fail_on_preservation_regression=True)
        report = run_experiment(fixtures, config, full, full)
        self.assertEqual(
            report["aggregate"]["candidate"]["preservation_failures"]["total"],
            2)
        self.assertFalse(report["gate"]["passed"])
        self.assertTrue(any("preservation regression" in failure
                            for failure in report["gate"]["failures"]))

    def test_threshold_limits_fail_the_gate(self):
        fixtures = self._regression_fixtures()
        sloppy = stub_impl("sloppy", fire_structural=True,
                           fire_clean_spans=True)
        precise = stub_impl("precise", fire_structural=False)
        config = make_config(max_false_positive_rate=0.0)
        report = run_experiment(fixtures, config, precise, sloppy)
        self.assertFalse(report["gate"]["passed"])
        self.assertTrue(any("exceeds limit" in failure
                            for failure in report["gate"]["failures"]))

    def test_regressions_do_not_fail_without_a_configured_flag(self):
        fixtures = self._regression_fixtures()
        sloppy = stub_impl("sloppy", fire_structural=True,
                           fire_clean_spans=True)
        precise = stub_impl("precise", fire_structural=False)
        config = make_config()
        report = run_experiment(fixtures, config, precise, sloppy)
        self.assertTrue(report["regressions"])
        self.assertTrue(report["gate"]["passed"])


class TestPerProfile(unittest.TestCase):
    """Profile and genre provenance are required and per-profile metrics are
    reported."""

    def test_per_profile_metrics_are_reported(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        per_profile = report["aggregate"]["baseline"]["per_profile"]
        self.assertIn("general", per_profile)
        self.assertEqual(per_profile["general"]["fixtures"], 4)
        self.assertEqual(per_profile["general"]["recall"]["rate"], 1.0)

    def test_every_fixture_records_profile_and_genre(self):
        report = run_experiment(REG_TEST_FIXTURES, make_config())
        for entry in report["fixtures"]:
            self.assertIn(entry["profile"], ("general", "technical"))
            self.assertTrue(entry["genre"])
            self.assertTrue(entry["locale"])
            self.assertTrue(entry["source"])
            self.assertTrue(entry["label_provenance"])


class TestProductionCorpus(unittest.TestCase):
    """The shipped corpus runs end to end and its gate passes."""

    def setUp(self):
        self.config = load_config()
        self.fixtures = load_fixtures()
        baseline = calibration.build_implementation(
            self.config["baseline"],
            os.path.dirname(CONFIG))
        candidate = calibration.build_implementation(
            self.config["candidate"],
            os.path.dirname(CONFIG))
        self.report = calibration.run_experiment(
            self.fixtures, baseline, candidate, self.config,
            registry_path=REGISTRY)

    def test_gate_passes_on_production_corpus(self):
        self.assertEqual(self.report["gate"]["failures"], [])
        self.assertTrue(self.report["gate"]["passed"])

    def test_fixture_revision_is_frozen_and_shared(self):
        self.assertEqual(self.report["fixture_revision"],
                         self.config["fixture_revision"])
        self.assertTrue(self.report["frozen"])

    def test_per_category_recall_does_not_hide_the_candidate_regression(self):
        baseline = self.report["aggregate"]["baseline"]["recall"]["by_category"]
        candidate = self.report["aggregate"]["candidate"]["recall"]["by_category"]
        for category in ("mechanism", "structural"):
            self.assertEqual(baseline[category]["rate"], 1.0)
            self.assertEqual(candidate[category]["rate"], 0.0)
        regression_categories = {reg["category"] for reg in self.report["regressions"]}
        self.assertEqual(regression_categories, {"mechanism", "structural"})

    def test_unlabeled_categories_are_null_in_production(self):
        candidate = self.report["aggregate"]["candidate"]["recall"]["by_category"]
        for category in ("filler", "formatting", "integrity", "preferred",
                         "evaluation"):
            self.assertIsNone(candidate[category]["rate"])

    def test_rewrite_fixture_reports_preservation_failure_and_delta(self):
        entry = next(entry for entry in self.report["fixtures"]
                     if entry["id"] == "calibration-rewrite-lowers-risk-drops-qualifier")
        self.assertEqual(entry["preservation"]["total"], 2)
        self.assertTrue(entry["baseline"]["score_delta"]["direction_improvement"])

    def test_repeated_cli_runs_are_byte_identical(self):
        rc1, out1, _err1 = run_calibration_cli(
            "--experiment-config", "skills/antislop/evals/calibration-experiment.json")
        rc2, out2, _err2 = run_calibration_cli(
            "--experiment-config", "skills/antislop/evals/calibration-experiment.json")
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        self.assertEqual(out1, out2)

    def test_cli_writes_a_reviewable_artifact(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "results.json")
            rc, _out, _err = run_calibration_cli(
                "--experiment-config",
                "skills/antislop/evals/calibration-experiment.json",
                "--output", output)
            self.assertEqual(rc, 0)
            with open(output, encoding="utf-8") as f:
                report = json.load(f)
            self.assertEqual(report["interface"], "antislop.calibration")
            self.assertEqual(report["version"], "3.0.0")

    def test_cli_rejects_a_missing_experiment_config(self):
        rc, _out, _err = run_calibration_cli("--experiment-config", "nope.json")
        self.assertEqual(rc, 2)

    def test_cli_enforces_the_expected_version(self):
        rc, _out, _err = run_calibration_cli(
            "--experiment-config",
            "skills/antislop/evals/calibration-experiment.json",
            "--expect-version", "9.9.9")
        self.assertEqual(rc, 2)

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


if __name__ == "__main__":
    unittest.main()
