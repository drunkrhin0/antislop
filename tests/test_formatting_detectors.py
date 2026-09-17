#!/usr/bin/env python3
"""Tests for the formatting detectors wired up in issue #131.

Each of the previously-skipped fmt-* rules (emoji in prose, emoji bullet
markers, bolded-term inline headers, exclamation overuse, semicolon overuse,
-ly adverb compounds, and title-case headings) now names a registered
detector. These tests pin the trigger, clean, boundary, and technical
false-positive behavior at the executable seam: structural.run_detectors with
the shipped rule definitions.
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import structural  # noqa: E402

REGISTRY = os.path.join(ROOT, "rules.json")


def fmt_rule(rid):
    with open(REGISTRY, encoding="utf-8") as f:
        registry = json.load(f)
    for rule in registry["rules"]:
        if rule["id"] == rid:
            return rule
    raise KeyError(rid)


def detect(rid, text):
    rule = fmt_rule(rid)
    return structural.run_detectors(text, [rule], "general")["findings"]


class TestEmojis(unittest.TestCase):
    def test_trigger(self):
        findings = detect("fmt-emojis", "Great job 🎉 on the release!")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["signal"], "strict")

    def test_clean(self):
        self.assertEqual(detect("fmt-emojis", "Plain ASCII prose only."), [])

    def test_code_and_quote_protected(self):
        text = "Run `echo 🎉` and say \"ok 🎉\" then continue."
        findings = detect("fmt-emojis", text)
        self.assertEqual(findings, [])


class TestEmojiBullets(unittest.TestCase):
    def test_trigger(self):
        findings = detect("fmt-emoji-bullets", "- ✅ Finished\n- Second item")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["signal"], "strict")

    def test_clean_plain_bullets(self):
        self.assertEqual(
            detect("fmt-emoji-bullets", "- First item\n- Second item"), [])

    def test_fenced_example_is_protected(self):
        self.assertEqual(
            detect("fmt-emoji-bullets",
                   "Example:\n\n```markdown\n- ✅ Finished\n```"), [])


class TestInlineHeader(unittest.TestCase):
    def test_trigger(self):
        findings = detect("fmt-inline-header", "**Speed:** it improved a lot.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["signal"], "strict")

    def test_bold_without_colon_is_clean(self):
        self.assertEqual(
            detect("fmt-inline-header", "This is **important** to note."), [])


class TestExclamation(unittest.TestCase):
    def test_trigger(self):
        findings = detect("fmt-exclamation", "Wow! Amazing!")
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["signal"], "advisory")

    def test_clean(self):
        self.assertEqual(detect("fmt-exclamation", "No exclamation here."), [])

    def test_quoted_exclamation_protected(self):
        self.assertEqual(detect("fmt-exclamation", "He said \"Stop!\""), [])

    def test_curly_quoted_exclamation_protected(self):
        self.assertEqual(
            detect("fmt-exclamation", "He wrote “Wow!” in the sample."), [])


class TestSemicolon(unittest.TestCase):
    def test_trigger(self):
        findings = detect("fmt-semicolon", "One; two; three.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["signal"], "advisory")
        self.assertEqual(findings[0]["sample"]["count"], 2)

    def test_single_semicolon_clean(self):
        self.assertEqual(detect("fmt-semicolon", "One; two."), [])

    def test_code_semicolons_protected(self):
        self.assertEqual(
            detect("fmt-semicolon", "Run `a; b; c; d;` and stop."), [])


class TestLyHyphen(unittest.TestCase):
    def test_trigger(self):
        findings = detect("fmt-compound-hyphen",
                          "A highly-qualified engineer arrived.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["signal"], "advisory")
        self.assertEqual(findings[0]["sample"]["compound"], "highly-qualified")

    def test_conventional_hyphen_clean(self):
        self.assertEqual(
            detect("fmt-compound-hyphen", "A state-of-the-art pipeline."), [])


class TestTitleCase(unittest.TestCase):
    def test_trigger(self):
        findings = detect("fmt-title-case", "# How To Write Good Prose")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["signal"], "strict")

    def test_short_and_stopword_title_case_triggers(self):
        for heading in (
                "# Release Process Guide",
                "# The Rise of Open Source Software"):
            with self.subTest(heading=heading):
                self.assertEqual(len(detect("fmt-title-case", heading)), 1)

    def test_sentence_case_clean(self):
        self.assertEqual(detect("fmt-title-case", "# How to write good prose"),
                         [])

    def test_proper_noun_heading_clean(self):
        self.assertEqual(
            detect("fmt-title-case", "# Using OpenAI in Antislop"), [])

    def test_fenced_heading_example_is_protected(self):
        self.assertEqual(
            detect("fmt-title-case",
                   "Example:\n\n```markdown\n# How To Write Good Prose\n```"),
            [])

    def test_tilde_fenced_heading_example_is_protected(self):
        self.assertEqual(
            detect("fmt-title-case",
                   "Example:\n\n~~~markdown\n# How To Write Good Prose\n~~~"),
            [])

    def test_sentence_case_technical_headings_are_clean(self):
        for heading in (
                "# Deploying Kubernetes safely",
                "# Understanding OAuth tokens",
                "# Integrating Kubernetes API safely",
                "# HTTP Status Codes",
                "# OAuth Token Endpoint",
                "# RFC Field Definitions",
                "# Configuring Amazon Web Services safely",
                "# Managing Transport Layer Security settings",
                "# Using Visual Studio Code extensions"):
            with self.subTest(heading=heading):
                self.assertEqual(detect("fmt-title-case", heading), [])

    def test_three_word_technical_names_are_clean(self):
        for heading in (
                "# Amazon Web Services",
                "# Visual Studio Code",
                "# Transport Layer Security"):
            with self.subTest(heading=heading):
                self.assertEqual(detect("fmt-title-case", heading), [])

    def test_title_case_with_technical_tokens_still_triggers(self):
        for heading in (
                "# Better OAuth Token Handling",
                "# Building REST APIs Safely"):
            with self.subTest(heading=heading):
                self.assertEqual(len(detect("fmt-title-case", heading)), 1)

    def test_paragraph_is_not_a_heading(self):
        self.assertEqual(detect("fmt-title-case", "How To Write Good Prose"),
                         [])


class TestSkippedCount(unittest.TestCase):
    def test_fmt_rules_no_longer_skipped(self):
        with open(REGISTRY, encoding="utf-8") as f:
            registry = json.load(f)
        for rid in ("fmt-title-case", "fmt-inline-header",
                    "fmt-compound-hyphen", "fmt-emojis", "fmt-exclamation",
                    "fmt-semicolon", "fmt-emoji-bullets"):
            rule = fmt_rule(rid)
            self.assertIn(rule["detector"], structural.DETECTORS, rid)


if __name__ == "__main__":
    unittest.main()
