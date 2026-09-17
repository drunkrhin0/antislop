#!/usr/bin/env python3
"""Humanizer Stack staged scan (issue #98).

An ordered two-stage audit over prose: a surface scan first, a structural
review second. Surface checks run deterministic lexical matchers against
prose with fenced and inline code masked, and return strict or advisory
findings. The structural review runs the registered structural detectors and
recommends at most two high-value interventions per pass, with no change as a
valid result. An optional corpus comparison detects repeated document shapes
(hook, reveal, lesson, close) only when the user supplies two or more
documents; a single document never produces a cross-document convergence
claim.

Design evidence: NulightJens/humanizer-stack at 13f5c02 (MIT). StoryScope
rates and detector thresholds from that repository are not imported.

The report is machine-readable JSON. Surface and structural results stay in
separate sections. Strict findings affect the exit status; advisory findings
do not unless --fail-on-advisory is set.

Usage:
    python3 tools/scan.py --file text.txt --profile general
    cat text.txt | python3 tools/scan.py --profile general
    python3 tools/scan.py --doc a.md --doc b.md --doc c.md
    python3 tools/scan.py --fixtures skills/antislop/evals/staged-scan-fixtures.json
    python3 tools/scan.py --help

Exit codes:
    0 -- the scan ran and no strict finding is present (advisory findings do
         not fail unless --fail-on-advisory)
    1 -- at least one strict finding is present, an advisory finding is
         present with --fail-on-advisory, or a fixture corpus failed
    2 -- usage or input error
"""

import argparse
import json
import os
import re
import sys
from findings import excerpt as _excerpt

import limits
from registry import load_registry, filter_rules_by_profile
import fidelity
import score as scoring
import structural

INTERFACE = "antislop.scan"
SCHEMA = "staged-scan-report-1"
PROFILES = ("general", "technical")

DISCLAIMER = (
    "Staged scan results report strict and advisory findings over prose; "
    "they never prove AI authorship or detector immunity."
)

# The zero-em-dash rule stays strict and absolute: any literal mark in prose
# is a strict finding regardless of profile or context.
EM_DASH_RE = re.compile(r"\u2014|\u2013| -- ")

INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

SURFACE_SEMANTIC_TYPES = ("forbidden", "discouraged")
SURFACE_DETECTIONS = ("exact_match", "phrase_match")

STRUCTURAL_DETECTION = "structural"

SLOTS = ("hook", "reveal", "lesson", "close")
CORPUS_SHAPE_MIN_SLOTS = 2
CORPUS_SHAPE_JACCARD = 0.5
LESSON_MARKERS = ("learned", "lesson", "taught", "takeaway", "the moral",
                  "what i learned", "the lesson")

SENTENCE_END_RE = re.compile(r"[.!?]+(?:\s+|$)")
WORD_RE = re.compile(r"[a-z0-9']+")

STRUCTURAL_DECISIONS = ("no-change", "intervene")
CORPUS_STATES = ("requires-multiple-documents", "no-convergence",
                 "convergence")


def mask_code(text):
    """Blank fenced and inline code with same-length spaces.

    Offsets are preserved so findings over the masked prose keep valid
    positions in the original text. Code is never prose for either stage.
    """
    masked = list(text)
    for pattern in (fidelity.CODE_FENCE_RE, INLINE_CODE_RE):
        for match in pattern.finditer(text):
            for index in range(match.start(), match.end()):
                masked[index] = " "
    return "".join(masked)


def surface_scan(text, registry, profile="general"):
    """Stage 1: deterministic lexical checks over prose-only text.

    Returns strict or advisory findings with spans into the original text.
    Fenced and inline code are masked before any match runs.
    """
    masked = mask_code(text)
    rules = filter_rules_by_profile(registry, profile)
    findings = []

    for rule in rules:
        if rule.get("semantic_type") not in SURFACE_SEMANTIC_TYPES:
            continue
        detection = rule.get("detection_class", "exact_match")
        if detection == "exact_match":
            matches = scoring.find_exact_matches(masked, rule)
        elif detection == "phrase_match":
            matches = scoring.find_phrase_matches(masked, rule)
        else:
            continue
        signal = scoring.rule_signal(rule)
        for match in matches:
            start, end = match.start(), match.end()
            findings.append({
                "rule_id": rule["id"],
                "category": rule["category"],
                "severity": rule["severity"],
                "base_weight": rule["base_weight"],
                "signal": signal,
                "span": [start, end],
                "excerpt": _excerpt(masked, start, end),
                "message": "Detected %s pattern: %s"
                           % (rule["category"], rule["id"]),
                "repair": rule.get("correction", ""),
                "evidence": "span",
            })

    em_dash = next((rule for rule in rules if rule["id"] == "fmt-em-dash"),
                   None)
    if em_dash is not None:
        for match in EM_DASH_RE.finditer(masked):
            start, end = match.start(), match.end()
            findings.append({
                "rule_id": em_dash["id"],
                "category": em_dash["category"],
                "severity": em_dash["severity"],
                "base_weight": em_dash["base_weight"],
                "signal": "strict",
                "span": [start, end],
                "excerpt": _excerpt(masked, start, end),
                "message": "Detected formatting pattern: fmt-em-dash",
                "repair": em_dash.get("correction", ""),
                "evidence": "span",
            })

    findings.sort(key=lambda finding: (finding["span"][0], finding["span"][1]))
    strict_count = sum(1 for finding in findings
                       if finding["signal"] == "strict")
    return {
        "findings": findings,
        "strict_count": strict_count,
        "advisory_count": len(findings) - strict_count,
    }


def structural_review(text, registry, profile="general", max_interventions=2):
    """Stage 2: bounded structural review over prose-only text.

    Detector findings are ranked by value (strict first, then base weight,
    then position) and at most max_interventions are returned. No change is a
    valid result and is never replaced with a mandatory recipe.
    """
    masked = mask_code(text)
    rules = filter_rules_by_profile(registry, profile)
    detector_rules = [rule for rule in rules
                      if rule.get("detection_class") == STRUCTURAL_DETECTION
                      and rule.get("detector") in structural.DETECTORS]
    result = structural.run_detectors(masked, detector_rules, profile)
    findings = sorted(result["findings"], key=lambda finding: (
        0 if finding["signal"] == "strict" else 1,
        -finding.get("base_weight", 0),
        finding["start"],
        finding["end"],
    ))
    rule_by_id = {rule["id"]: rule for rule in detector_rules}
    interventions = []
    for finding in findings[:max_interventions]:
        rule = rule_by_id.get(finding["rule_id"], {})
        interventions.append({
            "rule_id": finding["rule_id"],
            "signal": finding["signal"],
            "evidence": finding.get("evidence", "span"),
            "span": [finding["start"], finding["end"]],
            "message": finding["message"],
            "recommendation": rule.get("correction", ""),
            "sample": finding.get("sample", {}),
        })
    return {
        "decision": "no-change" if not interventions else "intervene",
        "interventions": interventions,
        "count": len(interventions),
        "max_interventions": max_interventions,
        "metrics": result["metrics"],
    }


def _prose_paragraphs(text):
    """Prose paragraphs: code masked, headings, lists, and tables stripped."""
    masked = mask_code(text)
    paragraphs = []
    current = []
    for line in masked.split("\n"):
        t = line.strip()
        if not t:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if (t.startswith("#") or t.startswith(("- ", "* ", "|"))
                or re.match(r"^[0-9]+\.\s", t)):
            continue
        current.append(t)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _sentences(flat):
    result = []
    start = 0
    for match in SENTENCE_END_RE.finditer(flat):
        end = match.start()
        if end > start and flat[start:end].strip():
            result.append(flat[start:end].strip())
        start = match.end()
    if start < len(flat) and flat[start:].strip():
        result.append(flat[start:].strip())
    return result


def _slot_words(text):
    return set(WORD_RE.findall(text.lower()))


def _shape_signature(text):
    """The hook, reveal, lesson, and close slots of one document.

    hook is the first sentence, reveal is the first sentence of the second
    paragraph, lesson is the first sentence carrying a lesson marker, and
    close is the last sentence. A document with one paragraph uses its hook
    as the reveal. Each slot is a normalized word set for Jaccard comparison.
    """
    paragraphs = _prose_paragraphs(text)
    if not paragraphs:
        return {slot: set() for slot in SLOTS}
    first_sentences = _sentences(paragraphs[0])
    last_sentences = _sentences(paragraphs[-1])
    hook = _slot_words(first_sentences[0]) if first_sentences else set()
    if len(paragraphs) >= 2:
        reveal_sentences = _sentences(paragraphs[1])
        reveal = (_slot_words(reveal_sentences[0])
                  if reveal_sentences else set())
    else:
        reveal = hook
    lesson = set()
    for paragraph in paragraphs:
        for sentence in _sentences(paragraph):
            lower = sentence.lower()
            if any(marker in lower for marker in LESSON_MARKERS):
                lesson = _slot_words(sentence)
                break
        if lesson:
            break
    if not lesson:
        lesson = _slot_words(last_sentences[0]) if last_sentences else set()
    close = _slot_words(last_sentences[-1]) if last_sentences else set()
    return {"hook": hook, "reveal": reveal, "lesson": lesson, "close": close}


def _jaccard(a, b):
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def corpus_analysis(documents):
    """Optional stage: repeated document shapes across supplied documents.

    documents is a list of (doc_id, text) pairs. Comparison runs only when
    at least two documents are supplied; a single document always reports
    requires-multiple-documents and never triggers a convergence claim.
    """
    n = len(documents)
    if n < 2:
        return {"state": "requires-multiple-documents", "n": n,
                "convergence_findings": []}
    signatures = [_shape_signature(text) for _doc_id, text in documents]
    findings = []
    for i in range(n):
        for j in range(i + 1, n):
            matched = [slot for slot in SLOTS
                       if _jaccard(signatures[i][slot], signatures[j][slot])
                       >= CORPUS_SHAPE_JACCARD]
            if len(matched) >= CORPUS_SHAPE_MIN_SLOTS:
                findings.append({
                    "kind": "shared_shape",
                    "documents": [documents[i][0], documents[j][0]],
                    "matched_slots": matched,
                    "signal": "advisory",
                })
    findings.sort(key=lambda finding: (finding["documents"][0],
                                       finding["documents"][1]))
    return {
        "state": "convergence" if findings else "no-convergence",
        "n": n,
        "convergence_findings": findings,
    }


def scan_text(text, registry, profile="general"):
    """The two audit stages for one document, without corpus comparison."""
    limits.check_input_size(text)
    return {
        "surface": surface_scan(text, registry, profile),
        "structural": structural_review(text, registry, profile),
    }


def scan_documents(documents, registry, profile="general"):
    """Scan one or more documents and compare corpus shapes when supplied.

    Returns a machine-readable JSON report. Strict findings and advisory
    findings are reported separately per document; the corpus section holds
    the optional cross-document shape comparison.
    """
    limits.check_input_collection(
        [text for _document_id, text in documents])
    per_doc = []
    strict_present = False
    advisory_present = False
    for doc_id, text in documents:
        result = scan_text(text, registry, profile)
        result["id"] = doc_id
        per_doc.append(result)
        strict_present = (
            strict_present
            or result["surface"]["strict_count"] > 0
            or any(intervention["signal"] == "strict"
                   for intervention in result["structural"]["interventions"]))
        advisory_present = (
            advisory_present
            or result["surface"]["advisory_count"] > 0
            or any(intervention["signal"] == "advisory"
                   for intervention in result["structural"]["interventions"]))
    corpus = corpus_analysis(documents)
    convergence = bool(corpus["convergence_findings"])
    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "mode": "corpus" if len(documents) > 1 else "scan",
        "profile": profile,
        "document_count": len(documents),
        "documents": per_doc,
        "corpus": corpus,
        "signals": {
            "strict_present": strict_present,
            "advisory_present": advisory_present or convergence,
            "convergence_present": convergence,
        },
        "meta": {
            "disclaimer": DISCLAIMER,
        },
    }


def exit_status(report, fail_on_advisory=False):
    """Exit status from a scan report.

    Strict findings fail. Advisory findings fail only when configured, the
    same switch that makes corpus convergence fail.
    """
    if report["signals"]["strict_present"]:
        return 1
    if fail_on_advisory and report["signals"]["advisory_present"]:
        return 1
    return 0


def validate_staged_fixture(fixture, seen_ids):
    """Schema-validate one staged-scan fixture. Returns error strings."""
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

    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(PROFILES)))

    has_source = isinstance(fixture.get("source"), str) and fixture["source"].strip()
    corpus = fixture.get("corpus")
    has_corpus = isinstance(corpus, list) and len(corpus) >= 2
    if has_source and has_corpus:
        errors.append("%s: give 'source' or 'corpus', not both" % where)
    if not has_source and not has_corpus:
        errors.append("%s: needs a non-empty 'source' or a 'corpus' list of "
                      "at least two documents" % where)

    if has_corpus:
        for index, doc in enumerate(corpus):
            if not isinstance(doc, dict):
                errors.append("%s: corpus[%d] must be an object" % (where, index))
                continue
            if not (isinstance(doc.get("id"), str) and doc["id"].strip()):
                errors.append("%s: corpus[%d] needs a non-empty 'id'"
                              % (where, index))
            if not (isinstance(doc.get("text"), str) and doc["text"].strip()):
                errors.append("%s: corpus[%d] needs a non-empty 'text'"
                              % (where, index))

    for field in ("expected_surface_strict", "expected_surface_advisory",
                  "expected_structural_count", "expected_convergence_count"):
        value = fixture.get(field)
        if value is not None and (not isinstance(value, int)
                                  or isinstance(value, bool) or value < 0):
            errors.append("%s: %s must be a non-negative integer"
                          % (where, field))

    expected_rule_ids = fixture.get("expected_structural_rule_ids")
    if expected_rule_ids is not None:
        if (not isinstance(expected_rule_ids, list)
                or any(not isinstance(rule_id, str) or not rule_id.strip()
                       for rule_id in expected_rule_ids)
                or len(expected_rule_ids) != len(set(expected_rule_ids))):
            errors.append("%s: expected_structural_rule_ids must be a list "
                          "of unique non-empty strings" % where)

    decision = fixture.get("expected_structural_decision")
    if decision is not None and decision not in STRUCTURAL_DECISIONS:
        errors.append("%s: expected_structural_decision must be one of %s"
                      % (where, ", ".join(STRUCTURAL_DECISIONS)))

    state = fixture.get("expected_corpus_state")
    if state is not None and state not in CORPUS_STATES:
        errors.append("%s: expected_corpus_state must be one of %s"
                      % (where, ", ".join(CORPUS_STATES)))

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
    """Compare a computed scan report against its fixture expectations."""
    failures = []
    single = report["documents"][0]

    expected = fixture.get("expected_surface_strict")
    if expected is not None and single["surface"]["strict_count"] != expected:
        failures.append("expected %d strict surface finding(s), got %d"
                        % (expected, single["surface"]["strict_count"]))
    expected = fixture.get("expected_surface_advisory")
    if expected is not None and single["surface"]["advisory_count"] != expected:
        failures.append("expected %d advisory surface finding(s), got %d"
                        % (expected, single["surface"]["advisory_count"]))

    expected = fixture.get("expected_structural_decision")
    if expected is not None and single["structural"]["decision"] != expected:
        failures.append("expected structural decision %s, got %s"
                        % (expected, single["structural"]["decision"]))
    expected = fixture.get("expected_structural_count")
    if expected is not None and single["structural"]["count"] != expected:
        failures.append("expected %d structural intervention(s), got %d"
                        % (expected, single["structural"]["count"]))
    expected_rule_ids = fixture.get("expected_structural_rule_ids")
    if expected_rule_ids is not None:
        actual_rule_ids = [item["rule_id"]
                           for item in single["structural"]["interventions"]]
        if actual_rule_ids != expected_rule_ids:
            failures.append("expected structural rule ids %s, got %s"
                            % (expected_rule_ids, actual_rule_ids))
    if single["structural"]["count"] > single["structural"]["max_interventions"]:
        failures.append("structural interventions exceed the bound of %d"
                        % single["structural"]["max_interventions"])

    if not fixture.get("corpus"):
        if report["corpus"]["state"] != "requires-multiple-documents":
            failures.append("single document corpus state is %s, expected "
                            "requires-multiple-documents"
                            % report["corpus"]["state"])
        if report["corpus"]["convergence_findings"]:
            failures.append("a single document triggered a cross-document "
                            "convergence claim")

    expected = fixture.get("expected_corpus_state")
    if expected is not None and report["corpus"]["state"] != expected:
        failures.append("expected corpus state %s, got %s"
                        % (expected, report["corpus"]["state"]))
    expected = fixture.get("expected_convergence_count")
    if expected is not None and len(report["corpus"]["convergence_findings"]) != expected:
        failures.append("expected %d convergence finding(s), got %d"
                        % (expected, len(report["corpus"]["convergence_findings"])))
    return failures


def run_staged_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one staged-scan fixture against its expectations."""
    fid = fixture["id"]
    profile = fixture.get("profile", "general")
    if fixture.get("corpus"):
        documents = [(doc["id"], doc["text"]) for doc in fixture["corpus"]]
    else:
        documents = [("single", fixture["source"])]
    report = scan_documents(documents, registry, profile)
    report["id"] = fid
    report["expected_corpus_state"] = fixture.get("expected_corpus_state")
    report["meta"]["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
    report["failures"] = fixture_failures(report, fixture)
    return report


def run_staged_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the staged-scan fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_staged_fixture(fixture, seen_ids))

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

    reports = [run_staged_fixture(fixture, registry, registry_path)
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
            "profile": report["profile"],
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


def _read_documents(paths):
    """Read a corpus without allocating beyond the aggregate text budget."""
    documents = []
    total = 0
    for path in paths:
        remaining = limits.MAX_INPUT_CHARS - total
        text = _read_document(path, max_chars=remaining)
        documents.append((path, text))
        total += len(text)
    return documents


def main():
    parser = argparse.ArgumentParser(description="Antislop staged scan")
    parser.add_argument("--file", default=None,
                        help="Path to a single document to scan")
    parser.add_argument("--doc", action="append", default=[],
                        help="Path to a corpus document (repeatable); two or "
                             "more enable the cross-document shape comparison")
    parser.add_argument("--profile", default="general",
                        help="Writing profile (default: general)")
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--fail-on-advisory", action="store_true",
                        help="Advisory findings and corpus convergence fail "
                             "the exit status too")
    parser.add_argument("--fixtures", default=None,
                        help="Run the staged-scan fixture corpus instead of "
                             "scanning input")
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
        report = run_staged_corpus(fixtures.get("evals", fixtures), registry,
                                   args.registry)
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

    if documents:
        if len(documents) < 2:
            print(json.dumps({
                "error": "corpus comparison needs at least two documents; "
                         "use --doc twice or scan a single --file",
            }, indent=2))
            sys.exit(2)
    elif args.file:
        if not os.path.exists(args.file):
            print(json.dumps({"error": "file not found: %s" % args.file},
                             indent=2))
            sys.exit(2)
        try:
            documents.append((args.file, _read_document(args.file)))
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
    elif not sys.stdin.isatty():
        try:
            stdin_text = limits.read_text(sys.stdin)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
        if not stdin_text.strip():
            print(json.dumps({"error": "Empty input"}, indent=2))
            sys.exit(2)
        documents.append(("stdin", stdin_text))
    else:
        print(json.dumps({"error": "No input. Use --file, --doc, or pipe "
                                   "text."}, indent=2))
        sys.exit(2)

    try:
        report = scan_documents(documents, registry, args.profile)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)
    print(json.dumps(report, indent=2))
    sys.exit(exit_status(report, args.fail_on_advisory))


if __name__ == "__main__":
    main()
