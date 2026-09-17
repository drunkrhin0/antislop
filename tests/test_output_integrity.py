#!/usr/bin/env python3
"""Tests for the output-integrity finding runner (issue #99).

Covers the acceptance criteria:
  - integrity findings are reported separately from formulaic-writing risk
  - each finding carries an exact span, line, stable ID, and repair guidance
  - code, quotes, and intentional example fixtures are protected
  - tracking detection distinguishes analytics parameters from functional
    query data
  - Unicode checks expose the code point and safe interpretation without
    mutating the text
  - baseline mode fails only on new or worsened configured findings
  - short samples return uncertainty rather than fabricated metrics

Run: python3 -m unittest tests/test_output_integrity.py -v
"""

import json
import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import output_integrity as oi  # noqa: E402 -- import after sys.path setup

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "output-integrity-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
RUNNER = os.path.join(ROOT, "tools", "output_integrity.py")
VALIDATE = os.path.join(ROOT, "tools", "validate.py")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def run_runner(*args, input_text=None):
    result = subprocess.run([sys.executable, RUNNER] + list(args),
                            capture_output=True, text=True, cwd=ROOT,
                            input=input_text)
    return result.returncode, result.stdout, result.stderr


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


def baseline_doc(counts, enabled=None):
    return {
        "schema": "output-integrity-baseline-1",
        "config": {"enabled_kinds": enabled or list(oi.INTEGRITY_KINDS)},
        "documents": [{"id": "doc", "counts": counts}],
    }


def make_fixture(rid="oi-test", **overrides):
    fixture = {
        "id": rid,
        "source": "The meeting ran long and nothing was decided today.",
        "expected_counts": {kind: 0 for kind in oi.INTEGRITY_KINDS},
        "expected_finding_count": 0,
    }
    fixture.update(overrides)
    return fixture


CITATION_SOURCE = (
    "The rollout used the earlier design "
    "[Smith 2020](https://example.com/design). The schema team flagged "
    "[source: internal] and left it unresolved in the report they handed "
    "back."
)

PLACEHOLDER_SOURCE = (
    "The release note still says [PLACEHOLDER] for the customer impact "
    "section, and the review checklist expects the owner name there before "
    "it ships to the wider team."
)

TRACKING_SOURCE = (
    "Share the campaign link "
    "https://example.com/?utm_source=newsletter&utm_medium=email, and keep "
    "the functional signed link "
    "https://example.com/download?sig=a1b2c3&expires=1700000000 for direct "
    "access without any tracking."
)

QUOTED_AND_CODE_SOURCE = (
    "The reviewer wrote: \"As an AI language model, let me think step by "
    "step.\" It stays quoted.\n\n"
    "```text\n"
    "[PLACEHOLDER] https://example.com/?utm_source=code&utm_medium=scan\n"
    "As an AI, I would say something here.\n"
    "```\n\n"
    "The paragraph above the code is clean prose and stays clean."
)

HOMOGLYPH_SOURCE = (
    "The team called the fake page pr\u043educt, using a Cyrillic letter "
    "inside an otherwise Latin word, while the genuine caf\u00e9 name stayed "
    "untouched."
)

ZERO_WIDTH_SOURCE = (
    "The caf\u00e9 menu\u200b lists the daily specials and the chef's name, "
    "and the fixed menu repeats the same items every week without a change."
)

SHORT_SOURCE = "The meeting ran long."


class TestSeparateReport(unittest.TestCase):
    """Integrity findings are reported separately from formulaic risk."""

    def setUp(self):
        self.registry = load_registry()

    def test_report_is_machine_readable_json(self):
        report = oi.scan_documents([("doc", PLACEHOLDER_SOURCE)],
                                   self.registry)
        json.dumps(report)
        for key in ("interface", "schema", "version", "documents", "signals",
                    "risk", "meta"):
            self.assertIn(key, report)
        self.assertEqual(report["schema"], "output-integrity-report-1")
        self.assertEqual(report["version"], "3.0.0")

    def test_findings_are_never_scored_as_risk(self):
        report = oi.scan_documents([("doc", PLACEHOLDER_SOURCE)],
                                   self.registry)
        risk = report["risk"]
        self.assertTrue(risk["scored_separately"])
        self.assertTrue(risk["advisory"])
        self.assertFalse(risk["authorship_evidence"])
        self.assertIn("never prove AI authorship", risk["disclaimer"])

    def test_report_never_mutates_text(self):
        report = oi.scan_documents([("doc", ZERO_WIDTH_SOURCE)],
                                   self.registry)
        self.assertFalse(report["meta"]["mutated"])
        self.assertIn("never prove AI authorship",
                      report["meta"]["disclaimer"])


class TestFindingRecord(unittest.TestCase):
    """Each finding has exact span, line, stable ID, and repair guidance."""

    def setUp(self):
        self.registry = load_registry()

    def test_finding_carries_span_line_id_repair(self):
        doc = oi.scan_text(CITATION_SOURCE)
        finding = doc["findings"][0]
        self.assertEqual(finding["kind"], "provider_citation")
        self.assertEqual(finding["rule_id"], "integrity-leaked-citation")
        start, end = finding["span"]
        self.assertEqual(CITATION_SOURCE[start:end], "[source: internal]")
        self.assertEqual(finding["line"], 1)
        self.assertTrue(finding["id"].startswith("oi-provider_citation-"))
        self.assertTrue(finding["repair"])
        self.assertEqual(finding["evidence"], "span")

    def test_multi_line_finding_reports_start_line(self):
        text = ("First clean line.\n"
                "Second clean line.\n"
                "The reviewer let me think step by step here and left it "
                "in the final copy.")
        doc = oi.scan_text(text)
        finding = next(f for f in doc["findings"]
                       if f["kind"] == "leaked_reasoning")
        self.assertEqual(finding["line"], 3)

    def test_line_lookup_uses_the_precomputed_index(self):
        text = ("clean line\n" * 2000
                + "[PLACEHOLDER a] then [PLACEHOLDER b] remain.")
        with mock.patch.object(
                oi, "_line_number",
                wraps=oi._line_number) as line_number:
            doc = oi.scan_text(text)
        self.assertEqual(doc["counts"]["placeholder"], 2)
        self.assertEqual(line_number.call_count, 2)

    def test_stable_ids_are_deterministic_per_kind(self):
        doc = oi.scan_text("[PLACEHOLDER a] then [PLACEHOLDER b] stayed in "
                           "the draft we still need to finish and send.")
        ids = [f["id"] for f in doc["findings"]]
        self.assertEqual(ids, ["oi-placeholder-1", "oi-placeholder-2"])
        doc2 = oi.scan_text("[PLACEHOLDER a] then [PLACEHOLDER b] stayed in "
                            "the draft we still need to finish and send.")
        self.assertEqual([f["id"] for f in doc2["findings"]], ids)

    def test_counters_are_accurate(self):
        doc = oi.scan_text(CITATION_SOURCE)
        self.assertEqual(doc["finding_count"], 1)
        self.assertEqual(doc["counts"]["provider_citation"], 1)


class TestProtectedTokenization(unittest.TestCase):
    """Code, quotes, and intentional example fixtures stay protected."""

    def setUp(self):
        self.registry = load_registry()

    def test_fenced_code_and_quotes_are_protected(self):
        doc = oi.scan_text(QUOTED_AND_CODE_SOURCE)
        self.assertEqual(doc["finding_count"], 0)
        for kind in oi.INTEGRITY_KINDS:
            self.assertEqual(doc["counts"][kind], 0)

    def test_inline_code_is_protected(self):
        text = ("The command `echo [PLACEHOLDER]` is documented, and the "
                "runner does not flag the marker inside the inline code at "
                "all here.")
        doc = oi.scan_text(text)
        self.assertEqual(doc["counts"]["placeholder"], 0)

    def test_multiline_blockquotes_are_protected(self):
        text = "> [PLACEHOLDER] and utilize this.\n> More quoted prose."
        doc = oi.scan_text(text)
        self.assertEqual(doc["finding_count"], 0)

    def test_markdown_link_citation_is_protected(self):
        doc = oi.scan_text(
            "The design is documented as [Smith 2020](https://example.com/"
            "design) and the team referenced it in the review that closed "
            "the loop for good.")
        self.assertEqual(doc["counts"]["provider_citation"], 0)

    def test_url_inside_quotes_is_protected_from_tracking(self):
        text = ("They quoted the campaign as \"https://example.com/?utm_"
                "source=mail&utm_medium=email\" in the notes, and the quote "
                "is not treated as a tracking link by the scanner.")
        doc = oi.scan_text(text)
        self.assertEqual(doc["counts"]["tracking_parameter"], 0)

    def test_quoted_bad_example_is_protected(self):
        doc = oi.scan_text(
            "The review quoted a bad example: \"utilize [PLACEHOLDER] to "
            "track https://example.com/?utm_source=x\" and asked the author "
            "to fix the sentence that followed.")
        self.assertEqual(doc["finding_count"], 0)


class TestProviderCitation(unittest.TestCase):
    def test_citation_residue_is_a_finding(self):
        doc = oi.scan_text(CITATION_SOURCE)
        kinds = {f["kind"] for f in doc["findings"]}
        self.assertEqual(kinds, {"provider_citation"})
        self.assertEqual(doc["counts"]["provider_citation"], 1)

    def test_legitimate_markdown_citation_never_fires(self):
        text = ("The claim follows [Jones 2019](https://example.com/jones) "
                "and the report cites it on every page that repeats the "
                "finding for the reader.")
        doc = oi.scan_text(text)
        self.assertEqual(doc["counts"]["provider_citation"], 0)


class TestPlaceholder(unittest.TestCase):
    def test_placeholder_in_deliverable_prose_is_a_finding(self):
        doc = oi.scan_text(PLACEHOLDER_SOURCE)
        self.assertEqual(doc["counts"]["placeholder"], 1)
        self.assertEqual(doc["template"], False)

    def test_template_mode_suppresses_placeholders(self):
        text = ("Onboarding template for new tenants.\n\n"
                "Welcome: [PLACEHOLDER tenant name]\n"
                "Primary contact: [PLACEHOLDER email]\n"
                "Kickoff date: [PLACEHOLDER date]\n"
                "Security review: [PLACEHOLDER owner]\n"
                "Expected duration: [PLACEHOLDER weeks]")
        doc = oi.scan_text(text, template=True)
        self.assertEqual(doc["counts"]["placeholder"], 0)
        self.assertEqual(doc["template"], True)


class TestTrackingParameters(unittest.TestCase):
    def test_analytics_only_url_is_a_finding(self):
        doc = oi.scan_text(TRACKING_SOURCE)
        findings = [f for f in doc["findings"]
                    if f["kind"] == "tracking_parameter"]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["parameters"],
                         ["utm_medium", "utm_source"])
        self.assertIn("utm_source", finding["url"])
        start, end = finding["span"]
        self.assertFalse(TRACKING_SOURCE[end - 1:end] in ".,;")

    def test_functional_signed_url_is_not_a_finding(self):
        doc = oi.scan_text(TRACKING_SOURCE)
        self.assertEqual(doc["counts"]["tracking_parameter"], 1)
        signed = next(f for f in doc["findings"]
                      if f["kind"] == "tracking_parameter")
        self.assertNotIn("sig=", signed["url"])

    def test_mixed_functional_and_tracking_query_is_left_alone(self):
        text = ("Follow the link https://example.com/report?id=42&utm_source=x "
                "for the full report, it is the only one we have left and "
                "the rest of the archive is offline today.")
        doc = oi.scan_text(text)
        self.assertEqual(doc["counts"]["tracking_parameter"], 0)

    def test_url_without_query_is_not_a_finding(self):
        text = ("The homepage at https://example.com is linked from the "
                "footer, and the footer also lists the support address for "
                "anyone who needs direct help with an account issue.")
        doc = oi.scan_text(text)
        self.assertEqual(doc["counts"]["tracking_parameter"], 0)


class TestZeroWidth(unittest.TestCase):
    def test_zero_width_char_is_exposed_with_code_point(self):
        doc = oi.scan_text(ZERO_WIDTH_SOURCE)
        findings = [f for f in doc["findings"] if f["kind"] == "zero_width"]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["code_point"], "U+200B")
        self.assertEqual(finding["name"], "ZERO WIDTH SPACE")
        self.assertEqual(finding["safe_interpretation"], "zero-width space")
        self.assertEqual(finding["char"], "\u200b")

    def test_legitimate_non_ascii_identifier_is_untouched(self):
        doc = oi.scan_text(ZERO_WIDTH_SOURCE)
        self.assertEqual(doc["counts"]["homoglyph"], 0)
        for finding in doc["findings"]:
            self.assertNotEqual(finding["kind"], "homoglyph")

    def test_text_is_not_silently_replaced(self):
        doc = oi.scan_text(ZERO_WIDTH_SOURCE)
        self.assertFalse(doc["findings"][0]["repair"].startswith(
            "Replace the invisible character"))


class TestHomoglyph(unittest.TestCase):
    def test_mixed_script_token_is_a_finding(self):
        doc = oi.scan_text(HOMOGLYPH_SOURCE)
        findings = [f for f in doc["findings"] if f["kind"] == "homoglyph"]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["code_point"], "U+043E")
        self.assertEqual(finding["lookalike"], "o")

    def test_genuine_foreign_word_is_not_a_finding(self):
        text = ("The label on the jar said \u043f\u0440\u0438\u0432\u0435\u0442 "
                "and the shop owner explained it meant hello, so the sign "
                "was left exactly as the importers wrote it.")
        doc = oi.scan_text(text)
        self.assertEqual(doc["counts"]["homoglyph"], 0)


class TestShortSample(unittest.TestCase):
    def test_short_sample_reports_uncertainty(self):
        doc = oi.scan_text(SHORT_SOURCE)
        self.assertEqual(doc["sample_status"], "short-sample")
        self.assertEqual(doc["certainty"], "uncertain")
        self.assertTrue(doc["sample_message"])

    def test_short_sample_still_reports_observed_findings(self):
        doc = oi.scan_text("Wait [PLACEHOLDER]?")
        self.assertEqual(doc["sample_status"], "short-sample")
        self.assertEqual(doc["counts"]["placeholder"], 1)

    def test_adequate_sample_is_confident(self):
        doc = oi.scan_text(PLACEHOLDER_SOURCE)
        self.assertEqual(doc["sample_status"], "adequate")
        self.assertEqual(doc["certainty"], "confident")
        self.assertIsNone(doc["sample_message"])


class TestBaselineComparison(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_new_finding_is_a_regression(self):
        report = oi.scan_documents([("doc", PLACEHOLDER_SOURCE)],
                                   self.registry)
        base = baseline_doc({kind: 0 for kind in oi.INTEGRITY_KINDS})
        report["baseline"] = oi.compare_to_baseline(report, base)
        self.assertTrue(report["baseline"]["failed"])
        regressions = report["baseline"]["regressions"]
        self.assertEqual(len(regressions), 1)
        self.assertEqual(regressions[0]["direction"], "new")
        self.assertEqual(regressions[0]["kind"], "placeholder")
        self.assertEqual(oi.exit_status(report, fail_on_regression=True), 1)

    def test_worsened_count_is_a_regression(self):
        report = oi.scan_documents([("doc", PLACEHOLDER_SOURCE)],
                                   self.registry)
        base = baseline_doc({
            "placeholder": 0, "provider_citation": 0, "tracking_parameter": 0,
            "leaked_reasoning": 0, "zero_width": 0, "homoglyph": 0})
        report["baseline"] = oi.compare_to_baseline(report, base)
        regressions = report["baseline"]["regressions"]
        self.assertEqual(regressions[0]["direction"], "new")

    def test_unchanged_findings_match_frozen_baseline(self):
        counts = {kind: 0 for kind in oi.INTEGRITY_KINDS}
        counts["placeholder"] = 1
        report = oi.scan_documents([("doc", PLACEHOLDER_SOURCE)],
                                   self.registry)
        report["baseline"] = oi.compare_to_baseline(report, baseline_doc(counts))
        self.assertFalse(report["baseline"]["regressions"])
        self.assertFalse(report["baseline"]["failed"])
        self.assertEqual(oi.exit_status(report, fail_on_regression=True), 0)

    def test_improvement_is_not_a_regression(self):
        report = oi.scan_documents([("doc", PLACEHOLDER_SOURCE)],
                                   self.registry)
        counts = {kind: 0 for kind in oi.INTEGRITY_KINDS}
        counts["placeholder"] = 2
        report["baseline"] = oi.compare_to_baseline(report, baseline_doc(counts))
        self.assertFalse(report["baseline"]["regressions"])
        self.assertFalse(report["baseline"]["failed"])
        improvements = report["baseline"]["improvements"]
        self.assertEqual(len(improvements), 1)
        self.assertEqual(improvements[0]["kind"], "placeholder")

    def test_disabled_kind_never_fails(self):
        report = oi.scan_documents([("doc", TRACKING_SOURCE)],
                                   self.registry)
        base = baseline_doc({kind: 0 for kind in oi.INTEGRITY_KINDS},
                            enabled=["placeholder"])
        report["baseline"] = oi.compare_to_baseline(report, base)
        self.assertFalse(report["baseline"]["regressions"])
        self.assertEqual(oi.exit_status(report, fail_on_regression=True), 0)

    def test_without_fail_flag_regressions_do_not_gate(self):
        report = oi.scan_documents([("doc", PLACEHOLDER_SOURCE)],
                                   self.registry)
        base = baseline_doc({kind: 0 for kind in oi.INTEGRITY_KINDS})
        report["baseline"] = oi.compare_to_baseline(report, base)
        self.assertTrue(report["baseline"]["failed"])
        self.assertEqual(oi.exit_status(report), 1)

    def test_new_document_findings_are_new_regressions(self):
        report = oi.scan_documents([("new-doc", PLACEHOLDER_SOURCE)],
                                   self.registry)
        base = baseline_doc({kind: 0 for kind in oi.INTEGRITY_KINDS})
        report["baseline"] = oi.compare_to_baseline(report, base)
        self.assertTrue(report["baseline"]["failed"])
        self.assertTrue(report["baseline"]["regressions"])

    def test_baseline_schema_validation(self):
        self.assertEqual(oi.validate_baseline(
            baseline_doc({kind: 0 for kind in oi.INTEGRITY_KINDS})), [])
        self.assertTrue(any("schema must be" in error
                            for error in oi.validate_baseline({})))
        bad = baseline_doc({kind: 0 for kind in oi.INTEGRITY_KINDS})
        bad["documents"][0]["counts"]["placeholder"] = -1
        self.assertTrue(any("non-negative integer" in error
                            for error in oi.validate_baseline(bad)))
        unknown = baseline_doc({kind: 0 for kind in oi.INTEGRITY_KINDS})
        unknown["config"]["enabled_kinds"] = ["bogus"]
        self.assertTrue(any("unknown kind" in error
                            for error in oi.validate_baseline(unknown)))


class TestExitStatus(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_clean_document_exits_zero(self):
        rc, out, err = run_runner("--profile", "general",
                                  input_text=SHORT_SOURCE)
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertFalse(report["signals"]["findings_present"])
        self.assertTrue(report["signals"]["short_sample"])

    def test_finding_exits_one(self):
        rc, out, err = run_runner("--profile", "general",
                                  input_text=PLACEHOLDER_SOURCE)
        self.assertEqual(rc, 1, err)
        report = json.loads(out)
        self.assertTrue(report["signals"]["findings_present"])

    def test_template_flag_suppresses_placeholder_finding(self):
        rc, out, err = run_runner("--profile", "general", "--template",
                                  input_text=PLACEHOLDER_SOURCE)
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertTrue(report["documents"][0]["template"])

    def test_exit_status_function_matches_cli(self):
        clean = oi.scan_documents([("doc", SHORT_SOURCE)], self.registry)
        self.assertEqual(oi.exit_status(clean), 0)
        finding = oi.scan_documents([("doc", PLACEHOLDER_SOURCE)],
                                    self.registry)
        self.assertEqual(oi.exit_status(finding), 1)


class TestFixtureSchema(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = oi.validate_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_missing_source_is_rejected(self):
        errors = oi.validate_fixture(
            {"id": "empty", "source": "  "}, set())
        self.assertTrue(any("non-empty string" in error
                            for error in errors))

    def test_unknown_kind_in_expected_counts_is_rejected(self):
        errors = oi.validate_fixture(
            make_fixture(expected_counts={"bogus": 1}), set())
        self.assertTrue(any("unknown kind" in error for error in errors))

    def test_negative_count_is_rejected(self):
        errors = oi.validate_fixture(
            make_fixture(expected_counts={"placeholder": -1}), set())
        self.assertTrue(any("non-negative integer" in error
                            for error in errors))

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        oi.validate_fixture(make_fixture(), seen)
        errors = oi.validate_fixture(make_fixture(), seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))

    def test_unknown_sample_status_is_rejected(self):
        errors = oi.validate_fixture(
            make_fixture(expected_sample_status="long"), set())
        self.assertTrue(any("expected_sample_status must be one of"
                            in error for error in errors))

    def test_template_must_be_boolean(self):
        errors = oi.validate_fixture(make_fixture(template="yes"), set())
        self.assertTrue(any("template must be a boolean" in error
                            for error in errors))


class TestProductionCorpus(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = oi.run_output_integrity_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "oi-provider-citation-beside-legitimate-citation",
            "oi-placeholder-in-deliverable-prose",
            "oi-placeholder-in-documented-template",
            "oi-zero-width-char-and-legitimate-identifier",
            "oi-tracking-url-and-functional-signed-url",
            "oi-quoted-bad-example-and-fenced-code-protected",
        }
        self.assertEqual(ids & required, required)

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestCliInterface(unittest.TestCase):
    def test_fixture_corpus_exits_zero(self):
        rc, out, err = run_runner(
            "--fixtures", "skills/antislop/evals/output-integrity-fixtures.json")
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertTrue(report["gate_pass"])

    def test_stdin_accepts_input_without_a_file(self):
        rc, out, err = run_runner("--profile", "general",
                                  input_text=PLACEHOLDER_SOURCE)
        self.assertEqual(rc, 1, err)
        report = json.loads(out)
        self.assertEqual(report["document_count"], 1)

    def test_baseline_fail_on_regression_exits_one(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base_path = os.path.join(tmp, "baseline.json")
            with open(base_path, "w", encoding="utf-8") as f:
                json.dump(baseline_doc(
                    {kind: 0 for kind in oi.INTEGRITY_KINDS}), f)
            rc, out, err = run_runner(
                "--baseline", base_path, "--fail-on-regression",
                input_text=PLACEHOLDER_SOURCE)
        self.assertEqual(rc, 1, err)
        report = json.loads(out)
        self.assertTrue(report["baseline"]["failed"])

    def test_missing_file_is_a_usage_error(self):
        rc, out, err = run_runner("--file", os.path.join(ROOT, "nope.md"))
        self.assertEqual(rc, 2, err)

    def test_later_document_reads_only_the_remaining_budget(self):
        first = "a" * 600_000
        with mock.patch.object(
                oi.limits, "read_text_file",
                side_effect=(first, ValueError("documents exceed limit"))) as read:
            with self.assertRaisesRegex(ValueError, "documents exceed"):
                oi._read_documents(("first.md", "second.md"))
        self.assertEqual(read.call_args_list[0].kwargs["max_chars"],
                         oi.limits.MAX_INPUT_CHARS)
        self.assertEqual(read.call_args_list[1].kwargs["max_chars"], 400_000)


if __name__ == "__main__":
    unittest.main()
