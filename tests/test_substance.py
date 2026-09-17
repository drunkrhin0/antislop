#!/usr/bin/env python3
"""Tests for the Tagore-style substance report (issue #102).

Covers the acceptance criteria:
  - substance results are separate from the risk score and its score bands
  - every dimension includes evidence, a status, and an author-safe next step
  - `unknown` is used when author facts or intent are missing
  - clean but intentionally terse reference prose marks dimensions
    not-applicable
  - no result labels the text human or AI
  - contribution validation requires one narrow behavior and paired fixtures
  - source-derived examples are normalized to the zero-em-dash policy
  - the two Tagore groups are preserved: mechanics (directness, rhythm,
    trust, authenticity, density) and substance (specificity, restraint,
    voice)

Run: python3 -m unittest tests/test_substance.py -v
"""

import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import substance  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "substance-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
SUBSTANCE = os.path.join(ROOT, "substance.py")
VALIDATE = os.path.join(ROOT, "validate.py")

EMPTY_PROSE = (
    "The project matters. It represents an important step forward that could "
    "change how we work. The implications matter for everyone involved. We "
    "are optimistic. The work is going well."
)
REFERENCE_ENTRY = (
    "Postgres 16 supports MERGE with a WHERE clause. The ON clause can "
    "filter the rows that the MERGE action applies to. RETURNING is "
    "available for the modified rows."
)
OPINION_NO_STAKES = "I think this library is the best option for us."
OPINION_WITH_STAKES = (
    "I think this library is the best option for us. Without it, our "
    "release process stalls and the on-call team gets paged nightly."
)

AUTHORSHIP_PHRASE_RE = substance.AUTHORSHIP_PHRASE_RE


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def run_substance(*args, input_text=None):
    result = subprocess.run([sys.executable, SUBSTANCE] + list(args),
                            capture_output=True, text=True, cwd=ROOT,
                            input=input_text)
    return json.loads(result.stdout), result.returncode


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestTwoGroups(unittest.TestCase):
    """The report preserves Tagore's two groups and their dimensions."""

    def setUp(self):
        self.registry = load_registry()

    def test_group_membership(self):
        self.assertEqual(
            substance.MECHANICS,
            ("directness", "rhythm", "trust", "authenticity", "density"))
        self.assertEqual(substance.SUBSTANCE_DIMS,
                         ("specificity", "restraint", "voice"))
        self.assertEqual(set(substance.MECHANICS) | set(substance.SUBSTANCE_DIMS),
                         set(substance.DIMENSIONS))

    def test_report_has_both_groups(self):
        report = substance.report_text(EMPTY_PROSE, "argument", self.registry)
        groups = report["groups"]
        self.assertEqual({r["dimension"] for r in groups["mechanics"]},
                         set(substance.MECHANICS))
        self.assertEqual({r["dimension"] for r in groups["substance"]},
                         set(substance.SUBSTANCE_DIMS))

    def test_substance_group_is_unscored(self):
        report = substance.report_text(EMPTY_PROSE, "argument", self.registry)
        for result in report["groups"]["substance"]:
            self.assertNotIn("score", result)
            self.assertNotIn("weight", result)


class TestMechanicallyCleanEmptyProse(unittest.TestCase):
    """Clean mechanics with an empty substance group, separate from risk."""

    def setUp(self):
        self.registry = load_registry()

    def test_mechanics_are_evidenced(self):
        report = substance.report_text(EMPTY_PROSE, "argument", self.registry)
        for result in report["groups"]["mechanics"]:
            self.assertEqual(result["status"], "evidenced",
                             result["dimension"])

    def test_substance_is_unsupported(self):
        report = substance.report_text(EMPTY_PROSE, "argument", self.registry)
        statuses = {result["dimension"]: result["status"]
                    for result in report["groups"]["substance"]}
        self.assertEqual(statuses["specificity"], "unsupported")
        self.assertEqual(statuses["restraint"], "unsupported")
        self.assertEqual(statuses["voice"], "unsupported")

    def test_risk_stays_clean_band_and_separate(self):
        report = substance.report_text(EMPTY_PROSE, "argument", self.registry)
        self.assertEqual(report["risk"]["score"], 100)
        self.assertEqual(report["risk"]["band"],
                         "Low formulaic-writing risk.")
        self.assertTrue(report["risk"]["separate"])
        self.assertFalse(report["risk"]["authorship_evidence"])

    def test_risk_score_does_not_absorb_substance(self):
        data, rc = run_substance("--source-text", EMPTY_PROSE,
                                 "--medium", "argument")
        self.assertEqual(rc, 0)
        report = data
        self.assertEqual(report["risk"]["score"], 100)
        self.assertEqual(report["risk"]["separate"], True)


class TestReferenceNotApplicable(unittest.TestCase):
    """Clean terse reference prose marks dimensions not-applicable."""

    def setUp(self):
        self.registry = load_registry()

    def test_reference_marks_voice_and_rhythm_not_applicable(self):
        report = substance.report_text(REFERENCE_ENTRY, "reference",
                                       self.registry)
        statuses = {result["dimension"]: result["status"]
                    for result in (report["groups"]["mechanics"]
                                   + report["groups"]["substance"])}
        self.assertEqual(statuses["voice"], "not-applicable")
        self.assertEqual(statuses["rhythm"], "not-applicable")

    def test_reference_specificity_is_evidenced(self):
        report = substance.report_text(REFERENCE_ENTRY, "reference",
                                       self.registry)
        statuses = {result["dimension"]: result["status"]
                    for result in (report["groups"]["mechanics"]
                                   + report["groups"]["substance"])}
        self.assertEqual(statuses["specificity"], "evidenced")
        self.assertEqual(statuses["restraint"], "evidenced")

    def test_not_applicable_offers_no_forced_judgment(self):
        report = substance.report_text(REFERENCE_ENTRY, "reference",
                                       self.registry)
        voice = next(r for r in report["groups"]["substance"]
                     if r["dimension"] == "voice")
        self.assertIn("not applicable", voice["next_step"].lower())


class TestVoiceStakes(unittest.TestCase):
    """An opinion without stakes is thin; a supported opinion with
    consequences is evidenced."""

    def setUp(self):
        self.registry = load_registry()

    def voice_status(self, text):
        report = substance.report_text(text, "argument", self.registry)
        return next(r for r in report["groups"]["substance"]
                    if r["dimension"] == "voice")

    def test_opinion_without_stakes_is_unsupported(self):
        result = self.voice_status(OPINION_NO_STAKES)
        self.assertEqual(result["status"], "unsupported")
        self.assertIn("[TK:", result["next_step"])

    def test_opinion_with_consequences_is_evidenced(self):
        result = self.voice_status(OPINION_WITH_STAKES)
        self.assertEqual(result["status"], "evidenced")

    def test_stakes_question_never_invents_material(self):
        result = self.voice_status(OPINION_NO_STAKES)
        self.assertIn("[TK:", result["next_step"])
        self.assertNotIn("because", result["next_step"])


class TestUnknown(unittest.TestCase):
    """unknown is used when author facts or intent are missing."""

    def setUp(self):
        self.registry = load_registry()

    def test_quoted_opinion_is_unknown(self):
        text = ("The lead said the migration was a mistake. 'I think we "
                "should have stayed on the old schema,' she told us. 'We had "
                "no buffer for rollback.'")
        report = substance.report_text(text, "argument", self.registry)
        voice = next(r for r in report["groups"]["substance"]
                     if r["dimension"] == "voice")
        self.assertEqual(voice["status"], "unknown")

    def test_short_sample_rhythm_is_unknown(self):
        report = substance.report_text(OPINION_NO_STAKES, "argument",
                                       self.registry)
        rhythm = next(r for r in report["groups"]["mechanics"]
                      if r["dimension"] == "rhythm")
        self.assertEqual(rhythm["status"], "unknown")

    def test_ambiguous_claim_specificity_is_unknown(self):
        report = substance.report_text("We feel strongly about this.",
                                       "argument", self.registry)
        specificity = next(r for r in report["groups"]["substance"]
                           if r["dimension"] == "specificity")
        self.assertEqual(specificity["status"], "unknown")

    def test_unknown_next_step_is_a_question(self):
        report = substance.report_text("We feel strongly about this.",
                                       "argument", self.registry)
        for group in report["groups"].values():
            for result in group:
                if result["status"] == "unknown":
                    self.assertIn("[TK:", result["next_step"])


class TestEveryDimensionHasEvidence(unittest.TestCase):
    """Every dimension carries evidence, a status, and an author-safe next
    step."""

    def setUp(self):
        self.registry = load_registry()

    def test_all_dimensions_have_the_three_fields(self):
        for text in (EMPTY_PROSE, REFERENCE_ENTRY, OPINION_WITH_STAKES):
            report = substance.report_text(text, "argument", self.registry)
            for group in report["groups"].values():
                for result in group:
                    self.assertIn("dimension", result)
                    self.assertIn("group", result)
                    self.assertIn(result["status"], substance.STATUSES)
                    self.assertTrue(result["evidence"],
                                    result["dimension"])
                    self.assertTrue(result["next_step"],
                                    result["dimension"])


class TestNoHumanOrAiLabels(unittest.TestCase):
    """No result labels the text human or AI."""

    def setUp(self):
        self.registry = load_registry()

    def test_report_label_is_null(self):
        report = substance.report_text(EMPTY_PROSE, "argument", self.registry)
        self.assertIsNone(report["label"])

    def test_statuses_never_human_or_ai(self):
        for status in substance.STATUSES:
            self.assertNotIn(status.lower(), ("human", "ai"))
        report = substance.report_text(OPINION_WITH_STAKES, "argument",
                                       self.registry)
        for group in report["groups"].values():
            for result in group:
                self.assertIn(result["status"], substance.STATUSES)

    def test_evidence_and_next_steps_do_not_label(self):
        report = substance.report_text(EMPTY_PROSE, "argument", self.registry)
        for group in report["groups"].values():
            for result in group:
                for value in result["evidence"] + [result["next_step"]]:
                    self.assertIsNone(
                        AUTHORSHIP_PHRASE_RE.search(value),
                        "%s labels the text: %r"
                        % (result["dimension"], value))

    def test_label_errors_empty_for_all_production_sources(self):
        for fixture in load_fixtures():
            if fixture["kind"] != "report":
                continue
            report = substance.report_text(
                fixture["text"], fixture.get("medium", "argument"),
                self.registry)
            self.assertEqual(substance.label_errors(report), [],
                             fixture["id"])

    def test_disclaimer_never_proves_authorship(self):
        report = substance.report_text(EMPTY_PROSE, "argument", self.registry)
        self.assertIn("never", report["meta"]["disclaimer"].lower())


class TestContributionContract(unittest.TestCase):
    """Contribution validation requires one narrow behavior and paired
    fixtures."""

    def setUp(self):
        self.registry = load_registry()

    def proposal(self, **overrides):
        proposal = {
            "distinct_tell": ("Launch posts open with a cheerleading "
                              "announcement far more often than human "
                              "writing."),
            "rule": {
                "id": "proposal-cheer-announce",
                "name": "Cheerleading announcement opener",
                "pattern": r"\b(?:we are|we're) (?:excited|thrilled) to "
                           r"announce\b",
                "rewrite": ("Cut the announcement and state what the "
                            "product actually does."),
            },
            "before_text": "We are thrilled to announce the launch of Quill.",
            "after_text": ("Quill is a note-taking app we built after the "
                           "tools we tried were too rigid."),
            "model_context": "Claude 3.5 Sonnet, launch-post drafts",
            "frequency_context": "about 60% of sampled drafts",
            "fixtures": {
                "positive": [
                    {"text": "We are thrilled to announce our new editor.",
                     "expect": "finding"},
                ],
                "clean": [
                    {"text": "The editor ships today with inline review.",
                     "expect": "no-finding"},
                ],
            },
        }
        proposal.update(overrides)
        return proposal

    def test_complete_proposal_is_accepted(self):
        report = substance.validate_contribution(self.proposal(), self.registry)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["failures"], [])
        self.assertTrue(all(item["satisfied"] for item in report["items"]))

    def test_missing_clean_false_positive_fixture_is_rejected(self):
        proposal = self.proposal(
            fixtures={"positive": [
                {"text": "We are thrilled to announce our new editor.",
                 "expect": "finding"}]})
        report = substance.validate_contribution(proposal, self.registry)
        self.assertFalse(report["accepted"])
        self.assertTrue(any("clean false-positive fixture is missing"
                            in failure for failure in report["failures"]))

    def test_missing_distinct_tell_is_rejected(self):
        proposal = self.proposal(distinct_tell="")
        report = substance.validate_contribution(proposal, self.registry)
        self.assertFalse(report["accepted"])
        self.assertTrue(any("distinct_tell" in failure
                            for failure in report["failures"]))

    def test_missing_context_is_rejected_unless_marked_unknown(self):
        proposal = self.proposal(model_context="", frequency_context="")
        report = substance.validate_contribution(proposal, self.registry)
        self.assertFalse(report["accepted"])
        self.assertTrue(any("context" in failure
                            for failure in report["failures"]))
        proposal = self.proposal(model_context="", frequency_context="",
                                 context_unknown=True)
        report = substance.validate_contribution(proposal, self.registry)
        self.assertTrue(report["accepted"])

    def test_after_text_still_containing_pattern_is_rejected(self):
        proposal = self.proposal(
            after_text="We are excited to announce that Quill now ships.")
        report = substance.validate_contribution(proposal, self.registry)
        self.assertFalse(report["accepted"])
        self.assertTrue(any("after text still contains" in failure
                            for failure in report["failures"]))

    def test_before_text_without_pattern_is_rejected(self):
        proposal = self.proposal(
            before_text="The editor ships today with inline review.")
        report = substance.validate_contribution(proposal, self.registry)
        self.assertFalse(report["accepted"])
        self.assertTrue(any("before text does not contain" in failure
                            for failure in report["failures"]))

    def test_multiple_rules_are_rejected(self):
        proposal = self.proposal(rules=[{"id": "a", "name": "A",
                                         "pattern": "x",
                                         "rewrite": "r"},
                                        {"id": "b", "name": "B",
                                         "pattern": "y",
                                         "rewrite": "r"}])
        report = substance.validate_contribution(proposal, self.registry)
        self.assertFalse(report["accepted"])
        self.assertTrue(any("narrow_rule" in failure
                            for failure in report["failures"]))

    def test_positive_fixture_without_pattern_is_rejected(self):
        proposal = self.proposal(fixtures={
            "positive": [
                {"text": "The editor ships today with inline review.",
                 "expect": "finding"}],
            "clean": [
                {"text": "The editor ships today with inline review.",
                 "expect": "no-finding"}]})
        report = substance.validate_contribution(proposal, self.registry)
        self.assertFalse(report["accepted"])
        self.assertTrue(any("positive fixture" in failure
                            for failure in report["failures"]))

    def test_contract_items_in_registry_order(self):
        report = substance.validate_contribution(self.proposal(), self.registry)
        self.assertEqual([item["item"] for item in report["items"]],
                         list(substance.CONTRACT_ITEMS))


class TestFixtureSchema(unittest.TestCase):
    """The substance fixture schema validates."""

    def setUp(self):
        self.registry = load_registry()

    def test_valid_report_fixture_has_no_schema_errors(self):
        fixture = {
            "id": "schema-test-report",
            "kind": "report",
            "locale": "en-US",
            "label_provenance": "human-hand-labeled",
            "source": "test",
            "text": EMPTY_PROSE,
            "medium": "argument",
            "expected_statuses": {"voice": "unsupported"},
            "expected_label_none": True,
        }
        errors = substance.validate_fixture(fixture, set())
        self.assertEqual(errors, [])

    def test_valid_contribution_fixture_has_no_schema_errors(self):
        fixture = {
            "id": "schema-test-contribution",
            "kind": "contribution",
            "locale": "en-US",
            "label_provenance": "human-hand-labeled",
            "source": "test",
            "distinct_tell": "a distinct tell",
            "rule": {"id": "r", "name": "n", "pattern": "x",
                     "rewrite": "r"},
            "before_text": "before",
            "after_text": "after",
            "expected_accepted": True,
            "expected_failures": [],
        }
        errors = substance.validate_fixture(fixture, set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = substance.validate_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        substance.validate_fixture({"id": "dup", "kind": "report",
                                    "source": "s", "text": "t."}, seen)
        errors = substance.validate_fixture({"id": "dup", "kind": "report",
                                             "source": "s", "text": "t."},
                                            seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))

    def test_unknown_kind_is_rejected(self):
        errors = substance.validate_fixture({"id": "x", "kind": "review",
                                             "source": "s"}, set())
        self.assertTrue(any("kind must be one of" in error
                            for error in errors))

    def test_unknown_status_is_rejected(self):
        errors = substance.validate_fixture(
            {"id": "x", "kind": "report", "source": "s", "text": "t.",
             "expected_statuses": {"voice": "pass"}}, set())
        self.assertTrue(any("expected_statuses['voice'] must be one of"
                            in error for error in errors))

    def test_missing_label_provenance_is_rejected(self):
        errors = substance.validate_fixture(
            {"id": "x", "kind": "report", "text": "t."}, set())
        self.assertTrue(any("label_provenance must be a non-empty string"
                            in error for error in errors))


class TestProductionCorpus(unittest.TestCase):
    """The production substance corpus passes end to end."""

    def setUp(self):
        self.registry = load_registry()

    def test_corpus_passes(self):
        report = substance.run_corpus(load_fixtures(), self.registry)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        required = {
            "substance-empty-prose-clean-mechanics",
            "substance-reference-entry-pov-not-applicable",
            "substance-opinion-without-stakes",
            "substance-opinion-with-consequences",
            "substance-voice-unknown-quoted",
            "substance-contribution-missing-clean-fixture",
            "substance-contribution-accepted",
        }
        self.assertEqual(ids & required, required)

    def test_corpus_covers_both_unknown_and_not_applicable(self):
        report_fixtures = [f for f in load_fixtures() if f["kind"] == "report"]
        expected = [f for f in report_fixtures
                    if "not-applicable" in f.get("expected_statuses", {}).values()]
        unknown = [f for f in report_fixtures
                   if "unknown" in f.get("expected_statuses", {}).values()]
        self.assertTrue(expected)
        self.assertTrue(unknown)

    def test_fixture_prose_is_zero_em_dash_normalized(self):
        with open(FIXTURES, encoding="utf-8") as handle:
            raw = handle.read()
        self.assertNotIn("\u2014", raw)
        self.assertNotIn("\u2013", raw)
        self.assertNotIn(" -- ", raw)
        self.assertNotIn("->", raw)

    def test_validate_passes_on_production_skills(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)


class TestRegistrySchema(unittest.TestCase):
    """The registry carries the substance dimensions, statuses, and contract."""

    def setUp(self):
        self.registry = load_registry()

    def test_substance_dimensions_present(self):
        dimensions = self.registry["substance_dimensions"]
        self.assertEqual(list(dimensions["mechanics"].keys()),
                         list(substance.MECHANICS))
        self.assertEqual(list(dimensions["substance"].keys()),
                         list(substance.SUBSTANCE_DIMS))

    def test_substance_statuses_present(self):
        self.assertEqual(list(self.registry["substance_statuses"].keys()),
                         list(substance.STATUSES))

    def test_contribution_contract_items_present(self):
        items = self.registry["contribution_contract"]["items"]
        self.assertEqual([item["id"] for item in items],
                         list(substance.CONTRACT_ITEMS))
        source = self.registry["contribution_contract"]["source"]
        self.assertIn("1238743725cb2d731b780f237c82e0041c9b4c67", source)

    def test_registry_stays_at_3_0_0(self):
        self.assertEqual(self.registry["version"], "3.0.0")


class TestCliInterface(unittest.TestCase):
    """The command accepts --source-text, stdin, --proposal, and --fixtures."""

    def test_source_text_accepts_input(self):
        data, rc = run_substance("--source-text", OPINION_WITH_STAKES,
                                 "--medium", "argument")
        self.assertEqual(rc, 0)
        voice = next(r for r in data["groups"]["substance"]
                     if r["dimension"] == "voice")
        self.assertEqual(voice["status"], "evidenced")
        self.assertIsNone(data["label"])

    def test_stdin_accepts_input(self):
        data, rc = run_substance("--medium", "reference",
                                 input_text=REFERENCE_ENTRY)
        self.assertEqual(rc, 0)
        self.assertEqual(data["medium"], "reference")

    def test_unknown_medium_is_an_error(self):
        with self.assertRaises(ValueError):
            substance.report_text(OPINION_WITH_STAKES, "essay",
                                  load_registry())

    def test_proposal_flag_validates_a_proposal(self):
        import tempfile
        proposal = {
            "distinct_tell": "a distinct tell",
            "rule": {"id": "r", "name": "n", "pattern": "bounc",
                     "rewrite": "r"},
            "before_text": "the ball bounced twice",
            "after_text": "the ball stopped",
            "model_context": "a model",
            "fixtures": {"positive": [{"text": "the ball bounces"}],
                         "clean": [{"text": "the ball stops"}]},
        }
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", dir="/tmp", delete=False) as handle:
            json.dump(proposal, handle)
            path = handle.name
        try:
            data, rc = run_substance("--proposal", path)
            self.assertEqual(rc, 0)
            self.assertTrue(data["accepted"])
        finally:
            os.unlink(path)

    def test_fixture_corpus_exits_zero(self):
        result = subprocess.run(
            [sys.executable, SUBSTANCE, "--fixtures", FIXTURES],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["gate_pass"])

    def test_missing_file_is_a_usage_error(self):
        result = subprocess.run(
            [sys.executable, SUBSTANCE, "--file", os.path.join(ROOT, "nope.md")],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
