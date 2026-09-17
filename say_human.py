#!/usr/bin/env python3
"""Say-It-Human evidence and locale routing (issue #97).

Reviewed against taxueseek/say-it-human at 71bb6f8 (MIT). Antislop never
labels whether a claim comes from supplied source text, logic, author
experience, inference, or an unknown source, and it lacks locale-aware
punctuation and translationese checks, so a general English repair can
damage Chinese prose or technical spans. This runner adds claim evidence
classes, protected technical spans, an opt-in zh-CN locale profile, and
venue routing for technical documentation, release notes, marketing,
presentations, and social prose.

Operations:
  label   -- label supplied claims with their evidence class
  repair  -- evidence-aware repair. Required claims whose evidence is
             unknown stop rewriting and request a source. Technical spans
             survive byte for byte. zh-CN rules activate only when selected
             or reliably routed. Venue routing keeps a release note grounded
             in supplied change evidence. Large deletions need explicit
             edit authority and emit a visible diff.

Evidence classes:
  source      the claim is present in the supplied source text
  logic       the claim follows by logic from the supplied material
  experience  the claim is the author's own experience
  inference   the claim is inferred from the supplied material
  unknown     no basis can be established

Reused machinery: repair.py (protected regions, edit planning, apply),
fidelity.py (protected anchors), drift.py (word-stable fact matching),
and the registry (profiles). The runner never adds emotion, mess, slang,
errors, or first-person experience to simulate humanity.

Usage:
    python3 say_human.py label --source-text "..." --claim "..."
    python3 say_human.py repair --source-text "..." \
        --required-claim "..." --locale zh-CN --venue release-note \
        --authorize-delete --term "..." --voice-trait "..."
    python3 say_human.py locale --source-text "..." --locale zh-CN
    python3 say_human.py --fixtures skills/antislop/evals/say-human-fixtures.json

Exit codes:
    0 -- the run succeeded, or every fixture decision matched its expectation
    1 -- a fixture decision failed
    2 -- usage or input error
"""

import argparse
import difflib
import json
import os
import re
import sys

import limits
from registry import load_registry
import drift
import repair

INTERFACE = "antislop.say-human"
SCHEMA = "say-human-report-1"
FIXTURE_SCHEMA = "say-human-fixtures-1"

EVIDENCE_CLASSES = ("source", "logic", "experience", "inference", "unknown")
LOCALES = ("", "zh-CN")
VENUES = ("technical-documentation", "release-note", "marketing",
          "presentation", "social")
REPAIR_DECISIONS = ("no-change", "applied", "needs-source",
                    "needs-authority", "reject")
FIXTURE_KINDS = ("label", "repair", "locale")
LARGE_DELETE_CHARS = 20

DEFAULT_REGISTRY = "rules.json"
DEFAULT_PROFILE = "general"

DISCLAIMER = (
    "Say-It-Human evidence and locale routing labels claims and routes "
    "repairs; it never proves AI authorship or detector immunity."
)

# --------------------------------------------------------------------------
# Claim evidence classification (deterministic markers and source matching).
# --------------------------------------------------------------------------

EXPERIENCE_RE = re.compile(
    r"\b(I|we|my|our|I've|we've|I'm|we're|I saw|we saw|"
    r"in my experience|as someone who)\b", re.IGNORECASE)
LOGIC_RE = re.compile(
    r"\b(because|therefore|thus|hence|so|since|consequently|if|then|"
    r"implies|means|leads to|caused|as a result)\b", re.IGNORECASE)
INFERENCE_RE = re.compile(
    r"\b(likely|probably|suggests?|appears?|seems?|may|might|could|"
    r"possibly|presumably|implies|indicates?)\b", re.IGNORECASE)

# --------------------------------------------------------------------------
# Protected technical spans (code, URLs, paths, API names, numbers, tags,
# supplied terminology).
# --------------------------------------------------------------------------

API_NAME_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
    r"|\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"
    r"|\b[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9_]*\b"
    r"|\b[A-Za-z_][A-Za-z0-9_]*\s*\(")
TAG_RE = re.compile(r"#[A-Za-z][A-Za-z0-9_]*|@[A-Za-z][A-Za-z0-9_]*|<[^>]+>")

# --------------------------------------------------------------------------
# zh-CN locale profile (opt-in or reliably routed).
# --------------------------------------------------------------------------

HAN_RE = re.compile(r"[\u4e00-\u9fff]")
HAN_RATIO_THRESHOLD = 0.1

PUNCT_WIDTH_RE = re.compile(r"[\u4e00-\u9fff][,.;:!?()]|[,.;:!?()][\u4e00-\u9fff]")
SPACING_RE = re.compile(r"[\u4e00-\u9fff][A-Za-z]|[A-Za-z][\u4e00-\u9fff]")

TRANSLATIONESE_PATTERNS = (
    (r"被[\u4e00-\u9fff]{1,12}所", "被X所 passive frame"),
    (r"进行了", "carried out verb-noun padding"),
    (r"这一现象", "vague this-phenomenon reference"),
    (r"在[\u4e00-\u9fff]{1,12}的过程中", "in the process of"),
)

# --------------------------------------------------------------------------
# Venue routing expectations (deterministic rows).
# --------------------------------------------------------------------------

VENUE_CHECKS = {
    "technical-documentation": ("technical-spans", "claim-grounding"),
    "release-note": ("change-evidence",),
    "marketing": ("voice-trait", "no-invention"),
    "presentation": ("numbers-preserved", "claim-grounding"),
    "social": ("voice-trait", "no-invention"),
}


def split_claims(text):
    """Split text into claim sentences with source offsets.

    A full stop splits a claim only when followed by whitespace or the end
    of the text, so a period inside a URL or API name never breaks a claim.
    Chinese and English sentence enders always split.
    """
    claims = []
    start = 0
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        is_ender = char in ("。", "！", "？", "!", "?")
        if char == ".":
            following = text[index + 1:index + 2]
            is_ender = (not following or following.isspace())
        if is_ender:
            end = index + 1
            claim = text[start:end].strip()
            if claim:
                claims.append((claim, start, end))
            start = end
        index += 1
    tail = text[start:].strip()
    if tail:
        claims.append((tail, start, len(text)))
    return claims


def classify_claim(claim, source):
    """Evidence class of a single claim against its supplied source.

    Precedence: source > experience > logic > inference > unknown.
    """
    claim = claim.strip()
    if not claim:
        return "unknown"
    if source and drift.contains_fact(source, claim):
        return "source"
    if EXPERIENCE_RE.search(claim):
        return "experience"
    if LOGIC_RE.search(claim):
        return "logic"
    if INFERENCE_RE.search(claim):
        return "inference"
    return "unknown"


def label_claims(source, claims):
    """Label each claim with its evidence class."""
    return [{"claim": claim, "evidence": classify_claim(claim, source)}
            for claim in claims]


def _in_protected(pos, protected_spans):
    return any(span["start"] <= pos < span["end"] for span in protected_spans)


def _mask_protected(text, protected_spans):
    """Blank protected spans so locale regexes never fire inside them."""
    chars = list(text)
    for span in protected_spans:
        for index in range(span["start"], span["end"]):
            chars[index] = " "
    return "".join(chars)


def route_locale(text, requested=""):
    """Active locale: selected, or reliably routed when the text is
    predominantly Han. Anything else returns no locale."""
    if requested == "zh-CN":
        return "zh-CN"
    if requested:
        return ""
    non_space = re.sub(r"\s+", "", text)
    if not non_space:
        return ""
    ratio = len(HAN_RE.findall(non_space)) / len(non_space)
    return "zh-CN" if ratio >= HAN_RATIO_THRESHOLD else ""


def protected_technical_spans(text, required_terms=()):
    """repair.protected_regions plus API names and tags, sorted and merged."""
    regions = repair.protected_regions(text, required_terms)
    for match in API_NAME_RE.finditer(text):
        regions.append({"category": "api_name", "start": match.start(),
                        "end": match.end()})
    for match in TAG_RE.finditer(text):
        regions.append({"category": "tag", "start": match.start(),
                        "end": match.end()})
    regions.sort(key=lambda region: (region["start"], -region["end"]))
    merged = []
    for region in regions:
        if merged and region["start"] < merged[-1]["end"]:
            if region["end"] > merged[-1]["end"]:
                merged[-1]["end"] = region["end"]
            continue
        merged.append(dict(region))
    return merged


def zh_cn_findings(text, protected_spans):
    """Locale findings: punctuation width, spacing, translationese."""
    masked = _mask_protected(text, protected_spans)
    findings = []

    for match in PUNCT_WIDTH_RE.finditer(masked):
        if _in_protected(match.start(), protected_spans):
            continue
        findings.append({
            "rule_id": "zh-cn-punct-width",
            "span": [match.start(), match.end()],
            "excerpt": text[match.start():match.end()],
            "pattern": "half-width punctuation adjacent to Han",
            "repair": "Use the full-width form (，。；：！？（）)",
        })

    for match in SPACING_RE.finditer(masked):
        if _in_protected(match.start(), protected_spans):
            continue
        findings.append({
            "rule_id": "zh-cn-spacing",
            "span": [match.start(), match.end()],
            "excerpt": text[match.start():match.end()],
            "pattern": "missing Chinese-Western space",
            "repair": "Add a space between Han and Latin text",
        })

    for pattern, label in TRANSLATIONESE_PATTERNS:
        regex = re.compile(pattern)
        for match in regex.finditer(masked):
            if _in_protected(match.start(), protected_spans):
                continue
            findings.append({
                "rule_id": "zh-cn-translationese",
                "span": [match.start(), match.end()],
                "excerpt": text[match.start():match.end()],
                "pattern": label,
                "repair": "Prefer a direct Chinese construction",
            })

    findings.sort(key=lambda finding: finding["span"][0])
    return findings


def _evidence_for(claims, source, position):
    for claim, start, end in claims:
        if start <= position < end:
            return classify_claim(claim, source)
    return "unknown"


def venue_checks(source, venue, evidence, protected_spans, voice_traits,
                 supplied_changes):
    """Deterministic venue-expectation rows for a repair report."""
    rows = []
    if venue is None:
        return rows
    if venue not in VENUES:
        raise ValueError("unknown venue %r" % venue)
    grounded = all(entry["evidence"] in ("source", "logic")
                   for entry in evidence)

    if venue == "technical-documentation":
        rows.append({
            "feature": "technical-spans",
            "status": "keep" if protected_spans else "missing",
            "why": "Technical spans (code, URLs, paths, API names, numbers, "
                   "tags, supplied terms) are preserved byte for byte.",
        })
        rows.append({
            "feature": "claim-grounding",
            "status": "keep" if grounded else "missing",
            "why": "Every claim is grounded in supplied material or logic.",
        })
    elif venue == "release-note":
        basis = " ".join(supplied_changes) if supplied_changes else source
        unsupported = [entry["claim"] for entry in evidence
                       if classify_claim(entry["claim"], basis)
                       not in ("source", "logic")]
        rows.append({
            "feature": "change-evidence",
            "status": "keep" if not unsupported else "missing",
            "why": ("A release note uses only supplied change evidence; "
                    "unsupported claims: %s" % "; ".join(unsupported)
                    if unsupported else
                    "Every claim is grounded in the supplied changes."),
        })
    elif venue == "marketing":
        rows.append({
            "feature": "voice-trait",
            "status": "keep" if voice_traits else "n/a",
            "why": "Supplied informal voice traits stay unchanged.",
        })
        rows.append({
            "feature": "no-invention",
            "status": "keep",
            "why": "No emotion, mess, slang, errors, or invented experience "
                   "is added to simulate humanity.",
        })
    elif venue == "presentation":
        numbers = [span for span in protected_spans
                   if span.get("category") == "number"]
        rows.append({
            "feature": "numbers-preserved",
            "status": "keep" if numbers else "n/a",
            "why": "Exact numbers survive byte for byte.",
        })
        rows.append({
            "feature": "claim-grounding",
            "status": "keep" if grounded else "missing",
            "why": "Every claim is grounded in supplied material or logic.",
        })
    elif venue == "social":
        rows.append({
            "feature": "voice-trait",
            "status": "keep" if voice_traits else "n/a",
            "why": "Supplied informal voice traits stay unchanged.",
        })
        rows.append({
            "feature": "no-invention",
            "status": "keep",
            "why": "No emotion, mess, slang, errors, or invented experience "
                   "is added to simulate humanity.",
        })
    return rows


def _unified_diff(source, candidate, path="<stdin>"):
    return "".join(difflib.unified_diff(
        source.splitlines(keepends=True),
        candidate.splitlines(keepends=True),
        fromfile=path, tofile=path + ".repaired"))


def label_report(source, claims, registry):
    limits.check_input_size(source, "source text")
    evidence = label_claims(source, claims)
    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "operation": "label",
        "decision": "labeled",
        "evidence": evidence,
        "meta": {
            "disclaimer": DISCLAIMER,
        },
    }


def repair_say_human(source, registry, *, required_claims=(),
                     locale="", venue=None, authorize_delete=False,
                     required_terms=(), voice_traits=(),
                     supplied_changes=(), registry_path=DEFAULT_REGISTRY,
                     profile=DEFAULT_PROFILE):
    limits.check_input_size(source, "source text")
    """Evidence-aware repair with protected spans, locale routing, venue
    routing, and an edit-authority gate for large deletions."""
    claims = split_claims(source)
    evidence = [{"claim": claim, "evidence": classify_claim(claim, source),
                 "span": [start, end]}
                for claim, start, end in claims]

    active_locale = route_locale(source, locale)
    all_terms = tuple(required_terms) + tuple(voice_traits)
    protected_spans = protected_technical_spans(source, all_terms)

    needs_source = []
    for claim in required_claims:
        if classify_claim(claim, source) == "unknown":
            needs_source.append({
                "claim": claim,
                "request": "[TK: what is the source for this claim?]",
            })

    venue_rows = venue_checks(source, venue, evidence, protected_spans,
                              voice_traits, supplied_changes)
    release_missing = any(row["status"] == "missing"
                          for row in venue_rows
                          if row["feature"] == "change-evidence")
    if release_missing:
        basis = " ".join(supplied_changes) if supplied_changes else source
        for entry in evidence:
            if classify_claim(entry["claim"], basis) \
                    not in ("source", "logic"):
                if all(item["claim"] != entry["claim"]
                       for item in needs_source):
                    needs_source.append({
                        "claim": entry["claim"],
                        "request": "[TK: what is the source for this claim?]",
                    })

    if needs_source:
        report = {
            "interface": INTERFACE,
            "schema": SCHEMA,
            "version": registry.get("version", "unknown"),
            "operation": "repair",
            "decision": "needs-source",
            "evidence": evidence,
            "needs_source": needs_source,
            "protected_spans": protected_spans,
            "locale": {
                "requested": locale,
                "active": active_locale,
                "findings": (zh_cn_findings(source, protected_spans)
                             if active_locale == "zh-CN" else []),
            },
            "venue": {"venue": venue, "checks": venue_rows},
            "replacements": [],
            "diff": None,
            "text": source,
            "meta": {
                "disclaimer": DISCLAIMER,
                "authorize_delete": authorize_delete,
                "profile": profile,
            },
        }
        return report

    edits, records = repair.plan_edits(source, registry, profile,
                                       protected_spans)

    large = [edit for edit in edits
             if edit.get("action") == "remove"
             and len(edit.get("original", "")) >= LARGE_DELETE_CHARS]
    if large and not authorize_delete:
        refused = [{"span": [edit["start"], edit["end"]],
                    "original": edit["original"]} for edit in large]
        proposed = repair.apply_edits(source, large)
        return {
            "interface": INTERFACE,
            "schema": SCHEMA,
            "version": registry.get("version", "unknown"),
            "operation": "repair",
            "decision": "needs-authority",
            "evidence": evidence,
            "needs_source": [],
            "protected_spans": protected_spans,
            "locale": {
                "requested": locale,
                "active": active_locale,
                "findings": (zh_cn_findings(source, protected_spans)
                             if active_locale == "zh-CN" else []),
            },
            "venue": {"venue": venue, "checks": venue_rows},
            "replacements": records,
            "refused_deletions": refused,
            "diff": _unified_diff(source, proposed),
            "text": source,
            "meta": {
                "disclaimer": DISCLAIMER,
                "authorize_delete": False,
                "profile": profile,
            },
        }

    candidate = repair.apply_edits(source, edits)
    replacement_rows = []
    for record in records:
        row = dict(record)
        span = record.get("span")
        if span:
            row["evidence"] = _evidence_for(claims, source, span[0])
        else:
            row["evidence"] = "unknown"
        replacement_rows.append(row)
    for edit in edits:
        if any(row["span"] == [edit["start"], edit["end"]]
               and row["rule_id"] == edit["rule_id"]
               for row in replacement_rows):
            continue
        replacement_rows.append({
            "rule_id": edit["rule_id"],
            "span": [edit["start"], edit["end"]],
            "action": edit["action"],
            "original": edit["original"],
            "replacement": edit["replacement"],
            "preservation": "passed",
            "unresolved": False,
            "evidence": _evidence_for(claims, source, edit["start"]),
        })
    replacement_rows.sort(key=lambda row: (row["span"][0], row["span"][1]))

    decision = "applied" if edits else "no-change"
    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "operation": "repair",
        "decision": decision,
        "evidence": evidence,
        "needs_source": [],
        "protected_spans": protected_spans,
        "locale": {
            "requested": locale,
            "active": active_locale,
            "findings": (zh_cn_findings(source, protected_spans)
                         if active_locale == "zh-CN" else []),
        },
        "venue": {"venue": venue, "checks": venue_rows},
        "replacements": replacement_rows,
        "diff": _unified_diff(source, candidate) if edits else None,
        "text": candidate,
        "meta": {
            "disclaimer": DISCLAIMER,
            "authorize_delete": authorize_delete,
            "profile": profile,
        },
    }


def locale_report(source, requested, registry):
    active = route_locale(source, requested)
    protected_spans = protected_technical_spans(source)
    findings = (zh_cn_findings(source, protected_spans)
                if active == "zh-CN" else [])
    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "operation": "locale",
        "decision": "active" if active else "inactive",
        "active": active,
        "findings": findings,
        "protected_spans": protected_spans,
        "meta": {
            "disclaimer": DISCLAIMER,
        },
    }


# --------------------------------------------------------------------------
# Fixture corpus validation.
# --------------------------------------------------------------------------

def validate_fixture(fixture, seen_ids):
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

    kind = fixture.get("kind")
    if kind not in FIXTURE_KINDS:
        errors.append("%s: kind must be one of %s"
                      % (where, ", ".join(FIXTURE_KINDS)))

    source = fixture.get("source")
    if not isinstance(source, str) or not source.strip():
        errors.append("%s: 'source' must be a non-empty string" % where)

    if kind == "label":
        claim = fixture.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            errors.append("%s: label fixtures need a non-empty 'claim'"
                          % where)
        expected = fixture.get("expected_evidence")
        if expected not in EVIDENCE_CLASSES:
            errors.append("%s: expected_evidence must be one of %s"
                          % (where, ", ".join(EVIDENCE_CLASSES)))

    if kind == "repair":
        expected = fixture.get("expected_decision")
        if expected not in REPAIR_DECISIONS:
            errors.append("%s: expected_decision must be one of %s"
                          % (where, ", ".join(REPAIR_DECISIONS)))
        if fixture.get("locale", "") not in LOCALES:
            errors.append("%s: locale must be one of %r" % (where, LOCALES))
        venue = fixture.get("venue")
        if venue is not None and venue not in VENUES:
            errors.append("%s: venue must be one of %s"
                          % (where, ", ".join(VENUES)))
        for field in ("required_claims", "required_terms", "voice_traits",
                      "supplied_changes"):
            values = fixture.get(field, [])
            if not isinstance(values, list):
                errors.append("%s: %s must be a list" % (where, field))
            else:
                for index, value in enumerate(values):
                    if not isinstance(value, str) or not value.strip():
                        errors.append("%s: %s[%d] must be a non-empty string"
                                      % (where, field, index))
        if not isinstance(fixture.get("authorize_delete", False), bool):
            errors.append("%s: authorize_delete must be a boolean" % where)
        for field in ("expected_needs_source", "expected_preserved",
                      "expected_findings", "expected_clean"):
            values = fixture.get(field, [])
            if not isinstance(values, list):
                errors.append("%s: %s must be a list" % (where, field))
            else:
                for index, value in enumerate(values):
                    if not isinstance(value, str) or not value.strip():
                        errors.append("%s: %s[%d] must be a non-empty string"
                                      % (where, field, index))
        expected_replacements = fixture.get("expected_replacement_evidence",
                                            [])
        if not isinstance(expected_replacements, list):
            errors.append("%s: expected_replacement_evidence must be a list"
                          % where)
        else:
            for index, entry in enumerate(expected_replacements):
                if not isinstance(entry, list) or len(entry) != 2:
                    errors.append("%s: expected_replacement_evidence[%d] "
                                  "must be a [rule_id, evidence] pair"
                                  % (where, index))
                elif (not isinstance(entry[0], str)
                      or entry[1] not in EVIDENCE_CLASSES):
                    errors.append("%s: expected_replacement_evidence[%d] "
                                  "must be [str, %s]"
                                  % (where, index,
                                     ", ".join(EVIDENCE_CLASSES)))
        expected_evidence = fixture.get("expected_evidence", {})
        if not isinstance(expected_evidence, dict):
            errors.append("%s: expected_evidence must be an object" % where)
        else:
            for claim, expected in expected_evidence.items():
                if expected not in EVIDENCE_CLASSES:
                    errors.append("%s: expected_evidence['%s'] must be one "
                                  "of %s"
                                  % (where, claim, ", ".join(EVIDENCE_CLASSES)))
        venue_statuses = fixture.get("expected_venue_statuses", {})
        if not isinstance(venue_statuses, dict):
            errors.append("%s: expected_venue_statuses must be an object"
                          % where)
        else:
            for feature, status in venue_statuses.items():
                if status not in ("keep", "missing", "n/a"):
                    errors.append("%s: expected_venue_statuses['%s'] must be "
                                  "keep, missing, or n/a" % (where, feature))
        expected_text = fixture.get("expected_text")
        if expected_text is not None and not isinstance(expected_text, str):
            errors.append("%s: expected_text must be a string" % where)

    if kind == "locale":
        if fixture.get("locale", "") not in LOCALES:
            errors.append("%s: locale must be one of %r" % (where, LOCALES))
        if not isinstance(fixture.get("expected_active", True), bool):
            errors.append("%s: expected_active must be a boolean" % where)
        for field in ("expected_findings", "expected_clean"):
            values = fixture.get(field, [])
            if not isinstance(values, list):
                errors.append("%s: %s must be a list" % (where, field))
            else:
                for index, value in enumerate(values):
                    if not isinstance(value, str) or not value.strip():
                        errors.append("%s: %s[%d] must be a non-empty string"
                                      % (where, field, index))

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
    failures = []
    kind = fixture["kind"]
    if kind == "label":
        evidence = report["evidence"][0]["evidence"]
        if evidence != fixture["expected_evidence"]:
            failures.append("expected evidence %s, got %s"
                            % (fixture["expected_evidence"], evidence))
        return failures

    if kind == "locale":
        expected_active = fixture.get("expected_active")
        if expected_active is not None:
            active = "zh-CN" if report["active"] else ""
            if (active == "zh-CN") != expected_active:
                failures.append("expected active %s, got %r"
                                % (expected_active, report["active"]))
        rule_ids = {finding["rule_id"] for finding in report["findings"]}
        for rule in fixture.get("expected_findings", []):
            if rule not in rule_ids:
                failures.append("expected locale finding '%s' not reported"
                                % rule)
        for rule in fixture.get("expected_clean", []):
            if rule in rule_ids:
                failures.append("clean fixture fired locale rule '%s'" % rule)
        return failures

    if report["decision"] != fixture["expected_decision"]:
        failures.append("expected decision %s, got %s"
                        % (fixture["expected_decision"], report["decision"]))
    need_texts = [item["claim"] for item in report["needs_source"]]
    for claim in fixture.get("expected_needs_source", []):
        if claim not in need_texts:
            failures.append("claim %r not requested for a source" % claim)
    for text in fixture.get("expected_preserved", []):
        if text not in report["text"]:
            failures.append("protected text %r did not survive byte for byte"
                            % text)
    expected_text = fixture.get("expected_text")
    if expected_text is not None and report["text"] != expected_text:
        failures.append("expected exact text, got %r" % report["text"])
    rule_ids = {finding["rule_id"] for finding in report["locale"]["findings"]}
    for rule in fixture.get("expected_findings", []):
        if rule not in rule_ids:
            failures.append("expected locale finding '%s' not reported" % rule)
    for rule in fixture.get("expected_clean", []):
        if rule in rule_ids:
            failures.append("clean fixture fired locale rule '%s'" % rule)
    checks = {row["feature"]: row["status"]
              for row in report["venue"]["checks"]}
    for feature, status in (fixture.get("expected_venue_statuses", {})
                            or {}).items():
        if checks.get(feature) != status:
            failures.append("venue feature '%s' expected %s, got %s"
                            % (feature, status, checks.get(feature)))
    evidence_map = {entry["claim"]: entry["evidence"]
                    for entry in report["evidence"]}
    for claim, expected in (fixture.get("expected_evidence", {}) or {}).items():
        if evidence_map.get(claim) != expected:
            failures.append("claim %r expected evidence %s, got %s"
                            % (claim, expected, evidence_map.get(claim)))
    for rule_id, expected in fixture.get("expected_replacement_evidence",
                                         []):
        matched = [row["evidence"] for row in report["replacements"]
                   if row["rule_id"] == rule_id and row.get("evidence")]
        if expected not in matched:
            failures.append("replacement '%s' expected evidence %s, got %s"
                            % (rule_id, expected, matched or "no record"))
    return failures


def run_fixture(fixture, registry, registry_path=DEFAULT_REGISTRY):
    fid = fixture["id"]
    kind = fixture["kind"]
    profile = fixture.get("profile", DEFAULT_PROFILE)
    if kind == "label":
        report = label_report(fixture["source"], [fixture["claim"]], registry)
    elif kind == "locale":
        report = locale_report(fixture["source"], fixture.get("locale", ""),
                               registry)
    else:
        report = repair_say_human(
            fixture["source"], registry,
            required_claims=tuple(fixture.get("required_claims", [])),
            locale=fixture.get("locale", ""),
            venue=fixture.get("venue"),
            authorize_delete=fixture.get("authorize_delete", False),
            required_terms=tuple(fixture.get("required_terms", [])),
            voice_traits=tuple(fixture.get("voice_traits", [])),
            supplied_changes=tuple(fixture.get("supplied_changes", [])),
            registry_path=registry_path, profile=profile)
    report["id"] = fid
    report["expected_decision"] = fixture.get("expected_decision")
    report["meta"]["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
    report["fixture_failures"] = _fixture_failures(report, fixture)
    return report


def run_corpus(fixtures, registry, registry_path=DEFAULT_REGISTRY):
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
    failed = [report for report in reports if report["fixture_failures"]]
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
            "kind": report["operation"],
            "expected": report.get("expected_decision"),
            "got": report.get("decision"),
            "findings": report["fixture_failures"],
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
    parser.add_argument(
        "--fixtures",
        default="skills/antislop/evals/say-human-fixtures.json",
        help="Run the say-human fixture corpus instead of an operation")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY,
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Print a compact JSON report")
    sub = parser.add_subparsers(dest="operation")

    label_p = sub.add_parser("label", help="Label claims by evidence class")
    label_p.add_argument("--source-text", required=True)
    label_p.add_argument("--claim", action="append", default=[],
                         help="Claim to label (repeatable)")

    repair_p = sub.add_parser("repair", help="Evidence-aware repair")
    repair_p.add_argument("--source-text", required=True)
    repair_p.add_argument("--required-claim", action="append", default=[],
                          help="Claim that must have known evidence "
                               "(repeatable)")
    repair_p.add_argument("--locale", default="",
                          help="Locale profile (zh-CN or empty for routing)")
    repair_p.add_argument("--venue", default=None,
                          help="One of: %s" % ", ".join(VENUES))
    repair_p.add_argument("--authorize-delete", action="store_true",
                          help="Allow large deletions with a visible diff")
    repair_p.add_argument("--term", action="append", default=[],
                          help="Supplied terminology to protect (repeatable)")
    repair_p.add_argument("--voice-trait", action="append", default=[],
                          help="Supplied informal voice trait (repeatable)")
    repair_p.add_argument("--supplied-change", action="append", default=[],
                          help="Supplied change evidence (repeatable)")

    locale_p = sub.add_parser("locale", help="Report locale routing")
    locale_p.add_argument("--source-text", required=True)
    locale_p.add_argument("--locale", default="",
                          help="Locale profile (zh-CN or empty for routing)")

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

    if args.operation == "label":
        report = label_report(args.source_text, args.claim, registry)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0)
    if args.operation == "repair":
        report = repair_say_human(
            args.source_text, registry,
            required_claims=tuple(args.required_claim),
            locale=args.locale,
            venue=args.venue,
            authorize_delete=args.authorize_delete,
            required_terms=tuple(args.term),
            voice_traits=tuple(args.voice_trait),
            supplied_changes=tuple(args.supplied_change),
            registry_path=args.registry)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0)
    if args.operation == "locale":
        report = locale_report(args.source_text, args.locale, registry)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0)

    parser.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
