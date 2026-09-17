#!/usr/bin/env python3
"""Focused tests for the issue #131 local structural detector slice."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import structural  # noqa: E402
from registry import load_registry  # noqa: E402


class TestLocalStructuralDetectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry(os.path.join(ROOT, "rules.json"))

    def rule(self, rule_id):
        return next(rule for rule in self.registry["rules"]
                    if rule["id"] == rule_id)

    def findings(self, rule_id, text):
        return structural.detect_rule(text, self.rule(rule_id))["findings"]

    def test_overlong_sentence_is_advisory(self):
        text = ("A parser reads input, validates the schema, checks the profile, "
                "records evidence, compares the result, and returns the result.")
        findings = self.findings("struct-overlong-sentence", text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["signal"], "advisory")
        self.assertEqual(findings[0]["evidence"], "span")

    def test_overlong_sentence_leaves_short_text_clean(self):
        self.assertFalse(self.findings(
            "struct-overlong-sentence", "The parser reads the input, then returns it."
        ))

    def test_line_break_detector_masks_code_and_hard_breaks(self):
        text = "```python\nvalue = one, two, three, four, five\n```\n\nA deliberate  \nbreak."
        self.assertFalse(self.findings("struct-artificial-line-breaks", text))
        text = "This sentence wraps in the middle\nof a paragraph."
        self.assertEqual(len(self.findings("struct-artificial-line-breaks", text)), 1)

    def test_generic_link_text_only_reports_visible_label(self):
        findings = self.findings(
            "struct-link-text", "Read [learn more](https://example.com/guide)."
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["sample"]["label"], "learn more")
        self.assertFalse(self.findings(
            "struct-link-text", "Read [deployment guide](https://example.com/guide)."
        ))

    def test_colon_reveal_keeps_labels_and_code_clean(self):
        findings = self.findings("struct-colon-reveal", "The best part: it learns.")
        self.assertEqual(len(findings), 1)
        self.assertFalse(self.findings("struct-colon-reveal", "Note: use the API."))
        self.assertFalse(self.findings("struct-colon-reveal", "The report covers the 2026 threat landscape [source: internal Q1 report]."))
        self.assertFalse(self.findings("struct-colon-reveal", "The lesson: move the lease check before dispatch."))
        self.assertFalse(self.findings("struct-colon-reveal", "This change is crucial: it cut deploy time from 40 minutes to 4."))
        self.assertFalse(self.findings(
            "struct-colon-reveal", "`The best part: it learns.`"
        ))


if __name__ == "__main__":
    unittest.main()
