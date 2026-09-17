#!/usr/bin/env python3
"""Slopkit-style semantic drift fixtures (issue #91).

A deterministic evaluation runner for source/candidate fixture pairs. Each
fixture declares a preservation contract: required facts and terms, forbidden
additions, protected spans, provenance labels, semantic dimensions, expected
finding spans, and a false-positive rationale. The runner reports missing,
added, changed, and unresolved items separately, and never lets a risk score
improvement hide a dropped mechanism, caveat, condition, or uncertainty marker.

Contracts are adapted from ehmo/slopkit at b33718b (MIT): the preservation
checker's protected tokens, the semantic-drift checker's marker groups and
risk classification, the false-positive tracker's leave-alone and light-edit
actions, and the evidence-bound provenance labels. Slopkit benchmark scores
are not imported as Antislop targets.

Antislop provenance statuses are fact, inference, placeholder, and unknown.
'unknown' marks missing or unclassified provenance; it is not an upstream
label. Detector observations may be recorded with tool, date, raw result, and
limitation, but never gate release or appear in the Formulaic Writing Risk
Score. Evaluation results never claim authorship or detector immunity.

Usage:
    python3 tools/drift.py --fixtures skills/antislop/evals/drift-fixtures.json
    python3 tools/drift.py --false-positive-corpus skills/antislop/evals/false-positive-corpus.json
    python3 tools/drift.py --fixtures ... --false-positive-corpus ...
    python3 tools/drift.py --help

Exit codes:
    0 -- all fixtures match their expected decisions and the corpus passes
    1 -- a fixture decision or corpus check failed
    2 -- usage or input error
"""

import argparse
import json
import os
import re
import sys

import limits
from registry import load_registry
import fidelity
import score as scoring

FACT = "fact"
INFERENCE = "inference"
PLACEHOLDER = "placeholder"
UNKNOWN = "unknown"
PROVENANCE_LABELS = {FACT, INFERENCE, PLACEHOLDER, UNKNOWN}

DIMENSION_ORDER = (
    "negation", "obligation", "scope", "temporal_condition",
    "causality", "uncertainty", "promise_intensity",
)
DIMENSION_MODES = {"preserve", "refuse"}

REVIEW_PROMPT_KEYS = ("sentence_load", "topic_swap", "summary_loss",
                      "information_gain")

FP_CATEGORIES = {
    "technical_term", "literal_metaphor", "necessary_repetition",
    "formal_register", "quotation", "author_supplied",
}
FP_ACTIONS = {"leave_alone", "light_copyedit"}
FP_MIN_ROWS = 6
FP_LIGHT_EDIT_GROWTH = 1.15

RISK_CLASSES = {"forbidden", "discouraged", "preferred", "structural",
                "integrity", "evaluation"}
DECISIONS = {"accept", "reject", "review"}
PROFILES = {"general", "technical"}

DISCLAIMER = (
    "Drift results report preservation and drift risk; they never prove "
    "AI authorship or detector immunity."
)
OBSERVATION_DISCLAIMER = (
    "Detector observations are advisory, dated evidence with stated "
    "limitations; they never gate release or appear in the Formulaic "
    "Writing Risk Score."
)

WORD_RE = re.compile(r"\b[\w'-]+\b")

MARKER_GROUPS = {
    "negation": [
        "no", "not", "never", "none", "nobody", "nothing", "nowhere",
        "without", "neither", "nor", "can't", "cannot", "won't", "wouldn't",
        "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't", "weren't",
        "shouldn't", "couldn't", "mustn't", "hasn't", "haven't", "hadn't",
    ],
    "obligation": [
        "must", "may", "can", "should", "shall", "required", "requires",
        "requiring", "needs", "needed", "need to", "have to", "has to",
        "allowed", "permitted", "mandatory", "optional", "must not",
    ],
    "scope": [
        "only", "all", "every", "each", "any", "none", "except",
        "read-only", "full", "restricted", "limited", "exclusive",
        "up to", "at most", "at least", "no more than", "no less than",
        "under", "over", "within", "exactly",
    ],
    "temporal_condition": [
        "if", "unless", "when", "whenever", "before", "after", "until",
        "provided that", "as long as", "given that", "assuming", "once",
        "expires", "expired", "expiration", "expiry",
    ],
    "causality": [
        "because", "caused", "causes", "cause", "causing", "due to",
        "therefore", "thus", "hence", "consequently", "leads to", "led to",
        "results in", "results from", "so that", "means",
    ],
    "uncertainty": [
        "might", "could", "may", "likely", "possibly", "perhaps", "maybe",
        "probably", "suggests", "suggested", "appears", "appeared", "seems",
        "seemed", "reportedly", "presumably", "estimated", "claims",
        "claimed", "not proven", "unverified", "tentatively", "pending",
    ],
    "promise_intensity": [
        "guarantee", "guaranteed", "ensures", "ensure", "promises",
        "promise", "always", "seamless", "world-class", "best-in-class",
        "definitely", "absolutely", "perfect",
    ],
}


def words(text):
    return [word.lower() for word in WORD_RE.findall(text)]


def word_count(text):
    return len(WORD_RE.findall(text))


def _variants(word):
    variants = {word}
    if word.isalpha() and len(word) > 2:
        variants.add(word + "s")
        variants.add(word + "ed")
        variants.add(word + "ing")
        if word.endswith("e"):
            variants.add(word + "d")
        if word.endswith("y"):
            variants.add(word[:-1] + "ies")
    return variants


def fact_pattern(fact):
    """Word-stable pattern for a required fact, with inflection on the last
    word, matching Slopkit's exact-fact matcher."""
    fact_words = words(fact)
    if not fact_words:
        return None
    tokens = [re.escape(word) for word in fact_words[:-1]]
    final = "|".join(re.escape(variant) for variant in
                     sorted(_variants(fact_words[-1]), key=len, reverse=True))
    tokens.append("(?:%s)" % final)
    pattern = r"[^\w]+".join(tokens)
    return re.compile(r"(?<!\w)" + pattern + r"(?!\w)", re.IGNORECASE)


def contains_fact(text, fact):
    pattern = fact_pattern(fact)
    if pattern is None:
        return False
    return pattern.search(text) is not None


def extract_markers(text):
    """Slopkit-style marker groups present in text, as term lists."""
    found = {}
    for dimension, terms in MARKER_GROUPS.items():
        hits = [term for term in terms
                if re.search(r"\b" + re.escape(term) + r"\b", text,
                             re.IGNORECASE)]
        if hits:
            found[dimension] = sorted(hits)
    return found


def compare_marker_groups(source_markers, candidate_markers):
    """Group-level diff between source and candidate marker sets."""
    source_groups = set(source_markers)
    candidate_groups = set(candidate_markers)
    missing_groups = sorted(source_groups - candidate_groups)
    added_groups = sorted(candidate_groups - source_groups)
    changed_groups = {}
    for group in sorted(source_groups & candidate_groups):
        missing_terms = sorted(set(source_markers[group]) -
                               set(candidate_markers[group]))
        added_terms = sorted(set(candidate_markers[group]) -
                             set(source_markers[group]))
        if missing_terms or added_terms:
            changed_groups[group] = {
                "missing_terms": missing_terms,
                "added_terms": added_terms,
            }
    return {"missing_groups": missing_groups,
            "added_groups": added_groups,
            "changed_groups": changed_groups}


def rule_risk_class(rule):
    return rule.get("semantic_type", "forbidden")


def _str_list(value, where):
    if not isinstance(value, list):
        return ["%s must be a list" % where]
    return ["%s[%d] must be a non-empty string" % (where, i)
            for i, item in enumerate(value)
            if not isinstance(item, str) or not item.strip()]


def _validate_observations(observations, where):
    errors = []
    if not isinstance(observations, list):
        return ["%s must be a list" % where]
    for i, observation in enumerate(observations):
        if not isinstance(observation, dict):
            errors.append("%s[%d] must be an object" % (where, i))
            continue
        for key in ("tool", "date", "result", "limitation"):
            value = observation.get(key)
            if value is not None and (not isinstance(value, str)
                                      or not value.strip()):
                errors.append("%s[%d].%s must be a non-empty string"
                              % (where, i, key))
    return errors


def validate_drift_fixture(fixture, seen_ids):
    """Schema-validate one drift fixture. Returns a list of error strings."""
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

    for field in ("source", "candidate"):
        value = fixture.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append("%s: '%s' must be a non-empty string"
                          % (where, field))

    expected = fixture.get("expected_decision")
    if expected not in DECISIONS:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(sorted(DECISIONS))))

    profile = fixture.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(sorted(PROFILES))))

    errors.extend(_str_list(fixture.get("required_facts", []),
                            "%s.required_facts" % where))
    errors.extend(_str_list(fixture.get("required_terms", []),
                            "%s.required_terms" % where))
    errors.extend(_str_list(fixture.get("forbidden_additions", []),
                            "%s.forbidden_additions" % where))

    spans = fixture.get("protected_spans", [])
    if not isinstance(spans, list):
        errors.append("%s: protected_spans must be a list" % where)
    else:
        for i, span in enumerate(spans):
            if not isinstance(span, dict):
                errors.append("%s: protected_spans[%d] must be an object"
                              % (where, i))
                continue
            if span.get("category") not in fidelity.PROTECTED_ORDER:
                errors.append("%s: protected_spans[%d] has unknown category"
                              % (where, i))
            if not (isinstance(span.get("start"), int)
                    and isinstance(span.get("end"), int)
                    and span["start"] >= 0 and span["end"] > span["start"]):
                errors.append("%s: protected_spans[%d] needs start and end "
                              "ints with end greater than start" % (where, i))

    provenance = fixture.get("provenance", [])
    if not isinstance(provenance, list):
        errors.append("%s: provenance must be a list" % where)
    else:
        for i, item in enumerate(provenance):
            if not isinstance(item, dict):
                errors.append("%s: provenance[%d] must be an object"
                              % (where, i))
                continue
            if not (isinstance(item.get("text"), str) and item["text"].strip()):
                errors.append("%s: provenance[%d] needs a non-empty 'text'"
                              % (where, i))
            if item.get("label") not in PROVENANCE_LABELS:
                errors.append("%s: provenance[%d] label must be one of %s"
                              % (where, i, ", ".join(sorted(PROVENANCE_LABELS))))
            hedge = item.get("hedge")
            if hedge is not None and (not isinstance(hedge, str)
                                      or not hedge.strip()):
                errors.append("%s: provenance[%d].hedge must be a non-empty "
                              "string" % (where, i))

    dimensions = fixture.get("semantic_dimensions", {})
    if not isinstance(dimensions, dict):
        errors.append("%s: semantic_dimensions must be an object" % where)
    else:
        for dimension, mode in dimensions.items():
            if dimension not in DIMENSION_ORDER:
                errors.append("%s: unknown semantic dimension '%s'"
                              % (where, dimension))
            if mode not in DIMENSION_MODES:
                errors.append("%s: dimension '%s' mode must be preserve or "
                              "refuse" % (where, dimension))

    expected_findings = fixture.get("expected_findings", [])
    if not isinstance(expected_findings, list):
        errors.append("%s: expected_findings must be a list" % where)
    else:
        for i, finding in enumerate(expected_findings):
            if not isinstance(finding, dict):
                errors.append("%s: expected_findings[%d] must be an object"
                              % (where, i))
                continue
            if finding.get("target") not in ("source", "candidate"):
                errors.append("%s: expected_findings[%d].target must be "
                              "source or candidate" % (where, i))
            if not (isinstance(finding.get("rule_id"), str)
                    and finding["rule_id"].strip()):
                errors.append("%s: expected_findings[%d] needs a non-empty "
                              "'rule_id'" % (where, i))
            span = finding.get("span")
            if not (isinstance(span, list) and len(span) == 2
                    and isinstance(span[0], int) and isinstance(span[1], int)
                    and span[1] > span[0]):
                errors.append("%s: expected_findings[%d].span needs a "
                              "[start, end] int pair" % (where, i))
            risk_class = finding.get("risk_class")
            if risk_class is not None and risk_class not in RISK_CLASSES:
                errors.append("%s: expected_findings[%d].risk_class must be "
                              "one of %s"
                              % (where, i, ", ".join(sorted(RISK_CLASSES))))

    absent_findings = fixture.get("absent_findings", [])
    if not isinstance(absent_findings, list):
        errors.append("%s: absent_findings must be a list" % where)
    else:
        for i, finding in enumerate(absent_findings):
            if not isinstance(finding, dict):
                errors.append("%s: absent_findings[%d] must be an object"
                              % (where, i))
                continue
            if finding.get("target") not in ("source", "candidate"):
                errors.append("%s: absent_findings[%d].target must be source "
                              "or candidate" % (where, i))
            if not (isinstance(finding.get("rule_id"), str)
                    and finding["rule_id"].strip()):
                errors.append("%s: absent_findings[%d] needs a non-empty "
                              "'rule_id'" % (where, i))

    rationale = fixture.get("false_positive_rationale")
    if rationale is not None and (not isinstance(rationale, str)
                                  or not rationale.strip()):
        errors.append("%s: false_positive_rationale must be a non-empty "
                      "string" % where)

    prompts = fixture.get("review_prompts", {})
    if not isinstance(prompts, dict):
        errors.append("%s: review_prompts must be an object" % where)
    else:
        for key, value in prompts.items():
            if key not in REVIEW_PROMPT_KEYS:
                errors.append("%s: unknown review prompt '%s'" % (where, key))
            if not (isinstance(value, str) and value.strip()):
                errors.append("%s: review_prompts.%s must be a non-empty "
                              "string" % (where, key))

    notes = fixture.get("reviewer_notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append("%s: reviewer_notes must be a non-empty string" % where)

    errors.extend(_validate_observations(
        fixture.get("detector_observations", []),
        "%s.detector_observations" % where))
    return errors


def validate_false_positive_entry(entry, seen_ids):
    """Schema-validate one false-positive corpus entry."""
    errors = []
    if not isinstance(entry, dict):
        return ["false-positive entry must be a JSON object"]
    eid = entry.get("id")
    if not isinstance(eid, str) or not eid.strip():
        errors.append("false-positive entry missing non-empty string 'id'")
    else:
        if eid in seen_ids:
            errors.append("duplicate false-positive entry id '%s'" % eid)
        seen_ids.add(eid)

    where = "entry '%s'" % (eid if eid else "?")

    if entry.get("category") not in FP_CATEGORIES:
        errors.append("%s: category must be one of %s"
                      % (where, ", ".join(sorted(FP_CATEGORIES))))
    if entry.get("expected_action") not in FP_ACTIONS:
        errors.append("%s: expected_action must be one of %s"
                      % (where, ", ".join(sorted(FP_ACTIONS))))
    for field in ("source", "candidate", "why_keep"):
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append("%s: '%s' must be a non-empty string"
                          % (where, field))
    profile = entry.get("profile", "general")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(sorted(PROFILES))))
    errors.extend(_str_list(entry.get("required_facts", []),
                            "%s.required_facts" % where))
    errors.extend(_str_list(entry.get("required_terms", []),
                            "%s.required_terms" % where))
    errors.extend(_str_list(entry.get("forbidden_additions", []),
                            "%s.forbidden_additions" % where))
    errors.extend(_validate_observations(
        entry.get("detector_observations", []),
        "%s.detector_observations" % where))
    return errors


def _target_text(fixture, target, source, candidate):
    return source if target == "source" else candidate


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


def check_findings(fixture, registry, source, candidate, profile):
    """Expected and absent finding checks at exact character offsets."""
    by_id = {rule["id"]: rule for rule in registry.get("rules", [])}
    results = {"expected": [], "absent": [], "mismatches": []}

    for expected in fixture.get("expected_findings", []):
        target = expected.get("target", "candidate")
        text = _target_text(fixture, target, source, candidate)
        span = list(expected["span"])
        rule_id = expected["rule_id"]
        rule = by_id.get(rule_id)
        scored = _score_risk(text, registry, profile)
        matches = [f for f in scored["findings"]
                   if f["rule_id"] == rule_id and f["span"] == span
                   and f["primary"]]
        risk_class = expected.get("risk_class")
        risk_ok = risk_class is None or (
            rule is not None and rule_risk_class(rule) == risk_class)
        entry = {"target": target, "rule_id": rule_id, "span": span,
                 "present": bool(matches), "risk_class": risk_class,
                 "risk_ok": risk_ok}
        results["expected"].append(entry)
        if not matches:
            results["mismatches"].append({
                "kind": "expected_finding_missing",
                "target": target, "rule_id": rule_id, "span": span,
            })
        elif not risk_ok:
            results["mismatches"].append({
                "kind": "expected_finding_risk_class",
                "target": target, "rule_id": rule_id, "span": span,
            })

    for absent in fixture.get("absent_findings", []):
        target = absent.get("target", "candidate")
        text = _target_text(fixture, target, source, candidate)
        rule_id = absent["rule_id"]
        scored = _score_risk(text, registry, profile)
        present = any(f["rule_id"] == rule_id and f["primary"]
                      for f in scored["findings"])
        entry = {"target": target, "rule_id": rule_id, "present": present}
        results["absent"].append(entry)
        if present:
            results["mismatches"].append({
                "kind": "absent_finding_present",
                "target": target, "rule_id": rule_id,
            })
    return results


def check_protected_spans_offsets(fixture, source):
    """Declared protected spans must match the extractor's exact offsets."""
    extracted = fidelity.extract_anchors(source, ())["protected_spans"]
    drift = []
    for expected in fixture.get("protected_spans", []):
        match = any(span["category"] == expected["category"]
                    and span["start"] == expected["start"]
                    and span["end"] == expected["end"]
                    for span in extracted)
        if not match:
            drift.append({
                "category": expected["category"],
                "start": expected["start"],
                "end": expected["end"],
            })
    return drift


def check_provenance(fixture, candidate):
    """Provenance labels must survive the rewrite or stay unresolved."""
    items = {"fact": [], "inference": [], "placeholder": [], "unknown": []}
    violations = []
    unresolved = []
    for item in fixture.get("provenance", []):
        text = item["text"]
        label = item.get("label")
        hedge = item.get("hedge")
        entry = {"text": text, "state": "kept"}
        if label == FACT:
            if not contains_fact(candidate, text):
                entry["state"] = "missing"
                violations.append("source fact '%s' is missing" % text)
                items["fact"].append(entry)
            else:
                items["fact"].append(entry)
        elif label == INFERENCE:
            if not contains_fact(candidate, text):
                entry["state"] = "missing"
                violations.append("source inference '%s' is missing" % text)
            elif hedge and not re.search(r"\b" + re.escape(hedge) + r"\b",
                                         candidate, re.IGNORECASE):
                entry["state"] = "hedge_dropped"
                violations.append(
                    "inference '%s' lost its hedge '%s' and now reads as "
                    "fact" % (text, hedge))
            items["inference"].append(entry)
        elif label == PLACEHOLDER:
            if contains_fact(candidate, text):
                entry["state"] = "kept_unresolved"
            else:
                entry["state"] = "removed_unresolved"
            items["placeholder"].append(entry)
            unresolved.append({
                "kind": "placeholder_%s" % entry["state"].split("_")[0],
                "label": PLACEHOLDER, "text": text,
            })
        elif label == UNKNOWN:
            if contains_fact(candidate, text):
                entry["state"] = "kept_unresolved"
            else:
                entry["state"] = "removed_unresolved"
            items["unknown"].append(entry)
            unresolved.append({
                "kind": "unknown_%s" % entry["state"].split("_")[0],
                "label": UNKNOWN, "text": text,
            })
    return {"items": items, "violations": violations,
            "unresolved": unresolved}


def check_semantic_dimensions(fixture, source, candidate):
    """Marker-group diff, enforced only for the declared dimensions."""
    source_markers = extract_markers(source)
    candidate_markers = extract_markers(candidate)
    diff = compare_marker_groups(source_markers, candidate_markers)
    declared = fixture.get("semantic_dimensions", {})
    verdicts = {}
    violations = []
    for dimension, mode in declared.items():
        verdict = "ok"
        if mode == "preserve":
            if dimension in diff["missing_groups"]:
                verdict = "missing_group"
                violations.append(
                    "dimension '%s' markers (%s) were dropped"
                    % (dimension, ", ".join(source_markers[dimension])))
            elif dimension in diff["changed_groups"]:
                change = diff["changed_groups"][dimension]
                verdict = "changed_terms"
                violations.append(
                    "dimension '%s' markers changed (missing %s, added %s)"
                    % (dimension,
                       ", ".join(change["missing_terms"]) or "none",
                       ", ".join(change["added_terms"]) or "none"))
        elif mode == "refuse":
            if dimension in diff["added_groups"]:
                verdict = "added_group"
                violations.append(
                    "dimension '%s' markers (%s) were added and must be "
                    "refused" % (dimension,
                                 ", ".join(candidate_markers[dimension])))
        verdicts[dimension] = verdict
    return {"source_markers": source_markers,
            "candidate_markers": candidate_markers,
            "missing_groups": diff["missing_groups"],
            "added_groups": diff["added_groups"],
            "changed_groups": diff["changed_groups"],
            "verdicts": verdicts,
            "violations": violations}


def run_drift_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one drift fixture against its preservation contract."""
    fid = fixture["id"]
    profile = fixture.get("profile", "general")
    source = fixture["source"]
    candidate = fixture["candidate"]
    required_terms = fixture.get("required_terms", [])

    items = {"missing": [], "added": [], "changed": [], "unresolved": []}
    reasons = []

    for fact in fixture.get("required_facts", []):
        if not contains_fact(candidate, fact):
            items["missing"].append({"kind": "required_fact", "value": fact})
            reasons.append("required fact '%s' is missing" % fact)

    for term in fixture.get("forbidden_additions", []):
        if contains_fact(candidate, term):
            items["added"].append({"kind": "forbidden_addition", "value": term})
            reasons.append("forbidden addition '%s' is present" % term)

    source_terms = {span["value"].lower() for span in fidelity.extract_anchors(
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
        items["added"].append({"kind": "required_term", "value": term})

    fidelity_report = fidelity.check_fidelity(
        source, candidate,
        required_terms=tuple(required_terms),
        authorized_changes=(),
        hot_zones=[],
        churn_limit=None,
        registry_path=registry_path,
        profile=profile,
    )
    preservation = fidelity_report["preservation"]
    for failure in preservation["hard_failures"]:
        kind = failure["kind"]
        category = failure.get("category", "anchor")
        source_value = failure.get("source")
        candidate_value = failure.get("candidate")
        if kind == "protected_span_changed":
            items["changed"].append({"kind": "protected_span_changed",
                                     "category": category,
                                     "source": source_value,
                                     "candidate": candidate_value})
            reasons.append("protected %s changed from '%s' to '%s'"
                           % (category, source_value, candidate_value))
        elif kind == "protected_span_removed":
            items["missing"].append({"kind": "protected_span_removed",
                                     "category": category,
                                     "source": source_value})
            reasons.append("protected %s '%s' is missing"
                           % (category, source_value))
        else:
            items["changed"].append({"kind": kind, "category": category,
                                     "source": source_value,
                                     "candidate": candidate_value})
            reasons.append("%s in %s" % (kind, category))

    span_drift = check_protected_spans_offsets(fixture, source)
    for drift in span_drift:
        items["changed"].append({"kind": "protected_span_offset",
                                 "category": drift["category"],
                                 "start": drift["start"], "end": drift["end"]})
        reasons.append("declared protected %s span [%d, %d] does not match "
                       "the extractor"
                       % (drift["category"], drift["start"], drift["end"]))

    provenance = check_provenance(fixture, candidate)
    items["unresolved"].extend(provenance["unresolved"])
    for item in provenance["items"]["fact"]:
        if item["state"] == "missing":
            items["missing"].append({"kind": "provenance_fact",
                                     "value": item["text"]})
    for item in provenance["items"]["inference"]:
        if item["state"] == "missing":
            items["missing"].append({"kind": "provenance_inference",
                                     "value": item["text"]})
        elif item["state"] == "hedge_dropped":
            items["changed"].append({"kind": "provenance_hedge_dropped",
                                     "value": item["text"]})
    for violation in provenance["violations"]:
        reasons.append(violation)

    dimensions = check_semantic_dimensions(fixture, source, candidate)
    for violation in dimensions["violations"]:
        reasons.append(violation)

    findings = check_findings(fixture, registry, source, candidate, profile)
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

    prompts = fixture.get("review_prompts", {})
    review_items = [{"kind": key, "prompt": value}
                    for key, value in sorted(prompts.items())]

    source_risk = _score_risk(source, registry, profile)
    candidate_risk = _score_risk(candidate, registry, profile)
    delta = None
    improved = False
    if source_risk["score"] is not None and candidate_risk["score"] is not None:
        delta = candidate_risk["score"] - source_risk["score"]
        improved = delta > 0

    if reasons:
        decision = "reject"
    elif review_items:
        decision = "review"
    else:
        decision = "accept"

    return {
        "id": fid,
        "interface": "antislop.drift",
        "schema": "drift-fixture-report-1",
        "version": registry.get("version", "unknown"),
        "profile": profile,
        "expected_decision": fixture["expected_decision"],
        "decision": decision,
        "reasons": reasons,
        "items": items,
        "facts": {
            "required": fixture.get("required_facts", []),
            "missing": [item["value"] for item in items["missing"]
                        if item["kind"] == "required_fact"],
        },
        "forbidden_additions": [
            item["value"] for item in items["added"]
            if item["kind"] == "forbidden_addition"
        ],
        "protected_spans": {
            "changed": [item for item in items["changed"]
                        if item["kind"] == "protected_span_changed"],
            "removed": [item for item in items["missing"]
                        if item["kind"] == "protected_span_removed"],
            "offset_drift": span_drift,
            "extracted_total": len(
                fidelity.extract_anchors(source, ())["protected_spans"]),
        },
        "provenance": provenance,
        "semantic_dimensions": dimensions,
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
            "false_positive_rationale": fixture.get("false_positive_rationale"),
            "reviewer_notes": fixture.get("reviewer_notes"),
            "detector_observations": fixture.get("detector_observations", []),
        },
    }


def run_drift_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate a drift fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_drift_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "interface": "antislop.drift",
            "schema": "drift-report-1",
            "version": registry.get("version", "unknown"),
            "fixture_count": len(fixtures),
            "passed": 0,
            "failed": len(fixtures),
            "failing_ids": [fixture.get("id", "?") for fixture in fixtures],
            "schema_errors": schema_errors,
            "disclaimer": DISCLAIMER,
            "fixtures": [],
        }

    reports = [run_drift_fixture(fixture, registry,
                                registry_path=registry_path)
               for fixture in fixtures]
    failed = [report for report in reports
              if report["decision"] != report["expected_decision"]]
    return {
        "interface": "antislop.drift",
        "schema": "drift-report-1",
        "version": registry.get("version", "unknown"),
        "fixture_count": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "failures": [{
            "id": report["id"],
            "expected": report["expected_decision"],
            "got": report["decision"],
            "reasons": report["reasons"],
        } for report in failed],
        "schema_errors": schema_errors,
        "disclaimer": DISCLAIMER,
        "fixtures": reports,
    }


def run_false_positive_entry(entry, registry, registry_path="rules.json"):
    """Check one false-positive corpus entry for restraint."""
    profile = entry.get("profile", "general")
    source = entry["source"]
    candidate = entry["candidate"]
    action = entry["expected_action"]
    required_terms = entry.get("required_terms", [])

    failures = []
    if action == "leave_alone" and source != candidate:
        failures.append("changed_leave_alone_text")

    growth = word_count(candidate) / max(1, word_count(source))
    if action == "light_copyedit" and growth > FP_LIGHT_EDIT_GROWTH:
        failures.append("light_edit_grew_too_much")

    added_forbidden = [term for term in entry.get("forbidden_additions", [])
                       if contains_fact(candidate, term)]
    if added_forbidden:
        failures.append("forbidden_addition")

    missing_facts = [fact for fact in entry.get("required_facts", [])
                     if not contains_fact(candidate, fact)]
    if missing_facts:
        failures.append("critical_missing_facts")

    source_terms = {span["value"].lower() for span in fidelity.extract_anchors(
        source, required_terms)["protected_spans"]
        if span["category"] == "required_term"}
    candidate_terms = {span["value"].lower()
                       for span in fidelity.extract_anchors(
                           candidate, required_terms)["protected_spans"]
                       if span["category"] == "required_term"}
    if source_terms - candidate_terms:
        failures.append("missing_required_terms")

    fidelity_report = fidelity.check_fidelity(
        source, candidate,
        required_terms=tuple(required_terms),
        hot_zones=[],
        churn_limit=None,
        registry_path=registry_path,
        profile=profile,
    )
    if fidelity_report["preservation"]["hard_failures"]:
        failures.append("protected_content_changed")

    source_risk = _score_risk(source, registry, profile)
    candidate_risk = _score_risk(candidate, registry, profile)
    return {
        "id": entry["id"],
        "interface": "antislop.drift",
        "schema": "false-positive-entry-report-1",
        "version": registry.get("version", "unknown"),
        "category": entry["category"],
        "profile": profile,
        "expected_action": action,
        "why_keep": entry.get("why_keep", ""),
        "input_words": word_count(source),
        "output_words": word_count(candidate),
        "growth_ratio": round(growth, 3),
        "added_forbidden": added_forbidden,
        "missing_facts": missing_facts,
        "failures": failures,
        "passed": not failures,
        "risk": {
            "source_score": source_risk["score"],
            "candidate_score": candidate_risk["score"],
            "advisory": True,
            "authorship_evidence": False,
            "disclaimer": OBSERVATION_DISCLAIMER,
        },
        "meta": {
            "disclaimer": DISCLAIMER,
            "detector_observations": entry.get("detector_observations", []),
        },
    }


def run_false_positive_corpus(entries, registry, registry_path="rules.json",
                              required_categories=FP_CATEGORIES):
    """Validate and evaluate the false-positive corpus."""
    schema_errors = []
    seen_ids = set()
    for entry in entries:
        schema_errors.extend(validate_false_positive_entry(entry, seen_ids))

    if schema_errors:
        return {
            "interface": "antislop.drift",
            "schema": "false-positive-corpus-report-1",
            "version": registry.get("version", "unknown"),
            "entry_count": len(entries),
            "passed": 0,
            "failed": len(entries),
            "failing_ids": [entry.get("id", "?") for entry in entries],
            "schema_errors": schema_errors,
            "corpus_failures": ["schema_errors"],
            "disclaimer": DISCLAIMER,
            "rows": [],
        }

    rows = [run_false_positive_entry(entry, registry,
                                    registry_path=registry_path)
            for entry in entries]
    failing = [row for row in rows if row["failures"]]
    categories = {row["category"] for row in rows}
    actions = {row["expected_action"] for row in rows}
    corpus_failures = []
    if len(rows) < FP_MIN_ROWS:
        corpus_failures.append("too_few_rows")
    missing_categories = required_categories - categories
    if missing_categories:
        corpus_failures.append("missing_categories: " +
                               ", ".join(sorted(missing_categories)))
    if "leave_alone" not in actions or "light_copyedit" not in actions:
        corpus_failures.append("missing_action_mix")
    if failing:
        corpus_failures.append("row_failures")

    return {
        "interface": "antislop.drift",
        "schema": "false-positive-corpus-report-1",
        "version": registry.get("version", "unknown"),
        "entry_count": len(rows),
        "passed": len(rows) - len(failing),
        "failed": len(failing),
        "failing_ids": [row["id"] for row in failing],
        "failures": [{
            "id": row["id"], "category": row["category"],
            "entry_failures": row["failures"],
        } for row in failing],
        "corpus_failures": corpus_failures,
        "schema_errors": schema_errors,
        "disclaimer": DISCLAIMER,
        "rows": rows,
    }


def load_json(path):
    return limits.load_json_file(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        default="skills/antislop/evals/drift-fixtures.json",
        help="Path to the drift fixture corpus (default: repo path)",
    )
    parser.add_argument(
        "--false-positive-corpus",
        default="skills/antislop/evals/false-positive-corpus.json",
        help="Path to the false-positive corpus (default: repo path)",
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

    report = {
        "interface": "antislop.drift",
        "version": registry.get("version", "unknown"),
        "disclaimer": DISCLAIMER,
    }
    failures = []

    fixtures_path = args.fixtures
    fp_path = args.false_positive_corpus

    if os.path.exists(fixtures_path):
        fixtures = load_json(fixtures_path)
        fixture_report = run_drift_corpus(fixtures.get("evals", fixtures),
                                          registry)
        report["drift_fixtures"] = fixture_report
        if fixture_report["schema_errors"] or fixture_report["failures"]:
            failures.append("drift_fixtures")
    else:
        report["drift_fixtures"] = {"skipped": fixtures_path}

    if os.path.exists(fp_path):
        fp_data = load_json(fp_path)
        fp_report = run_false_positive_corpus(fp_data.get("evals", fp_data),
                                              registry)
        report["false_positive_corpus"] = fp_report
        if fp_report["schema_errors"] or fp_report["failures"]:
            failures.append("false_positive_corpus")
    else:
        report["false_positive_corpus"] = {"skipped": fp_path}

    report["gate_pass"] = not failures
    print(json.dumps(report, indent=2 if not args.as_json else None,
                     sort_keys=args.as_json))
    sys.exit(0 if report["gate_pass"] else 1)


if __name__ == "__main__":
    main()
