#!/usr/bin/env python3
"""ReviewWrite-style evidence-bound delivery envelope (issue #95).

Reviewed against songhai-dg/review-write at 5c51063 (MIT). Antislop never
bound a reviewed source, a revision plan, a delivered body, and a
verification result into one inspectable record, so findings or verifier
commentary could leak into the revised prose and an old verification result
could be mistaken for evidence about a later edit. This runner defines an
optional repair envelope with four separate fields:

  review_report        the findings on the reviewed source, kept out of the
                       deliverable
  revision_plan        the planned edits, kept out of the deliverable
  deliverable_body     the delivered text, stored separately
  verification_report  the verification result, with the exact source and
                       body digests it covers

The body digest is a stable SHA-256 over the UTF-8 body with normalized line
endings. When a source record is bound, its digest uses a versioned canonical
serialization: stable key order, UTF-8 encoding, and normalized line endings,
with the serialization version hashed as part of the digest.

check_envelope returns typed failures for missing, stale, or mismatched
verification:

  missing_verification     no verification_report is bound
  stale_verification       the stored verification's body digest no longer
                           matches the current deliverable body
  mismatched_verification  the stored verification's source digest does not
                           match the bound source record

Preservation (required facts, protected literals, qualifiers, uncertainty,
attribution, and forbidden additions) reuses fidelity.py's protected spans
and semantic anchors, drift.py's fact matching and semantic dimensions, and
the edit.py revise contract. Long documents can be verified in chunks so a
fact introduced in one chunk and qualified in another is retained across the
whole delivered body.

Boundaries: the digest is not proof of semantic equivalence; the ReviewWrite
operational platform (planning UI, credit budgets, and multi-model
orchestration) is not imported; model judgment stays advisory and the runner
fails only on explicit envelope or preservation contracts.

Usage:
    python3 tools/delivery.py verify --source-text "..." --body-text "..."
    python3 tools/delivery.py envelope --source-text "..." --body-text "..." --medium argument
    python3 tools/delivery.py check --envelope envelope.json
    python3 tools/delivery.py --fixtures skills/antislop/evals/delivery-envelope-fixtures.json
    python3 tools/delivery.py --help

Exit codes:
    0 -- the run verified, or every fixture decision matched its expectation
    1 -- verification failed, or a fixture decision failed
    2 -- usage or input error
"""

import argparse
import hashlib
import json
import os
import re
import sys

import limits
from registry import load_registry
import drift
import fidelity
import review

INTERFACE = "antislop.delivery"
SCHEMA = "delivery-report-1"
ENVELOPE_SCHEMA = "delivery-envelope-1"
VERIFICATION_SCHEMA = "delivery-verification-1"
ENVELOPE_CHECK_SCHEMA = "delivery-envelope-check-1"
FIXTURE_SCHEMA = "delivery-envelope-fixtures-1"

SOURCE_DIGEST_SCHEMA = "antislop-source-v1"
SOURCE_RECORD_SCHEMA = "reviewed-source-v1"
DIGEST_SCHEMA = "antislop-digest-v1"

PROFILES = {"general", "technical"}
DECISIONS = ("verified", "failed")
VERIFY_FAILURE_KINDS = (
    "required_fact_missing",
    "forbidden_addition",
    "protected_literal_changed",
    "protected_literal_missing",
    "qualifier_changed",
    "promise_changed",
    "attribution_changed",
    "source_record_mismatch",
)
ENVELOPE_FAILURE_KINDS = (
    "missing_verification",
    "stale_verification",
    "mismatched_verification",
)
FIXTURE_KINDS = ("verify", "chunked", "envelope")
TAMPERS = ("none", "body", "source", "drop-verification")
MEDIUMS = review.MEDIUMS

DISCLAIMER = (
    "Delivery results bind a reviewed source, revision plan, delivered body, "
    "and verification result; they never prove AI authorship or detector "
    "immunity."
)

LINE_ENDING_RE = re.compile(r"\r\n|\r")


def normalize_line_endings(text):
    """Normalize CRLF and CR to LF so a digest is stable across editors."""
    return LINE_ENDING_RE.sub("\n", text)


def body_digest(body):
    """Stable SHA-256 over the normalized UTF-8 body."""
    return hashlib.sha256(
        normalize_line_endings(body).encode("utf-8")).hexdigest()


def _normalize_record(record):
    """Recursively normalize line endings inside string values."""
    if isinstance(record, dict):
        return {key: _normalize_record(value) for key, value in record.items()}
    if isinstance(record, list):
        return [_normalize_record(value) for value in record]
    if isinstance(record, str):
        return normalize_line_endings(record)
    return record


def canonical_serialize(record, schema=DIGEST_SCHEMA):
    """Versioned canonical serialization for hashing.

    Stable key order (sort_keys), UTF-8 encoding, and line endings normalized
    to LF inside string values before serialization, so the escaped newline
    forms cannot differ across editors. The schema name is hashed as part of
    the payload so a later format change cannot reuse an old digest.
    """
    payload = {"schema": schema, "record": _normalize_record(record)}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return text.encode("utf-8")


def record_digest(record, schema=DIGEST_SCHEMA):
    return hashlib.sha256(canonical_serialize(record, schema)).hexdigest()


def source_digest(source_record):
    """Digest of a source record under the versioned source serialization."""
    return record_digest(source_record, schema=SOURCE_DIGEST_SCHEMA)


def bind_source_record(source, medium=None):
    """The default reviewed-source record bound into an envelope."""
    return {"schema": SOURCE_RECORD_SCHEMA,
            "medium": medium or "argument",
            "source": source}


def _anchor_failure_kind(category):
    return ("attribution_changed" if category in ("attribution", "name")
            else "qualifier_changed")


def _preservation(source, body, *, required_facts=(), required_terms=(),
                  forbidden_additions=(), semantic_dimensions=None,
                  registry_path="rules.json", profile="general"):
    """Preservation contracts reused from fidelity.py, drift.py, and the
    edit.py revise contract. Returns (failures, reasons, items)."""
    failures = []
    reasons = []
    items = {"missing": [], "changed": [], "added": [], "unresolved": []}

    for fact in required_facts:
        if not drift.contains_fact(body, fact):
            failures.append({"kind": "required_fact_missing", "value": fact})
            items["missing"].append({"kind": "required_fact_missing",
                                     "value": fact})
            reasons.append("required fact '%s' is missing" % fact)

    for term in forbidden_additions:
        if drift.contains_fact(body, term):
            failures.append({"kind": "forbidden_addition", "value": term})
            items["added"].append({"kind": "forbidden_addition", "value": term})
            reasons.append("forbidden addition '%s' is present" % term)

    fidelity_report = fidelity.check_fidelity(
        source, body,
        required_terms=tuple(required_terms),
        authorized_changes=(),
        hot_zones=[],
        churn_limit=None,
        human_review_categories=(),
        registry_path=registry_path,
        profile=profile,
    )
    for failure in fidelity_report["preservation"]["hard_failures"]:
        kind = failure["kind"]
        category = failure.get("category", "anchor")
        source_value = failure.get("source")
        candidate_value = failure.get("candidate")
        if kind == "protected_span_changed":
            failures.append({"kind": "protected_literal_changed",
                             "category": category, "source": source_value,
                             "candidate": candidate_value})
            items["changed"].append({"kind": "protected_literal_changed",
                                     "category": category,
                                     "source": source_value,
                                     "candidate": candidate_value})
            reasons.append("protected %s changed from '%s' to '%s'"
                           % (category, source_value, candidate_value))
        elif kind == "protected_span_removed":
            failures.append({"kind": "protected_literal_missing",
                             "category": category, "source": source_value})
            items["missing"].append({"kind": "protected_literal_missing",
                                     "category": category,
                                     "source": source_value})
            reasons.append("protected %s '%s' is missing"
                           % (category, source_value))
        else:
            fkind = _anchor_failure_kind(category)
            failures.append({"kind": fkind, "category": category,
                             "source": source_value,
                             "candidate": candidate_value})
            items["changed"].append({"kind": fkind, "category": category,
                                     "source": source_value,
                                     "candidate": candidate_value})
            reasons.append("%s in %s" % (kind, category))
    for item in fidelity_report["preservation"]["human_review"]:
        fkind = _anchor_failure_kind(item["category"])
        failures.append({"kind": fkind, "category": item["category"],
                         "source": item.get("source"),
                         "candidate": item.get("candidate")})
        items["changed"].append({"kind": fkind, "category": item["category"],
                                 "source": item.get("source"),
                                 "candidate": item.get("candidate")})
        reasons.append("human review required for changed %s"
                       % item["category"])

    if semantic_dimensions:
        dimensions = drift.check_semantic_dimensions(
            {"semantic_dimensions": semantic_dimensions}, source, body)
        for violation in dimensions["violations"]:
            kind = ("promise_changed"
                    if "promise_intensity" in violation
                    else "qualifier_changed")
            failures.append({"kind": kind, "value": violation})
            items["changed"].append({"kind": kind, "value": violation})
            reasons.append(violation)

    return failures, reasons, items


def verify_delivery(source, body, *, source_record=None, required_facts=(),
                    required_terms=(), forbidden_additions=(),
                    semantic_dimensions=None, registry_path="rules.json",
                    profile="general"):
    limits.check_input_size(source, "source text")
    limits.check_input_size(body, "body text")
    """Verify a delivered body against its source and return a verification
    report with the exact source and body digests it covers."""
    registry = load_registry(registry_path)
    failures, reasons, items = _preservation(
        source, body,
        required_facts=required_facts, required_terms=required_terms,
        forbidden_additions=forbidden_additions,
        semantic_dimensions=semantic_dimensions,
        registry_path=registry_path, profile=profile)
    if source_record is not None:
        if not isinstance(source_record, dict) or source_record.get("source") != source:
            failures.append({"kind": "source_record_mismatch"})
            reasons.append("source_record does not contain the verified source")
    decision = "verified" if not failures else "failed"
    return {
        "interface": INTERFACE,
        "schema": VERIFICATION_SCHEMA,
        "version": registry.get("version", "unknown"),
        "decision": decision,
        "failures": failures,
        "reasons": reasons,
        "items": items,
        "body_digest": body_digest(body),
        "source_digest": (source_digest(source_record)
                          if source_record is not None else None),
        "digests": {
            "scheme": "sha256",
            "encoding": "utf-8",
            "line_endings": "lf-normalized",
            "source_schema": SOURCE_DIGEST_SCHEMA,
        },
        "meta": {
            "disclaimer": DISCLAIMER,
            "profile": profile,
        },
    }


def verify_chunked_delivery(chunks, body, *, forbidden_additions=(),
                            semantic_dimensions=None, registry_path="rules.json",
                            profile="general"):
    """Verify a long document delivered in chunks.

    Each chunk declares facts and terms for its own source section; a fact
    or term introduced in one chunk must survive in the whole body
    (cross-section facts). The register checks run over the whole assembled
    source and body, so a qualifier in one chunk cannot be dropped while the
    fact it qualifies lives in another (whole-document register).
    """
    facts = []
    terms = []
    seen_facts = set()
    seen_terms = set()
    sources = []
    for chunk in chunks:
        source = chunk.get("source", "")
        sources.append(source)
        for fact in chunk.get("required_facts", []):
            if fact not in seen_facts and drift.contains_fact(source, fact):
                seen_facts.add(fact)
                facts.append(fact)
        for term in chunk.get("required_terms", []):
            if term not in seen_terms and drift.contains_fact(source, term):
                seen_terms.add(term)
                terms.append(term)
    full_source = "\n\n".join(sources)
    return verify_delivery(
        full_source, body,
        required_facts=facts, required_terms=terms,
        forbidden_additions=forbidden_additions,
        semantic_dimensions=semantic_dimensions,
        registry_path=registry_path, profile=profile)


def bind_envelope(*, body="", review_report=None, revision_plan=None,
                  verification_report=None, source_record=None,
                  registry_path="rules.json"):
    """Bind the four envelope fields into one inspectable record.

    The deliverable body stays separate from findings, plans, and verification
    commentary. The envelope carries the current body digest so the covered
    digest is visible next to the bound verification.
    """
    registry = load_registry(registry_path)
    envelope = {
        "interface": INTERFACE,
        "schema": ENVELOPE_SCHEMA,
        "version": registry.get("version", "unknown"),
        "review_report": review_report if review_report is not None else {},
        "revision_plan": revision_plan if revision_plan is not None else {},
        "deliverable_body": body,
        "body_digest": body_digest(body),
        "verification_report": verification_report,
    }
    if source_record is not None:
        envelope["source_record"] = source_record
    return envelope


def deliver(*, source=None, body=None, medium=None, source_record=None,
            review_report=None, revision_plan=None, bind_source=False,
            required_facts=(), required_terms=(), forbidden_additions=(),
            semantic_dimensions=None, profile="general",
            registry_path="rules.json"):
    """Build an envelope: optional review report and revision plan, a fresh
    verification, and the four fields bound together."""
    registry = load_registry(registry_path)
    if review_report is None and medium is not None and source is not None:
        review_report = review.review_text(source, medium, registry,
                                           profile=profile)
    if source_record is None and bind_source and source is not None:
        source_record = bind_source_record(source, medium)
    verification = verify_delivery(
        source or "", body or "", source_record=source_record,
        required_facts=required_facts, required_terms=required_terms,
        forbidden_additions=forbidden_additions,
        semantic_dimensions=semantic_dimensions,
        registry_path=registry_path, profile=profile)
    return bind_envelope(body=body or "", review_report=review_report,
                         revision_plan=revision_plan,
                         verification_report=verification,
                         source_record=source_record,
                         registry_path=registry_path)


def check_envelope(envelope, *, registry_path="rules.json"):
    """Inspect a stored envelope for missing, stale, or mismatched
    verification.

    The body digest is recomputed from the current deliverable body, never
    trusted from the stored field, so a body edited after verification cannot
    keep a passing record.
    """
    registry = load_registry(registry_path)
    failures = []
    body = envelope.get("deliverable_body", "")
    current_body_digest = body_digest(body)
    verification = envelope.get("verification_report")
    verification_decision = None
    covered_body = None
    covered_source = None
    if not isinstance(verification, dict) or not verification:
        failures.append({"kind": "missing_verification"})
    else:
        verification_decision = verification.get("decision")
        covered_body = verification.get("body_digest")
        covered_source = verification.get("source_digest")
        if covered_body != current_body_digest:
            failures.append({
                "kind": "stale_verification",
                "covered": covered_body,
                "current": current_body_digest,
            })
        source_record = envelope.get("source_record")
        if source_record is not None:
            current_source_digest = source_digest(source_record)
            if covered_source != current_source_digest:
                failures.append({
                    "kind": "mismatched_verification",
                    "covered": covered_source,
                    "current": current_source_digest,
                })
        elif covered_source is not None:
            failures.append({
                "kind": "mismatched_verification",
                "covered": covered_source,
                "current": None,
            })
    decision = "verified"
    if failures or verification_decision == "failed":
        decision = "failed"
    return {
        "interface": INTERFACE,
        "schema": ENVELOPE_CHECK_SCHEMA,
        "version": registry.get("version", "unknown"),
        "decision": decision,
        "failures": failures,
        "body_digest": current_body_digest,
        "verification": {
            "present": isinstance(verification, dict) and bool(verification),
            "decision": verification_decision,
            "covered_body_digest": covered_body,
            "covered_source_digest": covered_source,
        },
        "meta": {
            "disclaimer": DISCLAIMER,
        },
    }


def _report_text_in_body(review_report, body):
    """Verifier commentary (why, suggestion, author questions) must not leak
    into the deliverable. Quoted source patterns and excerpts are excluded:
    they are the reviewed material, not the reviewer's own words."""
    for finding in (review_report or {}).get("findings", []):
        for field in ("why", "suggestion", "tk", "message"):
            text = finding.get(field)
            if text and text in body:
                return True
    return False


def validate_fixture(fixture, seen_ids):
    """Schema-validate one delivery-envelope fixture. Returns error strings."""
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

    expected = fixture.get("expected_decision")
    if expected not in DECISIONS:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(DECISIONS)))

    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(sorted(PROFILES))))

    if kind in ("verify", "envelope"):
        source = fixture.get("source")
        if not isinstance(source, str) or not source.strip():
            errors.append("%s: 'source' must be a non-empty string" % where)
    body = fixture.get("body")
    if not isinstance(body, str) or not body.strip():
        errors.append("%s: 'body' must be a non-empty string" % where)

    errors.extend(drift._str_list(fixture.get("required_facts", []),
                                  "%s.required_facts" % where))
    errors.extend(drift._str_list(fixture.get("required_terms", []),
                                  "%s.required_terms" % where))
    errors.extend(drift._str_list(fixture.get("forbidden_additions", []),
                                  "%s.forbidden_additions" % where))

    dimensions = fixture.get("semantic_dimensions", {})
    if not isinstance(dimensions, dict):
        errors.append("%s: semantic_dimensions must be an object" % where)
    else:
        for dimension, mode in dimensions.items():
            if dimension not in drift.DIMENSION_ORDER:
                errors.append("%s: unknown semantic dimension '%s'"
                              % (where, dimension))
            if mode not in drift.DIMENSION_MODES:
                errors.append("%s: dimension '%s' mode must be preserve or "
                              "refuse" % (where, dimension))

    failure_kinds = fixture.get("expected_failure_kinds", [])
    if not isinstance(failure_kinds, list):
        errors.append("%s: expected_failure_kinds must be a list" % where)
    else:
        for index, value in enumerate(failure_kinds):
            if value not in VERIFY_FAILURE_KINDS \
                    and value not in ENVELOPE_FAILURE_KINDS:
                errors.append("%s: expected_failure_kinds[%d] must be one of "
                              "%s" % (where, index,
                                      ", ".join(VERIFY_FAILURE_KINDS
                                                + ENVELOPE_FAILURE_KINDS)))

    if kind == "chunked":
        chunks = fixture.get("chunks", [])
        if not isinstance(chunks, list) or not chunks:
            errors.append("%s: chunked fixture needs a non-empty 'chunks' "
                          "list" % where)
        else:
            for index, chunk in enumerate(chunks):
                if not isinstance(chunk, dict):
                    errors.append("%s: chunks[%d] must be an object"
                                  % (where, index))
                    continue
                source = chunk.get("source")
                if not isinstance(source, str) or not source.strip():
                    errors.append("%s: chunks[%d].source must be a non-empty "
                                  "string" % (where, index))
                errors.extend(drift._str_list(
                    chunk.get("required_facts", []),
                    "%s.chunks[%d].required_facts" % (where, index)))
                errors.extend(drift._str_list(
                    chunk.get("required_terms", []),
                    "%s.chunks[%d].required_terms" % (where, index)))

    if kind == "envelope":
        medium = fixture.get("medium")
        if medium is not None and medium not in MEDIUMS:
            errors.append("%s: medium must be one of %s"
                          % (where, ", ".join(MEDIUMS)))
        tamper = fixture.get("tamper", "none")
        if tamper not in TAMPERS:
            errors.append("%s: tamper must be one of %s"
                          % (where, ", ".join(TAMPERS)))
        if fixture.get("tamper") == "source" \
                and not fixture.get("bind_source", False):
            errors.append("%s: 'source' tamper needs bind_source so the "
                          "envelope binds a source record" % where)
        if not isinstance(fixture.get("bind_source", False), bool):
            errors.append("%s: bind_source must be a boolean" % where)
        if not isinstance(fixture.get("report_has_findings", False), bool):
            errors.append("%s: report_has_findings must be a boolean" % where)
        if fixture.get("report_has_findings") and medium is None:
            errors.append("%s: report_has_findings needs a 'medium' so the "
                          "runner can build the review report" % where)
        verification_expected = fixture.get("expected_verification_decision")
        if verification_expected is not None \
                and verification_expected not in DECISIONS:
            errors.append("%s: expected_verification_decision must be one of "
                          "%s" % (where, ", ".join(DECISIONS)))
        revision_plan = fixture.get("revision_plan")
        if revision_plan is not None and not isinstance(revision_plan, dict):
            errors.append("%s: revision_plan must be an object" % where)

    rationale = fixture.get("false_positive_rationale")
    if rationale is not None and (not isinstance(rationale, str)
                                  or not rationale.strip()):
        errors.append("%s: false_positive_rationale must be a non-empty "
                      "string" % where)
    notes = fixture.get("reviewer_notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append("%s: reviewer_notes must be a non-empty string" % where)
    return errors


def _tamper_envelope(envelope, tamper):
    """Apply a fixture tamper to a built envelope."""
    if tamper == "body":
        envelope["deliverable_body"] = envelope.get("deliverable_body", "") + "x"
    elif tamper == "source":
        record = dict(envelope.get("source_record") or {})
        record["note"] = "edited after verification"
        envelope["source_record"] = record
    elif tamper == "drop-verification":
        envelope["verification_report"] = None
    return envelope


def _verify_fixture_failures(report, fixture):
    """Compare a verify or chunked report against its fixture expectations."""
    failures = []
    if report["decision"] != fixture["expected_decision"]:
        failures.append("expected decision %s, got %s"
                        % (fixture["expected_decision"], report["decision"]))
    actual_kinds = [failure["kind"] for failure in report["failures"]]
    for kind in fixture.get("expected_failure_kinds", []):
        if kind not in actual_kinds:
            failures.append("expected failure kind '%s' not reported" % kind)
    return failures


def _envelope_fixture_failures(report, fixture, envelope):
    """Compare an envelope check against its fixture expectations."""
    failures = []
    if report["decision"] != fixture["expected_decision"]:
        failures.append("expected decision %s, got %s"
                        % (fixture["expected_decision"], report["decision"]))
    actual_kinds = [failure["kind"] for failure in report["failures"]]
    for kind in fixture.get("expected_failure_kinds", []):
        if kind not in actual_kinds:
            failures.append("expected failure kind '%s' not reported" % kind)
    expected_verification = fixture.get("expected_verification_decision")
    if expected_verification is not None:
        stored = envelope.get("verification_report") or {}
        if stored.get("decision") != expected_verification:
            failures.append("expected verification decision %s, got %s"
                            % (expected_verification, stored.get("decision")))
    if fixture.get("report_has_findings"):
        report_findings = (envelope.get("review_report") or {}).get(
            "findings", [])
        if not report_findings:
            failures.append("expected the review report to carry findings")
    body = envelope.get("deliverable_body", "")
    leaked = _report_text_in_body(envelope.get("review_report"), body)
    if leaked:
        failures.append("the deliverable body contains review report "
                        "commentary")
    return failures


def run_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one delivery-envelope fixture against its expectations."""
    fid = fixture["id"]
    kind = fixture["kind"]
    profile = fixture.get("profile", "general")
    report = None
    if kind == "verify":
        report = verify_delivery(
            fixture["source"], fixture["body"],
            required_facts=fixture.get("required_facts", []),
            required_terms=fixture.get("required_terms", []),
            forbidden_additions=fixture.get("forbidden_additions", []),
            semantic_dimensions=fixture.get("semantic_dimensions"),
            registry_path=registry_path, profile=profile)
        report["kind"] = kind
        report["id"] = fid
        report["expected_decision"] = fixture["expected_decision"]
        report["meta"]["false_positive_rationale"] = fixture.get(
            "false_positive_rationale")
        report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
        report["fixture_failures"] = _verify_fixture_failures(report, fixture)
    elif kind == "chunked":
        report = verify_chunked_delivery(
            fixture["chunks"], fixture["body"],
            forbidden_additions=fixture.get("forbidden_additions", []),
            semantic_dimensions=fixture.get("semantic_dimensions"),
            registry_path=registry_path, profile=profile)
        report["kind"] = kind
        report["id"] = fid
        report["expected_decision"] = fixture["expected_decision"]
        report["meta"]["false_positive_rationale"] = fixture.get(
            "false_positive_rationale")
        report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
        report["fixture_failures"] = _verify_fixture_failures(report, fixture)
    else:
        envelope = deliver(
            source=fixture.get("source"),
            body=fixture.get("body"),
            medium=fixture.get("medium"),
            bind_source=fixture.get("bind_source", False),
            revision_plan=fixture.get("revision_plan"),
            required_facts=fixture.get("required_facts", []),
            required_terms=fixture.get("required_terms", []),
            forbidden_additions=fixture.get("forbidden_additions", []),
            semantic_dimensions=fixture.get("semantic_dimensions"),
            profile=profile, registry_path=registry_path)
        _tamper_envelope(envelope, fixture.get("tamper", "none"))
        report = check_envelope(envelope, registry_path=registry_path)
        report["kind"] = kind
        report["id"] = fid
        report["expected_decision"] = fixture["expected_decision"]
        report["meta"]["false_positive_rationale"] = fixture.get(
            "false_positive_rationale")
        report["meta"]["reviewer_notes"] = fixture.get("reviewer_notes")
        report["envelope"] = envelope
        report["fixture_failures"] = _envelope_fixture_failures(
            report, fixture, envelope)
    return report


def run_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the delivery-envelope fixture corpus."""
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
            "kind": report.get("kind", report["schema"]),
            "expected": report["expected_decision"],
            "got": report["decision"],
            "findings": report["fixture_failures"],
        } for report in failed],
        "schema_errors": schema_errors,
        "gate_pass": not schema_errors and not failed,
        "disclaimer": DISCLAIMER,
        "fixtures": reports,
    }


def load_json(path):
    return limits.load_json_file(path)


def _parse_dimensions(specs):
    dimensions = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError("--dimension must be name=mode")
        name, mode = spec.split("=", 1)
        if name not in drift.DIMENSION_ORDER \
                or mode not in drift.DIMENSION_MODES:
            raise ValueError("invalid dimension %s=%s" % (name, mode))
        dimensions[name] = mode
    return dimensions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        default="skills/antislop/evals/delivery-envelope-fixtures.json",
        help="Run the delivery-envelope fixture corpus instead of a command",
    )
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Print a compact JSON report")
    sub = parser.add_subparsers(dest="command")

    verify_p = sub.add_parser("verify", help="Verify a delivered body")
    verify_p.add_argument("--source-text", required=True)
    verify_p.add_argument("--body-text", required=True)
    verify_p.add_argument("--bind-source", action="store_true",
                          help="Bind a source record so its digest is "
                               "recorded")
    verify_p.add_argument("--profile", default="general")
    verify_p.add_argument("--fact", action="append", default=[],
                          help="Required fact (repeatable)")
    verify_p.add_argument("--require-term", action="append", default=[],
                          help="Required term (repeatable)")
    verify_p.add_argument("--forbid", action="append", default=[],
                          help="Forbidden addition (repeatable)")
    verify_p.add_argument("--dimension", action="append", default=[],
                          help="Semantic dimension as name=mode (repeatable)")

    envelope_p = sub.add_parser("envelope", help="Build a delivery envelope")
    envelope_p.add_argument("--source-text", required=True)
    envelope_p.add_argument("--body-text", required=True)
    envelope_p.add_argument("--medium", default=None,
                            help="Review medium for the bound report "
                                 "(default: no report)")
    envelope_p.add_argument("--bind-source", action="store_true")
    envelope_p.add_argument("--profile", default="general")
    envelope_p.add_argument("--fact", action="append", default=[])
    envelope_p.add_argument("--require-term", action="append", default=[])
    envelope_p.add_argument("--forbid", action="append", default=[])
    envelope_p.add_argument("--dimension", action="append", default=[])
    envelope_p.add_argument("--revision-plan", default=None,
                            help="Path to a revision-plan JSON file")

    check_p = sub.add_parser("check", help="Check a stored envelope")
    check_p.add_argument("--envelope", required=True,
                         help="Path to an envelope JSON file")

    args = parser.parse_args()

    registry = load_registry(args.registry)
    if args.expect_version and registry.get("version") != args.expect_version:
        print(json.dumps({
            "error": "registry version %s does not match --expect-version %s"
                     % (registry.get("version"), args.expect_version),
        }, indent=2))
        sys.exit(2)

    if args.command is None:
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

    profile = getattr(args, "profile", "general")
    if profile not in PROFILES:
        print(json.dumps({"error": "unknown profile '%s'. Valid: %s"
                                   % (profile, sorted(PROFILES))},
                         indent=2))
        sys.exit(2)

    try:
        dimensions = _parse_dimensions(getattr(args, "dimension", []))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)

    if args.command == "verify":
        source_record = (bind_source_record(args.source_text)
                         if args.bind_source else None)
        report = verify_delivery(
            args.source_text, args.body_text, source_record=source_record,
            required_facts=tuple(args.fact),
            required_terms=tuple(args.require_term),
            forbidden_additions=tuple(args.forbid),
            semantic_dimensions=dimensions or None,
            registry_path=args.registry, profile=profile)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0 if report["decision"] == "verified" else 1)

    if args.command == "envelope":
        revision_plan = None
        if args.revision_plan:
            if not os.path.exists(args.revision_plan):
                print(json.dumps({"error": "revision plan not found: %s"
                                           % args.revision_plan}, indent=2))
                sys.exit(2)
            revision_plan = load_json(args.revision_plan)
        envelope = deliver(
            source=args.source_text, body=args.body_text,
            medium=args.medium, bind_source=args.bind_source,
            revision_plan=revision_plan,
            required_facts=tuple(args.fact),
            required_terms=tuple(args.require_term),
            forbidden_additions=tuple(args.forbid),
            semantic_dimensions=dimensions or None,
            profile=profile, registry_path=args.registry)
        print(json.dumps(envelope, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        verification = envelope.get("verification_report") or {}
        sys.exit(0 if verification.get("decision") == "verified" else 1)

    if args.command == "check":
        if not os.path.exists(args.envelope):
            print(json.dumps({"error": "envelope file not found: %s"
                                       % args.envelope}, indent=2))
            sys.exit(2)
        envelope = load_json(args.envelope)
        report = check_envelope(envelope, registry_path=args.registry)
        print(json.dumps(report, indent=2 if not args.as_json else None,
                         sort_keys=args.as_json))
        sys.exit(0 if report["decision"] == "verified" else 1)

    parser.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
