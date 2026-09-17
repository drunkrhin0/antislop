#!/usr/bin/env python3
"""Antislop density and precision review (issue #100).

Reviewed aplaceforallmystuff/the-antislop at 732678d (MIT). The reviewed
project scores many isolated terms but has no first-class passage-density
signal, and it describes specificity theater without a focused review of exact
unsourced percentages, ratios, and counts. This module adds both as advisory
signals and fixtures the structural candidates that stay untested there.

  passage density    a document-level advisory finding when three or more
                     distinct flagged terms sit inside one documented passage
                     window; isolated legitimate use never triggers it
  unsourced          a span-level advisory finding for an exact percentage,
  precision          ratio, or count with no nearby source, supplied fact,
                     estimate, or technical-constant framing; it never
                     declares the number false
  structural         heading-hierarchy anomalies, engagement-bait openings,
  candidates         explanatory template headings, self-promotional framing,
                     and decorative "X rather than Y" comparisons, each with a
                     load-bearing positive case that produces no finding

Design evidence only, never a runtime dependency: the Horoscope Test from the
reviewed project stays an optional manual specificity question and never
enters the numeric risk score, and no reviewed score band is imported.

Usage:
    python3 tools/density.py --file text.txt --profile general --medium argument
    cat text.txt | python3 tools/density.py --medium reference
    python3 tools/density.py --fixtures skills/antislop/evals/density-precision-fixtures.json
    python3 tools/density.py --help

Exit codes:
    0 -- the review ran, or every fixture decision matched its expectation
    1 -- a fixture decision failed
    2 -- usage or input error
"""

import argparse
import bisect
import json
import os
import re
import sys
from findings import signal as _signal, short_excerpt as _short_excerpt, excerpt as _excerpt

import limits
from registry import load_registry

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(REPO_ROOT, "rules.json")

INTERFACE = "antislop.density_precision"
SCHEMA = "density-precision-report-1"
PROFILES = ("general", "technical")
MEDIUMS = ("argument", "explanation", "evocation", "narrative", "guide",
           "reference", "message")
STATUSES = ("keep", "revise", "ask-author", "cut", "no-finding")

DISCLAIMER = (
    "Density and precision findings are advisory formulaic-writing-risk "
    "signals; they never prove AI authorship and never declare a number "
    "false."
)
RISK_DISCLAIMER = (
    "Density and precision findings are not part of the Formulaic Writing "
    "Risk Score and never prove AI authorship."
)
HOROSCOPE_NOTE = (
    "Optional manual specificity question from the reviewed project: pick one "
    "random specific detail and ask the author to verify it. The question is "
    "manual, never scored, and never authorship evidence."
)

# A cluster is CLUSTER_MIN distinct flagged rules whose word positions fall
# inside one PASSAGE_WINDOW-word passage.
PASSAGE_WINDOW = 100
CLUSTER_MIN = 3
EVIDENCE_WINDOW = 120

CODE_FENCE_RE = re.compile(
    r"(?ms)^`{3,}[^\n]*\n.*?^`{3,}[ \t]*$"
    r"|^~{3,}[^\n]*\n.*?^~{3,}[ \t]*$"
)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
QUOTED_RE = re.compile(
    r'"[^"\n]*"|\'[^\'\n]*\'|“[^”\n]*”|‘[^’\n]*’|`[^`\n]*`'
)
HEADING_RE = re.compile(r"(?m)^#{1,6}\s+[^\n]+$")
TABLE_RE = re.compile(r"(?m)^\s*\|.*\|\s*$")
BLOCKQUOTE_RE = re.compile(r"(?m)^>\s?.*$")
WORD_RE = re.compile(r"[A-Za-z0-9']+")

# Exact statistics: percentages, multipliers, ratios, and specific counts.
STAT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|percent(?:age)?)(?!\w)"
    r"|\b\d+(?:[.,]\d+)?\s*[x\u00d7](?!\w)"
    r"|\b\d+\s+(?:in|out of)\s+\d+\b"
    r"|\b\d+\s+of\s+\d+\b"
    r"|\b\d+(?:[.,]\d+)?\s+(?:companies|organizations|organisations|firms|"
    r"businesses|startups|teams|developers|engineers|users|customers|clients|"
    r"subscribers|apps|applications|services|servers|hosts|nodes|instances|"
    r"containers|reports|findings|incidents|vulnerabilities|breaches|attacks|"
    r"cases|studies|surveys|respondents|participants|requests|queries|"
    r"commits|releases|deployments|features)\b"
)

# An estimate marker immediately before, or 'or so' immediately after, a
# statistic marks it as an estimate, never an unsourced exact figure.
ESTIMATE_RE = re.compile(
    r"\b(?:about|approximately|approx|roughly|around|nearly|almost|circa|"
    r"some|up to|at least|at most|more than|less than|over|under|close to|"
    r"on the order of|give or take)\b",
    re.IGNORECASE,
)

# Technical-spec framing: the statistic is a constant of a standard, an SLA,
# a protocol, a limit, or a configuration rather than an evidence claim.
TECHNICAL_FRAME_RE = re.compile(
    r"\b(?:spec|specification|standard|sla|rfc|protocol|limit|threshold|"
    r"baseline|config|configuration|configured|constant|nominal|rated|"
    r"fixed|hardcoded|parameter|setting|budget|cap\b|ceiling|floor|"
    r"guarantee|guarantees)\b",
    re.IGNORECASE,
)

# A nearby citation, attribution, or named study marks the statistic sourced.
SOURCE_RE = re.compile(
    r"\[[^\]]*\]\([^)]*\)"
    r"|https?://\S+"
    r"|\[[0-9]+\]"
    r"|\(\s*(?:see\s+)?[A-Z][A-Za-z.'-]+,?\s+[0-9]{4}\s*\)"
    r"|\b(?:according to|reported by|reported in|reported that|cited in|"
    r"based on|sourced? from|source:|citation:|data from|findings from|"
    r"per\s+[A-Z]|study\s+(?:by|from)|survey\s+(?:by|from)|"
    r"report\s+(?:by|from)|research\s+(?:by|from)|analysis\s+(?:by|from)|"
    r"a\s+[0-9]{4}\s+(?:study|survey|report|analysis)|"
    r"the\s+[0-9]{4}\s+(?:study|survey|report|analysis)|"
    r"study\b|survey\b|research\b|analysis\b|findings?\b)\b",
    re.IGNORECASE,
)

# The author's own measurement or consequence near the statistic marks it a
# supplied fact: an observation verb, a measured result, a causal result, or
# an owned measurement noun.
SUPPLIED_RE = re.compile(
    r"\b(?:measured|observed|counted|tracked|recorded|benchmarked|tested|"
    r"audited|surveyed|sampled|found|calculated|computed|quantified|"
    r"detected|experiment(?:s)?|pilot|load test|a/b test|benchmark|"
    r"reduced|reduces|cut\b|cut\s+(?:down\s+)?by|improved|improves|boosted|"
    r"increased|decreased|dropped|doubled|halved|tripled|saved|gained|lost|"
    r"grew|rose|fell|shrank|ranked|scored|achieved|eliminated|"
    r"caused|causes|causing|resulted\s+in|leads?\s+to|produced|"
    r"our\s+(?:audit|survey|test|benchmark|experiment|measurement|data|"
    r"analysis|findings|results|load test)|"
    r"we\s+(?:measured|counted|found|observed|tested|benchmarked|audited|"
    r"surveyed|tracked|recorded|ran))\b",
    re.IGNORECASE,
)

# Generic engagement-bait openers. A specific real question (a named event, a
# named system) never matches, so specific openings stay clean.
ENGAGEMENT_BAIT_RE = re.compile(
    r"\b(?:have you ever (?:wondered|thought|noticed|asked)|"
    r"ever wondered|ever thought about|picture this|imagine (?:this|if)|"
    r"let me ask you something|you won'?t believe|let'?s be honest|"
    r"raise your hand if|we'?ve all been there|you might be wondering|"
    r"you may be wondering|i know what you'?re thinking)\b",
    re.IGNORECASE,
)

# Explanatory template headings that announce a generic category instead of a
# specific claim. Reference, guide, and explanation mediums earn them.
TEMPLATE_HEADING_RE = re.compile(
    r"(?m)^#{1,6}\s+(?:introduction|conclusion|overview|summary|"
    r"key\s+takeaways|takeaways|faq|frequently\s+asked\s+questions|"
    r"getting\s+started|the\s+basics|background|the\s+problem|the\s+solution|"
    r"next\s+steps|benefits|features|challenges|best\s+practices|"
    r"pros\s+and\s+cons|what\s+is|what\s+are|"
    r"why\s+(?:do|does|is|are|should)|why\b.*\bmatters?|"
    r"how\s+it\s+works|how\s+does)\b",
    re.IGNORECASE,
)

# Self-promotional framing. A promotional phrase used as a measured comparison
# (matches the industry-leading baseline) or quoted material is not a finding.
SELF_PROMOTION_RE = re.compile(
    r"\b(?:as\s+(?:an?\s+)?industry\s+leader|industry[- ]leading|"
    r"market[- ]leading|best[- ]in[- ]class|world[- ]class|"
    r"leading\s+(?:provider|vendor|platform|solution|product|company)|"
    r"we'?re\s+proud|we\s+are\s+proud|proudly\s+(?:announce|present|"
    r"introduce|offer)|trusted\s+by|trusted\s+across|loved\s+by|"
    r"used\s+by\s+(?:thousands|millions)|pioneer\s+in|unmatched|"
    r"second\s+to\s+none|premier|state[- ]of[- ]the[- ]art)\b",
    re.IGNORECASE,
)
COMPARISON_RE = re.compile(
    r"\b(?:baseline|benchmark|on\s+par|comparable|matches?|"
    r"within\s+[\d.]|margin|difference|ahead\s+of|behind)\b",
    re.IGNORECASE,
)

# A decorative "X rather than Y" comparison. A comparison that frames a real
# choice between concrete options (use, choose, prefer, decide, recommend) or
# carries a measured result nearby is load-bearing and produces no finding.
RATHER_THAN_RE = re.compile(
    r"\b\w[\w'\-]*\s+rather\s+than\s+\w[\w'\-]*\b", re.IGNORECASE)
DECISION_RE = re.compile(
    r"\b(?:choose|chooses|chose|use\b|uses|using|prefer|prefers|pick|picks|"
    r"decide|decided|opt|opted|select|selects|recommend|recommended|"
    r"switch|switched|replace|replaced|trade|substitute|should|must|instead|"
    r"avoid|avoiding)\b",
    re.IGNORECASE,
)
RESULT_MEASURE_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|x|\u00d7|ms|secs?|minutes?|hours?|days?|runs?|"
    r"times?|fold|points?)\b",
    re.IGNORECASE,
)



def _overlaps_any(start, end, spans):
    return any(s.start() < end and start < s.end() for s in spans)


def _mask_code(text):
    """Blank fenced and inline code with same-length spaces.

    Offsets are preserved so findings keep valid positions in the original
    text. Code is never prose for either density or precision checks.
    """
    masked = list(text)
    for pattern in (CODE_FENCE_RE, INLINE_CODE_RE):
        for match in pattern.finditer(text):
            for index in range(match.start(), match.end()):
                masked[index] = " "
    return "".join(masked)


def _prose_mask(text):
    """Blank code, headings, tables, and blockquotes for precision checks."""
    masked = list(text)
    for pattern in (CODE_FENCE_RE, INLINE_CODE_RE, HEADING_RE, TABLE_RE,
                    BLOCKQUOTE_RE):
        for match in pattern.finditer(text):
            for index in range(match.start(), match.end()):
                masked[index] = " "
    return "".join(masked)


def _finding(rule, start, end, message, repair, excerpt, signal, evidence,
             sample=None):
    return {
        "rule_id": rule["id"],
        "category": rule["category"],
        "severity": rule["severity"],
        "base_weight": rule["base_weight"],
        "signal": signal,
        "start": start,
        "end": end,
        "message": message,
        "repair": repair,
        "excerpt": excerpt,
        "evidence": evidence,
        "sample": sample or {},
    }


def _flagged_rules(registry, profile):
    """Forbidden and discouraged lexical rules active in the profile."""
    rules = []
    for rule in registry.get("rules", []):
        if rule.get("semantic_type") not in ("forbidden", "discouraged"):
            continue
        if rule.get("detection_class") in ("exact_match", "phrase_match"):
            if "*" in rule.get("profiles", ["general"]) or \
                    profile in rule.get("profiles", ["general"]):
                rules.append(rule)
    return rules


def _flagged_matches(masked, rules):
    """(rule_id, start, end) for every flagged term in masked text."""
    from score import find_exact_matches, find_phrase_matches
    matches = []
    for rule in rules:
        detection = rule.get("detection_class", "exact_match")
        if detection == "exact_match":
            found = find_exact_matches(masked, rule)
        elif detection == "phrase_match":
            found = find_phrase_matches(masked, rule)
        else:
            continue
        for match in found:
            matches.append((rule["id"], match.start(), match.end()))
    matches.sort(key=lambda item: item[1])
    return matches


def detect_passage_density(text, rule, profile="general", registry=None):
    """A document-level advisory finding when CLUSTER_MIN distinct flagged
    terms cluster inside one PASSAGE_WINDOW-word passage.

    The finding reports the contributing rule IDs. One term, two separated
    terms, and any cluster below CLUSTER_MIN distinct rules never trigger it.
    """
    signal = _signal(rule)
    registry = registry or load_registry(REGISTRY_PATH)
    masked = _mask_code(text)
    matches = _flagged_matches(masked, _flagged_rules(registry, profile))
    if not matches:
        return {"findings": [], "metrics": []}
    word_offsets = [m.start() for m in WORD_RE.finditer(masked)]
    positions = [bisect.bisect_left(word_offsets, start)
                 for _rid, start, _end in matches]

    findings = []
    index = 0
    count = len(matches)
    while index < count:
        end = index
        while end < count and positions[end] - positions[index] \
                < PASSAGE_WINDOW:
            end += 1
        ids = sorted({rid for rid, _s, _e in matches[index:end]})
        if len(ids) >= CLUSTER_MIN:
            start = matches[index][1]
            stop = max(stop for _rid, _s, stop in matches[index:end])
            message = (
                "%d distinct flagged terms cluster inside a %d-word passage "
                "(%s). Isolated legitimate use of any one term does not "
                "trigger this. Advisory signal; never proves AI authorship."
                % (len(ids), PASSAGE_WINDOW, ", ".join(ids))
            )
            findings.append(_finding(
                rule, start, stop, message, rule.get("correction", ""),
                _excerpt(masked, start, stop), signal, "document",
                {"window_words": positions[end - 1] - positions[index] + 1,
                 "passage_window": PASSAGE_WINDOW,
                 "cluster_min": CLUSTER_MIN,
                 "distinct_terms": len(ids),
                 "contributing_rules": ids},
            ))
            index = end
        else:
            index += 1
    return {"findings": findings, "metrics": []}


def _stat_kind(value):
    if "%" in value or "percent" in value:
        return "percent"
    if "x" in value or "\u00d7" in value:
        return "multiplier"
    if "out of" in value or re.search(r"\b(?:in|of)\b", value):
        return "ratio"
    return "count"


def _estimate_near(text, start, end):
    before = text[max(0, start - 40):start]
    after = text[end:min(len(text), end + 16)]
    tail = " ".join(re.findall(r"\S+", before)[-4:])
    head = " ".join(re.findall(r"\S+", after)[:3])
    if ESTIMATE_RE.search(tail):
        return True
    if re.search(r"^(?:or so|give or take)\b", head, re.IGNORECASE):
        return True
    return "~" in before[-3:] or "~" in after[:3]


def _exemption(text, start, end):
    """The exemption kind for an exact statistic, or None when unsourced."""
    window = text[max(0, start - EVIDENCE_WINDOW):
                  min(len(text), end + EVIDENCE_WINDOW)]
    if _estimate_near(text, start, end):
        return "estimate"
    if SOURCE_RE.search(window):
        return "source"
    if SUPPLIED_RE.search(window):
        return "supplied"
    if TECHNICAL_FRAME_RE.search(window):
        return "technical"
    return None


def precision_entries(text, profile="general", registry=None):
    """Every exact statistic in the prose, classified as unsourced or exempt.

    Each entry carries declared: False: the review never declares a number
    false, only that its source is not established.
    """
    registry = registry or load_registry(REGISTRY_PATH)
    masked = _prose_mask(text)
    entries = []
    for match in STAT_RE.finditer(masked):
        start, end = match.start(), match.end()
        exemption = _exemption(masked, start, end)
        entries.append({
            "statistic": match.group(0),
            "start": start,
            "end": end,
            "kind": _stat_kind(match.group(0)),
            "state": "unsourced" if exemption is None else "exempt",
            "exemption": exemption,
            "declared": False,
        })
    entries.sort(key=lambda entry: entry["start"])
    return entries


def detect_unsourced_precision(text, rule, profile="general", registry=None):
    """A span-level advisory finding for an exact statistic with no nearby
    source, supplied fact, estimate, or technical-constant framing.

    The finding never declares the number false; it asks the author for the
    source. Estimates, supplied facts, nearby citations, and technical
    constants produce clean text.
    """
    signal = _signal(rule)
    masked = _prose_mask(text)
    findings = []
    for match in STAT_RE.finditer(masked):
        start, end = match.start(), match.end()
        exemption = _exemption(masked, start, end)
        if exemption is not None:
            continue
        statistic = match.group(0)
        message = (
            "The exact statistic '%s' has no nearby source, supplied fact, "
            "estimate, or technical-constant framing. Advisory: the review "
            "asks the author for the source and never declares the figure "
            "false." % statistic
        )
        findings.append(_finding(
            rule, start, end, message,
            "Add the source, mark the figure as an estimate, or ask the "
            "author to supply the fact.",
            _excerpt(masked, start, end), signal, "span",
            {"statistic": statistic, "kind": _stat_kind(statistic),
             "exemption": exemption, "evidence_window": EVIDENCE_WINDOW},
        ))
    return {"findings": findings, "metrics": []}


def detect_heading_hierarchy(text, rule, profile="general", registry=None):
    """Heading-level anomalies: a heading that skips a level on descent.

    A functional hierarchy (#, ##, ###, ##) and intentional accessibility
    ladders are preserved; a skip like H1 followed by H3 is reported.
    """
    signal = _signal(rule)
    findings = []
    levels = []
    for match in HEADING_RE.finditer(text):
        line = match.group(0)
        hashes = re.match(r"#+", line)
        levels.append((len(hashes.group(0)) if hashes else 0,
                       match.start(), match.end(), line))
    for index in range(1, len(levels)):
        level, start, end, line = levels[index]
        prev_level = levels[index - 1][0]
        if level > prev_level + 1:
            message = (
                "Heading level skips from H%d to H%d, omitting H%d. Keep the "
                "heading ladder contiguous so the hierarchy stays usable."
                % (prev_level, level, prev_level + 1)
            )
            findings.append(_finding(
                rule, start, end, message, rule.get("correction", ""),
                line.strip(), signal, "span",
                {"heading": line.strip(), "previous_level": prev_level,
                 "level": level, "skipped": prev_level + 1},
            ))
    return {"findings": findings, "metrics": []}


def detect_engagement_bait(text, rule, profile="general", registry=None):
    """Generic engagement-bait openings. A specific real question never
    matches, so specific openings stay clean."""
    signal = _signal(rule)
    findings = []
    for match in ENGAGEMENT_BAIT_RE.finditer(text):
        start, end = match.start(), match.end()
        message = (
            "Generic engagement-bait opening '%s': it asks for attention "
            "instead of leading with the point. Lead with the specific claim "
            "or question." % match.group(0)
        )
        findings.append(_finding(
            rule, start, end, message, rule.get("correction", ""),
            _excerpt(text, start, end), signal, "span",
            {"opening": match.group(0)},
        ))
    return {"findings": findings, "metrics": []}


def detect_template_headings(text, rule, profile="general", registry=None):
    """Explanatory template headings that announce a generic category.

    Reference, guide, and explanation mediums earn them (the review routes
    those to keep); an argument or narrative that leans on a template heading
    is a defect.
    """
    signal = _signal(rule)
    findings = []
    for match in TEMPLATE_HEADING_RE.finditer(text):
        start, end = match.start(), match.end()
        message = (
            "Explanatory template heading '%s': the heading announces a "
            "generic category instead of a specific claim." % match.group(0).strip()
        )
        findings.append(_finding(
            rule, start, end, message, rule.get("correction", ""),
            match.group(0).strip(), signal, "span",
            {"heading": match.group(0).strip()},
        ))
    return {"findings": findings, "metrics": []}


def detect_self_promotion(text, rule, profile="general", registry=None):
    """Self-promotional framing. Quoted material and a measured comparison
    (matches the industry-leading baseline) are load-bearing, not findings."""
    signal = _signal(rule)
    findings = []
    quoted = list(QUOTED_RE.finditer(text))
    for match in SELF_PROMOTION_RE.finditer(text):
        start, end = match.start(), match.end()
        if _overlaps_any(start, end, quoted):
            continue
        window = text[max(0, start - 60):min(len(text), end + 60)]
        if COMPARISON_RE.search(window):
            continue
        message = (
            "Self-promotional framing '%s': let the reader reach the "
            "judgment from the specifics instead of asserting it."
            % match.group(0)
        )
        findings.append(_finding(
            rule, start, end, message, rule.get("correction", ""),
            _excerpt(text, start, end), signal, "span",
            {"phrase": match.group(0)},
        ))
    return {"findings": findings, "metrics": []}


def detect_rather_than(text, rule, profile="general", registry=None):
    """A decorative 'X rather than Y' comparison.

    Load-bearing: the comparison frames a real choice between concrete
    options (use, choose, prefer, decide, recommend) or carries a measured
    result nearby. Those produce no finding; a rhetorical contrast with no
    choice or consequence is decorative.
    """
    signal = _signal(rule)
    findings = []
    for match in RATHER_THAN_RE.finditer(text):
        start, end = match.start(), match.end()
        window = text[max(0, start - 60):min(len(text), end + 60)]
        if DECISION_RE.search(window) or RESULT_MEASURE_RE.search(window):
            continue
        message = (
            "Decorative '%s' comparison: the contrast manages tone instead "
            "of ruling out a specific alternative the reader would otherwise "
            "assume." % match.group(0)
        )
        findings.append(_finding(
            rule, start, end, message, rule.get("correction", ""),
            _excerpt(text, start, end), signal, "span",
            {"comparison": match.group(0)},
        ))
    return {"findings": findings, "metrics": []}


DETECTORS = {
    "passage_density": detect_passage_density,
    "unsourced_precision": detect_unsourced_precision,
    "heading_hierarchy": detect_heading_hierarchy,
    "engagement_bait": detect_engagement_bait,
    "template_headings": detect_template_headings,
    "self_promotion": detect_self_promotion,
    "rather_than": detect_rather_than,
}


def detect_rule(text, rule, profile="general", registry=None):
    func = DETECTORS.get(rule.get("detector"))
    if func is None:
        return {"findings": [], "metrics": []}
    result = func(text, rule, profile, registry)
    for finding in result["findings"]:
        finding["profile"] = profile
    return result


def analyze_text(text, registry, profile="general", medium="argument"):
    """One artifact's density and precision report, plus its review outcome."""
    limits.check_input_size(text)
    rule_by_id = {rule["id"]: rule for rule in registry.get("rules", [])}
    density_findings = []
    precision_findings = []
    entries = []
    density_rule = rule_by_id.get("struct-passage-density")
    precision_rule = rule_by_id.get("struct-unsourced-precision")
    if density_rule is not None:
        density_findings = detect_passage_density(
            text, density_rule, profile, registry)["findings"]
    if precision_rule is not None:
        precision_findings = detect_unsourced_precision(
            text, precision_rule, profile, registry)["findings"]
        entries = precision_entries(text, profile, registry)

    import review  # noqa: F401 -- lazy: review imports density at module load
    review_report = review.review_text(text, medium, registry, profile)

    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "profile": profile,
        "medium": medium,
        "density": {
            "count": len(density_findings),
            "findings": density_findings,
            "rule_ids": sorted({rid for finding in density_findings
                                for rid in finding["sample"].get(
                                    "contributing_rules", [])}),
            "passage_window": PASSAGE_WINDOW,
            "cluster_min": CLUSTER_MIN,
        },
        "precision": {
            "count": len(precision_findings),
            "findings": precision_findings,
            "entries": entries,
        },
        "decision": review_report["decision"],
        "findings": review_report["findings"],
        "author_questions": review_report["author_questions"],
        "risk": review_report["risk"],
        "meta": {
            "disclaimer": DISCLAIMER,
            "horoscope_test": HOROSCOPE_NOTE,
        },
    }


def validate_fixture(fixture, seen_ids):
    """Schema-validate one density-precision fixture. Returns error strings."""
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

    medium = fixture.get("medium", "argument")
    if medium not in MEDIUMS:
        errors.append("%s: medium must be one of %s"
                      % (where, ", ".join(MEDIUMS)))

    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(sorted(PROFILES))))

    for field in ("expected_density_count", "expected_precision_count"):
        value = fixture.get(field)
        if value is not None and (not isinstance(value, int)
                                  or isinstance(value, bool) or value < 0):
            errors.append("%s: %s must be a non-negative integer"
                          % (where, field))

    for field in ("expected_density_rule_ids", "expected_unsourced_statistics",
                  "expected_exempt_statistics", "expected_present_rules",
                  "expected_absent_rules", "expected_author_questions"):
        value = fixture.get(field)
        if value is not None:
            if not isinstance(value, list) or any(
                    not isinstance(item, str) or not item for item in value):
                errors.append("%s: %s must be a list of non-empty strings"
                              % (where, field))

    decision = fixture.get("expected_decision")
    if decision is not None and decision not in STATUSES:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(STATUSES)))

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
    expected = fixture.get("expected_density_count")
    if expected is not None and report["density"]["count"] != expected:
        failures.append("expected %d density finding(s), got %d"
                        % (expected, report["density"]["count"]))
    expected = fixture.get("expected_density_rule_ids")
    if expected is not None:
        got = report["density"]["rule_ids"]
        if sorted(expected) != got:
            failures.append("expected density rules %s, got %s"
                            % (sorted(expected), got))
    expected = fixture.get("expected_precision_count")
    if expected is not None and report["precision"]["count"] != expected:
        failures.append("expected %d precision finding(s), got %d"
                        % (expected, report["precision"]["count"]))
    expected = fixture.get("expected_decision")
    if expected is not None and report["decision"] != expected:
        failures.append("expected decision %s, got %s"
                        % (expected, report["decision"]))

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
    for rule_id in fixture.get("expected_present_rules", []):
        if rule_id not in findings_by_rule:
            failures.append("rule '%s' expected present" % rule_id)
    for rule_id in fixture.get("expected_absent_rules", []):
        if rule_id in findings_by_rule:
            failures.append("rule '%s' expected absent" % rule_id)

    question_texts = [finding.get("tk", "") for finding in report["findings"]]
    question_texts += [item["tk"] for item in report["author_questions"]]
    for question in fixture.get("expected_author_questions", []):
        if not any(question in text for text in question_texts):
            failures.append("missing author question containing %r" % question)

    entries = report["precision"]["entries"]
    expected = fixture.get("expected_unsourced_statistics")
    if expected is not None:
        got = sorted(entry["statistic"] for entry in entries
                     if entry["state"] == "unsourced")
        if sorted(expected) != got:
            failures.append("expected unsourced statistics %s, got %s"
                            % (sorted(expected), got))
    expected = fixture.get("expected_exempt_statistics")
    if expected is not None:
        got = sorted(entry["statistic"] for entry in entries
                     if entry["state"] == "exempt")
        if sorted(expected) != got:
            failures.append("expected exempt statistics %s, got %s"
                            % (sorted(expected), got))
    return failures


def run_density_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one density-precision fixture against its expectations."""
    fid = fixture["id"]
    profile = fixture.get("profile", "general")
    medium = fixture.get("medium", "argument")
    report = analyze_text(fixture["source"], registry, profile, medium)
    report["id"] = fid
    report["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["reviewer_notes"] = fixture.get("reviewer_notes")
    report["failures"] = fixture_failures(report, fixture)
    return report


def run_density_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the density-precision fixture corpus."""
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

    reports = [run_density_fixture(fixture, registry, registry_path)
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
            "medium": report["medium"],
            "findings": report["failures"],
        } for report in failed],
        "schema_errors": schema_errors,
        "gate_pass": not schema_errors and not failed,
        "disclaimer": DISCLAIMER,
        "fixtures": reports,
    }


def load_json(path):
    return limits.load_json_file(path)


def _read_document(path):
    text = limits.read_text_file(path, "document %s" % path)
    if not text.strip():
        raise ValueError("empty input: %s" % path)
    return text


def main():
    parser = argparse.ArgumentParser(description="Antislop density and "
                                                 "precision review")
    parser.add_argument("--file", default=None,
                        help="Path to a single artifact to review")
    parser.add_argument("--medium", default="argument",
                        help="Medium routing: one of %s (default: argument)"
                             % ", ".join(MEDIUMS))
    parser.add_argument("--profile", default="general",
                        help="Writing profile (default: general)")
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--fixtures", default=None,
                        help="Run the density-precision fixture corpus "
                             "instead of reviewing input")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    if args.expect_version and registry.get("version") != args.expect_version:
        print(json.dumps({
            "error": "registry version %s does not match --expect-version %s"
                     % (registry.get("version"), args.expect_version),
        }, indent=2))
        sys.exit(2)

    valid_profiles = set(registry.get("profiles", {}).keys())
    if args.profile not in valid_profiles:
        print(json.dumps({
            "error": "unknown profile '%s'. Valid: %s"
                     % (args.profile, sorted(valid_profiles)),
        }, indent=2))
        sys.exit(2)

    if args.fixtures:
        if not os.path.exists(args.fixtures):
            print(json.dumps({"error": "fixture corpus not found: %s"
                              % args.fixtures}, indent=2))
            sys.exit(2)
        fixtures = load_json(args.fixtures)
        report = run_density_corpus(fixtures.get("evals", fixtures), registry,
                                    args.registry)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["gate_pass"] else 1)

    if args.file:
        if not os.path.exists(args.file):
            print(json.dumps({"error": "file not found: %s" % args.file},
                             indent=2))
            sys.exit(2)
        try:
            text = _read_document(args.file)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
    elif not sys.stdin.isatty():
        try:
            text = limits.read_text(sys.stdin)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
        if not text.strip():
            print(json.dumps({"error": "Empty input"}, indent=2))
            sys.exit(2)
    else:
        print(json.dumps({"error": "No input. Use --file, --fixtures, or "
                                    "pipe text."}, indent=2))
        sys.exit(2)

    report = analyze_text(text, registry, args.profile, args.medium)
    report["meta"]["disclaimer"] = DISCLAIMER
    print(json.dumps(report, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
