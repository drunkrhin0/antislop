#!/usr/bin/env python3
"""Sepia-style operation and venue routing (issue #94).

A standard-library runner reviewed against Nanako0129/sepia at 361e82e
(MIT). Antislop's general and technical profiles do not capture the
different jobs performed by review, refactor, recreate, or venue-specific
prose. This runner adds three operations on top of edit.py's operation
authority and routes structural expectations by venue.

Operations:
  review    -- diagnose only, never edits. Every finding carries a quoted
               span, rule, status, and reason. Statuses are the Antislop
               keep / revise / ask-author / cut set plus Sepia's n/a (a
               structural feature does not apply to the venue) and
               over-correction (applying the rule would flatten valid voice
               or structure).
  refactor  -- lists the full finding set first, then applies only the
               accepted minimal edits and reports the rejected and
               unresolved findings.
  recreate  -- extracts facts, claims, quotes, intent, and constraints from
               the source, then verifies a freshly drafted candidate keeps
               them.

Venue routing changes which structural features apply: a postmortem must
keep a timeline, impact, contributing factors, and honest uncertainty; a
ticket must keep reproduction steps and acceptance conditions; a developer
reply must lead with the verified action and its caveat; a release note
must ground every claim in the supplied changes. Fiction is an explicit
opt-in profile, never a venue, and its guidance cannot affect general or
technical scoring.

The question-under-discussion review asks whether each paragraph advances
one implicit question and whether the sequence ends in an unearned
reflection tail. The paragraph question check stays human-review structural
guidance; the reflection tail has an exact deterministic condition (the
final paragraph opens with a generic reflection marker after at least one
earlier paragraph) and is a deterministic finding.

Reused machinery: edit.py (operations, inventory), review.py (statuses,
author gaps, mechanism checks), repair.py (literal replacements, protected
regions, apply_edits), fidelity.py (protected spans), drift.py (fact
matching), density.py (precision, horoscope note).

Usage:
    python3 tools/sepia.py --fixtures skills/antislop/evals/sepia-routing-fixtures.json
    python3 tools/sepia.py review --source-text "..." --venue ticket
    python3 tools/sepia.py review --source-text "..." --fiction
    python3 tools/sepia.py refactor --source-text "..." --venue ticket --accept vocab-utilize=use
    python3 tools/sepia.py recreate --source-text "..." --candidate "..." --venue postmortem

Exit codes:
    0 -- the run succeeded, or every fixture decision matched its expectation
    1 -- a fixture decision failed
    2 -- usage or input error
"""

import argparse
import collections
import json
import os
import re
import sys
from findings import short_excerpt as _short_excerpt

import limits
from registry import load_registry
import density
import drift
import edit
import fidelity
import repair
import review
import score as scoring

INTERFACE = "antislop.sepia-routing"
SCHEMA = "sepia-routing-report-1"
FIXTURE_SCHEMA = "sepia-routing-fixtures-1"
OPERATIONS = ("review", "refactor", "recreate")
VENUES = ("ticket", "developer-reply", "postmortem", "technical-article",
          "release-note")
STATUSES = ("keep", "revise", "ask-author", "cut", "n/a", "over-correction")
REVIEW_DECISIONS = ("no-finding", "keep", "over-correction", "revise", "cut",
                    "ask-author")
REFACTOR_DECISIONS = ("applied", "no-change", "rejected")
RECREATE_DECISIONS = ("accept", "reject")
PROFILES = ("general", "technical", "fiction")

STATUS_WEIGHT = {"n/a": 0, "no-finding": 0, "keep": 1, "over-correction": 1,
                 "revise": 2, "cut": 3, "ask-author": 4}

DISCLAIMER = (
    "Sepia-style routing reports operations, venues, and preservation; it "
    "never proves AI authorship or detector immunity."
)

WORD_RE = re.compile(r"[A-Za-z0-9']+")

# --------------------------------------------------------------------------
# Venue feature detectors (deterministic conditions).
# --------------------------------------------------------------------------

FEATURE_PATTERNS = {
    "timeline": re.compile(
        r"\b\d{1,2}:\d{2}\b"
        r"|\b\d{4}-\d{2}-\d{2}\b"
        r"|\b\d{1,2}\s*(?:am|pm)\b"
        r"|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        re.IGNORECASE,
    ),
    "impact": re.compile(
        r"\b\d+(?:\.\d+)?\s*%(?!\w)"
        r"|\b\d+(?:\.\d+)?\s*(?:ms|s|secs?|seconds?|mins?|minutes?|hours?|"
        r"days?|weeks?|months?|requests?|users?|percent|dollars?|USD|EUR|"
        r"GBP)\b",
        re.IGNORECASE,
    ),
    "contributing-factors": re.compile(
        r"\bbecause\b|\bcaused\b|\bcausing\b|\bdue to\b|\benabled\b|"
        r"\bsince\b|\bled to\b|\bleads to\b|\bcontributed\b|"
        r"\bwhich allowed\b",
        re.IGNORECASE,
    ),
    "uncertainty": re.compile(
        r"\bunknown\b|\bunclear\b|\bnot sure\b|\buncertain\b|"
        r"\bdon't know\b|\bdo not know\b|\bprobably\b|\blikely\b|"
        r"\bhypothesis\b|\[TK:",
        re.IGNORECASE,
    ),
    "repro": re.compile(
        r"\bsteps to reproduce\b|\brepro\b|\breproduce\b|\bversion\b|"
        r"\bexpected\b|\bactual\b|^\s*\d+\.\s+",
        re.IGNORECASE | re.MULTILINE,
    ),
    "acceptance": re.compile(
        r"\bacceptance\b|\bdone when\b|^\s*[-*]\s*\[\s*\]\s|"
        r"\bp\d{2,}\b|\bwhen\b[^.\n]{0,60}\bthen\b|\bunder\s+\d+\s*ms\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    "answer-first": re.compile(
        r"^\s*(?:fixed|done|yes|no|merged|shipped|works|reproduced|cannot|"
        r"can't|won't|won't fix|wontfix|will|already|found|installed|"
        r"patched|resolved|blocked|not a bug|not reproduced|closing)\b",
        re.IGNORECASE,
    ),
    "breaking-changes": re.compile(
        r"\bbreaking\b|\bmigration\b|\brenamed\b|\bremoving\b|\bremoved\b|"
        r"\bno longer\b|\bnow requires\b|\bdeprecated\b|\brenaming\b",
        re.IGNORECASE,
    ),
    "problem-first": re.compile(
        r"\bfailed\b|\bbroke\b|\bbroken\b|\berror\b|\bbug\b|\bincident\b|"
        r"\boutage\b|\bissue\b|\bproblem\b|\bwhy\b|\bcrash\b|\bwent down\b",
        re.IGNORECASE,
    ),
    "reflection-tail": re.compile(
        r"^\s*(?:in the end|ultimately|in conclusion|in summary|looking "
        r"back|at the end of the day|what mattered|it was then|this taught|"
        r"the lesson|all in all|as we look ahead|going forward|in hindsight)"
        r"\b",
        re.IGNORECASE,
    ),
}

QUD_REFLECTION_RE = FEATURE_PATTERNS["reflection-tail"]

# Rules whose application would flatten valid fiction voice or structure.
FICTION_RELAX = {
    "mechanism-importance", "mechanism-impact", "mechanism-causality",
    "mechanism-superiority", "struct-antithesis", "struct-specificity-theater",
    "struct-all-same-length", "struct-balanced-take", "struct-empty-declaratives",
}

# Formal-register venues where the semicolon exception applies.
SEMICOLON_FORMAL_VENUES = ("technical-article", "release-note")
# Venues where conventional heading-plus-first-line pairs are earned.
HEADING_CONVENTIONAL_VENUES = ("release-note", "technical-article",
                               "postmortem")

_STOP = frozenset((
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "for", "of",
    "to", "in", "on", "at", "by", "with", "from", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those", "it",
    "its", "it's", "we", "our", "you", "your", "they", "their", "he", "his",
    "she", "her", "i", "my", "me", "not", "no", "yes", "do", "does", "did",
    "have", "has", "had",
))


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def _paragraphs(text):
    return [para.strip() for para in re.split(r"\n\s*\n", text)
            if para.strip()]


def _quoted_spans(text):
    return [{"start": match.start(), "end": match.end()}
            for match in fidelity.QUOTED_RE.finditer(text)]


def _overlaps_any(start, end, spans):
    return any(span["start"] < end and start < span["end"] for span in spans)


def _content_words(text):
    return {word for word in WORD_RE.findall(text.lower()) if word not in _STOP}


def _span_text(text, finding):
    start = finding.get("position")
    if start is None:
        span = finding.get("span")
        if span and len(span) == 2:
            return text[span[0]:span[1]]
        return ""
    return text[start:start + finding.get("match_length", 6)]


def detect_venue_features(text):
    """Deterministic evidence spans for every registered venue feature.

    Scope is per feature: answer-first checks only the first sentence,
    problem-first only the first paragraph, reflection-tail only the final
    paragraph. Every other feature scans the whole text.
    """
    paragraphs = _paragraphs(text)
    first_para = paragraphs[0] if paragraphs else ""
    tail_para = paragraphs[-1] if len(paragraphs) >= 2 else ""
    first_sentence = ""
    if text.strip():
        parts = re.split(r"[.!?]+(?:\s+|$)", text.lstrip())
        first_sentence = parts[0] if parts else ""

    found = {}
    for feature_id, pattern in FEATURE_PATTERNS.items():
        if feature_id == "problem-first":
            source = first_para
            finder = text.find
        elif feature_id == "answer-first":
            source = first_sentence
            finder = text.find
        elif feature_id == "reflection-tail":
            source = tail_para
            finder = text.rfind
        else:
            source = text
            finder = text.find
        spans = []
        if source:
            base = finder(source)
            for match in pattern.finditer(source):
                start = base + match.start()
                spans.append({"start": start,
                              "end": start + len(match.group(0)),
                              "value": match.group(0)})
        found[feature_id] = spans
    return found


def qud_review(text):
    """Question-under-discussion review.

    The per-paragraph implicit-question check is human-review structural
    guidance, with a deterministic advisory topic-break signal between
    consecutive paragraphs. The reflection tail has an exact deterministic
    condition and is a finding: the final paragraph opens with a generic
    reflection marker after at least one earlier paragraph.
    """
    paragraphs = _paragraphs(text)
    guidance = []
    for index, para in enumerate(paragraphs):
        first = re.split(r"[.!?]+(?:\s+|$)", para)[0][:140]
        entry = {
            "paragraph": index + 1,
            "first_sentence": first.strip(),
            "status": "guidance",
            "question": "What one implicit question does this paragraph "
                        "answer?",
        }
        guidance.append(entry)

    for index in range(1, len(paragraphs)):
        previous = [s for s in
                    re.split(r"[.!?]+(?:\s+|$)", paragraphs[index - 1])
                    if s.strip()]
        previous_last = previous[-1] if previous else ""
        current_first = guidance[index]["first_sentence"]
        shared = _content_words(previous_last) & _content_words(current_first)
        if _content_words(current_first) and not shared:
            guidance[index]["topic_break"] = True
            guidance[index]["question"] = (
                "This paragraph changes topic without sharing content with "
                "the previous one. Does it advance the implicit question, "
                "or start a new one?")

    tail_finding = []
    if len(paragraphs) >= 2:
        tail = paragraphs[-1]
        base = text.rfind(tail)
        match = QUD_REFLECTION_RE.match(tail)
        if match is not None:
            start = base + match.start()
            end = base + len(tail)
            tail_finding.append({
                "status": "cut",
                "rule_id": "sepia-qud-reflection-tail",
                "pattern": "An unearned reflection tail closes the piece",
                "excerpt": _short_excerpt(text, start, end),
                "span": [start, end],
                "why": ("The final paragraph opens with a generic reflection "
                        "marker and no earlier paragraph earned the question "
                        "it answers."),
                "suggestion": "End at the content, or move the reflection so "
                              "an earlier paragraph earns it.",
            })
    return {
        "paragraphs": guidance,
        "reflection_tail": tail_finding,
        "guidance_only": True,
        "deterministic_rules": ["sepia-qud-reflection-tail"],
    }


# --------------------------------------------------------------------------
# Review operation
# --------------------------------------------------------------------------

def _author_habit(span_text, author_habits):
    """True when a finding's span matches a verified author habit.

    A habit is a token or phrase the author demonstrably uses in their own
    writing. Applying the rule to it would flatten their voice, so the
    finding is recorded as over-correction.
    """
    if not author_habits:
        return False
    st = span_text.strip().lower()
    if not st:
        return False
    for habit in author_habits:
        h = habit.strip().lower()
        if not h:
            continue
        if h in st or st in h:
            return True
    return False


def _finding_status(rule, start, end, profile, quoted_spans, span_text,
                    author_habits):
    """One explicit status per review finding."""
    if _overlaps_any(start, end, quoted_spans):
        return "keep"
    if rule is None:
        return "revise"
    rule_id = rule["id"]
    if profile == "fiction" and rule_id in FICTION_RELAX:
        return "over-correction"
    if _author_habit(span_text, author_habits):
        return "over-correction"
    if (rule["semantic_type"] == "forbidden"
            and rule.get("review_mode") == "deterministic"):
        if rule["category"] in ("filler", "chatbot") or rule_id in review.CUT_RULES:
            return "cut"
        return "revise"
    if rule_id in review.CUT_RULES or rule["category"] in ("filler", "chatbot"):
        return "cut"
    return "revise"


def _status_reason(status, profile):
    if status == "cut":
        return ("The passage adds only repetition, ceremony, unsupported "
                "emphasis, or closure.")
    if status == "keep":
        return ("The pattern is quoted material, earned by context, or "
                "required by the venue.")
    if status == "over-correction":
        if profile == "fiction":
            return ("Applying the rule would flatten valid fiction voice or "
                    "structure.")
        return ("Applying the rule would flatten valid voice or structure, "
                "such as a formal register, quoted material, or an author's "
                "verified habit.")
    if status == "ask-author":
        return ("The improvement needs author-owned material the source does "
                "not supply.")
    return ("Deterministic banned pattern; the source can support an honest "
            "improvement.")


def _status_suggestion(rule, status):
    if status == "cut":
        return "Cut it, or keep only what the passage needs."
    if status == "keep":
        return "Keep as-is."
    if status == "over-correction":
        return "Keep the voice; the rule does not apply here."
    return rule.get("correction", "") if rule else "Rewrite the passage."


def _scored_findings(text, registry, profile, quoted_spans, author_habits):
    """Lexical and structural findings from the scorer, minus mechanism."""
    rules = registry.get("rules", [])
    rule_by_id = {rule["id"]: rule for rule in rules}
    mechanism_ids = {rule["id"] for rule in rules
                     if rule["category"] == "mechanism"}
    scored, _skipped, _metrics = scoring.detect_findings(text, registry, profile)
    scored = [finding for finding in scored
              if finding["rule_id"] not in mechanism_ids
              and finding["rule_id"] != "fmt-semicolon"]
    scored = scoring.handle_overlaps(scored)

    findings = []
    for finding in scored:
        rule = rule_by_id.get(finding["rule_id"])
        start = finding["position"]
        end = start + finding.get("match_length", 6)
        span_text = _span_text(text, finding)
        status = _finding_status(rule, start, end, profile, quoted_spans,
                                 span_text, author_habits)
        findings.append({
            "status": status,
            "rule_id": finding["rule_id"],
            "pattern": (rule.get("text", "") if rule
                        else finding.get("message", "")),
            "excerpt": finding.get("excerpt", ""),
            "span": [start, end],
            "why": _status_reason(status, profile),
            "suggestion": _status_suggestion(rule, status),
        })
    return findings, rule_by_id


def _mechanism_findings(text, registry, profile):
    findings = []
    for entry in review.mechanism_entries(text, registry):
        if profile == "fiction":
            status = "over-correction"
            why = ("Narrative causality and significance are valid fiction "
                   "voice; applying the mechanism rule would flatten it.")
            suggestion = "Keep the voice; the rule does not apply here."
        elif entry["evidenced"]:
            status = "keep"
            why = ("The claim is supported by a nearby mechanism or measured "
                   "result.")
            suggestion = ("Keep; the passage names the mechanism, actor, "
                          "result, or limit that earns the claim.")
        else:
            status = "ask-author"
            why = ("The claim names no mechanism, actor, result, or limit "
                   "nearby.")
            suggestion = review.MECHANISM_QUESTIONS[entry["kind"]]
        item = {
            "status": status,
            "rule_id": entry["rule_id"],
            "kind": entry["kind"],
            "pattern": entry["pattern"],
            "excerpt": _short_excerpt(text, entry["start"], entry["end"]),
            "span": [entry["start"], entry["end"]],
            "why": why,
            "suggestion": suggestion,
        }
        if status == "ask-author":
            item["tk"] = review.MECHANISM_QUESTIONS[entry["kind"]]
        findings.append(item)
    return findings


def _semicolon_findings(text, venue, profile, rule):
    """Paragraph-level semicolon clusters (2+ per paragraph).

    The fmt-semicolon rule's exception is formal or academic register. In
    the formal-register venues the cluster is over-correction; elsewhere it
    is a rhythm tell. A single semicolon never fires.
    """
    findings = []
    for para in _paragraphs(text):
        if para.count(";") < 2:
            continue
        base = text.find(para)
        if profile == "fiction" or venue in SEMICOLON_FORMAL_VENUES:
            status = "over-correction"
            why = ("The semicolon cluster is formal register or valid voice; "
                   "applying the rule would flatten it.")
            suggestion = "Keep the semicolons; the rule does not apply here."
        else:
            status = "revise"
            why = ("Two or more semicolons per paragraph is a rhythm tell "
                   "outside formal register.")
            suggestion = ("Split into separate sentences, or keep the "
                          "cluster where the register is formal.")
        findings.append({
            "status": status,
            "rule_id": rule["id"] if rule else "fmt-semicolon",
            "pattern": (rule.get("text", "Semicolon overuse (2+ per "
                                            "paragraph)")
                        if rule else "Semicolon overuse (2+ per paragraph)"),
            "excerpt": _short_excerpt(text, base, base + len(para)),
            "span": [base, base + len(para)],
            "why": why,
            "suggestion": suggestion,
        })
    return findings


def _heading_findings(text, venue, rule):
    """Conventional heading-plus-first-line pairs.

    A heading immediately restated by its first line is earned in the
    venues whose templates use conventional section headings; elsewhere it
    is a structural defect.
    """
    findings = []
    for span in review.detect_fragmented_headers(text):
        status = "keep" if venue in HEADING_CONVENTIONAL_VENUES else "revise"
        why = ("Conventional heading-plus-first-line pairs are earned in "
               "this venue." if status == "keep"
               else "A heading immediately restated by its first line "
                    "weakens the piece.")
        suggestion = ("Keep; conventional structure serves this venue."
                      if status == "keep"
                      else "Merge the heading and its restatement into one "
                           "point.")
        findings.append({
            "status": status,
            "rule_id": "struct-fragmented-headers",
            "pattern": (rule.get("text", "Fragmented headers") if rule
                        else "Fragmented headers"),
            "excerpt": _short_excerpt(text, span["start"], span["end"]),
            "span": [span["start"], span["end"]],
            "why": why,
            "suggestion": suggestion,
        })
    return findings


def _em_dash_findings(text, rule, author_habits):
    """Zero-em-dash rule, absolute in every profile and venue."""
    findings = []
    for match in review.EM_DASH_RE.finditer(text):
        span_text = text[match.start():match.end()]
        status = ("over-correction"
                  if _author_habit(span_text, author_habits) else "revise")
        findings.append({
            "status": status,
            "rule_id": rule["id"],
            "pattern": rule.get("text",
                                "Em-dash, en-dash, or double hyphen"),
            "excerpt": text[max(0, match.start() - 20):
                            min(len(text), match.end() + 20)].strip(),
            "span": [match.start(), match.end()],
            "why": (_status_reason(status, "general")
                    if status == "over-correction"
                    else "The em-dash rule is absolute and applies in every "
                         "profile and venue."),
            "suggestion": (rule.get("correction", "Replace with a period or "
                                                    "comma and break the "
                                                    "sentence.") if rule
                           else "Replace with a period or comma."),
        })
    return findings


def _venue_check_rows(text, venue, registry):
    """Which venue features are kept, missing, or n/a in this venue."""
    conf = registry.get("venues", {}).get(venue, {})
    applicable = conf.get("applicable", [])
    not_applicable = conf.get("not_applicable", [])
    features = registry.get("venue_features", {})
    evidence = detect_venue_features(text)
    rows = []
    for feature_id in applicable:
        description = features.get(feature_id, {}).get(
            "description", feature_id)
        spans = evidence.get(feature_id, [])
        if spans:
            rows.append({
                "feature": feature_id,
                "status": "keep",
                "excerpt": spans[0]["value"],
                "span": [spans[0]["start"], spans[0]["end"]],
                "why": ("The venue requires %s and the text supplies it."
                        % description),
            })
        else:
            rows.append({
                "feature": feature_id,
                "status": "missing",
                "excerpt": None,
                "span": None,
                "why": ("The venue requires %s and none is present."
                        % description),
            })
    for feature_id in not_applicable:
        description = features.get(feature_id, {}).get(
            "description", feature_id)
        rows.append({
            "feature": feature_id,
            "status": "n/a",
            "excerpt": None,
            "span": None,
            "why": ("This structural feature does not apply to the venue: "
                    "%s" % description),
        })
    return rows


def _overall_decision(findings, missing_features):
    statuses = [finding["status"] for finding in findings]
    if missing_features:
        statuses.append("revise")
    if not statuses:
        return "no-finding"
    return max(statuses, key=lambda status: STATUS_WEIGHT[status])


def review_venue(text, venue, registry, profile="general", *,
                 author_habits=(), voice_sample=None, sample_facts=(),
                 registry_path="rules.json"):
    limits.check_input_size(text, "source text")
    """Review a single artifact under a venue without editing it.

    Returns a JSON-serializable report. The report never contains a
    rewritten passage: missing author material becomes a '[TK: ...]'
    question, and every finding carries a quoted span, rule, status, and
    reason. Under the fiction profile no venue routes the review.
    """
    if profile == "fiction":
        if venue is not None:
            raise ValueError("fiction profile does not route by venue")
    elif venue not in VENUES:
        raise ValueError("unknown venue %r" % venue)
    if profile not in PROFILES:
        raise ValueError("unknown profile %r" % profile)

    rules = registry.get("rules", [])
    rule_by_id = {rule["id"]: rule for rule in rules}
    quoted_spans = _quoted_spans(text)

    findings, _by_id = _scored_findings(text, registry, profile,
                                        quoted_spans, author_habits)

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

    findings.extend(_mechanism_findings(text, registry, profile))

    semicolon_rule = rule_by_id.get("fmt-semicolon")
    findings.extend(_semicolon_findings(text, venue, profile, semicolon_rule))

    heading_rule = rule_by_id.get("struct-fragmented-headers")
    findings.extend(_heading_findings(text, venue, heading_rule))

    em_dash_rule = rule_by_id.get("fmt-em-dash")
    if em_dash_rule is not None:
        findings.extend(_em_dash_findings(text, em_dash_rule, author_habits))

    for gap in review.detect_author_gaps(text):
        rule = rule_by_id.get(gap["rule_id"])
        findings.append({
            "status": "ask-author",
            "rule_id": gap["rule_id"],
            "kind": gap["kind"],
            "pattern": rule.get("text", "") if rule else gap["kind"],
            "excerpt": gap["excerpt"],
            "span": [gap["start"], gap["end"]],
            "why": ("The example has the grammar of a specific story and no "
                    "specific content." if gap["kind"] == "vague_example"
                    else "The claim asserts significance without saying what "
                         "changed or for whom."),
            "suggestion": gap["tk"],
            "tk": gap["tk"],
        })

    qud = qud_review(text)
    findings.extend(qud["reflection_tail"])

    voice = review.check_voice_sample(voice_sample, text, sample_facts)
    findings.extend(voice["findings"])

    findings.sort(key=lambda finding: (finding.get("excerpt", ""),
                                       finding["rule_id"]))

    rows = _venue_check_rows(text, venue, registry) if venue else []
    missing_features = [row["feature"] for row in rows
                        if row["status"] == "missing"]
    overall = _overall_decision(findings, missing_features)

    author_questions = []
    for finding in findings:
        if finding.get("tk"):
            author_questions.append({
                "tk": finding["tk"],
                "rule_id": finding["rule_id"],
                "excerpt": finding.get("excerpt", ""),
            })

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
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "mode": "review",
        "operation": "review",
        "venue": venue,
        "profile": profile,
        "edited": False,
        "decision": overall,
        "statuses": {status: count for status, count
                     in collections.Counter(
                         finding["status"] for finding in findings).items()},
        "findings": findings,
        "venue_checks": rows,
        "qud": qud,
        "author_questions": author_questions,
        "output_integrity": {
            "defects": integrity_defects,
            "tk_markers": [defect for defect in integrity_defects
                           if defect["kind"] == "placeholder"
                           and defect["value"].startswith("[TK")],
        },
        "risk": risk,
        "meta": {
            "disclaimer": DISCLAIMER,
            "authority": edit.OPERATIONS["audit"]["authority"],
            "false_positive_rationale": None,
            "reviewer_notes": None,
            "horoscope_test": density.HOROSCOPE_NOTE,
        },
    }


# --------------------------------------------------------------------------
# Refactor operation
# --------------------------------------------------------------------------

def _proposed_edits(text, findings, registry):
    """The full finding set's repairable edits, derived from the registry.

    Only findings whose rule carries a registered literal correction become
    proposals; the rest are reported as unresolved, never silently fixed.
    """
    rule_by_id = {rule["id"]: rule for rule in registry.get("rules", [])}
    proposals = []
    for finding in findings:
        rule = rule_by_id.get(finding["rule_id"])
        replacement = repair.literal_replacement(rule) if rule else None
        span = finding.get("span")
        if replacement is None or not span or len(span) != 2:
            continue
        proposals.append({
            "rule_id": finding["rule_id"],
            "span": list(span),
            "original": text[span[0]:span[1]],
            "replacement": replacement,
            "correction_id": "registry:%s" % finding["rule_id"],
        })
    return proposals


def _resolve_accepted(text, accepted_edits, findings, registry,
                      required_terms):
    """Resolve accepted edit specs into concrete spans.

    An accepted edit may name an exact span, or a rule_id whose replacement
    lands on the first finding span of that rule.
    """
    rule_by_id = {rule["id"]: rule for rule in registry.get("rules", [])}
    rule_spans = {}
    for finding in findings:
        span = finding.get("span")
        if not span or len(span) != 2:
            continue
        rule_spans.setdefault(finding["rule_id"], list(span))
    resolved = []
    for spec in accepted_edits:
        rule_id = spec.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            continue
        if rule_id not in rule_spans:
            continue
        replacement = spec.get("replacement")
        if not isinstance(replacement, str) or not replacement:
            rule = rule_by_id.get(rule_id)
            replacement = repair.literal_replacement(rule) if rule else None
        if not isinstance(replacement, str) or not replacement:
            continue
        span = spec.get("span") or rule_spans.get(rule_id)
        if not span or len(span) != 2:
            continue
        start, end = span
        if start < 0 or end > len(text) or start >= end:
            continue
        resolved.append({
            "rule_id": rule_id,
            "span": [start, end],
            "replacement": replacement,
            "original": text[start:end],
            "correction_id": "accepted:%s" % rule_id,
        })
    return resolved


def _apply_edits(text, edits):
    kept = []
    for correction in sorted(edits,
                             key=lambda c: (c["span"][1] - c["span"][0],
                                            c["span"][0])):
        start, end = correction["span"]
        if any(start < existing["span"][1] and existing["span"][0] < end
               for existing in kept):
            continue
        kept.append(correction)
    kept.sort(key=lambda c: c["span"][0])
    applied = [{"start": c["span"][0], "end": c["span"][1],
                "replacement": c["replacement"], "rule_id": c["rule_id"],
                "action": "replace"} for c in kept]
    candidate = repair.apply_edits(text, applied)
    return candidate, kept


def refactor_venue(text, venue, registry, profile="general", *,
                   accepted_edits=(), author_habits=(), required_terms=(),
                   registry_path="rules.json"):
    """Refactor under a venue: list the full finding set, then apply only
    the accepted minimal edits and report the rejected and unresolved
    findings."""
    if venue not in VENUES:
        raise ValueError("unknown venue %r" % venue)
    if profile not in PROFILES:
        raise ValueError("unknown profile %r" % profile)

    rule_by_id = {rule["id"]: rule for rule in registry.get("rules", [])}
    review_report = review_venue(text, venue, registry, profile,
                                 author_habits=author_habits,
                                 registry_path=registry_path)
    full_findings = review_report["findings"]
    proposals = _proposed_edits(text, full_findings, registry)

    resolved = _resolve_accepted(text, accepted_edits, full_findings, registry,
                                 required_terms)

    regions = repair.protected_regions(text, required_terms)
    applied = []
    rejected = []
    for correction in sorted(resolved, key=lambda c: c["span"][0]):
        start, end = correction["span"]
        if start < 0 or end > len(text) or start >= end:
            rejected.append({
                "rule_id": correction["rule_id"],
                "span": correction["span"],
                "original": correction["original"],
                "reason": "invalid span",
            })
            continue
        if repair._overlaps_protected(start, end, regions):
            rejected.append({
                "rule_id": correction["rule_id"],
                "span": correction["span"],
                "original": correction["original"],
                "reason": "protected span",
            })
            continue
        applied.append(correction)

    accepted_ids = {correction["rule_id"] for correction in applied}
    rejected.extend({
        "rule_id": proposal["rule_id"],
        "span": proposal["span"],
        "original": proposal["original"],
        "replacement": proposal["replacement"],
        "reason": "not accepted",
    } for proposal in proposals
        if proposal["rule_id"] not in accepted_ids
        and not any(correction["rule_id"] == proposal["rule_id"]
                    and correction["span"] == proposal["span"]
                    for correction in resolved))

    candidate, applied_corrections = _apply_edits(text, applied)
    edited = candidate != text

    full_rule_ids = {finding["rule_id"] for finding in full_findings}
    cand_findings, _skipped, _metrics = scoring.detect_findings(
        candidate, registry, profile)
    cand_findings = scoring.handle_overlaps(cand_findings)
    unresolved = []
    for finding in cand_findings:
        if finding["rule_id"] not in full_rule_ids:
            continue
        unresolved.append({
            "rule_id": finding["rule_id"],
            "span": [finding["position"],
                     finding["position"] + finding.get("match_length", 6)],
        })

    if applied:
        decision = "rejected" if any(item["reason"] != "not accepted"
                                     for item in rejected) else "applied"
    elif resolved and not applied:
        decision = "rejected"
    else:
        decision = "no-change"

    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "mode": "refactor",
        "operation": "refactor",
        "venue": venue,
        "profile": profile,
        "decision": decision,
        "edited": edited,
        "findings": full_findings,
        "proposed": proposals,
        "accepted": [{
            "rule_id": correction["rule_id"],
            "span": correction["span"],
            "original": correction["original"],
            "replacement": correction["replacement"],
            "correction_id": correction["correction_id"],
        } for correction in applied_corrections],
        "rejected": rejected,
        "unresolved": unresolved,
        "text": candidate,
        "meta": {
            "disclaimer": DISCLAIMER,
            "required_terms": list(required_terms),
            "authority": edit.OPERATIONS["revise"]["authority"],
            "false_positive_rationale": None,
            "reviewer_notes": None,
        },
    }


# --------------------------------------------------------------------------
# Recreate operation
# --------------------------------------------------------------------------

def extract_source_inventory(source, venue, registry, *, required_facts=(),
                             required_terms=(), declared_claims=(),
                             intent=None, constraints=()):
    """Extract facts, claims, quotes, intent, and constraints from the
    source before any fresh prose is drafted.

    Facts and claims are kept only when the source actually contains them;
    a declared fact the source does not carry is not part of the inventory.
    Venue-preserve features present in the source are recorded so the
    candidate must keep them.
    """
    anchors = fidelity.extract_anchors(source, required_terms)
    venue_conf = registry.get("venues", {}).get(venue, {})
    evidence = detect_venue_features(source)
    present_features = [feature_id for feature_id
                        in venue_conf.get("applicable", [])
                        if evidence.get(feature_id)]
    return {
        "facts": [fact for fact in required_facts
                  if drift.contains_fact(source, fact)],
        "claims": [claim for claim in declared_claims
                   if drift.contains_fact(source, claim)],
        "quotes": [{"value": source[span["start"]:span["end"]]}
                   for span in _quoted_spans(source)],
        "intent": intent,
        "constraints": {
            "venue": venue,
            "optimize": venue_conf.get("optimize", ""),
            "preserve": venue_conf.get("preserve", ""),
            "avoid": venue_conf.get("avoid", ""),
            "declared": list(constraints),
        },
        "protected_spans": anchors["protected_spans"],
        "required_terms": list(required_terms),
        "venue_preserve_features": present_features,
    }


def verify_recreate(source, candidate, venue, registry, extraction, *,
                    authorized_changes=(), profile="general"):
    """Verify the freshly drafted candidate keeps the extracted inventory.

    Required facts, claims, quotes, and venue-preserve features must
    survive, and protected spans must not be dropped or changed beyond an
    authorized change. The decision is accept when nothing is missing or
    changed, reject otherwise.
    """
    items = {"missing": [], "changed": [], "added": []}
    reasons = []

    for fact in extraction["facts"]:
        if not drift.contains_fact(candidate, fact):
            items["missing"].append({"kind": "fact", "value": fact})
            reasons.append("fact '%s' is missing" % fact)
    for claim in extraction["claims"]:
        if not drift.contains_fact(candidate, claim):
            items["missing"].append({"kind": "claim", "value": claim})
            reasons.append("claim '%s' is missing" % claim)

    candidate_quotes = [candidate[span["start"]:span["end"]]
                        for span in _quoted_spans(candidate)]
    for quote in extraction["quotes"]:
        if candidate_quotes.count(quote["value"]) < 1:
            items["missing"].append({"kind": "quote", "value": quote["value"]})
            reasons.append("quote '%s' is missing" % quote["value"])

    candidate_evidence = detect_venue_features(candidate)
    for feature_id in extraction["venue_preserve_features"]:
        if not candidate_evidence.get(feature_id):
            items["missing"].append({"kind": "venue_feature",
                                     "value": feature_id})
            reasons.append("venue feature '%s' is missing" % feature_id)

    source_by_category = collections.defaultdict(list)
    candidate_by_category = collections.defaultdict(list)
    for span in extraction["protected_spans"]:
        source_by_category[span["category"]].append(span["value"].lower())
    for span in fidelity.extract_anchors(
            candidate, tuple(extraction.get("required_terms", ()))
            )["protected_spans"]:
        candidate_by_category[span["category"]].append(span["value"].lower())

    authorized = set()
    for change in authorized_changes:
        for part in change.split("="):
            authorized.add(part.strip().lower())

    for category, source_values in source_by_category.items():
        candidate_values = candidate_by_category.get(category, [])
        source_counts = collections.Counter(source_values)
        candidate_counts = collections.Counter(candidate_values)
        for value in source_counts:
            missing = source_counts[value] - candidate_counts.get(value, 0)
            if missing > 0:
                items["missing"].append({"kind": "protected_%s" % category,
                                         "value": value})
                reasons.append("protected %s '%s' is missing"
                               % (category, value))
        for value in candidate_counts:
            added = candidate_counts[value] - source_counts.get(value, 0)
            if added > 0:
                items["added"].append({"kind": "protected_%s" % category,
                                       "value": value})

    decision = "reject" if items["missing"] or items["changed"] else "accept"
    return {
        "decision": decision,
        "items": items,
        "reasons": reasons,
        "authorized_changes": list(authorized_changes),
    }


def recreate_venue(source, candidate, venue, registry, profile="general", *,
                   required_facts=(), required_terms=(), declared_claims=(),
                   intent=None, constraints=(), authorized_changes=(),
                   registry_path="rules.json"):
    """Recreate under a venue: extract the source inventory, then verify
    the freshly drafted candidate keeps it."""
    if venue not in VENUES:
        raise ValueError("unknown venue %r" % venue)
    if profile not in PROFILES:
        raise ValueError("unknown profile %r" % profile)

    extraction = extract_source_inventory(
        source, venue, registry, required_facts=required_facts,
        required_terms=required_terms, declared_claims=declared_claims,
        intent=intent, constraints=constraints)
    verification = verify_recreate(
        source, candidate, venue, registry, extraction,
        authorized_changes=authorized_changes, profile=profile)

    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "mode": "recreate",
        "operation": "recreate",
        "venue": venue,
        "profile": profile,
        "decision": verification["decision"],
        "extracted": extraction,
        "missing": verification["items"]["missing"],
        "changed": verification["items"]["changed"],
        "added": verification["items"]["added"],
        "reasons": verification["reasons"],
        "meta": {
            "disclaimer": DISCLAIMER,
            "authority": edit.OPERATIONS["draft"]["authority"],
            "false_positive_rationale": None,
            "reviewer_notes": None,
        },
    }


# --------------------------------------------------------------------------
# Fixture corpus
# --------------------------------------------------------------------------

def validate_fixture(fixture, seen_ids):
    """Schema-validate one sepia-routing fixture. Returns error strings."""
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

    operation = fixture.get("operation")
    if operation not in OPERATIONS:
        errors.append("%s: operation must be one of %s"
                      % (where, ", ".join(OPERATIONS)))

    venue = fixture.get("venue")
    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(PROFILES)))
    if profile == "fiction":
        if venue is not None:
            errors.append("%s: fiction profile must not carry a venue" % where)
    elif venue not in VENUES:
        errors.append("%s: venue must be one of %s"
                      % (where, ", ".join(VENUES)))

    source = fixture.get("source")
    if not isinstance(source, str) or not source.strip():
        errors.append("%s: 'source' must be a non-empty string" % where)

    expected = fixture.get("expected_decision")
    if operation == "review" and expected not in REVIEW_DECISIONS:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(REVIEW_DECISIONS)))
    if operation == "refactor" and expected not in REFACTOR_DECISIONS:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(REFACTOR_DECISIONS)))
    if operation == "recreate" and expected not in RECREATE_DECISIONS:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(RECREATE_DECISIONS)))

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

    venue_statuses = fixture.get("expected_venue_statuses", {})
    if not isinstance(venue_statuses, dict):
        errors.append("%s: expected_venue_statuses must be an object" % where)
    else:
        for feature_id, status in venue_statuses.items():
            if not (isinstance(feature_id, str) and feature_id.strip()):
                errors.append("%s: expected_venue_statuses keys must be "
                              "non-empty strings" % where)
            if status not in ("keep", "missing", "n/a"):
                errors.append("%s: expected_venue_statuses['%s'] must be "
                              "keep, missing, or n/a" % (where, feature_id))

    questions = fixture.get("expected_author_questions", [])
    if not isinstance(questions, list):
        errors.append("%s: expected_author_questions must be a list" % where)
    else:
        for i, question in enumerate(questions):
            if not (isinstance(question, str) and question.strip()):
                errors.append("%s: expected_author_questions[%d] must be a "
                              "non-empty string" % (where, i))

    habits = fixture.get("author_habits", [])
    if not isinstance(habits, list):
        errors.append("%s: author_habits must be a list" % where)
    else:
        for i, habit in enumerate(habits):
            if not (isinstance(habit, str) and habit.strip()):
                errors.append("%s: author_habits[%d] must be a non-empty "
                              "string" % (where, i))

    if not isinstance(fixture.get("no_invention", False), bool):
        errors.append("%s: no_invention must be a boolean" % where)

    edits = fixture.get("accepted_edits", [])
    if not isinstance(edits, list):
        errors.append("%s: accepted_edits must be a list" % where)
    else:
        for i, entry in enumerate(edits):
            if not isinstance(entry, dict):
                errors.append("%s: accepted_edits[%d] must be an object"
                              % (where, i))
                continue
            if not (isinstance(entry.get("rule_id"), str)
                    and entry["rule_id"].strip()):
                errors.append("%s: accepted_edits[%d] missing non-empty "
                              "'rule_id'" % (where, i))
            if not isinstance(entry.get("replacement"), str):
                errors.append("%s: accepted_edits[%d] replacement must be a "
                              "string" % (where, i))

    for field in ("expected_applied_rule_ids", "expected_rejected_rule_ids",
                  "expected_unresolved_rule_ids"):
        values = fixture.get(field, [])
        if not isinstance(values, list):
            errors.append("%s: %s must be a list" % (where, field))
        else:
            for index, value in enumerate(values):
                if not (isinstance(value, str) and value.strip()):
                    errors.append("%s: %s[%d] must be a non-empty string"
                                  % (where, field, index))

    for field in ("required_facts", "required_terms", "declared_claims",
                  "constraints"):
        values = fixture.get(field, [])
        if not isinstance(values, list):
            errors.append("%s: %s must be a list" % (where, field))
        else:
            for index, value in enumerate(values):
                if not (isinstance(value, str) and value.strip()):
                    errors.append("%s: %s[%d] must be a non-empty string"
                                  % (where, field, index))

    candidate = fixture.get("candidate")
    if operation == "recreate":
        if not isinstance(candidate, str) or not candidate.strip():
            errors.append("%s: 'candidate' must be a non-empty string "
                          "for a recreate fixture" % where)

    expected_text = fixture.get("expected_text")
    if expected_text is not None and not isinstance(expected_text, str):
        errors.append("%s: expected_text must be a string" % where)
    unchanged = fixture.get("expected_unchanged_text")
    if unchanged is not None and not isinstance(unchanged, str):
        errors.append("%s: expected_unchanged_text must be a string" % where)

    rationale = fixture.get("false_positive_rationale")
    if rationale is not None and (not isinstance(rationale, str)
                                  or not rationale.strip()):
        errors.append("%s: false_positive_rationale must be a non-empty "
                      "string" % where)
    notes = fixture.get("reviewer_notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append("%s: reviewer_notes must be a non-empty string" % where)
    return errors


def _fixture_failures(report, fixture):
    """Compare a computed report against its fixture expectations."""
    failures = []
    expected = fixture["expected_decision"]
    if report["decision"] != expected:
        failures.append("expected decision %s, got %s"
                        % (expected, report["decision"]))

    if fixture.get("operation") == "review":
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
        checks_by_feature = {row["feature"]: row["status"]
                             for row in report["venue_checks"]}
        for feature_id, status in (
                fixture.get("expected_venue_statuses", {}) or {}).items():
            if checks_by_feature.get(feature_id) != status:
                failures.append("venue feature '%s' expected %s, got %s"
                                % (feature_id, status,
                                   checks_by_feature.get(feature_id)))
        question_texts = [finding.get("tk", "")
                          for finding in report["findings"]]
        question_texts += [item["tk"] for item in report["author_questions"]]
        for question in fixture.get("expected_author_questions", []):
            if not any(question in text for text in question_texts):
                failures.append("missing author question containing %r"
                                % question)
        if fixture.get("no_invention"):
            for finding in report["findings"]:
                if finding["status"] != "ask-author":
                    continue
                suggestion = finding.get("suggestion", "")
                if not re.search(r"\[TK:|Ask the author|ask the author|"
                                 r"\bcut\b|fallback", suggestion,
                                 re.IGNORECASE):
                    failures.append("ask-author suggestion '%s' invents "
                                    "content" % suggestion)

    if fixture.get("operation") == "refactor":
        applied_ids = [item["rule_id"] for item in report["accepted"]]
        for rule_id in fixture.get("expected_applied_rule_ids", []):
            if rule_id not in applied_ids:
                failures.append("rule '%s' was not applied" % rule_id)
        rejected_ids = [item["rule_id"] for item in report["rejected"]]
        for rule_id in fixture.get("expected_rejected_rule_ids", []):
            if rule_id not in rejected_ids:
                failures.append("rule '%s' was not reported as rejected"
                                % rule_id)
        unresolved_ids = [item["rule_id"] for item in report["unresolved"]]
        for rule_id in fixture.get("expected_unresolved_rule_ids", []):
            if rule_id not in unresolved_ids:
                failures.append("rule '%s' was not reported as unresolved"
                                % rule_id)
        expected_text = fixture.get("expected_text")
        if expected_text is not None and report["text"] != expected_text:
            failures.append("expected exact text, got %r" % report["text"])
        unchanged = fixture.get("expected_unchanged_text")
        if unchanged is not None:
            if unchanged not in report["text"]:
                failures.append("unaffected text '%s' was rewritten"
                                % unchanged)

    if fixture.get("operation") == "recreate":
        missing_kinds = [item["kind"] for item in report["missing"]]
        for kind in fixture.get("expected_missing_kinds", []):
            if kind not in missing_kinds:
                failures.append("expected missing kind '%s' not reported"
                                % kind)
    return failures


def run_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one sepia-routing fixture against its expectations."""
    fid = fixture["id"]
    profile = fixture.get("profile", "general")
    venue = fixture.get("venue")
    operation = fixture["operation"]
    if operation == "review":
        report = review_venue(
            fixture["source"], venue, registry, profile,
            author_habits=tuple(fixture.get("author_habits", [])),
            voice_sample=fixture.get("voice_sample"),
            sample_facts=tuple(fixture.get("sample_facts", [])),
            registry_path=registry_path)
    elif operation == "refactor":
        report = refactor_venue(
            fixture["source"], venue, registry, profile,
            accepted_edits=tuple(fixture.get("accepted_edits", [])),
            author_habits=tuple(fixture.get("author_habits", [])),
            required_terms=tuple(fixture.get("required_terms", [])),
            registry_path=registry_path)
    else:
        report = recreate_venue(
            fixture["source"], fixture["candidate"], venue, registry, profile,
            required_facts=fixture.get("required_facts", []),
            required_terms=fixture.get("required_terms", []),
            declared_claims=fixture.get("declared_claims", []),
            intent=fixture.get("intent"),
            constraints=fixture.get("constraints", []),
            authorized_changes=fixture.get("authorized_changes", []),
            registry_path=registry_path)
    report["id"] = fid
    report["expected_decision"] = fixture["expected_decision"]
    report["meta"]["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
    report["failures"] = _fixture_failures(report, fixture)
    return report


def run_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the sepia-routing fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "interface": INTERFACE,
            "schema": SCHEMA,
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

    reports = [run_fixture(fixture, registry, registry_path=registry_path)
               for fixture in fixtures]
    failed = [report for report in reports if report["failures"]]
    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "fixture_count": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "failures": [{
            "id": report["id"],
            "operation": report["operation"],
            "venue": report.get("venue"),
            "profile": report["profile"],
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


def _parse_accept_spec(spec):
    """Parse a 'rule-id=replacement' refactor accept spec."""
    if "=" not in spec:
        return {"rule_id": spec}
    rule_id, replacement = spec.split("=", 1)
    return {"rule_id": rule_id, "replacement": replacement}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        default="skills/antislop/evals/sepia-routing-fixtures.json",
        help="Run the sepia-routing fixture corpus instead of an operation "
             "(default: repo path)")
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Print a compact JSON report")
    sub = parser.add_subparsers(dest="operation")

    review_p = sub.add_parser("review", help="Review without editing")
    review_p.add_argument("--source-text", required=True)
    review_p.add_argument("--venue", default=None,
                          help="One of: %s" % ", ".join(VENUES))
    review_p.add_argument("--profile", default="general")
    review_p.add_argument("--fiction", action="store_true",
                          help="Review under the opt-in fiction profile")

    refactor_p = sub.add_parser("refactor", help="Apply only accepted edits")
    refactor_p.add_argument("--source-text", required=True)
    refactor_p.add_argument("--venue", required=True,
                            help="One of: %s" % ", ".join(VENUES))
    refactor_p.add_argument("--profile", default="general")
    refactor_p.add_argument("--accept", action="append", default=[],
                            help="Accepted edit as rule-id=replacement "
                                 "(repeatable)")

    recreate_p = sub.add_parser("recreate", help="Extract and verify")
    recreate_p.add_argument("--source-text", required=True)
    recreate_p.add_argument("--candidate", required=True)
    recreate_p.add_argument("--venue", required=True,
                            help="One of: %s" % ", ".join(VENUES))
    recreate_p.add_argument("--profile", default="general")
    recreate_p.add_argument("--fact", action="append", default=[],
                            help="Required fact (repeatable)")

    args = parser.parse_args()

    registry = load_registry(args.registry)
    if args.expect_version and registry.get("version") != args.expect_version:
        print(json.dumps({
            "error": "registry version %s does not match --expect-version %s"
                     % (registry.get("version"), args.expect_version),
        }, indent=2))
        sys.exit(2)

    if args.operation is None:
        if not os.path.exists(args.fixtures):
            print(json.dumps({"error": "fixture corpus not found: %s"
                              % args.fixtures}, indent=2))
            sys.exit(2)
        fixtures = load_json(args.fixtures)
        report = run_corpus(fixtures.get("evals", fixtures), registry,
                            args.registry)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0 if report["gate_pass"] else 1)

    if args.operation == "review":
        venue = None if args.fiction else args.venue
        if venue is None and not args.fiction:
            print(json.dumps({"error": "review needs --venue or --fiction"},
                             indent=2))
            sys.exit(2)
        profile = "fiction" if args.fiction else args.profile
        report = review_venue(args.source_text, venue, registry, profile,
                              registry_path=args.registry)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0)
    if args.operation == "refactor":
        report = refactor_venue(
            args.source_text, args.venue, registry, args.profile,
            accepted_edits=tuple(_parse_accept_spec(spec)
                                 for spec in args.accept),
            registry_path=args.registry)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0)
    if args.operation == "recreate":
        report = recreate_venue(
            args.source_text, args.candidate, args.venue, registry,
            args.profile, required_facts=tuple(args.fact),
            registry_path=args.registry)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0)

    parser.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
