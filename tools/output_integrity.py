#!/usr/bin/env python3
"""Output-integrity finding runner (issue #99).

Reviewed Aboudjem/humanizer-skill at 17bb5bb (MIT): provider citation
tokens, hidden Unicode, unresolved placeholders, tracking parameters, and
leaked reasoning are integrity defects, not stylistic risk. Folding them
into one prose score hides the type of failure and can corrupt quotes or
code. This runner reports them as a separate output-integrity finding type,
never as formulaic-writing risk and never as authorship evidence.

Deterministic checks, each with an exact span, line, stable ID, and repair
guidance:

  provider_citation  leaked citation or attribution residue tokens
  placeholder        unresolved placeholder tokens in deliverable prose
  tracking_parameter analytics-only query parameters on a URL
  leaked_reasoning   leaked reasoning or planning wrappers
  zero_width         invisible Unicode characters, code point exposed
  homoglyph          high-confidence mixed-script lookalike characters

Protected tokenization keeps fenced code, inline code, quotes, markdown
links, blockquotes, indented code, and URLs out of the checks. URLs are
inspected for tracking only when they carry an analytics-only query; a URL
with any functional query parameter is left alone. The runner never mutates
text: Unicode findings expose the code point and a safe interpretation, and
the report carries no silent replacement. Baseline mode compares per-kind
counts against a frozen baseline and, with --fail-on-regression, fails only
on new or worsened configured findings. Short samples report uncertainty
instead of a fabricated clean verdict.

Usage:
    python3 tools/output_integrity.py --file doc.md
    cat doc.md | python3 tools/output_integrity.py
    python3 tools/output_integrity.py --file doc.md --template
    python3 tools/output_integrity.py --file doc.md --baseline baseline.json --fail-on-regression
    python3 tools/output_integrity.py --fixtures skills/antislop/evals/output-integrity-fixtures.json
    python3 tools/output_integrity.py --help

Exit codes:
    0 -- the scan ran and no finding is present, or no regression failed
    1 -- at least one finding is present, a regression failed with
         --fail-on-regression, or a fixture corpus failed
    2 -- usage or input error
"""

import argparse
import bisect
import json
import os
import re
import sys

import limits
from registry import load_registry
import edit
import fidelity
import repair

INTERFACE = "antislop.output_integrity"
SCHEMA = "output-integrity-report-1"
PROFILES = ("general", "technical")

DISCLAIMER = (
    "Output-integrity findings report deterministic output defects; they are "
    "reported separately from formulaic-writing risk and never prove AI "
    "authorship or detector immunity."
)
RISK_DISCLAIMER = (
    "Output-integrity findings are not part of the Formulaic Writing Risk "
    "Score and never prove AI authorship."
)

MIN_WORDS_FOR_CONFIDENCE = 15

INTEGRITY_KINDS = (
    "provider_citation", "placeholder", "tracking_parameter",
    "leaked_reasoning", "zero_width", "homoglyph",
)

RULE_IDS = {
    "provider_citation": "integrity-leaked-citation",
    "placeholder": "integrity-placeholder",
    "tracking_parameter": "integrity-tracking-parameter",
    "leaked_reasoning": "integrity-leaked-reasoning",
    "zero_width": "integrity-hidden-unicode",
    "homoglyph": "integrity-homoglyph",
}

REPAIR_GUIDANCE = {
    "provider_citation": ("Remove the leaked citation or attribution token or "
                          "resolve it into a real citation."),
    "placeholder": ("Replace the placeholder with real content or remove it "
                    "from the deliverable."),
    "tracking_parameter": ("Remove the analytics query parameters from the "
                           "URL."),
    "leaked_reasoning": ("Remove the leaked reasoning or planning wrapper "
                         "from the output."),
    "zero_width": ("Remove the invisible character from the text."),
    "homoglyph": ("Replace the lookalike character with the intended ASCII "
                  "letter."),
}

SAMPLE_STATUSES = ("adequate", "short-sample")

PROVIDER_CITATION_RE = re.compile(
    r"\[(?:source|sources|citation|reference)"
    r"(?:\s+(?:needed|required|resolved))?[\s:=-]*[^\]]*\]"
    r"|\((?:source|sources|citation|reference)"
    r"(?:\s+(?:needed|required|resolved))?[\s:=-]*[^)]*\)",
    re.IGNORECASE,
)

# Common analytics and campaign parameters. A URL whose query is composed
# entirely of these is a tracking URL; any functional parameter beside them
# makes the query data the page needs, so the URL is left alone.
TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format",
    "utm_marketing_tactic", "gclid", "dclid", "fbclid", "igshid", "twclid",
    "li_fat_id", "mc_cid", "mc_eid", "ref_src", "ref_url", "wt_mc",
    "pk_campaign", "pk_kwd", "mkt_tok", "hs_campaign", "hs_ad", "_hsenc",
    "_hsmi", "oly_anon_id", "oly_enc_id", "vero_id", "s_cid", "cjevent",
    "msclkid", "yclid", "gbraid", "wbraid", "zanpid", "epik",
})

URL_TRAILING_PUNCT = ".,;:!?)]}"

HIDDEN_UNICODE = {
    0x00AD: ("SOFT HYPHEN", "soft hyphen"),
    0x180E: ("MONGOLIAN VOWEL SEPARATOR", "mongolian vowel separator"),
    0x200B: ("ZERO WIDTH SPACE", "zero-width space"),
    0x200C: ("ZERO WIDTH NON-JOINER", "zero-width non-joiner"),
    0x200D: ("ZERO WIDTH JOINER", "zero-width joiner"),
    0x200E: ("LEFT-TO-RIGHT MARK", "left-to-right mark"),
    0x200F: ("RIGHT-TO-LEFT MARK", "right-to-left mark"),
    0x202A: ("LEFT-TO-RIGHT EMBEDDING", "bidi control character"),
    0x202B: ("RIGHT-TO-LEFT EMBEDDING", "bidi control character"),
    0x202C: ("POP DIRECTIONAL FORMATTING", "bidi control character"),
    0x202D: ("LEFT-TO-RIGHT OVERRIDE", "bidi control character"),
    0x202E: ("RIGHT-TO-LEFT OVERRIDE", "bidi control character"),
    0x2060: ("WORD JOINER", "word joiner"),
    0x2061: ("FUNCTION APPLICATION", "invisible operator"),
    0x2062: ("INVISIBLE TIMES", "invisible operator"),
    0x2063: ("INVISIBLE SEPARATOR", "invisible separator"),
    0x2064: ("INVISIBLE PLUS", "invisible operator"),
    0x3164: ("HANGUL FILLER", "hangul filler"),
    0xFEFF: ("ZERO WIDTH NO-BREAK SPACE",
             "byte order mark / zero-width no-break space"),
    0xFFA0: ("HALFWIDTH HANGUL FILLER", "halfwidth hangul filler"),
}
HIDDEN_UNICODE_RE = re.compile(
    "[" + "".join(chr(cp) for cp in sorted(HIDDEN_UNICODE)) + "]"
)

# High-confidence homoglyphs: characters from another script that are
# visually identical to an ASCII Latin letter. A character is flagged only
# inside a letter run that also contains ASCII letters, so a genuine foreign
# word (all-Cyrillic or all-Greek) and a legitimate accented identifier
# (café, über, naïve) are never touched.
HOMOGLYPHS = {
    0x0410: ("CYRILLIC CAPITAL LETTER A", "A"),
    0x0415: ("CYRILLIC CAPITAL LETTER IE", "E"),
    0x041E: ("CYRILLIC CAPITAL LETTER O", "O"),
    0x0420: ("CYRILLIC CAPITAL LETTER ER", "P"),
    0x0421: ("CYRILLIC CAPITAL LETTER ES", "C"),
    0x0425: ("CYRILLIC CAPITAL LETTER HA", "X"),
    0x0430: ("CYRILLIC SMALL LETTER A", "a"),
    0x0435: ("CYRILLIC SMALL LETTER IE", "e"),
    0x043E: ("CYRILLIC SMALL LETTER O", "o"),
    0x0440: ("CYRILLIC SMALL LETTER ER", "p"),
    0x0441: ("CYRILLIC SMALL LETTER ES", "c"),
    0x0445: ("CYRILLIC SMALL LETTER HA", "x"),
    0x0456: ("CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I", "i"),
    0x039F: ("GREEK CAPITAL LETTER OMICRON", "O"),
    0x03BF: ("GREEK SMALL LETTER OMICRON", "o"),
}
LETTER_RUN_RE = re.compile(r"[A-Za-z\u0080-\uFFFD]+")

INDENTED_CODE_RE = re.compile(r"^ {4,}\S")
BLOCKQUOTE_RE = re.compile(
    r"(?m)^[ \t]{0,3}>[^\n]*(?:\n|$)"
    r"(?:[ \t]{0,3}>[^\n]*(?:\n|$))*"
)


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _protected_spans(text):
    """Protected spans in text: code, quotes, markdown links, blockquotes,
    indented code, and URLs. Sorted, non-overlapping records."""
    spans = []
    for match in fidelity.CODE_FENCE_RE.finditer(text):
        spans.append({"category": "code_block", "start": match.start(),
                      "end": match.end()})
    for match in fidelity.QUOTED_RE.finditer(text):
        spans.append({"category": "quoted", "start": match.start(),
                      "end": match.end()})
    for match in repair.MARKDOWN_LINK_RE.finditer(text):
        spans.append({"category": "markdown_link", "start": match.start(),
                      "end": match.end()})
    for match in BLOCKQUOTE_RE.finditer(text):
        spans.append({"category": "blockquote", "start": match.start(),
                      "end": match.end()})
    for start, end in _line_runs(text, INDENTED_CODE_RE):
        spans.append({"category": "indented_code", "start": start, "end": end})
    for match in fidelity.URL_RE.finditer(text):
        spans.append({"category": "url", "start": match.start(),
                      "end": match.end()})
    kept = []
    for span in sorted(spans, key=lambda s: (s["start"], -s["end"])):
        if (kept and _overlaps(
                span["start"], span["end"],
                kept[-1]["start"], kept[-1]["end"])):
            continue
        kept.append(span)
    return kept


def _line_runs(text, pattern):
    """Runs of consecutive lines matching a pattern, as start/end offsets."""
    lines = text.split("\n")
    spans = []
    pos = 0
    for line in lines:
        spans.append((pos, pos + len(line)))
        pos += len(line) + 1
    runs = []
    index = 0
    while index < len(lines):
        if not pattern.match(lines[index]):
            index += 1
            continue
        end = index
        while end + 1 < len(lines) and pattern.match(lines[end + 1]):
            end += 1
        runs.append((spans[index][0], spans[end][1]))
        index = end + 1
    return runs


def _inside_protected(start, end, spans, exclude_categories=()):
    low = 0
    high = len(spans)
    while low < high:
        middle = (low + high) // 2
        if spans[middle]["start"] < end:
            low = middle + 1
        else:
            high = middle
    for index in (low - 1, low):
        if not 0 <= index < len(spans):
            continue
        span = spans[index]
        if (span["category"] not in exclude_categories
                and _overlaps(start, end, span["start"], span["end"])):
            return True
    return False


def _line_starts(text):
    starts = [0]
    starts.extend(match.end() for match in re.finditer("\n", text))
    return starts


def _line_number(starts, offset):
    return bisect.bisect_right(starts, offset)


def _is_ascii_letter(ch):
    return "a" <= ch <= "z" or "A" <= ch <= "Z"


def _query_parameters(url):
    """Query parameter names on a URL, trailing punctuation stripped.

    An analytics-only query is one whose parameters are all tracking
    parameters. A signed or functional URL carries a non-tracking parameter
    and is left alone.
    """
    query = url.partition("?")[2]
    if not query:
        return []
    query = query.partition("#")[0].rstrip(URL_TRAILING_PUNCT)
    if not query:
        return []
    names = []
    for pair in query.split("&"):
        name = pair.split("=", 1)[0].strip()
        if name:
            names.append(name.lower())
    return names


def _tracking_finding(match):
    """A tracking-parameter finding for a URL match, or None.

    The trailing punctuation is stripped from the span so the finding's
    exact span is the URL itself, not the comma or period after it.
    """
    raw = match.group(0)
    trimmed = raw.rstrip(URL_TRAILING_PUNCT)
    start, end = match.start(), match.start() + len(trimmed)
    names = _query_parameters(trimmed)
    if not names or not all(name in TRACKING_PARAMS for name in names):
        return None
    return {
        "kind": "tracking_parameter",
        "rule_id": RULE_IDS["tracking_parameter"],
        "span": [start, end],
        "value": trimmed,
        "url": trimmed,
        "parameters": sorted(names),
    }


def scan_text(text, profile="general", template=False):
    """Scan one document for output-integrity findings.

    Returns a JSON-serializable document report with per-kind counts, exact
    spans, lines, stable IDs, and repair guidance. Text is never mutated.
    """
    limits.check_input_size(text)
    protected = _protected_spans(text)
    line_starts = _line_starts(text)
    findings = []

    def add(kind, start, end, value, **extra):
        if _inside_protected(start, end, protected):
            return
        finding = {
            "kind": kind,
            "rule_id": RULE_IDS[kind],
            "span": [start, end],
            "line": _line_number(line_starts, start),
            "value": value,
            "message": "Detected %s: %s" % (kind, value),
            "repair": REPAIR_GUIDANCE[kind],
            "evidence": "span",
        }
        finding.update(extra)
        findings.append(finding)

    for match in PROVIDER_CITATION_RE.finditer(text):
        add("provider_citation", match.start(), match.end(), match.group(0))

    if not template:
        for match in edit.PLACEHOLDER_RE.finditer(text):
            add("placeholder", match.start(), match.end(), match.group(0))

    for match in repair.LEAKED_REASONING_RE.finditer(text):
        add("leaked_reasoning", match.start(), match.end(), match.group(0))

    for match in HIDDEN_UNICODE_RE.finditer(text):
        cp = ord(match.group(0))
        name, interpretation = HIDDEN_UNICODE[cp]
        add("zero_width", match.start(), match.end(), match.group(0),
            code_point="U+%04X" % cp, char=match.group(0), name=name,
            safe_interpretation=interpretation)

    for match in LETTER_RUN_RE.finditer(text):
        run = match.group(0)
        if not any(_is_ascii_letter(ch) for ch in run):
            continue
        for index, ch in enumerate(run):
            cp = ord(ch)
            if cp not in HOMOGLYPHS:
                continue
            start = match.start() + index
            if _inside_protected(start, start + 1, protected):
                continue
            name, lookalike = HOMOGLYPHS[cp]
            findings.append({
                "kind": "homoglyph",
                "rule_id": RULE_IDS["homoglyph"],
                "span": [start, start + 1],
                "line": _line_number(line_starts, start),
                "value": ch,
                "message": "Detected homoglyph %s (looks like '%s')"
                           % (name, lookalike),
                "repair": REPAIR_GUIDANCE["homoglyph"],
                "evidence": "span",
                "code_point": "U+%04X" % cp,
                "char": ch,
                "name": name,
                "lookalike": lookalike,
            })

    for match in fidelity.URL_RE.finditer(text):
        if _inside_protected(match.start(), match.end(), protected,
                             exclude_categories=("url",)):
            continue
        tracking = _tracking_finding(match)
        if tracking is None:
            continue
        start, end = tracking["span"]
        tracking["line"] = _line_number(line_starts, start)
        tracking["message"] = ("Detected analytics-only query parameters: %s"
                               % ", ".join(tracking["parameters"]))
        tracking["repair"] = REPAIR_GUIDANCE["tracking_parameter"]
        tracking["evidence"] = "span"
        findings.append(tracking)

    findings.sort(key=lambda finding: (finding["span"][0], finding["span"][1]))
    counters = {}
    for finding in findings:
        kind = finding["kind"]
        counters[kind] = counters.get(kind, 0) + 1
        finding["id"] = "oi-%s-%d" % (kind, counters[kind])

    counts = {kind: 0 for kind in INTEGRITY_KINDS}
    for finding in findings:
        counts[finding["kind"]] += 1

    word_count = len(text.split())
    short = word_count < MIN_WORDS_FOR_CONFIDENCE
    return {
        "word_count": word_count,
        "template": bool(template),
        "sample_status": "short-sample" if short else "adequate",
        "certainty": "uncertain" if short else "confident",
        "sample_message": (
            "Sample is below %d words. Findings listed are what the "
            "deterministic checks observed; the absence of findings is not "
            "reported with confidence because the sample is too short to "
            "cover." % MIN_WORDS_FOR_CONFIDENCE
        ) if short else None,
        "finding_count": len(findings),
        "findings": findings,
        "counts": counts,
    }


def scan_documents(documents, registry, profile="general", template=False):
    """Scan one or more documents and build the JSON report.

    documents is a list of (doc_id, text) pairs. Integrity findings stay in
    a separate report section from formulaic-writing risk and never count as
    authorship evidence.
    """
    limits.check_input_collection(
        [text for _document_id, text in documents])
    per_doc = []
    findings_present = False
    short_sample = False
    for doc_id, text in documents:
        result = scan_text(text, profile, template)
        result["id"] = doc_id
        per_doc.append(result)
        findings_present = findings_present or result["finding_count"] > 0
        short_sample = short_sample or result["sample_status"] == "short-sample"

    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "mode": "corpus" if len(documents) > 1 else "scan",
        "profile": profile,
        "document_count": len(documents),
        "documents": per_doc,
        "signals": {
            "findings_present": findings_present,
            "short_sample": short_sample,
        },
        "baseline": None,
        "risk": {
            "scored_separately": True,
            "advisory": True,
            "authorship_evidence": False,
            "disclaimer": RISK_DISCLAIMER,
        },
        "meta": {
            "disclaimer": DISCLAIMER,
            "mutated": False,
        },
    }


def validate_baseline(baseline):
    """Schema-validate a baseline file. Returns error strings."""
    errors = []
    if not isinstance(baseline, dict):
        return ["baseline must be a JSON object"]
    if baseline.get("schema") != "output-integrity-baseline-1":
        errors.append("baseline schema must be output-integrity-baseline-1")
    docs = baseline.get("documents")
    if not isinstance(docs, list):
        errors.append("baseline 'documents' must be a list")
        return errors
    seen = set()
    for index, doc in enumerate(docs):
        if not isinstance(doc, dict):
            errors.append("baseline documents[%d] must be an object" % index)
            continue
        doc_id = doc.get("id")
        if not (isinstance(doc_id, str) and doc_id.strip()):
            errors.append("baseline documents[%d] needs a non-empty 'id'"
                          % index)
        elif doc_id in seen:
            errors.append("baseline duplicate document id '%s'" % doc_id)
        else:
            seen.add(doc_id)
        counts = doc.get("counts")
        if counts is not None:
            if not isinstance(counts, dict):
                errors.append("baseline documents[%d].counts must be an "
                              "object" % index)
            else:
                for kind, value in counts.items():
                    if kind not in INTEGRITY_KINDS:
                        errors.append("baseline documents[%d].counts has "
                                      "unknown kind '%s'" % (index, kind))
                    elif (not isinstance(value, int)
                          or isinstance(value, bool) or value < 0):
                        errors.append("baseline documents[%d].counts.%s must "
                                      "be a non-negative integer"
                                      % (index, kind))
    config = baseline.get("config")
    if config is not None:
        if not isinstance(config, dict):
            errors.append("baseline 'config' must be an object")
        else:
            enabled = config.get("enabled_kinds")
            if enabled is not None:
                if not isinstance(enabled, list):
                    errors.append("baseline config.enabled_kinds must be a "
                                  "list")
                else:
                    for kind in enabled:
                        if kind not in INTEGRITY_KINDS:
                            errors.append("baseline config.enabled_kinds has "
                                          "unknown kind '%s'" % kind)
    return errors


def compare_to_baseline(report, baseline):
    """Compare each document's per-kind counts against a frozen baseline.

    Only kinds in the baseline config's enabled_kinds are compared. A
    regression is a new finding (baseline 0, current above 0) or a worsened
    count (current above baseline). Improvements are reported, never
    regressions. A document absent from the baseline reports every enabled
    finding as new.
    """
    config = baseline.get("config", {}) or {}
    enabled = set(config.get("enabled_kinds", INTEGRITY_KINDS))
    enabled &= set(INTEGRITY_KINDS)
    baseline_docs = {doc["id"]: doc for doc in baseline.get("documents", [])}

    regressions = []
    improvements = []
    comparisons = []
    for doc in report["documents"]:
        base = baseline_docs.get(doc["id"])
        entry = {"id": doc["id"], "kinds": {}}
        for kind in INTEGRITY_KINDS:
            current = doc["counts"][kind]
            if base is None:
                if kind not in enabled or current == 0:
                    entry["kinds"][kind] = {
                        "baseline": None, "current": current,
                        "state": "unmatched",
                    }
                else:
                    entry["kinds"][kind] = {
                        "baseline": None, "current": current, "state": "new",
                    }
                    regressions.append({
                        "document": doc["id"], "kind": kind, "baseline": 0,
                        "current": current, "direction": "new",
                    })
                continue
            base_count = base.get("counts", {}).get(kind, 0)
            if kind not in enabled:
                entry["kinds"][kind] = {
                    "baseline": base_count, "current": current,
                    "state": "disabled",
                }
            elif current > base_count:
                direction = "new" if base_count == 0 else "worsened"
                entry["kinds"][kind] = {
                    "baseline": base_count, "current": current,
                    "state": direction,
                }
                regressions.append({
                    "document": doc["id"], "kind": kind, "baseline": base_count,
                    "current": current, "direction": direction,
                })
            elif current < base_count:
                entry["kinds"][kind] = {
                    "baseline": base_count, "current": current,
                    "state": "resolved",
                }
                improvements.append({
                    "document": doc["id"], "kind": kind,
                    "baseline": base_count, "current": current,
                })
            else:
                entry["kinds"][kind] = {
                    "baseline": base_count, "current": current,
                    "state": "unchanged",
                }
        comparisons.append(entry)

    return {
        "configured": True,
        "enabled_kinds": sorted(enabled),
        "documents": comparisons,
        "regressions": regressions,
        "improvements": improvements,
        "failed": bool(regressions),
    }


def exit_status(report, fail_on_regression=False):
    """Exit status from a report.

    In baseline mode with --fail-on-regression, the gate fails only on new
    or worsened configured findings; findings that match the frozen baseline
    stay accepted. Without that mode, any finding fails. Short samples with
    no findings exit 0 and report uncertainty instead of a clean verdict.
    """
    baseline = report.get("baseline")
    if fail_on_regression and baseline:
        return 1 if baseline["failed"] else 0
    if report["signals"]["findings_present"]:
        return 1
    return 0


def validate_fixture(fixture, seen_ids):
    """Schema-validate one output-integrity fixture. Returns error strings."""
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

    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(PROFILES)))

    template = fixture.get("template")
    if template is not None and not isinstance(template, bool):
        errors.append("%s: template must be a boolean" % where)

    counts = fixture.get("expected_counts")
    if counts is not None:
        if not isinstance(counts, dict):
            errors.append("%s: expected_counts must be an object" % where)
        else:
            for kind, value in counts.items():
                if kind not in INTEGRITY_KINDS:
                    errors.append("%s: expected_counts has unknown kind '%s'"
                                  % (where, kind))
                elif (not isinstance(value, int) or isinstance(value, bool)
                      or value < 0):
                    errors.append("%s: expected_counts.%s must be a "
                                  "non-negative integer" % (where, kind))

    count = fixture.get("expected_finding_count")
    if count is not None and (not isinstance(count, int)
                              or isinstance(count, bool) or count < 0):
        errors.append("%s: expected_finding_count must be a non-negative "
                      "integer" % where)

    status = fixture.get("expected_sample_status")
    if status is not None and status not in SAMPLE_STATUSES:
        errors.append("%s: expected_sample_status must be one of %s"
                      % (where, ", ".join(SAMPLE_STATUSES)))

    rationale = fixture.get("false_positive_rationale")
    if rationale is not None and (not isinstance(rationale, str)
                                  or not rationale.strip()):
        errors.append("%s: false_positive_rationale must be a non-empty "
                      "string" % where)

    notes = fixture.get("reviewer_notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append("%s: reviewer_notes must be a non-empty string" % where)
    return errors


def fixture_failures(doc, fixture):
    """Compare a computed document scan against its fixture expectations."""
    failures = []
    for kind, expected in (fixture.get("expected_counts") or {}).items():
        if doc["counts"][kind] != expected:
            failures.append("expected %d %s finding(s), got %d"
                            % (expected, kind, doc["counts"][kind]))
    expected = fixture.get("expected_finding_count")
    if expected is not None and doc["finding_count"] != expected:
        failures.append("expected %d finding(s), got %d"
                        % (expected, doc["finding_count"]))
    expected = fixture.get("expected_sample_status")
    if expected is not None and doc["sample_status"] != expected:
        failures.append("expected sample status %s, got %s"
                        % (expected, doc["sample_status"]))
    return failures


def run_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one output-integrity fixture against its expectations."""
    fid = fixture["id"]
    profile = fixture.get("profile", "general")
    template = bool(fixture.get("template"))
    doc = scan_text(fixture["source"], profile, template)
    doc["id"] = fid
    doc["expected_counts"] = fixture.get("expected_counts")
    doc["expected_finding_count"] = fixture.get("expected_finding_count")
    doc["expected_sample_status"] = fixture.get("expected_sample_status")
    doc["false_positive_rationale"] = fixture.get("false_positive_rationale")
    doc["reviewer_notes"] = fixture.get("reviewer_notes")
    doc["failures"] = fixture_failures(doc, fixture)
    return doc


def run_output_integrity_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the output-integrity fixture corpus."""
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

    reports = [run_fixture(fixture, registry, registry_path)
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
            "profile": report.get("profile", "general"),
            "findings": report["failures"],
        } for report in failed],
        "schema_errors": schema_errors,
        "gate_pass": not schema_errors and not failed,
        "disclaimer": DISCLAIMER,
        "fixtures": reports,
    }


def load_json(path):
    return limits.load_json_file(path)


def _read_document(path, max_chars=None):
    """Read one document, rejecting empty input as a usage error."""
    text = limits.read_text_file(path, "document %s" % path,
                                 max_chars=max_chars)
    if not text.strip():
        raise ValueError("empty input: %s" % path)
    return text


def _read_documents(paths, initial_total=0):
    """Read documents without allocating beyond the aggregate text budget."""
    documents = []
    total = initial_total
    for path in paths:
        remaining = limits.MAX_INPUT_CHARS - total
        text = _read_document(path, max_chars=remaining)
        documents.append((path, text))
        total += len(text)
    return documents


def main():
    parser = argparse.ArgumentParser(description="Antislop output-integrity "
                                                 "scan")
    parser.add_argument("--file", default=None,
                        help="Path to a single document to scan")
    parser.add_argument("--doc", action="append", default=[],
                        help="Path to a document (repeatable); each is "
                             "scanned and compared separately")
    parser.add_argument("--profile", default="general",
                        help="Writing profile (default: general)")
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--template", action="store_true",
                        help="Treat the input as a documented template so "
                             "deliberate placeholders are not findings")
    parser.add_argument("--baseline", default=None,
                        help="Compare per-kind counts against a frozen "
                             "baseline JSON file")
    parser.add_argument("--fail-on-regression", action="store_true",
                        help="Fail the exit status when the baseline reports "
                             "new or worsened configured findings")
    parser.add_argument("--fixtures", default=None,
                        help="Run the output-integrity fixture corpus "
                             "instead of scanning input")
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
        report = run_output_integrity_corpus(fixtures.get("evals", fixtures),
                                             registry, args.registry)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["gate_pass"] else 1)

    for path in args.doc:
        if not os.path.exists(path):
            print(json.dumps({"error": "document not found: %s" % path},
                             indent=2))
            sys.exit(2)
    try:
        documents = _read_documents(args.doc)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)

    if args.file:
        if not os.path.exists(args.file):
            print(json.dumps({"error": "file not found: %s" % args.file},
                             indent=2))
            sys.exit(2)
        try:
            documents.extend(_read_documents(
                (args.file,), sum(len(text) for _name, text in documents)))
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
    elif not documents and not sys.stdin.isatty():
        try:
            stdin_text = limits.read_text(sys.stdin)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
        if not stdin_text.strip():
            print(json.dumps({"error": "Empty input"}, indent=2))
            sys.exit(2)
        documents.append(("stdin", stdin_text))
    elif not documents:
        print(json.dumps({"error": "No input. Use --file, --doc, or pipe "
                                    "text."}, indent=2))
        sys.exit(2)

    try:
        report = scan_documents(
            documents, registry, args.profile, args.template)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)

    if args.baseline:
        if not os.path.exists(args.baseline):
            print(json.dumps({"error": "baseline file not found: %s"
                              % args.baseline}, indent=2))
            sys.exit(2)
        baseline = load_json(args.baseline)
        baseline_errors = validate_baseline(baseline)
        if baseline_errors:
            print(json.dumps({"error": "invalid baseline: %s"
                              % "; ".join(baseline_errors)}, indent=2))
            sys.exit(2)
        report["baseline"] = compare_to_baseline(report, baseline)

    print(json.dumps(report, indent=2))
    sys.exit(exit_status(report, args.fail_on_regression))


if __name__ == "__main__":
    main()
