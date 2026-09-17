#!/usr/bin/env python3
"""Tests for the Sepia-style operation and venue routing runner (issue #94).

Covers the acceptance criteria:
  - review never rewrites and every finding carries a quoted span, rule,
    status, and reason
  - n/a is available when a structural feature does not apply to the venue
  - over-correction records where applying a rule would flatten valid voice
    or structure (formal semicolons, author habits)
  - refactor lists the full finding set, applies only accepted edits, and
    reports rejected and unresolved findings
  - recreate extracts facts, claims, quotes, intent, and constraints from
    the source and verifies the candidate keeps them
  - ticket, developer-reply, postmortem, technical-article, and release-note
    fixtures activate distinct expectations
  - fiction guidance is opt-in and cannot affect general or technical
    scoring
  - the question-under-discussion reflection tail has an exact deterministic
    condition; the paragraph question check stays human-review guidance
  - formal semicolons, quoted banned words, conventional headings, and
    author habits have false-positive cases

Run: python3 -m unittest tests/test_sepia_routing.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import sepia  # noqa: E402
from registry import filter_rules_by_profile  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "sepia-routing-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
SEPIA = os.path.join(ROOT, "sepia.py")
VALIDATE = os.path.join(ROOT, "validate.py")
SCORE = os.path.join(ROOT, "score.py")

STATUSES = ("keep", "revise", "ask-author", "cut", "n/a", "over-correction")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def make_fixture(rid="sepia-review-test", **overrides):
    fixture = {
        "id": rid,
        "operation": "review",
        "venue": "ticket",
        "source": "We utilize the API to fetch records.",
        "expected_decision": "revise",
    }
    fixture.update(overrides)
    return fixture


def run_score(input_text, profile="general"):
    result = subprocess.run([sys.executable, SCORE, "--profile", profile,
                             "--stdin"], capture_output=True, text=True,
                            cwd=ROOT, input=input_text)
    return json.loads(result.stdout), result.returncode


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestFixtureSchema(unittest.TestCase):
    """The sepia-routing fixture schema validates operations and statuses."""

    def setUp(self):
        self.registry = load_registry()

    def test_all_fixtures_validate(self):
        fixtures = load_fixtures()
        seen = set()
        for fixture in fixtures:
            errors = sepia.validate_fixture(fixture, seen)
            self.assertEqual(errors, [], "fixture %s: %s"
                             % (fixture.get("id"), errors))

    def test_unknown_venue_rejected(self):
        errors = sepia.validate_fixture(
            make_fixture("bad-venue", venue="novel"), set())
        self.assertTrue(any("venue must be one of" in error
                            for error in errors))

    def test_fiction_cannot_carry_venue(self):
        errors = sepia.validate_fixture(
            make_fixture("fiction-venue", profile="fiction", venue="ticket"),
            set())
        self.assertTrue(any("fiction profile must not carry a venue" in error
                            for error in errors))

    def test_unknown_status_rejected(self):
        errors = sepia.validate_fixture(
            make_fixture("bad-status",
                         expected_statuses={"vocab-utilize": "delete"}),
            set())
        self.assertTrue(any("must be one of" in error for error in errors))


class TestReviewOperation(unittest.TestCase):
    """Review never rewrites; every finding has the four required fields."""

    def setUp(self):
        self.registry = load_registry()

    def test_review_never_rewrites(self):
        report = sepia.review_venue("We utilize the API to fetch records.",
                                    "ticket", self.registry)
        self.assertFalse(report["edited"])
        self.assertEqual(report["operation"], "review")
        for finding in report["findings"]:
            self.assertIn("excerpt", finding)
            self.assertIn("rule_id", finding)
            self.assertIn("status", finding)
            self.assertIn("why", finding)
            self.assertIn("span", finding)

    def test_review_reports_banned_word(self):
        report = sepia.review_venue("We utilize the API to fetch records.",
                                    "ticket", self.registry)
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("vocab-utilize"), "revise")
        self.assertEqual(report["decision"], "revise")

    def test_review_clean_prose_is_no_finding(self):
        report = sepia.review_venue(
            "Run `fetch` with version 2.4. When the cache is cold, then one "
            "record should come back.", "ticket", self.registry)
        self.assertEqual(report["decision"], "no-finding")

    def test_n_a_available_by_venue(self):
        source = ("Reproduce with version 2.4: run `fetch`. When the cache "
                  "is cold, then one record should come back. Opened at "
                  "09:00.")
        report = sepia.review_venue(source, "ticket", self.registry)
        checks = {row["feature"]: row["status"]
                  for row in report["venue_checks"]}
        self.assertEqual(checks["timeline"], "n/a")
        self.assertEqual(checks["repro"], "keep")
        self.assertEqual(checks["acceptance"], "keep")

    def test_missing_venue_feature_flags_revise(self):
        report = sepia.review_venue(
            "The service went down. It came back up. We changed the process.",
            "postmortem", self.registry)
        checks = {row["feature"]: row["status"]
                  for row in report["venue_checks"]}
        self.assertEqual(checks["timeline"], "missing")
        self.assertEqual(report["decision"], "revise")

    def test_overcorrection_formal_semicolons(self):
        report = sepia.review_venue(
            "The deploy failed; the cache kept evicting entries; users saw "
            "timeouts for 40 minutes.", "technical-article", self.registry)
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("fmt-semicolon"), "over-correction")
        self.assertEqual(report["decision"], "over-correction")

    def test_overcorrection_author_habit(self):
        report = sepia.review_venue(
            "We utilize the API to fetch records. Reproduce with version "
            "2.4: run `fetch`. When the cache is cold, then one record "
            "should come back.",
            "ticket", self.registry,
            author_habits=("the author writes 'utilize'",))
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("vocab-utilize"), "over-correction")

    def test_quoted_banned_word_is_keep(self):
        report = sepia.review_venue(
            'Fixed the review comment; the writer quoted "leverage" in '
            "their note, and I'm not sure why.",
            "developer-reply", self.registry)
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("vocab-leverage"), "keep")

    def test_conventional_headings_are_keep(self):
        report = sepia.review_venue(
            "## Added\n\nAdded a retry queue.\n\n## Removed\n\nRemoved the "
            "legacy scheduler.", "release-note", self.registry)
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("struct-fragmented-headers"), "keep")

    def test_venue_routing_activates_distinct_expectations(self):
        source = ("At 02:14 the queue backed up because the worker lost its "
                  "lease. 40% of users saw errors for 12 minutes. We don't "
                  "know why the alert was silent.")
        postmortem = sepia.review_venue(source, "postmortem", self.registry)
        ticket = sepia.review_venue(source, "ticket", self.registry)
        pm_checks = {row["feature"]: row["status"]
                     for row in postmortem["venue_checks"]}
        tk_checks = {row["feature"]: row["status"]
                     for row in ticket["venue_checks"]}
        self.assertEqual(pm_checks["timeline"], "keep")
        self.assertEqual(pm_checks["uncertainty"], "keep")
        self.assertEqual(tk_checks["timeline"], "n/a")
        self.assertEqual(tk_checks["repro"], "missing")


class TestRefactorOperation(unittest.TestCase):
    """Refactor lists the full finding set and applies only accepted edits."""

    def setUp(self):
        self.registry = load_registry()

    def test_applies_only_accepted_edit(self):
        report = sepia.refactor_venue(
            "We utilize the API to fetch records and leverage the cache.",
            "ticket", self.registry,
            accepted_edits=({"rule_id": "vocab-utilize", "replacement": "use"},))
        self.assertEqual(report["decision"], "applied")
        applied = [item["rule_id"] for item in report["accepted"]]
        rejected = [item["rule_id"] for item in report["rejected"]]
        unresolved = [item["rule_id"] for item in report["unresolved"]]
        self.assertEqual(applied, ["vocab-utilize"])
        self.assertIn("vocab-leverage", rejected)
        self.assertIn("vocab-leverage", unresolved)
        self.assertIn("and leverage the cache.", report["text"])

    def test_reports_unresolved_findings(self):
        report = sepia.refactor_venue(
            "We utilize the API. It's worth noting that it's fast.",
            "ticket", self.registry,
            accepted_edits=({"rule_id": "vocab-utilize", "replacement": "use"},))
        self.assertEqual(report["decision"], "applied")
        unresolved = [item["rule_id"] for item in report["unresolved"]]
        self.assertIn("phrase-worth-noting", unresolved)

    def test_no_accepted_edits_means_no_change(self):
        report = sepia.refactor_venue(
            "We utilize the API to fetch records.", "ticket", self.registry)
        self.assertEqual(report["decision"], "no-change")
        self.assertFalse(report["edited"])
        self.assertEqual(report["text"],
                         "We utilize the API to fetch records.")

    def test_refactor_lists_full_finding_set(self):
        report = sepia.refactor_venue(
            "We utilize the API to fetch records.", "ticket", self.registry)
        rule_ids = [finding["rule_id"] for finding in report["findings"]]
        self.assertIn("vocab-utilize", rule_ids)

    def test_refactor_ignores_fabricated_rule_edit(self):
        report = sepia.refactor_venue(
            "We utilize the API to fetch records.", "ticket", self.registry,
            accepted_edits=({"rule_id": "fabricated-rule",
                             "replacement": "replace"},))
        self.assertEqual(report["decision"], "no-change")
        self.assertEqual(report["text"],
                         "We utilize the API to fetch records.")
        self.assertEqual(report["accepted"], [])


class TestRecreateOperation(unittest.TestCase):
    """Recreate extracts the source inventory and verifies the candidate."""

    def setUp(self):
        self.registry = load_registry()

    def test_postmortem_keeps_inventory(self):
        source = ("At 02:14 the queue backed up because the worker lost its "
                  "lease. 40% of users saw errors for 12 minutes. We don't "
                  "know why the alert was silent.")
        candidate = ("The queue backed up because the worker lost its lease. "
                     "40% of users saw errors for 12 minutes. We don't know "
                     "why the alert was silent. It started at 02:14.")
        report = sepia.recreate_venue(
            source, candidate, "postmortem", self.registry,
            required_facts=("40% of users saw errors",))
        self.assertEqual(report["decision"], "accept")
        self.assertIn("venue_preserve_features", report["extracted"])
        self.assertIn("quotes", report["extracted"])
        self.assertIn("intent", report["extracted"])
        self.assertIn("constraints", report["extracted"])

    def test_postmortem_drops_timeline_fails(self):
        source = ("At 02:14 the queue backed up because the worker lost its "
                  "lease. 40% of users saw errors for 12 minutes. We don't "
                  "know why the alert was silent.")
        candidate = ("The queue backed up because the worker lost its lease. "
                     "40% of users saw errors. We are investigating.")
        report = sepia.recreate_venue(
            source, candidate, "postmortem", self.registry,
            required_facts=("40% of users saw errors",))
        self.assertEqual(report["decision"], "reject")
        missing_kinds = [item["kind"] for item in report["missing"]]
        self.assertIn("venue_feature", missing_kinds)

    def test_developer_reply_must_keep_caveat(self):
        source = ("Fixed the retry bug. The queue drops jobs on redeploy, "
                  "but only when the lease expires; I'm not sure if the "
                  "alert fires.")
        candidate = "Fixed. The queue drops jobs when the lease expires."
        report = sepia.recreate_venue(source, candidate, "developer-reply",
                                      self.registry)
        self.assertEqual(report["decision"], "reject")
        missing_kinds = [item["kind"] for item in report["missing"]]
        self.assertIn("venue_feature", missing_kinds)

    def test_quote_extraction_and_verification(self):
        source = ("The runbook says: \"always drain the queue first.\" The "
                  "worker lost its lease at 02:14, which caused the backlog.")
        candidate = "The worker lost its lease at 02:14."
        report = sepia.recreate_venue(
            source, candidate, "postmortem", self.registry,
            required_facts=("The worker lost its lease",),
            declared_claims=("which caused the backlog",))
        self.assertEqual(report["decision"], "reject")
        missing_kinds = [item["kind"] for item in report["missing"]]
        self.assertIn("quote", missing_kinds)
        self.assertIn("claim", missing_kinds)


class TestFictionProfile(unittest.TestCase):
    """Fiction guidance is opt-in and cannot affect general or technical."""

    def setUp(self):
        self.registry = load_registry()

    def test_fiction_rules_excluded_from_general_and_technical(self):
        fiction_ids = {"fiction-unresolved-tension",
                       "fiction-irregular-paragraphs"}
        for profile in ("general", "technical"):
            active = {rule["id"] for rule in
                      filter_rules_by_profile(self.registry["rules"], profile)}
            self.assertTrue(fiction_ids.isdisjoint(active),
                            "fiction rules leaked into %s" % profile)

    def test_fiction_profile_activates_fiction_rules(self):
        active = {rule["id"] for rule in
                  filter_rules_by_profile(self.registry["rules"], "fiction")}
        self.assertIn("fiction-unresolved-tension", active)
        self.assertIn("fiction-irregular-paragraphs", active)

    def test_fiction_rules_never_scored(self):
        for profile in ("general", "technical"):
            _result, _rc = run_score("The garden went quiet.", profile)
            for rule_id in ("fiction-unresolved-tension",
                            "fiction-irregular-paragraphs"):
                self.assertNotIn(
                    rule_id, _result["findings"],
                    "%s fired fiction rule %s" % (profile, rule_id))

    def test_fiction_relaxes_mechanism_in_review(self):
        source = ("The silence caused the garden to wither. A door stayed "
                  "shut. The tomatoes ripened anyway.")
        fiction = sepia.review_venue(source, None, self.registry,
                                     profile="fiction")
        general = sepia.review_venue(source, "postmortem", self.registry,
                                     profile="general")
        fiction_statuses = {finding["rule_id"]: finding["status"]
                            for finding in fiction["findings"]}
        general_statuses = {finding["rule_id"]: finding["status"]
                            for finding in general["findings"]}
        self.assertEqual(fiction_statuses.get("mechanism-causality"),
                         "over-correction")
        self.assertEqual(general_statuses.get("mechanism-causality"),
                         "ask-author")

    def test_unresolved_tension_and_irregular_paragraphs_valid(self):
        source = ("The garden went quiet.\n\nThe door stayed shut. A "
                  "neighbor called, once.\n\nThe tomatoes ripened anyway.")
        report = sepia.review_venue(source, None, self.registry,
                                    profile="fiction")
        self.assertEqual(report["decision"], "no-finding")


class TestQuestionUnderDiscussion(unittest.TestCase):
    """The reflection tail is deterministic; the paragraph check is guidance."""

    def setUp(self):
        self.registry = load_registry()

    def test_reflection_tail_is_a_finding(self):
        source = ("The deploy broke the cold start on Tuesday. It cut cold "
                  "start from 1.8s to 0.4s.\n\nThe team changed the alert "
                  "threshold on Friday. The monitor went quiet.\n\nIn the "
                  "end, what mattered was the team's resilience.")
        report = sepia.review_venue(source, "technical-article",
                                    self.registry)
        statuses = {finding["rule_id"]: finding["status"]
                    for finding in report["findings"]}
        self.assertEqual(statuses.get("sepia-qud-reflection-tail"), "cut")
        self.assertTrue(report["qud"]["guidance_only"])
        self.assertEqual(report["qud"]["deterministic_rules"],
                         ["sepia-qud-reflection-tail"])

    def test_single_paragraph_has_no_tail(self):
        report = sepia.review_venue(
            "In the end, the deploy worked.", "technical-article",
            self.registry)
        self.assertEqual(report["qud"]["reflection_tail"], [])

    def test_paragraph_question_check_is_guidance(self):
        qud = sepia.qud_review("One paragraph.\n\nA second paragraph.")
        self.assertTrue(all(entry["status"] == "guidance"
                            for entry in qud["paragraphs"]))
        self.assertIn("question", qud["paragraphs"][0])


class TestCorpus(unittest.TestCase):
    """The shipped fixture corpus validates and passes."""

    def test_corpus_gate_passes(self):
        fixtures = load_fixtures()
        report = sepia.run_corpus(fixtures, load_registry(), REGISTRY)
        self.assertEqual(report["schema_errors"], [])
        self.assertTrue(report["gate_pass"],
                        "failing: %s" % report["failing_ids"])
        self.assertEqual(report["failed"], 0)

    def test_validator_runs_sepia_checks(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestCli(unittest.TestCase):
    """The CLI entry points exercise each operation."""

    def setUp(self):
        self.registry = load_registry()

    def test_cli_review(self):
        result = subprocess.run(
            [sys.executable, SEPIA, "review", "--source-text",
             "We utilize the API to fetch records.", "--venue", "ticket"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["edited"])

    def test_cli_fiction(self):
        result = subprocess.run(
            [sys.executable, SEPIA, "review", "--source-text",
             "The garden went quiet.", "--fiction"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["profile"], "fiction")

    def test_cli_refactor(self):
        result = subprocess.run(
            [sys.executable, SEPIA, "refactor", "--source-text",
             "We utilize the API to fetch records.", "--venue", "ticket",
             "--accept", "vocab-utilize=use"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["decision"], "applied")
        self.assertEqual(report["text"], "We use the API to fetch records.")

    def test_cli_recreate(self):
        result = subprocess.run(
            [sys.executable, SEPIA, "recreate", "--source-text",
             "Run `fetch` with version 2.4. When the cache is cold, then "
             "three records come back instead of one.",
             "--candidate",
             "Run `fetch` with version 2.4. When the cache is cold, then "
             "three records come back instead of one.",
             "--venue", "ticket"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["decision"], "accept")

    def test_cli_fixture_corpus(self):
        result = subprocess.run(
            [sys.executable, SEPIA, "--fixtures",
             os.path.join(ROOT, "skills", "antislop", "evals",
                          "sepia-routing-fixtures.json")],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["gate_pass"])


if __name__ == "__main__":
    unittest.main()
