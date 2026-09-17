#!/usr/bin/env python3
"""Validate the generate-slop skill's packaging and taxonomy boundary."""

import os
import re
import unittest

import validate


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "generate-slop", "SKILL.md")
REFERENCE = os.path.join(
    ROOT, "skills", "antislop", "references", "pattern-reference.md"
)
KIRO_SKILL = os.path.join(ROOT, ".kiro", "skills", "generate-slop", "SKILL.md")


class TestGenerateSlopSkill(unittest.TestCase):
    def setUp(self):
        with open(SKILL, encoding="utf-8") as handle:
            self.text = handle.read()
        with open(REFERENCE, encoding="utf-8") as handle:
            self.reference = handle.read()

    def test_skill_file_passes_shared_validation(self):
        self.assertEqual(validate.validate_skill_file(SKILL), [])

    def test_skill_is_explicit_and_synthetic(self):
        frontmatter = validate.parse_frontmatter(self.text)
        self.assertEqual(frontmatter["name"], "generate-slop")
        self.assertEqual(frontmatter["description"], "Generate controlled synthetic slop for demos and evaluation fixtures.")
        self.assertEqual(frontmatter["disable-model-invocation"], "true")
        normalized = re.sub(r"\s+", " ", self.text.lower())
        for phrase in (
            "fictional evaluation material",
            "do not activate for ordinary writing",
            "does not prove anything about authorship",
        ):
            self.assertIn(phrase, normalized)

    def test_kiro_workspace_exposes_the_canonical_skill(self):
        with open(KIRO_SKILL, encoding="utf-8") as handle:
            kiro_text = handle.read()
        frontmatter = validate.parse_frontmatter(kiro_text)
        self.assertEqual(frontmatter["name"], "generate-slop")
        self.assertEqual(frontmatter["disable-model-invocation"], "true")
        self.assertIn("../../../skills/generate-slop/SKILL.md", kiro_text)
        self.assertNotIn("single discoverable skill", self.text.lower())

    def test_supported_filters_exist_in_generated_reference(self):
        headings = {
            re.sub(r"\s+", " ", heading.lower()).strip()
            for heading in re.findall(r"^## (.+)$", self.reference, re.MULTILINE)
        }
        for heading in (
            "vocabulary — forbidden",
            "phrases — forbidden",
            "filler phrases — forbidden",
            "structural patterns — discouraged",
            "formatting",
            "chatbot artifacts — forbidden",
        ):
            self.assertIn(heading, headings)

    def test_density_contract_is_operational(self):
        normalized = re.sub(r"\s+", " ", self.text)
        for phrase in (
            "light`: 1-2 deliberate pattern instances per 200 words",
            "medium`: 3-5 deliberate pattern instances per 200 words",
            "high`: 6 or more deliberate pattern instances per 200 words",
            "everything` at `high`",
            "include at least one instance from each listed category",
            "do not force every rule",
        ):
            self.assertIn(phrase.replace("`", chr(96)), normalized)

    def test_skill_points_to_generated_taxonomy_without_copying_rule_table(self):
        self.assertIn("../antislop/references/pattern-reference.md", self.text)
        self.assertIn("rules.json", self.text)
        self.assertNotIn('"rule_id"', self.text)


if __name__ == "__main__":
    unittest.main()
