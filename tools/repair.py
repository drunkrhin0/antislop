#!/usr/bin/env python3
"""Unslop-style protected repair interface (issue #92).

A registry-aware repair command for prose embedded in Markdown or technical
documents. It accepts stdin or one named file and emits text, JSON, or a
unified diff. Protected regions (fenced and indented code, inline code, YAML
and JSON blocks, tables, blockquotes, headings, Markdown links, URLs, paths,
commands, quoted source text, numbers, dates, units, operators, and required
terms) stay byte-identical. A failed preservation check prevents any write and
returns a nonzero status.

Repair classes, all deterministic:

  replace   exact phrase replacement for a deterministic forbidden or
            discouraged rule whose correction supplies a literal replacement
  split     one supported deterministic structural case: splitting an
            overlong sentence at a comma-preceded conjunction while retaining
            both clauses and their punctuation meaning
  remove    leaked reasoning or planning wrappers, classified as integrity
            findings and removed only when they sit outside quoted or code
            material
  keep      a protected or unrepairable finding, left byte-identical and
            recorded as unresolved

A proposed repair (--edit) runs through the same fidelity preservation gate:
an attempt that changes a number, qualifier, or other protected span fails and
is never written.

Every repair reruns both audit stages on the candidate and reports residual
findings in the report's residual_scan section, so a deterministic defect that
survives the repair stays visible next to whatever the structural review still
recommends.

Boundaries: no detector feedback, surprisal targets, detector bypass modes,
external models, persistent voice facts, or em-dash allowance. Numeric style
traits stay out of scope for a later author profile.

Usage:
    python3 tools/repair.py --file doc.md
    cat doc.md | python3 tools/repair.py --format json
    python3 tools/repair.py --file doc.md --write
    python3 tools/repair.py --file doc.md --format diff
    python3 tools/repair.py --file doc.md --edit 0-5=use --write
    python3 tools/repair.py --fixtures skills/antislop/evals/repair-fixtures.json
    python3 tools/repair.py --help

Exit codes:
    0 -- repair ran; decision accept or no-change
    1 -- a preservation check failed; the write was prevented
    2 -- usage or input error
"""

import argparse
import difflib
import json
import os
import re
import sys
import tempfile

import limits
from registry import load_registry
import fidelity
import scan
import score as scoring

DEFAULT_PROFILE = "general"
DEFAULT_REGISTRY = "rules.json"

DECISIONS = ("accept", "no-change", "reject")
PROFILES = {"general", "technical"}

DISCLAIMER = (
    "Repair results report deterministic edits and preservation; they never "
    "prove AI authorship or detector immunity."
)

REPAIRABLE_SEMANTIC_TYPES = ("forbidden", "discouraged")
REPAIRABLE_DETECTION = ("exact_match", "phrase_match")


def atomic_write_text(path, text):
    """Atomically replace the named file while preserving its mode."""
    target = os.path.realpath(path)
    directory = os.path.dirname(target)
    original = os.stat(target)
    fd, temporary = tempfile.mkstemp(prefix=".antislop-repair-",
                                     dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            fd = None
            stream.write(text)
            stream.flush()
            os.fchmod(stream.fileno(), original.st_mode & 0o7777)
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if fd is not None:
            os.close(fd)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

SPLIT_MIN_COMMAS = 3
SPLIT_MIN_HALF_WORDS = 4
SPLIT_CONJUNCTIONS = ("and", "but", "or", "so", "yet", "while", "whereas")

INTEGRITY_RULE_ID = "integrity-leaked-reasoning"

SENTENCE_END_RE = re.compile(r"[.!?]+(?:\s+|$)")
WORD_RE = re.compile(r"[A-Za-z0-9']+")

FENCE_RE = fidelity.CODE_FENCE_RE
FENCE_LANG_RE = re.compile(r"```\s*([A-Za-z0-9_+-]+)")

MARKDOWN_LINK_RE = re.compile(
    r"\[[^\]\n]*\]\([^)\n]+\)"
    r"|\[[^\]\n]*\]\[[^\]\n]*\]"
    r"|\[[^\]\n]*\]:[^\n]*"
)

INDENTED_CODE_RE = re.compile(r"^ {4,}\S")
TABLE_ROW_RE = re.compile(r"^\|.*\|")
TABLE_SEP_RE = re.compile(r"^\|?[\s:|-]+\|?$")
BLOCKQUOTE_RE = re.compile(r"^>\s?")
HEADING_RE = re.compile(r"^#{1,6}\s+\S")
COMMAND_RE = re.compile(r"^\$\s+\S")

TEXT_REASONING_RE = re.compile(
    r"\bLet me (?:think about this step by step|think step by step|"
    r"reason through this|work through this|consider this|analyze this|"
    r"break this down|start by)\b"
    r"|\bLet's think (?:about this)?\b"
    r"|\bHere('s| is) my (?:step-by-step )?(?:reasoning|thinking|analysis|plan)\b"
    r"|\bAs an AI(?: language model)?\b",
    re.IGNORECASE,
)
MAX_REASONING_TAG_OPEN_CHARS = 200
TAG_REASONING_RE = re.compile(
    r"<(?:thought|thinking|reasoning)[^>]{0,"
    + str(MAX_REASONING_TAG_OPEN_CHARS)
    + r"}>.{0,1000}?</(?:thought|thinking|reasoning)>",
    re.IGNORECASE | re.DOTALL,
)
LEAKED_REASONING_RE = re.compile(
    TEXT_REASONING_RE.pattern + "|" + TAG_REASONING_RE.pattern,
    re.IGNORECASE | re.DOTALL,
)


def _literal_replacement(rule):
    """A literal replacement derived from a rule's correction, when the
    correction names one directly ('Use 'X'.'), or None.

    Corrections that advise rather than supply text (cut this, say what
    changed) have no mechanical replacement, so the finding is left
    unresolved.
    """
    correction = rule.get("correction", "") or ""
    match = re.match(r"\s*[Uu]se\s+['\"]([^'\"]+)['\"]", correction)
    if match is None:
        return None
    return match.group(1).strip()


def literal_replacement(rule):
    """Public wrapper for the literal correction a rule's guidance names.

    Reused by the bounded repair loop (repair_loop.py) so both paths source
    corrections from the same registry authority.
    """
    return _literal_replacement(rule)


def _line_spans(text):
    spans = []
    pos = 0
    for line in text.split("\n"):
        spans.append((pos, pos + len(line)))
        pos += len(line) + 1
    return spans


def _run_spans(line_spans, lines, predicate):
    runs = []
    index = 0
    while index < len(lines):
        if not predicate(lines[index]):
            index += 1
            continue
        end = index
        while end + 1 < len(lines) and predicate(lines[end + 1]):
            end += 1
        runs.append((line_spans[index][0], line_spans[end][1]))
        index = end + 1
    return runs


def _block_regions(text):
    lines = text.split("\n")
    spans = _line_spans(text)
    regions = []

    for start, end in _run_spans(spans, lines, INDENTED_CODE_RE.match):
        regions.append({"category": "indented_code", "start": start,
                        "end": end})

    def is_table_row(line):
        return bool(TABLE_ROW_RE.match(line.strip())) or bool(
            TABLE_SEP_RE.match(line.strip()) and "-" in line)

    for start, end in _run_spans(spans, lines, is_table_row):
        regions.append({"category": "table", "start": start, "end": end})

    for start, end in _run_spans(spans, lines,
                                 lambda line: BLOCKQUOTE_RE.match(line)):
        regions.append({"category": "blockquote", "start": start, "end": end})

    for start, end in _run_spans(spans, lines, COMMAND_RE.match):
        regions.append({"category": "command", "start": start, "end": end})

    for index, line in enumerate(lines):
        if HEADING_RE.match(line):
            regions.append({"category": "heading", "start": spans[index][0],
                            "end": spans[index][1]})

    for match in FENCE_RE.finditer(text):
        opening = text[match.start():match.start() + 8]
        lang = FENCE_LANG_RE.match(opening)
        label = "code_block"
        if lang is not None:
            language = lang.group(1).lower()
            if language in ("yaml", "yml"):
                label = "yaml_block"
            elif language == "json":
                label = "json_block"
        regions.append({"category": label, "start": match.start(),
                        "end": match.end()})

    return regions


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _dedupe_regions(regions):
    kept = []
    for region in sorted(regions, key=lambda r: (r["start"], -r["end"])):
        if any(_overlaps(region["start"], region["end"],
                         existing["start"], existing["end"])
               for existing in kept):
            continue
        kept.append(region)
    kept.sort(key=lambda r: r["start"])
    return kept


def protected_regions(text, required_terms=()):
    """Every protected region in text, byte-identical targets for a repair.

    Combines fidelity.py's span extractor (inline code and quoted source,
    URLs, paths, numbers, dates, units, operators, required terms, fenced
    code) with Markdown-aware block and inline protection: indented code,
    YAML and JSON blocks, tables, blockquotes, headings, commands, and
    Markdown links. Returns sorted, non-overlapping records.
    """
    base = fidelity.extract_anchors(text, required_terms)["protected_spans"]
    regions = _block_regions(text)
    for match in MARKDOWN_LINK_RE.finditer(text):
        regions.append({"category": "markdown_link", "start": match.start(),
                        "end": match.end()})
    regions.extend({"category": span["category"], "start": span["start"],
                    "end": span["end"]} for span in base)
    return _dedupe_regions(regions)


def _overlaps_protected(start, end, regions):
    return any(_overlaps(start, end, region["start"], region["end"])
               for region in regions)


def _spans_overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _would_reintroduce(text, start, end, replacement, registry, profile):
    """True when applying a replacement would fire another repairable finding
    inside the replacement region. The guard keeps the repair idempotent: a
    second pass over the same text plans no new edits."""
    after = text[:start] + replacement + text[end:]
    findings, _skipped, _metrics = scoring.detect_findings(
        after, registry, profile)
    replacement_end = start + len(replacement)
    for finding in findings:
        f_start = finding["position"]
        f_end = f_start + finding.get("match_length", 6)
        if _spans_overlap(f_start, f_end, start, replacement_end):
            return True
    return False


def _findings_with_rules(text, registry, profile):
    rules = registry.get("rules", [])
    rule_by_id = {rule["id"]: rule for rule in rules}
    findings, _skipped, _metrics = scoring.detect_findings(
        text, registry, profile)
    findings = scoring.handle_overlaps(findings)
    return findings, rule_by_id


def _repairable(rule):
    return (rule.get("semantic_type") in REPAIRABLE_SEMANTIC_TYPES
            and rule.get("review_mode") == "deterministic"
            and rule.get("detection_class") in REPAIRABLE_DETECTION)


def repairable_rule(rule):
    """Public wrapper for the deterministic-repair eligibility check.

    Reused by the bounded repair loop (repair_loop.py) so both paths gate on
    the same repairable rule classes.
    """
    return _repairable(rule)


def _split_candidates(text):
    """Deterministic clause-boundary splits for overlong sentences.

    A candidate is a comma-preceded conjunction in a sentence with at least
    SPLIT_MIN_COMMAS commas where both halves carry at least
    SPLIT_MIN_HALF_WORDS words. Splitting there replaces the comma with a
    period and keeps the conjunction, so both clauses and their punctuation
    meaning survive. The last qualifying conjunction in the sentence wins.
    """
    candidates = []
    start = 0
    for match in SENTENCE_END_RE.finditer(text):
        sentence_end = match.start()
        if sentence_end > start:
            sentence = text[start:sentence_end]
            commas = sentence.count(",")
            if commas >= SPLIT_MIN_COMMAS:
                split = _split_point(sentence)
                if split is not None:
                    s_start, s_end, conjunction = split
                    candidates.append({
                        "start": start + s_start,
                        "end": start + s_end,
                        "replacement": ". " + conjunction.capitalize() + " ",
                        "rule_id": "struct-overlong-sentence",
                        "action": "split",
                        "original": sentence[s_start:s_end],
                    })
        start = match.end()
    return candidates


def _split_point(sentence):
    best = None
    for conjunction in SPLIT_CONJUNCTIONS:
        pattern = re.compile(r",\s+" + re.escape(conjunction) + r"\s+",
                             re.IGNORECASE)
        for match in pattern.finditer(sentence):
            first_half = sentence[:match.start()]
            second_half = sentence[match.end():]
            if (len(WORD_RE.findall(first_half)) >= SPLIT_MIN_HALF_WORDS
                    and len(WORD_RE.findall(second_half)) >=
                    SPLIT_MIN_HALF_WORDS):
                best = (match.start(), match.end(), conjunction)
    return best


def _integrity_matches(text, regions):
    matches = []
    for match in TEXT_REASONING_RE.finditer(text):
        inside = _overlaps_protected(match.start(), match.end(), regions)
        matches.append({
            "start": match.start(),
            "end": match.end(),
            "value": match.group(0),
            "inside_protected": inside,
        })
    if any(tag in text for tag in ("</thought>", "</thinking>", "</reasoning>")):
        for match in TAG_REASONING_RE.finditer(text):
            inside = _overlaps_protected(match.start(), match.end(), regions)
            matches.append({
                "start": match.start(),
                "end": match.end(),
                "value": match.group(0),
                "inside_protected": inside,
            })
    matches.sort(key=lambda m: (m["start"], m["end"]))
    return matches


def _remove_span(text, match):
    start, end = match["start"], match["end"]
    while end < len(text) and text[end] in " .!?:;":
        end += 1
    return start, end


def plan_edits(text, registry, profile="general", regions=None):
    """Plan one repair pass on text. Returns (edits, records).

    edits are deterministic, non-overlapping repairs to apply. records are
    the JSON replacement records for every planned item, applied or kept.
    Protected regions stay untouched; a finding inside one is kept and
    recorded unresolved.
    """
    if regions is None:
        regions = protected_regions(text)
    findings, rule_by_id = _findings_with_rules(text, registry, profile)

    edits = []
    records = []

    def add_edit(edit):
        if any(_overlaps(edit["start"], edit["end"],
                         existing["start"], existing["end"])
               for existing in edits):
            return
        edits.append(edit)

    for finding in findings:
        if not finding.get("primary", True):
            continue
        rule = rule_by_id.get(finding["rule_id"])
        if rule is None or not _repairable(rule):
            continue
        start = finding["position"]
        end = start + finding.get("match_length", 6)
        original = text[start:end]
        replacement = _literal_replacement(rule)
        if replacement is None:
            records.append({
                "rule_id": finding["rule_id"], "span": [start, end],
                "action": "keep", "original": original,
                "replacement": "", "preservation": "passed",
                "unresolved": True,
                "reason": "no literal replacement",
            })
            continue
        if _overlaps_protected(start, end, regions):
            records.append({
                "rule_id": finding["rule_id"], "span": [start, end],
                "action": "keep", "original": original,
                "replacement": "", "preservation": "protected",
                "unresolved": True,
                "reason": "inside a protected region",
            })
            continue
        if _would_reintroduce(text, start, end, replacement, registry, profile):
            records.append({
                "rule_id": finding["rule_id"], "span": [start, end],
                "action": "keep", "original": original,
                "replacement": "", "preservation": "passed",
                "unresolved": True,
                "reason": "replacement would reintroduce a finding",
            })
            continue
        add_edit({
            "start": start, "end": end, "replacement": replacement,
            "rule_id": finding["rule_id"], "action": "replace",
            "original": original,
        })

    for split in _split_candidates(text):
        if _overlaps_protected(split["start"], split["end"], regions):
            records.append({
                "rule_id": split["rule_id"],
                "span": [split["start"], split["end"]],
                "action": "keep", "original": split["original"],
                "replacement": "", "preservation": "protected",
                "unresolved": True,
                "reason": "inside a protected region",
            })
            continue
        add_edit(split)

    for match in _integrity_matches(text, regions):
        original = text[match["start"]:match["end"]]
        if match["inside_protected"]:
            records.append({
                "rule_id": INTEGRITY_RULE_ID,
                "span": [match["start"], match["end"]],
                "action": "keep", "original": original,
                "replacement": "", "preservation": "protected",
                "unresolved": True,
                "reason": "inside quoted or code material",
            })
            continue
        r_start, r_end = _remove_span(text, match)
        add_edit({
            "start": r_start, "end": r_end, "replacement": "",
            "rule_id": INTEGRITY_RULE_ID, "action": "remove",
            "original": text[r_start:r_end],
        })

    return edits, records


def apply_edits(text, edits):
    """Apply non-overlapping edits to text."""
    result = text
    for edit in sorted(edits, key=lambda edit: edit["start"], reverse=True):
        result = (result[:edit["start"]] + edit["replacement"]
                  + result[edit["end"]:])
    return result


def _mask_spans(text, spans):
    """Replace the given spans with same-length spaces.

    Used for the integrity gate: a removed leaked-reasoning wrapper is an
    output defect, not author prose, so the anchors inside it (scope words
    like 'about', modality like 'can') must not count as meaning removed from
    the source. Masking hides exactly the removed wrapper text while keeping
    every other span comparable.
    """
    masked = list(text)
    for start, end in spans:
        for index in range(start, end):
            masked[index] = " "
    return "".join(masked)


def check_candidate(source, candidate, profile=DEFAULT_PROFILE,
                    hot_zones=(), required_terms=(),
                    registry_path=DEFAULT_REGISTRY):
    """The preservation gate for a repair candidate.

    A thin wrapper over fidelity.py's source-to-candidate check: protected
    spans must stay byte-identical and semantic anchors must hold. The repair
    never writes when this gate fails.
    """
    return fidelity.check_fidelity(
        source, candidate,
        required_terms=required_terms,
        hot_zones=list(hot_zones),
        churn_limit=None,
        registry_path=registry_path,
        profile=profile,
    )


def _risk(source, candidate, registry, profile):
    source_score = candidate_score = None
    for label, text in (("source", source), ("candidate", candidate)):
        try:
            result = scoring.score_text(text, registry, profile)
            if label == "source":
                source_score = result["score"]
            else:
                candidate_score = result["score"]
        except Exception:  # noqa: BLE001 -- risk is advisory, never a gate
            continue
    delta = None
    improved = False
    if source_score is not None and candidate_score is not None:
        delta = candidate_score - source_score
        improved = delta > 0
    return {
        "source_score": source_score,
        "candidate_score": candidate_score,
        "delta": delta,
        "improved": improved,
        "advisory": True,
        "authorship_evidence": False,
        "disclaimer": (
            "Score deltas are advisory risk signals, never authorship "
            "evidence."
        ),
    }


def _gate_failed(report):
    return (report["decision"] == "reject"
            or report["decision"] == "review"
            or report["preservation"]["status"] == "failed")


def _source_to_candidate_offset(records, pos):
    """Map a source position into candidate coordinates using applied edits.

    Protected regions never overlap an applied edit, so a position inside one
    maps through the cumulative length delta of every edit that ends before
    it.
    """
    delta = 0
    for record in sorted(records, key=lambda record: record["span"][0]):
        if record["action"] == "keep":
            continue
        start, end = record["span"]
        if pos >= end:
            delta += len(record["replacement"]) - (end - start)
    return pos + delta


def repair_text(text, registry, profile=DEFAULT_PROFILE,
                required_terms=(), registry_path=DEFAULT_REGISTRY):
    """Repair a single text automatically. Returns a JSON-serializable report.

    The planner protects every protected region, applies deterministic exact
    phrase, structural split, and integrity removal edits in one pass, then
    runs the fidelity preservation gate. Because each replacement is checked
    against reintroducing a repairable finding, a second repair over the
    candidate plans no new edits and returns identical output.
    """
    limits.check_input_size(text)
    regions = protected_regions(text, required_terms)
    edits, records = plan_edits(text, registry, profile, regions)
    candidate = apply_edits(text, edits)

    hot_zones = [{"start": edit["start"], "end": edit["end"],
                  "label": edit["rule_id"]} for edit in edits]
    removal_spans = [(edit["start"], edit["end"]) for edit in edits
                     if edit["action"] == "remove"]
    gate_source = _mask_spans(text, removal_spans) if removal_spans else text
    gate = check_candidate(gate_source, candidate, profile, hot_zones,
                           required_terms, registry_path)

    if not edits:
        decision = "no-change"
    elif _gate_failed(gate):
        decision = "reject"
    else:
        decision = "accept"

    preservation = "passed"
    if decision == "reject":
        preservation = "failed"
    for record in records:
        if record["action"] == "keep":
            continue
        record["preservation"] = preservation

    for edit in edits:
        if any(record["span"] == [edit["start"], edit["end"]]
               and record["rule_id"] == edit["rule_id"]
               for record in records):
            continue
        records.append({
            "rule_id": edit["rule_id"], "span": [edit["start"], edit["end"]],
            "action": edit["action"], "original": edit["original"],
            "replacement": edit["replacement"],
            "preservation": preservation, "unresolved": False,
        })
    records.sort(key=lambda record: (record["span"][0], record["span"][1]))

    integrity_matches = _integrity_matches(text, regions)
    integrity = {
        "findings": [{
            "rule_id": INTEGRITY_RULE_ID,
            "span": [match["start"], match["end"]],
            "value": match["value"],
            "inside_protected": match["inside_protected"],
            "removed": (not match["inside_protected"]
                        and decision in ("accept", "no-change")),
        } for match in integrity_matches],
        "removed_count": sum(1 for match in integrity_matches
                             if not match["inside_protected"]),
        "kept_count": sum(1 for match in integrity_matches
                          if match["inside_protected"]),
    }

    report = {
        "interface": "antislop.repair",
        "schema": "repair-report-1",
        "version": registry.get("version", "unknown"),
        "mode": "repair",
        "profile": profile,
        "edited": candidate != text,
        "written": False,
        "dry_run": True,
        "decision": decision,
        "replacement_count": len(edits),
        "replacements": records,
        "integrity": integrity,
        "protected_regions": regions,
        "preservation": {
            "status": "passed" if not _gate_failed(gate) else "failed",
            "gate_decision": gate["decision"],
            "hard_failures": gate["preservation"]["hard_failures"],
            "protected_spans": gate["preservation"]["protected_spans"],
        },
        "fidelity": {
            "decision": gate["decision"],
            "reason": gate["reason"],
        },
        "residual_scan": scan.scan_text(candidate, registry, profile),
        "risk": _risk(text, candidate, registry, profile),
        "text": candidate,
        "meta": {
            "disclaimer": DISCLAIMER,
        },
    }
    return report


def repair_proposal(source, edits, registry, profile=DEFAULT_PROFILE,
                    required_terms=(), registry_path=DEFAULT_REGISTRY):
    """Gate a proposed repair (--edit) through the preservation check.

    A proposed edit that changes a number, qualifier, or other protected span
    fails the fidelity gate: the report decision is reject, the write is
    prevented, and the exit status is nonzero.
    """
    limits.check_input_size(source, "source")
    regions = protected_regions(source, required_terms)
    normalized = []
    for edit in edits:
        start = int(edit["start"])
        end = int(edit["end"])
        if start < 0 or end > len(source) or start >= end:
            raise ValueError("proposed edit span [%d, %d) is outside the "
                             "source" % (start, end))
        if any(_overlaps(start, end, existing["start"], existing["end"])
               for existing in normalized):
            raise ValueError("proposed edits must not overlap")
        normalized.append({
            "start": start, "end": end,
            "replacement": edit.get("replacement", ""),
            "rule_id": edit.get("rule_id", "proposed"),
            "action": edit.get("action", "replace"),
            "original": source[start:end],
        })

    candidate = apply_edits(source, normalized)
    hot_zones = [{"start": edit["start"], "end": edit["end"],
                  "label": edit["rule_id"]} for edit in normalized]
    gate = check_candidate(source, candidate, profile, hot_zones, required_terms,
                           registry_path)

    if candidate == source:
        decision = "no-change"
    elif _gate_failed(gate):
        decision = "reject"
    else:
        decision = "accept"

    preservation = "failed" if decision == "reject" else "passed"
    records = [{
        "rule_id": edit["rule_id"],
        "span": [edit["start"], edit["end"]],
        "action": edit["action"],
        "original": edit["original"],
        "replacement": edit["replacement"],
        "preservation": preservation,
        "unresolved": decision == "reject",
    } for edit in normalized]

    return {
        "interface": "antislop.repair",
        "schema": "repair-report-1",
        "version": registry.get("version", "unknown"),
        "mode": "proposed",
        "profile": profile,
        "edited": candidate != source,
        "written": False,
        "dry_run": True,
        "decision": decision,
        "replacement_count": len(normalized),
        "replacements": records,
        "integrity": {
            "findings": [], "removed_count": 0, "kept_count": 0,
        },
        "protected_regions": regions,
        "preservation": {
            "status": "passed" if not _gate_failed(gate) else "failed",
            "gate_decision": gate["decision"],
            "hard_failures": gate["preservation"]["hard_failures"],
            "protected_spans": gate["preservation"]["protected_spans"],
        },
        "fidelity": {
            "decision": gate["decision"],
            "reason": gate["reason"],
        },
        "residual_scan": scan.scan_text(candidate, registry, profile),
        "risk": _risk(source, candidate, registry, profile),
        "text": candidate,
        "meta": {
            "disclaimer": DISCLAIMER,
        },
    }


def _unified_diff(source, candidate, path="<stdin>"):
    lines = list(difflib.unified_diff(
        source.splitlines(keepends=True),
        candidate.splitlines(keepends=True),
        fromfile=path, tofile=path + ".repaired"))
    return "".join(lines)


def validate_repair_fixture(fixture, seen_ids):
    """Schema-validate one repair fixture. Returns error strings."""
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

    expected = fixture.get("expected_decision")
    if expected not in DECISIONS:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(DECISIONS)))

    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(sorted(PROFILES))))

    expected_text = fixture.get("expected_text")
    if expected_text is not None and not isinstance(expected_text, str):
        errors.append("%s: expected_text must be a string" % where)

    count = fixture.get("expected_replacement_count")
    if count is not None and (not isinstance(count, int) or count < 0):
        errors.append("%s: expected_replacement_count must be a "
                      "non-negative integer" % where)

    replacements = fixture.get("expected_replacements", [])
    if not isinstance(replacements, list):
        errors.append("%s: expected_replacements must be a list" % where)
    else:
        for index, item in enumerate(replacements):
            if not isinstance(item, dict):
                errors.append("%s: expected_replacements[%d] must be an "
                              "object" % (where, index))
                continue
            if not (isinstance(item.get("rule_id"), str)
                    and item["rule_id"].strip()):
                errors.append("%s: expected_replacements[%d] missing "
                              "non-empty 'rule_id'" % (where, index))
            if item.get("action") not in ("replace", "split", "remove",
                                          "keep", "proposed"):
                errors.append("%s: expected_replacements[%d].action must be "
                              "one of replace, split, remove, keep, proposed"
                              % (where, index))

    unresolved = fixture.get("expected_unresolved", [])
    if not isinstance(unresolved, list):
        errors.append("%s: expected_unresolved must be a list" % where)
    else:
        for index, item in enumerate(unresolved):
            if not (isinstance(item, str) and item.strip()):
                errors.append("%s: expected_unresolved[%d] must be a "
                              "non-empty string" % (where, index))

    removed = fixture.get("expected_integrity_removed")
    if removed is not None and (not isinstance(removed, int) or removed < 0):
        errors.append("%s: expected_integrity_removed must be a "
                      "non-negative integer" % where)
    kept = fixture.get("expected_integrity_kept")
    if kept is not None and (not isinstance(kept, int) or kept < 0):
        errors.append("%s: expected_integrity_kept must be a "
                      "non-negative integer" % where)

    preserved = fixture.get("expected_preserved", [])
    if not isinstance(preserved, list):
        errors.append("%s: expected_preserved must be a list" % where)
    else:
        for index, item in enumerate(preserved):
            if not (isinstance(item, str) and item.strip()):
                errors.append("%s: expected_preserved[%d] must be a "
                              "non-empty string" % (where, index))

    proposed = fixture.get("proposed_edits", [])
    if not isinstance(proposed, list):
        errors.append("%s: proposed_edits must be a list" % where)
    else:
        for index, item in enumerate(proposed):
            if not isinstance(item, dict):
                errors.append("%s: proposed_edits[%d] must be an object"
                              % (where, index))
                continue
            for field in ("start", "end"):
                if not isinstance(item.get(field), int):
                    errors.append("%s: proposed_edits[%d].%s must be an "
                                  "integer" % (where, index, field))
            if not isinstance(item.get("replacement"), str):
                errors.append("%s: proposed_edits[%d].replacement must be a "
                              "string" % (where, index))

    rationale = fixture.get("false_positive_rationale")
    if rationale is not None and (not isinstance(rationale, str)
                                  or not rationale.strip()):
        errors.append("%s: false_positive_rationale must be a non-empty "
                      "string" % where)

    notes = fixture.get("reviewer_notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append("%s: reviewer_notes must be a non-empty string" % where)
    return errors


def run_repair_fixture(fixture, registry, registry_path=DEFAULT_REGISTRY):
    """Evaluate one repair fixture against its expectations."""
    fid = fixture["id"]
    profile = fixture.get("profile", "general")
    source = fixture["source"]
    if fixture.get("proposed_edits"):
        report = repair_proposal(source, fixture["proposed_edits"], registry,
                                 profile, registry_path=registry_path)
    else:
        report = repair_text(source, registry, profile,
                             registry_path=registry_path)

    failures = []
    if report["decision"] != fixture["expected_decision"]:
        failures.append("expected decision %s, got %s"
                        % (fixture["expected_decision"], report["decision"]))

    expected_text = fixture.get("expected_text")
    if expected_text is not None and report["text"] != expected_text:
        failures.append("expected exact text, got %r"
                        % report["text"])

    count = fixture.get("expected_replacement_count")
    if count is not None and report["replacement_count"] != count:
        failures.append("expected %d replacement(s), got %d"
                        % (count, report["replacement_count"]))

    applied = [record for record in report["replacements"]
               if record["action"] != "keep"]
    for expected in fixture.get("expected_replacements", []):
        matches = [record for record in applied
                   if record["rule_id"] == expected["rule_id"]]
        if not matches:
            failures.append("no recorded %s replacement for rule '%s'"
                            % (expected.get("action", "replace"),
                               expected["rule_id"]))
            continue
        if expected.get("action") and not any(
                record["action"] == expected["action"] for record in matches):
            failures.append("rule '%s' expected action %s"
                            % (expected["rule_id"], expected["action"]))

    unresolved_ids = [record["rule_id"] for record in report["replacements"]
                      if record.get("unresolved")]
    for rule_id in fixture.get("expected_unresolved", []):
        if rule_id not in unresolved_ids:
            failures.append("rule '%s' was not left unresolved" % rule_id)

    removed = fixture.get("expected_integrity_removed")
    if removed is not None and report["integrity"]["removed_count"] != removed:
        failures.append("expected %d integrity removal(s), got %d"
                        % (removed, report["integrity"]["removed_count"]))
    kept = fixture.get("expected_integrity_kept")
    if kept is not None and report["integrity"]["kept_count"] != kept:
        failures.append("expected %d integrity keep(s), got %d"
                        % (kept, report["integrity"]["kept_count"]))

    for category in fixture.get("expected_preserved", []):
        spans = [region for region in report["protected_regions"]
                 if region["category"] == category]
        if not spans:
            failures.append("no protected %s region in the source" % category)
            continue
        for span in spans:
            cand_start = _source_to_candidate_offset(report["replacements"],
                                                     span["start"])
            cand_end = _source_to_candidate_offset(report["replacements"],
                                                   span["end"])
            if report["text"][cand_start:cand_end] != source[span["start"]:span["end"]]:
                failures.append("protected %s region changed at [%d, %d)"
                                % (category, span["start"], span["end"]))

    report["id"] = fid
    report["expected_decision"] = fixture["expected_decision"]
    report["meta"]["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
    report["failures"] = failures
    return report


def run_repair_corpus(fixtures, registry, registry_path=DEFAULT_REGISTRY):
    """Validate and evaluate the repair fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_repair_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "interface": "antislop.repair",
            "schema": "repair-report-1",
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

    reports = [run_repair_fixture(fixture, registry,
                                  registry_path=registry_path)
               for fixture in fixtures]
    failed = [report for report in reports if report["failures"]]
    return {
        "interface": "antislop.repair",
        "schema": "repair-report-1",
        "version": registry.get("version", "unknown"),
        "fixture_count": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "failures": [{
            "id": report["id"],
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


def _parse_edit(spec):
    """Parse an --edit start-end=replacement spec."""
    if "=" not in spec:
        raise ValueError("--edit must be start-end=replacement")
    span, replacement = spec.split("=", 1)
    if "-" not in span:
        raise ValueError("--edit span must be start-end")
    start_text, end_text = span.split("-", 1)
    return {"start": int(start_text), "end": int(end_text),
            "replacement": replacement}


def main():
    parser = argparse.ArgumentParser(
        description="Antislop protected repair interface")
    parser.add_argument("--file", default=None,
                        help="Path to the single named file to repair")
    parser.add_argument("--format", choices=("text", "json", "diff"),
                        default="text",
                        help="Output format (default: text)")
    parser.add_argument("--write", action="store_true",
                        help="Write the repaired file back when preservation "
                             "passes; without this flag nothing is written")
    parser.add_argument("--dry-run", action="store_true",
                        help="Never write, even with --write")
    parser.add_argument("--edit", action="append", default=[],
                        help="Proposed repair start-end=replacement "
                             "(repeatable); gated by preservation")
    parser.add_argument("--profile", default=DEFAULT_PROFILE,
                        help="Writing profile (default: general)")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY,
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--fixtures", default=None,
                        help="Run the repair fixture corpus instead of "
                             "repairing input")
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
        report = run_repair_corpus(fixtures.get("evals", fixtures), registry,
                                   args.registry)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["gate_pass"] else 1)

    source = None
    if args.file:
        if not os.path.exists(args.file):
            print(json.dumps({"error": "file not found: %s" % args.file},
                             indent=2))
            sys.exit(2)
        try:
            source = limits.read_text_file(args.file)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
    elif not sys.stdin.isatty():
        try:
            source = limits.read_text(sys.stdin)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
    else:
        print(json.dumps({"error": "No input. Use --file or pipe text."},
                         indent=2))
        sys.exit(2)
    proposed = []
    try:
        for spec in args.edit:
            proposed.append(_parse_edit(spec))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)

    if proposed:
        report = repair_proposal(source, proposed, registry, args.profile,
                                 registry_path=args.registry)
    else:
        report = repair_text(source, registry, args.profile,
                             registry_path=args.registry)

    written = False
    if (args.file and args.write and not args.dry_run
            and args.format != "diff" and report["decision"] != "reject"):
        try:
            atomic_write_text(args.file, report["text"])
        except OSError as exc:
            print(json.dumps({"error": "write failed: %s" % exc}, indent=2))
            sys.exit(2)
        written = True
    report["written"] = written
    report["dry_run"] = not written
    report["input"] = {
        "source": "file" if args.file else "stdin",
        "path": os.path.abspath(args.file) if args.file else None,
    }

    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif args.format == "diff":
        if report["text"] == source or report["decision"] == "reject":
            print("(no changes)")
        else:
            path = args.file or "<stdin>"
            print(_unified_diff(source, report["text"], path))
    else:
        if report["decision"] == "reject":
            print(source)
        else:
            print(report["text"])

    sys.exit(0 if report["decision"] in ("accept", "no-change") else 1)


if __name__ == "__main__":
    main()
