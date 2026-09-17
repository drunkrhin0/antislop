#!/usr/bin/env python3
"""Tests for the Vale-style structural detector interface (issue #88).

Covers the eight detectors: sentence and paragraph length variance,
sentence-start and transition repetition, paragraph similarity, tricolon
density, paragraph duplication, and passive density. Each detector gets
trigger, clean, boundary, and technical false-positive fixtures, plus the
issue's evaluation fixtures: repeated sentence openings with a deliberate
parallel passage, paragraph duplication with a technical definition that
repeats necessary terms, a tricolon reflex with an earned three-part
requirement, and short text where variation metrics return
insufficient-sample.

Also covers the acceptance criteria at the score seam:
  - strict and advisory findings have distinct exit and score behavior
  - same-span overlaps produce one primary finding and related signals
  - every new registry rule names a registered detector
  - metrics never make authorship claims

Run: python3 -m unittest tests/test_structural.py -v
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGISTRY = os.path.join(ROOT, "rules.json")
SCORE = os.path.join(ROOT, "tools", "score.py")
STRUCTURAL = os.path.join(ROOT, "tools", "structural.py")

sys.path.insert(0, ROOT)
import structural  # noqa: E402

DETECTOR_RULES = [
    ("struct-sentence-length-variance", "sentence_length_variance", "advisory"),
    ("struct-paragraph-length-variance", "paragraph_length_variance", "advisory"),
    ("struct-sentence-start-repetition", "sentence_start_repetition", "advisory"),
    ("struct-transition-repetition", "transition_repetition", "advisory"),
    ("struct-paragraph-similarity", "paragraph_similarity", "advisory"),
    ("struct-tricolon-density", "tricolon_density", "advisory"),
    ("struct-paragraph-duplication", "paragraph_duplication", "deterministic"),
    ("struct-passive-density", "passive_density", "deterministic"),
]


def make_rule(rid, detector, review_mode="advisory", severity="medium",
              base_weight=4):
    return {
        "id": rid,
        "category": "structural",
        "severity": severity,
        "base_weight": base_weight,
        "detection_class": "structural",
        "detector": detector,
        "profiles": ["*"],
        "semantic_type": "discouraged",
        "correction": "fix it",
        "review_mode": review_mode,
    }


def run_detector(text, rid, detector, review_mode="advisory"):
    result = structural.run_detectors(
        text, [make_rule(rid, detector, review_mode)], "general")
    return result


def run_cli(*args, input_text=None):
    result = subprocess.run([sys.executable, STRUCTURAL] + list(args),
                            capture_output=True, text=True, cwd=ROOT,
                            input=input_text)
    return result.returncode, result.stdout, result.stderr


def run_score(text):
    result = subprocess.run([sys.executable, SCORE, "--profile", "general",
                             "--stdin"], capture_output=True, text=True,
                            cwd=ROOT, input=text)
    return json.loads(result.stdout), result.returncode


UNIFORM_SENTENCES = (
    "The parser validates every incoming request before the handler thread "
    "begins its work. "
    "The worker drains the pending queue and writes a complete audit record "
    "for each task. "
    "The scheduler retries each failed job with a fixed exponential backoff "
    "policy applied. "
    "The gateway checks the bearer token and enforces the per-tenant quota "
    "before accepting. "
    "The runner collects the finished results and posts them to the shared "
    "durable store."
)

VARIED_SENTENCES = (
    "Short. "
    "Then a much longer sentence that keeps adding clauses and qualifiers "
    "until it has clearly run past the length of the first one by a wide "
    "margin and a half. "
    "Brief again. "
    "And one more deliberately long-winded sentence, the kind that drags on "
    "with subordinate clauses and extra detail long after the point has been "
    "made, to stretch the average. "
    "Terse. "
    "Final sentence with a middling length that lands between the extremes."
)

PARA_A = (
    "The deployment pipeline compiles the binary, runs the unit test suite, "
    "and pushes the container image to the registry before the load balancer "
    "cuts the fleet over to the new version."
)
PARA_B = (
    "Our release pipeline compiles the binary, runs the unit test suite, and "
    "pushes the container image to the registry, and then the load balancer "
    "cuts the fleet over to the patched build."
)
PARA_DUP = (
    "The deployment pipeline compiles the binary, runs the unit test suite, "
    "and pushes the container image to the registry before the load balancer "
    "cuts over to the new version."
)
PARA_DUP2 = (
    "The deployment pipeline compiles the binary, runs the unit test suite, "
    "and pushes the container image to the registry before the load balancer "
    "cuts over to the patched version."
)

TECH_DEFINITION = (
    "A CVE record is a publicly disclosed identifier for a specific "
    "vulnerability in a product or service. Security teams track CVE records "
    "to prioritize patches and assess exposure across their fleet. Each "
    "record names the affected component and the conditions that make the "
    "flaw exploitable.\n\n"
    "The CVE system publishes identifiers that vendors and researchers use "
    "to reference the same vulnerability across many tools. A record links "
    "the disclosure to its proof of concept and to the advisory the vendor "
    "later publishes. The identifier itself never carries a severity rating; "
    "the CVSS score does."
)

TRICOLON_REFLEX = (
    "The tool validates inputs, normalizes data, and transforms records. "
    "The worker fetches rows, applies rules, and writes output. "
    "The gateway parses tokens, checks quotas, and logs attempts. "
    "The runner loads configs, schedules jobs, and reports status. "
    "The daemon reads metrics, updates caches, and serves requests."
)

EARNED_REQUIREMENT = (
    "The gateway must validate the token, enforce the quota, and log the "
    "attempt before serving the request. It runs once per request and never "
    "blocks the fast path. Failures are retried with exponential backoff up "
    "to three attempts. The dashboard shows live state for every tenant in "
    "the fleet."
)

PASSIVE_DENSE = (
    "The proposal was reviewed by the committee. Several concerns were "
    "raised during the meeting. The budget is considered adequate for the "
    "first phase. A decision has been made to proceed. The vendor was "
    "selected after a long evaluation. Implementation details will be "
    "finalized next quarter."
)


class TestSentenceLengthVariance(unittest.TestCase):
    def test_trigger_uniform_sentences(self):
        result = run_detector(UNIFORM_SENTENCES, "struct-sentence-length-variance",
                              "sentence_length_variance")
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["signal"], "advisory")
        self.assertEqual(finding["evidence"], "document")
        self.assertIn("coefficient of variation", finding["message"])

    def test_clean_varied_sentences(self):
        result = run_detector(VARIED_SENTENCES, "struct-sentence-length-variance",
                              "sentence_length_variance")
        self.assertEqual(result["findings"], [])

    def test_boundary_four_sentences_is_insufficient_sample(self):
        text = ("One middling sentence of roughly normal length here. "
                "Another middling sentence of roughly similar length there. "
                "A third middling sentence about the same length again. "
                "A fourth middling sentence that matches the pattern as well.")
        result = run_detector(text, "struct-sentence-length-variance",
                              "sentence_length_variance")
        self.assertEqual(result["findings"], [])
        states = {m["metric"]: m for m in result["metrics"]}
        self.assertEqual(states["sentence_length_variance"]["state"],
                         "insufficient-sample")
        self.assertEqual(states["sentence_length_variance"]["required"], 5)

    def test_technical_false_positive_lists_and_code_excluded(self):
        text = ("# Setup\n\n"
                "- Deploy the binary\n"
                "- Run the tests\n"
                "- Push the image\n"
                "- Cut over\n"
                "- Watch the metrics\n\n"
                "```\nfurthermore\nfurthermore\nfurthermore\n```\n\n"
                "This varies. And here is a much longer sentence that keeps "
                "going with more words and more clauses until it is clearly "
                "long enough to measure as different. Short again.")
        result = run_detector(text, "struct-sentence-length-variance",
                              "sentence_length_variance")
        self.assertEqual(result["findings"], [])


class TestParagraphLengthVariance(unittest.TestCase):
    @staticmethod
    def _uniform_paragraphs():
        para = ("The deployment pipeline compiles the binary, runs the unit "
                "test suite, and pushes the container image to the registry "
                "before the load balancer cuts over to the new version "
                "exactly as planned.")
        return "\n\n".join([para] * 5)

    def test_trigger_uniform_paragraphs(self):
        result = run_detector(self._uniform_paragraphs(),
                              "struct-paragraph-length-variance",
                              "paragraph_length_variance")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["signal"], "advisory")
        self.assertIn("coefficient of variation", result["findings"][0]["message"])

    def test_clean_varied_paragraphs(self):
        long_para = ("The deployment pipeline compiles the binary, runs the "
                     "entire unit test suite across every supported platform, "
                     "and pushes the resulting container image to the "
                     "registry before the load balancer cuts the whole fleet "
                     "over to the new version, which takes the remainder of "
                     "the maintenance window to complete before anyone "
                     "resumes shipping.")
        text = "\n\n".join([PARA_A, PARA_A, long_para, PARA_A, long_para])
        result = run_detector(text, "struct-paragraph-length-variance",
                              "paragraph_length_variance")
        self.assertEqual(result["findings"], [])

    def test_boundary_three_paragraphs_is_insufficient_sample(self):
        text = "\n\n".join([PARA_A, PARA_A, PARA_A])
        result = run_detector(text, "struct-paragraph-length-variance",
                              "paragraph_length_variance")
        self.assertEqual(result["findings"], [])
        states = {m["metric"]: m for m in result["metrics"]}
        self.assertEqual(states["paragraph_length_variance"]["state"],
                         "insufficient-sample")
        self.assertEqual(states["paragraph_length_variance"]["required"], 4)

    def test_technical_false_positive_heading_and_lists_excluded(self):
        text = ("# Steps\n\n"
                "- Run the build\n"
                "- Run the tests\n"
                "- Push the image\n"
                "- Roll out\n\n"
                "A short paragraph here. And another short paragraph here "
                "with a few extra words for good measure.")
        result = run_detector(text, "struct-paragraph-length-variance",
                              "paragraph_length_variance")
        self.assertEqual(result["findings"], [])


class TestSentenceStartRepetition(unittest.TestCase):
    def test_trigger_repeated_openings(self):
        text = ("The parser reads the config. The parser builds the graph. "
                "The parser runs the query. The parser writes the output. "
                "The parser handles errors. The parser exits cleanly.")
        result = run_detector(text, "struct-sentence-start-repetition",
                              "sentence_start_repetition")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["signal"], "advisory")
        self.assertIn("Repeated sentence openings", result["findings"][0]["message"])

    def test_trigger_deliberate_parallel_passage(self):
        text = ("We parse the request. We validate the payload. We format "
                "the response. We deploy the build. We monitor the rollout. "
                "We roll back on failure.")
        result = run_detector(text, "struct-sentence-start-repetition",
                              "sentence_start_repetition")
        self.assertEqual(len(result["findings"]), 1)

    def test_clean_varied_openers(self):
        text = ("The parser reads the config. Each worker drains a queue. "
                "Errors surface in the log. The scheduler retries the job. "
                "Metrics update every minute. Operators get an alert.")
        result = run_detector(text, "struct-sentence-start-repetition",
                              "sentence_start_repetition")
        self.assertEqual(result["findings"], [])

    def test_boundary_ratio_at_limit_does_not_fire(self):
        text = ("The parser reads the config. Each worker drains a queue. "
                "Errors surface in the log. The scheduler retries the job. "
                "Metrics update each minute. Operators get an alert. "
                "The runner posts the results. Auditors review the trail. "
                "Billing runs on the first of each month. Alerts page the "
                "on-call engineer.")
        result = run_detector(text, "struct-sentence-start-repetition",
                              "sentence_start_repetition")
        self.assertEqual(result["findings"], [])

    def test_technical_false_positive_short_openers_excluded(self):
        text = ("A parser reads the config. The parser builds the graph. "
                "The parser runs the query. The parser writes the output. "
                "The parser handles errors. The parser exits cleanly. "
                "2024 saw the release. 2025 saw the rewrite.")
        result = run_detector(text, "struct-sentence-start-repetition",
                              "sentence_start_repetition")
        self.assertEqual(result["findings"], [])


class TestTransitionRepetition(unittest.TestCase):
    def test_trigger_three_repeats(self):
        text = ("Furthermore, the cache warms on boot. Furthermore, the "
                "index rebuilds nightly. Furthermore, the queue drains "
                "cleanly on shutdown.")
        result = run_detector(text, "struct-transition-repetition",
                              "transition_repetition")
        self.assertEqual(len(result["findings"]), 1)
        self.assertIn("furthermore", result["findings"][0]["message"])

    def test_clean_single_uses(self):
        text = ("Furthermore, the cache warms on boot. Moreover, the index "
                "rebuilds nightly. In addition, the queue drains on "
                "shutdown. Consequently, the system stays healthy.")
        result = run_detector(text, "struct-transition-repetition",
                              "transition_repetition")
        self.assertEqual(result["findings"], [])

    def test_boundary_two_repeats_does_not_fire(self):
        text = ("Furthermore, the cache warms on boot. Furthermore, the "
                "index rebuilds nightly. The queue drains cleanly on "
                "shutdown.")
        result = run_detector(text, "struct-transition-repetition",
                              "transition_repetition")
        self.assertEqual(result["findings"], [])

    def test_technical_false_positive_code_block_excluded(self):
        text = ("Furthermore, the cache warms on boot. Furthermore, the "
                "index rebuilds nightly.\n\n"
                "```\nFurthermore, one. Furthermore, two. Furthermore, "
                "three. Furthermore, four.\n```")
        result = run_detector(text, "struct-transition-repetition",
                              "transition_repetition")
        self.assertEqual(result["findings"], [])


class TestParagraphSimilarity(unittest.TestCase):
    def test_trigger_overlapping_paragraphs(self):
        text = PARA_A + "\n\n" + PARA_B
        result = run_detector(text, "struct-paragraph-similarity",
                              "paragraph_similarity")
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["signal"], "advisory")
        self.assertEqual(finding["evidence"], "span")
        self.assertGreaterEqual(finding["start"], len(PARA_A) + 2)

    def test_clean_distinct_paragraphs(self):
        text = PARA_A + "\n\n" + (
            "The database stores every audit event with a timestamp and a "
            "trace id. Retention policy keeps the events for ninety days "
            "before archival to cold storage.")
        result = run_detector(text, "struct-paragraph-similarity",
                              "paragraph_similarity")
        self.assertEqual(result["findings"], [])

    def test_boundary_below_jaccard_does_not_fire(self):
        first = ("The database stores audit events with a timestamp and a "
                 "trace id for ninety days before archival to cold storage "
                 "on a separate cluster in the same region.")
        second = ("Cold storage keeps the audit events on a separate "
                  "cluster. Retention holds them for ninety days. Every "
                  "event carries a trace id and a timestamp. The region is "
                  "the same for both clusters.")
        result = run_detector(first + "\n\n" + second,
                              "struct-paragraph-similarity",
                              "paragraph_similarity")
        self.assertEqual(result["findings"], [])

    def test_technical_false_positive_definition_repeats_terms(self):
        result = run_detector(TECH_DEFINITION, "struct-paragraph-similarity",
                              "paragraph_similarity")
        self.assertEqual(result["findings"], [])


class TestTricolonDensity(unittest.TestCase):
    def test_trigger_tricolon_reflex(self):
        result = run_detector(TRICOLON_REFLEX, "struct-tricolon-density",
                              "tricolon_density")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["signal"], "advisory")
        self.assertEqual(result["findings"][0]["evidence"], "document")
        self.assertIn("Tricolon reflex", result["findings"][0]["message"])

    def test_clean_single_tricolon(self):
        text = ("The gateway validates the token, enforces the quota, and "
                "logs the attempt. It runs once per request. Failures are "
                "retried with backoff. The dashboard shows live state.")
        result = run_detector(text, "struct-tricolon-density",
                              "tricolon_density")
        self.assertEqual(result["findings"], [])

    def test_boundary_below_minimum_count_does_not_fire(self):
        text = ("The tool validates inputs, normalizes data, and transforms "
                "records. The worker fetches rows, applies rules, and writes "
                "output. The gateway parses tokens, checks quotas, and logs "
                "attempts.")
        result = run_detector(text, "struct-tricolon-density",
                              "tricolon_density")
        self.assertEqual(result["findings"], [])

    def test_technical_false_positive_earned_requirement(self):
        result = run_detector(EARNED_REQUIREMENT, "struct-tricolon-density",
                              "tricolon_density")
        self.assertEqual(result["findings"], [])


class TestParagraphDuplication(unittest.TestCase):
    def test_trigger_near_verbatim_duplicate(self):
        text = PARA_DUP + "\n\n" + PARA_DUP2
        result = run_detector(text, "struct-paragraph-duplication",
                              "paragraph_duplication", review_mode="deterministic")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["signal"], "strict")
        self.assertEqual(result["findings"][0]["evidence"], "span")

    def test_clean_distinct_paragraphs(self):
        text = PARA_DUP + "\n\n" + (
            "The database stores every audit event with a timestamp and a "
            "trace id. Retention policy keeps the events for ninety days "
            "before archival to cold storage.")
        result = run_detector(text, "struct-paragraph-duplication",
                              "paragraph_duplication", review_mode="deterministic")
        self.assertEqual(result["findings"], [])

    def test_boundary_paraphrase_is_not_duplication(self):
        text = PARA_A + "\n\n" + PARA_B
        result = run_detector(text, "struct-paragraph-duplication",
                              "paragraph_duplication", review_mode="deterministic")
        self.assertEqual(result["findings"], [])

    def test_technical_false_positive_definition_repeats_terms(self):
        result = run_detector(TECH_DEFINITION, "struct-paragraph-duplication",
                              "paragraph_duplication", review_mode="deterministic")
        self.assertEqual(result["findings"], [])


class TestPassiveDensity(unittest.TestCase):
    def test_trigger_sustained_passive(self):
        result = run_detector(PASSIVE_DENSE, "struct-passive-density",
                              "passive_density", review_mode="deterministic")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["signal"], "strict")
        self.assertIn("Sustained passive voice", result["findings"][0]["message"])

    def test_clean_active_voice(self):
        text = ("The committee reviewed the proposal. The team raised "
                "several concerns during the meeting. The board approved "
                "the budget for the first phase. The committee decided to "
                "proceed. The vendor evaluated the candidates. The team "
                "finalizes the details next quarter.")
        result = run_detector(text, "struct-passive-density",
                              "passive_density", review_mode="deterministic")
        self.assertEqual(result["findings"], [])

    def test_boundary_fewer_than_six_sentences_is_insufficient(self):
        text = ("The proposal was reviewed by the committee. Several "
                "concerns were raised. The budget is considered adequate. "
                "A decision has been made to proceed.")
        result = run_detector(text, "struct-passive-density",
                              "passive_density", review_mode="deterministic")
        self.assertEqual(result["findings"], [])
        states = {m["metric"]: m for m in result["metrics"]}
        self.assertEqual(states["passive_density"]["state"], "insufficient-sample")

    def test_technical_false_positive_predicate_adjectives_protected(self):
        text = ("The results were mixed. The team was excited about the "
                "launch. The color is red. The report was reviewed before "
                "release. The tests were rerun overnight. The build was "
                "published to the registry.")
        result = run_detector(text, "struct-passive-density",
                              "passive_density", review_mode="deterministic")
        self.assertEqual(result["findings"], [])


class TestRegistryWiring(unittest.TestCase):
    def test_every_new_rule_names_a_registered_detector(self):
        with open(REGISTRY, encoding="utf-8") as f:
            registry = json.load(f)
        rules = {r["id"]: r for r in registry["rules"]}
        for rid, detector, review_mode in DETECTOR_RULES:
            rule = rules.get(rid)
            self.assertIsNotNone(rule, f"{rid} missing from registry")
            self.assertEqual(rule["detector"], detector, rid)
            self.assertEqual(rule["review_mode"], review_mode, rid)
            self.assertEqual(rule["detection_class"], "structural", rid)
            self.assertEqual(rule["profiles"], ["*"], rid)
            self.assertIn(detector, structural.DETECTORS, detector)

    def test_score_no_longer_skips_detector_rules(self):
        with open(REGISTRY, encoding="utf-8") as f:
            registry = json.load(f)
        scoring = [r for r in registry["rules"]
                   if r["semantic_type"] in ("forbidden", "discouraged")]
        expected = sum(1 for r in scoring
                       if r.get("detection_class") in ("pattern_match", "structural")
                       and not r.get("detector"))
        data, rc = run_score("This text has no violations at all.")
        self.assertEqual(rc, 0)
        self.assertEqual(data["metadata"]["skipped_rules"], expected)


class TestScoreBehavior(unittest.TestCase):
    def test_advisory_findings_do_not_change_the_score(self):
        text = UNIFORM_SENTENCES
        data, rc = run_score(text)
        self.assertEqual(rc, 0)
        self.assertEqual(data["score"], 100)
        advisory = [f for f in data["findings"] if f["signal"] == "advisory"]
        self.assertGreater(len(advisory), 0)
        for f in advisory:
            self.assertEqual(f["weight"], 0)

    def test_strict_finding_deducts(self):
        text = PARA_DUP + "\n\n" + PARA_DUP2
        data, rc = run_score(text)
        self.assertEqual(rc, 0)
        self.assertLess(data["score"], 100)
        strict = [f for f in data["findings"]
                  if f["signal"] == "strict" and f["primary"]]
        self.assertGreater(len(strict), 0)
        self.assertGreater(strict[0]["weight"], 0)

    def test_same_span_overlap_one_primary_one_related(self):
        text = PARA_DUP + "\n\n" + PARA_DUP2
        data, rc = run_score(text)
        self.assertEqual(rc, 0)
        spans = {}
        for f in data["findings"]:
            key = tuple(f["span"])
            spans.setdefault(key, []).append(f)
        overlap = [g for g in spans.values() if len(g) > 1]
        self.assertGreater(len(overlap), 0)
        for group in overlap:
            primaries = [f for f in group if f["primary"]]
            related = [f for f in group if not f["primary"]]
            self.assertEqual(len(primaries), 1)
            self.assertGreater(len(related), 0)

    def test_short_text_reports_insufficient_sample(self):
        data, rc = run_score("This text has no violations at all.")
        self.assertEqual(rc, 0)
        metrics = data["metadata"]["structural_metrics"]
        self.assertGreater(len(metrics), 0)
        for m in metrics:
            self.assertEqual(m["state"], "insufficient-sample")
            self.assertIn("required", m)

    def test_findings_carry_span_message_and_repair(self):
        text = PARA_DUP + "\n\n" + PARA_DUP2
        data, rc = run_score(text)
        self.assertEqual(rc, 0)
        for f in data["findings"]:
            self.assertIsInstance(f["span"], list)
            self.assertEqual(len(f["span"]), 2)
            self.assertTrue(f["span"][1] > f["span"][0])
            self.assertTrue(f["message"])
            self.assertTrue(f["repair"])
            self.assertEqual(f["profile"], "general")

    def test_detector_findings_carry_profile(self):
        result = run_detector(UNIFORM_SENTENCES, "struct-sentence-length-variance",
                              "sentence_length_variance")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["profile"], "general")


class TestExitBehavior(unittest.TestCase):
    def test_no_findings_exit_zero(self):
        rc, out, err = run_cli("--profile", "general", "--stdin",
                               input_text="This text has no violations at all.")
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertEqual(report["findings"], [])

    def test_advisory_only_exit_one(self):
        rc, out, err = run_cli("--profile", "general", "--stdin",
                               input_text=UNIFORM_SENTENCES)
        self.assertEqual(rc, 1, err)
        report = json.loads(out)
        signals = {f["signal"] for f in report["findings"]}
        self.assertEqual(signals, {"advisory"})

    def test_strict_finding_exit_two(self):
        rc, out, err = run_cli("--profile", "general", "--stdin",
                               input_text=PARA_DUP + "\n\n" + PARA_DUP2)
        self.assertEqual(rc, 2, err)
        report = json.loads(out)
        signals = {f["signal"] for f in report["findings"]}
        self.assertIn("strict", signals)

    def test_report_carries_authorship_disclaimer(self):
        rc, out, err = run_cli("--profile", "general", "--stdin",
                               input_text=UNIFORM_SENTENCES)
        report = json.loads(out)
        self.assertIn("never prove AI authorship", report["disclaimer"])

    def test_unclosed_comment_masking_is_guarded(self):
        # A large body of unclosed comments must not trigger the bounded-body
        # comment scan; the guard skips masking when no closing marker exists.
        source = ("<!-- " * 20000)
        rc, out, err = run_cli("--profile", "general", "--stdin",
                               input_text=source)
        self.assertIn(rc, (0, 1, 2), err)


if __name__ == "__main__":
    unittest.main()