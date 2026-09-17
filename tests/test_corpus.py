#!/usr/bin/env python3
"""Run register-labelled false-positive controls through the public scorer."""

import json
import os
import unittest

from registry import load_registry
from score import score_text


ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestCorpusControls(unittest.TestCase):
    def test_manifest_cases_match_declared_findings(self):
        registry = load_registry(os.path.join(ROOT, "rules.json"))
        with open(os.path.join(ROOT, "corpus", "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)

        registers = {case["register"] for case in manifest["cases"]}
        self.assertGreaterEqual(len(registers), 3)
        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                result = score_text(case["text"], registry, context=case["register"])
                found = {finding["rule_id"] for finding in result["findings"]}
                self.assertTrue(set(case.get("expected_present", [])) <= found)
                self.assertFalse(set(case.get("expected_absent", [])) & found)


if __name__ == "__main__":
    unittest.main()
