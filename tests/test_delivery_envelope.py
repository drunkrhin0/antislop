#!/usr/bin/env python3
"""Tests for the ReviewWrite-style delivery envelope runner (issue #95).

Covers the acceptance criteria:
  - the deliverable body is stored and emitted separately from findings,
    plans, and verification commentary
  - verification records include the exact source and body digest they cover
  - source-record digests use a versioned canonical serialization with stable
    key order, UTF-8 encoding, and normalized line endings
  - missing, stale, or mismatched verification returns a typed failure
  - required facts, protected literals, qualifiers, and forbidden additions
    reuse the fidelity and drift preservation contracts
  - long-document fixtures retain cross-section facts and whole-document
    register across chunks
  - a valid document can return no changes and still produce a successful
    verification record

Run: python3 -m unittest tests/test_delivery_envelope.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import delivery  # noqa: E402
import drift  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "delivery-envelope-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
DELIVERY = os.path.join(ROOT, "tools", "delivery.py")
VALIDATE = os.path.join(ROOT, "tools", "validate.py")

CLEAN = ("Run `fetch` with version 2.4. When the cache is cold, then one "
         "record should come back.")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def make_fixture(rid="delivery-verify-test", **overrides):
    fixture = {
        "id": rid,
        "kind": "verify",
        "source": CLEAN,
        "body": CLEAN,
        "expected_decision": "verified",
    }
    fixture.update(overrides)
    return fixture


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestDigests(unittest.TestCase):
    """Body and source digests are stable, canonical, and versioned."""

    def test_body_digest_normalizes_line_endings(self):
        self.assertEqual(delivery.body_digest("a\nb"),
                         delivery.body_digest("a\r\nb"))
        self.assertEqual(delivery.body_digest("a\r\nb"),
                         delivery.body_digest("a\rb"))

    def test_body_digest_is_utf8(self):
        self.assertNotEqual(delivery.body_digest("café"),
                            delivery.body_digest("cafe"))
        self.assertEqual(delivery.body_digest("café"),
                         delivery.body_digest("café"))

    def test_body_digest_changes_with_body(self):
        self.assertNotEqual(delivery.body_digest("one"),
                            delivery.body_digest("onex"))

    def test_record_digest_is_key_order_stable(self):
        first = delivery.record_digest({"a": 1, "b": 2, "c": {"d": 3}})
        second = delivery.record_digest({"c": {"d": 3}, "b": 2, "a": 1})
        self.assertEqual(first, second)

    def test_record_digest_is_utf8_and_lf_normalized(self):
        first = delivery.record_digest({"text": "line one\r\nline two"})
        second = delivery.record_digest({"text": "line one\nline two"})
        self.assertEqual(first, second)
        self.assertNotEqual(delivery.record_digest({"text": "café"}),
                            delivery.record_digest({"text": "cafe"}))

    def test_source_digest_is_versioned(self):
        record = {"source": CLEAN, "medium": "argument"}
        self.assertEqual(delivery.source_digest(record),
                         delivery.record_digest(record, "antislop-source-v1"))
        self.assertNotEqual(delivery.source_digest(record),
                            delivery.record_digest(record, "other-schema"))

    def test_source_digest_changes_with_record(self):
        record = {"source": CLEAN}
        changed = {"source": CLEAN, "note": "edited after verification"}
        self.assertNotEqual(delivery.source_digest(record),
                            delivery.source_digest(changed))


class TestVerifyDelivery(unittest.TestCase):
    """Verification reuses the fidelity and drift preservation contracts."""

    def setUp(self):
        self.registry = load_registry()

    def test_no_changes_verifies(self):
        report = delivery.verify_delivery(CLEAN, CLEAN)
        self.assertEqual(report["decision"], "verified")
        self.assertEqual(report["failures"], [])

    def test_clean_revision_preserving_contract_verifies(self):
        report = delivery.verify_delivery(
            "We utilize the old endpoint; the fix may take effect on "
            "2026-09-01 and usually completes in about 3 hours.",
            "We use the old endpoint; the fix may take effect on "
            "2026-09-01 and usually completes in about 3 hours.",
            required_facts=("the fix may take effect",),
            required_terms=("endpoint",),
            semantic_dimensions={"uncertainty": "preserve"})
        self.assertEqual(report["decision"], "verified")

    def test_required_fact_missing(self):
        report = delivery.verify_delivery(
            "The cache stores entries until they expire.",
            "The cache evicts entries when full.",
            required_facts=("The cache stores entries until they expire",))
        self.assertEqual(report["decision"], "failed")
        self.assertIn("required_fact_missing",
                      [f["kind"] for f in report["failures"]])

    def test_forbidden_addition(self):
        report = delivery.verify_delivery(
            "The system restarts overnight.",
            "The system restarts overnight, and the change is truly "
            "revolutionary.",
            forbidden_additions=("revolutionary",))
        self.assertEqual(report["decision"], "failed")
        self.assertIn("forbidden_addition",
                      [f["kind"] for f in report["failures"]])

    def test_date_change_is_protected_literal(self):
        report = delivery.verify_delivery(
            "The release ships on 2026-09-01.",
            "The release ships on 2026-09-02.")
        self.assertEqual(report["decision"], "failed")
        self.assertIn("protected_literal_changed",
                      [f["kind"] for f in report["failures"]])

    def test_dropped_may_is_qualifier_change(self):
        report = delivery.verify_delivery(
            "The change may fix the flaky test.",
            "The change fixes the flaky test.",
            semantic_dimensions={"uncertainty": "preserve"})
        self.assertEqual(report["decision"], "failed")
        self.assertIn("qualifier_changed",
                      [f["kind"] for f in report["failures"]])

    def test_strengthened_promise(self):
        report = delivery.verify_delivery(
            "The fix may resolve the issue.",
            "We guarantee the fix resolves the issue.",
            semantic_dimensions={"promise_intensity": "refuse"})
        self.assertEqual(report["decision"], "failed")
        kinds = [f["kind"] for f in report["failures"]]
        self.assertIn("promise_changed", kinds)
        self.assertIn("qualifier_changed", kinds)

    def test_attribution_change(self):
        report = delivery.verify_delivery(
            "According to Dr. Reyes, the fix works.",
            "The fix works.")
        self.assertEqual(report["decision"], "failed")
        self.assertIn("attribution_changed",
                      [f["kind"] for f in report["failures"]])

    def test_verification_records_exact_digests(self):
        source_record = delivery.bind_source_record(
            "The fix may resolve the issue.", "argument")
        report = delivery.verify_delivery(
            "The fix may resolve the issue.", "The fix may resolve the issue.",
            source_record=source_record)
        self.assertEqual(report["body_digest"],
                         delivery.body_digest("The fix may resolve the issue."))
        self.assertEqual(report["source_digest"],
                         delivery.source_digest(source_record))

    def test_mismatched_source_record_is_typed_failure(self):
        source_record = delivery.bind_source_record("Different source")
        report = delivery.verify_delivery(
            "The fix may resolve the issue.", "The fix may resolve the issue.",
            source_record=source_record)
        self.assertEqual(report["decision"], "failed")
        self.assertEqual(report["failures"][0]["kind"],
                         "source_record_mismatch")


class TestChunkedDelivery(unittest.TestCase):
    """Long documents retain cross-section facts and whole-document register."""

    def setUp(self):
        self.registry = load_registry()

    def test_retains_cross_section_fact_and_register(self):
        chunks = [
            {"source": "The migration renames the /api/v1/legacy endpoint "
                       "to /api/v2.",
             "required_facts": ["renames the /api/v1/legacy endpoint"],
             "required_terms": ["migration"]},
            {"source": "The cutover may take about 6 hours.",
             "required_facts": ["take about 6 hours"],
             "required_terms": ["cutover"]},
        ]
        body = ("The migration renames the /api/v1/legacy endpoint to "
                "/api/v2. The cutover may take about 6 hours.")
        report = delivery.verify_chunked_delivery(
            chunks, body, semantic_dimensions={"uncertainty": "preserve"})
        self.assertEqual(report["decision"], "verified")

    def test_dropped_cross_section_fact(self):
        chunks = [
            {"source": "The migration renames the /api/v1/legacy endpoint "
                       "to /api/v2.",
             "required_facts": ["renames the /api/v1/legacy endpoint"]},
            {"source": "The cutover may take about 6 hours.",
             "required_facts": ["take about 6 hours"]},
        ]
        body = "The migration points at a new endpoint. The cutover may take " \
               "about 6 hours."
        report = delivery.verify_chunked_delivery(chunks, body)
        self.assertEqual(report["decision"], "failed")
        kinds = [f["kind"] for f in report["failures"]]
        self.assertIn("required_fact_missing", kinds)
        self.assertIn("protected_literal_missing", kinds)

    def test_dropped_whole_document_register(self):
        chunks = [
            {"source": "The migration renames the /api/v1/legacy endpoint "
                       "to /api/v2.",
             "required_facts": ["renames the /api/v1/legacy endpoint"]},
            {"source": "The cutover may take about 6 hours.",
             "required_facts": ["take about 6 hours"]},
        ]
        body = ("The migration renames the /api/v1/legacy endpoint to "
                "/api/v2. The cutover will take about 6 hours.")
        report = delivery.verify_chunked_delivery(
            chunks, body, semantic_dimensions={"uncertainty": "preserve"})
        self.assertEqual(report["decision"], "failed")
        self.assertIn("qualifier_changed",
                      [f["kind"] for f in report["failures"]])


class TestEnvelope(unittest.TestCase):
    """The envelope keeps the four fields separate and fails on typed
    verification defects."""

    def setUp(self):
        self.registry = load_registry()

    def test_envelope_has_four_separate_fields(self):
        envelope = delivery.deliver(
            source="We utilize this approach to delve deeper.",
            body="We use this approach to explore further.",
            medium="argument", bind_source=True,
            revision_plan={"edits": [{"rule_id": "vocab-utilize",
                                      "action": "replace"}]})
        self.assertIn("review_report", envelope)
        self.assertIn("revision_plan", envelope)
        self.assertIn("deliverable_body", envelope)
        self.assertIn("verification_report", envelope)
        self.assertNotEqual(envelope["deliverable_body"],
                            envelope["review_report"])

    def test_body_contains_no_report_commentary(self):
        envelope = delivery.deliver(
            source="We utilize this approach to delve deeper.",
            body="We use this approach to explore further.",
            medium="argument")
        self.assertTrue(envelope["review_report"]["findings"])
        self.assertFalse(delivery._report_text_in_body(
            envelope["review_report"], envelope["deliverable_body"]))

    def test_no_changes_produces_successful_verification(self):
        envelope = delivery.deliver(source=CLEAN, body=CLEAN, medium="argument",
                                    bind_source=True)
        report = delivery.check_envelope(envelope)
        self.assertEqual(report["decision"], "verified")
        self.assertEqual(report["verification"]["decision"], "verified")

    def test_missing_verification_is_typed_failure(self):
        envelope = delivery.deliver(source=CLEAN, body=CLEAN, bind_source=True)
        envelope["verification_report"] = None
        report = delivery.check_envelope(envelope)
        self.assertEqual(report["decision"], "failed")
        self.assertEqual(report["failures"][0]["kind"], "missing_verification")

    def test_stale_verification_on_one_character_change(self):
        envelope = delivery.deliver(source=CLEAN, body=CLEAN, bind_source=True)
        envelope["deliverable_body"] = envelope["deliverable_body"] + "x"
        report = delivery.check_envelope(envelope)
        self.assertEqual(report["decision"], "failed")
        self.assertEqual(report["failures"][0]["kind"], "stale_verification")

    def test_stale_detection_does_not_trust_stored_digest(self):
        envelope = delivery.deliver(source=CLEAN, body=CLEAN, bind_source=True)
        envelope["deliverable_body"] = envelope["deliverable_body"] + "x"
        envelope["body_digest"] = delivery.body_digest(
            envelope["deliverable_body"])
        report = delivery.check_envelope(envelope)
        self.assertEqual(report["failures"][0]["kind"], "stale_verification")

    def test_mismatched_source_verification(self):
        envelope = delivery.deliver(source=CLEAN, body=CLEAN, bind_source=True)
        record = dict(envelope["source_record"])
        record["note"] = "edited after verification"
        envelope["source_record"] = record
        report = delivery.check_envelope(envelope)
        self.assertEqual(report["decision"], "failed")
        self.assertEqual(report["failures"][0]["kind"],
                         "mismatched_verification")

    def test_bound_failed_verification_keeps_envelope_failed(self):
        envelope = delivery.deliver(
            source="The change may fix the flaky test.",
            body="The change fixes the flaky test.",
            semantic_dimensions={"uncertainty": "preserve"},
            bind_source=True)
        report = delivery.check_envelope(envelope)
        self.assertEqual(report["decision"], "failed")
        self.assertEqual(report["verification"]["decision"], "failed")
        self.assertEqual(report["failures"], [])

    def test_verification_source_digest_covers_bound_record(self):
        envelope = delivery.deliver(source=CLEAN, body=CLEAN, bind_source=True)
        verification = envelope["verification_report"]
        self.assertEqual(verification["source_digest"],
                         delivery.source_digest(envelope["source_record"]))
        self.assertEqual(verification["body_digest"],
                         delivery.body_digest(envelope["deliverable_body"]))


class TestFixtureSchema(unittest.TestCase):
    """The delivery-envelope fixture schema validates kinds and expectations."""

    def test_all_fixtures_validate(self):
        fixtures = load_fixtures()
        seen = set()
        for fixture in fixtures:
            errors = delivery.validate_fixture(fixture, seen)
            self.assertEqual(errors, [], "fixture %s: %s"
                             % (fixture.get("id"), errors))

    def test_unknown_kind_rejected(self):
        errors = delivery.validate_fixture(
            make_fixture("bad-kind", kind="rewrite"), set())
        self.assertTrue(any("kind must be one of" in error
                            for error in errors))

    def test_unknown_failure_kind_rejected(self):
        errors = delivery.validate_fixture(
            make_fixture("bad-kind-name",
                         expected_failure_kinds=["ghost_failure"]), set())
        self.assertTrue(any("expected_failure_kinds[0] must be one of"
                            in error for error in errors))

    def test_unknown_dimension_rejected(self):
        errors = delivery.validate_fixture(
            make_fixture("bad-dimension",
                         semantic_dimensions={"mood": "preserve"}), set())
        self.assertTrue(any("unknown semantic dimension" in error
                            for error in errors))

    def test_source_tamper_needs_bind_source(self):
        errors = delivery.validate_fixture(
            make_fixture("bad-tamper", kind="envelope", tamper="source"),
            set())
        self.assertTrue(any("source' tamper needs bind_source" in error
                            for error in errors))

    def test_report_findings_need_medium(self):
        errors = delivery.validate_fixture(
            make_fixture("bad-report", kind="envelope",
                         report_has_findings=True), set())
        self.assertTrue(any("report_has_findings needs a 'medium'" in error
                            for error in errors))


class TestCorpus(unittest.TestCase):
    """The shipped fixture corpus validates and passes."""

    def test_corpus_gate_passes(self):
        fixtures = load_fixtures()
        report = delivery.run_corpus(fixtures, load_registry(), REGISTRY)
        self.assertEqual(report["schema_errors"], [])
        self.assertTrue(report["gate_pass"],
                        "failing: %s" % report["failing_ids"])
        self.assertEqual(report["failed"], 0)

    def test_validator_runs_delivery_checks(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestCli(unittest.TestCase):
    """The CLI entry points verify, build, and check envelopes."""

    def test_cli_verify_clean(self):
        result = subprocess.run(
            [sys.executable, DELIVERY, "verify", "--source-text", CLEAN,
             "--body-text", CLEAN],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["decision"], "verified")

    def test_cli_verify_failed_exit_code(self):
        result = subprocess.run(
            [sys.executable, DELIVERY, "verify", "--source-text",
             "The release ships on 2026-09-01.",
             "--body-text", "The release ships on 2026-09-02."],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 1, result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["decision"], "failed")

    def test_cli_envelope_then_check(self):
        envelope_path = os.path.join(ROOT, "tests", "envelope-test.json")
        try:
            result = subprocess.run(
                [sys.executable, DELIVERY, "envelope", "--source-text", CLEAN,
                 "--body-text", CLEAN, "--bind-source"],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(envelope_path, "w", encoding="utf-8") as f:
                f.write(result.stdout)
            result = subprocess.run(
                [sys.executable, DELIVERY, "check", "--envelope", envelope_path],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["decision"], "verified")
        finally:
            if os.path.exists(envelope_path):
                os.remove(envelope_path)

    def test_cli_envelope_failed_verification_has_failure_exit(self):
        result = subprocess.run(
            [sys.executable, DELIVERY, "envelope", "--source-text",
             "The release ships on 2026-09-01.", "--body-text",
             "The release ships on 2026-09-02."],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 1, result.stdout)
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["verification_report"]["decision"], "failed")

    def test_cli_fixture_corpus(self):
        result = subprocess.run(
            [sys.executable, DELIVERY, "--fixtures", FIXTURES],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["gate_pass"])


if __name__ == "__main__":
    unittest.main()
