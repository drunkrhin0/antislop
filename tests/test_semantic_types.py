#!/usr/bin/env python3
"""Tests for semantic rule types (issue #86).

Covers:
  - registry schema: semantic_type, review_mode, and the six metadata fields
  - score behavior: non-scoring semantic types never change the risk score
  - validate.py rejection of unknown semantic types, non-deterministic
    forbidden rules, and rules without source provenance
  - generate.py determinism and semantic labelling of the pattern reference
  - migration: every pre-change stable rule ID is retained
  - skill surfaces: style renders positive/structural guidance as actions and
    audit distinguishes deterministic, advisory, human, and integrity findings

Run: python3 -m unittest tests/test_semantic_types.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGISTRY = os.path.join(ROOT, "rules.json")
VALIDATE = os.path.join(ROOT, "validate.py")
GENERATE = os.path.join(ROOT, "generate.py")
SCORE = os.path.join(ROOT, "score.py")
TOP_LEVEL_SKILL = os.path.join(ROOT, "skills", "antislop", "SKILL.md")
AUDIT_SKILL = os.path.join(ROOT, "skills", "antislop", "references",
                             "audit-mode.md")
STYLE_SKILL = os.path.join(ROOT, "skills", "antislop", "references",
                           "style-mode.md")
SHARED_CONTRACT = os.path.join(ROOT, "skills", "antislop", "references",
                               "shared-contract.md")


def read_references(*paths):
    return chr(10).join(
        open(path, encoding="utf-8").read()
        for path in paths
    )

sys.path.insert(0, ROOT)
import validate  # noqa: E402 -- import after sys.path setup, for direct unit tests

VALID_SEMANTIC_TYPES = {"forbidden", "discouraged", "preferred", "structural",
                        "integrity", "evaluation"}
VALID_REVIEW_MODES = {"deterministic", "advisory", "human"}

# Frozen migration contract: the stable rule IDs that existed before the
# semantic-type migration. None of these may be renamed or dropped.
STABLE_RULE_IDS = [
    "vocab-delve", "vocab-leverage", "vocab-tapestry", "vocab-testament", "vocab-vibrant",
    "vocab-pivotal", "vocab-utilize", "vocab-synergy", "vocab-holistic", "vocab-seamless",
    "vocab-robust", "vocab-groundbreaking", "vocab-cutting-edge", "vocab-innovative",
    "vocab-dynamic", "vocab-comprehensive", "vocab-embark", "vocab-foster",
    "vocab-revolutionize", "vocab-transformative", "vocab-empower", "vocab-unlock",
    "vocab-supercharge", "vocab-significant", "vocab-commence", "vocab-obtain",
    "vocab-implement", "vocab-facilitate", "vocab-subsequently", "vocab-discontinue",
    "vocab-dispatch", "vocab-ascertain", "vocab-navigate", "vocab-unpack", "vocab-enhance",
    "vocab-showcase", "vocab-interplay", "phrase-worth-noting", "phrase-today-world",
    "phrase-ever-evolving", "phrase-agile-adaptation", "phrase-at-core", "phrase-dive-in", "phrase-not-just",
    "phrase-game-changer", "phrase-treasure-trove", "phrase-cannot-denied",
    "phrase-underscores", "phrase-knowledge-cutoff", "phrase-research-shows",
    "phrase-despite-thrive", "phrase-future-bright", "phrase-let-sink-in",
    "phrase-full-stop", "phrase-make-no-mistake", "phrase-let-me-clear", "phrase-explore",
    "phrase-what-looks-like", "phrase-creeps-in", "phrase-heres-thing",
    "phrase-hint-plot-spoiler", "phrase-walk-through", "phrase-think-about-it",
    "phrase-thats-okay", "phrase-transition-glue", "phrase-complexity-signal",
    "phrase-discovery-narration", "phrase-in-conclusion", "phrase-certainly",
    "phrase-absolutely-right", "phrase-hope-helps", "phrase-moreover", "filler-in-order",
    "filler-due-to-fact", "filler-at-point-in-time", "filler-system-ability",
    "filler-important-note", "filler-crucial", "struct-rule-of-three",
    "struct-synonym-cycling", "struct-copula-avoidance", "struct-ing-analyses",
    "struct-significance-inflation", "struct-passive-voice", "struct-emphasis-tails",
    "struct-rhetorical-hooks", "struct-balanced-take", "struct-simile-adverb",
    "struct-hedged-reactions", "struct-because-fragments", "struct-temperature-emotion",
    "struct-physical-tells", "struct-uniform-sentence", "struct-overlong-sentence",
    "struct-link-text", "struct-all-same-length", "struct-parataxis", "struct-subject-loops",
    "struct-fragmented-headers", "struct-anthropomorphized-silence",
    "struct-paragraph-redundancy", "struct-artificial-line-breaks", "struct-bullet-crutch",
    "struct-concession-rhythm", "struct-type-definition", "struct-announce-structure",
    "struct-antithesis", "struct-negation-flip", "struct-false-ranges", "struct-promotional",
    "struct-notability-dropping", "struct-triplet-overlap", "struct-awkward-metaphors",
    "struct-ending-cliches", "struct-specificity-theater", "struct-catalog-prose",
    "struct-system-tour", "struct-transition-glue", "struct-complexity-signalling",
    "struct-discovery-narration", "struct-wisdom-sandwich", "struct-corrective-reveals",
    "struct-punchy-closure", "struct-weak-verbs", "struct-empty-declaratives",
    "struct-transformation-chains", "struct-it-turns-out", "fmt-em-dash", "fmt-title-case",
    "fmt-inline-header", "fmt-compound-hyphen", "fmt-curly-quotes", "fmt-emojis",
    "fmt-exclamation", "fmt-semicolon", "chatbot-hope-helps", "chatbot-let-me-know",
    "chatbot-great-question", "chatbot-certainly-absolutely", "chatbot-cutoff-disclaimers",
    "phrase-expert-cosplay", "struct-colon-reveal", "filler-padding-adverbs",
    "phrase-what-if-i-told", "phrase-self-answered-qa", "fmt-emoji-bullets",
    "struct-listicle-trenchcoat",
    # Issue #82: Cursor unslop adaptation adds a mid-sentence colon-overuse
    # structural rule (advisory, never skipped). Extends the stable set.
    "struct-colon-overuse",
    # Issue #77: audit and vocabulary acceptance gaps add agile and
    # constantly-evolving to the scored surface. Extends the stable set.
    "vocab-agile", "phrase-constantly-evolving",
    # Issue #85: evidence-first adaptation adds eight marketing-adjacent
    # phrase/vocab rules and six structural publishing detectors. Extends
    # the stable set.
    "vocab-streamline", "phrase-stay-ahead", "phrase-end-to-end",
    "phrase-actionable-insights", "phrase-optimal-outcomes",
    "phrase-goes-without-saying", "phrase-best-in-class",
    "phrase-second-to-none", "struct-numbered-list-inflation",
    "struct-paragraph-reshuffle", "struct-treadmill-prose",
    "struct-chat-citation-leaks", "struct-ai-url-parameters",
    "struct-unfilled-placeholders",
    # Issue #88: Vale-style structural detectors (six advisory metrics, two
    # strict checks). These extend the stable set; no pre-existing ID moves.
    "struct-sentence-length-variance", "struct-paragraph-length-variance",
    "struct-sentence-start-repetition", "struct-transition-repetition",
    "struct-paragraph-similarity", "struct-tricolon-density",
    "struct-paragraph-duplication", "struct-passive-density",
    # Issue #96: Clarity-style mechanism checks (advisory, never skipped).
    # These extend the stable set; no pre-existing ID moves.
    "mechanism-importance", "mechanism-impact", "mechanism-causality",
    "mechanism-superiority",
    # Issue #100: density, precision, and structural-candidate detectors
    # (advisory or human review, never skipped). These extend the stable set;
    # no pre-existing ID moves.
    "struct-passage-density", "struct-unsourced-precision",
    "struct-heading-hierarchy", "struct-engagement-bait",
    "struct-template-headings", "struct-self-promotion", "struct-rather-than",
    # Issue #139: accepted Humanizer 3 contextual structural rules.
    "struct-vague-association", "struct-previous-version",
]


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def run(*args, input_text=None, cwd=ROOT):
    result = subprocess.run([sys.executable] + list(args), capture_output=True,
                            text=True, cwd=cwd, input=input_text)
    return result.returncode, result.stdout, result.stderr


def make_rule(rid="test-rule", **overrides):
    """A minimal, schema-valid rule with per-test overrides."""
    rule = {
        "id": rid,
        "text": "example",
        "category": "vocabulary",
        "severity": "high",
        "base_weight": 8,
        "detection_class": "exact_match",
        "profiles": ["*"],
        "exceptions": [],
        "overlaps": [],
        "examples": [],
        "confidence": "high",
        "semantic_type": "forbidden",
        "correction": "fix it",
        "sources": ["drunkrhin0/antislop (self)"],
        "evidence": "a match is sufficient evidence",
        "false_positive_boundary": "quoted material is not a target",
        "review_mode": "deterministic",
    }
    rule.update(overrides)
    return rule


def run_validator_on_registry(registry):
    """Run validate.py against a tmp repo whose only registry is the given one."""
    with tempfile.TemporaryDirectory(prefix="antislop-sem-") as tmp:
        os.makedirs(os.path.join(tmp, "skills"))
        with open(os.path.join(tmp, "rules.json"), "w", encoding="utf-8") as f:
            json.dump(registry, f)
        rc, stdout, stderr = run(VALIDATE, "--skills-dir", os.path.join(tmp, "skills"))
        return rc, stdout + stderr


class TestSemanticTypeSchema(unittest.TestCase):
    """The registry schema accepts and validates every semantic type."""

    def setUp(self):
        self.registry = load_registry()
        self.rules = self.registry["rules"]
        self.by_id = {r["id"]: r for r in self.rules}

    def test_all_six_semantic_types_are_represented(self):
        types = {r["semantic_type"] for r in self.rules}
        self.assertEqual(types, VALID_SEMANTIC_TYPES,
                         f"Registry must represent every semantic type, got {types}")

    def test_semantic_type_values_are_valid(self):
        for rule in self.rules:
            self.assertIn(rule["semantic_type"], VALID_SEMANTIC_TYPES,
                          f"Rule {rule['id']}: invalid semantic_type")

    def test_review_mode_values_are_valid(self):
        for rule in self.rules:
            self.assertIn(rule["review_mode"], VALID_REVIEW_MODES,
                          f"Rule {rule['id']}: invalid review_mode")

    def test_every_rule_has_the_six_metadata_fields(self):
        required = {"semantic_type", "correction", "sources", "evidence",
                    "false_positive_boundary", "review_mode"}
        for rule in self.rules:
            missing = required - set(rule.keys())
            self.assertFalse(missing, f"Rule {rule['id']} missing: {missing}")

    def test_metadata_fields_are_non_empty(self):
        for rule in self.rules:
            for field in ("semantic_type", "correction", "evidence",
                          "false_positive_boundary", "review_mode"):
                self.assertTrue(rule.get(field),
                                f"Rule {rule['id']}: empty '{field}'")
            self.assertIsInstance(rule["sources"], list)
            self.assertGreater(len(rule["sources"]), 0,
                               f"Rule {rule['id']}: empty sources")

    def test_forbidden_rules_are_deterministic_with_machine_evidence(self):
        for rule in self.rules:
            if rule["semantic_type"] != "forbidden":
                continue
            self.assertEqual(rule["review_mode"], "deterministic",
                             f"Rule {rule['id']}: forbidden must be deterministic")
            self.assertIn(rule["detection_class"],
                          ("exact_match", "phrase_match", "pattern_match"),
                          f"Rule {rule['id']}: forbidden needs machine-checkable detection")

    def test_preferred_and_structural_are_never_scored(self):
        for rule in self.rules:
            if rule["semantic_type"] in ("preferred", "structural"):
                self.assertIn("never", rule["evidence"].lower(),
                              f"Rule {rule['id']}: evidence must state it never deducts")

    def test_em_dash_rule_contract(self):
        """The em-dash rule stays forbidden, universal, deterministic, zero-count."""
        rule = self.by_id["fmt-em-dash"]
        self.assertEqual(rule["semantic_type"], "forbidden")
        self.assertEqual(rule["review_mode"], "deterministic")
        self.assertEqual(rule["profiles"], ["*"])
        self.assertEqual(rule["detection_class"], "exact_match")
        self.assertEqual(rule["severity"], "high")
        self.assertIn("zero", rule["evidence"].lower())

    def test_discouraged_rules_state_their_false_positive_boundary(self):
        """A contextual rule names its boundary; the quotation case is explicit."""
        rule = self.by_id["phrase-game-changer"]
        self.assertEqual(rule["semantic_type"], "discouraged")
        self.assertEqual(rule["review_mode"], "advisory")
        boundary = rule["false_positive_boundary"].lower()
        self.assertIn("quotations", boundary)

    def test_sources_cite_reviewed_snapshots_for_adopted_rules(self):
        """Adopted rules carry pinned source provenance."""
        rule = self.by_id["struct-catalog-prose"]
        self.assertTrue(any("Anbeeld" in s for s in rule["sources"]), rule["sources"])
        rule = self.by_id["vocab-interplay"]
        self.assertTrue(any("tagore" in s for s in rule["sources"]), rule["sources"])


class TestScoreBehavior(unittest.TestCase):
    """Non-scoring semantic types never change the Formulaic Writing Risk Score."""

    def setUp(self):
        self.registry = load_registry()

    def _score(self, text):
        rc, stdout, stderr = run(SCORE, "--profile", "general", "--stdin", input_text=text)
        self.assertEqual(rc, 0, stderr)
        return json.loads(stdout)

    def test_clean_text_scores_100(self):
        data = self._score("This text has no violations at all.")
        self.assertEqual(data["score"], 100)
        self.assertEqual(data["findings"], [])

    def test_integrity_tokens_do_not_change_the_score(self):
        text = ("The report covers the 2026 threat landscape "
                "[source: internal Q1 report]. Key findings [TODO: add specifics].")
        data = self._score(text)
        self.assertEqual(data["score"], 100)
        self.assertEqual(data["findings"], [])

    def test_short_factual_reference_entry_keeps_full_score(self):
        text = ("Nessus scan of the 10.0.0.0/24 range found 12 hosts running "
                "a service with CVE-2024-3094. Three are internet-facing.")
        data = self._score(text)
        self.assertEqual(data["score"], 100)

    def test_existing_score_behavior_is_unchanged(self):
        """A high-severity finding still deducts 8 points at 500 words."""
        text = "delve " + "ordinary " * 499
        data = self._score(text)
        self.assertEqual(data["score"], 92)

    def test_skipped_rules_do_not_inflate_from_new_rule_types(self):
        """Non-scoring rules must not add to the skipped-rule coverage gap.

        Detector-backed structural rules are implemented (never skipped), so
        the expected gap counts only scoring rules that still lack a
        registered detector.
        """
        scoring = [r for r in self.registry["rules"]
                   if r["semantic_type"] in ("forbidden", "discouraged")]
        expected = sum(1 for r in scoring
                       if r.get("detection_class") in ("pattern_match", "structural")
                       and not r.get("detector"))
        data = self._score("This text has no violations at all.")
        self.assertEqual(data["metadata"]["skipped_rules"], expected)


class TestValidateRejects(unittest.TestCase):
    """AC 8: validation rejects bad semantic metadata."""

    def _make_registry(self, *rules):
        social = [
            make_rule(rid="social-reach-promise",
                      category="structural", severity="medium",
                      base_weight=4, detection_class="pattern_match",
                      detector="social_reach_promise", profiles=["social-linkedin"],
                      semantic_type="discouraged", review_mode="advisory",
                      evidence="a promise with no mechanism nearby"),
            make_rule(rid="social-mobile-paragraphs",
                      category="structural", severity="low",
                      base_weight=2, detection_class="manual",
                      profiles=["social-linkedin"], semantic_type="preferred",
                      review_mode="advisory", evidence="guidance, never a deduction"),
            make_rule(rid="social-optional-cta",
                      category="structural", severity="low",
                      base_weight=2, detection_class="manual",
                      profiles=["social-linkedin"], semantic_type="preferred",
                      review_mode="advisory", evidence="guidance, never a deduction"),
            make_rule(rid="social-optional-hook",
                      category="structural", severity="low",
                      base_weight=2, detection_class="manual",
                      profiles=["social-linkedin"], semantic_type="preferred",
                      review_mode="advisory", evidence="guidance, never a deduction"),
            make_rule(rid="social-optional-hashtags",
                      category="structural", severity="low",
                      base_weight=2, detection_class="manual",
                      profiles=["social-linkedin"], semantic_type="preferred",
                      review_mode="advisory", evidence="guidance, never a deduction"),
            make_rule(rid="social-scarl-optional",
                      category="structural", severity="low",
                      base_weight=2, detection_class="manual",
                      profiles=["social-linkedin"], semantic_type="preferred",
                      review_mode="advisory", evidence="guidance, never a deduction"),
        ]
        return {
            "version": "2.0.3",
            "description": "test",
            "rules": list(rules) + social,
            "operations": {
                "draft": {"authority": "create", "boundary": "style only"},
                "revise": {"authority": "edit", "boundary": "preserve"},
                "audit": {"authority": "report", "boundary": "unchanged"},
                "transform": {"authority": "reshape", "boundary": "disclose"},
            },
            "inventory_categories": ["claims", "facts", "quantities"],
            "review_statuses": {
                "keep": "earned", "revise": "improve",
                "ask-author": "ask", "cut": "cut", "no-finding": "clean",
                "n/a": "does not apply", "over-correction": "flattens voice",
            },
            "profiles": {
                "general": {"default": True, "description": "default"},
                "technical": {"default": False, "description": "tech"},
                "fiction": {"default": False,
                            "description": "opt-in fiction profile"},
                "social-linkedin": {
                    "default": False,
                    "description": "opt-in social profile",
                },
            },
            "social_post_features": {
                name: {"name": name, "description": "d", "deterministic": "d"}
                for name in ("setup", "challenge", "action", "result",
                             "lesson", "position", "announcement", "steps")
            },
            "social_post_types": {
                name: {
                    "description": "d", "optimize": "o", "preserve": "p",
                    "avoid": "a", "applicable": [], "not_applicable": [],
                }
                for name in ("lesson", "case-study", "announcement",
                             "opinion", "practical-guide")
            },
            "venue_features": {
                name: {"name": name, "description": "d", "deterministic": "d"}
                for name in ("timeline", "impact", "contributing-factors",
                             "uncertainty", "repro", "acceptance",
                             "answer-first", "breaking-changes",
                             "problem-first", "reflection-tail")
            },
            "venues": {
                name: {
                    "description": "d", "optimize": "o", "preserve": "p",
                    "avoid": "a", "applicable": [], "not_applicable": [],
                }
                for name in ("ticket", "developer-reply", "postmortem",
                             "technical-article", "release-note")
            },
            "mediums": {
                "argument": {"description": "arg", "optimize": "fit",
                             "preserve": "evidence", "avoid": "survey"},
                "explanation": {"description": "explain", "optimize": "mech",
                                "preserve": "caveats", "avoid": "fudge"},
                "evocation": {"description": "evoke", "optimize": "image",
                              "preserve": "rhythm", "avoid": "thesis"},
                "narrative": {"description": "story", "optimize": "scene",
                              "preserve": "voice", "avoid": "disorder"},
                "guide": {"description": "steps", "optimize": "correct",
                          "preserve": "warnings", "avoid": "novelty"},
                "reference": {"description": "retrieve", "optimize": "scan",
                              "preserve": "schemas", "avoid": "inconsistent"},
                "message": {"description": "ask", "optimize": "request",
                            "preserve": "politeness", "avoid": "essay"},
            },
        }

    def test_accepts_a_valid_registry(self):
        reg = self._make_registry(make_rule())
        rc, output = run_validator_on_registry(reg)
        self.assertEqual(rc, 0, output)

    def test_rejects_a_registry_without_operations(self):
        reg = self._make_registry(make_rule())
        del reg["operations"]
        del reg["inventory_categories"]
        rc, output = run_validator_on_registry(reg)
        self.assertNotEqual(rc, 0)
        self.assertIn("missing 'operations' object", output)
        self.assertIn("inventory_categories must be a non-empty list", output)

    def test_rejects_unknown_semantic_type(self):
        reg = self._make_registry(make_rule(semantic_type="banned"))
        rc, output = run_validator_on_registry(reg)
        self.assertNotEqual(rc, 0)
        self.assertIn("unknown semantic_type", output)

    def test_rejects_forbidden_rule_without_deterministic_review(self):
        reg = self._make_registry(make_rule(review_mode="human"))
        rc, output = run_validator_on_registry(reg)
        self.assertNotEqual(rc, 0)
        self.assertIn("forbidden rule must be deterministic", output)

    def test_rejects_forbidden_rule_without_deterministic_evidence(self):
        reg = self._make_registry(make_rule(detection_class="manual"))
        rc, output = run_validator_on_registry(reg)
        self.assertNotEqual(rc, 0)
        self.assertIn("forbidden rule without deterministic evidence", output)

    def test_rejects_rule_without_source_provenance(self):
        reg = self._make_registry(make_rule(sources=[]))
        rc, output = run_validator_on_registry(reg)
        self.assertNotEqual(rc, 0)
        self.assertIn("without source provenance", output)

    def test_rejects_invalid_review_mode(self):
        reg = self._make_registry(
            make_rule(semantic_type="preferred", review_mode="automatic"))
        rc, output = run_validator_on_registry(reg)
        self.assertNotEqual(rc, 0)
        self.assertIn("invalid review_mode", output)

    def test_production_registry_passes_validation(self):
        rc, stdout, stderr = run(VALIDATE, "--skills-dir", "skills",
                                 "--expect-version", "3.0.0")
        self.assertEqual(rc, 0, stdout + stderr)


class TestGeneratorSemantics(unittest.TestCase):
    """Generated pattern references group and label rules by semantics."""

    def test_generate_check_passes(self):
        rc, stdout, stderr = run(GENERATE, "--check")
        self.assertEqual(rc, 0, stdout + stderr)

    def test_pattern_reference_labels_semantics(self):
        path = os.path.join(ROOT, "skills", "antislop", "references",
                            "pattern-reference.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for heading in ("## Semantic types",
                        "## Vocabulary — forbidden",
                        "## Phrases — discouraged (context required)",
                        "## Structural patterns — discouraged",
                        "## Positive guidance — preferred (never scored)",
                        "## Document guidance — structural (never scored)",
                        "## Output integrity — reported separately, never scored",
                        "## Evaluation metadata — never scored, not authorship evidence",
                        "## Severity weights"):
            self.assertIn(heading, text, f"missing generated heading: {heading}")

    def test_non_scoring_rules_render_in_their_own_sections(self):
        registry = load_registry()
        from registry import filter_rules_by_profile
        active = {rule["id"]: rule for rule in
                  filter_rules_by_profile(registry["rules"], "general")}
        path = os.path.join(ROOT, "skills", "antislop", "references",
                            "pattern-reference.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for rule in active.values():
            if rule["semantic_type"] in ("preferred", "structural", "integrity", "evaluation"):
                self.assertIn(rule["text"], text,
                              f"Rule {rule['id']} missing from pattern reference")
        for rule in active.values():
            if rule["semantic_type"] in ("forbidden", "discouraged"):
                self.assertIn(rule["text"], text,
                              f"Scored rule {rule['id']} missing from pattern reference")


class TestStableRuleIDMigration(unittest.TestCase):
    """AC 9: every existing stable rule ID is retained."""

    def test_all_stable_ids_retained(self):
        registry = load_registry()
        ids = {r["id"] for r in registry["rules"]}
        missing = [i for i in STABLE_RULE_IDS if i not in ids]
        self.assertEqual(missing, [], f"Stable rule IDs dropped: {missing}")

    def test_no_duplicate_ids(self):
        registry = load_registry()
        ids = [r["id"] for r in registry["rules"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_scoring_rule_count_is_unchanged(self):
        """Forbidden + discouraged rules in the general profile match the
        stable set.

        The stable set is the migrated set, the #54 acceptance regression,
        and the issue #88 structural rules, which are scored (discouraged) yet never skipped because each
        names a registered detector. Profile-scoped rules (fiction, and the
        opt-in social-linkedin reach-promise rule) are not part of the
        general scoring surface and are excluded here.
        """
        from registry import filter_rules_by_profile
        registry = load_registry()
        active = filter_rules_by_profile(registry["rules"], "general")
        scored = [r for r in active
                  if r["semantic_type"] in ("forbidden", "discouraged")]
        self.assertEqual(len(scored), len(STABLE_RULE_IDS),
                         "Scoring rule set must match the stable set")


class TestSkillSurfaces(unittest.TestCase):
    """AC 5 and 6: style renders guidance as actions; audit distinguishes findings."""

    def test_style_skill_renders_positive_and_structural_guidance_as_actions(self):
        text = read_references(STYLE_SKILL, SHARED_CONTRACT)
        self.assertIn("## Positive guidance", text)
        self.assertIn("## Document structure", text)
        self.assertIn("never count against a score", text)
        self.assertIn("## Output integrity", text)

    def test_audit_skill_distinguishes_review_modes_and_integrity(self):
        text = read_references(TOP_LEVEL_SKILL, AUDIT_SKILL, SHARED_CONTRACT)
        self.assertIn("Deterministic", text)
        self.assertIn("Advisory", text)
        self.assertIn("Human", text)
        self.assertIn("## Output integrity", text)
        self.assertIn("never change the score", text)
        self.assertIn("cannot prove AI authorship", text)


if __name__ == "__main__":
    unittest.main()
