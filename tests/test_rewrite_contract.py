#!/usr/bin/env python3
"""Tests for the controlled rewrite and preservation evals (issue #65).

The controlled rewrite contract is documented in skills/antislop/SKILL.md as a
provider-neutral two-pass workflow: audit first, rewrite against the selected
findings only, check preservation, re-audit the result, and keep final
acceptance human-controlled. The compatible assistant produces the candidate;
Antislop supplies the protected-span rules and the acceptance checks.

This module implements the deterministic acceptance check (run_contract) on top
of the existing modules and drives it from the fixture corpus. It covers:

  - audit before rewriting: source findings are listed with rule, span, excerpt
  - clean input produces no selection, no new findings, and a passing check
  - only selected findings are addressed; unselected findings are preserved
  - selected findings the rewrite leaves in place are reported as rejected
  - protected Markdown, code, Mermaid, URLs, and quoted material stay intact
  - a changed protected value fails the preservation check
  - an extra user-declared protected span is enforced like a fixed region
  - a newly introduced audit finding is visible in the result
  - the report identifies selected, changed, preserved, and rejected findings
  - running the acceptance check twice is idempotent

Run: python3 -m unittest tests/test_rewrite_contract.py -v
"""

import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from registry import load_registry as load_registry_file  # noqa: E402
import fidelity  # noqa: E402
import repair  # noqa: E402
import score as scoring  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "rewrite-contract-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")

INTERFACE = "antislop.rewrite-contract"
SCHEMA = "rewrite-contract-report-1"
DECISIONS = ("accept", "review", "reject")
PROFILES = ("general", "technical")

DISCLAIMER = (
    "Controlled rewrite results report selection, preservation, and re-audit; "
    "they never prove AI authorship or detector immunity."
)

REQUIRED_SCENARIOS = {
    "rewrite-clean-input-unchanged",
    "rewrite-selected-findings-only",
    "rewrite-rejected-selected-finding",
    "rewrite-protected-markdown-regions",
    "rewrite-code-fence-protected",
    "rewrite-mermaid-diagram-protected",
    "rewrite-url-preserved",
    "rewrite-quoted-material-protected",
    "rewrite-factual-number-drift-fails",
    "rewrite-new-findings-visible",
    "rewrite-user-declared-span-preserved",
    "rewrite-user-declared-span-changed-fails",
}


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def audit(text, registry, profile="general"):
    rules = registry.get("rules", [])
    raw, _skipped, _metrics = scoring.detect_findings(text, rules, profile)
    return scoring.handle_overlaps(raw)


def _finding_record(finding):
    return {
        "rule_id": finding["rule_id"],
        "span": [finding["position"],
                 finding["position"] + finding.get("match_length", 6)],
        "excerpt": finding.get("excerpt", ""),
    }


def _counts(findings):
    counts = {}
    for finding in findings:
        counts[finding["rule_id"]] = counts.get(finding["rule_id"], 0) + 1
    return counts


def _protected_counts(findings, regions):
    protected = {}
    actionable = {}
    for finding in findings:
        start = finding["position"]
        end = start + finding.get("match_length", 6)
        if any(start < region["end"] and region["start"] < end
               for region in regions):
            protected[finding["rule_id"]] = (
                protected.get(finding["rule_id"], 0) + 1)
        else:
            actionable[finding["rule_id"]] = (
                actionable.get(finding["rule_id"], 0) + 1)
    return protected, actionable


def run_contract(source, candidate, *, selected_rule_ids=(),
                 protected_terms=(), registry_path="rules.json",
                 profile="general"):
    """The deterministic acceptance check for a controlled rewrite.

    Implements the deterministic parts of the documented seven-step contract:
    audit the source, classify the author's selection, run the fidelity
    preservation gate, re-audit the candidate, and report selected, changed,
    preserved, and rejected findings plus newly introduced findings. The
    candidate text comes from the compatible assistant; this function only
    checks it.
    """
    registry = load_registry_file(registry_path)
    source_findings = [f for f in audit(source, registry, profile)
                       if f.get("primary", True)]
    candidate_findings = [f for f in audit(candidate, registry, profile)
                          if f.get("primary", True)]
    selected = set(selected_rule_ids)

    source_counts = _counts(source_findings)
    candidate_counts = _counts(candidate_findings)
    candidate_regions = repair.protected_regions(candidate, protected_terms)
    protected_counts, actionable_counts = _protected_counts(
        candidate_findings, candidate_regions)

    changed = []
    preserved = []
    rejected = []
    for rule_id in sorted(set(source_counts) | set(candidate_counts)):
        source_count = source_counts.get(rule_id, 0)
        candidate_count = candidate_counts.get(rule_id, 0)
        cleared = max(0, source_count - candidate_count)
        if cleared:
            changed.append({
                "rule_id": rule_id, "count": cleared,
                "selected": rule_id in selected,
            })
        if rule_id in selected:
            if protected_counts.get(rule_id):
                preserved.append({
                    "rule_id": rule_id,
                    "count": protected_counts.get(rule_id, 0),
                    "protected": True,
                })
            if actionable_counts.get(rule_id):
                rejected.append({
                    "rule_id": rule_id,
                    "count": actionable_counts.get(rule_id, 0),
                })
        elif source_count:
            preserved.append({
                "rule_id": rule_id,
                "count": candidate_count,
                "protected": bool(protected_counts.get(rule_id)),
            })

    selected_findings = [_finding_record(f) for f in source_findings
                         if f["rule_id"] in selected]
    source_rule_ids = set(source_counts)
    new_findings = [_finding_record(f) for f in candidate_findings
                    if f["rule_id"] not in source_rule_ids]

    gate = fidelity.check_fidelity(
        source, candidate,
        required_terms=tuple(protected_terms),
        hot_zones=[{"start": record["span"][0], "end": record["span"][1],
                    "label": record["rule_id"]}
                   for record in selected_findings],
        churn_limit=None,
        registry_path=registry_path,
        profile=profile,
    )
    preservation_status = gate["preservation"]["status"]
    if preservation_status == "failed":
        decision = "reject"
    elif rejected:
        decision = "review"
    else:
        decision = "accept"

    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "profile": profile,
        "source_audit": {
            "score": scoring.score_text(source, registry, profile)["score"],
            "findings": [_finding_record(f) for f in source_findings],
        },
        "candidate_audit": {
            "score": scoring.score_text(candidate, registry, profile)["score"],
            "findings": [_finding_record(f) for f in candidate_findings],
        },
        "selection": {
            "selected_rule_ids": sorted(selected),
            "selected": selected_findings,
            "changed": changed,
            "preserved": preserved,
            "rejected": rejected,
        },
        "new_findings": new_findings,
        "preservation": {
            "status": preservation_status,
            "gate_decision": gate["decision"],
            "hard_failures": gate["preservation"]["hard_failures"],
            "protected_spans": gate["preservation"]["protected_spans"],
        },
        "decision": decision,
        "meta": {
            "disclaimer": DISCLAIMER,
            "protected_terms": list(protected_terms),
        },
    }


def validate_rewrite_fixture(fixture, seen_ids):
    """Schema-validate one controlled-rewrite fixture. Returns error strings."""
    errors = []
    if not isinstance(fixture, dict):
        return ["fixture must be a JSON object"]
    fid = fixture.get("id")
    if not isinstance(fid, str) or not fid.strip():
        errors.append("fixture missing non-empty string 'id'")
    else:
        if fid in seen_ids:
            errors.append("duplicate fixture id '%s'" % fid)
        seen_ids.add(fid)

    where = "fixture '%s'" % (fid if fid else "?")

    for field in ("source", "candidate"):
        value = fixture.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append("%s: '%s' must be a non-empty string"
                          % (where, field))

    if fixture.get("expected_decision") not in DECISIONS:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(DECISIONS)))
    if fixture.get("expected_preservation") not in ("passed", "failed"):
        errors.append("%s: expected_preservation must be passed or failed"
                      % where)

    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(PROFILES)))

    for field in ("selected_rule_ids", "protected_terms", "expected_selected",
                  "expected_new"):
        value = fixture.get(field, [])
        if not isinstance(value, list):
            errors.append("%s: %s must be a list" % (where, field))
        else:
            for index, item in enumerate(value):
                if not (isinstance(item, str) and item.strip()):
                    errors.append("%s: %s[%d] must be a non-empty string"
                                  % (where, field, index))

    for field in ("expected_changed", "expected_preserved",
                  "expected_rejected"):
        value = fixture.get(field, [])
        if not isinstance(value, list):
            errors.append("%s: %s must be a list" % (where, field))
        else:
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    errors.append("%s: %s[%d] must be an object"
                                  % (where, field, index))
                    continue
                if not (isinstance(item.get("rule_id"), str)
                        and item["rule_id"].strip()):
                    errors.append("%s: %s[%d] missing non-empty 'rule_id'"
                                  % (where, field, index))
                count = item.get("count")
                if not (isinstance(count, int)
                        and not isinstance(count, bool) and count >= 0):
                    errors.append("%s: %s[%d].count must be a non-negative "
                                  "integer" % (where, field, index))

    for field in ("false_positive_rationale", "reviewer_notes"):
        value = fixture.get(field)
        if value is not None and (not isinstance(value, str)
                                  or not value.strip()):
            errors.append("%s: %s must be a non-empty string" % (where, field))
    return errors


def _check_bucket(failures, label, actual, expected):
    actual_counts = {item["rule_id"]: item.get("count", 0)
                     for item in actual}
    for item in expected:
        rule_id = item["rule_id"]
        if rule_id not in actual_counts:
            failures.append("%s does not list rule '%s'" % (label, rule_id))
            continue
        if actual_counts[rule_id] != item.get("count", 0):
            failures.append("%s rule '%s' count %d, expected %d"
                            % (label, rule_id, actual_counts[rule_id],
                               item.get("count", 0)))


def run_rewrite_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one controlled-rewrite fixture against its expectations."""
    report = run_contract(
        fixture["source"], fixture["candidate"],
        selected_rule_ids=tuple(fixture.get("selected_rule_ids", [])),
        protected_terms=tuple(fixture.get("protected_terms", [])),
        registry_path=registry_path,
        profile=fixture.get("profile", "general"),
    )

    failures = []
    if report["decision"] != fixture["expected_decision"]:
        failures.append("expected decision %s, got %s"
                        % (fixture["expected_decision"], report["decision"]))
    if report["preservation"]["status"] != fixture["expected_preservation"]:
        failures.append("expected preservation %s, got %s"
                        % (fixture["expected_preservation"],
                           report["preservation"]["status"]))

    selected_ids = {record["rule_id"]
                    for record in report["selection"]["selected"]}
    for rule_id in fixture.get("expected_selected", []):
        if rule_id not in selected_ids:
            failures.append("rule '%s' was not selected" % rule_id)

    _check_bucket(failures, "changed", report["selection"]["changed"],
                  fixture.get("expected_changed", []))
    _check_bucket(failures, "preserved", report["selection"]["preserved"],
                  fixture.get("expected_preserved", []))
    _check_bucket(failures, "rejected", report["selection"]["rejected"],
                  fixture.get("expected_rejected", []))

    new_ids = {record["rule_id"] for record in report["new_findings"]}
    for rule_id in fixture.get("expected_new", []):
        if rule_id not in new_ids:
            failures.append("new finding '%s' is not visible" % rule_id)

    report["id"] = fixture["id"]
    report["expected_decision"] = fixture["expected_decision"]
    report["meta"]["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
    report["failures"] = failures
    return report


def run_rewrite_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the controlled-rewrite fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_rewrite_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "interface": INTERFACE,
            "schema": "rewrite-contract-corpus-report-1",
            "version": registry.get("version", "unknown"),
            "fixture_count": len(fixtures),
            "passed": 0,
            "failed": len(fixtures),
            "failing_ids": [fixture.get("id", "?") for fixture in fixtures],
            "schema_errors": schema_errors,
            "gate_pass": False,
            "disclaimer": DISCLAIMER,
            "fixtures": [],
        }

    reports = [run_rewrite_fixture(fixture, registry,
                                    registry_path=registry_path)
               for fixture in fixtures]
    failed = [report for report in reports if report["failures"]]
    return {
        "interface": INTERFACE,
        "schema": "rewrite-contract-corpus-report-1",
        "version": registry.get("version", "unknown"),
        "fixture_count": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "failures": [{
            "id": report["id"],
            "expected": report["expected_decision"],
            "got": report["decision"],
            "findings": report["failures"],
        } for report in failed],
        "schema_errors": schema_errors,
        "gate_pass": not schema_errors and not failed,
        "disclaimer": DISCLAIMER,
        "fixtures": reports,
    }


def make_fixture(rid="rewrite-test", **overrides):
    """A schema-valid controlled-rewrite fixture with per-test overrides."""
    fixture = {
        "id": rid,
        "source": "The worker lost its lease and the queue drained the "
                  "backlog overnight.",
        "candidate": "The worker lost its lease and the queue drained the "
                     "backlog overnight.",
        "expected_decision": "accept",
        "expected_preservation": "passed",
    }
    fixture.update(overrides)
    return fixture


class TestAuditBeforeRewrite(unittest.TestCase):
    """Pass one of the contract: source findings are listed with span."""

    def setUp(self):
        self.registry = load_registry()

    def test_source_findings_are_recorded(self):
        report = run_contract(
            "We utilize the API and then delve into the failure.",
            "We use the API and then delve into the failure.",
            selected_rule_ids=("vocab-utilize", "vocab-delve"),
            registry_path=REGISTRY,
        )
        findings = report["source_audit"]["findings"]
        self.assertEqual({f["rule_id"] for f in findings},
                         {"vocab-utilize", "vocab-delve"})
        for finding in findings:
            self.assertIn("span", finding)
            self.assertIn("excerpt", finding)

    def test_candidate_is_reaudited(self):
        report = run_contract(
            "We utilize the API and then delve into the failure.",
            "We use the API and then delve into the failure.",
            selected_rule_ids=("vocab-utilize",),
            registry_path=REGISTRY,
        )
        candidate_ids = {f["rule_id"]
                         for f in report["candidate_audit"]["findings"]}
        self.assertEqual(candidate_ids, {"vocab-delve"})

    def test_report_shape_and_version(self):
        report = run_contract("Plain clean prose stays unchanged.",
                              "Plain clean prose stays unchanged.",
                              registry_path=REGISTRY)
        json.dumps(report)
        for key in ("interface", "schema", "version", "profile",
                    "source_audit", "candidate_audit", "selection",
                    "new_findings", "preservation", "decision", "meta"):
            self.assertIn(key, report)
        self.assertEqual(report["version"], "3.0.0")
        self.assertIn("never prove", report["meta"]["disclaimer"])


class TestCleanInput(unittest.TestCase):
    """Clean input produces no selection, no new findings, and a pass."""

    def setUp(self):
        self.registry = load_registry()

    def test_clean_input_is_accepted(self):
        text = ("The worker lost its lease and the queue drained the "
                "backlog overnight.")
        report = run_contract(text, text, registry_path=REGISTRY)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["selection"]["selected"], [])
        self.assertEqual(report["selection"]["changed"], [])
        self.assertEqual(report["selection"]["preserved"], [])
        self.assertEqual(report["selection"]["rejected"], [])
        self.assertEqual(report["new_findings"], [])
        self.assertEqual(report["preservation"]["status"], "passed")


class TestSelectedFindings(unittest.TestCase):
    """Only the selected findings are addressed; others are preserved."""

    def setUp(self):
        self.registry = load_registry()

    def test_unselected_finding_is_preserved(self):
        report = run_contract(
            "We utilize the API and then delve into the failure.",
            "We use the API and then delve into the failure.",
            selected_rule_ids=("vocab-utilize",),
            registry_path=REGISTRY,
        )
        self.assertEqual(report["decision"], "accept")
        self.assertEqual({f["rule_id"] for f in report["selection"]["selected"]},
                         {"vocab-utilize"})
        self.assertEqual(report["selection"]["changed"],
                         [{"rule_id": "vocab-utilize", "count": 1,
                           "selected": True}])
        self.assertEqual(report["selection"]["preserved"],
                         [{"rule_id": "vocab-delve", "count": 1,
                           "protected": False}])
        self.assertEqual(report["selection"]["rejected"], [])

    def test_selected_finding_left_in_place_is_rejected(self):
        report = run_contract(
            "We utilize the API and then delve into the failure.",
            "We use the API and then delve into the failure.",
            selected_rule_ids=("vocab-utilize", "vocab-delve"),
            registry_path=REGISTRY,
        )
        self.assertEqual(report["decision"], "review")
        self.assertEqual(report["selection"]["rejected"],
                         [{"rule_id": "vocab-delve", "count": 1}])


class TestProtectedRegions(unittest.TestCase):
    """Protected Markdown, code, Mermaid, URLs, and quoted text stay intact."""

    def setUp(self):
        self.registry = load_registry()

    def test_code_fence_and_quoted_span_survive(self):
        source = ('We utilize the API.\n\n```python\n'
                  'def deploy():\n    return "utilize"\n```\n\n'
                  'The customer said "we utilize the old tool".\n')
        candidate = source.replace("We utilize the API.",
                                   "We use the API.")
        report = run_contract(source, candidate,
                              selected_rule_ids=("vocab-utilize",),
                              registry_path=REGISTRY)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["preservation"]["status"], "passed")
        self.assertIn("```python\n", candidate)
        self.assertIn('"we utilize the old tool"', candidate)

    def test_mermaid_block_is_byte_identical(self):
        diagram = ("```mermaid\nflowchart LR\n"
                   "    A[Start] --> B{Check}\n"
                   "    B -->|yes| C[Deploy]\n```")
        source = "We utilize the pipeline.\n\n%s\n" % diagram
        candidate = source.replace("We utilize the pipeline.",
                                   "We use the pipeline.")
        report = run_contract(source, candidate,
                              selected_rule_ids=("vocab-utilize",),
                              registry_path=REGISTRY)
        self.assertEqual(report["decision"], "accept")
        self.assertIn(diagram, candidate)
        self.assertEqual(candidate.count(diagram), 1)

    def test_url_is_preserved(self):
        source = ("See https://example.com/docs for the reference, and we "
                  "utilize it daily.")
        candidate = ("See https://example.com/docs for the reference, and we "
                     "use it daily.")
        report = run_contract(source, candidate,
                              selected_rule_ids=("vocab-utilize",),
                              registry_path=REGISTRY)
        self.assertEqual(report["decision"], "accept")
        self.assertIn("https://example.com/docs", candidate)

    def test_markdown_document_repairs_prose_only(self):
        source = ("# Notes\n\nWe utilize the checklist below.\n\n"
                  "| Metric | Value |\n|--------|-------|\n"
                  "| utilize rate | 40 ms |\n\n"
                  "> The worker \"utilize\" retried the job.\n")
        candidate = source.replace("We utilize the checklist below.",
                                   "We use the checklist below.")
        report = run_contract(source, candidate,
                              selected_rule_ids=("vocab-utilize",),
                              registry_path=REGISTRY)
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["selection"]["changed"],
                         [{"rule_id": "vocab-utilize", "count": 1,
                           "selected": True}])
        self.assertEqual(report["selection"]["preserved"],
                         [{"rule_id": "vocab-utilize", "count": 2,
                           "protected": True}])
        self.assertIn("| utilize rate | 40 ms |", candidate)
        self.assertIn('> The worker "utilize" retried the job.', candidate)


class TestPreservationFails(unittest.TestCase):
    """A changed protected value fails the preservation check."""

    def setUp(self):
        self.registry = load_registry()

    def test_changed_number_rejects(self):
        report = run_contract(
            "The fix cut deploy time to 40 minutes and we utilize the API.",
            "The fix cut deploy time to 50 minutes and we use the API.",
            selected_rule_ids=("vocab-utilize",),
            registry_path=REGISTRY,
        )
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["preservation"]["status"], "failed")
        self.assertTrue(any(f["category"] == "number"
                            for f in report["preservation"]["hard_failures"]))

    def test_changed_user_declared_span_rejects(self):
        report = run_contract(
            "The service meets SOC 2 and we utilize it.",
            "The service is fully compliant now and we use it.",
            selected_rule_ids=("vocab-utilize",),
            protected_terms=("SOC 2",),
            registry_path=REGISTRY,
        )
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["preservation"]["status"], "failed")
        self.assertTrue(any(f["category"] == "required_term"
                            for f in report["preservation"]["hard_failures"]))


class TestNewFindings(unittest.TestCase):
    """A newly introduced audit finding is visible in the result."""

    def setUp(self):
        self.registry = load_registry()

    def test_introduced_word_is_reported(self):
        report = run_contract(
            "We utilize the API and the queue drained overnight.",
            "We use the API and the queue drained overnight and it is "
            "seamless.",
            selected_rule_ids=("vocab-utilize",),
            registry_path=REGISTRY,
        )
        self.assertEqual(report["decision"], "accept")
        new_ids = {f["rule_id"] for f in report["new_findings"]}
        self.assertEqual(new_ids, {"vocab-seamless"})

    def test_new_finding_is_never_hidden_by_a_pass(self):
        report = run_contract(
            "We utilize the API and the queue drained overnight.",
            "We use the API and the queue drained overnight and it is "
            "seamless.",
            selected_rule_ids=("vocab-utilize",),
            registry_path=REGISTRY,
        )
        self.assertEqual(report["preservation"]["status"], "passed")
        self.assertTrue(report["new_findings"])


class TestUserDeclaredProtectedSpans(unittest.TestCase):
    """Extra user-declared protected spans are enforced like fixed regions."""

    def setUp(self):
        self.registry = load_registry()

    def test_declared_term_is_preserved(self):
        source = "The service meets SOC 2 and we utilize it."
        candidate = "The service meets SOC 2 and we use it."
        report = run_contract(
            source, candidate,
            selected_rule_ids=("vocab-utilize",),
            protected_terms=("SOC 2",),
            registry_path=REGISTRY,
        )
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["meta"]["protected_terms"], ["SOC 2"])
        self.assertIn("SOC 2", candidate)
        unchanged = report["preservation"]["protected_spans"][
            "unchanged_by_category"]
        self.assertGreaterEqual(unchanged.get("required_term", 0), 1)


class TestIdempotence(unittest.TestCase):
    """Running the acceptance check twice yields an identical report."""

    def setUp(self):
        self.registry = load_registry()

    def test_repeated_run_is_identical(self):
        source = ("We utilize the API and then delve into the failure, and "
                  "the customer said \"we utilize the old tool\".")
        candidate = ("We use the API and then delve into the failure, and "
                     "the customer said \"we utilize the old tool\".")
        kwargs = {"selected_rule_ids": ("vocab-utilize", "vocab-delve"),
                  "registry_path": REGISTRY}
        first = run_contract(source, candidate, **kwargs)
        second = run_contract(source, candidate, **kwargs)
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))


class TestFixtureSchema(unittest.TestCase):
    """The fixture schema validates the full acceptance contract."""

    def test_valid_fixture_has_no_schema_errors(self):
        errors = validate_rewrite_fixture(make_fixture(), set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = validate_rewrite_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        validate_rewrite_fixture(make_fixture(), seen)
        errors = validate_rewrite_fixture(make_fixture(), seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))

    def test_decision_and_preservation_must_be_valid(self):
        errors = validate_rewrite_fixture(
            make_fixture(expected_decision="maybe",
                         expected_preservation="maybe"), set())
        joined = "\n".join(errors)
        self.assertIn("expected_decision must be one of", joined)
        self.assertIn("expected_preservation must be passed or failed", joined)

    def test_rule_lists_must_be_strings(self):
        errors = validate_rewrite_fixture(
            make_fixture(selected_rule_ids=[42],
                         expected_new=["ok", 42]), set())
        joined = "\n".join(errors)
        self.assertIn("selected_rule_ids[0]", joined)
        self.assertIn("expected_new[1]", joined)

    def test_bucket_entries_validate_rule_id_and_count(self):
        errors = validate_rewrite_fixture(
            make_fixture(expected_changed=[
                {"rule_id": "", "count": -1},
            ]), set())
        joined = "\n".join(errors)
        self.assertIn("expected_changed[0] missing non-empty 'rule_id'",
                      joined)
        self.assertIn("expected_changed[0].count must be a non-negative "
                      "integer", joined)

    def test_profile_must_be_valid(self):
        errors = validate_rewrite_fixture(make_fixture(profile="essay"), set())
        self.assertTrue(any("profile must be one of" in error
                            for error in errors))


class TestProductionCorpus(unittest.TestCase):
    """The production controlled-rewrite corpus passes end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = run_rewrite_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        self.assertEqual(ids & REQUIRED_SCENARIOS, REQUIRED_SCENARIOS)

    def test_fixtures_cover_every_decision(self):
        decisions = {fixture["expected_decision"]
                     for fixture in load_fixtures()}
        self.assertEqual(decisions, {"accept", "review", "reject"})

    def test_fixtures_cover_both_preservation_states(self):
        states = {fixture["expected_preservation"]
                  for fixture in load_fixtures()}
        self.assertEqual(states, {"passed", "failed"})


if __name__ == "__main__":
    unittest.main()