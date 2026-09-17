#!/usr/bin/env python3
"""Antislop rule provenance and decay review (issue #101).

Reviewed ama-zingco/anti-ai-writing-skill at a0571d7 (MIT). The reviewed
project records its rules with an expiry-aware mindset but has no structured
per-rule evidence metadata, no stale-rule review queue, and no way to keep a
stable house policy distinct from a dated external observation. This module
adds all three to the rule registry and pins the review queue with an
evaluation fixture corpus.

  evidence_classes   the eight provenance classes a rule's evidence_meta can
                     carry, from stable project policy to secondary claim
  decay_states       current, review, and stale, where listing a rule never
                     disables it automatically
  review_queue       stale lexical rules (still active) plus fixture-backed
                     candidate metrics, each with matched-length and
                     matched-profile clean cases

Boundaries: source metadata never proves a rule is correct, decay never
disables a rule on its own, and no unreproduced study number or fake
imperfection is added. Candidate metrics are advisory by design; none carries
an external numeric threshold as a strict finding.

Usage:
    python3 provenance.py --fixtures skills/antislop/evals/provenance-fixtures.json
    python3 provenance.py
    python3 provenance.py --help

Exit codes:
    0 -- the review ran, or every fixture matched its expectation
    1 -- a fixture or schema check failed
    2 -- usage or input error
"""

import argparse
import json
import os
import re
import sys

import limits
from registry import load_registry

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(MODULE_DIR, "rules.json")
FIXTURES_PATH = os.path.join(MODULE_DIR, "skills", "antislop", "evals",
                             "provenance-fixtures.json")

INTERFACE = "antislop.rule_provenance"
SCHEMA = "provenance-report-1"
PROFILES = ("general", "technical")

EVIDENCE_CLASSES = (
    "project-policy", "project-fixture", "upstream-evidence",
    "tested-adaptation", "primary-research", "secondary-claim",
    "maintainer-judgment", "unknown",
)
DECAY_STATES = ("current", "review", "stale")
IDENTIFIED_SOURCE_CLASSES = ("upstream-evidence", "tested-adaptation")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
URL_RE = re.compile(r"^https?://")
NUMERIC_RE = re.compile(r"\d+(?:[.,]\d+)?\s*%|\b\d+(?:[.,]\d+)?\b")
SOURCE_REVIEW_DECISIONS = ("adopt", "adapt", "reject")
HUMANIZER_SOURCE_REVIEW = "humanizer-3.0.0"

# A matched-length clean fixture's source must be within this ratio of the
# positive fixture's source length, so a candidate cannot be accused of
# firing only on text length.
LENGTH_MATCH_RATIO = 0.30

DISCLAIMER = (
    "Rule provenance records where a rule came from and when it was reviewed; "
    "it never proves the rule is correct, and a decayed or queued rule stays "
    "active until a human changes it."
)


def validate_source_reviews(registry):
    """Validate source-level review records and their decision matrix.

    Per-rule evidence metadata answers where a rule came from. A source
    review record answers what changed in a reviewed revision and whether
    Antislop adopted, adapted, or rejected it. Keeping both layers prevents a
    generic source credit from being mistaken for a decision to import its
    whole taxonomy.
    """
    errors = []
    reviews = registry.get("source_reviews")
    if reviews is None:
        return errors
    if not isinstance(reviews, dict) or not reviews:
        return ["rules.json: source_reviews must be a non-empty object"]

    rules = registry.get("rules", [])
    rule_by_id = {rule.get("id"): rule for rule in rules}
    for review_id, review in reviews.items():
        where = "rules.json: source_reviews.%s" % review_id
        if not isinstance(review, dict):
            errors.append("%s must be an object" % where)
            continue
        for field in ("name", "repository", "reviewed_revision",
                      "source_file", "license", "source_date",
                      "reviewed_date", "decay"):
            if not (isinstance(review.get(field), str)
                    and review[field].strip()):
                errors.append("%s missing non-empty '%s'" % (where, field))
        revision = review.get("reviewed_revision")
        if revision and not COMMIT_RE.match(revision):
            errors.append("%s reviewed_revision must be a 7-40 hex commit" % where)
        source_file = review.get("source_file")
        if source_file and (not URL_RE.match(source_file)
                            or "/blob/%s/" % revision not in source_file):
            errors.append("%s source_file must pin reviewed_revision" % where)
        for field in ("source_date", "reviewed_date"):
            value = review.get(field)
            if value and not DATE_RE.match(value):
                errors.append("%s %s must be an ISO date" % (where, field))
        if review.get("decay") not in DECAY_STATES:
            errors.append("%s decay must be current, review, or stale" % where)
        if review.get("license") != review.get("licence"):
            errors.append("%s license and licence must agree" % where)

        decisions = review.get("decisions")
        if not isinstance(decisions, list) or not decisions:
            errors.append("%s decisions must be a non-empty list" % where)
            continue
        seen_changes = set()
        for index, decision in enumerate(decisions):
            dwhere = "%s decisions[%d]" % (where, index)
            if not isinstance(decision, dict):
                errors.append("%s must be an object" % dwhere)
                continue
            change = decision.get("change")
            if not (isinstance(change, str) and change.strip()):
                errors.append("%s missing non-empty 'change'" % dwhere)
            elif change in seen_changes:
                errors.append("%s repeats change" % dwhere)
            seen_changes.add(change)
            if decision.get("decision") not in SOURCE_REVIEW_DECISIONS:
                errors.append("%s decision must be adopt, adapt, or reject" % dwhere)
            if not (isinstance(decision.get("rationale"), str)
                    and decision["rationale"].strip()):
                errors.append("%s missing non-empty 'rationale'" % dwhere)
            rule_ids = decision.get("rule_ids", [])
            if not isinstance(rule_ids, list) or any(
                    not isinstance(rid, str) or rid not in rule_by_id
                    for rid in rule_ids):
                errors.append("%s rule_ids must reference registered rules" % dwhere)
    return errors


def validate_source_review_fixtures(fixtures, registry):
    """Validate paired positive and clean cases for accepted source rules."""
    errors = []
    if not isinstance(fixtures, list):
        return ["humanizer review fixtures must be a list"]
    rule_by_id = {rule.get("id"): rule for rule in registry.get("rules", [])}
    reviews = registry.get("source_reviews", {})
    review = reviews.get(HUMANIZER_SOURCE_REVIEW, {}) if isinstance(reviews, dict) else {}
    accepted = set()
    for decision in review.get("decisions", []) if isinstance(review, dict) else []:
        if decision.get("decision") in ("adopt", "adapt"):
            accepted.update(decision.get("rule_ids", []))
    by_rule = {}
    seen_ids = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            errors.append("humanizer review fixture must be an object")
            continue
        fid = fixture.get("id")
        rid = fixture.get("rule_id")
        kind = fixture.get("kind")
        if not isinstance(fid, str) or not fid.strip() or fid in seen_ids:
            errors.append("humanizer review fixture ids must be unique, non-empty strings")
        seen_ids.add(fid)
        if rid not in rule_by_id:
            errors.append("humanizer review fixture '%s' references unknown rule '%s'" % (fid, rid))
        if kind not in ("positive", "clean"):
            errors.append("humanizer review fixture '%s' kind must be positive or clean" % fid)
        if not isinstance(fixture.get("source"), str) or not fixture["source"].strip():
            errors.append("humanizer review fixture '%s' needs source text" % fid)
        if not isinstance(fixture.get("expected_finding"), bool):
            errors.append("humanizer review fixture '%s' expected_finding must be boolean" % fid)
        if not isinstance(fixture.get("rationale"), str) or not fixture["rationale"].strip():
            errors.append("humanizer review fixture '%s' needs rationale" % fid)
        by_rule.setdefault(rid, []).append(fixture)

    for rid in sorted(accepted):
        fixtures_for_rule = by_rule.get(rid, [])
        kinds = {fixture.get("kind") for fixture in fixtures_for_rule}
        if kinds != {"positive", "clean"}:
            errors.append("accepted rule '%s' needs one positive and one clean fixture" % rid)
        rule = rule_by_id.get(rid, {})
        declared = set(rule.get("evidence_meta", {}).get("local_fixtures", []))
        actual = {fixture.get("id") for fixture in fixtures_for_rule}
        if actual != declared:
            errors.append("accepted rule '%s' local_fixtures must match its paired fixtures" % rid)
    return errors


def validate_evidence_schema(registry):
    """Validate the provenance sections of the rule registry.

    Returns a list of error strings. Guards the evidence metadata schema
    (AC1), pins adopted external concepts to an exact commit and source-file
    permalink (AC2), keeps the provenance classes distinguishable (AC3), and
    enforces the stale-lexical queue, strict-threshold, and zero-em-dash
    contracts (AC5, AC6, AC8).
    """
    errors = []
    relpath = "rules.json"

    classes = registry.get("evidence_classes")
    if not isinstance(classes, dict):
        errors.append(f"{relpath}: missing 'evidence_classes' object")
        classes = {}
    for name in EVIDENCE_CLASSES:
        desc = classes.get(name)
        if not (isinstance(desc, str) and desc.strip()):
            errors.append(f"{relpath}: evidence_classes missing non-empty "
                          f"'{name}'")
    for name in classes:
        if name not in EVIDENCE_CLASSES:
            errors.append(f"{relpath}: unknown evidence class '{name}'")

    decays = registry.get("decay_states")
    if not isinstance(decays, dict):
        errors.append(f"{relpath}: missing 'decay_states' object")
        decays = {}
    for name in DECAY_STATES:
        desc = decays.get(name)
        if not (isinstance(desc, str) and desc.strip()):
            errors.append(f"{relpath}: decay_states missing non-empty "
                          f"'{name}'")
    for name in decays:
        if name not in DECAY_STATES:
            errors.append(f"{relpath}: unknown decay state '{name}'")

    queue = registry.get("review_queue")
    if not isinstance(queue, dict):
        errors.append(f"{relpath}: missing 'review_queue' object")
        queue = {}
    if not (isinstance(queue.get("schema"), str) and queue["schema"].strip()):
        errors.append(f"{relpath}: review_queue missing non-empty 'schema'")

    rules = registry.get("rules", [])
    rule_by_id = {rule.get("id"): rule for rule in rules}

    for rule in rules:
        rid = rule.get("id", "?")
        meta = rule.get("evidence_meta")
        if not isinstance(meta, dict):
            errors.append(f"{relpath}: rule '{rid}': missing 'evidence_meta' "
                          "object")
            continue
        where = f"{relpath}: rule '{rid}' evidence_meta"
        cls = meta.get("class")
        if cls not in EVIDENCE_CLASSES:
            errors.append(f"{where}: unknown class '{cls}'")
        decay = meta.get("decay")
        if decay not in DECAY_STATES:
            errors.append(f"{where}: unknown decay '{decay}'")
        last_reviewed = meta.get("last_reviewed")
        if not (isinstance(last_reviewed, str) and DATE_RE.match(last_reviewed)):
            errors.append(f"{where}: last_reviewed must be an ISO date")
        source_date = meta.get("source_date")
        if source_date is not None and not (
                isinstance(source_date, str) and DATE_RE.match(source_date)):
            errors.append(f"{where}: source_date must be an ISO date")
        if cls in IDENTIFIED_SOURCE_CLASSES:
            for field in ("repository", "commit", "source_file"):
                value = meta.get(field)
                if not (isinstance(value, str) and value.strip()):
                    errors.append(f"{where}: class '{cls}' requires "
                                  f"non-empty '{field}'")
            commit = meta.get("commit")
            if commit and not COMMIT_RE.match(commit):
                errors.append(f"{where}: commit must be a 7-40 hex string")
            source_file = meta.get("source_file")
            if source_file and not URL_RE.match(source_file):
                errors.append(f"{where}: source_file must be a permalink URL")
        if cls == "project-policy" and meta.get("commit"):
            errors.append(f"{where}: a project-policy rule must not pin an "
                          "external commit")
        local_fixtures = meta.get("local_fixtures")
        if local_fixtures is not None and (
                not isinstance(local_fixtures, list) or any(
                    not isinstance(fid, str) or not fid
                    for fid in local_fixtures)):
            errors.append(f"{where}: local_fixtures must be a list of "
                          "non-empty strings")

    entries = queue.get("entries", []) if isinstance(queue, dict) else []
    if not isinstance(entries, list):
        errors.append(f"{relpath}: review_queue.entries must be a list")
        entries = []
    queued_ids = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(f"{relpath}: review_queue.entries must be objects")
            continue
        eid = entry.get("rule_id")
        if not (isinstance(eid, str) and eid.strip()):
            errors.append(f"{relpath}: review_queue entry missing 'rule_id'")
            continue
        queued_ids.add(eid)
        if eid not in rule_by_id:
            errors.append(f"{relpath}: review_queue entry '{eid}' has no rule")
            continue
        meta = rule_by_id[eid].get("evidence_meta", {})
        if meta.get("decay") not in ("review", "stale"):
            errors.append(f"{relpath}: review_queue entry '{eid}' is not "
                          "decay=review/stale")
        reason = entry.get("reason")
        if not (isinstance(reason, str) and reason.strip()):
            errors.append(f"{relpath}: review_queue entry '{eid}' missing "
                          "non-empty 'reason'")
    for rule in rules:
        rid = rule.get("id")
        meta = rule.get("evidence_meta", {})
        if meta.get("decay") in ("review", "stale") and rid not in queued_ids:
            errors.append(f"{relpath}: rule '{rid}' decay={meta.get('decay')} "
                          "is not listed in the review_queue")

    # AC6: a strict (deterministic) scoring rule with an external numeric
    # threshold needs a directly identified source and local fixtures.
    for rule in rules:
        rid = rule.get("id", "?")
        if rule.get("review_mode") != "deterministic":
            continue
        if rule.get("semantic_type") not in ("forbidden", "discouraged"):
            continue
        has_numeric = bool(NUMERIC_RE.search(rule.get("text", ""))) or bool(
            rule.get("detector"))
        if not has_numeric:
            continue
        meta = rule.get("evidence_meta", {})
        has_fixtures = bool(meta.get("local_fixtures"))
        if meta.get("class") == "project-policy":
            # A house-style rule is the project's own policy: it needs local
            # fixtures to be a strict executable rule but no external source.
            if not has_fixtures:
                errors.append(f"{relpath}: rule '{rid}' is deterministic "
                              "with a registered detector; it needs local "
                              "fixtures to pin its behavior")
            continue
        has_source = all(meta.get(f) for f in
                         ("repository", "commit", "source_file"))
        if not (has_source and has_fixtures):
            errors.append(f"{relpath}: rule '{rid}' is deterministic with an "
                          "external numeric threshold; it needs a directly "
                          "identified source and local fixtures")

    # AC8: the zero-em-dash policy stays absolute regardless of corpus drift.
    em_dash = rule_by_id.get("fmt-em-dash")
    if em_dash is not None:
        meta = em_dash.get("evidence_meta", {})
        if meta.get("class") != "project-policy":
            errors.append(f"{relpath}: fmt-em-dash must be evidence class "
                          "'project-policy'")
        if meta.get("decay") != "current":
            errors.append(f"{relpath}: fmt-em-dash must stay decay 'current'")

    candidates = queue.get("candidates", []) if isinstance(queue, dict) else []
    if not isinstance(candidates, list):
        errors.append(f"{relpath}: review_queue.candidates must be a list")
        candidates = []
    for cand in candidates:
        if not isinstance(cand, dict):
            errors.append(f"{relpath}: review_queue.candidates must be objects")
            continue
        cid = cand.get("id")
        if not (isinstance(cid, str) and cid.strip()):
            errors.append(f"{relpath}: candidate missing 'id'")
            continue
        where = f"{relpath}: candidate '{cid}'"
        if cid in rule_by_id:
            errors.append(f"{where}: candidate id collides with a rule id")
        for field in ("name", "description"):
            if not (isinstance(cand.get(field), str) and cand[field].strip()):
                errors.append(f"{where}: missing non-empty '{field}'")
        signal = cand.get("signal")
        fixture_ids = cand.get("fixture_ids")
        if not (isinstance(fixture_ids, list) and fixture_ids):
            errors.append(f"{where}: candidate needs non-empty fixture_ids")
            fixture_ids = []
        has_source = all(cand.get(f) for f in
                         ("repository", "commit", "source_file"))
        if signal == "strict" and cand.get("threshold") is not None and not (
                has_source and fixture_ids):
            errors.append(f"{where}: a strict numeric candidate needs a "
                          "directly identified source and local fixtures")
        for ref in ("matched_length_clean", "matched_profile_clean"):
            ref_id = cand.get(ref)
            if not (isinstance(ref_id, str) and ref_id.strip()):
                errors.append(f"{where}: missing '{ref}' fixture reference")

    errors.extend(validate_source_reviews(registry))
    return errors


def _run_detection(source, rule, registry, profile):
    """Detect one rule against a source. Returns True when a finding fires."""
    import score  # noqa: F401 -- lazy import keeps fixture runs cheap

    findings, _skipped, _metrics = score.detect_findings(
        source, registry, profile)
    return any(f["rule_id"] == rule.get("id") for f in findings)


def _contract_violations(rule):
    """Verify the absolute zero-em-dash contract for fmt-em-dash."""
    violations = []
    if rule.get("semantic_type") != "forbidden":
        violations.append("fmt-em-dash must stay forbidden")
    if rule.get("review_mode") != "deterministic":
        violations.append("fmt-em-dash must stay deterministic")
    if rule.get("profiles") != ["*"]:
        violations.append("fmt-em-dash must stay universal")
    if "zero" not in rule.get("evidence", "").lower():
        violations.append("fmt-em-dash evidence must state the zero-count "
                          "contract")
    return violations


def validate_fixture(fixture, seen_ids, registry):
    """Schema-validate one provenance fixture. Returns error strings."""
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
    if kind not in ("rule", "candidate"):
        errors.append("%s: kind must be 'rule' or 'candidate'" % where)
        return errors

    rule_by_id = {rule.get("id"): rule for rule in registry.get("rules", [])}
    candidates = {c.get("id"): c
                  for c in (registry.get("review_queue", {}) or {})
                  .get("candidates", [])}

    if kind == "rule":
        rid = fixture.get("rule_id")
        if not (isinstance(rid, str) and rid.strip()):
            errors.append("%s: rule fixture missing 'rule_id'" % where)
        elif rid not in rule_by_id:
            errors.append("%s: rule_id '%s' is not in the registry" % (where, rid))
        detection = fixture.get("detection")
        if detection not in ("contract", "score", "structural"):
            errors.append("%s: detection must be 'contract', 'score', or "
                          "'structural'" % where)
        else:
            source = fixture.get("source")
            if detection in ("score", "structural") and not (
                    isinstance(source, str) and source.strip()):
                errors.append("%s: detection %s requires a non-empty 'source'"
                              % (where, detection))
        if detection != "contract":
            expected = fixture.get("expected_finding")
            if not isinstance(expected, bool):
                errors.append("%s: expected_finding must be a boolean" % where)
        profile = fixture.get("profile", "general")
        if profile not in PROFILES:
            errors.append("%s: profile must be one of %s"
                          % (where, ", ".join(PROFILES)))
        return errors

    cid = fixture.get("candidate_id")
    if not (isinstance(cid, str) and cid.strip()):
        errors.append("%s: candidate fixture missing 'candidate_id'" % where)
        return errors
    if cid not in candidates:
        errors.append("%s: candidate_id '%s' is not in the review_queue"
                      % (where, cid))
    source = fixture.get("source")
    if not (isinstance(source, str) and source.strip()):
        errors.append("%s: 'source' must be a non-empty string" % where)
    expected_clean = fixture.get("expected_clean")
    if not isinstance(expected_clean, bool):
        errors.append("%s: expected_clean must be a boolean" % where)
    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(PROFILES)))
    clean_kind = fixture.get("clean_kind")
    if clean_kind is not None:
        kinds = clean_kind if isinstance(clean_kind, list) else [clean_kind]
        if not kinds or any(k not in ("matched-length", "matched-profile")
                            for k in kinds):
            errors.append("%s: clean_kind must be 'matched-length', "
                          "'matched-profile', or a list of the two" % where)
    if expected_clean is False and clean_kind is not None:
        errors.append("%s: a positive fixture must not carry clean_kind"
                      % where)
    rationale = fixture.get("rationale")
    if not (isinstance(rationale, str) and rationale.strip()):
        errors.append("%s: missing non-empty 'rationale'" % where)
    notes = fixture.get("reviewer_notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append("%s: reviewer_notes must be a non-empty string" % where)
    return errors


def rule_fixture_failures(fixture, rule, registry):
    """Compare a rule fixture against the registry and detection."""
    failures = []
    meta = rule.get("evidence_meta", {})
    expected_class = fixture.get("expected_evidence_class")
    if expected_class is not None and meta.get("class") != expected_class:
        failures.append("expected evidence class %s, got %s"
                        % (expected_class, meta.get("class")))
    expected_decay = fixture.get("expected_decay")
    if expected_decay is not None and meta.get("decay") != expected_decay:
        failures.append("expected decay %s, got %s"
                        % (expected_decay, meta.get("decay")))

    # Being listed in the review queue must never disable a rule: the rule
    # still carries an active semantic type and review mode.
    if not rule.get("semantic_type") or not rule.get("review_mode"):
        failures.append("rule is not active (missing semantic_type or "
                        "review_mode)")

    detection = fixture.get("detection")
    if detection == "contract":
        failures.extend(_contract_violations(rule))
    elif detection in ("score", "structural"):
        fired = _run_detection(fixture["source"], rule, registry,
                               fixture.get("profile", "general"))
        expected = fixture.get("expected_finding")
        if fired != expected:
            failures.append("expected_finding=%s, detection=%s"
                            % (expected, fired))
    return failures


def candidate_fixture_failures(fixture, candidate, registry):
    """Compare a candidate fixture against its candidate definition."""
    failures = []
    fixture_ids = candidate.get("fixture_ids", [])
    if fixture["id"] not in fixture_ids:
        failures.append("fixture not referenced by candidate.fixture_ids")
    if fixture.get("expected_clean"):
        kinds = fixture.get("clean_kind") or []
        if isinstance(kinds, str):
            kinds = [kinds]
        if "matched-length" in kinds and candidate.get(
                "matched_length_clean") != fixture["id"]:
            failures.append("fixture is not the candidate's "
                            "matched_length_clean reference")
        if "matched-profile" in kinds and candidate.get(
                "matched_profile_clean") != fixture["id"]:
            failures.append("fixture is not the candidate's "
                            "matched_profile_clean reference")
    return failures


def run_provenance_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one provenance fixture."""
    report = {
        "id": fixture["id"],
        "kind": fixture["kind"],
        "profile": fixture.get("profile", "general"),
        "rationale": fixture.get("rationale"),
        "reviewer_notes": fixture.get("reviewer_notes"),
        "failures": [],
    }
    if fixture["kind"] == "rule":
        rule_by_id = {rule.get("id"): rule
                      for rule in registry.get("rules", [])}
        rule = rule_by_id.get(fixture.get("rule_id"))
        if rule is None:
            report["failures"].append("rule not found")
            return report
        report["rule_id"] = rule["id"]
        report["evidence_class"] = rule.get("evidence_meta", {}).get("class")
        report["decay"] = rule.get("evidence_meta", {}).get("decay")
        report["failures"] = rule_fixture_failures(fixture, rule, registry)
        return report
    candidates = {c.get("id"): c
                  for c in (registry.get("review_queue", {}) or {})
                  .get("candidates", [])}
    candidate = candidates.get(fixture.get("candidate_id"))
    if candidate is None:
        report["failures"].append("candidate not found")
        return report
    report["candidate_id"] = candidate["id"]
    report["expected_clean"] = fixture.get("expected_clean")
    report["clean_kind"] = fixture.get("clean_kind")
    report["failures"] = candidate_fixture_failures(fixture, candidate,
                                                    registry)
    return report


def corpus_candidate_errors(fixtures, registry):
    """Corpus-level checks for the candidate clean-case contract (AC7).

    Every candidate needs a positive case plus matched-length and
    matched-profile clean cases. The matched-length clean case must be within
    LENGTH_MATCH_RATIO of the positive case's length, and the matched-profile
    clean case must use the positive case's profile.
    """
    errors = []
    by_id = {f.get("id"): f for f in fixtures if isinstance(f, dict)}
    candidates = (registry.get("review_queue", {}) or {}).get("candidates", [])
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        cid = cand.get("id")
        where = "candidate '%s'" % (cid or "?")
        related = [f for f in fixtures
                   if isinstance(f, dict)
                   and f.get("candidate_id") == cid
                   and f.get("id") in cand.get("fixture_ids", [])]
        positive = [f for f in related if f.get("expected_clean") is False]
        if len(positive) != 1:
            errors.append("%s: expected exactly one positive fixture, got %d"
                          % (where, len(positive)))
            continue
        pos = positive[0]
        pos_len = len(pos.get("source", ""))
        if pos_len == 0:
            errors.append("%s: positive fixture has no source" % where)
            continue

        clean = [f for f in related if f.get("expected_clean") is True]
        if not clean:
            errors.append("%s: no clean fixture referenced" % where)
            continue

        length_ref = cand.get("matched_length_clean")
        if length_ref not in by_id:
            errors.append("%s: matched_length_clean '%s' not in the corpus"
                          % (where, length_ref))
        else:
            clean_fx = by_id[length_ref]
            if clean_fx.get("expected_clean") is not True:
                errors.append("%s: matched_length_clean fixture must be clean"
                              % where)
            length = len(clean_fx.get("source", ""))
            if pos_len and abs(length - pos_len) / pos_len > LENGTH_MATCH_RATIO:
                errors.append(
                    "%s: matched-length clean case is %d chars vs positive "
                    "%d (ratio limit %.2f)"
                    % (where, length, pos_len, LENGTH_MATCH_RATIO))

        profile_ref = cand.get("matched_profile_clean")
        if profile_ref not in by_id:
            errors.append("%s: matched_profile_clean '%s' not in the corpus"
                          % (where, profile_ref))
        else:
            clean_fx = by_id[profile_ref]
            if clean_fx.get("expected_clean") is not True:
                errors.append("%s: matched_profile_clean fixture must be clean"
                              % where)
            if clean_fx.get("profile", "general") != pos.get(
                    "profile", "general"):
                errors.append("%s: matched-profile clean case uses profile "
                              "'%s', positive uses '%s'"
                              % (where, clean_fx.get("profile", "general"),
                                 pos.get("profile", "general")))

        for ref_id in (length_ref, profile_ref):
            if ref_id and ref_id not in cand.get("fixture_ids", []):
                errors.append("%s: clean reference '%s' is not listed in "
                              "fixture_ids" % (where, ref_id))
    return errors


def run_provenance_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the provenance fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_fixture(fixture, seen_ids, registry))
    if not schema_errors:
        schema_errors.extend(corpus_candidate_errors(fixtures, registry))

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

    reports = [run_provenance_fixture(fixture, registry, registry_path)
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
            "kind": report["kind"],
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
        description="Antislop rule provenance and decay review")
    parser.add_argument("--fixtures", default=FIXTURES_PATH,
                        help="Path to the provenance fixture corpus")
    parser.add_argument("--registry", default=REGISTRY_PATH,
                        help="Path to the rule registry")
    args = parser.parse_args()

    if not os.path.exists(args.registry):
        print(f"ERROR: registry not found: {args.registry}", file=sys.stderr)
        sys.exit(2)
    registry = load_registry(args.registry)

    schema_errors = validate_evidence_schema(registry)
    if schema_errors:
        for err in schema_errors:
            print(f"  FAIL  {err}")
        print(f"\n{len(schema_errors)} evidence-schema error(s)")
        sys.exit(1)

    if not os.path.exists(args.fixtures):
        print(f"ERROR: fixtures not found: {args.fixtures}", file=sys.stderr)
        sys.exit(2)
    try:
        data = load_json(args.fixtures)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {args.fixtures}: {exc}", file=sys.stderr)
        sys.exit(2)
    fixtures = data.get("evals", data)
    if not isinstance(fixtures, list):
        print("ERROR: fixture corpus must be a JSON list or carry an 'evals' "
              "list", file=sys.stderr)
        sys.exit(2)

    report = run_provenance_corpus(fixtures, registry, args.registry)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["gate_pass"] else 1)


if __name__ == "__main__":
    main()
