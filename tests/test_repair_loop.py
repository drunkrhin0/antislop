#!/usr/bin/env python3
"""Tests for the Lynote-adapted bounded repair loop (issue #93).

Covers the acceptance criteria:
  - each attempt names input findings, selected spans, correction IDs,
    output findings, fidelity result, and decision
  - unaffected spans are never sent through broad rewriting
  - a retry happens only when the target finding remains and fidelity still
    passes
  - retry count and the changed-character budget are strictly bounded
  - any fidelity or integrity failure rolls back immediately
  - advisory rhythm diagnostics are reported separately and never decide
    whether a passage is human
  - the loop runs entirely from fixed local fixtures with no external model
    or service, and the trace proves no detector adapter, translation step,
    or network call ran
  - the loop leaves already clean text unchanged

Run: python3 -m unittest tests/test_repair_loop.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import repair_loop  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "repair-loop-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
REPAIR_LOOP = os.path.join(ROOT, "tools", "repair_loop.py")
VALIDATE = os.path.join(ROOT, "tools", "validate.py")

CLEAN = ("The worker lost its lease and the queue drained the backlog "
         "overnight.")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def make_fixture(rid="repair-loop-test", **overrides):
    fixture = {
        "id": rid,
        "source": "We utilize the API to fetch records.",
        "expected_decision": "accept",
    }
    fixture.update(overrides)
    return fixture


def run_loop_cli(*args, input_text=None):
    result = subprocess.run([sys.executable, REPAIR_LOOP] + list(args),
                            capture_output=True, text=True, cwd=ROOT,
                            input=input_text)
    return result.returncode, result.stdout, result.stderr


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestFirstAttemptAccept(unittest.TestCase):
    """A single phrase finding is repaired on the first attempt."""

    def setUp(self):
        self.registry = load_registry()

    def test_one_finding_accepted_on_first_attempt(self):
        report = repair_loop.run_repair_loop(
            "We utilize the API to fetch records.", self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["attempt_count"], 1)
        self.assertEqual(report["retry_count"], 0)
        self.assertEqual(report["text"], "We use the API to fetch records.")

    def test_attempt_trace_names_every_stage(self):
        report = repair_loop.run_repair_loop("We utilize the API.", self.registry)
        trace = report["attempts"][0]
        for field in ("attempt", "input_findings", "selected_spans",
                      "corrections", "output_findings", "fidelity",
                      "integrity", "decision", "target_findings_cleared"):
            self.assertIn(field, trace)
        self.assertEqual(trace["input_findings"][0]["rule_id"],
                         "vocab-utilize")
        self.assertEqual(trace["selected_spans"][0]["span"], [3, 10])
        self.assertEqual(trace["corrections"][0]["correction_id"],
                         "registry:vocab-utilize")
        self.assertEqual(trace["corrections"][0]["replacement"], "use")
        self.assertEqual(trace["output_findings"], [])
        self.assertTrue(trace["target_findings_cleared"])
        self.assertEqual(trace["fidelity"]["decision"], "accept")
        self.assertEqual(trace["decision"], "accept")

    def test_clean_loop_is_idempotent(self):
        first = repair_loop.run_repair_loop("We utilize the API.", self.registry)
        second = repair_loop.run_repair_loop(first["text"], self.registry)
        self.assertEqual(first["text"], second["text"])
        self.assertEqual(second["decision"], "no-change")
        self.assertEqual(second["attempt_count"], 0)


class TestTwoIndependentFindings(unittest.TestCase):
    """Two independent findings are repaired without touching between spans."""

    def setUp(self):
        self.registry = load_registry()

    def test_two_corrections_in_one_attempt(self):
        report = repair_loop.run_repair_loop(
            "We utilize the API and then leverage the SDK.", self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["attempt_count"], 1)
        rule_ids = [c["rule_id"] for c in report["attempts"][0]["corrections"]]
        self.assertIn("vocab-utilize", rule_ids)
        self.assertIn("vocab-leverage", rule_ids)
        self.assertEqual(report["text"],
                         "We use the API and then use the SDK.")

    def test_between_spans_are_never_rewritten(self):
        source = "We utilize the API and then leverage the SDK."
        report = repair_loop.run_repair_loop(source, self.registry)
        self.assertIn("the API and then", report["text"])

    def test_unaffected_spans_stay_byte_identical(self):
        source = ("We utilize the API and then leverage the SDK, "
                  "while the queue drains the backlog overnight.")
        report = repair_loop.run_repair_loop(source, self.registry)
        self.assertIn("the API and then", report["text"])
        self.assertIn("the queue drains the backlog overnight",
                      report["text"])

    def test_finding_inside_code_fence_is_never_rewritten(self):
        source = ("We utilize the API.\n\n```python\n"
                  "# We utilize the API in code\n```\n")
        report = repair_loop.run_repair_loop(source, self.registry)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["text"],
                         "We use the API.\n\n```python\n"
                         "# We utilize the API in code\n```\n")
        selected = report["attempts"][0]["selected_spans"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["span"], [3, 10])


class TestRetryPolicy(unittest.TestCase):
    """A retry happens only when the target finding remains and fidelity passes."""

    def setUp(self):
        self.registry = load_registry()

    RETRY_PLAN = [
        [{"rule_id": "vocab-utilize", "start": 3, "end": 10,
          "replacement": "use"}],
        [{"rule_id": "vocab-utilize", "replacement": "use"}],
    ]

    def test_target_remaining_with_fidelity_pass_retries_once(self):
        source = "We utilize the staging API and we utilize the SDK."
        report = repair_loop.run_repair_loop(source, self.registry,
                                             correction_plan=self.RETRY_PLAN)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["attempt_count"], 2)
        self.assertEqual(report["retry_count"], 1)
        self.assertEqual(report["text"],
                         "We use the staging API and we use the SDK.")
        first = report["attempts"][0]
        self.assertEqual(first["decision"], "retry")
        self.assertFalse(first["target_findings_cleared"])
        self.assertEqual(first["fidelity"]["decision"], "accept")
        self.assertEqual(first["reason"],
                         "target finding remains and fidelity still passes")
        second = report["attempts"][1]
        self.assertEqual(second["decision"], "accept")
        self.assertTrue(second["target_findings_cleared"])

    def test_retries_exhausted_roll_back(self):
        plan = [
            [{"rule_id": "vocab-utilize", "replacement": "Utilize"}],
            [{"rule_id": "vocab-utilize", "replacement": "Utilize"}],
        ]
        report = repair_loop.run_repair_loop("We utilize the API.",
                                             self.registry,
                                             correction_plan=plan)
        self.assertEqual(report["decision"], "rollback")
        self.assertEqual(report["attempt_count"], 2)
        self.assertEqual(report["retry_count"], 1)
        self.assertTrue(report["rollback"]["applied"])
        self.assertEqual(report["text"], "We utilize the API.")

    def test_accept_does_not_happen_while_target_remains(self):
        source = "We utilize the staging API and we utilize the SDK."
        report = repair_loop.run_repair_loop(
            source, self.registry, max_attempts=1,
            correction_plan=self.RETRY_PLAN)
        self.assertEqual(report["decision"], "rollback")
        self.assertEqual(report["text"], source)

    def test_retry_count_is_bounded(self):
        plan = [
            [{"rule_id": "vocab-utilize", "replacement": "Utilize"}],
            [{"rule_id": "vocab-utilize", "replacement": "Utilize"}],
            [{"rule_id": "vocab-utilize", "replacement": "use"}],
        ]
        report = repair_loop.run_repair_loop("We utilize the API.",
                                             self.registry,
                                             max_attempts=2,
                                             correction_plan=plan)
        self.assertEqual(report["attempt_count"], 2)
        self.assertEqual(report["retry_count"], 1)

    def test_partial_repair_rolls_back_when_next_attempt_has_no_correction(self):
        source = "We utilize the API and leverage the cache."
        report = repair_loop.run_repair_loop(
            source, self.registry,
            correction_plan=[
                [{"rule_id": "vocab-utilize", "replacement": "use"}],
                [],
            ],
        )
        self.assertEqual(report["decision"], "rollback")
        self.assertTrue(report["rollback"]["applied"])
        self.assertEqual(report["text"], source)


class TestRollbackOnFidelityFailure(unittest.TestCase):
    """Any fidelity or integrity failure rolls back immediately."""

    def setUp(self):
        self.registry = load_registry()

    def test_quantity_change_rolls_back(self):
        report = repair_loop.run_repair_loop(
            "The fix cut deploy time to 40 minutes.", self.registry,
            correction_plan=[[{"rule_id": "proposed", "start": 27,
                               "end": 29, "replacement": "50"}]])
        self.assertEqual(report["decision"], "rollback")
        self.assertEqual(report["attempt_count"], 1)
        self.assertTrue(report["rollback"]["applied"])
        self.assertEqual(report["text"],
                         "The fix cut deploy time to 40 minutes.")

    def test_date_change_rolls_back(self):
        report = repair_loop.run_repair_loop(
            "Ships on 2024-01-15.", self.registry,
            correction_plan=[[{"rule_id": "proposed", "start": 9,
                               "end": 19, "replacement": "2025-06-01"}]])
        self.assertEqual(report["decision"], "rollback")
        self.assertEqual(report["text"], "Ships on 2024-01-15.")

    def test_name_change_rolls_back(self):
        report = repair_loop.run_repair_loop(
            "According to NIST, the standard requires encryption.",
            self.registry,
            correction_plan=[[{"rule_id": "proposed", "start": 13,
                               "end": 17, "replacement": "IETF"}]])
        self.assertEqual(report["decision"], "rollback")
        self.assertEqual(report["attempts"][0]["fidelity"]["decision"],
                         "review")
        self.assertEqual(report["text"],
                         "According to NIST, the standard requires encryption.")

    def test_quote_change_rolls_back(self):
        report = repair_loop.run_repair_loop(
            'He said, "ship it".', self.registry,
            correction_plan=[[{"rule_id": "proposed", "start": 9,
                               "end": 18,
                               "replacement": '"ship it now"'}]])
        self.assertEqual(report["decision"], "rollback")
        self.assertEqual(report["text"], 'He said, "ship it".')

    def test_technical_term_change_rolls_back(self):
        report = repair_loop.run_repair_loop(
            "The service is SOC 2 compliant.", self.registry,
            required_terms=("SOC 2",),
            correction_plan=[[{"rule_id": "proposed", "start": 15,
                               "end": 20, "replacement": "ISO"}]])
        self.assertEqual(report["decision"], "rollback")
        self.assertEqual(report["text"], "The service is SOC 2 compliant.")

    def test_rollback_returns_the_source_unchanged(self):
        source = "Ships on 2024-01-15."
        report = repair_loop.run_repair_loop(
            source, self.registry,
            correction_plan=[[{"rule_id": "proposed", "start": 9,
                               "end": 19, "replacement": "2025-06-01"}]])
        self.assertEqual(report["text"], source)
        self.assertFalse(report["edited"])


class TestCharBudgetBound(unittest.TestCase):
    """The changed-character budget is a strict bound."""

    def setUp(self):
        self.registry = load_registry()

    def test_budget_exceeded_rolls_back(self):
        report = repair_loop.run_repair_loop(
            "We utilize the API to fetch records.", self.registry,
            char_budget=2)
        self.assertEqual(report["decision"], "rollback")
        self.assertTrue(report["budget_exceeded"])
        self.assertTrue(report["rollback"]["applied"])
        self.assertEqual(report["text"], "We utilize the API to fetch records.")

    def test_budget_is_reported_even_when_not_exceeded(self):
        report = repair_loop.run_repair_loop("We utilize the API.",
                                             self.registry)
        self.assertIsInstance(report["char_budget"], int)
        self.assertIs(report["budget_exceeded"], False)
        self.assertLessEqual(report["total_changed_chars"],
                             report["char_budget"])


class TestCleanNoOp(unittest.TestCase):
    """Clean text returns a no-op trace and is left unchanged."""

    def setUp(self):
        self.registry = load_registry()

    def test_clean_text_no_op_trace(self):
        report = repair_loop.run_repair_loop(CLEAN, self.registry)
        self.assertEqual(report["decision"], "no-change")
        self.assertEqual(report["attempt_count"], 0)
        self.assertEqual(report["retry_count"], 0)
        self.assertEqual(report["total_changed_chars"], 0)
        self.assertEqual(report["text"], CLEAN)
        self.assertFalse(report["edited"])
        self.assertFalse(report["rollback"]["applied"])

    def test_no_attempt_means_no_correction(self):
        report = repair_loop.run_repair_loop(CLEAN, self.registry)
        self.assertEqual(report["attempts"], [])
        self.assertEqual(report["input_findings"], [])


class TestAdvisoryRhythmNeverDecides(unittest.TestCase):
    """Rhythm diagnostics are advisory and never drive the decision."""

    def setUp(self):
        self.registry = load_registry()

    def test_rhythm_is_reported_separately_as_advisory(self):
        report = repair_loop.run_repair_loop("We utilize the API.",
                                             self.registry)
        advisory = report["advisory"]
        self.assertTrue(advisory["advisory_only"])
        self.assertTrue(advisory["never_decides_humanity"])
        self.assertFalse(advisory["authorship_evidence"])
        self.assertIn("avg_words_per_sentence",
                      advisory["rhythm"]["source"])
        self.assertIn("unique_word_ratio",
                      advisory["rhythm"]["candidate"])

    def test_identical_findings_with_different_rhythm_same_decision(self):
        short = "We utilize the API."
        long = ("We utilize the API, and the deployment pipeline handles "
                "releases regularly, while the queue drains the backlog "
                "overnight, and the worker retries the lease.")
        first = repair_loop.run_repair_loop(short, self.registry)
        second = repair_loop.run_repair_loop(long, self.registry)
        self.assertEqual(first["decision"], "accept")
        self.assertEqual(second["decision"], "accept")
        self.assertEqual(first["attempt_count"], second["attempt_count"])
        self.assertNotEqual(first["advisory"]["rhythm"]["source"],
                            second["advisory"]["rhythm"]["source"])


class TestNoAdapterTranslationNetwork(unittest.TestCase):
    """The trace proves no detector adapter, translation, or network call."""

    def setUp(self):
        self.registry = load_registry()

    def test_execution_flags_are_all_false(self):
        report = repair_loop.run_repair_loop("We utilize the API.",
                                             self.registry)
        execution = report["execution"]
        for flag in ("detector_adapter", "translation_step", "network_call",
                     "model_call"):
            self.assertFalse(execution[flag])

    def test_execution_section_present_on_clean_trace(self):
        report = repair_loop.run_repair_loop(CLEAN, self.registry)
        self.assertFalse(report["execution"]["detector_adapter"])
        self.assertFalse(report["execution"]["network_call"])


class TestReportShape(unittest.TestCase):
    """The report is serializable and carries the required sections."""

    def setUp(self):
        self.registry = load_registry()

    def test_report_is_json_serializable(self):
        report = repair_loop.run_repair_loop("We utilize the API.",
                                             self.registry)
        json.dumps(report)
        for key in ("interface", "schema", "version", "decision", "attempts",
                    "retry_count", "char_budget", "rollback", "advisory",
                    "execution", "text", "meta"):
            self.assertIn(key, report)
        self.assertEqual(report["version"], "3.0.0")

    def test_disclaimer_present(self):
        report = repair_loop.run_repair_loop("We utilize the API.",
                                             self.registry)
        self.assertIn("never prove", report["meta"]["disclaimer"])


class TestFixtureSchema(unittest.TestCase):
    """The repair-loop fixture schema validates."""

    def setUp(self):
        self.registry = load_registry()

    def test_valid_fixture_has_no_schema_errors(self):
        errors = repair_loop.validate_repair_loop_fixture(make_fixture(),
                                                          set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = repair_loop.validate_repair_loop_fixture(fixture, seen)
            self.assertEqual(errors, [], "%s: %s" % (fixture["id"], errors))

    def test_expected_decision_must_be_valid(self):
        errors = repair_loop.validate_repair_loop_fixture(
            make_fixture(expected_decision="rewrite"), set())
        self.assertTrue(any("expected_decision must be one of" in error
                            for error in errors))

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        repair_loop.validate_repair_loop_fixture(make_fixture(), seen)
        errors = repair_loop.validate_repair_loop_fixture(make_fixture(),
                                                          seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))

    def test_attempt_correction_fields_must_be_valid(self):
        errors = repair_loop.validate_repair_loop_fixture(
            make_fixture(attempt_corrections=[[
                {"rule_id": "", "replacement": 3, "start": "x"}
            ]]), set())
        self.assertTrue(any("missing non-empty 'rule_id'" in error
                            for error in errors))
        self.assertTrue(any("replacement must be a string" in error
                            for error in errors))
        self.assertTrue(any("start must be an integer" in error
                            for error in errors))

    def test_char_budget_must_be_positive(self):
        errors = repair_loop.validate_repair_loop_fixture(
            make_fixture(char_budget=0), set())
        self.assertTrue(any("char_budget must be a positive integer" in error
                            for error in errors))


class TestProductionCorpus(unittest.TestCase):
    """The production repair-loop corpus passes end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = repair_loop.run_repair_loop_corpus(load_fixtures(),
                                                    self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "repair-loop-one-phrase-first-attempt",
            "repair-loop-two-independent-findings",
            "repair-loop-retry-once",
            "repair-loop-quantity-change-rolls-back",
            "repair-loop-clean-no-op",
            "repair-loop-no-adapter-translation-network",
        }
        self.assertEqual(ids & required, required)

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestCliInterface(unittest.TestCase):
    """The command accepts stdin and a file and maps rollback to nonzero."""

    def setUp(self):
        self.tmp = os.path.join("/tmp", "repair-loop-cli-test")
        os.makedirs(self.tmp, exist_ok=True)
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", self.tmp]))
        self.path = os.path.join(self.tmp, "doc.md")

    def write_doc(self, text):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_stdin_accept_input(self):
        rc, out, _err = run_loop_cli(input_text="We utilize the API.")
        self.assertEqual(rc, 0)
        report = json.loads(out)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["text"], "We use the API.")

    def test_rollback_exits_nonzero(self):
        self.write_doc("Ships on 2024-01-15.")
        rc, out, _err = run_loop_cli("--file", self.path)
        self.assertEqual(rc, 0)

    def test_missing_file_is_usage_error(self):
        rc, _out, _err = run_loop_cli("--file",
                                      os.path.join(self.tmp, "nope.md"))
        self.assertEqual(rc, 2)

    def test_fixture_corpus_exits_zero(self):
        rc, _out, _err = run_loop_cli(
            "--fixtures", "skills/antislop/evals/repair-loop-fixtures.json")
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
