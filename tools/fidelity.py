#!/usr/bin/env python3
"""Source-to-candidate fidelity gate (issue #90).

A Patina-style executable edit contract: prove a repair kept the source's
meaning before accepting it. Five phases:

  1. extract   -- record protected spans and semantic anchors from the source
  2. repair    -- the caller edits only the named hot zones (recorded finding
                  spans, available from finding_spans() or the report)
  3. compare   -- compare the candidate with the source span by span
  4. rescan    -- rescore the repaired rules and measure edit churn
  5. gate      -- accept, retry within a bound, or roll back to the source

Protected spans (number, date, unit, operator, url, path, quoted, code_block,
required_term) fail closed when changed unless explicitly authorized.
Semantic anchors (negation, polarity, modality, quantifier, causality,
condition, scope, attribution, name) produce a hard failure or a named
human-review state. The report is JSON and keeps hard preservation failures
separate from advisory style findings. Stylometric measures are advisory only
and never authorship evidence.

Standard library only. No Patina service, payment, model backend, persona
catalog, or detector claim is involved.

Usage:
    python3 tools/fidelity.py --source-text "..." --candidate-text "..."
    python3 tools/fidelity.py --source before.txt --candidate after.txt
    python3 tools/fidelity.py --help
"""

import argparse
import bisect
import difflib
import heapq
import itertools
import json
import os
import re
import sys

import limits
from registry import load_registry
import score as scoring

DEFAULT_PROFILE = "general"

NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.])\d+(?:,\d{3})*(?:\.\d+)?%?")

DATE_RE = re.compile(
    r"(?<![A-Za-z0-9])\d{4}[-/]\d{1,2}[-/]\d{1,2}(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|"
    r"Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}(?![A-Za-z0-9])"
)

OPERATOR_RE = re.compile(r"<=|>=|!=|==|&&|\|\||[+*/]|(?<=\d)-(?=\d)")

URL_RE = re.compile(
    r"\bhttps?://[^\s<>\"']+"
    r"|\bftp://[^\s<>\"']+"
    r"|\bwww\.[A-Za-z0-9_.\-]+"
)

PATH_RE = re.compile(
    r"(?:[A-Za-z0-9_.\-]+/){2,}[A-Za-z0-9_.\-]*(?:/[^\s<>\"']*)?"
    r"|(?<![A-Za-z0-9_.\-])/(?:[A-Za-z0-9_.\-]+/)*[A-Za-z0-9_.\-]+"
    r"|(?<![A-Za-z0-9_.\-])(?!(?:and|or|either)/)"
    r"(?:[A-Za-z0-9_.\-]+/)+[A-Za-z0-9_.\-]+"
    r"|\.[/][^\s<>\"']+"
    r"|~/[^\s<>\"']+"
    r"|\b[A-Za-z]:[\\/][^\s<>\"']+"
)

QUOTED_RE = re.compile(
    r'"[^"\n]*"|\'[^\'\n]*\'|“[^”\n]*”|‘[^’\n]*’|`[^`\n]*`'
)

CODE_FENCE_RE = re.compile(
    r"(?ms)^`{3,}[^\n]*\n.*?^`{3,}[ \t]*$"
    r"|^~{3,}[^\n]*\n.*?^~{3,}[ \t]*$"
)

UNITS = {
    "ms", "sec", "secs", "second", "seconds",
    "millisecond", "milliseconds", "microsecond", "microseconds",
    "nanosecond", "nanoseconds",
    "min", "mins", "minute", "minutes",
    "hr", "hrs", "hour", "hours", "day", "days", "week", "weeks",
    "month", "months", "yr", "yrs", "year", "years",
    "kb", "mb", "gb", "tb", "pb", "bit", "bits", "byte", "bytes",
    "kib", "mib", "gib", "tib",
    "bps", "kbps", "mbps", "gbps", "tbps",
    "hz", "khz", "mhz", "ghz", "thz",
    "px", "em", "rem", "vh", "vw", "vmin", "vmax", "dpi", "ppi",
    "usd", "eur", "gbp", "aud", "cad", "jpy",
    "cm", "mm", "km", "mi", "mile", "miles",
    "ft", "foot", "feet", "inch", "inches", "mph", "kmh",
    "kg", "mg", "g", "lb", "lbs", "oz",
    "qps", "rps", "tps", "rpm", "percent", "percentage",
}

NEGATION_RE = re.compile(
    r"\b(?:not|no|never|none|nobody|nothing|nowhere|without|neither|nor|"
    r"isn't|isnt|aren't|arent|wasn't|wasnt|weren't|werent|don't|dont|"
    r"doesn't|doesnt|didn't|didnt|can't|cant|cannot|won't|wont|wouldn't|"
    r"wouldnt|couldn't|couldnt|shouldn't|shouldnt|mustn't|mustnt|hasn't|"
    r"hasnt|haven't|havent|hadn't|hadnt)\b"
)

POLARITY_RE = re.compile(
    r"\b(?:increase|increases|increased|increasing|decrease|decreases|"
    r"decreased|decreasing|rise|rises|rose|rising|fall|falls|fell|falling|"
    r"grow|grows|grew|growing|shrink|shrinks|shrank|shrinking|reduce|"
    r"reduces|reduced|reducing|cut|cuts|cutting|double|doubles|doubled|"
    r"doubling|improve|improves|improved|improving|worsen|worsens|worsened|"
    r"worsening|positive|negative|more|less|higher|lower|greater|fewer)\b"
)

MODALITY_RE = re.compile(
    r"\b(?:may|might|can|could|will|would|shall|should|must|ought|need to|"
    r"have to|has to)\b"
)

QUANTIFIER_RE = re.compile(
    r"\b(?:all|some|any|every|each|many|most|few|several|none|both|neither|"
    r"plenty|at least|at most|no more than|no less than|up to|over|under|"
    r"more than|less than)\b"
)

CAUSALITY_RE = re.compile(
    r"\b(?:because|therefore|thus|hence|consequently|leads? to|led to|"
    r"results? in|results? from|caused|causes|causing|cause|so that)\b"
)

CONDITION_RE = re.compile(
    r"\b(?:if|unless|provided that|as long as|given that|assuming|whenever)\b"
)

SCOPE_RE = re.compile(
    r"\b(?:up to|at most|no more than|at least|no less than|approximately|"
    r"about|roughly|nearly|more than|less than|over|under|within|exactly)\b"
)

NAME_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}(?:[0-9]+)?\b")

ATTR_PATTERNS = [
    (re.compile(
        r"\b[Aa]ccording to\s+[A-Z][A-Za-z0-9']+(?:\s+[A-Z][A-Za-z0-9']+)?"),
     "attribution"),
    (re.compile(
        r"\breported by\s+[A-Z][A-Za-z0-9']+(?:\s+[A-Z][A-Za-z0-9']+)?"),
     "attribution"),
    (re.compile(
        r"\bper\s+[A-Z][A-Za-z0-9']+(?:\s+[A-Z][A-Za-z0-9']+)?"),
     "attribution"),
    (re.compile(
        r"\b[A-Z][A-Za-z0-9']+\s+(?:said|reported|stated|claimed|argued|"
        r"wrote|noted|highlighted)"),
     "attribution"),
]

ANCHOR_ORDER = ("negation", "polarity", "modality", "quantifier", "causality",
                "condition", "scope", "attribution", "name")
ANCHOR_PATTERNS = [
    ("negation", NEGATION_RE),
    ("polarity", POLARITY_RE),
    ("modality", MODALITY_RE),
    ("quantifier", QUANTIFIER_RE),
    ("causality", CAUSALITY_RE),
    ("condition", CONDITION_RE),
    ("scope", SCOPE_RE),
]

PROTECTED_ORDER = ("code_block", "quoted", "url", "path", "required_term",
                   "date", "unit", "number", "operator")
PROTECTED_PRIORITY = {category: index for index, category in
                      enumerate(PROTECTED_ORDER)}
CANONICAL_CATEGORIES = {"number", "date", "unit", "operator"}
MAX_DIFF_WORK = 1_000_000


def _canonical(category, value):
    if category == "number":
        return value.replace("%", "").replace(",", "").strip()
    if category == "date":
        normalized = re.sub(r"[,./]", "-", value.lower())
        return re.sub(r"\s+", " ", normalized).strip()
    if category == "unit":
        return value.lower().strip()
    if category == "operator":
        return re.sub(r"\s+", "", value)
    return value


def _overlaps(a, b):
    return a["start"] < b["end"] and b["start"] < a["end"]


def _same_span(a, b):
    return (a["category"] == b["category"] and a["start"] == b["start"]
            and a["end"] == b["end"] and a["value"] == b["value"])


def _overlaps_sorted(span, intervals, starts):
    """Check overlap in disjoint start-sorted intervals in logarithmic time."""
    index = bisect.bisect_left(starts, span["end"]) - 1
    return index >= 0 and intervals[index]["end"] > span["start"]


def _extract_protected_spans(text, required_terms=()):
    spans = []

    def add(category, start, end, value):
        spans.append({
            "category": category,
            "start": start,
            "end": end,
            "value": value,
            "canonical": _canonical(category, value),
        })

    for match in CODE_FENCE_RE.finditer(text):
        add("code_block", match.start(), match.end(), match.group(0))
    for match in QUOTED_RE.finditer(text):
        add("quoted", match.start(), match.end(), match.group(0))
    for match in URL_RE.finditer(text):
        add("url", match.start(), match.end(), match.group(0))
    for match in PATH_RE.finditer(text):
        add("path", match.start(), match.end(), match.group(0))
    for term in required_terms:
        if not term:
            continue
        pattern = r"\b" + re.escape(term) + r"\b"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            add("required_term", match.start(), match.end(), match.group(0))
    for match in DATE_RE.finditer(text):
        add("date", match.start(), match.end(), match.group(0))
    for match in re.finditer(r"[A-Za-z]+", text):
        token = match.group(0)
        if token.lower() in UNITS:
            add("unit", match.start(), match.end(), token)
    for match in NUMBER_RE.finditer(text):
        add("number", match.start(), match.end(), match.group(0))
    for match in OPERATOR_RE.finditer(text):
        add("operator", match.start(), match.end(), match.group(0))

    spans.sort(key=lambda span: (PROTECTED_PRIORITY[span["category"]],
                                 span["start"], span["end"]))
    kept = []
    kept_starts = []
    for _priority, group in itertools.groupby(
            spans, key=lambda span: PROTECTED_PRIORITY[span["category"]]):
        accepted = []
        for span in group:
            if _overlaps_sorted(span, kept, kept_starts):
                continue
            if accepted and span["start"] < accepted[-1]["end"]:
                continue
            accepted.append(span)
        if accepted:
            kept = list(heapq.merge(kept, accepted,
                                    key=lambda span: span["start"]))
            kept_starts = [span["start"] for span in kept]
    return kept


def _extract_semantic_anchors(text, protected_spans):
    anchors = []

    def add(category, start, end, value):
        anchors.append({
            "category": category,
            "start": start,
            "end": end,
            "value": value,
            "canonical": value,
        })

    for category, pattern in ANCHOR_PATTERNS:
        for match in pattern.finditer(text):
            add(category, match.start(), match.end(), match.group(0).lower())
    for match in NAME_ACRONYM_RE.finditer(text):
        add("name", match.start(), match.end(), match.group(0))
    for pattern, category in ATTR_PATTERNS:
        for match in pattern.finditer(text):
            add(category, match.start(), match.end(), match.group(0))

    kept = []
    protected_starts = [span["start"] for span in protected_spans]
    seen = set()
    for anchor in anchors:
        if _overlaps_sorted(anchor, protected_spans, protected_starts):
            continue
        identity = (anchor["category"], anchor["start"], anchor["end"],
                    anchor["value"])
        if identity in seen:
            continue
        seen.add(identity)
        kept.append(anchor)
    kept.sort(key=lambda anchor: anchor["start"])
    return kept


def extract_anchors(text, required_terms=()):
    """Phase 1: extract protected spans and semantic anchors from text."""
    protected_spans = _extract_protected_spans(text, required_terms)
    semantic_anchors = _extract_semantic_anchors(text, protected_spans)
    return {"protected_spans": protected_spans,
            "semantic_anchors": semantic_anchors}


def _group_by_category(spans):
    groups = {}
    for span in spans:
        groups.setdefault(span["category"], []).append(span)
    return groups


def _linear_opcodes(source, candidate):
    """Return conservative opcodes without comparing every possible pair."""
    if len(source) == len(candidate):
        opcodes = []
        run_start = 0
        run_tag = None
        for index, (source_item, candidate_item) in enumerate(
                zip(source, candidate)):
            tag = "equal" if source_item == candidate_item else "replace"
            if run_tag is None:
                run_tag = tag
            elif tag != run_tag:
                opcodes.append((run_tag, run_start, index,
                                run_start, index))
                run_start = index
                run_tag = tag
        if run_tag is not None:
            opcodes.append((run_tag, run_start, len(source),
                            run_start, len(candidate)))
        return opcodes

    prefix = 0
    shared = min(len(source), len(candidate))
    while prefix < shared and source[prefix] == candidate[prefix]:
        prefix += 1

    suffix = 0
    remaining = shared - prefix
    while (suffix < remaining
           and source[len(source) - suffix - 1]
           == candidate[len(candidate) - suffix - 1]):
        suffix += 1

    opcodes = []
    if prefix:
        opcodes.append(("equal", 0, prefix, 0, prefix))
    source_end = len(source) - suffix
    candidate_end = len(candidate) - suffix
    if prefix < source_end or prefix < candidate_end:
        if prefix == source_end:
            tag = "insert"
        elif prefix == candidate_end:
            tag = "delete"
        else:
            tag = "replace"
        opcodes.append((tag, prefix, source_end, prefix, candidate_end))
    if suffix:
        opcodes.append(("equal", source_end, len(source),
                        candidate_end, len(candidate)))
    return opcodes


def _bounded_opcodes(source, candidate):
    if len(source) * len(candidate) > MAX_DIFF_WORK:
        return _linear_opcodes(source, candidate)
    return difflib.SequenceMatcher(
        None, source, candidate, autojunk=False).get_opcodes()


def _compare_sequences(source_items, candidate_items, use_canonical):
    def key(span):
        return span["canonical"] if use_canonical else span["value"]

    source_values = [key(span) for span in source_items]
    candidate_values = [key(span) for span in candidate_items]
    unchanged = []
    changed = []
    removed = []
    added = []
    for tag, i1, i2, j1, j2 in _bounded_opcodes(
            source_values, candidate_values):
        if tag == "equal":
            unchanged.extend(source_items[i1:i2])
        elif tag == "replace":
            paired = min(i2 - i1, j2 - j1)
            for offset in range(paired):
                changed.append({
                    "source": source_items[i1 + offset],
                    "candidate": candidate_items[j1 + offset],
                })
            removed.extend(source_items[i1 + paired:i2])
            added.extend(candidate_items[j1 + paired:j2])
        elif tag == "delete":
            removed.extend(source_items[i1:i2])
        elif tag == "insert":
            added.extend(candidate_items[j1:j2])
    return {"unchanged": unchanged, "changed": changed,
            "removed": removed, "added": added}


def _matches_authorization(change, authorizations):
    span = change["source"]
    candidate = change["candidate"]
    for authorization in authorizations:
        if authorization.get("category") != span["category"]:
            continue
        if authorization.get("from") and authorization["from"] not in (
                span["value"], span["canonical"]):
            continue
        if authorization.get("to") and authorization["to"] not in (
                candidate["value"], candidate["canonical"]):
            continue
        return authorization
    return None


def _in_any_hot_zone(span, hot_zones):
    return any(span["start"] < zone["end"] and zone["start"] < span["end"]
               for zone in hot_zones)


def _dedupe_entries(entries):
    seen = set()
    result = []
    for entry in entries:
        key = (entry.get("category"), entry.get("source"),
               entry.get("candidate"))
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def finding_spans(text, registry, profile=DEFAULT_PROFILE):
    """Recorded finding spans in text, used as the named hot zones."""
    raw_findings, _skipped, _metrics = scoring.detect_findings(
        text, registry, profile)
    findings = scoring.handle_overlaps(raw_findings)
    spans = []
    for finding in findings:
        if not finding.get("primary", True):
            continue
        start = finding["position"]
        end = start + finding.get("match_length", 6)
        spans.append({"start": start, "end": end,
                      "label": finding["rule_id"]})
    return spans


def _churn(source, candidate):
    if source == candidate:
        return 0
    touched = 0
    for tag, i1, i2, j1, j2 in _bounded_opcodes(source, candidate):
        if tag == "equal":
            continue
        source_len = i2 - i1
        candidate_len = j2 - j1
        if tag == "replace":
            touched += max(source_len, candidate_len)
        elif tag == "delete":
            touched += source_len
        elif tag == "insert":
            touched += candidate_len
    return touched


def _stylometrics(text):
    words = re.findall(r"[A-Za-z0-9']+", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        sentences = [text]
    sentence_words = [len(re.findall(r"[A-Za-z0-9']+", sentence))
                      for sentence in sentences]
    average = sum(sentence_words) / len(sentence_words)
    unique = len({word.lower() for word in words}) / len(words) if words else 0
    punctuation = sum(1 for char in text if char in ".,;:!?()[]{}\"'")
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "avg_words_per_sentence": round(average, 2),
        "unique_word_ratio": round(unique, 3),
        "punctuation_density": round(punctuation / max(1, len(text)), 4),
    }


def stylometrics(text):
    """Public wrapper for the advisory rhythm measures.

    Sentence length and lexical-repetition statistics are advisory signals
    reported separately by the bounded repair loop (repair_loop.py); they
    never decide whether a passage is human.
    """
    return _stylometrics(text)


def check_fidelity(source, candidate, *, required_terms=(),
                   authorized_changes=(), hot_zones=None, churn_limit=0.5,
                   churn_multiplier=3.0,
                   human_review_categories=("attribution", "name"),
                   registry_path="rules.json", profile=DEFAULT_PROFILE):
    """Phase 3 + 4 + 5: compare source and candidate, return the JSON report.

    Returns a dict serializable to JSON. Decisions: accept, reject, or review.
    """
    limits.check_input_size(source, "source")
    limits.check_input_size(candidate, "candidate")
    registry = load_registry(registry_path)
    version = registry.get("version", "unknown")

    source_extract = extract_anchors(source, required_terms)
    candidate_extract = extract_anchors(candidate, required_terms)

    if hot_zones is None:
        hot_zones = finding_spans(source, registry, profile)
    hot_zones = [{"start": int(zone["start"]), "end": int(zone["end"]),
                  "label": zone.get("label")} for zone in hot_zones]

    source_by_category = _group_by_category(source_extract["protected_spans"])
    candidate_by_category = _group_by_category(candidate_extract["protected_spans"])

    protected_result = {
        "total": len(source_extract["protected_spans"]),
        "byte_identical": 0,
        "changed": [],
        "removed": [],
        "added": [],
        "authorized": [],
        "unchanged_by_category": {},
    }
    hard_failures = []

    for category in PROTECTED_ORDER:
        source_items = source_by_category.get(category, [])
        candidate_items = candidate_by_category.get(category, [])
        use_canonical = category in CANONICAL_CATEGORIES
        comparison = _compare_sequences(source_items, candidate_items,
                                        use_canonical)
        protected_result["byte_identical"] += len(comparison["unchanged"])
        protected_result["unchanged_by_category"][category] = len(
            comparison["unchanged"])

        for change in comparison["changed"]:
            authorization = _matches_authorization(change, authorized_changes)
            entry = {
                "category": category,
                "source": change["source"]["value"],
                "candidate": change["candidate"]["value"],
                "hot_zone": _in_any_hot_zone(change["source"], hot_zones),
            }
            if authorization:
                entry["authorized"] = True
                protected_result["authorized"].append(entry)
            else:
                protected_result["changed"].append(entry)
                hard_failures.append({
                    "kind": "protected_span_changed",
                    "category": category,
                    "source": entry["source"],
                    "candidate": entry["candidate"],
                    "hot_zone": entry["hot_zone"],
                })
        for span in comparison["removed"]:
            in_zone = _in_any_hot_zone(span, hot_zones)
            protected_result["removed"].append({
                "category": category, "source": span["value"],
                "hot_zone": in_zone,
            })
            hard_failures.append({
                "kind": "protected_span_removed",
                "category": category, "source": span["value"],
                "hot_zone": in_zone,
            })
        protected_result["added"].extend({
            "category": category, "value": span["value"],
        } for span in comparison["added"])

    protected_result["changed"] = _dedupe_entries(protected_result["changed"])
    protected_result["authorized"] = _dedupe_entries(protected_result["authorized"])
    protected_result["removed"] = _dedupe_entries(protected_result["removed"])

    source_anchors = _group_by_category(source_extract["semantic_anchors"])
    candidate_anchors = _group_by_category(candidate_extract["semantic_anchors"])

    anchor_result = {
        "total": len(source_extract["semantic_anchors"]),
        "unchanged": 0,
        "hard_failure": [],
        "human_review": [],
        "authorized": [],
        "added": [],
        "unchanged_by_category": {},
    }
    review_items = []

    for category in ANCHOR_ORDER:
        source_items = source_anchors.get(category, [])
        candidate_items = candidate_anchors.get(category, [])
        comparison = _compare_sequences(source_items, candidate_items, True)
        anchor_result["unchanged"] += len(comparison["unchanged"])
        anchor_result["unchanged_by_category"][category] = len(
            comparison["unchanged"])

        for change in comparison["changed"]:
            authorization = _matches_authorization(change, authorized_changes)
            entry = {
                "category": category,
                "source": change["source"]["value"],
                "candidate": change["candidate"]["value"],
            }
            if authorization:
                anchor_result["authorized"].append(dict(entry,
                                                        authorized=True))
            elif category in human_review_categories:
                anchor_result["human_review"].append(entry)
                review_items.append(entry)
            else:
                anchor_result["hard_failure"].append(entry)
                hard_failures.append({
                    "kind": "semantic_anchor_changed",
                    "category": category,
                    "source": entry["source"],
                    "candidate": entry["candidate"],
                })
        for span in comparison["removed"]:
            entry = {"category": category, "source": span["value"],
                     "candidate": None}
            if category in human_review_categories:
                anchor_result["human_review"].append(entry)
                review_items.append(entry)
            else:
                anchor_result["hard_failure"].append(entry)
                hard_failures.append({
                    "kind": "semantic_anchor_removed",
                    "category": category, "source": span["value"],
                })
        for span in comparison["added"]:
            entry = {"category": category, "source": None,
                     "candidate": span["value"]}
            anchor_result["added"].append(entry)
            if category in human_review_categories:
                anchor_result["human_review"].append(entry)
                review_items.append(entry)
            else:
                anchor_result["hard_failure"].append(entry)
                hard_failures.append({
                    "kind": "semantic_anchor_added",
                    "category": category, "candidate": span["value"],
                })

    anchor_result["hard_failure"] = _dedupe_entries(
        anchor_result["hard_failure"])
    anchor_result["human_review"] = _dedupe_entries(
        anchor_result["human_review"])

    touched = _churn(source, candidate)
    source_length = max(1, len(source))
    churn_ratio = touched / source_length
    justified_chars = sum(max(0, int(zone["end"]) - int(zone["start"]))
                          for zone in hot_zones)
    justified_ratio = justified_chars / source_length
    justified_budget = justified_ratio * churn_multiplier
    exceeds_limit = churn_limit is not None and churn_ratio > churn_limit
    exceeds_justified = bool(hot_zones) and churn_ratio > justified_budget

    integrity_failures = []
    integrity_status = "passed"
    if exceeds_limit:
        integrity_failures.append({
            "kind": "churn_over_limit",
            "churn_ratio": round(churn_ratio, 4),
            "limit": churn_limit,
        })
        integrity_status = "failed"
    if exceeds_justified:
        integrity_failures.append({
            "kind": "churn_over_justification",
            "churn_ratio": round(churn_ratio, 4),
            "justified_budget": round(justified_budget, 4),
        })
        integrity_status = "failed"

    source_score = None
    candidate_score = None
    source_findings = []
    candidate_findings = []
    try:
        source_score = scoring.score_text(source, registry, profile)
        candidate_score = scoring.score_text(candidate, registry, profile)
    except Exception:  # noqa: BLE001  -- the gate never blocks on scoring
        source_score = None
        candidate_score = None

    if source_score is not None:
        source_findings = [
            {"rule_id": finding["rule_id"], "severity": finding["severity"],
             "weight": finding["weight"]}
            for finding in source_score["findings"]
        ]
    if candidate_score is not None:
        candidate_findings = [
            {"rule_id": finding["rule_id"], "severity": finding["severity"],
             "weight": finding["weight"]}
            for finding in candidate_score["findings"]
        ]

    risk = {
        "source_score": source_score["score"] if source_score else None,
        "candidate_score": candidate_score["score"] if candidate_score else None,
        "delta": None,
        "improved": False,
        "source_findings": source_findings,
        "candidate_findings": candidate_findings,
        "hot_zones": hot_zones,
    }
    if risk["source_score"] is not None and risk["candidate_score"] is not None:
        risk["delta"] = risk["candidate_score"] - risk["source_score"]
        risk["improved"] = risk["delta"] > 0

    if hard_failures or integrity_failures:
        decision = "reject"
        categories = sorted({failure["category"]
                             for failure in hard_failures if "category" in failure})
        reasons = []
        if hard_failures:
            reasons.append("preservation failed on %s" % ", ".join(categories))
        if integrity_failures:
            reasons.append("integrity failed on edit churn")
        reason = "; ".join(reasons)
    elif review_items:
        decision = "review"
        reason = "human review required for changed semantic anchors"
    else:
        decision = "accept"
        reason = "protected content preserved and edit churn within budget"

    report = {
        "interface": "antislop.fidelity",
        "schema": "fidelity-report-1",
        "version": version,
        "decision": decision,
        "reason": reason,
        "risk": risk,
        "preservation": {
            "status": ("failed" if hard_failures else
                       "review" if review_items else "passed"),
            "hard_failures": hard_failures,
            "human_review": review_items,
            "protected_spans": protected_result,
            "semantic_anchors": anchor_result,
        },
        "integrity": {
            "status": integrity_status,
            "hot_zone_count": len(hot_zones),
            "churn": {
                "touched_chars": touched,
                "source_chars": len(source),
                "ratio": round(churn_ratio, 4),
                "limit": churn_limit,
                "justified_ratio": round(justified_ratio, 4),
                "justified_budget": round(justified_budget, 4),
                "exceeds_limit": exceeds_limit,
                "exceeds_justification": exceeds_justified,
            },
            "failures": integrity_failures,
        },
        "review": {
            "status": "unresolved" if review_items else "none",
            "items": review_items,
        },
        "meta": {
            "stylometrics": {
                "advisory": True,
                "authorship_evidence": False,
                "disclaimer": "Stylometric measures are advisory only and "
                              "never authorship evidence.",
                "source": _stylometrics(source),
                "candidate": _stylometrics(candidate),
            },
            "required_terms": list(required_terms),
        },
    }
    return report


def apply_repairs(source, repair, *, max_retries=2, registry_path="rules.json",
                  profile=DEFAULT_PROFILE, **check_kwargs):
    """Phase 2 + 5 loop: repair only named hot zones, bounded retries.

    Each attempt calls repair(source, attempt, hot_zones) and runs the
    fidelity check on the returned candidate. accept and review are terminal;
    reject retries up to max_retries; a failed final candidate rolls back to
    the source (decision "rollback", text equal to source).
    """
    limits.check_input_size(source, "source")
    max_retries = max(1, int(max_retries))
    if check_kwargs.get("hot_zones") is None:
        registry = load_registry(registry_path)
        check_kwargs["hot_zones"] = finding_spans(source, registry, profile)

    attempts = []
    last_report = None
    candidate = source
    for attempt in range(max_retries):
        candidate = repair(source, attempt, check_kwargs["hot_zones"])
        report = check_fidelity(source, candidate, registry_path=registry_path,
                                profile=profile, **check_kwargs)
        attempts.append({
            "attempt": attempt + 1,
            "decision": report["decision"],
            "reason": report["reason"],
        })
        if report["decision"] in ("accept", "review"):
            report["text"] = candidate
            report["attempts"] = attempts
            return report
        last_report = report

    rollback = dict(last_report)
    rollback["decision"] = "rollback"
    rollback["reason"] = "retries exhausted; rolled back to the source"
    rollback["text"] = source
    rollback["attempts"] = attempts
    return rollback


def main():
    parser = argparse.ArgumentParser(
        description="Antislop source-to-candidate fidelity gate")
    parser.add_argument("--source-text", default=None, help="Source text")
    parser.add_argument("--candidate-text", default=None, help="Candidate text")
    parser.add_argument("--source", default=None, help="Path to source file")
    parser.add_argument("--candidate", default=None, help="Path to candidate file")
    parser.add_argument("--required-term", action="append", default=[],
                        help="Required term (repeatable)")
    parser.add_argument("--authorize", action="append", default=[],
                        help="Authorized change, category or category=to")
    parser.add_argument("--hot-zone", action="append", default=[],
                        help="Hot zone start-end (repeatable)")
    parser.add_argument("--churn-limit", type=float, default=0.5,
                        help="Maximum edit churn ratio (default: 0.5)")
    parser.add_argument("--registry", default="rules.json")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    args = parser.parse_args()

    if args.source_text is not None:
        try:
            source = limits.check_input_size(args.source_text, "source")
        except ValueError as exc:
            parser.error(str(exc))
    elif args.source:
        try:
            source = limits.read_text_file(args.source, "source")
        except ValueError as exc:
            parser.error(str(exc))
    else:
        parser.error("Provide --source-text or --source")

    if args.candidate_text is not None:
        try:
            candidate = limits.check_input_size(
                args.candidate_text, "candidate")
        except ValueError as exc:
            parser.error(str(exc))
    elif args.candidate:
        try:
            candidate = limits.read_text_file(args.candidate, "candidate")
        except ValueError as exc:
            parser.error(str(exc))
    else:
        parser.error("Provide --candidate-text or --candidate")

    authorized = []
    for spec in args.authorize:
        if "=" in spec:
            category, value = spec.split("=", 1)
            authorized.append({"category": category, "to": value})
        else:
            authorized.append({"category": spec})

    hot_zones = []
    for spec in args.hot_zone:
        start_text, end_text = spec.split("-", 1)
        hot_zones.append({"start": int(start_text), "end": int(end_text),
                          "label": "cli"})

    report = check_fidelity(
        source, candidate,
        required_terms=args.required_term,
        authorized_changes=authorized,
        hot_zones=hot_zones or None,
        churn_limit=args.churn_limit,
        registry_path=args.registry,
        profile=args.profile,
    )
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["decision"] == "accept" else 1)


if __name__ == "__main__":
    main()
