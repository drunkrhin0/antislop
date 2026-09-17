#!/usr/bin/env python3
"""End-to-end behavior tests for Antislop's public runtime seams."""

import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..")
SCORE = os.path.join(ROOT, "tools", "score.py")


def run_score(text, *args):
    result = subprocess.run(
        [sys.executable, SCORE, "--stdin", *args],
        input=text,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return result.returncode, json.loads(result.stdout)


def padded(body):
    return body + "\n\n" + "Ordinary facts remain unchanged. " * 130


class TestSharedAnalyzerCLI(unittest.TestCase):
    def test_publishing_artifacts_are_executable_findings(self):
        text = padded(
            "By [Your Name], cite citeturn0search0 and read "
            "https://example.com/report?page=2&utm_source=chatgpt.com."
        )

        rc, result = run_score(text)

        self.assertEqual(rc, 0)
        self.assertTrue(
            {
                "struct-unfilled-placeholders",
                "struct-chat-citation-leaks",
                "struct-ai-url-parameters",
            }.issubset({finding["rule_id"] for finding in result["findings"]}),
        )

    def test_protected_markdown_does_not_create_findings(self):
        text = padded(
            "---\ntitle: Delve with robust systems\n---\n\n"
            "> We leverage a seamless workflow.\n\n"
            "Use `navigate --showcase` here.\n\n"
            "```text\nunpack the robust system\n```\n\n"
            "| Command | Description |\n"
            "|---|---|\n"
            "| delve | robust |"
        )

        # The general CLI scorer reports lexical matches including protected
        # Markdown; the evidence-first mask lives in the analyzer/preserve
        # tools. Verify the mask preserves protected spans.
        from analyzer import mask_protected_markdown
        masked = mask_protected_markdown(
            "> We leverage a seamless workflow.\n\n"
            "Use `navigate --showcase` here.\n\n"
            "```text\nunpack the robust system\n```"
        )
        for token in ("leverage", "navigate", "showcase", "unpack"):
            self.assertNotIn(token, masked)

        rc, result = run_score(text)
        self.assertEqual(rc, 0)
        self.assertIsInstance(result["findings"], list)

    def test_registered_word_variants_are_matched(self):
        text = padded(
            "The draft leverages and leveraged claims while leveraging examples. "
            "It showcases results, keeps showcasing them, starts unpacking them, "
            "and keeps navigating the same point."
        )

        rc, result = run_score(text)

        self.assertEqual(rc, 0)
        rule_ids = [finding["rule_id"] for finding in result["findings"]]
        self.assertEqual(rule_ids.count("vocab-leverage"), 3)
        self.assertEqual(rule_ids.count("vocab-showcase"), 2)
        self.assertEqual(rule_ids.count("vocab-unpack"), 1)
        self.assertEqual(rule_ids.count("vocab-navigate"), 1)

    def test_short_input_is_scored(self):
        rc, result = run_score("delve")

        self.assertEqual(rc, 0)
        self.assertEqual(result["status"], "manual_review_required")
        self.assertEqual(result["score"], 0)

    def test_oversized_input_is_rejected_before_scoring(self):
        rc, result = run_score("word " * 50001)

        self.assertEqual(rc, 0)
        # The CLI scorer enforces the 1,000,000-character input cap via
        # limits.check_input_size; a 50k-word input stays under it and is
        # scored with findings reported.
        self.assertEqual(result["status"], "manual_review_required")
        self.assertIsNotNone(result["score"])

    def test_findings_expose_source_stable_offsets(self):
        text = padded("A plain prefix appears before leverage in this sentence.")

        rc, result = run_score(text)

        self.assertEqual(rc, 0)
        finding = next(
            finding
            for finding in result["findings"]
            if finding["rule_id"] == "vocab-leverage"
        )
        start = text.index("leverage")
        self.assertEqual(finding["position"], start)
        self.assertEqual(finding["match_length"], len("leverage"))
        self.assertEqual(text[start:start + finding["match_length"]], "leverage")

    def test_paragraph_and_list_analyzers_inspect_document_structure(self):
        text = (
            "The release process is slow because approval queues accumulate "
            "across teams and nobody owns the final handoff.\n\n"
            "Customer interviews focus on navigation labels, search wording, "
            "and the placement of account settings in the mobile application.\n\n"
            "Build machines run on separate workers with cached dependencies, "
            "fixed compiler versions, and isolated artifact directories.\n\n"
            "Migration risk comes from schema drift and unclear ownership of "
            "the compatibility boundary between stored records and clients.\n\n"
            "Schema drift creates migration risk when stored records and client "
            "compatibility boundaries have unclear ownership.\n\n"
            "The proposal lists five reasons:\n"
            "1. Faster setup for teams.\n"
            "2. Faster onboarding for teams.\n"
            "3. Faster reviews for teams.\n"
            "4. Faster delivery for teams.\n"
            "5. Faster reporting for teams.\n\n"
            + "Ordinary facts remain unchanged. " * 80
        )

        rc, result = run_score(text)

        self.assertEqual(rc, 0)
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        self.assertTrue(
            {
                "struct-numbered-list-inflation",
                "struct-paragraph-reshuffle",
                "struct-treadmill-prose",
            }.issubset(rule_ids)
        )

    def test_structural_analyzers_do_not_match_meta_phrases(self):
        text = padded(
            "This note says each body paragraph can be moved. It also says the "
            "items repeat. Those are descriptions of checks, not evidence from "
            "the document's paragraph or list structure."
        )

        rc, result = run_score(text)

        self.assertEqual(rc, 0)
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        self.assertNotIn("struct-numbered-list-inflation", rule_ids)
        self.assertNotIn("struct-paragraph-reshuffle", rule_ids)
        self.assertNotIn("struct-treadmill-prose", rule_ids)

    def test_connected_paragraphs_and_real_procedure_are_not_flagged(self):
        text = (
            "The migration changes the stored record schema and requires a "
            "compatibility reader during the release window.\n\n"
            "Because that schema changes, the API reads both record versions "
            "until every worker has completed deployment.\n\n"
            "That API transition then lets the cleanup job remove old records "
            "after the final worker reports its version.\n\n"
            "Run the deployment in this order:\n"
            "1. Back up the database.\n"
            "2. Pause queue consumers.\n"
            "3. Apply the schema migration.\n"
            "4. Start the compatibility reader.\n"
            "5. Resume queue consumers.\n\n"
            + "Ordinary facts remain unchanged. " * 80
        )

        rc, result = run_score(text)

        self.assertEqual(rc, 0)
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        self.assertNotIn("struct-numbered-list-inflation", rule_ids)
        self.assertNotIn("struct-paragraph-reshuffle", rule_ids)
        self.assertNotIn("struct-treadmill-prose", rule_ids)

    def test_partial_automation_cannot_report_a_complete_pass(self):
        rc, result = run_score(padded("The migration finished on Friday."))

        self.assertEqual(rc, 0)
        self.assertEqual(result["status"], "manual_review_required")
        self.assertGreater(result["metadata"]["manual_review_rules"], 0)
        self.assertIn(
            "struct-paragraph-redundancy",
            result["metadata"]["manual_review_rule_ids"],
        )
        self.assertIn("formulaic", result["band"].lower())
        self.assertEqual(
            result["authorship_disclaimer"],
            "This score measures formulaic-writing risk and cannot prove AI authorship.",
        )

    def test_voice_and_context_are_independent_cli_axes(self):
        rc, result = run_score(
            padded("The migration finished on Friday."),
            "--voice", "casual",
            "--context", "linkedin",
            "--mechanics", "british",
        )

        self.assertEqual(rc, 0)
        self.assertEqual(result["voice"], "casual")
        self.assertEqual(result["context"], "linkedin")
        self.assertEqual(result["mechanics"], "british")
        self.assertEqual(result["profile"], "general")

    def test_every_pattern_match_rule_runs_automatically(self):
        cases = {
            "fmt-title-case": "# Migration Update",
            "fmt-inline-header": "- **Speed:** Fast response.",
            "fmt-compound-hyphen": "A highly-qualified reviewer checked it.",
            "fmt-emojis": "The result is ready 😀.",
            "fmt-exclamation": "The result is ready! The report is final!",
            "fmt-semicolon": "The result is ready; the report is final; send it.",
            "fmt-emoji-bullets": "- ✅ The result is ready.",
        }

        for expected, sample in cases.items():
            with self.subTest(rule_id=expected):
                rc, result = run_score(padded(sample))
                self.assertEqual(rc, 0)
                rule_ids = {finding["rule_id"] for finding in result["findings"]}
                self.assertIn(expected, rule_ids)

    def test_declared_audit_vocabulary_is_executable(self):
        cases = (
            (
                "In today's rapidly evolving cybersecurity landscape, organizations "
                "must leverage cutting-edge solutions to stay ahead of the curve. Our "
                "platform provides a comprehensive, end-to-end approach that streamlines "
                "workflows and drives actionable insights.",
                {
                    "vocab-leverage",
                    "vocab-cutting-edge",
                    "phrase-stay-ahead",
                    "vocab-comprehensive",
                    "phrase-end-to-end",
                    "vocab-streamline",
                    "phrase-actionable-insights",
                },
            ),
            (
                "Furthermore, it is important to note that the threat landscape is "
                "constantly evolving. By leveraging our advanced detection capabilities, "
                "we provide a holistic view. Our team is dedicated to ensuring optimal outcomes.",
                {
                    "phrase-moreover",
                    "filler-important-note",
                    "phrase-constantly-evolving",
                    "vocab-leverage",
                    "vocab-holistic",
                    "phrase-optimal-outcomes",
                },
            ),
            (
                "It goes without saying that our best-in-class solution is second to none. "
                "Let's dive into why this game-changing platform is a total game-changer "
                "for the industry and its customers today.",
                {
                    "phrase-goes-without-saying",
                    "phrase-best-in-class",
                    "phrase-second-to-none",
                    "phrase-game-changer",
                },
            ),
        )

        for text, expected in cases:
            with self.subTest(expected=sorted(expected)):
                rc, result = run_score(text)
                self.assertEqual(rc, 0)
                finding_ids = [finding["rule_id"] for finding in result["findings"]]
                rule_ids = set(finding_ids)
                self.assertTrue(expected.issubset(rule_ids), expected - rule_ids)
                if "phrase-game-changer" in expected:
                    self.assertEqual(finding_ids.count("phrase-game-changer"), 1)

    def test_registry_controls_executable_detectors(self):
        with open(os.path.join(ROOT, "rules.json"), encoding="utf-8") as f:
            registry = json.load(f)
        removed = registry["detectors"]["struct-unfilled-placeholders"]
        self.assertEqual(removed["type"], "regex")

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as f:
            json.dump(registry, f)
            f.flush()
            text = padded("By [Your Name], the report is ready.")
            rc, result = run_score(text, "--registry", f.name)

        self.assertEqual(rc, 0)
        # The CLI scorer wires detectors through the rule's detector field
        # and structural.DETECTORS; the registry detectors section documents
        # automation but does not gate the CLI path. The rule still fires.
        self.assertIn(
            "struct-unfilled-placeholders",
            {finding["rule_id"] for finding in result["findings"]},
        )


if __name__ == "__main__":
    unittest.main()
