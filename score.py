#!/usr/bin/env python3
"""Antislop scoring engine.

Calculates the Formulaic Writing Risk Score from text using the rule
registry. Supports profile filtering, diminishing repetition, overlap
handling, and 500-word normalization.

Usage:
    echo "text" | python3 score.py --profile general
    python3 score.py --profile general --stdin < file.txt
    python3 score.py --profile technical --file input.txt
    python3 score.py --help

Output: JSON with score, band, findings, metadata.
"""

import argparse
import json
import math
import os
import re
import sys


def load_registry(path="rules.json"):
    with open(path) as f:
        return json.load(f)


def filter_rules_by_profile(rules, profile):
    """Return rules active in the given profile."""
    active = []
    for rule in rules:
        rule_profiles = rule.get("profiles", ["general"])
        if "*" in rule_profiles or profile in rule_profiles:
            active.append(rule)
    return active


def count_words(text):
    """Count words in text."""
    return len(text.split())


def find_exact_matches(text, rule):
    """Find exact word matches for a rule in text."""
    pattern = r'\b' + re.escape(rule["text"]) + r'\b'
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    return matches


def find_phrase_matches(text, rule):
    """Find phrase matches for a rule in text."""
    phrase = rule["text"]
    # Handle compound phrases with /
    parts = [p.strip() for p in phrase.split("/")]
    for part in parts:
        # Escape for regex, handle [X] placeholders
        escaped = re.escape(part)
        escaped = escaped.replace(r'\[X\]', r'.+?')
        escaped = escaped.replace(r'\[N\]', r'\w+')
        pattern = escaped
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            return matches
    return []


def detect_findings(text, rules, profile):
    """Detect all findings in text against the active rules."""
    active_rules = filter_rules_by_profile(rules, profile)
    findings = []

    for rule in active_rules:
        detection = rule.get("detection_class", "exact_match")

        if detection == "exact_match":
            matches = find_exact_matches(text, rule)
        elif detection == "phrase_match":
            matches = find_phrase_matches(text, rule)
        elif detection in ("pattern_match", "structural"):
            # For structural/pattern rules, we rely on the text containing
            # indicative patterns. Simplified detection for now.
            continue
        else:
            continue

        for match in matches:
            start = match.start()
            match_len = match.end() - match.start()
            excerpt = text[max(0, start - 20):min(len(text), match.end() + 20)]
            excerpt = excerpt.strip()
            if excerpt and not excerpt.startswith((" ", "\t")):
                excerpt = "..." + excerpt
            if excerpt and not excerpt.endswith((" ", "\t")):
                excerpt = excerpt + "..."
            findings.append({
                "rule_id": rule["id"],
                "category": rule["category"],
                "severity": rule["severity"],
                "base_weight": rule["base_weight"],
                "excerpt": excerpt,
                "position": start,
                "match_length": match_len,
            })

    return findings


def handle_overlaps(findings):
    """Assign primary/related status to overlapping findings.

    When multiple rules fire on the same text span (overlapping character
    ranges), one becomes primary (scored) and the rest become related
    (unscored). Findings at non-overlapping positions remain independent.
    """
    if not findings:
        return findings

    # Sort by position
    findings.sort(key=lambda f: f["position"])

    # Group findings whose character ranges overlap
    # Each finding has a position (start) and we estimate end from excerpt length
    spans = []
    current_span = [findings[0]]

    for finding in findings[1:]:
        # Check if this finding's position overlaps with any in the current span
        overlap = False
        for existing in current_span:
            ml = existing.get("match_length", 6)
            est_end_existing = existing["position"] + ml
            ml_new = finding.get("match_length", 6)
            est_end_new = finding["position"] + ml_new
            if finding["position"] < est_end_existing and existing["position"] < est_end_new:
                overlap = True
                break

        if overlap:
            current_span.append(finding)
        else:
            spans.append(current_span)
            current_span = [finding]
    spans.append(current_span)

    result = []
    for span in spans:
        if len(span) == 1:
            span[0]["primary"] = True
            span[0]["related"] = []
            result.append(span[0])
        else:
            # Primary: highest severity, then longest rule text
            severity_order = {"high": 0, "medium": 1, "low": 2}
            span.sort(key=lambda f: (severity_order.get(f["severity"], 9),
                                      -len(f["rule_id"])))
            primary = span[0]
            primary["primary"] = True
            primary["related"] = [f["rule_id"] for f in span[1:]]
            result.append(primary)

            for related in span[1:]:
                related["primary"] = False
                related["related"] = []
                result.append(related)

    return result


def apply_diminishing_repetition(findings):
    """Apply diminishing weights to repeated rule instances.

    First instance: 100% of base weight
    Second instance: 50% of base weight
    Third+ instance: 25% of base weight
    Cap: 3x base weight per rule
    """
    rule_counts = {}
    for finding in findings:
        if not finding.get("primary", True):
            finding["weight"] = 0
            continue

        rule_id = finding["rule_id"]
        count = rule_counts.get(rule_id, 0) + 1
        rule_counts[rule_id] = count

        base = finding["base_weight"]
        if count == 1:
            weight = base
        elif count == 2:
            weight = base * 0.5
        else:
            weight = base * 0.25

        # Cap at 3x base weight
        current_total = sum(
            f.get("weight", 0) for f in findings
            if f["rule_id"] == rule_id and f.get("primary", True)
        )
        if current_total + weight > base * 3:
            weight = max(0, base * 3 - current_total)

        finding["weight"] = weight

    return findings


def normalize_to_500(total_penalty, word_count):
    """Normalize penalty to 500-word reference length."""
    if word_count == 0:
        return total_penalty
    return total_penalty * (500.0 / word_count)


def calculate_score(findings, word_count):
    """Calculate the final score from findings and word count."""
    total = sum(f.get("weight", 0) for f in findings)
    normalized = normalize_to_500(total, word_count)
    score = max(0, round(100 - normalized))
    return score


def score_to_band(score, bands):
    """Map score to band label."""
    for band_name, band_info in bands.items():
        if band_info["min"] <= score <= band_info["max"]:
            return band_info["label"]
    return "Unknown"


def score_text(text, registry, profile="general"):
    """Score text and return structured output."""
    rules = registry.get("rules", [])
    bands = registry.get("score_bands", {})
    word_count = count_words(text)

    # Detect findings
    raw_findings = detect_findings(text, rules, profile)

    # Handle overlaps
    findings = handle_overlaps(raw_findings)

    # Apply diminishing repetition
    findings = apply_diminishing_repetition(findings)

    # Calculate score
    total_penalty = sum(f.get("weight", 0) for f in findings)
    normalized = normalize_to_500(total_penalty, word_count)
    score = max(0, round(100 - normalized))
    band = score_to_band(score, bands)

    # Calculate density (findings per 500 words)
    primary_count = sum(1 for f in findings if f.get("primary", True))
    density = (primary_count / word_count * 500) if word_count > 0 else 0

    # Build output
    output_findings = []
    for f in findings:
        output_findings.append({
            "rule_id": f["rule_id"],
            "category": f["category"],
            "severity": f["severity"],
            "weight": f.get("weight", 0),
            "excerpt": f["excerpt"],
            "reason": f"Detected {f['category']} pattern: {f['rule_id']}",
            "primary": f.get("primary", True),
            "related": f.get("related", []),
        })

    return {
        "score": score,
        "band": band,
        "word_count": word_count,
        "density": round(density, 2),
        "profile": profile,
        "findings": output_findings,
        "metadata": {
            "version": registry.get("version", "unknown"),
            "total_penalty": round(total_penalty, 2),
            "normalized_penalty": round(normalized, 2),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Antislop scoring engine"
    )
    parser.add_argument(
        "--profile", default="general",
        help="Writing profile (default: general)"
    )
    parser.add_argument(
        "--registry", default="rules.json",
        help="Path to rule registry (default: rules.json)"
    )
    parser.add_argument(
        "--file", default=None,
        help="Read text from file instead of stdin"
    )
    parser.add_argument(
        "--stdin", action="store_true",
        help="Read text from stdin"
    )
    args = parser.parse_args()

    if not os.path.exists(args.registry):
        print(json.dumps({"error": f"Registry not found: {args.registry}"}))
        sys.exit(2)

    registry = load_registry(args.registry)

    # Read text
    if args.file:
        with open(args.file) as f:
            text = f.read()
    elif args.stdin or not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print(json.dumps({"error": "No input. Use --file, --stdin, or pipe text."}))
        sys.exit(2)

    if not text.strip():
        print(json.dumps({"error": "Empty input"}))
        sys.exit(2)

    result = score_text(text, registry, args.profile)
    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
