#!/usr/bin/env python3
"""Clarity-style author gaps and review statuses (issue #96).

A review-only runner that reports findings on a single artifact without ever
editing it, modeled on addyosmani/clarity at 9e30711 (MIT). Review reuses
edit.py's audit authority: report findings, produce no rewritten passage or
file change. Every finding carries exactly one of five statuses:

  keep        the pattern is present but earned, required by the medium, or
              preferable to the alternatives
  revise      the source already contains enough material for an honest
              improvement
  ask-author  the improvement needs a fact, mechanism, example, opinion, or
              experience the source does not supply; ask with a
              '[TK: ...]' marker or a direct question, never invent it
  cut         the passage adds only repetition, ceremony, unsupported
              emphasis, or closure
  no-finding  the prose already performs its job

Author-owned gaps (facts, experience, opinion, motive) become targeted
questions, never generated content. Mechanism checks distinguish an
unsupported significance claim from an evidenced consequence by testing for a
nearby mechanism, actor, result, or limit. Medium routing changes structural
expectations (a reference page earns predictable headings; an evocation earns
sensory balance) without weakening absolute rules: banned words and em-dashes
are findings in every medium. Descriptive statistics stay separate from the
advisory risk score, and a voice sample transfers style only, never personal
facts.

Usage:
    python3 review.py --source-text "..." --medium argument
    python3 review.py --fixtures skills/antislop/evals/clarity-review-fixtures.json
    python3 review.py --help

Exit codes:
    0 -- the review ran, or every fixture decision matched its expectation
    1 -- a fixture decision failed
    2 -- usage or input error
"""

import argparse
import collections
import json
import os
import re
import sys

import limits
from findings import short_excerpt as _short_excerpt

from registry import load_registry
import density
import drift
import edit
import fidelity
import mechanism
import score as scoring

STATUSES = ("keep", "revise", "ask-author", "cut", "no-finding")
STATUS_WEIGHT = {"no-finding": 0, "keep": 1, "revise": 2, "cut": 3,
                 "ask-author": 4}
MEDIUMS = ("argument", "explanation", "evocation", "narrative", "guide",
           "reference", "message")
PROFILES = {"general", "technical"}

DISCLAIMER = (
    "Review results report statuses and author gaps; they never prove "
    "AI authorship or detector immunity."
)

TK_RE = re.compile(r"\[TK:[^\]]*\]")

VAGUE_EXAMPLE_RE = re.compile(
    r"\b(?:a|one|some|several|many)\s+"
    r"(?:client|customer|team|company|vendor|startup|organization|package|"
    r"incident|deployment|release|project|meeting|user|developer|product)\b"
    r"[^.\n]{0,80}?"
    r"\b(?:once|caused|had|experienced|saw|suffered|faced|reported|"
    r"learned|taught|happened)\b",
    re.IGNORECASE,
)

EMPTY_SIGNIFICANCE_RE = re.compile(
    r"\b(?:this|it|that)\s+(?:matters|is important|is significant|is crucial|"
    r"is the key|underscores|highlights)\b"
    r"|\bthe stakes are high\b"
    r"|\beverything is connected\b"
    r"|\bthis\s+(?:taught|shows?|proves?|means)\b",
    re.IGNORECASE,
)

GAP_QUESTIONS = {
    "vague_example": (
        "[TK: which subject? what happened, and how was it caught or "
        "measured?]"
    ),
    "empty_significance":
        "[TK: what specifically changed or matters, and to whom?]",
}

MECHANISM_QUESTIONS = {
    "importance": (
        "[TK: what is the mechanism, and what evidence supports this "
        "significance?]"
    ),
    "impact": "[TK: what is the measured result or limit behind this impact?]",
    "causality": (
        "[TK: what is the cause, and what measured result supports it?]"
    ),
    "superiority": (
        "[TK: what is the basis of comparison or the measured result?]"
    ),
}

# Rules whose passages add only ceremony, repetition, or closure: cut.
CUT_RULES = {
    "phrase-worth-noting", "phrase-at-core", "phrase-dive-in",
    "phrase-transition-glue", "phrase-complexity-signal",
    "phrase-discovery-narration", "phrase-in-conclusion",
    "phrase-let-sink-in", "phrase-make-no-mistake", "phrase-let-me-clear",
    "phrase-heres-thing", "phrase-hint-plot-spoiler", "phrase-think-about-it",
    "filler-in-order", "filler-due-to-fact", "filler-at-point-in-time",
    "filler-system-ability", "filler-important-note", "filler-crucial",
    "filler-padding-adverbs", "chatbot-hope-helps", "chatbot-let-me-know",
    "chatbot-great-question", "chatbot-certainly-absolutely",
    "chatbot-cutoff-disclaimers", "struct-announce-structure",
    "struct-transition-glue", "struct-complexity-signalling",
    "struct-discovery-narration", "struct-wisdom-sandwich",
    "struct-punchy-closure", "struct-ending-cliches", "struct-synonym-cycling",
    "struct-rule-of-three", "struct-bullet-crutch",
    "struct-listicle-trenchcoat", "struct-catalog-prose",
    "struct-system-tour", "struct-triplet-overlap", "fmt-emoji-bullets",
}

# Structural expectations relaxed by medium: the same structure is earned in
# one medium and a defect in another. Absolute rules (vocabulary, formatting,
# em-dashes) are never relaxed.
MEDIUM_RELAX = {
    "evocation": {"struct-antithesis", "struct-balanced-take",
                  "struct-all-same-length", "mechanism-importance",
                  "mechanism-impact", "mechanism-superiority"},
    "narrative": {"struct-antithesis", "struct-all-same-length",
                  "mechanism-causality"},
    "reference": {"struct-fragmented-headers", "struct-template-headings"},
    "guide": {"struct-fragmented-headers", "struct-listicle-trenchcoat",
              "struct-template-headings"},
    "explanation": {"struct-template-headings"},
    "message": set(),
    "argument": set(),
}

WORD_RE = re.compile(r"[A-Za-z0-9']+")
HEADING_RE = re.compile(r"(?m)^#{1,6}\s+[^\n]+$")
EM_DASH_RE = re.compile(r"\u2014|\u2013| -- ")


def em_dash_findings(text, rule):
    """Absolute rule, never relaxed by medium: zero em-dashes, en-dashes, or
    double hyphens in any review."""
    findings = []
    for match in EM_DASH_RE.finditer(text):
        findings.append({
            "status": "revise",
            "rule_id": rule["id"],
            "pattern": rule.get("text", "Em-dash, en-dash, or double hyphen"),
            "excerpt": text[max(0, match.start() - 20):
                            min(len(text), match.end() + 20)].strip(),
            "why": "The em-dash rule is absolute and applies in every medium.",
            "suggestion": rule.get("correction", "Replace with a period or "
                                                     "comma and break the "
                                                     "sentence."),
        })
    return findings


def _word_set(text):
    return set(WORD_RE.findall(text.lower()))


def _quoted_spans(text):
    return [{"start": match.start(), "end": match.end()}
            for match in fidelity.QUOTED_RE.finditer(text)]


def _overlaps(span, start, end):
    return span["start"] < end and start < span["end"]


def _overlaps_any(start, end, spans):
    return any(span["start"] < end and start < span["end"] for span in spans)


def detect_fragmented_headers(text):
    """A heading immediately restated by the prose that follows it.

    Deterministic and medium-sensitive: reference and guide pages earn
    predictable heading-plus-first-line pairs, argument pages treat them as a
    structural defect.
    """
    findings = []
    for match in HEADING_RE.finditer(text):
        heading_words = _word_set(re.sub(r"^#{1,6}\s*", "", match.group(0)))
        if not heading_words:
            continue
        after = text[match.end():match.end() + 200].lstrip("\n")
        first_line = after.split("\n\n")[0][:140]
        sentence_words = _word_set(first_line)
        shared = 0
        for word in heading_words:
            if len(word) < 4:
                continue
            if any(candidate.startswith(word) or word.startswith(candidate)
                   for candidate in sentence_words):
                shared += 1
        if shared and shared / len(heading_words) >= 0.5:
            findings.append({
                "start": match.start(), "end": match.end(),
                "heading": match.group(0).strip(),
                "restatement": first_line.strip(),
            })
    return findings


def detect_author_gaps(text):
    """Author-owned material the source does not supply, as [TK] questions.

    A vague example has the grammar of a story and no specific content; an
    empty significance claim asserts importance without saying what changed.
    Both become targeted questions, never invented detail.
    """
    gaps = []
    for match in VAGUE_EXAMPLE_RE.finditer(text):
        gaps.append({
            "kind": "vague_example", "rule_id": "struct-specificity-theater",
            "start": match.start(), "end": match.end(),
            "excerpt": match.group(0).strip(),
            "tk": GAP_QUESTIONS["vague_example"],
        })
    for match in EMPTY_SIGNIFICANCE_RE.finditer(text):
        gaps.append({
            "kind": "empty_significance",
            "rule_id": "struct-empty-declaratives",
            "start": match.start(), "end": match.end(),
            "excerpt": match.group(0).strip(),
            "tk": GAP_QUESTIONS["empty_significance"],
        })
    gaps.sort(key=lambda gap: gap["start"])
    return gaps


def mechanism_entries(text, registry):
    """Per-signal mechanism records: evidenced consequence or unsupported claim."""
    rules = {rule["id"]: rule for rule in registry.get("rules", [])
             if rule["category"] == "mechanism"}
    entries = []
    for rule_id, rule in sorted(rules.items()):
        kind = rule_id.split("-", 1)[1]
        pattern = mechanism.SIGNAL_RE.get(kind)
        if pattern is None:
            continue
        for match in pattern.finditer(text):
            entries.append({
                "rule_id": rule_id, "kind": kind,
                "token": match.group(0), "start": match.start(),
                "end": match.end(),
                "evidenced": mechanism._nearby_evidence(
                    text, match.start(), match.end()),
                "pattern": rule.get("text", ""),
            })
    entries.sort(key=lambda entry: entry["start"])
    return entries


def _status_for_mechanism(entry, medium):
    if medium in ("evocation", "narrative"):
        return "keep"
    return "keep" if entry["evidenced"] else "ask-author"


def assign_status(rule, start, end, medium, quoted_spans):
    """One explicit status per finding."""
    if rule is None:
        return "revise"
    if _overlaps_any(start, end, quoted_spans):
        return "keep"
    rule_id = rule["id"]
    if rule["semantic_type"] == "forbidden" \
            and rule.get("review_mode") == "deterministic":
        if rule["category"] in ("filler", "chatbot") or rule_id in CUT_RULES:
            return "cut"
        return "revise"
    if rule_id in CUT_RULES or rule["category"] in ("filler", "chatbot"):
        return "cut"
    if rule_id in MEDIUM_RELAX.get(medium, ()):
        return "keep"
    if rule["category"] == "formatting":
        return "revise"
    return "revise"


def _reason_for(rule, status):
    if status == "cut":
        return ("The passage adds only repetition, ceremony, unsupported "
                "emphasis, or closure.")
    if status == "keep":
        return ("The pattern is quoted material, earned by context, or "
                "required by the medium.")
    if status == "ask-author":
        return ("The improvement needs author-owned material the source does "
                "not supply.")
    return ("Deterministic banned pattern; the source can support an honest "
            "improvement.")


def _suggestion_for(rule, status):
    if status == "cut":
        return "Cut it, or keep only what the passage needs."
    if status == "keep":
        return "Keep as-is."
    return rule.get("correction", "") if rule else "Rewrite the passage."


def check_medium(medium, text, registry):
    """Structural expectations for a medium, deterministically checked.

    The check changes which structure is a defect and which is a feature, so
    the same structure can earn keep in one medium and revise in another.
    Absolute rules are never relaxed.
    """
    expectations = registry.get("mediums", {}).get(medium, {})
    checks = []
    headers = detect_fragmented_headers(text)
    if headers:
        expected = "earned" if medium in ("reference", "guide") else "defect"
        checks.append({
            "kind": "fragmented_headers",
            "medium": medium,
            "expectation": expected,
            "count": len(headers),
            "status": "keep" if expected == "earned" else "revise",
            "spans": headers,
        })
    checks.append({
        "kind": "optimize", "medium": medium,
        "value": expectations.get("optimize", ""),
    })
    checks.append({
        "kind": "preserve", "medium": medium,
        "value": expectations.get("preserve", ""),
    })
    return checks


def check_voice_sample(voice_sample, source, sample_facts=()):
    """Voice samples transfer style only; personal facts must not migrate."""
    leaked = [fact for fact in sample_facts
              if drift.contains_fact(source, fact)]
    findings = []
    for fact in leaked:
        findings.append({
            "status": "revise",
            "rule_id": "evaluation-voice-sample",
            "pattern": "Voice sample personal fact in the target",
            "excerpt": fact,
            "why": "The draft carries a personal fact from the voice sample; "
                   "a sample transfers style only.",
            "suggestion": "Replace with the author's own experience or cut "
                          "the detail.",
        })
    return {
        "provided": bool(voice_sample),
        "sample_facts": list(sample_facts),
        "leaked_personal_facts": leaked,
        "style_only": True,
        "findings": findings,
    }


def descriptive_stats(text, findings):
    words = WORD_RE.findall(text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()] or [text]
    sentence_words = [len(WORD_RE.findall(sentence))
                      for sentence in sentences]
    average = sum(sentence_words) / len(sentence_words)
    unique = len({word.lower() for word in words}) / len(words) if words else 0
    by_status = collections.Counter(f["status"] for f in findings)
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "avg_words_per_sentence": round(average, 2),
        "unique_word_ratio": round(unique, 3),
        "finding_count": len(findings),
        "by_status": dict(by_status),
    }


def _overall_decision(findings):
    if not findings:
        return "no-finding"
    statuses = [finding["status"] for finding in findings]
    return max(statuses, key=lambda status: STATUS_WEIGHT[status])


def review_text(text, medium, registry, profile="general",
                voice_sample=None, sample_facts=()):
    """Review a single artifact without editing it.

    Returns a JSON-serializable report. The report never contains a rewritten
    passage: missing author material becomes a '[TK: ...]' question, and the
    overall status falls back to the strongest finding present.
    """
    limits.check_input_size(text)
    if medium not in MEDIUMS:
        raise ValueError("unknown medium %r" % medium)

    rules = registry.get("rules", [])
    rule_by_id = {rule["id"]: rule for rule in rules}
    mechanism_ids = {rule["id"] for rule in rules
                     if rule["category"] == "mechanism"}

    scored, _skipped, _metrics = scoring.detect_findings(text, registry, profile)
    scored = [finding for finding in scored
              if finding["rule_id"] not in mechanism_ids]
    scored = scoring.handle_overlaps(scored)

    gaps = detect_author_gaps(text)
    quoted_spans = _quoted_spans(text)

    findings = []
    for finding in scored:
        rule = rule_by_id.get(finding["rule_id"])
        status = assign_status(
            rule, finding["position"],
            finding["position"] + finding.get("match_length", 6),
            medium, quoted_spans)
        findings.append({
            "status": status,
            "rule_id": finding["rule_id"],
            "pattern": (rule.get("text", "") if rule else
                        finding.get("message", "")),
            "excerpt": finding.get("excerpt", ""),
            "why": _reason_for(rule, status),
            "suggestion": _suggestion_for(rule, status),
        })

    for finding in findings:
        if finding["rule_id"] != "struct-unsourced-precision":
            continue
        finding["status"] = "ask-author"
        finding["why"] = ("The figure is exact and carries no nearby source, "
                          "supplied fact, estimate, or technical-constant "
                          "framing. The review never declares the number "
                          "false.")
        finding["suggestion"] = "[TK: what is the source for this figure?]"
        finding["tk"] = "[TK: what is the source for this figure?]"

    for entry in mechanism_entries(text, registry):
        status = _status_for_mechanism(entry, medium)
        if status == "ask-author":
            suggestion = MECHANISM_QUESTIONS[entry["kind"]]
        else:
            suggestion = ("Keep; the passage names the mechanism, actor, "
                          "result, or limit that earns the claim.")
        why = ("The claim names no mechanism, actor, result, or limit "
               "nearby." if status == "ask-author"
               else "The claim is supported by a nearby mechanism or "
                    "measured result.")
        item = {
            "status": status,
            "rule_id": entry["rule_id"],
            "kind": entry["kind"],
            "pattern": entry["pattern"],
            "excerpt": _short_excerpt(text, entry["start"], entry["end"]),
            "why": why,
            "suggestion": suggestion,
        }
        if status == "ask-author":
            item["tk"] = MECHANISM_QUESTIONS[entry["kind"]]
        findings.append(item)

    for gap in gaps:
        if any(_overlaps(gap, finding["position"],
                         finding["position"] + finding.get("match_length", 6))
               for finding in scored):
            continue
        rule = rule_by_id.get(gap["rule_id"])
        findings.append({
            "status": "ask-author",
            "rule_id": gap["rule_id"],
            "kind": gap["kind"],
            "pattern": rule.get("text", "") if rule else gap["kind"],
            "excerpt": gap["excerpt"],
            "why": ("The example has the grammar of a specific story and no "
                    "specific content." if gap["kind"] == "vague_example"
                    else "The claim asserts significance without saying what "
                         "changed or for whom."),
            "suggestion": gap["tk"],
            "tk": gap["tk"],
        })

    medium_checks = check_medium(medium, text, registry)
    for check in medium_checks:
        if check["kind"] != "fragmented_headers":
            continue
        rule = rule_by_id.get("struct-fragmented-headers")
        for span in check["spans"]:
            findings.append({
                "status": check["status"],
                "rule_id": "struct-fragmented-headers",
                "pattern": rule.get("text", "Fragmented headers") if rule
                           else "Fragmented headers",
                "excerpt": _short_excerpt(text, span["start"], span["end"]),
                "why": ("A heading immediately restated by its first line is "
                        "earned in this medium." if check["status"] == "keep"
                        else "A heading immediately restated by its first "
                             "line weakens the argument."),
                "suggestion": ("Keep; predictable structure serves this "
                               "medium." if check["status"] == "keep"
                               else "Merge the heading and its restatement "
                                    "into one point."),
            })

    voice = check_voice_sample(voice_sample, text, sample_facts)
    findings.extend(voice["findings"])

    em_dash_rule = rule_by_id.get("fmt-em-dash")
    if em_dash_rule is not None:
        findings.extend(em_dash_findings(text, em_dash_rule))

    findings.sort(key=lambda finding: (finding.get("excerpt", ""),
                                       finding["rule_id"]))

    author_questions = []
    for finding in findings:
        if finding.get("tk"):
            author_questions.append({
                "tk": finding["tk"],
                "rule_id": finding["rule_id"],
                "excerpt": finding.get("excerpt", ""),
            })

    overall = _overall_decision(findings)

    risk = {}
    try:
        risk_result = scoring.score_text(text, registry, profile)
        risk = {
            "score": risk_result["score"],
            "band": risk_result["band"],
            "advisory": True,
            "authorship_evidence": False,
            "disclaimer": drift.OBSERVATION_DISCLAIMER,
        }
    except Exception:  # noqa: BLE001 -- risk is advisory, never a gate
        risk = {"score": None, "band": None, "advisory": True,
                "authorship_evidence": False,
                "disclaimer": drift.OBSERVATION_DISCLAIMER}

    integrity_defects = edit.integrity_defects(text)

    return {
        "interface": "antislop.review",
        "schema": "clarity-review-report-1",
        "version": registry.get("version", "unknown"),
        "mode": "review",
        "medium": medium,
        "profile": profile,
        "edited": False,
        "decision": overall,
        "overall": overall,
        "statuses": {status: count for status, count
                     in collections.Counter(
                         finding["status"] for finding in findings).items()},
        "findings": findings,
        "author_questions": author_questions,
        "mechanism_checks": {
            "unsupported": [f for f in findings
                            if f.get("kind") in MECHANISM_QUESTIONS
                            and f["status"] == "ask-author"],
            "evidenced": [f for f in findings
                          if f.get("kind") in MECHANISM_QUESTIONS
                          and f["status"] == "keep"],
        },
        "precision_checks": {
            "considered": density.precision_entries(text, profile, registry),
            "unsupported": [f for f in findings
                            if f["rule_id"] == "struct-unsourced-precision"],
        },
        "medium_checks": medium_checks,
        "voice_sample": voice,
        "output_integrity": {
            "defects": integrity_defects,
            "tk_markers": [defect for defect in integrity_defects
                           if defect["kind"] == "placeholder"
                           and defect["value"].startswith("[TK")],
        },
        "descriptive_stats": descriptive_stats(text, findings),
        "risk": risk,
        "meta": {
            "disclaimer": DISCLAIMER,
            "authority": edit.OPERATIONS["audit"]["authority"],
            "false_positive_rationale": None,
            "reviewer_notes": None,
            "horoscope_test": density.HOROSCOPE_NOTE,
        },
    }


def validate_review_fixture(fixture, seen_ids):
    """Schema-validate one clarity-review fixture. Returns error strings."""
    errors = []
    if not isinstance(fixture, dict):
        return ["fixture must be a JSON object"]
    fid = fixture.get("id")
    if not isinstance(fid, str) or not fid.strip():
        errors.append("fixture missing non-empty string 'id'")
    else:
        if fid in seen_ids:
            errors.append("duplicate fixture id '%s'" % fid)
        seen_ids.add(fid)

    where = "fixture '%s'" % (fid if fid else "?")

    source = fixture.get("source")
    if not isinstance(source, str) or not source.strip():
        errors.append("%s: 'source' must be a non-empty string" % where)

    medium = fixture.get("medium")
    if medium not in MEDIUMS:
        errors.append("%s: medium must be one of %s"
                      % (where, ", ".join(MEDIUMS)))

    expected = fixture.get("expected_decision")
    if expected not in STATUSES:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(STATUSES)))

    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(sorted(PROFILES))))

    statuses = fixture.get("expected_statuses", {})
    if not isinstance(statuses, dict):
        errors.append("%s: expected_statuses must be an object" % where)
    else:
        for rule_id, status in statuses.items():
            if not (isinstance(rule_id, str) and rule_id.strip()):
                errors.append("%s: expected_statuses keys must be non-empty "
                              "strings" % where)
            if status not in STATUSES:
                errors.append("%s: expected_statuses['%s'] must be one of %s"
                              % (where, rule_id, ", ".join(STATUSES)))

    questions = fixture.get("expected_author_questions", [])
    if not isinstance(questions, list):
        errors.append("%s: expected_author_questions must be a list" % where)
    else:
        for i, question in enumerate(questions):
            if not (isinstance(question, str) and question.strip()):
                errors.append("%s: expected_author_questions[%d] must be a "
                              "non-empty string" % (where, i))

    sample = fixture.get("voice_sample")
    if sample is not None and (not isinstance(sample, str) or not sample.strip()):
        errors.append("%s: voice_sample must be a non-empty string" % where)

    facts = fixture.get("sample_facts", [])
    if not isinstance(facts, list):
        errors.append("%s: sample_facts must be a list" % where)
    else:
        for i, fact in enumerate(facts):
            if not (isinstance(fact, str) and fact.strip()):
                errors.append("%s: sample_facts[%d] must be a non-empty "
                              "string" % (where, i))

    if not isinstance(fixture.get("no_invention", False), bool):
        errors.append("%s: no_invention must be a boolean" % where)

    rationale = fixture.get("false_positive_rationale")
    if rationale is not None and (not isinstance(rationale, str)
                                  or not rationale.strip()):
        errors.append("%s: false_positive_rationale must be a non-empty "
                      "string" % where)

    notes = fixture.get("reviewer_notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append("%s: reviewer_notes must be a non-empty string" % where)
    return errors


def fixture_failures(report, fixture):
    """Compare a computed report against its fixture expectations."""
    failures = []
    if report["decision"] != fixture["expected_decision"]:
        failures.append("expected decision %s, got %s"
                        % (fixture["expected_decision"], report["decision"]))
    findings_by_rule = {}
    for finding in report["findings"]:
        findings_by_rule.setdefault(finding["rule_id"], finding)
    for rule_id, status in (fixture.get("expected_statuses", {}) or {}).items():
        finding = findings_by_rule.get(rule_id)
        if finding is None:
            failures.append("rule '%s' has no finding (expected status %s)"
                            % (rule_id, status))
        elif finding["status"] != status:
            failures.append("rule '%s' expected status %s, got %s"
                            % (rule_id, status, finding["status"]))
    question_texts = [finding.get("tk", "") for finding in report["findings"]]
    question_texts += [item["tk"] for item in report["author_questions"]]
    for question in fixture.get("expected_author_questions", []):
        if not any(question in text for text in question_texts):
            failures.append("missing author question containing %r" % question)
    if fixture.get("no_invention"):
        for finding in report["findings"]:
            if finding["status"] != "ask-author":
                continue
            suggestion = finding.get("suggestion", "")
            if not re.search(r"\[TK:|Ask the author|ask the author|\bcut\b|"
                             r"fallback", suggestion, re.IGNORECASE):
                failures.append("ask-author suggestion '%s' invents content"
                                % suggestion)
    return failures


def run_review_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one clarity-review fixture against its report expectations."""
    fid = fixture["id"]
    medium = fixture["medium"]
    report = review_text(
        fixture["source"], medium, registry,
        profile=fixture.get("profile", "general"),
        voice_sample=fixture.get("voice_sample"),
        sample_facts=tuple(fixture.get("sample_facts", [])),
    )
    report["id"] = fid
    report["expected_decision"] = fixture["expected_decision"]
    report["meta"]["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
    report["failures"] = fixture_failures(report, fixture)
    return report


def run_review_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the clarity-review fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_review_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "interface": "antislop.review",
            "schema": "clarity-review-report-1",
            "version": registry.get("version", "unknown"),
            "fixture_count": len(fixtures),
            "passed": 0,
            "failed": len(fixtures),
            "failing_ids": [fixture.get("id", "?") for fixture in fixtures],
            "schema_errors": schema_errors,
            "gate_pass": False,
            "disclaimer": DISCLAIMER,
            "fixtures": [],
        }

    reports = [run_review_fixture(fixture, registry,
                                  registry_path=registry_path)
               for fixture in fixtures]
    failed = [report for report in reports if report["failures"]]
    return {
        "interface": "antislop.review",
        "schema": "clarity-review-report-1",
        "version": registry.get("version", "unknown"),
        "fixture_count": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "failures": [{
            "id": report["id"],
            "medium": report["medium"],
            "expected": report["expected_decision"],
            "got": report["decision"],
            "findings": report["failures"],
        } for report in failed],
        "schema_errors": schema_errors,
        "gate_pass": not schema_errors and not failed,
        "disclaimer": DISCLAIMER,
        "fixtures": reports,
    }


def load_json(path):
    return limits.load_json_file(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-text", default=None,
                        help="Text to review (single artifact, never edited)")
    parser.add_argument("--medium", default="argument",
                        help="Medium routing: one of %s (default: argument)"
                             % ", ".join(MEDIUMS))
    parser.add_argument("--fixtures",
                        default="skills/antislop/evals/"
                                "clarity-review-fixtures.json",
                        help="Path to the clarity-review fixture corpus")
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Print a compact JSON report")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    if args.expect_version and registry.get("version") != args.expect_version:
        print(json.dumps({
            "error": "registry version %s does not match --expect-version %s"
                     % (registry.get("version"), args.expect_version),
        }, indent=2))
        sys.exit(2)

    if args.source_text is not None:
        try:
            source_text = limits.check_input_size(args.source_text)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
        report = review_text(source_text, args.medium, registry)
        report["meta"]["disclaimer"] = DISCLAIMER
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0)

    if not os.path.exists(args.fixtures):
        print(json.dumps({"error": "fixture corpus not found: %s"
                          % args.fixtures}, indent=2))
        sys.exit(2)

    fixtures = load_json(args.fixtures)
    report = run_review_corpus(fixtures.get("evals", fixtures), registry,
                               args.registry)
    print(json.dumps(report, indent=2 if not args.as_json else None,
                     sort_keys=args.as_json))
    sys.exit(0 if report["gate_pass"] else 1)


if __name__ == "__main__":
    main()
