#!/usr/bin/env python3
"""Regression tests for the final Daybreak review findings."""

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import score  # noqa: E402


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


class TestAgentScoreContract(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "rules.json"), encoding="utf-8") as handle:
            self.registry = json.load(handle)

    def test_agent_surfaces_document_the_executable_formula(self):
        for path in (
                "skills/antislop/references/audit-mode.md",
                ".opencode/agents/antislop.md"):
            with self.subTest(path=path):
                text = read(path)
                self.assertIn("500-word reference length", text)
                self.assertIn("second instance carries 50%", text.lower())
                self.assertIn("Advisory and human-review findings carry zero points", text)

    def test_score_bands_never_imply_authorship(self):
        for band in self.registry["score_bands"].values():
            label = band["label"].lower()
            self.assertNotIn("person", label)
            self.assertIsNone(re.search(r"\bai\b", label))

    def test_p3_patterns_and_score_match_acceptance_case(self):
        text = ("Furthermore, it is important to note that the threat "
                "landscape is constantly evolving.")
        report = score.score_text(text, self.registry)
        ids = {finding["rule_id"] for finding in report["findings"]}
        self.assertIn("phrase-moreover", ids)
        self.assertIn("filler-important-note", ids)
        self.assertIn("phrase-ever-evolving", ids)
        self.assertLess(report["score"], 40)

    def test_p5_bans_agile_and_its_nominalized_synonym(self):
        rule = next(rule for rule in self.registry["rules"]
                    if rule["id"] == "phrase-agile-adaptation")
        self.assertIn("agile", rule["text"].lower())
        self.assertIn("agility", rule["text"].lower())
        self.assertEqual(rule["semantic_type"], "discouraged")
        self.assertEqual(rule["review_mode"], "human")

    def test_p5_does_not_match_agile_inside_fragile(self):
        findings = score.detect_findings(
            "The protocol is fragile.", self.registry["rules"], "general")[0]
        self.assertNotIn("phrase-agile-adaptation",
                         {finding["rule_id"] for finding in findings})

    def test_n4_requires_full_audit_when_source_text_is_available(self):
        text = read("skills/antislop/references/audit-mode.md")
        self.assertIn("Do not return the authorship disclaimer by itself", text)
        self.assertIn("full score, violations table, and disclaimer", text)


class TestReviewDocumentation(unittest.TestCase):
    def test_acceptance_record_distinguishes_repo_fixes_from_live_rerun(self):
        text = read("docs/acceptance-record.md")
        self.assertIn("**Repository regressions:** passed", text)
        self.assertIn("**Codex Desktop plugin-only acceptance:** failed (6/9)", text)
        self.assertIn(
            "6926b3e78d7688d0361bfb19d1a4e3bc1c7a4ccb", text)
        self.assertIn("3.0.0", text)

    def test_submission_pack_separates_introduction_from_current_version(self):
        text = read("docs/submission-pack.md")
        self.assertIn("Introduced in `7ae4abd`", text)
        self.assertIn("current stack version is 3.0.0", text)

    def test_current_plugin_docs_use_the_consolidated_skill_boundary(self):
        submission = read("docs/submission-pack.md")
        e2e = read("docs/claude-code-e2e.md")
        self.assertIn("`antislop` routes writing and audit work", submission)
        self.assertIn("`skills/generate-slop/SKILL.md`", submission)
        self.assertIn("exactly `antislop` and `generate-slop`", submission)
        self.assertIn("antislop:antislop", e2e)
        self.assertIn("antislop:generate-slop", e2e)
        self.assertNotIn("antislop-audit", submission)
        self.assertNotIn("antislop-audit", e2e)

    def test_forgejo_docs_describe_the_current_release_gate(self):
        text = read("AGENTS.md")
        self.assertNotIn("auto-tag workflow never fires", text)
        self.assertNotIn("create-release.yml", text)
        self.assertIn("Verify release candidate", text)

    def test_source_credits_cover_issue_driven_references_and_recent_research(self):
        readme = read("README.md")
        agents = read("AGENTS.md")
        ledger = read("docs/sources/credits.md")
        self.assertIn("docs/sources/credits.md", readme)
        self.assertNotIn("[SpeechMap Lexical Fingerprints]", readme)
        self.assertNotIn("[Pydantic: Linguistic drift at the frontier]", readme)
        self.assertIn("docs/sources/credits.md", agents)
        for issue in ("#65", "#66", "#88", "#89", "#90", "#91", "#92",
                      "#93", "#94",
                      "#95", "#96", "#97", "#98", "#99", "#100", "#101",
                      "#102", "#103", "#137", "#140", "#144", "#167",
                      "#168"):
            with self.subTest(issue=issue):
                self.assertIn(issue, ledger)


if __name__ == "__main__":
    unittest.main()
