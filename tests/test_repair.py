#!/usr/bin/env python3
"""Tests for the Unslop-style protected repair interface (issue #92).

Covers the acceptance criteria:
  - stdin and a single named file, never changing a file without an explicit
    write flag
  - dry-run and diff modes never write
  - JSON replacement records carry rule ID, span, action, original,
    replacement, preservation result, and unresolved status
  - protected regions stay byte-identical
  - running repair twice produces no second change
  - structural repair fires only for one supported deterministic case and
    passes the fidelity gate
  - leaked reasoning wrappers are integrity findings, removed outside quoted
    or code material and kept inside it
  - general and technical profile fixtures prove literal domain terms are not
    rewritten
  - a failed preservation check prevents the write and returns nonzero

Run: python3 -m unittest tests/test_repair.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import repair  # noqa: E402
import fidelity  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "repair-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
REPAIR = os.path.join(ROOT, "repair.py")
VALIDATE = os.path.join(ROOT, "validate.py")

MARKDOWN_SOURCE = (
    "# Deployment notes\n\n"
    "We utilize the deployment checklist below.\n\n"
    "```python\n"
    "def probe(url):\n"
    "    return url + \"/health\"\n"
    "```\n\n"
    "Install with `pip install antislop` and see https://example.com/docs.\n\n"
    "| Metric | Value |\n"
    "|--------|-------|\n"
    "| utilize rate | 40 ms |\n"
    "| error rate | 0.5% |\n\n"
    "> The worker \"utilize\" retried the job.\n"
)


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def make_fixture(rid="repair-test", **overrides):
    fixture = {
        "id": rid,
        "source": "We utilize the API to fetch records.",
        "expected_decision": "accept",
    }
    fixture.update(overrides)
    return fixture


def run_repair_cli(*args, input_text=None):
    result = subprocess.run([sys.executable, REPAIR] + list(args),
                            capture_output=True, text=True, cwd=ROOT,
                            input=input_text)
    return result.returncode, result.stdout, result.stderr


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestProtectedRegions(unittest.TestCase):
    """Protected regions cover every named Markdown and technical category."""

    def setUp(self):
        self.registry = load_registry()

    def test_markdown_fixture_covers_all_named_categories(self):
        regions = repair.protected_regions(MARKDOWN_SOURCE)
        categories = {region["category"] for region in regions}
        for category in ("heading", "code_block", "quoted", "url", "table",
                         "blockquote"):
            self.assertIn(category, categories)

    def test_yaml_and_json_fences_are_labelled_blocks(self):
        text = "```yaml\nreplicas: 3\n```\n\n```json\n{\"a\": 1}\n```\n"
        categories = {region["category"]
                      for region in repair.protected_regions(text)}
        self.assertIn("yaml_block", categories)
        self.assertIn("json_block", categories)

    def test_markdown_link_and_command_are_protected(self):
        text = ("See [the docs](https://example.com) or run `$ deploy now` "
                "from the shell.\n")
        regions = repair.protected_regions(text)
        self.assertTrue(any(region["category"] == "markdown_link"
                            for region in regions))

    def test_regions_are_sorted_and_non_overlapping(self):
        regions = repair.protected_regions(MARKDOWN_SOURCE)
        previous_end = 0
        for region in regions:
            self.assertGreaterEqual(region["start"], previous_end)
            previous_end = region["end"]

    def test_fidelity_base_spans_are_included(self):
        text = "We utilize the API and wait up to 10 ms."
        categories = {region["category"]
                      for region in repair.protected_regions(text)}
        self.assertIn("number", categories)
        self.assertIn("unit", categories)


class TestExactPhraseRepair(unittest.TestCase):
    """A deterministic exact phrase repair records one replacement."""

    def setUp(self):
        self.registry = load_registry()

    def test_one_recorded_replacement(self):
        report = repair.repair_text("We utilize the API to fetch records.",
                                    self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["replacement_count"], 1)
        self.assertEqual(report["text"], "We use the API to fetch records.")

    def test_record_carries_all_required_fields(self):
        report = repair.repair_text("We utilize the API.", self.registry)
        record = report["replacements"][0]
        for field in ("rule_id", "span", "action", "original", "replacement",
                      "preservation", "unresolved"):
            self.assertIn(field, record)
        self.assertEqual(record["rule_id"], "vocab-utilize")
        self.assertEqual(record["action"], "replace")
        self.assertEqual(record["original"], "utilize")
        self.assertEqual(record["replacement"], "use")
        self.assertEqual(record["preservation"], "passed")
        self.assertFalse(record["unresolved"])

    def test_rule_without_literal_replacement_is_unresolved(self):
        report = repair.repair_text("It is fast \u2014 and simple.",
                                    self.registry)
        self.assertEqual(report["decision"], "no-change")
        self.assertEqual(report["text"],
                         "It is fast \u2014 and simple.")

    def test_repair_is_idempotent(self):
        source = "We utilize the API and then utilize the SDK."
        first = repair.repair_text(source, self.registry)
        second = repair.repair_text(first["text"], self.registry)
        self.assertEqual(first["text"], second["text"])
        self.assertEqual(second["decision"], "no-change")
        self.assertEqual(second["replacement_count"], 0)


class TestProtectedSpansStayByteIdentical(unittest.TestCase):
    """Protected regions in a Markdown document are untouched by a repair."""

    def setUp(self):
        self.registry = load_registry()

    def test_markdown_document_repairs_prose_only(self):
        report = repair.repair_text(MARKDOWN_SOURCE, self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["replacement_count"], 1)
        for region in report["protected_regions"]:
            cand_start = repair._source_to_candidate_offset(
                report["replacements"], region["start"])
            cand_end = repair._source_to_candidate_offset(
                report["replacements"], region["end"])
            self.assertEqual(
                report["text"][cand_start:cand_end],
                MARKDOWN_SOURCE[region["start"]:region["end"]],
                region["category"])

    def test_ban_inside_table_and_quote_is_kept_unresolved(self):
        report = repair.repair_text(MARKDOWN_SOURCE, self.registry)
        unresolved = [record for record in report["replacements"]
                      if record.get("unresolved")]
        self.assertTrue(all(record["rule_id"] == "vocab-utilize"
                            for record in unresolved))
        self.assertGreaterEqual(len(unresolved), 2)

    def test_gate_reports_no_protected_span_changes(self):
        report = repair.repair_text(MARKDOWN_SOURCE, self.registry)
        protected = report["preservation"]["protected_spans"]
        self.assertEqual(protected["changed"], [])
        self.assertEqual(protected["removed"], [])
        self.assertEqual(protected["byte_identical"], protected["total"])


class TestStructuralSplit(unittest.TestCase):
    """Structural repair fires only for the supported deterministic split."""

    def setUp(self):
        self.registry = load_registry()

    def test_split_retains_both_clauses_and_conjunction(self):
        source = ("The batch job stalled, the queue filled up, and the retry "
                  "loop doubled the load, but the worker eventually recovered.")
        report = repair.repair_text(source, self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["replacement_count"], 1)
        record = report["replacements"][0]
        self.assertEqual(record["rule_id"], "struct-overlong-sentence")
        self.assertEqual(record["action"], "split")
        self.assertEqual(
            report["text"],
            "The batch job stalled, the queue filled up, and the retry "
            "loop doubled the load. But the worker eventually recovered.")
        self.assertIn("stalled", report["text"])
        self.assertIn("recovered", report["text"])
        self.assertIn(". But ", report["text"])

    def test_split_passes_the_fidelity_gate(self):
        source = ("The batch job stalled, the queue filled up, and the retry "
                  "loop doubled the load, but the worker eventually recovered.")
        report = repair.repair_text(source, self.registry)
        self.assertEqual(report["fidelity"]["decision"], "accept")
        self.assertEqual(report["preservation"]["status"], "passed")

    def test_no_split_for_a_short_sentence(self):
        report = repair.repair_text("The worker lost its lease.", self.registry)
        self.assertEqual(report["decision"], "no-change")
        self.assertNotIn("struct-overlong-sentence",
                         [record["rule_id"]
                          for record in report["replacements"]])

    def test_split_is_idempotent(self):
        source = ("The batch job stalled, the queue filled up, and the retry "
                  "loop doubled the load, but the worker eventually recovered.")
        first = repair.repair_text(source, self.registry)
        second = repair.repair_text(first["text"], self.registry)
        self.assertEqual(first["text"], second["text"])
        self.assertEqual(second["replacement_count"], 0)


class TestLeakedReasoningIntegrity(unittest.TestCase):
    """Leaked reasoning wrappers are integrity findings: removed outside
    quoted or code material, kept inside it."""

    def setUp(self):
        self.registry = load_registry()

    def test_outside_removed_and_inside_quote_kept(self):
        source = ('Let me think about this step by step. We utilize the API. '
                  'He said, "Let me think about this step by step."')
        report = repair.repair_text(source, self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["integrity"]["removed_count"], 1)
        self.assertEqual(report["integrity"]["kept_count"], 1)
        self.assertEqual(report["text"],
                         'We use the API. He said, "Let me think about '
                         'this step by step."')

    def test_wrapper_inside_inline_code_is_kept(self):
        source = "Run `Let me think about this step by step` now."
        report = repair.repair_text(source, self.registry)
        self.assertEqual(report["integrity"]["removed_count"], 0)
        self.assertEqual(report["integrity"]["kept_count"], 1)

    def test_wrapper_inside_code_fence_is_kept(self):
        source = "```\n# Let me think about this step by step\n```\n"
        report = repair.repair_text(source, self.registry)
        self.assertEqual(report["integrity"]["removed_count"], 0)
        self.assertEqual(report["integrity"]["kept_count"], 1)

    def test_removal_is_idempotent(self):
        source = "Let me think about this step by step. We utilize the API."
        first = repair.repair_text(source, self.registry)
        second = repair.repair_text(first["text"], self.registry)
        self.assertEqual(first["text"], second["text"])
        self.assertEqual(second["integrity"]["removed_count"], 0)

    def test_tag_scan_short_circuits_without_closing_tags(self):
        # No closing wrapper exists anywhere, so the tag scan must not run its
        # bounded-body search over every opening tag (linear guard).
        source = "<thought " * 20000
        matches = repair._integrity_matches(source, [])
        self.assertEqual(matches, [])

    def test_tag_scan_still_matches_when_closing_tag_present(self):
        source = "We <thinking>should not do this</thinking> now."
        matches = repair._integrity_matches(source, [])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["value"],
                         "<thinking>should not do this</thinking>")

    def test_tag_scan_bounds_malformed_opening_tags_with_a_closer(self):
        source = ("<thought " + ("x" * 500) + " ") * 5000 + "</thought>"
        matches = repair._integrity_matches(source, [])
        self.assertEqual(matches, [])

    def test_tag_scan_accepts_reasonable_attributes(self):
        source = '<thinking class="private">remove this</thinking>'
        matches = repair._integrity_matches(source, [])
        self.assertEqual([match["value"] for match in matches], [source])


class TestProfileRepair(unittest.TestCase):
    """Literal domain terms are not rewritten under the technical profile."""

    def setUp(self):
        self.registry = load_registry()

    def test_general_profile_rewrites_domain_term(self):
        report = repair.repair_text("The service is robust.", self.registry,
                                    profile="general")
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["text"], "The service is reliable.")

    def test_technical_profile_keeps_domain_terms(self):
        report = repair.repair_text("The service is robust and significant.",
                                    self.registry, profile="technical")
        self.assertEqual(report["decision"], "no-change")
        self.assertEqual(report["replacement_count"], 0)
        self.assertEqual(report["text"], "The service is robust and significant.")

    def test_profile_gate_is_observed_in_records(self):
        report = repair.repair_text("The service is robust.", self.registry,
                                    profile="technical")
        self.assertEqual(report["replacements"], [])


class TestProposedRepairGate(unittest.TestCase):
    """A proposed repair that changes a protected value fails and never writes."""

    def setUp(self):
        self.registry = load_registry()

    def test_number_change_rejects(self):
        report = repair.repair_proposal(
            "The fix cut deploy time to 40 minutes.",
            [{"start": 27, "end": 29, "replacement": "50"}], self.registry)
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["preservation"]["status"], "failed")
        self.assertTrue(report["replacements"][0]["unresolved"])
        self.assertEqual(report["replacements"][0]["preservation"], "failed")

    def test_oversize_source_rejected_before_region_extraction(self):
        source = "x" * (repair.limits.MAX_INPUT_CHARS + 1)
        with mock.patch.object(
                repair, "protected_regions",
                side_effect=AssertionError("preprocessing reached")):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                repair.repair_proposal(
                    source,
                    [{"start": 0, "end": 1, "replacement": "y"}],
                    self.registry)

    def test_qualifier_change_rejects(self):
        report = repair.repair_proposal(
            "The call completes in about 40 ms.",
            [{"start": 22, "end": 27, "replacement": "roughly"}],
            self.registry)
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["preservation"]["status"], "failed")

    def test_safe_proposal_is_accepted(self):
        report = repair.repair_proposal(
            "We utilize the API.",
            [{"start": 3, "end": 10, "replacement": "use"}], self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["text"], "We use the API.")

    def test_invalid_span_is_rejected(self):
        with self.assertRaises(ValueError):
            repair.repair_proposal(
                "We utilize the API.",
                [{"start": 3, "end": 3, "replacement": ""}], self.registry)


class TestCleanProseNoChange(unittest.TestCase):
    """Clean prose produces no repair and no invented work."""

    def setUp(self):
        self.registry = load_registry()

    def test_clean_prose_no_change(self):
        report = repair.repair_text(
            "The worker lost its lease and the queue drained the backlog "
            "overnight.", self.registry)
        self.assertEqual(report["decision"], "no-change")
        self.assertEqual(report["replacement_count"], 0)
        self.assertFalse(report["edited"])


class TestReportBoundaries(unittest.TestCase):
    """The report never claims authorship and never adds an em-dash allowance."""

    def setUp(self):
        self.registry = load_registry()

    def test_report_is_json_serializable_with_expected_schema(self):
        report = repair.repair_text("We utilize the API.", self.registry)
        json.dumps(report)
        for key in ("interface", "schema", "version", "decision",
                    "replacement_count", "replacements", "integrity",
                    "protected_regions", "preservation", "fidelity", "risk",
                    "text", "meta"):
            self.assertIn(key, report)
        self.assertEqual(report["version"], "3.0.0")

    def test_risk_is_advisory_never_authorship_evidence(self):
        report = repair.repair_text("We utilize the API.", self.registry)
        self.assertTrue(report["risk"]["advisory"])
        self.assertFalse(report["risk"]["authorship_evidence"])

    def test_disclaimer_present(self):
        report = repair.repair_text("We utilize the API.", self.registry)
        self.assertIn("never prove", report["meta"]["disclaimer"])

    def test_no_em_dash_allowance(self):
        report = repair.repair_text("It is fast \u2014 and simple.",
                                    self.registry)
        self.assertEqual(report["text"], "It is fast \u2014 and simple.")
        self.assertIn("\u2014", report["text"])


class TestFixtureSchema(unittest.TestCase):
    """The repair fixture schema validates decisions, edits, and records."""

    def setUp(self):
        self.registry = load_registry()

    def test_valid_fixture_has_no_schema_errors(self):
        errors = repair.validate_repair_fixture(make_fixture(), set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = repair.validate_repair_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_expected_decision_must_be_valid(self):
        errors = repair.validate_repair_fixture(
            make_fixture(expected_decision="rewrite"), set())
        self.assertTrue(any("expected_decision must be one of" in error
                            for error in errors))

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        repair.validate_repair_fixture(make_fixture(), seen)
        errors = repair.validate_repair_fixture(make_fixture(), seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))

    def test_profile_must_be_valid(self):
        errors = repair.validate_repair_fixture(
            make_fixture(profile="essay"), set())
        self.assertTrue(any("profile must be one of" in error
                            for error in errors))

    def test_proposed_edit_fields_must_be_valid(self):
        errors = repair.validate_repair_fixture(
            make_fixture(proposed_edits=[{"start": "x", "end": 5,
                                          "replacement": 3}]), set())
        self.assertTrue(any("proposed_edits[0].start must be an integer"
                            in error for error in errors))
        self.assertTrue(any("proposed_edits[0].replacement must be a string"
                            in error for error in errors))


class TestProductionCorpus(unittest.TestCase):
    """The production repair corpus passes end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = repair.run_repair_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "repair-markdown-prose-and-protected-regions",
            "repair-exact-phrase-one-replacement",
            "repair-structural-split-retains-clauses",
            "repair-proposed-number-change-fails",
            "repair-leaked-reasoning-outside-removed-inside-kept",
            "repair-technical-profile-keeps-domain-terms",
            "repair-general-profile-rewrites-domain-terms",
        }
        self.assertEqual(ids & required, required)

    def test_fixtures_cover_every_decision(self):
        decisions = {fixture["expected_decision"]
                     for fixture in load_fixtures()}
        self.assertEqual(decisions, {"accept", "no-change", "reject"})

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestCliInterface(unittest.TestCase):
    """The command accepts stdin and one file and never writes without a flag."""

    def setUp(self):
        self.registry = load_registry()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "doc.md")

    def write_doc(self, text):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def read_doc(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_stdin_accepts_input_without_a_file(self):
        rc, out, _err = run_repair_cli(input_text="We utilize the API.")
        self.assertEqual(rc, 0)
        self.assertIn("We use the API.", out)

    def test_file_is_not_changed_without_write_flag(self):
        self.write_doc("We utilize the API.\n")
        rc, out, _err = run_repair_cli("--file", self.path)
        self.assertEqual(rc, 0)
        self.assertEqual(self.read_doc(), "We utilize the API.\n")

    def test_write_flag_changes_the_file(self):
        self.write_doc("We utilize the API.\n")
        os.chmod(self.path, 0o640)
        rc, _out, _err = run_repair_cli("--file", self.path, "--write")
        self.assertEqual(rc, 0)
        self.assertEqual(self.read_doc(), "We use the API.\n")
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o640)

    def test_atomic_write_preserves_special_mode_bits(self):
        self.write_doc("original\n")
        os.chmod(self.path, 0o4755)
        if os.stat(self.path).st_mode & 0o7777 != 0o4755:
            self.skipTest("filesystem does not retain setuid mode bits")
        repair.atomic_write_text(self.path, "replacement\n")
        self.assertEqual(os.stat(self.path).st_mode & 0o7777, 0o4755)

    def test_atomic_write_failure_preserves_the_original(self):
        self.write_doc("original\n")
        with mock.patch.object(repair.os, "replace",
                               side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                repair.atomic_write_text(self.path, "replacement\n")
        self.assertEqual(self.read_doc(), "original\n")
        self.assertEqual(os.listdir(self.tmp.name), ["doc.md"])

    def test_dry_run_never_writes_even_with_write(self):
        self.write_doc("We utilize the API.\n")
        rc, _out, _err = run_repair_cli("--file", self.path, "--write",
                                        "--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual(self.read_doc(), "We utilize the API.\n")

    def test_diff_mode_never_writes_even_with_write(self):
        self.write_doc("We utilize the API.\n")
        rc, out, _err = run_repair_cli("--file", self.path, "--write",
                                       "--format", "diff")
        self.assertEqual(rc, 0)
        self.assertIn("-We utilize", out)
        self.assertIn("+We use", out)
        self.assertEqual(self.read_doc(), "We utilize the API.\n")

    def test_json_output_records_replacement(self):
        rc, out, _err = run_repair_cli("--format", "json",
                                       input_text="We utilize the API.")
        self.assertEqual(rc, 0)
        report = json.loads(out)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["replacements"][0]["rule_id"],
                         "vocab-utilize")

    def test_failed_preservation_prevents_write_and_returns_nonzero(self):
        self.write_doc("The fix cut deploy time to 40 minutes.\n")
        rc, _out, _err = run_repair_cli("--file", self.path,
                                        "--edit", "27-29=50", "--write")
        self.assertEqual(rc, 1)
        self.assertEqual(self.read_doc(),
                         "The fix cut deploy time to 40 minutes.\n")

    def test_two_dry_runs_return_identical_output(self):
        source = ("Let me think about this step by step. We utilize the API. "
                  "The batch job stalled, the queue filled up, and the retry "
                  "loop doubled the load, but the worker recovered.")
        rc1, out1, _err1 = run_repair_cli("--format", "json",
                                          input_text=source)
        rc2, out2, _err2 = run_repair_cli("--format", "json",
                                          input_text=source)
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        self.assertEqual(out1, out2)

    def test_missing_file_is_a_usage_error(self):
        rc, _out, _err = run_repair_cli("--file",
                                        os.path.join(self.tmp.name, "nope.md"))
        self.assertEqual(rc, 2)

    def test_fixture_corpus_exits_zero(self):
        rc, _out, _err = run_repair_cli(
            "--fixtures", "skills/antislop/evals/repair-fixtures.json")
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
