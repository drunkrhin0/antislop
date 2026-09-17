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
import os
import re
import sys

import limits
from registry import load_registry, filter_rules_by_profile
from structural import DETECTORS, detect_rule as detect_structural_rule


# Only forbidden and discouraged rules deduct risk points. Preferred,
# structural, integrity, and evaluation rules carry guidance or metadata but
# never change the Formulaic Writing Risk Score.
SCORING_SEMANTIC_TYPES = {"forbidden", "discouraged"}


def rule_signal(rule):
    """Classify a rule's findings as strict or advisory.

    Deterministic review modes are strict (the pattern alone confirms the
    finding). Advisory and human review modes report a signal the reader must
    weigh against context; the executable never treats them as confirmed.
    """
    return "strict" if rule.get("review_mode") == "deterministic" else "advisory"


def count_words(text):
    """Count words in text."""
    return len(text.split())


def find_exact_matches(text, rule):
    """Find exact word matches for a rule in text."""
    pattern = r'\b' + re.escape(rule["text"]) + r'\b'
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    # Single-token vocabulary rules also match common inflections so the
    # detector does not miss "leveraging" when the rule bans "leverage".
    if " " not in rule["text"] and re.fullmatch(r"[A-Za-z]+", rule["text"]):
        base = rule["text"]
        stem = base[:-1] if base.endswith("e") else base
        inflected = {
            base + "s", base + "es", base + "ed", base + "d",
            base + "ing", base + "r", base + "st",
            stem + "ing", stem + "ed",
        }
        variants = "|".join(
            re.escape(variant) for variant in sorted(inflected, key=len, reverse=True)
            if variant != base
        )
        if variants:
            pattern = r'\b(?:' + variants + r')\b'
            seen = {match.start() for match in matches}
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if match.start() not in seen:
                    matches.append(match)
        matches.sort(key=lambda match: match.start())
    return matches


def find_phrase_matches(text, rule):
    """Find phrase matches for a rule in text."""
    phrase = rule["text"]
    # Handle compound phrases with /
    parts = [p.strip() for p in phrase.split("/")]
    matches_by_span = {}
    for part in parts:
        # Escape for regex, handle [X] placeholders
        escaped = re.escape(part)
        escaped = escaped.replace(r'\[X\]', r'.+?')
        escaped = escaped.replace(r'\[N\]', r'\w+')
        pattern = r'(?<!\w)' + escaped + r'(?!\w)'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches_by_span[(match.start(), match.end())] = match
    return sorted(matches_by_span.values(), key=lambda match: match.start())


def detect_findings(text, registry, profile):
    """Detect all findings in text against the active rules.

    Returns (findings, skipped_count, structural_metrics) where skipped_count
    is the number of active rules whose detection_class is not yet implemented
    (pattern_match, structural without a registered detector). The score
    output's metadata.skipped_rules field uses this to document coverage
    gaps. structural_metrics reports sample-size limits for detector metrics
    that could not measure the text.
    """
    active_rules = filter_rules_by_profile(registry, profile)
    findings = []
    skipped = 0
    structural_metrics = []

    for rule in active_rules:
        if rule.get("semantic_type", "forbidden") not in SCORING_SEMANTIC_TYPES:
            continue
        detection = rule.get("detection_class", "exact_match")

        if detection == "exact_match":
            matches = find_exact_matches(text, rule)
        elif detection == "phrase_match":
            matches = find_phrase_matches(text, rule)
        elif detection in ("pattern_match", "structural"):
            if rule.get("detector") in DETECTORS:
                detector_result = detect_structural_rule(text, rule, profile)
                structural_metrics.extend(detector_result.get("metrics", []))
                for f in detector_result.get("findings", []):
                    findings.append({
                        "rule_id": rule["id"],
                        "category": rule["category"],
                        "severity": rule["severity"],
                        "base_weight": rule["base_weight"],
                        "excerpt": f["excerpt"],
                        "position": f["start"],
                        "match_length": f["end"] - f["start"],
                        "start": f["start"],
                        "end": f["end"],
                        "message": f["message"],
                        "repair": f["repair"],
                        "signal": f["signal"],
                        "evidence": f["evidence"],
                        "profile": f.get("profile", profile),
                        "sample": f.get("sample", {}),
                    })
                continue
            skipped += 1
            continue
        else:
            skipped += 1
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
                "start": start,
                "end": start + match_len,
                "message": f"Detected {rule['category']} pattern: {rule['id']}",
                "repair": rule.get("correction", ""),
                "signal": rule_signal(rule),
                "evidence": "span",
                "sample": {},
            })

    return findings, skipped, structural_metrics


def handle_overlaps(findings):
    """Assign primary/related status to overlapping findings.

    When multiple rules fire on the same text span (overlapping character
    ranges), one becomes primary (scored) and the rest become related
    (unscored). Findings at non-overlapping positions remain independent.

    Grouping is by evidence kind: span-level findings overlap only other
    span-level findings, and document-level findings overlap only other
    document-level findings. A document-level metric covers a whole section
    and must not demote a specific-phrase finding inside that section to
    related, which would hide a concrete span under a broad signal.
    """
    if not findings:
        return findings

    # Sort by position
    findings.sort(key=lambda f: f["position"])

    # Group findings whose character ranges overlap. Evidence kind changes
    # start a new group, so span and document evidence never compete for the
    # same primary slot.
    spans = []
    current_span = [findings[0]]

    for finding in findings[1:]:
        kind = finding.get("evidence", "span")
        same_kind = all(existing.get("evidence", "span") == kind
                        for existing in current_span)
        # Check if this finding's position overlaps with any in the current span
        overlap = False
        if same_kind:
            for existing in current_span:
                ml = existing.get("match_length", 6)
                est_end_existing = existing["position"] + ml
                ml_new = finding.get("match_length", 6)
                est_end_new = finding["position"] + ml_new
                if finding["position"] < est_end_existing \
                        and existing["position"] < est_end_new:
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
            # Primary: strict over advisory, then highest severity, then
            # longest rule id. Strict findings keep their deduction when a
            # lower-severity or advisory signal overlaps the same span.
            severity_order = {"high": 0, "medium": 1, "low": 2}
            span.sort(key=lambda f: (0 if f.get("signal") == "strict" else 1,
                                      severity_order.get(f["severity"], 9),
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

        if finding.get("signal") == "advisory":
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


def compute_manual_review_rule_ids(registry, profile):
    """Rules that require manual review in the current profile.

    A rule is manual-review when it is scored (forbidden or discouraged) but
    its detection is not automated in the CLI scorer: a structural or
    pattern-match rule without a registered detector, or a rule declared
    human-review. The id set documents partial automation so a caller cannot
    mistake a skipped rule for a clean pass.
    """
    manual = set()
    for rule in filter_rules_by_profile(registry, profile):
        if rule.get("semantic_type", "forbidden") not in SCORING_SEMANTIC_TYPES:
            continue
        detection = rule.get("detection_class", "exact_match")
        if detection in ("pattern_match", "structural"):
            if rule.get("detector") not in DETECTORS:
                manual.add(rule["id"])
        elif rule.get("review_mode") == "human":
            manual.add(rule["id"])
    return manual


def validate_score_options(registry, profile, voice=None, context=None,
                           mechanics=None):
    """Reject unknown profile, voice, context, or mechanics values.

    Voice, context, and mechanics are declared as independent writing axes
    in the registry (voices, contexts, mechanics) and resolved by the
    evidence-first pipeline.
    """
    selections = (
        ("profile", profile, registry.get("profiles", {})),
        ("voice", voice, registry.get("voices", {})),
        ("context", context, registry.get("contexts", {})),
        ("mechanics", mechanics, registry.get("mechanics", {})),
    )
    for label, value, choices in selections:
        if value is None:
            continue
        if value not in choices:
            raise ValueError(
                f"unknown {label} '{value}'. Valid: {sorted(choices)}"
            )


def score_text(text, registry, profile="general", voice=None, context=None,
               mechanics=None):
    """Score text and return structured output.

    voice, context, and mechanics are advisory inputs from the evidence-first
    pipeline (analyzer/profile selection). They do not change the scored
    detector set in the CLI scorer; the deterministic slice keeps scoring
    profile-driven and stable.
    """
    limits.check_input_size(text)
    bands = registry.get("score_bands", {})
    word_count = count_words(text)

    # Detect findings
    raw_findings, skipped_rules, structural_metrics = detect_findings(
        text, registry, profile)
    manual_review_rule_ids = compute_manual_review_rule_ids(registry, profile)

    # Handle overlaps
    findings = handle_overlaps(raw_findings)

    # Apply diminishing repetition
    findings = apply_diminishing_repetition(findings)

    # Calculate score
    total_penalty = sum(f.get("weight", 0) for f in findings)
    normalized = normalize_to_500(total_penalty, word_count)
    score = max(0, round(100 - normalized))
    band = score_to_band(score, bands)

    # Calculate density (findings per 500 words). Only scored primary
    # findings count; advisory and related findings report signals without
    # inflating density.
    primary_count = sum(1 for f in findings
                        if f.get("primary", True) and f.get("weight", 0) > 0)
    density = (primary_count / word_count * 500) if word_count > 0 else 0

    # Build output
    output_findings = []
    for f in findings:
        position = f.get("position", 0)
        match_length = f.get("match_length", 0)
        output_findings.append({
            "rule_id": f["rule_id"],
            "category": f["category"],
            "severity": f["severity"],
            "weight": f.get("weight", 0),
            "excerpt": f["excerpt"],
            "position": position,
            "match_length": match_length,
            "reason": f"Detected {f['category']} pattern: {f['rule_id']}",
            "message": f.get("message",
                             f"Detected {f['category']} pattern: {f['rule_id']}"),
            "repair": f.get("repair", ""),
            "span": [position, position + match_length],
            "signal": f.get("signal", "advisory"),
            "evidence": f.get("evidence", "span"),
            "profile": f.get("profile", profile),
            "primary": f.get("primary", True),
            "related": f.get("related", []),
        })

    return {
        "score": score,
        "band": band,
        "word_count": word_count,
        "density": round(density, 2),
        "profile": profile,
        "voice": voice,
        "context": context,
        "mechanics": mechanics,
        "status": (
            "manual_review_required"
            if manual_review_rule_ids
            or any(f.get("signal") == "advisory" for f in findings)
            else "scored"
        ),
        "findings": output_findings,
        "metadata": {
            "version": registry.get("version", "unknown"),
            "total_penalty": round(total_penalty, 2),
            "normalized_penalty": round(normalized, 2),
            "skipped_rules": skipped_rules,
            "structural_metrics": structural_metrics,
            "manual_review_rule_ids": sorted(manual_review_rule_ids),
            "manual_review_rules": len(manual_review_rule_ids),
        },
        "authorship_disclaimer": (
            "This score measures formulaic-writing risk and cannot prove "
            "AI authorship."
        ),
    }


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Antislop scoring engine"
    )
    parser.add_argument(
        "--profile", default="general",
        help="Writing profile (default: general)"
    )
    parser.add_argument(
        "--voice", default="professional",
        help="Writing voice (advisory, default: professional)"
    )
    parser.add_argument(
        "--context", default="docs",
        help="Publication context (advisory, default: docs)"
    )
    parser.add_argument(
        "--mechanics", default="house",
        help="Mechanics profile (advisory, default: house)"
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

    try:
        validate_score_options(
            registry, args.profile, args.voice, args.context, args.mechanics
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(2)

    # Read text
    if args.file:
        try:
            text = limits.read_text_file(args.file)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            sys.exit(2)
    elif args.stdin or not sys.stdin.isatty():
        try:
            text = limits.read_text(sys.stdin)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            sys.exit(2)
    else:
        print(json.dumps({"error": "No input. Use --file, --stdin, or pipe text."}))
        sys.exit(2)

    if not text.strip():
        print(json.dumps({"error": "Empty input"}))
        sys.exit(2)
    result = score_text(
        text, registry, args.profile,
        voice=args.voice, context=args.context, mechanics=args.mechanics,
    )
    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
