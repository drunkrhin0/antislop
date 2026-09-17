#!/usr/bin/env python3
"""Tests for the Anbeeld-style edit integrity contract (issue #87).

Covers:
  - the four operations and their authority: draft, revise, audit, transform
  - audit leaves the artifact unchanged; a rewrite under audit is rejected
  - revise is least invasive and rejects causality or certainty strengthening
  - a voice sample contributes style traits only, never memories
  - transform may reorder sections but retains every claim and caveat, and
    discloses shape changes
  - the inventory composes fidelity protected spans and anchors with drift
    facts and output-integrity defects
  - output-integrity checks catch placeholders, malformed markup, leaked
    prompt tokens, and changed link targets
  - long-form information gain stays a human-review prompt, never a score
    deduction
  - boundaries: results never claim authorship or detector immunity

Run: python3 -m unittest tests/test_edit_integrity.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import edit  # noqa: E402 -- import after sys.path setup
import fidelity  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "edit-integrity-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
VALIDATE = os.path.join(ROOT, "validate.py")

OPERATIONS = ("draft", "revise", "audit", "transform")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def make_fixture(rid="edit-test", **overrides):
    """A schema-valid edit-integrity fixture with per-test overrides."""
    fixture = {
        "id": rid,
        "operation": "revise",
        "source": "We delve into the problem.",
        "candidate": "We dig into the problem.",
        "expected_decision": "accept",
    }
    fixture.update(overrides)
    return fixture


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestFixtureSchema(unittest.TestCase):
    """The edit fixture schema validates the operation and its contract."""

    def setUp(self):
        self.registry = load_registry()

    def test_valid_fixture_has_no_schema_errors(self):
        errors = edit.validate_edit_fixture(make_fixture(), set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = edit.validate_edit_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_operation_must_be_one_of_the_four(self):
        errors = edit.validate_edit_fixture(
            make_fixture(operation="summarize"), set())
        self.assertTrue(any("operation must be one of" in error
                            for error in errors))

    def test_information_gain_is_a_valid_review_prompt(self):
        errors = edit.validate_edit_fixture(
            make_fixture(review_prompts={
                "information_gain": "Check the added background stays on-topic.",
            }), set())
        self.assertEqual(errors, [])

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        edit.validate_edit_fixture(make_fixture(), seen)
        errors = edit.validate_edit_fixture(make_fixture(), seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))


class TestInventory(unittest.TestCase):
    """The inventory composes the preservation and integrity contracts."""

    def test_inventory_has_protected_spans_anchors_facts_and_defects(self):
        result = edit.inventory(
            "Pricing starts at 29.99 per month. "
            "See https://example.com/docs. [add release date]",
            required_terms=("per month",),
            declared_facts=("Pricing starts at 29.99 per month",),
        )
        categories = {s["category"] for s in result["protected_spans"]}
        self.assertIn("number", categories)
        self.assertIn("url", categories)
        self.assertIn("required_term", categories)
        self.assertIn("Pricing starts at 29.99 per month", result["facts"])
        self.assertTrue(any(d["kind"] == "placeholder"
                            for d in result["integrity_defects"]))

    def test_voice_sample_claim_is_absent_from_the_target_inventory(self):
        claim = ("My first deploy at 2am taught me to read logs twice")
        source_inventory = edit.inventory(
            claim + ", and I still remember the 2021 outage.",
            declared_facts=(claim,))
        self.assertEqual(source_inventory["facts"], [claim])
        target_inventory = edit.inventory(
            "Logs deserve a second read before you trust a deploy.",
            declared_facts=(claim,))
        self.assertEqual(target_inventory["facts"], [])


class TestOperationAuthority(unittest.TestCase):
    """Each operation enforces its own boundary over the artifact."""

    def setUp(self):
        self.registry = load_registry()

    def test_audit_reports_without_rewriting(self):
        report = edit.check_operation("We delve into the problem.",
                                      "We delve into the problem.", "audit")
        self.assertEqual(report["decision"], "accept")
        self.assertEqual(report["authority"], [])

    def test_audit_that_rewrites_is_rejected(self):
        report = edit.check_operation("We delve into the problem.",
                                      "We dig into the problem.", "audit")
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["authority"][0]["kind"],
                         "audit_rewrote_text")

    def test_revise_accepts_the_same_output_audit_rejected(self):
        report = edit.check_operation("We delve into the problem.",
                                      "We dig into the problem.", "revise")
        self.assertEqual(report["decision"], "accept")

    def test_revise_preserves_negation(self):
        report = edit.check_operation(
            "We delve into the problem. The access token is not required "
            "for read-only calls.",
            "We dig into the problem. The access token is not required "
            "for read-only calls.",
            "revise",
            required_facts=["The access token is not required for "
                            "read-only calls"],
            semantic_dimensions={"negation": "preserve"},
        )
        self.assertEqual(report["decision"], "accept")

    def test_revise_rejects_certainty_strengthening(self):
        report = edit.check_operation(
            "The feature may cause data loss, so test it first.",
            "The feature causes data loss, so test it first.",
            "revise",
            semantic_dimensions={"uncertainty": "preserve"},
        )
        self.assertEqual(report["decision"], "reject")

    def test_revise_rejects_causal_strengthening(self):
        report = edit.check_operation(
            "The delay was probably caused by the lease loss.",
            "The delay was caused by the lease loss.",
            "revise",
            semantic_dimensions={"uncertainty": "preserve",
                                 "causality": "preserve"},
        )
        self.assertEqual(report["decision"], "reject")

    def test_revise_rejects_changed_claim_direction(self):
        report = edit.check_operation(
            "The service reduced outages by 40%.",
            "The service doubled outages by 40%.",
            "revise",
        )
        self.assertEqual(report["decision"], "reject")

    def test_revise_attribution_change_requires_review(self):
        report = edit.check_operation(
            "According to NIST, the standard requires encryption.",
            "According to IETF, the standard requires encryption.",
            "revise",
        )
        self.assertEqual(report["decision"], "review")
        self.assertEqual(report["review"]["status"], "unresolved")

    def test_draft_voice_sample_supplies_style_only(self):
        report = edit.check_operation(
            "My first deploy at 2am taught me to read logs twice, and I "
            "still remember the 2021 outage.",
            "Logs deserve a second read before you trust a deploy. "
            "Errors hide in the tail of the output.",
            "draft",
            required_facts=[
                "Logs deserve a second read before you trust a deploy",
                "Errors hide in the tail of the output",
            ],
            forbidden_additions=[
                "My first deploy at 2am taught me to read logs twice",
                "the 2021 outage",
            ],
        )
        self.assertEqual(report["decision"], "accept")

    def test_draft_voice_sample_memory_is_rejected(self):
        report = edit.check_operation(
            "My first deploy at 2am taught me to read logs twice.",
            "Deploys need care. My first deploy at 2am taught me to read "
            "logs twice.",
            "draft",
            forbidden_additions=[
                "My first deploy at 2am taught me to read logs twice",
            ],
        )
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(i["kind"] == "forbidden_addition"
                            for i in report["items"]["added"]))

    def test_draft_without_supplied_facts_is_rejected(self):
        report = edit.check_operation(
            "A voice sample.", "I won the lottery.", "draft"
        )
        self.assertEqual(report["decision"], "reject")
        self.assertIn("draft requires supplied facts", report["reasons"])


class TestTransform(unittest.TestCase):
    """Transform may reorder sections but must preserve the inventory."""

    def setUp(self):
        self.registry = load_registry()

    SOURCE = ("Deploy time fell to 40 minutes after caching.\n\n"
              "The queue worker lost its lease, which caused the "
              "backlog.\n\n"
              "Only three merchants were affected, and access expires "
              "after 24 hours.")

    FACTS = ["Deploy time fell to 40 minutes after caching",
             "the queue worker lost its lease",
             "Only three merchants were affected",
             "access expires after 24 hours"]

    def test_reorder_retains_every_claim_and_caveat(self):
        candidate = ("Only three merchants were affected, and access "
                     "expires after 24 hours.\n\n"
                     "The queue worker lost its lease, which caused the "
                     "backlog.\n\n"
                     "Deploy time fell to 40 minutes after caching.")
        report = edit.check_operation(
            self.SOURCE, candidate, "transform",
            required_facts=self.FACTS,
            semantic_dimensions={"causality": "preserve", "scope": "preserve"},
        )
        self.assertEqual(report["decision"], "accept")
        self.assertTrue(report["shape"]["reordered"])
        self.assertEqual(report["shape"]["removed"], [])
        self.assertEqual(report["shape"]["added"], [])
        self.assertEqual(report["items"]["missing"], [])
        self.assertEqual(report["items"]["changed"], [])

    def test_reorder_preserves_protected_spans_as_a_multiset(self):
        candidate = ("Only three merchants were affected, and access "
                     "expires after 24 hours.\n\n"
                     "The queue worker lost its lease, which caused the "
                     "backlog.\n\n"
                     "Deploy time fell to 40 minutes after caching.")
        report = edit.check_operation(self.SOURCE, candidate, "transform",
                                      required_facts=self.FACTS)
        self.assertEqual(report["decision"], "accept")

    def test_transform_that_drops_a_caveat_is_rejected(self):
        candidate = ("Deploy time fell to 40 minutes after caching.\n\n"
                     "Only three merchants were affected.")
        report = edit.check_operation(self.SOURCE, candidate, "transform",
                                      required_facts=self.FACTS)
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(i["kind"] == "required_fact"
                            for i in report["items"]["missing"]))
        self.assertTrue(report["shape"]["removed"])


class TestOutputIntegrity(unittest.TestCase):
    """Output-integrity checks catch placeholders, markup, prompt tokens,
    and changed link targets."""

    def setUp(self):
        self.registry = load_registry()

    def test_changed_link_target_fails_the_fidelity_gate(self):
        report = edit.check_operation(
            "See https://example.com/docs for the reference.",
            "See https://example.net/docs for the reference.",
            "revise",
        )
        self.assertEqual(report["fidelity"]["status"], "failed")
        self.assertIn("url", [f["category"]
                              for f in report["items"]["changed"]
                              if f["kind"] == "protected_span_changed"])

    def test_leaked_prompt_token_is_rejected(self):
        report = edit.check_operation(
            "Rewrite the conclusion in plain language.",
            "Rewrite the conclusion in plain language.\n"
            "<|im_start|>system you are a helpful assistant<|im_end|>",
            "revise",
        )
        self.assertEqual(report["decision"], "reject")
        self.assertEqual(report["integrity"]["status"], "failed")
        self.assertIn("leaked_prompt_token",
                      report["integrity"]["failures"])

    def test_added_placeholder_is_rejected(self):
        report = edit.check_operation(
            "The plan covers migration, onboarding, and rollback.",
            "The plan covers migration, onboarding, and rollback. "
            "[INSERT PRICING HERE]",
            "revise",
        )
        self.assertEqual(report["decision"], "reject")
        self.assertTrue(any(i["kind"] == "placeholder_added"
                            for i in report["items"]["added"]))

    def test_kept_placeholder_is_reported_not_failed(self):
        source = ("<div aria-label=\"Checkout summary\"><p>We delve into "
                  "pricing below. Pricing starts at <strong>29.99</strong> "
                  "per month.</p><blockquote>\"Security is a process.\""
                  "</blockquote><p>See <a href=\"https://example.com/docs\">"
                  "the docs</a> for details [add release date].</p></div>")
        candidate = source.replace("We delve into pricing",
                                   "We dig into pricing")
        report = edit.check_operation(source, candidate, "revise",
                                      required_terms=("Checkout summary",),
                                      required_facts=("Pricing starts at",))
        self.assertEqual(report["decision"], "accept")
        self.assertTrue(any(i["kind"] == "placeholder_kept_unresolved"
                            for i in report["items"]["unresolved"]))

    def test_introduced_malformed_markup_is_rejected(self):
        report = edit.check_operation(
            "The rollout starts next week.",
            "The rollout starts next week.</div>",
            "revise",
        )
        self.assertEqual(report["decision"], "reject")
        self.assertIn("leaked_markup", report["integrity"]["failures"])


class TestReviewSeparation(unittest.TestCase):
    """Information gain stays a human-review prompt, never a deduction."""

    def setUp(self):
        self.registry = load_registry()

    def test_information_gain_resolves_to_review(self):
        report = edit.check_operation(
            "The queue worker lost its lease, which caused the backlog.",
            "The queue worker lost its lease, which caused the backlog. "
            "Operators watch renewal logs to catch this earlier.",
            "revise",
            review_prompts={
                "information_gain": "Check that the added background stays "
                                    "on-topic and carries no unverified "
                                    "claims.",
            },
        )
        self.assertEqual(report["decision"], "review")
        self.assertEqual(report["review"]["status"], "unresolved")
        kinds = {item["kind"] for item in report["review"]["items"]}
        self.assertEqual(kinds, {"information_gain"})

    def test_risk_delta_never_changes_the_decision(self):
        base = edit.check_operation(
            "The queue worker lost its lease, which caused the backlog.",
            "The queue worker lost its lease, which caused the backlog. "
            "Operators watch renewal logs to catch this earlier.",
            "revise",
        )
        self.assertEqual(base["decision"], "accept")


class TestProductionCorpus(unittest.TestCase):
    """The production edit-integrity corpus passes end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = edit.run_edit_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "edit-audit-reports-without-rewriting",
            "edit-audit-vs-revise-audit", "edit-audit-vs-revise-revise",
            "edit-revise-certainty-strengthening-rejected",
            "edit-revise-causal-strengthening-rejected",
            "edit-draft-voice-sample-style-only",
            "edit-draft-voice-donates-memory",
            "edit-revise-structured-document-preserved",
            "edit-transform-reorder-sections-preserved",
            "edit-transform-dropped-caveat-rejected",
            "edit-review-information-gain",
        }
        self.assertEqual(ids & required, required)

    def test_every_operation_appears_in_the_corpus(self):
        operations = {fixture["operation"] for fixture in load_fixtures()}
        self.assertEqual(operations, set(OPERATIONS))

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestBoundaries(unittest.TestCase):
    """Edit-integrity results never claim authorship or detector immunity."""

    def setUp(self):
        self.registry = load_registry()

    def test_every_report_carries_the_disclaimer(self):
        for fixture in load_fixtures():
            report = edit.run_edit_fixture(fixture, self.registry)
            self.assertIn("never prove", report["meta"]["disclaimer"])
            self.assertFalse(report["risk"]["authorship_evidence"])
            self.assertTrue(report["risk"]["advisory"])

    def test_corpus_report_carries_the_disclaimer(self):
        report = edit.run_edit_corpus(load_fixtures(), self.registry)
        self.assertIn("never prove", report["disclaimer"])


if __name__ == "__main__":
    unittest.main()
