#!/usr/bin/env python3
"""Tests for the Humanizer Stack staged scan (issue #98).

Covers the acceptance criteria:
  - surface and structural results are separate and machine-readable
  - strict findings affect the exit status; advisory findings do not unless
    configured
  - fenced and inline code are masked for prose-only checks
  - structural output is bounded and can return no intervention
  - corpus-shape analysis requires two or more explicit user-supplied
    documents
  - a single document never triggers a cross-document convergence claim
  - every repair reruns both stages and reports residual findings

Run: python3 -m unittest tests/test_staged_scan.py -v
"""

import json
import re
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import scan  # noqa: E402
import repair  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "staged-scan-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
SCAN = os.path.join(ROOT, "scan.py")
VALIDATE = os.path.join(ROOT, "validate.py")

UNIFORM_PLUS_EM_DASH = (
    "The parser validates every incoming request before the handler thread "
    "begins its work. "
    "The worker drains the pending queue and writes a complete audit record "
    "for each task. "
    "The scheduler retries each failed job \u2014 with a fixed exponential "
    "backoff policy applied. "
    "The gateway checks the bearer token and enforces the per-tenant quota "
    "before accepting. "
    "The runner collects the finished results and posts them to the shared "
    "durable store."
)

CLEAN_DOCUMENT = (
    "We switched from VMs to containers three years ago. It cut our deploy "
    "time by 40% and eliminated half our infrastructure headaches. We spent "
    "six months fixing our logging and monitoring first."
)

CODE_MASKED_SOURCE = (
    "```python\n"
    "result = utilize()\n"
    "```\n\n"
    "We utilize the API and run `utilize()` here."
)

SAME_SHAPE_DOCS = [
    ("launch-one", (
        "Every launch looked the same until the demo broke. The room went "
        "quiet and the clicker jammed.\n\n"
        "Then the backup laptop saved the talk. I learned that rehearsing "
        "with the real hardware changes everything. We shipped the next "
        "release with a dry run first.")),
    ("launch-two", (
        "Every launch looked the same until the demo froze. The room went "
        "silent and the remote jammed.\n\n"
        "Then the backup machine carried the talk. I learned that rehearsing "
        "on the real hardware changes everything. We shipped the next "
        "release with a full dry run first.")),
    ("launch-three", (
        "Every launch looked the same until the demo crashed. The room fell "
        "silent and the clicker stopped.\n\n"
        "Then the backup laptop finished the talk. I learned that rehearsing "
        "against the real hardware changes everything. We shipped the next "
        "release with one full dry run first.")),
]

DISTINCT_DOCS = [
    ("build-move", (
        "We moved the build to a faster cluster and cut wait times by a "
        "third.\n\n"
        "The rollout went out in stages. Operators watched the queue and "
        "rolled back twice. The final cut took four minutes and the fleet "
        "stayed healthy.")),
    ("interview-loop", (
        "Our interview loop changed when we added a take-home task.\n\n"
        "Candidates now show real work before the panel meets. We compare "
        "the result against a rubric and check for copied patterns.")),
    ("shed-rebuild", (
        "The garden shed collapsed after the winter storms.\n\n"
        "We rebuilt it with treated timber and a deeper footing. The new "
        "frame has lasted two seasons without a sag.")),
]


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def run_scan_cli(*args, input_text=None):
    result = subprocess.run([sys.executable, SCAN] + list(args),
                            capture_output=True, text=True, cwd=ROOT,
                            input=input_text)
    return result.returncode, result.stdout, result.stderr


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestSeparateStages(unittest.TestCase):
    """Surface, structural, and aggregate boundaries remain separate."""

    def setUp(self):
        self.registry = load_registry()

    def test_later_document_reads_only_the_remaining_budget(self):
        first = "a" * 600_000
        with mock.patch.object(
                scan.limits, "read_text_file",
                side_effect=(first, ValueError("documents exceed limit"))) as read:
            with self.assertRaisesRegex(ValueError, "documents exceed"):
                scan._read_documents(("first.md", "second.md"))
        self.assertEqual(read.call_args_list[0].kwargs["max_chars"],
                         scan.limits.MAX_INPUT_CHARS)
        self.assertEqual(read.call_args_list[1].kwargs["max_chars"], 400_000)

    def test_report_is_machine_readable_json(self):
        report = scan.scan_documents([("doc", CLEAN_DOCUMENT)], self.registry)
        json.dumps(report)
        for key in ("interface", "schema", "version", "documents", "corpus",
                    "signals", "meta"):
            self.assertIn(key, report)
        self.assertEqual(report["schema"], "staged-scan-report-1")
        self.assertEqual(report["version"], "3.0.0")

    def test_surface_and_structural_are_separate_sections(self):
        report = scan.scan_documents([("doc", UNIFORM_PLUS_EM_DASH)],
                                     self.registry)
        doc = report["documents"][0]
        self.assertIn("surface", doc)
        self.assertIn("structural", doc)
        self.assertEqual(doc["surface"]["strict_count"], 1)
        self.assertEqual(doc["structural"]["decision"], "intervene")

    def test_em_dash_is_a_strict_surface_finding(self):
        report = scan.scan_documents([("doc", UNIFORM_PLUS_EM_DASH)],
                                     self.registry)
        findings = report["documents"][0]["surface"]["findings"]
        signals = {finding["signal"] for finding in findings}
        rule_ids = {finding["rule_id"] for finding in findings}
        self.assertIn("strict", signals)
        self.assertIn("fmt-em-dash", rule_ids)

    def test_rhythm_concern_is_a_structural_intervention(self):
        report = scan.scan_documents([("doc", UNIFORM_PLUS_EM_DASH)],
                                     self.registry)
        interventions = report["documents"][0]["structural"]["interventions"]
        self.assertGreater(len(interventions), 0)
        self.assertIn("sentence", interventions[0]["rule_id"])


class TestExitStatus(unittest.TestCase):
    """Strict findings fail; advisory findings fail only when configured."""

    def setUp(self):
        self.registry = load_registry()

    def test_clean_document_exits_zero(self):
        rc, out, err = run_scan_cli("--profile", "general",
                                    input_text=CLEAN_DOCUMENT)
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertFalse(report["signals"]["strict_present"])

    def test_strict_finding_exits_one(self):
        rc, out, err = run_scan_cli("--profile", "general",
                                    input_text=UNIFORM_PLUS_EM_DASH)
        self.assertEqual(rc, 1, err)
        report = json.loads(out)
        self.assertTrue(report["signals"]["strict_present"])

    def test_advisory_only_exits_zero(self):
        rc, out, err = run_scan_cli("--profile", "general",
                                    input_text=(
                                        "The parser reads the config. The "
                                        "parser builds the graph. The parser "
                                        "runs the query. The parser writes "
                                        "the output. The parser handles "
                                        "errors. The parser exits cleanly."))
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertFalse(report["signals"]["strict_present"])
        self.assertTrue(report["signals"]["advisory_present"])

    def test_advisory_fails_when_configured(self):
        rc, out, err = run_scan_cli("--profile", "general",
                                    "--fail-on-advisory",
                                    input_text=(
                                        "The parser reads the config. The "
                                        "parser builds the graph. The parser "
                                        "runs the query. The parser writes "
                                        "the output. The parser handles "
                                        "errors. The parser exits cleanly."))
        self.assertEqual(rc, 1, err)

    def test_exit_status_function_matches_cli(self):
        self.registry = load_registry()
        clean = scan.scan_documents([("doc", CLEAN_DOCUMENT)], self.registry)
        self.assertEqual(scan.exit_status(clean), 0)
        strict = scan.scan_documents([("doc", UNIFORM_PLUS_EM_DASH)],
                                     self.registry)
        self.assertEqual(scan.exit_status(strict), 1)
        advisory = scan.scan_documents(
            [("doc", ("The parser reads the config. The parser builds the "
                      "graph. The parser runs the query. The parser writes "
                      "the output. The parser handles errors. The parser "
                      "exits cleanly."))], self.registry)
        self.assertEqual(scan.exit_status(advisory), 0)
        self.assertEqual(scan.exit_status(advisory, fail_on_advisory=True), 1)


class TestCodeMasking(unittest.TestCase):
    """Fenced and inline code are masked for prose-only checks."""

    def setUp(self):
        self.registry = load_registry()

    def test_banned_word_in_code_is_not_a_finding(self):
        report = scan.scan_documents([("doc", CODE_MASKED_SOURCE)],
                                     self.registry)
        doc = report["documents"][0]
        findings = doc["surface"]["findings"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "vocab-utilize")
        start = findings[0]["span"][0]
        self.assertEqual(CODE_MASKED_SOURCE[start:start + 7], "utilize")
        self.assertNotIn("```", CODE_MASKED_SOURCE[start - 4:start])

    def test_masking_preserves_offsets(self):
        masked = scan.mask_code(CODE_MASKED_SOURCE)
        self.assertEqual(len(masked), len(CODE_MASKED_SOURCE))
        self.assertIn("We utilize the API", masked)
        self.assertNotIn("utilize()", masked)

    def test_masking_removes_code_occurrences(self):
        report = scan.scan_documents([("doc", CODE_MASKED_SOURCE)],
                                     self.registry)
        findings = report["documents"][0]["surface"]["findings"]
        self.assertEqual(len(findings), 1)
        raw_occurrences = len(re.findall(r"\butilize\b", CODE_MASKED_SOURCE))
        self.assertEqual(raw_occurrences, 3)
        self.assertEqual(findings[0]["rule_id"], "vocab-utilize")


class TestBoundedStructural(unittest.TestCase):
    """Structural output is bounded and can return no intervention."""

    def setUp(self):
        self.registry = load_registry()

    def test_no_intervention_for_clean_document(self):
        report = scan.scan_documents([("doc", CLEAN_DOCUMENT)], self.registry)
        structural = report["documents"][0]["structural"]
        self.assertEqual(structural["decision"], "no-change")
        self.assertEqual(structural["count"], 0)
        self.assertEqual(structural["interventions"], [])

    def test_interventions_never_exceed_two(self):
        text = (
            "Furthermore, the cache warms on boot. Furthermore, the index "
            "rebuilds nightly. Furthermore, the queue drains cleanly on "
            "shutdown. "
            "The parser validates every incoming request before the handler "
            "thread begins its work. The worker drains the pending queue and "
            "writes a complete audit record for each task. The scheduler "
            "retries each failed job with a fixed exponential backoff "
            "policy applied."
        )
        report = scan.scan_documents([("doc", text)], self.registry)
        structural = report["documents"][0]["structural"]
        self.assertLessEqual(structural["count"],
                             structural["max_interventions"])
        self.assertLessEqual(len(structural["interventions"]), 2)

    def test_report_carries_the_bound(self):
        report = scan.scan_documents([("doc", CLEAN_DOCUMENT)], self.registry)
        self.assertEqual(
            report["documents"][0]["structural"]["max_interventions"], 2)


class TestCorpusAnalysis(unittest.TestCase):
    """Corpus-shape analysis needs multiple documents and never claims
    convergence for a single one."""

    def setUp(self):
        self.registry = load_registry()

    def test_three_same_shape_documents_converge(self):
        report = scan.scan_documents(SAME_SHAPE_DOCS, self.registry)
        self.assertEqual(report["corpus"]["state"], "convergence")
        self.assertEqual(len(report["corpus"]["convergence_findings"]), 3)
        for finding in report["corpus"]["convergence_findings"]:
            self.assertIn("hook", finding["matched_slots"])
            self.assertIn("close", finding["matched_slots"])
            self.assertEqual(finding["signal"], "advisory")

    def test_three_distinct_documents_do_not_converge(self):
        report = scan.scan_documents(DISTINCT_DOCS, self.registry)
        self.assertEqual(report["corpus"]["state"], "no-convergence")
        self.assertEqual(report["corpus"]["convergence_findings"], [])

    def test_single_document_requires_multiple_documents(self):
        report = scan.scan_documents([("one", CLEAN_DOCUMENT)], self.registry)
        self.assertEqual(report["corpus"]["state"],
                         "requires-multiple-documents")
        self.assertEqual(report["corpus"]["convergence_findings"], [])
        self.assertEqual(report["mode"], "scan")

    def test_single_document_never_claims_convergence(self):
        for text in (CLEAN_DOCUMENT, SAME_SHAPE_DOCS[0][1]):
            report = scan.scan_documents([("one", text)], self.registry)
            self.assertEqual(report["corpus"]["state"],
                             "requires-multiple-documents")
            self.assertFalse(report["signals"]["convergence_present"])

    def test_corpus_mode_reports_each_document_separately(self):
        report = scan.scan_documents(SAME_SHAPE_DOCS, self.registry)
        self.assertEqual(report["mode"], "corpus")
        self.assertEqual(len(report["documents"]), 3)
        for doc in report["documents"]:
            self.assertIn("surface", doc)
            self.assertIn("structural", doc)


class TestResidualScanInRepair(unittest.TestCase):
    """Every repair reruns both stages and reports residual findings."""

    def setUp(self):
        self.registry = load_registry()

    def test_repair_report_carries_residual_scan(self):
        report = repair.repair_text("We utilize the API.", self.registry)
        self.assertIn("residual_scan", report)
        residual = report["residual_scan"]
        self.assertIn("surface", residual)
        self.assertIn("structural", residual)
        self.assertEqual(residual["surface"]["strict_count"], 0)
        self.assertEqual(residual["surface"]["advisory_count"], 0)

    def test_residual_scan_reports_surviving_strict_findings(self):
        report = repair.repair_text(
            "We utilize the API \u2014 and run it.", self.registry)
        residual = report["residual_scan"]
        rule_ids = {finding["rule_id"]
                    for finding in residual["surface"]["findings"]}
        self.assertIn("fmt-em-dash", rule_ids)
        self.assertGreaterEqual(residual["surface"]["strict_count"], 1)

    def test_proposed_repair_report_carries_residual_scan(self):
        report = repair.repair_proposal(
            "We utilize the API.",
            [{"start": 3, "end": 10, "replacement": "use"}], self.registry)
        self.assertIn("residual_scan", report)
        self.assertEqual(report["residual_scan"]["surface"]["strict_count"], 0)


class TestFixtureSchema(unittest.TestCase):
    """The staged-scan fixture schema validates sources, corpora, and stages."""

    def setUp(self):
        self.registry = load_registry()

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = scan.validate_staged_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_missing_source_and_corpus_is_rejected(self):
        errors = scan.validate_staged_fixture(
            {"id": "empty", "profile": "general"}, set())
        self.assertTrue(any("needs a non-empty 'source'" in error
                            for error in errors))

    def test_single_document_corpus_is_rejected(self):
        errors = scan.validate_staged_fixture(
            {"id": "single", "corpus": [{"id": "a", "text": "Only one."}]},
            set())
        self.assertTrue(any("at least two documents" in error
                            for error in errors))

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        scan.validate_staged_fixture({"id": "dup", "source": "Text."}, seen)
        errors = scan.validate_staged_fixture(
            {"id": "dup", "source": "Text."}, seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))

    def test_invalid_structural_decision_is_rejected(self):
        errors = scan.validate_staged_fixture(
            {"id": "bad", "source": "Text.",
             "expected_structural_decision": "rewrite"}, set())
        self.assertTrue(any("expected_structural_decision must be one of"
                            in error for error in errors))

    def test_structural_rule_id_expectations_are_validated(self):
        errors = scan.validate_staged_fixture({
            "id": "bad-rule-ids",
            "source": "A short source.",
            "expected_structural_rule_ids": ["fmt-emojis", "fmt-emojis"],
        }, set())
        self.assertTrue(any("expected_structural_rule_ids" in error
                            for error in errors))


class TestProductionCorpus(unittest.TestCase):
    """The production staged-scan corpus passes end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = scan.run_staged_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "scan-strict-punctuation-advisory-rhythm",
            "scan-clean-document-no-structural-work",
            "scan-code-masked-for-prose-checks",
            "corpus-same-shape-converges",
            "corpus-distinct-shapes-no-convergence",
        }
        self.assertEqual(ids & required, required)

    def test_fixtures_cover_both_corpus_states(self):
        states = {fixture["expected_corpus_state"]
                  for fixture in load_fixtures()
                  if fixture.get("expected_corpus_state")}
        self.assertEqual(states, {"convergence", "no-convergence"})

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestCliInterface(unittest.TestCase):
    """The command accepts stdin, one file, and a multi-document corpus."""

    def test_stdin_accepts_input_without_a_file(self):
        rc, out, err = run_scan_cli("--profile", "general",
                                    input_text=CLEAN_DOCUMENT)
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertEqual(report["document_count"], 1)
        self.assertEqual(report["corpus"]["state"],
                         "requires-multiple-documents")

    def test_fixture_corpus_exits_zero(self):
        rc, out, err = run_scan_cli(
            "--fixtures", "skills/antislop/evals/staged-scan-fixtures.json")
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertTrue(report["gate_pass"])

    def test_single_doc_flag_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(CLEAN_DOCUMENT)
            rc, out, err = run_scan_cli("--doc", path)
        self.assertEqual(rc, 2, err)
        self.assertIn("at least two documents", out)

    def test_missing_file_is_a_usage_error(self):
        rc, out, err = run_scan_cli("--file", os.path.join(ROOT, "nope.md"))
        self.assertEqual(rc, 2, err)


if __name__ == "__main__":
    unittest.main()
