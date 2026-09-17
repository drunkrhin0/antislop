#!/usr/bin/env python3
"""Tests for the Say-It-Human evidence and locale routing runner (issue #97).

Covers the acceptance criteria:
  - every fact-dependent repair can retain or expose its evidence class
  - required unknown evidence stops rewriting and requests a source
  - protected technical spans survive byte for byte
  - zh-CN rules activate only when selected or reliably routed
  - Chinese punctuation fixtures include full-width, half-width, code,
    URLs, and mixed-script cases
  - release-note output uses only supplied change evidence
  - large deletions require explicit edit authority and a visible diff
  - a supplied informal voice trait stays unchanged without adding slang
  - one claim in each evidence class

Run: python3 -m unittest tests/test_say_human.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import say_human  # noqa: E402

FIXTURES = os.path.join(ROOT, "skills", "antislop", "evals",
                        "say-human-fixtures.json")
REGISTRY = os.path.join(ROOT, "rules.json")
SAY_HUMAN = os.path.join(ROOT, "say_human.py")
VALIDATE = os.path.join(ROOT, "validate.py")

EVIDENCE_CLASSES = ("source", "logic", "experience", "inference", "unknown")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def load_fixtures():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)["evals"]


def run_validator(*args):
    result = subprocess.run([sys.executable, VALIDATE] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


def run_cli(*args):
    result = subprocess.run([sys.executable, SAY_HUMAN] + list(args),
                            capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


class TestEvidenceClasses(unittest.TestCase):
    """One claim in each evidence class, classified deterministically."""

    def setUp(self):
        self.registry = load_registry()

    def test_source(self):
        evidence = say_human.classify_claim(
            "The cache evicts entries after they expire.",
            "The cache evicts entries after they expire.")
        self.assertEqual(evidence, "source")

    def test_logic(self):
        evidence = say_human.classify_claim(
            "The queue backed up because the worker lost its lease.",
            "The worker lost its lease. The queue backed up.")
        self.assertEqual(evidence, "logic")

    def test_experience(self):
        evidence = say_human.classify_claim(
            "In my experience, the deploy was slow.",
            "The deploy was slow.")
        self.assertEqual(evidence, "experience")

    def test_inference(self):
        evidence = say_human.classify_claim(
            "The error likely affects more hosts.",
            "Three of ten hosts fail.")
        self.assertEqual(evidence, "inference")

    def test_unknown(self):
        evidence = say_human.classify_claim(
            "The fix doubled throughput.",
            "The fix shipped.")
        self.assertEqual(evidence, "unknown")

    def test_source_precedence_over_experience_markers(self):
        evidence = say_human.classify_claim(
            "We shipped the retry queue.",
            "We shipped the retry queue.")
        self.assertEqual(evidence, "source")

    def test_all_fixture_claims_have_distinct_classes(self):
        fixtures = [f for f in load_fixtures() if f["kind"] == "label"]
        classes = {f["expected_evidence"] for f in fixtures}
        self.assertEqual(classes, set(EVIDENCE_CLASSES))


class TestFixtureSchema(unittest.TestCase):
    """The say-human fixture schema validates label, repair, and locale."""

    def setUp(self):
        self.registry = load_registry()

    def test_all_fixtures_validate(self):
        fixtures = load_fixtures()
        seen = set()
        for fixture in fixtures:
            errors = say_human.validate_fixture(fixture, seen)
            self.assertEqual(errors, [], "fixture %s: %s"
                             % (fixture.get("id"), errors))

    def test_unknown_evidence_rejected(self):
        errors = say_human.validate_fixture({
            "id": "bad-evidence",
            "kind": "label",
            "source": "x",
            "claim": "y",
            "expected_evidence": "bogus",
        }, set())
        self.assertTrue(any("expected_evidence must be one of"
                            in error for error in errors))

    def test_unknown_venue_rejected(self):
        errors = say_human.validate_fixture({
            "id": "bad-venue",
            "kind": "repair",
            "source": "x",
            "venue": "novel",
            "expected_decision": "applied",
        }, set())
        self.assertTrue(any("venue must be one of" in error
                           for error in errors))

    def test_unknown_locale_rejected(self):
        errors = say_human.validate_fixture({
            "id": "bad-locale",
            "kind": "locale",
            "source": "x",
            "locale": "ja-JP",
            "expected_active": True,
        }, set())
        self.assertTrue(any("locale must be one of" in error
                           for error in errors))


class TestRepairGates(unittest.TestCase):
    """Required unknown evidence, protected spans, authority, and venues."""

    def setUp(self):
        self.registry = load_registry()

    def test_required_unknown_evidence_stops(self):
        report = say_human.repair_say_human(
            "We utilize the API to fetch records.",
            self.registry,
            required_claims=("It doubles throughput.",))
        self.assertEqual(report["decision"], "needs-source")
        self.assertEqual([item["claim"] for item in report["needs_source"]],
                         ["It doubles throughput."])
        self.assertEqual(report["text"],
                         "We utilize the API to fetch records.")

    def test_required_source_evidence_proceeds(self):
        report = say_human.repair_say_human(
            "We utilize the API to fetch records. "
            "The new endpoint doubles throughput.",
            self.registry,
            required_claims=("The new endpoint doubles throughput.",))
        self.assertEqual(report["decision"], "applied")
        evidence = {entry["claim"]: entry["evidence"]
                    for entry in report["evidence"]}
        self.assertEqual(
            evidence["The new endpoint doubles throughput."], "source")

    def test_repair_exposes_evidence_class(self):
        report = say_human.repair_say_human(
            "We utilize the API to fetch records.", self.registry)
        self.assertEqual(report["decision"], "applied")
        replaced = [row for row in report["replacements"]
                    if row["rule_id"] == "vocab-utilize"]
        self.assertEqual(replaced[0]["evidence"], "source")

    def test_protected_technical_spans_survive(self):
        source = ("We utilize the API. Run `fetch(123)` against "
                  "https://example.com/api/v1 and check get_user_by_id "
                  "with 30 items.")
        report = say_human.repair_say_human(source, self.registry)
        self.assertEqual(report["decision"], "applied")
        for token in ("`fetch(123)`", "https://example.com/api/v1",
                      "get_user_by_id", "30"):
            self.assertIn(token, report["text"])

    def test_mixed_chinese_prose_with_technical_spans(self):
        source = ("系统启动时间缩短了。We utilize the API. 调用 "
                  "`fetchRecords` 和 https://example.com/api/v1 共 30 次。")
        report = say_human.repair_say_human(source, self.registry,
                                            locale="zh-CN")
        self.assertEqual(report["decision"], "applied")
        for token in ("`fetchRecords`", "https://example.com/api/v1", "30"):
            self.assertIn(token, report["text"])
        claims = [entry["claim"] for entry in report["evidence"]]
        self.assertIn("调用 `fetchRecords` 和 "
                      "https://example.com/api/v1 共 30 次。", claims)

    def test_split_claims_does_not_break_urls(self):
        claims = say_human.split_claims(
            "The API returns records at https://example.com/api/v1. Next.")
        texts = [claim for claim, _, _ in claims]
        self.assertIn("The API returns records at "
                      "https://example.com/api/v1.", texts)
        self.assertIn("Next.", texts)

    def test_voice_trait_preserved_without_new_slang(self):
        report = say_human.repair_say_human(
            "We utilize the API, kinda. It works.", self.registry,
            voice_traits=("kinda",))
        self.assertEqual(report["decision"], "applied")
        self.assertIn("kinda", report["text"])
        self.assertEqual(report["text"],
                         "We use the API, kinda. It works.")

    def test_release_note_unsupported_feature_claim(self):
        report = say_human.repair_say_human(
            "Added a retry queue. It now supports WebSockets.",
            self.registry, venue="release-note",
            supplied_changes=("Added a retry queue.",))
        self.assertEqual(report["decision"], "needs-source")
        self.assertIn("It now supports WebSockets.",
                      [item["claim"] for item in report["needs_source"]])

    def test_release_note_grounded(self):
        report = say_human.repair_say_human(
            "Added a retry queue.", self.registry, venue="release-note",
            supplied_changes=("Added a retry queue.",))
        self.assertEqual(report["decision"], "no-change")
        checks = {row["feature"]: row["status"]
                  for row in report["venue"]["checks"]}
        self.assertEqual(checks["change-evidence"], "keep")

    def test_large_deletion_refused_without_authority(self):
        source = ("The API returns records. Here is my reasoning: this is a "
                  "very long internal planning trace that should be removed "
                  "entirely from the output.")
        report = say_human.repair_say_human(source, self.registry)
        self.assertEqual(report["decision"], "needs-authority")
        self.assertTrue(report["refused_deletions"])
        self.assertEqual(report["text"], source)

    def test_large_deletion_applies_with_authority(self):
        source = ("The API returns records. Here is my reasoning: this is a "
                  "very long internal planning trace that should be removed "
                  "entirely from the output.")
        report = say_human.repair_say_human(source, self.registry,
                                            authorize_delete=True)
        self.assertEqual(report["decision"], "applied")
        self.assertTrue(report["diff"])
        self.assertNotIn("Here is my reasoning", report["text"])

    def test_technical_documentation_venue_routing(self):
        report = say_human.repair_say_human(
            "Run `fetch --all` and call get_user_by_id(7) against "
            "https://example.com/api. We utilize the API.",
            self.registry, venue="technical-documentation")
        self.assertEqual(report["decision"], "applied")
        checks = {row["feature"]: row["status"]
                  for row in report["venue"]["checks"]}
        self.assertEqual(checks["technical-spans"], "keep")


class TestLocaleRouting(unittest.TestCase):
    """zh-CN rules activate only when selected or reliably routed."""

    def test_selected_zh_cn_active(self):
        report = say_human.locale_report("他说:你好,世界。", "zh-CN",
                                         load_registry())
        self.assertEqual(report["active"], "zh-CN")
        self.assertIn("zh-cn-punct-width",
                      [f["rule_id"] for f in report["findings"]])

    def test_auto_routed_han_dominant(self):
        report = say_human.locale_report("系统启动时间缩短了。我们很高兴。",
                                         "", load_registry())
        self.assertEqual(report["active"], "zh-CN")

    def test_not_routed_english(self):
        report = say_human.locale_report(
            "This is purely English prose with no Chinese characters at all.",
            "", load_registry())
        self.assertEqual(report["active"], "")
        self.assertEqual(report["findings"], [])

    def test_fullwidth_punctuation_clean(self):
        report = say_human.locale_report("他说：你好，世界。", "zh-CN",
                                         load_registry())
        self.assertEqual([f["rule_id"] for f in report["findings"]], [])

    def test_code_and_url_protected(self):
        report = say_human.locale_report(
            "运行 `fetch(123)` 请求 https://example.com/api/v1 接口。",
            "zh-CN", load_registry())
        self.assertEqual([f["rule_id"] for f in report["findings"]], [])

    def test_spacing_finding(self):
        report = say_human.locale_report("使用Python开发", "zh-CN",
                                         load_registry())
        self.assertIn("zh-cn-spacing",
                      [f["rule_id"] for f in report["findings"]])

    def test_spacing_clean(self):
        report = say_human.locale_report("使用 Python 开发", "zh-CN",
                                         load_registry())
        self.assertEqual([f["rule_id"] for f in report["findings"]], [])

    def test_translationese_finding(self):
        report = say_human.locale_report("他被大家所熟知", "zh-CN",
                                         load_registry())
        self.assertIn("zh-cn-translationese",
                      [f["rule_id"] for f in report["findings"]])

    def test_translationese_clean(self):
        report = say_human.locale_report(
            "我们修复了缓存问题。现在启动很快。", "zh-CN", load_registry())
        self.assertEqual([f["rule_id"] for f in report["findings"]], [])


class TestCorpusAndCLI(unittest.TestCase):
    """The shipped corpus passes and the CLI reaches the runner."""

    def test_corpus_passes(self):
        fixtures = load_fixtures()
        registry = load_registry()
        report = say_human.run_corpus(fixtures, registry, REGISTRY)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["failures"], [])
        self.assertTrue(report["gate_pass"])
        self.assertEqual(report["passed"], len(fixtures))

    def test_validator_gate_passes(self):
        rc, output = run_validator("--skills-dir", "skills",
                                   "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, output)
        self.assertIn("ALL CHECKS PASSED", output)

    def test_cli_label(self):
        rc, output = run_cli("--json", "label",
                             "--source-text", "The cache evicts entries.",
                             "--claim", "The cache evicts entries.")
        self.assertEqual(rc, 0, output)
        report = json.loads(output)
        self.assertEqual(report["evidence"][0]["evidence"], "source")

    def test_cli_repair_needs_source(self):
        rc, output = run_cli("--json", "repair",
                             "--source-text", "We utilize the API.",
                             "--required-claim", "It doubles throughput.")
        self.assertEqual(rc, 0, output)
        report = json.loads(output)
        self.assertEqual(report["decision"], "needs-source")

    def test_cli_locale_auto_route(self):
        rc, output = run_cli("--json", "locale",
                             "--source-text", "系统启动时间缩短了。")
        self.assertEqual(rc, 0, output)
        report = json.loads(output)
        self.assertEqual(report["active"], "zh-CN")


if __name__ == "__main__":
    unittest.main()