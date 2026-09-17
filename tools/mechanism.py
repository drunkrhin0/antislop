#!/usr/bin/env python3
"""Mechanism checks for significance, impact, causality, and superiority
claims (issue #96).

A Clarity-style detector set: an evaluative claim that asserts importance,
impact, causality, or superiority without a nearby mechanism, actor, result,
or limit is unsupported significance. The same claim with the mechanism named
beside it is an evidenced consequence and is not a finding.

Adapted from addyosmani/clarity at 9e30711 (MIT): the 'Importance without
mechanism' diagnosis and the 'Specific-looking vagueness' test. Design
evidence only, never a runtime dependency.

Every finding is advisory. Mechanism checks never prove AI authorship and
never deduct from the Formulaic Writing Risk Score.

Usage (as a library, via structural.py's detector registry):
    python3 -c "import mechanism; print(mechanism.detect_rule(text, rule, 'general'))"
"""

import re


EVIDENCE_WINDOW = 120

# Numbers and measured results: 40%, 3x, 800ms, 40 minutes, 14 services.
# A trailing \b never matches after '%' (non-word char), so the percent and
# multiplier alternatives end with (?!\w) instead.
MEASURE_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|×)(?!\w)"
    r"|\b\d+(?:[.,]\d+)?\s*[xX](?!\w)"
    r"|\b\d+(?:[.,]\d+)?\s*[- ]?(?:ms|secs?|minutes?|hours?|days?|weeks?|"
    r"months?|years?|kb|mb|gb|tb|services?|runs?|tests?|launches?)\b"
)
# A named actor: a capitalized token (mid-sentence, not a common function
# word). Sentence-initial capitals are common prose, not evidence.
NAMED_ACTOR_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{2,}\b")
# An explicit evidence verb naming a measurement or observation.
OBSERVATION_RE = re.compile(
    r"\b(?:measured|tested|observed|benchmarked|tracked|recorded|"
    r"benchmark|experiment|study|survey|load test|a/b test|pilot)\b",
    re.IGNORECASE,
)

IMPORTANCE_SIGNALS = (
    "pivotal", "crucial", "transformative", "significant", "vital",
    "underscores", "underscored", "testament", "plays a key role",
    "represents a shift", "broader trend",
)
IMPACT_SIGNALS = (
    "impact", "game-changer", "game changing", "huge impact", "dramatic",
    "enormous", "massive", "moved the needle", "reduced", "reduces",
    "improved", "improves", "boosted", "boosts", "cut the time",
)
CAUSALITY_SIGNALS = (
    "causes", "caused", "causing", "is responsible for", "is the reason",
    "leads to", "led to", "results in", "resulted in", "stems from",
)
SUPERIORITY_SIGNALS = (
    "best-in-class", "world-class", "unbeatable", "superior", "the best",
    "better than", "the fastest", "the only", "leading provider",
    "cutting-edge", "groundbreaking", "best",
)

SIGNAL_PATTERNS = {
    "importance": IMPORTANCE_SIGNALS,
    "impact": IMPACT_SIGNALS,
    "causality": CAUSALITY_SIGNALS,
    "superiority": SUPERIORITY_SIGNALS,
}

SIGNAL_RE = {
    kind: re.compile(
        r"\b(?:" + "|".join(re.escape(sig) for sig in signals) + r")\b",
        re.IGNORECASE,
    )
    for kind, signals in SIGNAL_PATTERNS.items()
}

MESSAGES = {
    "importance": (
        "Importance claim without a nearby mechanism: '%s' asserts "
        "magnitude, but the passage names no actor, result, or limit that "
        "earns it. State the supported mechanism or ask the author."
    ),
    "impact": (
        "Impact claim without a nearby result: '%s' asserts an effect, but "
        "the passage names no measured result or limit. Name the result or "
        "ask the author."
    ),
    "causality": (
        "Causal claim without a nearby mechanism: '%s' asserts a cause, but "
        "the passage names no cause, result, or number that supports it. "
        "Name the cause and its measured result or keep the claim attributed."
    ),
    "superiority": (
        "Superiority claim without a nearby basis: '%s' asserts superiority, "
        "but the passage names no comparison or measured result. Name the "
        "basis or ask the author."
    ),
}

REPAIRS = {
    "importance": (
        "State the supported mechanism and let the reader judge the "
        "importance; or ask the author for it."
    ),
    "impact": "Name the measured result or limit; or ask the author for it.",
    "causality": (
        "Name the cause and the measured result; or keep the claim "
        "attributed and hedged."
    ),
    "superiority": (
        "Name the basis of comparison or the measured result; or ask the "
        "author for it."
    ),
}


def _nearby_evidence(text, start, end):
    """True when a measure, observation verb, or mid-sentence named actor sits
    within the evidence window of a claim. Sentence-initial capitals and
    common function words are not evidence."""
    window = text[max(0, start - EVIDENCE_WINDOW):end + EVIDENCE_WINDOW]
    if MEASURE_RE.search(window) or OBSERVATION_RE.search(window):
        return True
    for match in NAMED_ACTOR_RE.finditer(window):
        token = match.group(0)
        if token in _CAP_STOP:
            continue
        before = window[:match.start()]
        if before.strip() and not re.search(r"[.!?]\s*$", before):
            return True
    return False


# Common capitalized words that are prose, not named actors.
_CAP_STOP = {
    "The", "This", "That", "These", "Those", "It", "We", "Our", "You",
    "Your", "They", "Their", "There", "Here", "But", "And", "Or", "So",
    "Yet", "Then", "Thus", "Hence", "When", "If", "For", "In", "On", "At",
    "As", "No", "Not", "Nor", "Which", "What", "How", "Why", "Where", "Who",
    "Whom", "One", "Two", "Most", "Many", "Some", "Every", "Each", "Both",
    "Because", "Although", "However", "Also", "While", "After", "Before",
    "During", "Since", "Until", "Using", "Through", "Within", "Without",
    "Under", "Over", "Beyond", "About", "Above",
}


def _finding(kind, rule, start, end, text, signal):
    match = SIGNAL_RE[kind].search(text, start, end)
    token = match.group(0) if match else kind
    excerpt = text[max(0, start - 20):min(len(text), end + 20)].strip()
    if excerpt and not excerpt.startswith((" ", "\t")):
        excerpt = "..." + excerpt
    if excerpt and not excerpt.endswith((" ", "\t")):
        excerpt = excerpt + "..."
    return {
        "rule_id": rule["id"],
        "category": rule["category"],
        "severity": rule["severity"],
        "base_weight": rule["base_weight"],
        "signal": signal,
        "start": start,
        "end": end,
        "message": MESSAGES[kind] % token,
        "repair": REPAIRS[kind],
        "excerpt": excerpt,
        "evidence": "span",
        "sample": {"kind": kind, "token": token,
                   "evidence_window": EVIDENCE_WINDOW},
    }


def _check(text, rule, kind, signal):
    findings = []
    for match in SIGNAL_RE[kind].finditer(text):
        start = match.start()
        end = match.end()
        if _nearby_evidence(text, start, end):
            continue
        findings.append(_finding(kind, rule, start, end, text, signal))
    return findings


def _detect_kind(kind):
    def detect(text, rule, profile="general"):
        signal = "strict" if rule.get("review_mode") == "deterministic" else "advisory"
        return {"findings": _check(text, rule, kind, signal), "metrics": []}
    return detect


DETECTORS = {
    "mechanism_importance": _detect_kind("importance"),
    "mechanism_impact": _detect_kind("impact"),
    "mechanism_causality": _detect_kind("causality"),
    "mechanism_superiority": _detect_kind("superiority"),
}


def detect_rule(text, rule, profile="general"):
    func = DETECTORS.get(rule.get("detector"))
    if func is None:
        return {"findings": [], "metrics": []}
    result = func(text, rule, profile)
    for finding in result["findings"]:
        finding["profile"] = profile
    return result