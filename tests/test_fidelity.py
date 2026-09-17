#!/usr/bin/env python3
"""Tests for the source-to-candidate fidelity gate (issue #90).

Covers the five phases and the evaluation fixtures from the issue:
  - extract: protected spans and semantic anchors are recorded
  - compare: number, date, unit, URL, quoted, and required-term changes fail
    closed unless authorized
  - compare: negation, modality, scope, and quantifier changes produce hard
    failures; attribution changes reach a named human-review state
  - rescan: risk improvement is recorded and edit churn is measured
  - gate: authorization records rather than rejects; bounded retries roll
    back to the source
  - advisory: stylometric measures never become authorship evidence

Run: python3 -m unittest tests/test_fidelity.py -v
"""

import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import fidelity  # noqa: E402


class TestExtraction(unittest.TestCase):
    """Phase 1: protected spans and semantic anchors are recorded."""

    def test_extract_returns_both_span_kinds(self):
        result = fidelity.extract_anchors(
            "The beta release ships on 2024-01-15 and the call completes "
            "in up to 10 ms.",
            required_terms=("beta",),
        )
        protected = {s["category"] for s in result["protected_spans"]}
        self.assertIn("number", protected)
        self.assertIn("unit", protected)
        self.assertIn("date", protected)
        self.assertIn("required_term", protected)
        anchors = {a["category"] for a in result["semantic_anchors"]}
        self.assertIn("scope", anchors)
        self.assertIn("quantifier", anchors)

    def test_numbers_inside_dates_are_not_double_counted(self):
        result = fidelity.extract_anchors("Shipped on 2024-01-15.")
        numbers = [s for s in result["protected_spans"]
                   if s["category"] == "number"]
        self.assertEqual(numbers, [])

    def test_code_fence_is_a_protected_span(self):
        result = fidelity.extract_anchors("```python\nx = 1\n```")
        kinds = {s["category"] for s in result["protected_spans"]}
        self.assertIn("code_block", kinds)

    def test_many_distinct_anchors_do_not_use_pairwise_deduplication(self):
        text = " ".join("not item%d." % index for index in range(4000))
        with mock.patch.object(
                fidelity, "_same_span",
                wraps=fidelity._same_span) as same_span:
            result = fidelity.extract_anchors(text)
        self.assertEqual(
            len([anchor for anchor in result["semantic_anchors"]
                 if anchor["category"] == "negation"]),
            4000)
        self.assertLess(same_span.call_count, 100)


class TestProtectedSpanFidelity(unittest.TestCase):
    """Phase 3: exact-value changes fail closed unless authorized."""

    def test_number_change_fails_closed(self):
        report = fidelity.check_fidelity("Deploy time is 40 minutes.",
                                         "Deploy time is 50 minutes.")
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(f["category"] == "number"
                            for f in report["preservation"]["hard_failures"]))

    def test_date_change_fails_closed(self):
        report = fidelity.check_fidelity("Ships on 2024-01-15.",
                                         "Ships on 2024-02-20.")
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(f["category"] == "date"
                            for f in report["preservation"]["hard_failures"]))

    def test_unit_change_fails_closed(self):
        report = fidelity.check_fidelity("The batch finishes in 10 milliseconds.",
                                         "The batch finishes in 10 seconds.")
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(f["category"] == "unit"
                            for f in report["preservation"]["hard_failures"]))

    def test_url_change_fails_closed(self):
        report = fidelity.check_fidelity("See https://example.com/guide.",
                                         "See https://example.net/guide.")
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(f["category"] == "url"
                            for f in report["preservation"]["hard_failures"]))

    def test_filesystem_paths_with_one_separator_fail_closed(self):
        report = fidelity.check_fidelity(
            "See /tmp/file and docs/file.",
            "See /tmp/other and docs/other.",
        )
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(f["category"] == "path"
                            for f in report["preservation"]["hard_failures"]))

    def test_quoted_change_fails_closed(self):
        report = fidelity.check_fidelity('The customer wrote "ship it".',
                                         'The customer wrote "ship it now".')
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(f["category"] == "quoted"
                            for f in report["preservation"]["hard_failures"]))

    def test_required_term_change_fails_closed(self):
        report = fidelity.check_fidelity(
            "The service is SOC 2 compliant.",
            "The service is compliant.",
            required_terms=("SOC 2",),
        )
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(f["category"] == "required_term"
                            for f in report["preservation"]["hard_failures"]))

    def test_authorized_number_change_is_recorded_not_rejected(self):
        report = fidelity.check_fidelity(
            "The fix cut deploy time by 40%.",
            "The fix cut deploy time by 50%.",
            authorized_changes=[{"category": "number", "to": "50"}],
        )
        self.assertEqual(report["decision"], "accept")
        authorized = report["preservation"]["protected_spans"]["authorized"]
        self.assertTrue(any(entry["category"] == "number"
                            for entry in authorized))


class TestSemanticAnchorFidelity(unittest.TestCase):
    """Phase 3: meaning-bearing changes fail hard or reach named review."""

    def test_negation_flip_is_a_hard_failure(self):
        report = fidelity.check_fidelity(
            "This feature is not required for the release.",
            "This feature is required for the release.",
        )
        self.assertEqual(report["decision"], "reject")
        kinds = [f["category"]
                 for f in report["preservation"]["hard_failures"]]
        self.assertTrue(any(kind in ("negation", "polarity") for kind in kinds))

    def test_modality_change_is_a_hard_failure(self):
        report = fidelity.check_fidelity(
            "The system may restart during the update.",
            "The system will restart during the update.",
        )
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(f["category"] == "modality"
                            for f in report["preservation"]["hard_failures"]))

    def test_scope_and_quantifier_changes_are_hard_failures(self):
        report = fidelity.check_fidelity(
            "The call completes in up to 10 ms.",
            "The call completes in 10 ms.",
        )
        self.assertEqual(report["decision"], "reject")
        kinds = {f["category"]
                 for f in report["preservation"]["hard_failures"]}
        self.assertIn("scope", kinds)
        self.assertIn("quantifier", kinds)

    def test_cited_actor_change_reaches_named_review_state(self):
        report = fidelity.check_fidelity(
            "According to NIST, the standard requires encryption.",
            "According to IETF, the standard requires encryption.",
        )
        self.assertEqual(report["decision"], "review")
        self.assertEqual(report["review"]["status"], "unresolved")
        kinds = {item["category"] for item in report["review"]["items"]}
        self.assertTrue(kinds & {"attribution", "name"})


class TestRepairGate(unittest.TestCase):
    """Phase 4 + 5: rescore, churn, bounded retries, rollback."""

    def test_code_heavy_repair_preserves_code_links_and_commands(self):
        source = (
            "We delve into the problem.\n\n"
            "Run `pip install antislop` from the project root.\n\n"
            "```python\n"
            "def add(a, b):\n"
            "    return a + b\n"
            "```\n\n"
            "See https://example.com/docs for the reference.\n"
        )
        candidate = source.replace("delve", "dig into")
        report = fidelity.check_fidelity(source, candidate)
        self.assertEqual(report["decision"], "accept")
        protected = report["preservation"]["protected_spans"]
        self.assertEqual(protected["changed"], [])
        self.assertEqual(protected["removed"], [])
        unchanged = protected["unchanged_by_category"]
        self.assertEqual(sum(unchanged.values()), protected["total"])
        for kind in ("code_block", "url", "quoted"):
            self.assertEqual(unchanged.get(kind, 0), 1, kind)

    def test_risk_improvement_is_recorded(self):
        source = ("We delve into the problem. "
                  "The deployment pipeline handles releases regularly. " * 12)
        candidate = ("We dig into the problem. "
                     "The deployment pipeline handles releases regularly. " * 12)
        report = fidelity.check_fidelity(source, candidate)
        self.assertEqual(report["decision"], "accept")
        self.assertTrue(report["risk"]["improved"])
        self.assertGreater(report["risk"]["candidate_score"],
                           report["risk"]["source_score"])

    def test_edit_churn_limit_rejects_a_rewrite(self):
        source = ("We delve into the problem. "
                  "The deployment pipeline handles releases regularly. " * 10)
        candidate = ("We delve into the problem. "
                     "Plain words fill this space with ordinary prose across "
                     "the document. " * 10)
        report = fidelity.check_fidelity(
            source, candidate,
            hot_zones=[{"start": 3, "end": 8, "label": "vocab-delve"}],
            churn_limit=0.1,
        )
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["integrity"]["status"], "failed")
        self.assertTrue(report["integrity"]["churn"]["exceeds_limit"])

    def test_retries_exhausted_roll_back_to_the_source(self):
        source = ("Release date 2024-01-15. See https://example.com. "
                  "We delve into the problem.")

        def always_bad(_source, _attempt, _hot_zones):
            return ("Release date 2025-01-01. See https://example.net. "
                    "We dig into the problem.")

        result = fidelity.apply_repairs(source, always_bad, max_retries=2)
        self.assertEqual(result["decision"], "rollback")
        self.assertEqual(result["text"], source)
        self.assertEqual(len(result["attempts"]), 2)

    def test_repair_that_passes_is_accepted(self):
        source = "We delve into the problem."

        def good_repair(_source, _attempt, _hot_zones):
            return "We dig into the problem."

        result = fidelity.apply_repairs(source, good_repair, max_retries=2)
        self.assertEqual(result["decision"], "accept")
        self.assertEqual(result["text"], "We dig into the problem.")

    def test_churn_identical_input_is_zero(self):
        # difflib.SequenceMatcher is quadratic on large repetitive input;
        # identical source and candidate must short-circuit to zero churn.
        source = ("<thought " * 5000)
        self.assertEqual(fidelity._churn(source, source), 0)

    def test_large_near_equal_churn_uses_linear_fallback(self):
        source = "ab" * 2000
        candidate = source[:-1] + "c"
        with mock.patch.object(
                fidelity.difflib, "SequenceMatcher",
                side_effect=AssertionError("quadratic matcher reached")):
            self.assertGreater(fidelity._churn(source, candidate), 0)

    def test_large_span_sequences_use_linear_fallback(self):
        source = [{"value": "v%d" % index, "canonical": "v%d" % index}
                  for index in range(2500)]
        candidate = list(source)
        candidate[-1] = {"value": "changed", "canonical": "changed"}
        with mock.patch.object(
                fidelity.difflib, "SequenceMatcher",
                side_effect=AssertionError("quadratic matcher reached")):
            result = fidelity._compare_sequences(source, candidate, False)
        self.assertTrue(result["changed"])

    def test_large_equal_length_fallback_keeps_unchanged_middle_values(self):
        source = [{"value": "v%d" % index, "canonical": "v%d" % index}
                  for index in range(1001)]
        candidate = [dict(item) for item in source]
        candidate[1] = {"value": "first", "canonical": "first"}
        candidate[999] = {"value": "last", "canonical": "last"}
        result = fidelity._compare_sequences(source, candidate, False)
        self.assertEqual(len(result["changed"]), 2)
        self.assertEqual(len(result["unchanged"]), 999)

    def test_apply_repairs_rejects_oversize_before_finding_scan(self):
        source = "x" * (fidelity.limits.MAX_INPUT_CHARS + 1)
        with mock.patch.object(
                fidelity, "finding_spans",
                side_effect=AssertionError("preprocessing reached")):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                fidelity.apply_repairs(source, lambda *_args: source)


class TestReportShape(unittest.TestCase):
    """The interface returns serializable JSON with the required sections."""

    def test_report_is_json_serializable_with_expected_shape(self):
        report = fidelity.check_fidelity("One two three.", "One two three.")
        json.dumps(report)
        for key in ("interface", "schema", "version", "decision", "reason",
                    "risk", "preservation", "integrity", "review", "meta"):
            self.assertIn(key, report)
        self.assertEqual(report["version"], "3.0.0")
        self.assertEqual(report["decision"], "accept")

    def test_report_distinguishes_risk_preservation_integrity_review(self):
        report = fidelity.check_fidelity(
            "The system may restart during the update.",
            "The system will restart during the update.",
        )
        self.assertEqual(report["preservation"]["status"], "failed")
        self.assertEqual(report["integrity"]["status"], "passed")
        self.assertEqual(report["review"]["status"], "none")
        self.assertIsNotNone(report["risk"]["source_score"])
        self.assertIsNotNone(report["risk"]["candidate_score"])

    def test_stylometrics_are_advisory_never_authorship_evidence(self):
        report = fidelity.check_fidelity(
            "This is a plain sentence with clean wording.",
            "Different prose with a varied rhythm and a sharp tone.",
            churn_limit=1.5,
        )
        stylometrics = report["meta"]["stylometrics"]
        self.assertTrue(stylometrics["advisory"])
        self.assertFalse(stylometrics["authorship_evidence"])
        self.assertEqual(report["decision"], "accept")


if __name__ == "__main__":
    unittest.main()
