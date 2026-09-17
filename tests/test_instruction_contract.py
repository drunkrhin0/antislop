#!/usr/bin/env python3
"""Regression tests for Antislop's activation and author-gap contracts."""

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INSTRUCTION_SURFACES = (
    "skills/antislop/SKILL.md",
    ".opencode/agents/antislop.md",
    "powers/antislop/POWER.md",
)

ACTIVATION_SURFACES = INSTRUCTION_SURFACES


def read_surface(path):
    paths = [path]
    if path == "skills/antislop/SKILL.md":
        paths.extend((
            "skills/antislop/references/style-mode.md",
            "skills/antislop/references/shared-contract.md",
            "skills/antislop/references/preservation-contract.md",
            "skills/antislop/references/audit-mode.md",
        ))
    return chr(10).join(
        open(os.path.join(ROOT, item), encoding="utf-8").read()
        for item in paths
    ).lower()


def read_direct_surface(path):
    return open(os.path.join(ROOT, path), encoding="utf-8").read().lower()


class TestAuthorGapContract(unittest.TestCase):
    """Finished output never turns missing author facts into model content."""

    def test_surfaces_block_placeholders_and_markers_in_finished_deliverables(self):
        required_phrases = (
            "finished deliverable",
            "model-added generic placeholders",
            "[tk]",
            "ask one concise question before drafting",
            "omit an optional unknown field if that stays truthful",
            "markers are allowed only when the user explicitly requests a template, scaffold, or marked-up draft",
        )
        for path in INSTRUCTION_SURFACES:
            with self.subTest(path=path):
                text = read_surface(path)
                for phrase in required_phrases:
                    self.assertIn(phrase, text)

    def test_review_instructions_do_not_reauthorize_markers(self):
        for path in INSTRUCTION_SURFACES:
            with self.subTest(path=path):
                text = read_surface(path)
                self.assertNotIn("ask exactly for that, or mark it", text)
                self.assertNotIn("targeted question or [tk: ...] marker", text)

    def test_audit_summary_uses_grammatical_author_gap_sentences(self):
        review_surfaces = (
            ".opencode/agents/antislop.md",
        )
        for path in review_surfaces:
            with self.subTest(path=path):
                text = read_surface(path)
                self.assertIn(
                    "is an ask-author finding. ask one concise question before drafting and wait",
                    text,
                )
                self.assertNotIn(
                    "is an ask-author finding with one concise question before drafting and wait",
                    text,
                )


class TestActivationContract(unittest.TestCase):
    """Ordinary explanations do not activate the prose-writing guidance."""

    def test_activation_requires_explicit_prose_artifact_intent(self):
        required_phrases = (
            "explicit prose-artifact intent",
            "writing, rewriting, editing, polishing, reviewing, or auditing an artifact",
            "ordinary factual or technical explanations",
            "explain how cve scoring works",
            "once such a task is active, style guidance remains ambient",
        )
        for path in ACTIVATION_SURFACES:
            with self.subTest(path=path):
                text = read_direct_surface(path)
                for phrase in required_phrases:
                    self.assertIn(phrase, text)

    def test_runtime_references_do_not_repeat_activation_or_credits(self):
        style = read_direct_surface("skills/antislop/references/style-mode.md")
        audit = read_direct_surface("skills/antislop/references/audit-mode.md")
        self.assertNotIn("## when to use", style)
        self.assertNotIn("**sources:**", style)
        self.assertNotIn("](references/", style)
        self.assertNotIn("](references/", audit)

    def test_runtime_reference_links_resolve(self):
        reference_dir = os.path.join(ROOT, "skills", "antislop", "references")
        for filename in os.listdir(reference_dir):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(reference_dir, filename)
            text = open(path, encoding="utf-8").read()
            for target in re.findall(r"\]\(([^):]+\.md)\)", text):
                with self.subTest(source=filename, target=target):
                    self.assertTrue(
                        os.path.isfile(os.path.normpath(os.path.join(reference_dir, target))),
                        "%s points to missing %s" % (filename, target),
                    )


class TestRebasedAcceptanceContracts(unittest.TestCase):
    def test_missing_logistical_detail_does_not_block_a_requested_draft(self):
        required_phrases = (
            "draft immediately",
            "clear bracketed placeholder",
            "do not stop to ask for a missing logistical detail",
        )
        for path in INSTRUCTION_SURFACES:
            with self.subTest(path=path):
                text = read_surface(path)
                for phrase in required_phrases:
                    self.assertIn(phrase, text)

    def test_does_this_pass_with_technical_text_is_audit_intent(self):
        audit_surfaces = (
            "skills/antislop/SKILL.md",
            ".opencode/agents/antislop.md",
            "powers/antislop/steering/audit-mode.md",
        )
        required = (
            'when a request starts with "does this pass?" and includes text',
            "even when the text is technical, operational, or security-related",
        )
        for path in audit_surfaces:
            with self.subTest(path=path):
                text = read_surface(path)
                for phrase in required:
                    self.assertIn(phrase, text)

    def test_audit_flags_first_transition_opener_occurrence(self):
        audit_surfaces = (
            "skills/antislop/SKILL.md",
            ".opencode/agents/antislop.md",
            "powers/antislop/steering/audit-mode.md",
        )
        required = (
            'flag every occurrence of "moreover", "furthermore", and "additionally"',
            "including the first occurrence in a short sample",
        )
        for path in audit_surfaces:
            with self.subTest(path=path):
                text = read_surface(path)
                for phrase in required:
                    self.assertIn(phrase, text)

if __name__ == "__main__":
    unittest.main()
