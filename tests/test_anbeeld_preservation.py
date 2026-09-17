#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import edit
import registry


FIXTURE_PATH = ROOT / "skills" / "antislop" / "evals" / "anbeeld-preservation-fixtures.json"


class AnbeeldPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = registry.load_registry(str(ROOT / "rules.json"))
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cls.fixtures = json.load(handle)["evals"]
        cls.by_id = {fixture["id"]: fixture for fixture in cls.fixtures}

    def test_registry_contract_is_ordered_and_provenanced(self):
        contract = self.registry["edit_contract"]
        self.assertEqual(
            [item["rank"] for item in contract["precedence"]],
            [1, 2, 3, 4, 5, 6],
        )
        self.assertEqual(contract["preservation"]["failure_class"], "correctness")
        self.assertEqual(contract["source"]["commit"], "e59d477")
        self.assertEqual(contract["source"]["version"], "1.4.2")
        self.assertEqual(contract["source"]["license"], "MIT")

    def test_fixture_pairs_match_edit_contract(self):
        report = edit.run_edit_corpus(
            self.fixtures,
            self.registry,
            str(ROOT / "rules.json"),
        )
        self.assertTrue(report["gate_pass"], report)

    def test_each_protected_mutation_is_rejected(self):
        base = self.by_id["anbeeld-preserve-copyedit"]
        mutations = (
            ("number", "3.0.0", "3.2.0"),
            ("date", "2026-09-14", "2026-10-14"),
            ("path", "/srv/app/config.yaml", "/srv/app/other.yaml"),
            ("code", "prod", "staging"),
            ("quote", "Vendor text", "Changed vendor text"),
            ("url", "https://example.com/release", "https://example.com/changed"),
            ("required term", "leverage", "use"),
        )
        for label, old, new in mutations:
            with self.subTest(label=label):
                candidate = base["candidate"].replace(old, new, 1)
                result = edit.check_operation(
                    base["source"],
                    candidate,
                    "revise",
                    required_terms=tuple(base["required_terms"]),
                    registry_path=str(ROOT / "rules.json"),
                )
                self.assertEqual(result["decision"], "reject", result)
                self.assertEqual(
                    result["preservation_contract"]["failure_class"],
                    "correctness",
                )

    def test_output_integrity_mutation_is_rejected(self):
        base = self.by_id["anbeeld-preserve-copyedit"]
        result = edit.check_operation(
            base["source"],
            base["candidate"] + " <|user|>",
            "revise",
            required_terms=tuple(base["required_terms"]),
            registry_path=str(ROOT / "rules.json"),
        )
        self.assertEqual(result["decision"], "reject", result)
        self.assertIn("leaked_prompt_token", result["integrity"]["failures"])

    def test_authorized_change_is_recorded(self):
        fixture = self.by_id["anbeeld-authorized-number-change"]
        result = edit.run_edit_fixture(
            fixture,
            self.registry,
            str(ROOT / "rules.json"),
        )
        self.assertEqual(result["decision"], "accept", result)
        self.assertEqual(result["authorized_changes"], [{"category": "number"}])
        self.assertEqual(result["preservation_contract"]["failure_class"], "correctness")

    def test_audit_does_not_rewrite(self):
        fixture = self.by_id["anbeeld-audit-empty"]
        result = edit.run_edit_fixture(
            fixture,
            self.registry,
            str(ROOT / "rules.json"),
        )
        self.assertEqual(result["decision"], "accept", result)
        self.assertEqual(fixture["source"], fixture["candidate"])


if __name__ == "__main__":
    unittest.main()
