#!/usr/bin/env python3
"""Tests for rule provenance and decay (issue #101).

Covers the acceptance criteria:
  - registry validation supports and checks the evidence metadata schema
  - adopted external concepts identify an exact commit and source-file
    permalink, not only a repository home page
  - stable project policy, contextual heuristic, and dated external
    observation remain distinguishable
  - existing rules use explicit project-policy, project-fixture, or unknown
    provenance where appropriate
  - stale lexical evidence can be listed without disabling a rule
    automatically
  - external numeric thresholds cannot become strict without a directly
    identified source and local fixtures
  - candidate metrics have matched-length and matched-profile clean cases
  - the absolute zero-em-dash policy stays stable regardless of changing
    corpus observations
  - the five evaluation fixtures (house rule, stale lexical heuristic,
    structural fixture rule, scientific register, conjunction chain vs
    grammatical enumeration) all pass

Run: python3 -m unittest tests/test_provenance.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import provenance  # noqa: E402

REGISTRY = os.path.join(ROOT, "rules.json")
VALIDATE = os.path.join(ROOT, "tools", "validate.py")
PROVENANCE = os.path.join(ROOT, "tools", "provenance.py")
FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "provenance-fixtures.json")

EVIDENCE_CLASSES = (
    "project-policy", "project-fixture", "upstream-evidence",
    "tested-adaptation", "primary-research", "secondary-claim",
    "maintainer-judgment", "unknown",
)
DECAY_STATES = ("current", "review", "stale")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def run(*args, cwd=ROOT):
    result = subprocess.run([sys.executable] + list(args), capture_output=True,
                            text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def make_rule(rid="provenance-test-rule", **overrides):
    """A minimal schema-valid rule with evidence_meta overrides."""
    rule = {
        "id": rid,
        "text": "example",
        "category": "vocabulary",
        "severity": "high",
        "base_weight": 8,
        "detection_class": "exact_match",
        "profiles": ["*"],
        "exceptions": [],
        "overlaps": [],
        "examples": [],
        "confidence": "high",
        "semantic_type": "forbidden",
        "correction": "fix it",
        "sources": ["drunkrhin0/antislop (self)"],
        "evidence": "a match is sufficient evidence",
        "false_positive_boundary": "quoted material is not a target",
        "review_mode": "deterministic",
        "evidence_meta": {
            "class": "project-policy",
            "last_reviewed": "2026-09-01",
            "decay": "current",
        },
    }
    rule.update(overrides)
    return rule


def make_registry(*rules):
    return {
        "version": "2.0.3",
        "description": "test",
        "rules": list(rules),
        "evidence_classes": {
            name: "evidence class %s" % name for name in EVIDENCE_CLASSES
        },
        "decay_states": {
            name: "decay state %s" % name for name in DECAY_STATES
        },
        "review_queue": {
            "schema": "stale-lexical-review-queue-1",
            "entries": [],
            "candidates": [],
        },
    }


class TestEvidenceSchema(unittest.TestCase):
    """AC1: registry validation supports and checks the evidence schema."""

    def setUp(self):
        self.registry = load_registry()
        self.rules = self.registry["rules"]
        self.by_id = {r["id"]: r for r in self.rules}

    def test_every_rule_carries_evidence_meta(self):
        for rule in self.rules:
            self.assertIsInstance(rule.get("evidence_meta"), dict,
                                  f"Rule {rule['id']}: missing evidence_meta")

    def test_evidence_classes_are_all_represented_in_schema(self):
        classes = self.registry["evidence_classes"]
        for name in EVIDENCE_CLASSES:
            self.assertTrue(classes.get(name),
                            f"evidence class '{name}' missing from schema")

    def test_evidence_class_values_are_valid(self):
        for rule in self.rules:
            cls = rule["evidence_meta"]["class"]
            self.assertIn(cls, EVIDENCE_CLASSES,
                          f"Rule {rule['id']}: invalid evidence class")

    def test_decay_states_are_valid(self):
        for rule in self.rules:
            decay = rule["evidence_meta"]["decay"]
            self.assertIn(decay, DECAY_STATES,
                          f"Rule {rule['id']}: invalid decay state")

    def test_last_reviewed_and_source_dates_are_iso(self):
        import re
        for rule in self.rules:
            meta = rule["evidence_meta"]
            self.assertRegex(meta["last_reviewed"], r"^\d{4}-\d{2}-\d{2}$",
                             f"Rule {rule['id']}: bad last_reviewed")
            source_date = meta.get("source_date")
            if source_date is not None:
                self.assertRegex(source_date, r"^\d{4}-\d{2}-\d{2}$",
                                 f"Rule {rule['id']}: bad source_date")

    def test_production_schema_validates_clean(self):
        errors = provenance.validate_evidence_schema(self.registry)
        self.assertEqual(errors, [], "Production registry has schema errors: "
                         + "; ".join(errors))

    def test_rejects_unknown_evidence_class(self):
        reg = make_registry(make_rule(
            evidence_meta={"class": "bogus", "decay": "current",
                           "last_reviewed": "2026-09-01"}))
        errors = provenance.validate_evidence_schema(reg)
        self.assertTrue(any("unknown class" in e for e in errors), errors)

    def test_rejects_bad_last_reviewed_date(self):
        reg = make_registry(make_rule(
            evidence_meta={"class": "project-policy", "decay": "current",
                           "last_reviewed": "not-a-date"}))
        errors = provenance.validate_evidence_schema(reg)
        self.assertTrue(any("last_reviewed" in e for e in errors), errors)


class TestAdoptedConceptsPinSources(unittest.TestCase):
    """AC2: adopted external concepts pin an exact commit and permalink."""

    def setUp(self):
        self.registry = load_registry()
        self.by_id = {r["id"]: r for r in self.registry["rules"]}

    def test_upstream_evidence_rules_pin_commit_and_permalink(self):
        for rule in self.registry["rules"]:
            meta = rule["evidence_meta"]
            if meta.get("class") not in ("upstream-evidence",
                                         "tested-adaptation"):
                continue
            for field in ("repository", "commit", "source_file"):
                self.assertTrue(meta.get(field),
                                f"Rule {rule['id']}: class "
                                f"{meta['class']} missing '{field}'")
            self.assertRegex(meta["commit"], r"^[0-9a-f]{7,40}$",
                             f"Rule {rule['id']}: bad commit")
            self.assertTrue(meta["source_file"].startswith("http"),
                            f"Rule {rule['id']}: source_file not a URL")

    def test_no_repository_home_page_only(self):
        for rule in self.registry["rules"]:
            meta = rule["evidence_meta"]
            if meta.get("class") not in ("upstream-evidence",
                                         "tested-adaptation"):
                continue
            self.assertNotEqual(meta.get("source_file"), meta.get("repository"),
                                f"Rule {rule['id']}: source_file is just the "
                                "repository home page")

    def test_candidates_pin_the_reviewed_project_commit(self):
        candidates = self.registry["review_queue"]["candidates"]
        for cand in candidates:
            self.assertEqual(cand["commit"],
                             "a0571d7cad58a586a8b373e813e15046e484f028")
            self.assertIn("anti-ai-writing-skill", cand["source_file"])
            self.assertIn("/blob/", cand["source_file"])

    def test_validation_rejects_upstream_without_permalink(self):
        meta = {"class": "upstream-evidence", "decay": "current",
                "last_reviewed": "2026-09-01", "repository": "https://x/y"}
        reg = make_registry(make_rule(evidence_meta=meta))
        errors = provenance.validate_evidence_schema(reg)
        self.assertTrue(any("requires non-empty" in e for e in errors), errors)

    def test_validation_rejects_project_policy_with_external_commit(self):
        meta = {"class": "project-policy", "decay": "current",
                "last_reviewed": "2026-09-01", "commit": "abcdef1"}
        reg = make_registry(make_rule(evidence_meta=meta))
        errors = provenance.validate_evidence_schema(reg)
        self.assertTrue(any("must not pin an external commit" in e
                            for e in errors), errors)


class TestClassesAreDistinguishable(unittest.TestCase):
    """AC3 and AC4: classes stay distinguishable and existing rules are honest."""

    def setUp(self):
        self.registry = load_registry()
        self.rules = self.registry["rules"]
        self.by_id = {r["id"]: r for r in self.rules}

    def test_three_buckets_coexist(self):
        classes = {r["evidence_meta"]["class"] for r in self.rules}
        self.assertTrue(classes & {"project-policy", "project-fixture",
                                   "upstream-evidence", "secondary-claim"})

    def test_project_policy_used_for_house_rules(self):
        self.assertEqual(self.by_id["fmt-em-dash"]["evidence_meta"]["class"],
                         "project-policy")
        self.assertEqual(self.by_id["fmt-title-case"]["evidence_meta"]["class"],
                         "project-policy")

    def test_project_fixture_used_for_detector_rules(self):
        self.assertEqual(
            self.by_id["struct-sentence-length-variance"]["evidence_meta"]
            ["class"], "project-fixture")
        self.assertEqual(self.by_id["struct-passage-density"]["evidence_meta"]
                         ["class"], "project-fixture")

    def test_upstream_evidence_used_for_adopted_external_rules(self):
        self.assertEqual(self.by_id["vocab-delve"]["evidence_meta"]["class"],
                         "upstream-evidence")
        self.assertEqual(
            self.by_id["mechanism-importance"]["evidence_meta"]["class"],
            "upstream-evidence")

    def test_secondary_claim_used_for_written_guide_rules(self):
        self.assertEqual(self.by_id["struct-rule-of-three"]["evidence_meta"]
                         ["class"], "secondary-claim")

    def test_unknown_class_is_schema_supported(self):
        self.assertIn("unknown", self.registry["evidence_classes"])
        reg = make_registry(make_rule(
            evidence_meta={"class": "unknown", "decay": "current",
                           "last_reviewed": "2026-09-01"}))
        self.assertEqual(provenance.validate_evidence_schema(reg), [])

    def test_house_rule_has_no_external_study_claimed(self):
        meta = self.by_id["fmt-em-dash"]["evidence_meta"]
        self.assertNotIn("commit", meta)
        self.assertNotIn("source_file", meta)


class TestReviewQueueStaysNonDisabling(unittest.TestCase):
    """AC5: stale lexical evidence is listed without disabling a rule."""

    def setUp(self):
        self.registry = load_registry()
        self.by_id = {r["id"]: r for r in self.registry["rules"]}
        self.queue = self.registry["review_queue"]

    def test_queue_entries_reference_existing_rules_with_review_decay(self):
        for entry in self.queue["entries"]:
            rid = entry["rule_id"]
            self.assertIn(rid, self.by_id)
            self.assertEqual(self.by_id[rid]["evidence_meta"]["decay"],
                             "review")
            self.assertTrue(entry.get("reason"))

    def test_listed_rules_stay_active(self):
        for entry in self.queue["entries"]:
            rule = self.by_id[entry["rule_id"]]
            self.assertEqual(rule["semantic_type"], "forbidden")
            self.assertEqual(rule["review_mode"], "deterministic")

    def test_every_review_decay_rule_is_listed(self):
        listed = {e["rule_id"] for e in self.queue["entries"]}
        for rule in self.registry["rules"]:
            if rule["evidence_meta"]["decay"] in ("review", "stale"):
                self.assertIn(rule["id"], listed,
                              f"Rule {rule['id']} not listed in review queue")

    def test_queue_entries_still_detect(self):
        rule = self.by_id["phrase-knowledge-cutoff"]
        fired = provenance._run_detection(
            "As of my knowledge cutoff, the API shipped.", rule,
            self.registry, "general")
        self.assertTrue(fired, "review-queue rule must still detect")

    def test_validation_rejects_non_review_decay_entry(self):
        reg = make_registry(make_rule(
            evidence_meta={"class": "project-policy", "decay": "current",
                           "last_reviewed": "2026-09-01"}))
        reg["review_queue"]["entries"] = [
            {"rule_id": "provenance-test-rule", "decay": "current",
             "reason": "not actually stale"}]
        errors = provenance.validate_evidence_schema(reg)
        self.assertTrue(any("not decay=review/stale" in e for e in errors),
                        errors)

    def test_validation_rejects_unlisted_review_rule(self):
        reg = make_registry(make_rule(
            evidence_meta={"class": "project-policy", "decay": "review",
                           "last_reviewed": "2026-09-01"}))
        errors = provenance.validate_evidence_schema(reg)
        self.assertTrue(any("not listed in the review_queue" in e
                            for e in errors), errors)


class TestNumericThresholdsNeedSourceAndFixtures(unittest.TestCase):
    """AC6: external numeric thresholds cannot become strict unsourced."""

    def setUp(self):
        self.registry = load_registry()
        self.by_id = {r["id"]: r for r in self.registry["rules"]}

    def test_strict_numeric_rules_pin_source_and_local_fixtures(self):
        for rid in ("struct-passive-density", "struct-paragraph-duplication"):
            rule = self.by_id[rid]
            self.assertEqual(rule["review_mode"], "deterministic")
            meta = rule["evidence_meta"]
            self.assertEqual(meta["class"], "project-fixture")
            for field in ("repository", "commit", "source_file",
                          "local_fixtures"):
                self.assertTrue(meta.get(field),
                                f"Rule {rid}: missing '{field}'")

    def test_validation_rejects_strict_numeric_rule_without_source(self):
        rule = make_rule(review_mode="deterministic", semantic_type="forbidden",
                         text="More than 30% of sentences repeat",
                         evidence_meta={"class": "secondary-claim",
                                        "decay": "current",
                                        "last_reviewed": "2026-09-01"})
        errors = provenance.validate_evidence_schema(make_registry(rule))
        self.assertTrue(any("needs a directly identified source" in e
                            for e in errors), errors)

    def test_all_candidates_are_advisory(self):
        for cand in self.registry["review_queue"]["candidates"]:
            self.assertEqual(cand["signal"], "advisory")
            self.assertIsNone(cand.get("threshold"))


class TestCandidateCleanCases(unittest.TestCase):
    """AC7: candidate metrics have matched-length and matched-profile cases."""

    def setUp(self):
        self.registry = load_registry()
        with open(FIXTURES, encoding="utf-8") as f:
            self.fixtures = json.load(f)["evals"]
        self.candidates = self.registry["review_queue"]["candidates"]

    def test_every_candidate_names_both_clean_references(self):
        for cand in self.candidates:
            self.assertTrue(cand.get("matched_length_clean"),
                            f"{cand['id']}: no matched_length_clean")
            self.assertTrue(cand.get("matched_profile_clean"),
                            f"{cand['id']}: no matched_profile_clean")

    def test_clean_references_exist_and_are_clean(self):
        by_id = {f["id"]: f for f in self.fixtures}
        for cand in self.candidates:
            length = by_id.get(cand["matched_length_clean"])
            profile = by_id.get(cand["matched_profile_clean"])
            self.assertIsNotNone(length, f"{cand['id']}: bad length ref")
            self.assertIsNotNone(profile, f"{cand['id']}: bad profile ref")
            self.assertIs(length["expected_clean"], True)
            self.assertIs(profile["expected_clean"], True)

    def test_matched_length_case_controls_for_length(self):
        by_id = {f["id"]: f for f in self.fixtures}
        for cand in self.candidates:
            positive = next(f for f in self.fixtures
                            if f.get("candidate_id") == cand["id"]
                            and f.get("expected_clean") is False)
            clean = by_id[cand["matched_length_clean"]]
            pos_len = len(positive["source"])
            ratio = abs(len(clean["source"]) - pos_len) / pos_len
            self.assertLessEqual(ratio, 0.30,
                                 f"{cand['id']}: length ratio {ratio:.2f}")

    def test_matched_profile_case_controls_for_profile(self):
        by_id = {f["id"]: f for f in self.fixtures}
        for cand in self.candidates:
            positive = next(f for f in self.fixtures
                            if f.get("candidate_id") == cand["id"]
                            and f.get("expected_clean") is False)
            clean = by_id[cand["matched_profile_clean"]]
            self.assertEqual(clean["profile"], positive["profile"],
                             f"{cand['id']}: profile mismatch")

    def test_corpus_rejects_candidate_without_profile_clean_case(self):
        reg = make_registry(make_rule())
        cand = {
            "id": "candidate-nominalization",
            "name": "Nominalization",
            "description": "broken",
            "signal": "advisory",
            "fixture_ids": ["provenance-nominalization-positive",
                            "provenance-nominalization-clean-length",
                            "provenance-nominalization-clean-profile"],
            "matched_length_clean": "provenance-nominalization-clean-length",
        }
        reg["review_queue"]["candidates"] = [cand]
        errors = provenance.corpus_candidate_errors(
            [f for f in self.fixtures
             if f.get("candidate_id") == "candidate-nominalization"], reg)
        self.assertTrue(any("matched_profile_clean" in e for e in errors),
                        errors)


class TestZeroEmDashPolicy(unittest.TestCase):
    """AC8: the zero-em-dash policy stays stable regardless of corpus drift."""

    def setUp(self):
        self.registry = load_registry()
        self.by_id = {r["id"]: r for r in self.registry["rules"]}

    def test_em_dash_rule_is_stable_project_policy(self):
        rule = self.by_id["fmt-em-dash"]
        meta = rule["evidence_meta"]
        self.assertEqual(meta["class"], "project-policy")
        self.assertEqual(meta["decay"], "current")
        self.assertEqual(rule["semantic_type"], "forbidden")
        self.assertEqual(rule["review_mode"], "deterministic")
        self.assertEqual(rule["profiles"], ["*"])
        self.assertIn("zero", rule["evidence"].lower())

    def test_validation_rejects_decay_on_em_dash(self):
        reg = make_registry(make_rule())
        reg["rules"] = [
            {"id": "fmt-em-dash", "text": "Em-dash (—)", "category": "formatting",
             "severity": "high", "base_weight": 8,
             "detection_class": "exact_match", "profiles": ["*"],
             "semantic_type": "forbidden", "review_mode": "deterministic",
             "evidence": "Any instance; required output count is zero.",
             "evidence_meta": {"class": "project-policy",
                               "decay": "review",
                               "last_reviewed": "2026-09-01"}}]
        errors = provenance.validate_evidence_schema(reg)
        self.assertTrue(any("fmt-em-dash" in e for e in errors), errors)


class TestEvaluationFixtures(unittest.TestCase):
    """The five evaluation-fixture groups all pass."""

    def setUp(self):
        self.registry = load_registry()
        with open(FIXTURES, encoding="utf-8") as f:
            self.fixtures = json.load(f)["evals"]
        self.by_id = {f["id"]: f for f in self.fixtures}

    def test_all_shipped_fixtures_pass(self):
        report = provenance.run_provenance_corpus(self.fixtures, self.registry,
                                                  REGISTRY)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [], report["failures"])
        self.assertTrue(report["gate_pass"])

    def test_project_house_rule_fixture(self):
        self.assertIn("provenance-house-rule-em-dash", self.by_id)
        fx = self.by_id["provenance-house-rule-em-dash"]
        self.assertEqual(fx["kind"], "rule")
        self.assertEqual(fx["rule_id"], "fmt-em-dash")
        self.assertEqual(fx["expected_evidence_class"], "project-policy")

    def test_dated_lexical_heuristic_fixture(self):
        self.assertIn("provenance-stale-lexical-cutoff", self.by_id)
        fx = self.by_id["provenance-stale-lexical-cutoff"]
        self.assertEqual(fx["kind"], "rule")
        self.assertEqual(fx["rule_id"], "phrase-knowledge-cutoff")
        self.assertEqual(fx["expected_decay"], "review")

    def test_structural_fixture_rule(self):
        fx = self.by_id["provenance-structural-sentence-variance"]
        self.assertEqual(fx["rule_id"], "struct-sentence-length-variance")
        self.assertEqual(fx["expected_evidence_class"], "project-fixture")

    def test_scientific_terms_in_research_and_marketing(self):
        research = self.by_id["provenance-scientific-research"]
        marketing = self.by_id["provenance-scientific-marketing"]
        self.assertEqual(research["candidate_id"], "candidate-scientific-register")
        self.assertEqual(marketing["candidate_id"], "candidate-scientific-register")
        self.assertIs(research["expected_clean"], True)
        self.assertIs(marketing["expected_clean"], False)

    def test_conjunction_chain_and_grammatical_enumeration(self):
        chain = self.by_id["provenance-conjunction-chain"]
        enum = self.by_id["provenance-grammatical-enumeration"]
        self.assertIs(chain["expected_clean"], False)
        self.assertIs(enum["expected_clean"], True)

    def test_cli_runs_and_exits_zero(self):
        rc, stdout, stderr = run(PROVENANCE, "--fixtures", FIXTURES,
                                 "--registry", REGISTRY)
        self.assertEqual(rc, 0, stdout + stderr)


class TestValidatorWiring(unittest.TestCase):
    """validate.py runs the provenance schema and fixture checks."""

    def test_production_validation_passes(self):
        rc, stdout, stderr = run(VALIDATE, "--skills-dir", "skills",
                                 "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, stdout + stderr)


if __name__ == "__main__":
    unittest.main()