#!/usr/bin/env python3
"""Edit integrity and provenance contract (issue #87).

An Anbeeld-style operation contract. Four operations carry different
authority over an artifact:

  draft     -- create prose only from supplied facts and allowed research
  revise    -- make the least invasive change that satisfies the request
  audit     -- report findings without changing the artifact
  transform -- may change shape but must preserve the source inventory

Before revise or transform, inventory the source: claims, facts, quantities,
dates, modality, causality, negation, conditions, attribution, quotes,
citations, links, placeholders, markup, accessibility structure, required
terminology, and author-owned statements. A voice sample supplies style
traits only and cannot donate claims, memories, preferences, or experiences.

The inventory reuses fidelity.py's protected spans and semantic anchors and
drift.py's fact matching and semantic dimensions. Output-integrity checks
catch unresolved placeholders, malformed markup, leaked prompt tokens, and
changed link targets. Long-form information gain stays a human-review prompt,
never a universal score deduction.

Revise runs the strict fidelity gate. Transform may reorder the artifact, so
its preservation is checked as a multiset of inventory values rather than a
sequence: a pure reorder stays preserved and is disclosed as a shape change,
while any dropped or changed inventory item fails. The report keeps a
fidelity section that names the preservation status either way.

Usage:
    python3 tools/edit.py --fixtures skills/antislop/evals/edit-integrity-fixtures.json
    python3 tools/edit.py --help

Exit codes:
    0 -- every fixture decision matches its expected decision
    1 -- a fixture decision failed
    2 -- usage or input error
"""

import argparse
import collections
import json
import os
import re
import sys

import limits

from registry import load_registry
import drift
import fidelity
import score as scoring

OPERATION_ORDER = ("draft", "revise", "audit", "transform")
OPERATIONS = {
    "draft": {
        "authority": "Create prose only from supplied facts and allowed research.",
        "boundary": ("A voice sample contributes style traits only: vocabulary, "
                     "rhythm, punctuation, paragraph shape, and formality. It "
                     "cannot donate claims, memories, preferences, or "
                     "experiences to the target."),
    },
    "revise": {
        "authority": "Make the least invasive change that satisfies the request.",
        "boundary": ("Preserve every inventory item or report an authorized "
                     "change. Never strengthen causality or certainty beyond "
                     "the source."),
    },
    "audit": {
        "authority": "Report findings without changing the artifact.",
        "boundary": ("Produce no rewritten passage or file change unless the "
                     "user separately requests it."),
    },
    "transform": {
        "authority": "May change shape while preserving the source inventory.",
        "boundary": "Disclose structural changes and still pass the fidelity gate.",
    },
}

INVENTORY_ORDER = (
    "claims", "facts", "quantities", "dates", "modality", "causality",
    "negation", "conditions", "attribution", "quotes", "citations", "links",
    "placeholders", "markup", "accessibility structure", "required terminology",
    "author-owned statements",
)

DECISIONS = {"accept", "review", "reject"}
PROFILES = {"general", "technical"}


def resolve_edit_contract(registry):
    # The registry is authoritative for precedence and preservation policy.
    contract = registry.get("edit_contract")
    if not isinstance(contract, dict):
        raise ValueError("registry is missing edit_contract")
    precedence = contract.get("precedence")
    preservation = contract.get("preservation")
    if not isinstance(precedence, list) or not precedence:
        raise ValueError("edit_contract.precedence must be a non-empty list")
    if not isinstance(preservation, dict):
        raise ValueError("edit_contract.preservation must be an object")
    return contract


DISCLAIMER = (
    "Edit-integrity results report operation authority and preservation; "
    "they never prove AI authorship or detector immunity."
)
OBSERVATION_DISCLAIMER = drift.OBSERVATION_DISCLAIMER

PLACEHOLDER_RE = re.compile(
    r"\[(?:INSERT|TODO|YOUR TEXT HERE|add|placeholder|TK)[^\]]*\]"
    r"|Lorem ipsum",
    re.IGNORECASE,
)

PROMPT_TOKEN_RE = re.compile(
    r"<\|im_start\|>|<\|im_end\|>|<\|im_sep\|>|<\|system\|>|<\|user\|>"
    r"|<\|assistant\|>|<\|model\|>"
    r"|\[INST\]|\[/INST\]"
    r"|<system>|</system>|<user>|</user>|<assistant>|</assistant>"
    r"|<\?xml"
    r"|ignore all previous instructions|ignore previous instructions",
    re.IGNORECASE,
)

LEAKED_MARKUP_RE = re.compile(
    r"</?[a-z][a-z0-9]*(\s+[a-z][a-z0-9\-]*\s*=\s*\"[^\"]*\")*\s*/?>"
    r"|\*\*|__|~~",
    re.IGNORECASE,
)

HIDDEN_UNICODE_RE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]"
)

INTEGRITY_KINDS = ("leaked_markup", "leaked_prompt_token", "hidden_unicode")


def integrity_defects(text):
    """Scan text for output defects: placeholders, leaked markup, leaked
    prompt tokens, and hidden Unicode. Returns a list of defect records."""
    defects = []
    prompt_spans = []
    for match in PROMPT_TOKEN_RE.finditer(text):
        defects.append({
            "kind": "leaked_prompt_token",
            "value": match.group(0),
            "start": match.start(),
            "end": match.end(),
        })
        prompt_spans.append((match.start(), match.end()))
    for match in PLACEHOLDER_RE.finditer(text):
        defects.append({
            "kind": "placeholder",
            "value": match.group(0),
            "start": match.start(),
            "end": match.end(),
        })
    for match in LEAKED_MARKUP_RE.finditer(text):
        if any(match.start() < end and start < match.end()
               for start, end in prompt_spans):
            continue
        defects.append({
            "kind": "leaked_markup",
            "value": match.group(0),
            "start": match.start(),
            "end": match.end(),
        })
    for match in HIDDEN_UNICODE_RE.finditer(text):
        defects.append({
            "kind": "hidden_unicode",
            "value": match.group(0),
            "start": match.start(),
            "end": match.end(),
        })
    defects.sort(key=lambda defect: (defect["start"], defect["end"]))
    return defects


def inventory(text, required_terms=(), declared_facts=()):
    """Compose the edit-integrity inventory for a text.

    Reuses fidelity.py's protected spans and semantic anchors, drift.py's
    fact matching, and the output-integrity defect scan.
    """
    anchors = fidelity.extract_anchors(text, required_terms)
    return {
        "protected_spans": anchors["protected_spans"],
        "semantic_anchors": anchors["semantic_anchors"],
        "facts": [fact for fact in declared_facts
                  if drift.contains_fact(text, fact)],
        "integrity_defects": integrity_defects(text),
    }


def _value_counts(items, key):
    return collections.Counter(key(item) for item in items)


def _multiset_diff(source_items, candidate_items, key):
    source_counts = _value_counts(source_items, key)
    candidate_counts = _value_counts(candidate_items, key)
    removed = sorted((source_counts - candidate_counts).elements())
    added = sorted((candidate_counts - source_counts).elements())
    return removed, added


def _span_key(span):
    return span["canonical"]


def shape_change(source, candidate):
    """Block-level ordering disclosure used by transform.

    Blocks are newline-separated runs with internal whitespace collapsed. A
    reorder is the same multiset of blocks in a different order; it is
    disclosed, never a failure. Dropped or added blocks are reported.
    """
    def blocks(text):
        return [re.sub(r"\s+", " ", block).strip()
                for block in re.split(r"\n+", text) if block.strip()]

    source_blocks = blocks(source)
    candidate_blocks = blocks(candidate)
    removed, added = _multiset_diff(source_blocks, candidate_blocks, lambda b: b)
    reordered = not removed and not added and source_blocks != candidate_blocks
    return {
        "source_blocks": len(source_blocks),
        "candidate_blocks": len(candidate_blocks),
        "reordered": reordered,
        "removed": removed,
        "added": added,
        "unchanged": not removed and not added and not reordered,
    }


def _score_risk(text, registry, profile):
    try:
        result = scoring.score_text(text, registry, profile)
        return {
            "score": result["score"],
            "band": result["band"],
            "findings": [
                {"rule_id": f["rule_id"], "span": f["span"],
                 "signal": f["signal"], "primary": f.get("primary", True)}
                for f in result["findings"]
            ],
        }
    except Exception:  # noqa: BLE001 -- risk is advisory, never a gate
        return {"score": None, "band": None, "findings": []}


def check_operation(source, candidate, operation, *, required_terms=(),
                     required_facts=(), forbidden_additions=(),
                     semantic_dimensions=None, authorized_changes=(),
                     review_prompts=None, expected_findings=(),
                     absent_findings=(), registry_path="rules.json",
                     profile="general"):
    """Evaluate source and candidate under one operation's authority.

    Returns a JSON-serializable report with a decision of accept, review, or
    reject. Audit must leave the artifact byte-identical. Revise runs the
    strict fidelity gate and the declared semantic dimensions. Transform
    checks the inventory as a multiset so a pure reorder stays preserved, and
    discloses shape changes. Draft checks supplied facts, forbidden additions,
    and output integrity only.
    """
    if operation not in OPERATION_ORDER:
        raise ValueError("unknown operation %r" % operation)
    registry = load_registry(registry_path)
    contract = resolve_edit_contract(registry)

    items = {"missing": [], "added": [], "changed": [], "unresolved": []}
    reasons = []
    integrity_failures = []
    authority = []
    shape = None
    fidelity_report = None
    dimensions = None

    source_defects = integrity_defects(source)
    candidate_defects = integrity_defects(candidate)

    source_placeholders = {defect["value"] for defect in source_defects
                           if defect["kind"] == "placeholder"}
    candidate_placeholders = {defect["value"] for defect in candidate_defects
                              if defect["kind"] == "placeholder"}
    for value in sorted(candidate_placeholders - source_placeholders):
        items["added"].append({"kind": "placeholder_added", "value": value})
        reasons.append("placeholder '%s' was added and left unresolved" % value)
        integrity_failures.append("placeholder_added")
    for value in sorted(source_placeholders & candidate_placeholders):
        items["unresolved"].append({
            "kind": "placeholder_kept_unresolved", "value": value,
        })
    for value in sorted(source_placeholders - candidate_placeholders):
        items["changed"].append({"kind": "placeholder_resolved", "value": value})

    source_by_kind = {kind: {defect["value"] for defect in source_defects
                             if defect["kind"] == kind}
                      for kind in INTEGRITY_KINDS}
    candidate_by_kind = {kind: {defect["value"] for defect in candidate_defects
                                if defect["kind"] == kind}
                         for kind in INTEGRITY_KINDS}
    for kind in INTEGRITY_KINDS:
        for value in sorted(candidate_by_kind[kind] - source_by_kind[kind]):
            items["added"].append({
                "kind": "integrity_%s" % kind, "value": value,
            })
            reasons.append("%s '%s' was introduced in the output"
                           % (kind, value))
            integrity_failures.append(kind)
        for value in sorted(candidate_by_kind[kind] & source_by_kind[kind]):
            items["unresolved"].append({
                "kind": "defect_kept_%s" % kind, "value": value,
            })

    for fact in required_facts:
        if not drift.contains_fact(candidate, fact):
            items["missing"].append({"kind": "required_fact", "value": fact})
            reasons.append("required fact '%s' is missing" % fact)

    for term in forbidden_additions:
        if drift.contains_fact(candidate, term):
            items["added"].append({
                "kind": "forbidden_addition", "value": term,
            })
            reasons.append("forbidden addition '%s' is present" % term)

    source_terms = {span["value"].lower()
                    for span in fidelity.extract_anchors(
                        source, required_terms)["protected_spans"]
                    if span["category"] == "required_term"}
    candidate_terms = {span["value"].lower()
                       for span in fidelity.extract_anchors(
                           candidate, required_terms)["protected_spans"]
                       if span["category"] == "required_term"}
    for term in sorted(source_terms - candidate_terms):
        items["missing"].append({"kind": "required_term", "value": term})
        reasons.append("required term '%s' is missing" % term)
    for term in sorted(candidate_terms - source_terms):
        items["added"].append({"kind": "required_term_added", "value": term})

    if operation == "audit":
        if candidate != source:
            authority.append({"kind": "audit_rewrote_text"})
            reasons.append("audit produced a rewritten passage; the artifact "
                           "must stay unchanged")
    elif operation == "draft":
        if not required_facts:
            authority.append({"kind": "draft_missing_facts"})
            reasons.append("draft requires supplied facts")
    elif operation == "revise":
        fidelity_report = fidelity.check_fidelity(
            source, candidate,
            required_terms=tuple(required_terms),
            authorized_changes=tuple(authorized_changes),
            hot_zones=[], churn_limit=None,
            registry_path=registry_path, profile=profile,
        )
        for failure in fidelity_report["preservation"]["hard_failures"]:
            kind = failure["kind"]
            category = failure.get("category", "anchor")
            source_value = failure.get("source")
            candidate_value = failure.get("candidate")
            if kind == "protected_span_changed":
                items["changed"].append({
                    "kind": "protected_span_changed", "category": category,
                    "source": source_value, "candidate": candidate_value,
                })
                reasons.append("protected %s changed from '%s' to '%s'"
                               % (category, source_value, candidate_value))
            elif kind == "protected_span_removed":
                items["missing"].append({
                    "kind": "protected_span_removed", "category": category,
                    "source": source_value,
                })
                reasons.append("protected %s '%s' is missing"
                               % (category, source_value))
            else:
                items["changed"].append({
                    "kind": kind, "category": category,
                    "source": source_value, "candidate": candidate_value,
                })
                reasons.append("%s in %s" % (kind, category))
        if semantic_dimensions:
            dimensions = drift.check_semantic_dimensions(
                {"semantic_dimensions": semantic_dimensions},
                source, candidate)
            for violation in dimensions["violations"]:
                reasons.append(violation)
    elif operation == "transform":
        source_anchors = fidelity.extract_anchors(source, required_terms)
        candidate_anchors = fidelity.extract_anchors(candidate, required_terms)

        source_by_category = {
            category: [span for span in source_anchors["protected_spans"]
                       if span["category"] == category]
            for category in fidelity.PROTECTED_ORDER
        }
        candidate_by_category = {
            category: [span for span in candidate_anchors["protected_spans"]
                       if span["category"] == category]
            for category in fidelity.PROTECTED_ORDER
        }
        for category in fidelity.PROTECTED_ORDER:
            removed, added = _multiset_diff(
                source_by_category[category],
                candidate_by_category[category], _span_key)
            for value in removed:
                items["missing"].append({
                    "kind": "protected_span_removed", "category": category,
                    "source": value,
                })
                reasons.append("protected %s '%s' is missing"
                               % (category, value))
                if category == "url":
                    items["changed"].append({
                        "kind": "changed_link_target", "category": "url",
                        "source": value, "candidate": None,
                    })
                    reasons.append("link target '%s' changed" % value)
            for value in added:
                items["changed"].append({
                    "kind": "protected_span_changed", "category": category,
                    "source": None, "candidate": value,
                })
                reasons.append("protected %s '%s' was added"
                               % (category, value))

        source_by_category = {
            category: [anchor for anchor in source_anchors["semantic_anchors"]
                       if anchor["category"] == category]
            for category in fidelity.ANCHOR_ORDER
        }
        candidate_by_category = {
            category: [anchor for anchor in candidate_anchors["semantic_anchors"]
                       if anchor["category"] == category]
            for category in fidelity.ANCHOR_ORDER
        }
        for category in fidelity.ANCHOR_ORDER:
            removed, added = _multiset_diff(
                source_by_category[category],
                candidate_by_category[category], _span_key)
            for value in removed:
                items["missing"].append({
                    "kind": "semantic_anchor_removed", "category": category,
                    "source": value,
                })
                reasons.append("%s anchor '%s' is missing"
                               % (category, value))
            for value in added:
                items["changed"].append({
                    "kind": "semantic_anchor_added", "category": category,
                    "source": None, "candidate": value,
                })
                reasons.append("%s anchor '%s' was added"
                               % (category, value))
        if semantic_dimensions:
            dimensions = drift.check_semantic_dimensions(
                {"semantic_dimensions": semantic_dimensions},
                source, candidate)
            for violation in dimensions["violations"]:
                reasons.append(violation)
        shape = shape_change(source, candidate)
        if shape["removed"]:
            for block in shape["removed"]:
                items["missing"].append({
                    "kind": "shape_block_removed", "value": block,
                })
                reasons.append("transform dropped a block: '%s'" % block)
        if shape["added"]:
            for block in shape["added"]:
                items["added"].append({
                    "kind": "shape_block_added", "value": block,
                })
                reasons.append("transform added a block: '%s'" % block)

    findings = drift.check_findings(
        {"expected_findings": list(expected_findings),
         "absent_findings": list(absent_findings)},
        registry, source, candidate, profile)
    for mismatch in findings["mismatches"]:
        if mismatch["kind"] == "absent_finding_present":
            items["added"].append(mismatch)
            reasons.append("rule '%s' unexpectedly fires in %s"
                           % (mismatch["rule_id"], mismatch["target"]))
        else:
            items["changed"].append(mismatch)
            if mismatch["kind"] == "expected_finding_missing":
                reasons.append("expected finding %s at %s does not fire"
                               % (mismatch["rule_id"], mismatch["span"]))
            else:
                reasons.append("expected finding %s has the wrong risk class"
                               % mismatch["rule_id"])

    review_items = [{"kind": key, "prompt": value}
                    for key, value in sorted((review_prompts or {}).items())]
    if (fidelity_report is not None
            and fidelity_report["decision"] == "review"):
        review_items.extend(
            {"kind": "fidelity_%s" % item["category"],
             "prompt": "Review the changed %s: %s" % (
                 item["category"], item.get("source") or item.get("candidate"))}
            for item in fidelity_report["review"]["items"]
        )

    if reasons:
        decision = "reject"
    elif review_items:
        decision = "review"
    else:
        decision = "accept"

    source_risk = _score_risk(source, registry, profile)
    candidate_risk = _score_risk(candidate, registry, profile)
    delta = None
    improved = False
    if (source_risk["score"] is not None
            and candidate_risk["score"] is not None):
        delta = candidate_risk["score"] - source_risk["score"]
        improved = delta > 0

    report = {
        "interface": "antislop.edit",
        "schema": "edit-integrity-report-1",
        "version": registry.get("version", "unknown"),
        "operation": operation,
        "profile": profile,
        "contract": contract,
        "precedence": list(contract["precedence"]),
        "preservation_contract": contract["preservation"],
        "authorized_changes": list(authorized_changes),
        "decision": decision,
        "reasons": reasons,
        "authority": authority,
        "items": items,
        "facts": {
            "required": list(required_facts),
            "missing": [item["value"] for item in items["missing"]
                        if item["kind"] == "required_fact"],
        },
        "forbidden_additions": [
            item["value"] for item in items["added"]
            if item["kind"] == "forbidden_addition"
        ],
        "integrity": {
            "status": "failed" if integrity_failures else "passed",
            "failures": sorted(set(integrity_failures)),
            "source_defects": source_defects,
            "candidate_defects": candidate_defects,
            "unresolved": [
                item for item in items["unresolved"]
                if item["kind"].startswith(("placeholder", "defect"))
            ],
        },
        "findings": findings,
        "review": {
            "status": "unresolved" if review_items else "none",
            "items": review_items,
        },
        "risk": {
            "source_score": source_risk["score"],
            "candidate_score": candidate_risk["score"],
            "delta": delta,
            "improved": improved,
            "advisory": True,
            "authorship_evidence": False,
            "disclaimer": OBSERVATION_DISCLAIMER,
        },
        "meta": {
            "disclaimer": DISCLAIMER,
        },
    }
    if dimensions is not None:
        report["semantic_dimensions"] = dimensions
    if shape is not None:
        report["shape"] = shape
    if fidelity_report is not None:
        report["fidelity"] = {
            "status": fidelity_report["preservation"]["status"],
            "decision": fidelity_report["decision"],
            "reason": fidelity_report["reason"],
        }
    return report


def validate_edit_fixture(fixture, seen_ids):
    """Schema-validate one edit-integrity fixture. Returns error strings.

    Reuses drift's fixture validator for the shared preservation-contract
    fields and adds the operation selection on top.
    """
    errors = drift.validate_drift_fixture(fixture, seen_ids)
    operation = fixture.get("operation")
    if operation not in OPERATION_ORDER:
        where = "fixture '%s'" % (fixture.get("id", "?"))
        errors.append("%s: operation must be one of %s"
                      % (where, ", ".join(OPERATION_ORDER)))
    return errors


def run_edit_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one edit-integrity fixture against its operation contract."""
    fid = fixture["id"]
    operation = fixture["operation"]
    profile = fixture.get("profile", "general")
    report = check_operation(
        fixture["source"], fixture["candidate"], operation,
        required_terms=tuple(fixture.get("required_terms", [])),
        required_facts=fixture.get("required_facts", []),
        forbidden_additions=fixture.get("forbidden_additions", []),
        semantic_dimensions=fixture.get("semantic_dimensions"),
        authorized_changes=tuple(fixture.get("authorized_changes", [])),
        review_prompts=fixture.get("review_prompts"),
        expected_findings=fixture.get("expected_findings", []),
        absent_findings=fixture.get("absent_findings", []),
        registry_path=registry_path,
        profile=profile,
    )
    report["id"] = fid
    report["expected_decision"] = fixture["expected_decision"]
    report["meta"]["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
    return report


def run_edit_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate an edit-integrity fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_edit_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "interface": "antislop.edit",
            "schema": "edit-integrity-report-1",
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

    reports = [run_edit_fixture(fixture, registry,
                                registry_path=registry_path)
               for fixture in fixtures]
    failed = [report for report in reports
              if report["decision"] != report["expected_decision"]]
    return {
        "interface": "antislop.edit",
        "schema": "edit-integrity-report-1",
        "version": registry.get("version", "unknown"),
        "fixture_count": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "failures": [{
            "id": report["id"],
            "operation": report["operation"],
            "expected": report["expected_decision"],
            "got": report["decision"],
            "reasons": report["reasons"],
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
        default="skills/antislop/evals/edit-integrity-fixtures.json",
        help="Path to the edit-integrity fixture corpus (default: repo path)",
    )
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Print a compact JSON report")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    if args.expect_version and registry.get("version") != args.expect_version:
        print(json.dumps({
            "error": "registry version %s does not match --expect-version %s"
                     % (registry.get("version"), args.expect_version),
        }, indent=2))
        sys.exit(2)

    if not os.path.exists(args.fixtures):
        print(json.dumps({"error": "fixture corpus not found: %s"
                          % args.fixtures}, indent=2))
        sys.exit(2)

    fixtures = load_json(args.fixtures)
    report = run_edit_corpus(fixtures.get("evals", fixtures), registry,
                             args.registry)
    print(json.dumps(report, indent=2 if not args.as_json else None,
                     sort_keys=args.as_json))
    sys.exit(0 if report["gate_pass"] else 1)


if __name__ == "__main__":
    main()
