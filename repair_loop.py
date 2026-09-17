#!/usr/bin/env python3
"""Lynote-adapted bounded repair loop (issue #93).

An orchestration layer around the protected repair interface. Each attempt
runs six stages and records a trace for every one:

  1. detect   -- name the rule findings over the current text
  2. select   -- choose the smallest independent source spans to repair
  3. apply    -- apply the corrections registered for those rules
  4. verify   -- rescan the candidate and check the named findings are gone
  5. gate     -- run the fidelity and integrity gates
  6. decide   -- accept, retry within a strict bound, or roll back

The correction source is the literal replacement registered in rules.json
for each repairable rule, the same conservative authority the protected
repair interface (repair.py) uses. Retries and the cumulative
changed-character budget are strictly bounded. Any fidelity or integrity
failure rolls back immediately to the source. Advisory rhythm diagnostics
(sentence length, lexical repetition) are reported separately and never
decide whether a passage is human.

The loop never runs a detector adapter, a translation step, a model call, or
a network call. Fixture mode only supplies declared deterministic
corrections so the retry and rollback paths are exercised from fixed local
fixtures without any external model or service.

Rejected upstream mechanisms from Lynote (lynote-ai/humanize-text at
e43ca3a, MIT): multilingual translation chains, detector-score
optimization, random post-processing substitutions, broad paraphrase rounds,
and the em-dash merge behavior. The adapted goal is defect removal with
meaning preservation, never detector evasion.

Usage:
    python3 repair_loop.py --file doc.md
    cat doc.md | python3 repair_loop.py
    python3 repair_loop.py --file doc.md --max-attempts 2 --char-budget 100
    python3 repair_loop.py --fixtures skills/antislop/evals/repair-loop-fixtures.json
    python3 repair_loop.py --help

Exit codes:
    0 -- the loop ran; decision accept or no-change
    1 -- the loop rolled back, or a fixture corpus failed
    2 -- usage or input error
"""

import argparse
import json
import os
import sys

import limits

from registry import load_registry
import fidelity
import repair
import score as scoring

INTERFACE = "antislop.repair-loop"
SCHEMA = "repair-loop-report-1"
FIXTURE_SCHEMA = "repair-loop-fixtures-1"
DECISIONS = ("accept", "no-change", "rollback")
ATTEMPT_DECISIONS = ("accept", "retry", "rollback")
PROFILES = {"general", "technical"}
DEFAULT_MAX_ATTEMPTS = 2
CHURN_LIMIT = 0.5

DISCLAIMER = (
    "Repair loop results report span-bound repairs and preservation; they "
    "never prove AI authorship or detector immunity."
)
ADVISORY_DISCLAIMER = (
    "Advisory rhythm diagnostics are reported separately and never decide "
    "whether a passage is human."
)
EXECUTION_DISCLAIMER = (
    "The loop never runs a detector adapter, a translation step, a model "
    "call, or a network call; corrections come from the local registry."
)


def _overlaps_region(finding, regions):
    start = finding["position"]
    end = start + finding.get("match_length", 6)
    return any(start < region["end"] and region["start"] < end
               for region in regions)


def _detect(text, registry, profile):
    raw, _skipped, _metrics = scoring.detect_findings(text, registry, profile)
    return scoring.handle_overlaps(raw)


def _finding_record(finding):
    return {
        "rule_id": finding["rule_id"],
        "span": [finding["position"],
                 finding["position"] + finding.get("match_length", 6)],
        "signal": finding.get("signal", "advisory"),
        "primary": finding.get("primary", True),
    }


def _detect_and_select(text, registry, profile, rule_by_id, required_terms):
    """Stage 1 + 2: detect findings and select the smallest independent spans.

    Detection returns every primary finding. Selection keeps only the
    repairable findings outside protected regions, ordered by span length then
    position, greedily dropping any span that overlaps one already selected.
    """
    findings = _detect(text, registry, profile)
    regions = repair.protected_regions(text, required_terms)
    candidates = []
    for finding in findings:
        if not finding.get("primary", True):
            continue
        rule = rule_by_id.get(finding["rule_id"])
        if rule is None or not repair.repairable_rule(rule):
            continue
        if _overlaps_region(finding, regions):
            continue
        candidates.append({
            "rule_id": finding["rule_id"],
            "span": [finding["position"],
                     finding["position"] + finding.get("match_length", 6)],
            "excerpt": finding.get("excerpt", ""),
        })
    candidates.sort(key=lambda c: (c["span"][1] - c["span"][0], c["span"][0]))
    selected = []
    for candidate in candidates:
        start, end = candidate["span"]
        if any(start < existing["span"][1] and existing["span"][0] < end
               for existing in selected):
            continue
        selected.append(candidate)
    selected.sort(key=lambda c: c["span"][0])
    return findings, selected


def _plan_for(correction_plan, attempt):
    if not correction_plan:
        return None
    index = attempt - 1
    if index < len(correction_plan):
        return correction_plan[index]
    return []


def _plan_corrections(text, plan, selected):
    """Resolve a fixture-declared correction plan into concrete spans.

    An entry with explicit start and end applies at that span. A span-less
    entry applies to the first selected span of its rule. The plan is
    authoritative for fixture attempts: nothing outside the declared
    corrections is applied.
    """
    corrections = []
    skipped = []
    used = set()
    for entry in plan:
        rule_id = entry.get("rule_id", "proposed")
        if "start" in entry and "end" in entry:
            start, end = entry["start"], entry["end"]
            if start < 0 or end > len(text) or start >= end:
                skipped.append({"rule_id": rule_id, "span": [start, end],
                                "reason": "invalid span"})
                continue
        else:
            match = None
            for index, span in enumerate(selected):
                if index in used or span["rule_id"] != rule_id:
                    continue
                match = span
                used.add(index)
                break
            if match is None:
                skipped.append({"rule_id": rule_id,
                                "reason": "no matching finding span"})
                continue
            start, end = match["span"]
        corrections.append({
            "rule_id": rule_id,
            "span": [start, end],
            "correction_id": entry.get("correction_id")
                or "override:%s" % rule_id,
            "original": text[start:end],
            "replacement": entry["replacement"],
        })
    return corrections, skipped


def _registered_corrections(text, selected, rule_by_id):
    """Stage 3 default: the literal correction registered for each rule."""
    corrections = []
    skipped = []
    for span in selected:
        rule_id = span["rule_id"]
        rule = rule_by_id.get(rule_id)
        replacement = repair.literal_replacement(rule) if rule else None
        if replacement is None:
            skipped.append({"rule_id": rule_id, "span": span["span"],
                            "reason": "no registered literal correction"})
            continue
        start, end = span["span"]
        corrections.append({
            "rule_id": rule_id, "span": [start, end],
            "correction_id": "registry:%s" % rule_id,
            "original": text[start:end], "replacement": replacement,
        })
    return corrections, skipped


def _apply(text, corrections):
    """Apply non-overlapping corrections and measure changed characters."""
    kept = []
    for correction in sorted(corrections,
                             key=lambda c: (c["span"][1] - c["span"][0],
                                            c["span"][0])):
        start, end = correction["span"]
        if any(start < existing["span"][1] and existing["span"][0] < end
               for existing in kept):
            continue
        kept.append(correction)
    kept.sort(key=lambda c: c["span"][0])
    edits = [{"start": c["span"][0], "end": c["span"][1],
              "replacement": c["replacement"], "rule_id": c["rule_id"],
              "action": "replace"} for c in kept]
    candidate = repair.apply_edits(text, edits)
    changed_chars = sum(max(len(c["original"]), len(c["replacement"]))
                        for c in kept)
    return candidate, kept, changed_chars


def _remaining(output_findings, applied, rule_by_id, candidate,
               required_terms, input_findings):
    """Stage 4: which repairable findings survive in the candidate.

    A finding counts as remaining when the loop could still act on it: it is
    a targeted rule, or a repairable rule with a registered literal
    correction, and it sits outside a protected region. Findings that are
    unrepairable (protected, or a rule with no registered correction) stay
    recorded but never block acceptance.
    """
    regions = repair.protected_regions(candidate, required_terms)
    target_rule_ids = {c["rule_id"] for c in applied}
    input_rule_ids = {f["rule_id"] for f in input_findings}
    remaining = []
    for finding in output_findings:
        if not finding.get("primary", True):
            continue
        rule_id = finding["rule_id"]
        rule = rule_by_id.get(rule_id)
        fixable = (rule_id in target_rule_ids
                   or (rule is not None and repair.repairable_rule(rule)
                       and repair.literal_replacement(rule) is not None))
        if not fixable or _overlaps_region(finding, regions):
            continue
        remaining.append(finding)
    remaining_targets = [f for f in remaining
                         if f["rule_id"] in target_rule_ids]
    new_repairable = [f for f in remaining
                      if f["rule_id"] not in target_rule_ids
                      and f["rule_id"] not in input_rule_ids]
    return remaining, not remaining_targets, new_repairable


def _attempt_trace(attempt, input_findings, selected, skipped, applied,
                   changed_chars, output_findings, target_cleared,
                   new_repairable, gate):
    """Stage trace: detect, select, apply, verify, gate, decide."""
    return {
        "attempt": attempt,
        "input_findings": [_finding_record(f) for f in input_findings],
        "selected_spans": [{"rule_id": s["rule_id"], "span": s["span"]}
                           for s in selected],
        "skipped_spans": skipped,
        "corrections": [{
            "rule_id": c["rule_id"], "span": c["span"],
            "correction_id": c["correction_id"],
            "original": c["original"], "replacement": c["replacement"],
        } for c in applied],
        "changed_chars": changed_chars,
        "output_findings": [_finding_record(f) for f in output_findings],
        "target_findings_cleared": target_cleared,
        "new_repairable_findings": len(new_repairable),
        "fidelity": {"decision": gate["decision"], "reason": gate["reason"]},
        "integrity": {
            "status": gate["integrity"]["status"],
            "churn_ratio": gate["integrity"]["churn"]["ratio"],
        },
    }


def run_repair_loop(source, registry, profile="general", *,
                    required_terms=(), registry_path="rules.json",
                    max_attempts=DEFAULT_MAX_ATTEMPTS, char_budget=None,
                    correction_plan=None):
    """Run the bounded repair loop. Returns a JSON-serializable report.

    Each attempt detects findings, selects the smallest independent source
    spans, applies registered corrections, verifies the named findings are
    gone, runs the fidelity gate, and decides. A retry happens only when a
    repairable finding remains and fidelity still passes. Any fidelity or
    integrity failure, or an exhausted retry or character budget, rolls back
    to the source immediately.
    """
    limits.check_input_size(source, "source")
    max_attempts = max(1, int(max_attempts))
    if char_budget is None:
        char_budget = max(1, len(source))
    rule_by_id = {rule["id"]: rule for rule in registry.get("rules", [])}

    text = source
    attempts = []
    total_changed = 0
    retry_count = 0
    decision = "no-change"
    reason = "no repairable findings; text left unchanged"
    rollback_applied = False
    budget_exceeded = False

    for attempt in range(1, max_attempts + 1):
        plan = _plan_for(correction_plan, attempt)
        input_findings, selected = _detect_and_select(
            text, registry, profile, rule_by_id, required_terms)

        if plan is not None:
            corrections, skipped = _plan_corrections(text, plan, selected)
        else:
            corrections, skipped = _registered_corrections(
                text, selected, rule_by_id)

        if not corrections:
            if text != source:
                decision = "rollback"
                reason = ("no correction available after partial repair; "
                          "restoring the source")
                rollback_applied = True
            else:
                decision = "no-change"
                reason = "no correction available for the selected findings"
            break

        candidate, applied, changed_chars = _apply(text, corrections)
        total_changed += changed_chars
        output_findings = _detect(candidate, registry, profile)
        remaining, target_cleared, new_repairable = _remaining(
            output_findings, applied, rule_by_id, candidate, required_terms,
            input_findings)
        gate = fidelity.check_fidelity(
            text, candidate,
            required_terms=tuple(required_terms),
            hot_zones=[{"start": c["span"][0], "end": c["span"][1],
                        "label": c["rule_id"]} for c in applied],
            churn_limit=CHURN_LIMIT,
            registry_path=registry_path, profile=profile)

        trace = _attempt_trace(attempt, input_findings, selected, skipped,
                               applied, changed_chars, output_findings,
                               target_cleared, new_repairable, gate)

        if total_changed > char_budget:
            decision = "rollback"
            reason = ("changed-character budget of %d exceeded" % char_budget)
            budget_exceeded = True
            trace["decision"] = "rollback"
            trace["reason"] = reason
            attempts.append(trace)
            rollback_applied = True
            break
        if gate["decision"] in ("reject", "review"):
            decision = "rollback"
            reason = ("fidelity %s: %s" % (gate["decision"], gate["reason"]))
            trace["decision"] = "rollback"
            trace["reason"] = reason
            attempts.append(trace)
            rollback_applied = True
            break
        if remaining:
            if not target_cleared:
                retry_reason = ("target finding remains and fidelity still "
                                "passes")
            elif new_repairable:
                retry_reason = ("new repairable finding appeared and "
                                "fidelity still passes")
            else:
                retry_reason = "repairable finding remains"
            if attempt < max_attempts:
                trace["decision"] = "retry"
                trace["reason"] = retry_reason
                attempts.append(trace)
                retry_count += 1
                text = candidate
                continue
            decision = "rollback"
            reason = ("retries exhausted after %d attempt(s); findings remain"
                      % attempt)
            trace["decision"] = "rollback"
            trace["reason"] = reason
            attempts.append(trace)
            rollback_applied = True
            break

        decision = "accept"
        reason = ("all targeted findings cleared and fidelity passed on "
                  "attempt %d" % attempt)
        trace["decision"] = "accept"
        trace["reason"] = reason
        attempts.append(trace)
        text = candidate
        break

    final_text = source if rollback_applied else text
    initial_findings = [f for f in _detect(source, registry, profile)
                        if f.get("primary", True)]
    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "mode": "repair-loop",
        "profile": profile,
        "source_chars": len(source),
        "input_findings": [_finding_record(f) for f in initial_findings],
        "decision": decision,
        "reason": reason,
        "edited": final_text != source,
        "attempt_count": len(attempts),
        "retry_count": retry_count,
        "total_changed_chars": total_changed,
        "char_budget": char_budget,
        "budget_exceeded": budget_exceeded,
        "attempts": attempts,
        "rollback": {
            "applied": rollback_applied,
            "reason": reason if rollback_applied else None,
        },
        "advisory": {
            "rhythm": {
                "source": fidelity.stylometrics(source),
                "candidate": fidelity.stylometrics(final_text),
            },
            "advisory_only": True,
            "authorship_evidence": False,
            "never_decides_humanity": True,
            "disclaimer": ADVISORY_DISCLAIMER,
        },
        "execution": {
            "detector_adapter": False,
            "translation_step": False,
            "network_call": False,
            "model_call": False,
            "source": "local deterministic registry corrections",
            "disclaimer": EXECUTION_DISCLAIMER,
        },
        "text": final_text,
        "meta": {
            "disclaimer": DISCLAIMER,
            "required_terms": list(required_terms),
        },
    }


def validate_repair_loop_fixture(fixture, seen_ids):
    """Schema-validate one repair-loop fixture. Returns error strings."""
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

    for field in ("expected_attempt_count", "expected_retry_count"):
        value = fixture.get(field)
        if value is not None and (not isinstance(value, int)
                                  or isinstance(value, bool) or value < 0):
            errors.append("%s: %s must be a non-negative integer"
                          % (where, field))

    for field in ("max_attempts", "char_budget"):
        value = fixture.get(field)
        if value is not None and (not isinstance(value, int)
                                  or isinstance(value, bool) or value < 1):
            errors.append("%s: %s must be a positive integer"
                          % (where, field))

    replaced = fixture.get("expected_replaced_rule_ids", [])
    if not isinstance(replaced, list):
        errors.append("%s: expected_replaced_rule_ids must be a list" % where)
    else:
        for index, item in enumerate(replaced):
            if not (isinstance(item, str) and item.strip()):
                errors.append("%s: expected_replaced_rule_ids[%d] must be a "
                              "non-empty string" % (where, index))

    unchanged = fixture.get("expected_unchanged_text")
    if unchanged is not None and (not isinstance(unchanged, str)
                                  or not unchanged.strip()):
        errors.append("%s: expected_unchanged_text must be a non-empty "
                      "string" % where)

    required_terms = fixture.get("required_terms", [])
    if not isinstance(required_terms, list):
        errors.append("%s: required_terms must be a list" % where)
    else:
        for index, item in enumerate(required_terms):
            if not (isinstance(item, str) and item.strip()):
                errors.append("%s: required_terms[%d] must be a non-empty "
                              "string" % (where, index))

    for field in ("expected_budget_exceeded", "expected_rollback"):
        value = fixture.get(field)
        if value is not None and not isinstance(value, bool):
            errors.append("%s: %s must be a boolean" % (where, field))

    expected_execution = fixture.get("expected_execution")
    if expected_execution is not None and not isinstance(
            expected_execution, dict):
        errors.append("%s: expected_execution must be an object" % where)

    attempts = fixture.get("attempt_corrections")
    if attempts is not None:
        if not isinstance(attempts, list):
            errors.append("%s: attempt_corrections must be a list of "
                          "attempt plans" % where)
        else:
            for index, plan in enumerate(attempts):
                if not isinstance(plan, list):
                    errors.append("%s: attempt_corrections[%d] must be a "
                                  "list" % (where, index))
                    continue
                for entry_index, entry in enumerate(plan):
                    if not isinstance(entry, dict):
                        errors.append("%s: attempt_corrections[%d][%d] must "
                                      "be an object"
                                      % (where, index, entry_index))
                        continue
                    if not (isinstance(entry.get("rule_id"), str)
                            and entry["rule_id"].strip()):
                        errors.append("%s: attempt_corrections[%d][%d] "
                                      "missing non-empty 'rule_id'"
                                      % (where, index, entry_index))
                    if not isinstance(entry.get("replacement"), str):
                        errors.append("%s: attempt_corrections[%d][%d] "
                                      "replacement must be a string"
                                      % (where, index, entry_index))
                    for field in ("start", "end"):
                        if field in entry and not isinstance(entry[field],
                                                             int):
                            errors.append("%s: attempt_corrections[%d][%d].%s "
                                          "must be an integer"
                                          % (where, index, entry_index,
                                             field))

    rationale = fixture.get("false_positive_rationale")
    if rationale is not None and (not isinstance(rationale, str)
                                  or not rationale.strip()):
        errors.append("%s: false_positive_rationale must be a non-empty "
                      "string" % where)

    notes = fixture.get("reviewer_notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append("%s: reviewer_notes must be a non-empty string" % where)
    return errors


def run_repair_loop_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one repair-loop fixture against its expectations."""
    fid = fixture["id"]
    profile = fixture.get("profile", "general")
    report = run_repair_loop(
        fixture["source"], registry, profile,
        required_terms=tuple(fixture.get("required_terms", [])),
        registry_path=registry_path,
        max_attempts=fixture.get("max_attempts", DEFAULT_MAX_ATTEMPTS),
        char_budget=fixture.get("char_budget"),
        correction_plan=fixture.get("attempt_corrections"),
    )

    failures = []
    if report["decision"] != fixture["expected_decision"]:
        failures.append("expected decision %s, got %s"
                        % (fixture["expected_decision"], report["decision"]))

    expected_text = fixture.get("expected_text")
    if expected_text is not None and report["text"] != expected_text:
        failures.append("expected exact text, got %r" % report["text"])

    if fixture["expected_decision"] == "no-change" and report["attempts"]:
        failures.append("no-change decision must carry a no-op trace")

    count = fixture.get("expected_attempt_count")
    if count is not None and report["attempt_count"] != count:
        failures.append("expected %d attempt(s), got %d"
                        % (count, report["attempt_count"]))
    retries = fixture.get("expected_retry_count")
    if retries is not None and report["retry_count"] != retries:
        failures.append("expected %d retry(ies), got %d"
                        % (retries, report["retry_count"]))

    applied_ids = []
    for trace in report["attempts"]:
        applied_ids.extend(c["rule_id"] for c in trace["corrections"])
    for rule_id in fixture.get("expected_replaced_rule_ids", []):
        if rule_id not in applied_ids:
            failures.append("rule '%s' was not corrected" % rule_id)

    unchanged = fixture.get("expected_unchanged_text")
    if unchanged is not None:
        if unchanged not in fixture["source"]:
            failures.append("expected_unchanged_text is not in the source")
        elif unchanged not in report["text"]:
            failures.append("unaffected text '%s' was rewritten" % unchanged)

    expected_rollback = fixture.get("expected_rollback")
    if expected_rollback is not None and report["rollback"]["applied"] != (
            expected_rollback):
        failures.append("expected rollback %s, got %s"
                        % (expected_rollback,
                           report["rollback"]["applied"]))
    expected_budget = fixture.get("expected_budget_exceeded")
    if expected_budget is not None and report["budget_exceeded"] != (
            expected_budget):
        failures.append("expected budget_exceeded %s, got %s"
                        % (expected_budget, report["budget_exceeded"]))

    for key, value in (fixture.get("expected_execution") or {}).items():
        if report["execution"].get(key) != value:
            failures.append("execution.%s expected %s, got %s"
                            % (key, value, report["execution"].get(key)))

    report["id"] = fid
    report["expected_decision"] = fixture["expected_decision"]
    report["meta"]["false_positive_rationale"] = fixture.get(
        "false_positive_rationale")
    report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
    report["failures"] = failures
    return report


def run_repair_loop_corpus(fixtures, registry,
                           registry_path="rules.json"):
    """Validate and evaluate the repair-loop fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_repair_loop_fixture(fixture, seen_ids))

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

    reports = [run_repair_loop_fixture(fixture, registry,
                                       registry_path=registry_path)
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


def main():
    parser = argparse.ArgumentParser(
        description="Antislop bounded repair loop")
    parser.add_argument("--file", default=None,
                        help="Path to the single named file to repair")
    parser.add_argument("--profile", default="general",
                        help="Writing profile (default: general)")
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS,
                        help="Maximum repair attempts (default: 2)")
    parser.add_argument("--char-budget", type=int, default=None,
                        help="Changed-character budget (default: source "
                             "length)")
    parser.add_argument("--fixtures", default=None,
                        help="Run the repair-loop fixture corpus instead of "
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
        report = run_repair_loop_corpus(fixtures.get("evals", fixtures),
                                        registry, args.registry)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["gate_pass"] else 1)

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

    report = run_repair_loop(
        source, registry, args.profile,
        registry_path=args.registry,
        max_attempts=args.max_attempts,
        char_budget=args.char_budget,
    )
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["decision"] in ("accept", "no-change") else 1)


if __name__ == "__main__":
    main()
