#!/usr/bin/env python3
"""Tests for the Human Review companion workflow contract (issue #66).

The optional Human Review workflow is documented in skills/antislop/SKILL.md,
its derivatives, and README.md as a local browser-review loop that keeps Human
Review separate from the rule registry, preserves the skills-only package
boundary, and leaves final acceptance with the human.

This module is a static documentation and feedback-contract test. It proves
the integration guidance names the source-of-truth rules and drives the
fixture corpus through the documented feedback contract without launching a
browser, downloading npm packages, or requiring Node. The corpus covers:

  - a Markdown batch with an exact wording edit carried across verbatim
  - a formatting edit represented by after_html and translated into source
    syntax
  - an anchored selection comment located by its quote in the source
  - multiple pages in one batch, every page handled
  - a localhost URL edit applied to the matching source, never the rendered
    response
  - a timeout that never counts as acceptance
  - an acknowledgement after every edit is applied
  - the post-review audit requirement

Run: python3 -m unittest tests/test_human_review_contract.py -v
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "human-review-fixtures.json")
SKILL_REFERENCES = (
    os.path.join(ROOT, "skills", "antislop", "references", "shared-contract.md"),
    os.path.join(ROOT, "skills", "antislop", "references", "human-review.md"),
    os.path.join(ROOT, "skills", "antislop", "references", "preservation-contract.md"),
)
README = os.path.join(ROOT, "README.md")
REGISTRY = os.path.join(ROOT, "rules.json")
SKILLS_DIR = os.path.join(ROOT, "skills")

REQUIRED_SCENARIOS = {
    "hr-markdown-exact-wording-edit",
    "hr-formatting-edit-after-html",
    "hr-anchored-selection-comment",
    "hr-multiple-pages-batch",
    "hr-localhost-url-edit-to-source",
    "hr-timeout-not-acceptance",
    "hr-ack-after-all-edits",
    "hr-post-review-audit",
}

VALID_SCENARIOS = {
    "markdown-exact-wording-edit",
    "formatting-edit-after-html",
    "anchored-selection-comment",
    "multiple-pages-batch",
    "localhost-url-edit-to-source",
    "timeout-not-acceptance",
    "acknowledgement-after-all-edits",
    "post-review-audit",
}

# Source-of-truth rules the documentation must name. The SKILL.md file is the
# canonical skill surface; README.md carries the integration instructions.
# The checks are case-insensitive: both sides are lowercased.
SKILL_CONTRACT_PHRASES = (
    "rendered for review",
    "source remains the write target",
    "carried across verbatim",
    "before_html",
    "after_html",
    "source syntax",
    "every page in the feedback batch",
    'kind: "url"',
    "localhost route",
    "locate the matching source",
    "timeout is not acceptance",
    "after the human edits are applied",
    "overwrite the source",
    "never require it",
)

README_CONTRACT_PHRASES = (
    "rendered for review",
    "source remains the write target",
    "carried across verbatim",
    "before_html",
    "after_html",
    "relevant source syntax",
    "every page in the feedback batch",
    'kind: "url"',
    "localhost route",
    "locate and update the matching source",
    "timeout is not acceptance",
    "after the human edits are applied",
    "overwrite the source",
    "never required for normal antislop use or validation",
    "npx -y human-review",
    "poll",
    "--ack",
    "json feedback contract",
)

VALID_STATUSES = ("feedback", "timeout")


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def load_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_skill_surface():
    return chr(10).join(load_text(path) for path in SKILL_REFERENCES)


def translate_formatting(after_html):
    """Translate the inline formatting in after_html into Markdown syntax.

    Implements the documented translation for the corpus: strong becomes
    double asterisks and em becomes a single asterisk. Structural wrappers
    such as a paragraph tag map to Markdown structure and are dropped here,
    matching the rule that formatting is carried into the source, not
    reworded.
    """
    text = after_html
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text)
    return re.sub(r"<[^>]+>", "", text)


def validate_fixture(fixture, seen_ids):
    """Schema-validate one Human Review fixture. Returns error strings."""
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

    if fixture.get("scenario") not in VALID_SCENARIOS:
        errors.append("%s: scenario must be one of %s"
                      % (where, ", ".join(sorted(VALID_SCENARIOS))))

    for field in ("rationale", "expected_source_path"):
        value = fixture.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append("%s: %s must be a non-empty string" % (where, field))

    if not isinstance(fixture.get("source"), str):
        errors.append("%s: source must be a string" % where)

    batch = fixture.get("batch")
    if not isinstance(batch, dict):
        errors.append("%s: batch must be an object" % where)
    elif batch.get("status") not in VALID_STATUSES:
        errors.append("%s: batch.status must be one of %s"
                      % (where, ", ".join(VALID_STATUSES)))

    for field in ("timeout", "acceptance", "requires_post_audit",
                  "expects_ack"):
        if not isinstance(fixture.get(field), bool):
            errors.append("%s: %s must be a boolean" % (where, field))

    pages = fixture.get("expected_pages")
    if not (isinstance(pages, int) and not isinstance(pages, bool)
            and pages >= 0):
        errors.append("%s: expected_pages must be a non-negative integer"
                      % where)

    expected_after = fixture.get("expected_verbatim_after")
    if expected_after is not None and not isinstance(expected_after, str):
        if (not isinstance(expected_after, list)
                or any(not isinstance(item, str) or not item.strip()
                       for item in expected_after)):
            errors.append("%s: expected_verbatim_after must be a string, a "
                          "list of strings, or null" % where)
    if fixture.get("expected_source_edit") is not None and not isinstance(
            fixture.get("expected_source_edit"), str):
        errors.append("%s: expected_source_edit must be a string or null"
                      % where)
    return errors


def run_fixture(fixture):
    """Evaluate one fixture against the documented feedback contract."""
    failures = []
    batch = fixture["batch"]
    status = batch.get("status")
    pages = batch.get("pages", [])

    if fixture.get("timeout"):
        if status != "timeout":
            failures.append("a timeout fixture must carry status 'timeout'")
        if fixture.get("acceptance"):
            failures.append("a timeout must never be acceptance")
        if fixture.get("expects_ack"):
            failures.append("a timeout must not be acknowledged as handled")
        if pages:
            failures.append("a timeout carries no pages to handle")
        if fixture.get("expected_source_edit") is not None:
            failures.append("a timeout produces no source edit")
    else:
        if status != "feedback":
            failures.append("a handled batch must carry status 'feedback'")
        if len(pages) != fixture.get("expected_pages"):
            failures.append("expected %d page(s), got %d"
                            % (fixture.get("expected_pages"), len(pages)))

        if fixture.get("acceptance"):
            failures.append("applying feedback is never itself acceptance")

        expected = fixture.get("expected_verbatim_after")
        verbatim_values = set()
        for page in pages:
            if page.get("kind") == "url":
                url = page.get("url", "")
                if not url.startswith("http"):
                    failures.append("a url page must carry an http url")
                target = fixture["expected_source_path"]
                if target == url or target.startswith("http"):
                    failures.append("a url page must resolve to a source "
                                    "path, not the localhost route")
            else:
                if not fixture["expected_source_path"].endswith(
                        (".md", ".html")):
                    failures.append("a file page must name a writable "
                                    "source file")

            for edit in page.get("edits", []):
                after = edit.get("after")
                after_html = edit.get("after_html")
                if after is not None:
                    verbatim_values.add(after)
                    if isinstance(expected, list):
                        if after not in expected:
                            failures.append("edits[].after must be carried "
                                            "across verbatim")
                    elif after != expected:
                        failures.append("edits[].after must be carried "
                                        "across verbatim")
                    expected_edit = fixture.get("expected_source_edit")
                    if expected_edit and not isinstance(expected, list):
                        if after_html is not None:
                            translated = translate_formatting(after_html)
                            if translated not in expected_edit:
                                failures.append("after_html formatting must "
                                                "be translated into source "
                                                "syntax")
                        elif after not in expected_edit:
                            failures.append("the source edit must contain "
                                            "the verbatim after text")
                if (after is None and after_html is None
                        and page.get("comments")):
                    failures.append("a page must carry an edit or a comment")

            for comment in page.get("comments", []):
                quote = comment.get("quote")
                if comment.get("kind") == "selection" and quote:
                    if quote not in fixture.get("source", ""):
                        failures.append("a selection quote must appear in "
                                        "the source")

        if isinstance(expected, list):
            if verbatim_values != set(expected):
                failures.append("every expected verbatim edit must be "
                                "present in the batch")
        if fixture.get("expects_ack"):
            if not pages:
                failures.append("acknowledgement must follow after every "
                                "page is handled")
        if fixture.get("requires_post_audit") is not True:
            failures.append("the loop requires a final audit after the "
                            "human edits are applied")
    return failures


def run_corpus(fixtures):
    """Validate and evaluate the Human Review fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "fixture_count": len(fixtures),
            "passed": 0,
            "failed": len(fixtures),
            "failing_ids": [fixture.get("id", "?") for fixture in fixtures],
            "schema_errors": schema_errors,
            "failures": [],
            "gate_pass": False,
        }

    reports = []
    for fixture in fixtures:
        failures = run_fixture(fixture)
        reports.append({"id": fixture["id"], "failures": failures})
    failed = [report for report in reports if report["failures"]]
    return {
        "fixture_count": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "schema_errors": [],
        "failures": failed,
        "gate_pass": not failed,
    }


def make_fixture(rid="hr-test", **overrides):
    """A schema-valid Human Review fixture with per-test overrides."""
    fixture = {
        "id": rid,
        "scenario": "markdown-exact-wording-edit",
        "rationale": "Schema-valid fixture used by the contract tests.",
        "source": "# Test\n\nOne line to edit.\n",
        "expected_source_path": "docs/test.md",
        "expected_verbatim_after": "One line to keep.",
        "expected_source_edit": "# Test\n\nOne line to keep.\n",
        "batch": {
            "status": "feedback",
            "pages": [
                {
                    "file": "/abs/path/docs/test.md",
                    "comments": [],
                    "edits": [
                        {
                            "label": "Test line",
                            "kind": "edited",
                            "before": "One line to edit.",
                            "after": "One line to keep.",
                            "after_html": None,
                        }
                    ],
                }
            ],
            "overall_note": None,
        },
        "expected_pages": 1,
        "timeout": False,
        "acceptance": False,
        "requires_post_audit": True,
        "expects_ack": True,
    }
    fixture.update(overrides)
    return fixture


class TestFixtureSchema(unittest.TestCase):
    """The fixture schema validates the full feedback contract."""

    def test_valid_fixture_has_no_schema_errors(self):
        errors = validate_fixture(make_fixture(), set())
        self.assertEqual(errors, [])

    def test_production_fixtures_validate(self):
        seen = set()
        for fixture in load_fixtures():
            errors = validate_fixture(fixture, seen)
            self.assertEqual(errors, [], f"{fixture['id']}: {errors}")

    def test_duplicate_ids_are_rejected(self):
        seen = set()
        validate_fixture(make_fixture(), seen)
        errors = validate_fixture(make_fixture(), seen)
        self.assertTrue(any("duplicate fixture id" in error
                            for error in errors))

    def test_batch_status_must_be_valid(self):
        errors = validate_fixture(
            make_fixture(batch={"status": "closed"}), set())
        self.assertTrue(any("batch.status must be one of" in error
                            for error in errors))

    def test_scenario_must_be_valid(self):
        errors = validate_fixture(make_fixture(scenario="maybe"), set())
        self.assertTrue(any("scenario must be one of" in error
                            for error in errors))

    def test_boolean_flags_must_be_boolean(self):
        errors = validate_fixture(make_fixture(timeout="yes"), set())
        self.assertTrue(any("timeout must be a boolean" in error
                            for error in errors))

    def test_expected_pages_must_be_non_negative_integer(self):
        errors = validate_fixture(make_fixture(expected_pages=-1), set())
        self.assertTrue(any("expected_pages must be a non-negative integer"
                            in error for error in errors))

    def test_nullable_fields_accept_string_or_null(self):
        errors = validate_fixture(make_fixture(expected_verbatim_after=None,
                                               expected_source_edit=None),
                                  set())
        self.assertEqual(errors, [])


class TestDocumentationContract(unittest.TestCase):
    """The integration guidance names every source-of-truth rule."""

    def test_skill_names_the_contract_rules(self):
        skill = load_skill_surface().lower()
        missing = [phrase for phrase in SKILL_CONTRACT_PHRASES
                   if phrase not in skill]
        self.assertEqual(missing, [])

    def test_readme_names_the_contract_rules(self):
        readme = load_text(README).lower()
        missing = [phrase for phrase in README_CONTRACT_PHRASES
                   if phrase not in readme]
        self.assertEqual(missing, [])

    def test_skill_section_present(self):
        skill = load_skill_surface()
        self.assertIn("## Human Review companion workflow", skill)
        self.assertIn("## Controlled rewrite", skill)

    def test_readme_section_present(self):
        readme = load_text(README)
        self.assertIn("## Human Review companion workflow", readme)

    def test_human_review_is_optional(self):
        skill = load_skill_surface()
        readme = load_text(README)
        self.assertIn("optional", skill)
        self.assertIn("never require it", skill)
        self.assertIn("never required for normal Antislop use or validation",
                      readme)


class TestFeedbackCases(unittest.TestCase):
    """Each required feedback case is handled by the documented contract."""

    def _fixture(self, fid):
        for fixture in load_fixtures():
            if fixture["id"] == fid:
                return fixture
        self.fail("missing fixture %s" % fid)

    def test_markdown_exact_wording_edit(self):
        fixture = self._fixture("hr-markdown-exact-wording-edit")
        self.assertEqual(run_fixture(fixture), [])
        edit = fixture["batch"]["pages"][0]["edits"][0]
        self.assertEqual(edit["after"], fixture["expected_verbatim_after"])
        self.assertTrue(fixture["expected_source_path"].endswith(".md"))
        self.assertIn(fixture["expected_verbatim_after"],
                      fixture["expected_source_edit"])

    def test_formatting_edit_after_html(self):
        fixture = self._fixture("hr-formatting-edit-after-html")
        self.assertEqual(run_fixture(fixture), [])
        edit = fixture["batch"]["pages"][0]["edits"][0]
        self.assertEqual(edit["after"], edit["before"])
        self.assertNotEqual(edit["before_html"], edit["after_html"])
        translated = translate_formatting(edit["after_html"])
        self.assertIn("**deadline**", translated)
        self.assertIn("**deadline**", fixture["expected_source_edit"])

    def test_anchored_selection_comment(self):
        fixture = self._fixture("hr-anchored-selection-comment")
        self.assertEqual(run_fixture(fixture), [])
        comment = fixture["batch"]["pages"][0]["comments"][0]
        self.assertEqual(comment["kind"], "selection")
        self.assertIn(comment["quote"], fixture["source"])
        self.assertEqual(comment["quote"], comment["anchor"]["quote"])

    def test_multiple_pages_in_one_batch(self):
        fixture = self._fixture("hr-multiple-pages-batch")
        self.assertEqual(run_fixture(fixture), [])
        self.assertEqual(fixture["expected_pages"], 2)
        pages = fixture["batch"]["pages"]
        self.assertEqual(len(pages), 2)
        for page in pages:
            self.assertTrue(page["edits"])

    def test_localhost_url_edit_applied_to_source(self):
        fixture = self._fixture("hr-localhost-url-edit-to-source")
        self.assertEqual(run_fixture(fixture), [])
        page = fixture["batch"]["pages"][0]
        self.assertEqual(page["kind"], "url")
        self.assertTrue(page["url"].startswith("http://localhost"))
        self.assertNotEqual(fixture["expected_source_path"], page["url"])
        self.assertFalse(fixture["expected_source_path"].startswith("http"))

    def test_timeout_is_not_acceptance(self):
        fixture = self._fixture("hr-timeout-not-acceptance")
        self.assertEqual(run_fixture(fixture), [])
        self.assertEqual(fixture["batch"]["status"], "timeout")
        self.assertTrue(fixture["timeout"])
        self.assertFalse(fixture["acceptance"])
        self.assertFalse(fixture["expects_ack"])
        self.assertEqual(fixture["batch"].get("pages", []), [])

    def test_acknowledgement_after_all_edits(self):
        fixture = self._fixture("hr-ack-after-all-edits")
        self.assertEqual(run_fixture(fixture), [])
        self.assertTrue(fixture["expects_ack"])

    def test_post_review_audit_required(self):
        fixture = self._fixture("hr-post-review-audit")
        self.assertEqual(run_fixture(fixture), [])
        self.assertTrue(fixture["requires_post_audit"])


class TestPackageBoundary(unittest.TestCase):
    """Human Review stays optional, out of the registry, and skills-only."""

    def test_human_review_is_not_a_writing_rule(self):
        with open(REGISTRY, encoding="utf-8") as f:
            registry = json.load(f)
        for rule in registry.get("rules", []):
            self.assertNotIn("human-review", rule["id"])
            self.assertNotIn("human review", rule.get("text", "").lower())

    def test_no_human_review_skill_is_vendored(self):
        self.assertFalse(os.path.exists(os.path.join(SKILLS_DIR,
                                                     "human-review")))

    def test_fixture_corpus_is_a_json_eval(self):
        self.assertTrue(os.path.exists(FIXTURES))
        with open(FIXTURES, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["skill_name"], "antislop-human-review")

    def test_no_node_or_browser_dependency(self):
        with open(FIXTURES, encoding="utf-8") as f:
            text = f.read()
        for banned in ("package.json", "node_modules", "npm install",
                       "npx -y human-review"):
            self.assertNotIn(banned, text)


class TestProductionCorpus(unittest.TestCase):
    """The production Human Review corpus passes end to end."""

    def test_corpus_passes(self):
        report = run_corpus(load_fixtures())
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["gate_pass"])

    def test_fixtures_cover_the_required_scenarios(self):
        ids = {fixture["id"] for fixture in load_fixtures()}
        self.assertEqual(ids & REQUIRED_SCENARIOS, REQUIRED_SCENARIOS)

    def test_corpus_has_eight_scenarios(self):
        self.assertEqual(len(load_fixtures()), 8)

    def test_every_edit_scenario_requires_post_audit(self):
        for fixture in load_fixtures():
            if not fixture["timeout"]:
                self.assertTrue(fixture["requires_post_audit"],
                                fixture["id"])

    def test_no_feedback_batch_is_automatic_acceptance(self):
        for fixture in load_fixtures():
            self.assertFalse(fixture["acceptance"], fixture["id"])


if __name__ == "__main__":
    unittest.main()