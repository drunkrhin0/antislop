#!/usr/bin/env python3
"""Regression tests for the pinned Humanizer 3.0 source review (issue #139)."""

import copy
import json
import os
import unittest

import provenance

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGISTRY_PATH = os.path.join(ROOT, "rules.json")
FIXTURES_PATH = os.path.join(ROOT, "skills", "antislop", "evals",
                             "humanizer-3-fixtures.json")
GENERATED_PATHS = (
    "skills/antislop/references/pattern-reference.md",
    "skills/antislop/references/marketing-pattern-reference.md",
    "powers/antislop/steering/marketing-pattern-reference.md",
    "powers/antislop/steering/audit-mode.md",
    "powers/antislop/steering/vocabulary.md",
    "powers/antislop/steering/structure-patterns.md",
    "powers/antislop/steering/examples.md",
    "powers/antislop/steering/audit-checklist.md",
)


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class TestHumanizerReview(unittest.TestCase):
    def setUp(self):
        self.registry = load_json(REGISTRY_PATH)
        corpus = load_json(FIXTURES_PATH)
        self.fixtures = corpus["evals"]
        self.review = self.registry["source_reviews"]["humanizer-3.0.0"]
        self.rules = {rule["id"]: rule for rule in self.registry["rules"]}

    def test_pinned_source_and_license_are_complete(self):
        self.assertEqual(self.review["reviewed_revision"], "9862685")
        self.assertIn("/blob/9862685/", self.review["source_file"])
        self.assertEqual(self.review["license"], "MIT")
        self.assertEqual(self.review["licence"], "MIT")
        self.assertEqual(self.review["source_date"], "2026-09-06")
        self.assertEqual(self.review["reviewed_date"], "2026-09-14")
        self.assertEqual(self.review["decay"], "current")

    def test_every_material_change_has_one_explicit_decision(self):
        decisions = self.review["decisions"]
        self.assertEqual(len(decisions), len({item["change"] for item in decisions}))
        self.assertTrue(all(item["decision"] in {"adopt", "adapt", "reject"}
                            for item in decisions))
        self.assertEqual(
            {item["decision"] for item in decisions},
            {"adopt", "adapt", "reject"},
        )

    def test_accepted_rules_have_paired_positive_and_clean_fixtures(self):
        report = provenance.validate_source_review_fixtures(self.fixtures,
                                                            self.registry)
        self.assertEqual(report, [])
        accepted = set()
        for item in self.review["decisions"]:
            if item["decision"] in {"adopt", "adapt"}:
                accepted.update(item["rule_ids"])
        for rule_id in accepted:
            cases = [fixture for fixture in self.fixtures
                     if fixture["rule_id"] == rule_id]
            self.assertEqual({case["kind"] for case in cases},
                             {"positive", "clean"})

    def test_generated_surfaces_contain_accepted_guidance(self):
        accepted = {"struct-vague-association", "struct-previous-version",
                    "pref-source-fidelity"}
        texts = []
        for relative in GENERATED_PATHS:
            with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
                texts.append(handle.read())
        for rule_id in accepted:
            self.assertIn(self.rules[rule_id]["text"], texts[0])
        self.assertTrue(all(self.rules["struct-vague-association"]["text"] in text
                            for text in texts[:4]))

    def test_mutation_missing_source_provenance_fails(self):
        mutated = copy.deepcopy(self.registry)
        del mutated["source_reviews"]["humanizer-3.0.0"]["source_file"]
        errors = provenance.validate_source_reviews(mutated)
        self.assertTrue(any("source_file" in error for error in errors), errors)

    def test_mutation_removing_accepted_rule_fails_fixture_gate(self):
        mutated = copy.deepcopy(self.registry)
        mutated["rules"] = [rule for rule in mutated["rules"]
                             if rule["id"] != "struct-vague-association"]
        errors = provenance.validate_source_reviews(mutated)
        errors.extend(provenance.validate_source_review_fixtures(self.fixtures,
                                                                 mutated))
        self.assertTrue(any("struct-vague-association" in error
                            for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
