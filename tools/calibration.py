#!/usr/bin/env python3
"""Labeled calibration harness (issue #89).

A deterministic evaluation command that runs frozen labeled fixtures against
a baseline implementation and a candidate implementation. Each fixture
declares its profile, genre, locale, source, and label provenance, plus four
kinds of labels: expected findings, clean spans, preservation obligations,
and forbidden additions. Numeric targets and ranked findings drive calibration
metrics.

The report records per-category recall, false-positive rate, exact-span
agreement, preservation failures, integrity failures, score delta, score
stability, per-profile results, mean absolute error for numeric targets, and
rank correlation where ordering is meaningful. Missing labels stay missing and
never become zero: a category with no labeled expected findings reports an
explicit unlabeled state instead of a zero recall.

Experiment configuration and results are stored as reviewable JSON artifacts.
The experiment requires a non-empty holdout set and an explicit score
direction. Holdout fixtures are never used to tune thresholds: thresholds are
static configuration values, never derived from fixture data. The harness can
fail on configured false-positive, recall, or preservation regressions.

The reference implementation reuses score.py's matchers and overlap handling,
structural.py's detectors, fidelity.py's preservation gate, and drift.py's
fact matching. No external model or detector claim is involved.

Usage:
    python3 tools/calibration.py --experiment-config skills/antislop/evals/calibration-experiment.json
    python3 tools/calibration.py --experiment-config ... --output results.json
    python3 tools/calibration.py --help

Exit codes:
    0 -- experiment ran and the gate passed
    1 -- experiment ran and the gate failed
    2 -- usage, configuration, or input error
"""

import argparse
import hashlib
import json
import os
import re
import sys

import limits
from registry import load_registry, filter_rules_by_profile
import score as scoring
import structural
import fidelity
import drift

INTERFACE = "antislop.calibration"
EXPERIMENT_REPORT_SCHEMA = "calibration-experiment-report-1"
EXPERIMENT_CONFIG_SCHEMA = "calibration-experiment-1"
FIXTURE_SCHEMA = "calibration-fixtures-1"

PROFILES = ("general", "technical")
GENRES = ("argument", "explanation", "evocation", "narrative", "guide",
          "reference", "message")
SCORE_DIRECTIONS = ("higher_is_better", "lower_is_better")
TARGETS = ("text", "source", "candidate")
PRESERVATION_KINDS = ("fact", "term")

VALID_SEMANTIC_TYPES = {"forbidden", "discouraged", "preferred", "structural",
                        "integrity", "evaluation"}

DISCLAIMER = (
    "Calibration results compare detector behavior on labeled fixtures; they "
    "never prove AI authorship or detector immunity."
)

ALL_CATEGORIES = ("vocabulary", "phrase", "filler", "formatting", "chatbot",
                  "structural", "integrity", "mechanism", "evaluation",
                  "preferred")


def _str_list(value, where):
    if not isinstance(value, list):
        return ["%s must be a list" % where]
    return ["%s[%d] must be a non-empty string" % (where, i)
            for i, item in enumerate(value)
            if not isinstance(item, str) or not item.strip()]


def _span_errors(span, where):
    if not (isinstance(span, list) and len(span) == 2
            and isinstance(span[0], int) and isinstance(span[1], int)
            and span[1] > span[0]):
        return ["%s needs a [start, end] int pair" % where]
    return []


def validate_calibration_fixture(fixture, seen_ids):
    """Schema-validate one calibration fixture. Returns a list of errors."""
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

    profile = fixture.get("profile")
    if profile not in PROFILES:
        errors.append("%s: profile must be one of %s"
                      % (where, ", ".join(PROFILES)))
    genre = fixture.get("genre")
    if genre not in GENRES:
        errors.append("%s: genre must be one of %s"
                      % (where, ", ".join(GENRES)))
    for field in ("locale", "source", "label_provenance"):
        value = fixture.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append("%s: '%s' must be a non-empty string" % (where, field))

    holdout = fixture.get("holdout")
    if not isinstance(holdout, bool):
        errors.append("%s: 'holdout' must be a boolean" % where)

    has_text = isinstance(fixture.get("text"), str) and fixture["text"].strip()
    has_source = (isinstance(fixture.get("source_text"), str)
                  and fixture["source_text"].strip())
    has_candidate = (isinstance(fixture.get("candidate_text"), str)
                     and fixture["candidate_text"].strip())
    if not has_text and not (has_source and has_candidate):
        errors.append("%s: needs 'text' or a 'source_text'/'candidate_text' "
                      "pair" % where)
    allowed_targets = TARGETS if has_source else ("text",)
    for label_key, where_key in (("expected_findings", "expected_findings"),
                                 ("clean_spans", "clean_spans"),
                                 ("ranked_findings", "ranked_findings")):
        for i, label in enumerate(fixture.get(label_key, [])):
            if isinstance(label, dict) and label.get("target") not in allowed_targets:
                errors.append("%s: %s[%d].target must be one of %s"
                              % (where, where_key, i,
                                 ", ".join(allowed_targets)))

    expected_findings = fixture.get("expected_findings", [])
    if not isinstance(expected_findings, list):
        errors.append("%s: expected_findings must be a list" % where)
    else:
        for i, finding in enumerate(expected_findings):
            if not isinstance(finding, dict):
                errors.append("%s: expected_findings[%d] must be an object"
                              % (where, i))
                continue
            if finding.get("target") not in TARGETS:
                errors.append("%s: expected_findings[%d].target must be one "
                              "of %s" % (where, i, ", ".join(TARGETS)))
            if not (isinstance(finding.get("rule_id"), str)
                    and finding["rule_id"].strip()):
                errors.append("%s: expected_findings[%d] needs a non-empty "
                              "'rule_id'" % (where, i))
            if not (isinstance(finding.get("category"), str)
                    and finding["category"].strip()):
                errors.append("%s: expected_findings[%d] needs a non-empty "
                              "'category'" % (where, i))
            errors.extend(_span_errors(finding.get("span"),
                                       "%s: expected_findings[%d].span"
                                       % (where, i)))

    clean_spans = fixture.get("clean_spans", [])
    if not isinstance(clean_spans, list):
        errors.append("%s: clean_spans must be a list" % where)
    else:
        for i, span in enumerate(clean_spans):
            if not isinstance(span, dict):
                errors.append("%s: clean_spans[%d] must be an object"
                              % (where, i))
                continue
            if span.get("target") not in TARGETS:
                errors.append("%s: clean_spans[%d].target must be one of %s"
                              % (where, i, ", ".join(TARGETS)))
            errors.extend(_span_errors(span.get("span"),
                                       "%s: clean_spans[%d].span"
                                       % (where, i)))
            if not (isinstance(span.get("note"), str) and span["note"].strip()):
                errors.append("%s: clean_spans[%d] needs a non-empty 'note'"
                              % (where, i))
            category = span.get("category")
            if category is not None and (
                    not isinstance(category, str) or not category.strip()):
                errors.append("%s: clean_spans[%d].category must be a "
                              "non-empty string when present" % (where, i))

    ranked = fixture.get("ranked_findings", [])
    if not isinstance(ranked, list):
        errors.append("%s: ranked_findings must be a list" % where)
    else:
        for i, item in enumerate(ranked):
            if not isinstance(item, dict):
                errors.append("%s: ranked_findings[%d] must be an object"
                              % (where, i))
                continue
            if item.get("target") not in TARGETS:
                errors.append("%s: ranked_findings[%d].target must be one of "
                              "%s" % (where, i, ", ".join(TARGETS)))
            if not (isinstance(item.get("rule_id"), str)
                    and item["rule_id"].strip()):
                errors.append("%s: ranked_findings[%d] needs a non-empty "
                              "'rule_id'" % (where, i))

    target = fixture.get("score_target")
    if target is not None:
        if not isinstance(target, dict):
            errors.append("%s: score_target must be an object" % where)
        else:
            if target.get("target") not in TARGETS:
                errors.append("%s: score_target.target must be one of %s"
                              % (where, ", ".join(TARGETS)))
            if target.get("target") not in allowed_targets:
                errors.append("%s: score_target.target must be one of %s"
                              % (where, ", ".join(allowed_targets)))
            value = target.get("value")
            if not (isinstance(value, (int, float))
                    and not isinstance(value, bool)):
                errors.append("%s: score_target.value must be a number"
                              % where)
            if not (isinstance(target.get("label_provenance"), str)
                    and target["label_provenance"].strip()):
                errors.append("%s: score_target.label_provenance must be a "
                              "non-empty string" % where)

    preservation = fixture.get("preservation", [])
    if not isinstance(preservation, list):
        errors.append("%s: preservation must be a list" % where)
    else:
        for i, item in enumerate(preservation):
            if not isinstance(item, dict):
                errors.append("%s: preservation[%d] must be an object"
                              % (where, i))
                continue
            if item.get("kind") not in PRESERVATION_KINDS:
                errors.append("%s: preservation[%d].kind must be one of %s"
                              % (where, i, ", ".join(PRESERVATION_KINDS)))
            if not (isinstance(item.get("value"), str)
                    and item["value"].strip()):
                errors.append("%s: preservation[%d] needs a non-empty 'value'"
                              % (where, i))

    errors.extend(_str_list(fixture.get("forbidden_additions", []),
                            "%s.forbidden_additions" % where))
    return errors


def validate_experiment_config(config):
    """Schema-validate an experiment config. Returns a list of errors."""
    errors = []
    if not isinstance(config, dict):
        return ["experiment config must be a JSON object"]

    if config.get("schema") != EXPERIMENT_CONFIG_SCHEMA:
        errors.append("schema must be %s" % EXPERIMENT_CONFIG_SCHEMA)
    if not (isinstance(config.get("fixture_revision"), str)
            and config["fixture_revision"].strip()):
        errors.append("fixture_revision must be a non-empty string")

    direction = config.get("score_direction")
    if direction not in SCORE_DIRECTIONS:
        errors.append("score_direction must be one of %s"
                      % ", ".join(SCORE_DIRECTIONS))

    for impl_name in ("baseline", "candidate"):
        spec = config.get(impl_name)
        if not isinstance(spec, dict):
            errors.append("%s must be an implementation object" % impl_name)
            continue
        if not (isinstance(spec.get("name"), str) and spec["name"].strip()):
            errors.append("%s.name must be a non-empty string" % impl_name)
        if spec.get("kind") != "antislop-score":
            errors.append("%s.kind must be 'antislop-score'" % impl_name)
        if not (isinstance(spec.get("registry"), str)
                and spec["registry"].strip()):
            errors.append("%s.registry must be a non-empty string" % impl_name)
        categories = spec.get("categories")
        if categories is not None:
            if not isinstance(categories, list) or not categories or any(
                    cat not in VALID_SEMANTIC_TYPES for cat in categories):
                errors.append("%s.categories must be a non-empty list of "
                              "semantic types %s"
                              % (impl_name, sorted(VALID_SEMANTIC_TYPES)))

    holdout_ids = config.get("holdout_ids")
    if holdout_ids is not None and not isinstance(holdout_ids, list):
        errors.append("holdout_ids must be a list of fixture ids")

    expected_hash = config.get("expected_fixture_hash")
    if expected_hash is not None and not isinstance(expected_hash, str):
        errors.append("expected_fixture_hash must be a string")

    for flag in ("fail_on_false_positive_regression",
                 "fail_on_recall_regression",
                 "fail_on_preservation_regression"):
        value = config.get(flag)
        if value is not None and not isinstance(value, bool):
            errors.append("%s must be a boolean" % flag)

    for limit in ("max_false_positive_rate", "max_recall_regression",
                  "max_mae"):
        value = config.get(limit)
        if value is not None and not (isinstance(value, (int, float))
                                      and not isinstance(value, bool)):
            errors.append("%s must be a number or null" % limit)
    value = config.get("max_preservation_failures")
    if value is not None and not (isinstance(value, int)
                                  and not isinstance(value, bool)):
        errors.append("max_preservation_failures must be an integer or null")

    for extra in ("fixture_path", "registry"):
        if extra in config and not isinstance(config[extra], str):
            errors.append("%s must be a string" % extra)
    return errors


def canonical_hash(entries):
    """Deterministic SHA-256 over a fixture list, pinning a frozen revision."""
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve(path, base_dir):
    if os.path.isabs(path):
        return path
    if base_dir:
        candidate = os.path.join(base_dir, path)
        if os.path.exists(candidate):
            return candidate
    return path


def _detect_all(text, registry, profile):
    """Detect findings for every rule with a working detector.

    Mirrors score.py's detect_findings without the scoring-type gate so the
    harness can measure recall and false positives across every category,
    including advisory structural and mechanism findings. Reuses score.py's
    matchers and overlap handling and structural.py's detectors.
    """
    findings = []
    for rule in filter_rules_by_profile(registry, profile):
        detection = rule.get("detection_class", "exact_match")
        if detection == "exact_match":
            matches = scoring.find_exact_matches(text, rule)
        elif detection == "phrase_match":
            matches = scoring.find_phrase_matches(text, rule)
        elif detection in ("pattern_match", "structural"):
            if rule.get("detector") in structural.DETECTORS:
                result = structural.detect_rule(text, rule, profile)
                for finding in result.get("findings", []):
                    start = finding["start"]
                    end = finding["end"]
                    findings.append({
                        "rule_id": rule["id"],
                        "category": rule["category"],
                        "severity": rule["severity"],
                        "base_weight": rule["base_weight"],
                        "position": start,
                        "match_length": end - start,
                        "signal": finding["signal"],
                        "evidence": finding.get("evidence", "span"),
                    })
            continue
        else:
            continue
        for match in matches:
            findings.append({
                "rule_id": rule["id"],
                "category": rule["category"],
                "severity": rule["severity"],
                "base_weight": rule["base_weight"],
                "position": match.start(),
                "match_length": match.end() - match.start(),
                "signal": "strict",
                "evidence": "span",
            })

    overlapped = scoring.handle_overlaps(findings)
    return [{
        "rule_id": f["rule_id"],
        "category": f["category"],
        "severity": f["severity"],
        "base_weight": f["base_weight"],
        "signal": f["signal"],
        "primary": f.get("primary", True),
        "span": [f["position"], f["position"] + f["match_length"]],
    } for f in overlapped]


def antislop_implementation(name, registry_path, categories=None):
    """Return a scorer implementation callable for the harness.

    The callable takes (text, profile) and returns a dict with score, findings
    (rule_id, category, severity, signal, primary, span), name, and version.
    A categories list restricts the rule set to those semantic types, letting
    a candidate implementation drop advisory or structural rules.
    """
    registry = load_registry(registry_path)
    rules = registry["rules"]
    if categories is not None:
        allowed = set(categories)
        rules = [rule for rule in rules
                 if rule.get("semantic_type") in allowed]
    reg_copy = dict(registry)
    reg_copy["rules"] = rules
    version = registry.get("version", "unknown")

    def impl(text, profile):
        findings = _detect_all(text, reg_copy, profile)
        try:
            score = scoring.score_text(text, reg_copy, profile)["score"]
        except Exception:  # noqa: BLE001 -- scoring is advisory, never a gate
            score = None
        return {"name": name, "version": version, "score": score,
                "findings": findings}

    impl.name = name
    return impl


def build_implementation(spec, base_dir=None):
    """Turn a config implementation spec into a callable."""
    kind = spec.get("kind")
    if kind != "antislop-score":
        raise ValueError("unknown implementation kind %r" % kind)
    registry_path = _resolve(spec.get("registry", "rules.json"), base_dir)
    return antislop_implementation(spec.get("name", "antislop-score"),
                                   registry_path, spec.get("categories"))


def _overlaps(span, start, end):
    return span[0] < end and start < span[1]


def _run_stable(impl, text, profile):
    """Run an implementation twice and report whether the result is stable."""
    first = impl(text, profile)
    second = impl(text, profile)
    stable = (first["score"] == second["score"]
              and first["findings"] == second["findings"])
    return first, stable


def _spearman_rho(label_ranks, impl_ranks):
    """Pearson correlation on rank vectors (Spearman with average ranks)."""
    n = len(label_ranks)
    mean_label = sum(label_ranks) / n
    mean_impl = sum(impl_ranks) / n
    cov = sum((a - mean_label) * (b - mean_impl)
              for a, b in zip(label_ranks, impl_ranks))
    var_label = sum((a - mean_label) ** 2 for a in label_ranks)
    var_impl = sum((b - mean_impl) ** 2 for b in impl_ranks)
    if var_label == 0 or var_impl == 0:
        return None
    return cov / (var_label * var_impl) ** 0.5


def _rank_with_ties(values):
    """Average ranks for a list of comparable values, lowest value = rank 1."""
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(indexed):
        start = position
        value = values[indexed[start]]
        while position + 1 < len(indexed) and values[indexed[position + 1]] == value:
            position += 1
        average = (start + position) / 2.0 + 1.0
        for offset in range(start, position + 1):
            ranks[indexed[offset]] = average
        position += 1
    return ranks


def _fixture_text(fixture, target):
    if target == "source":
        return fixture.get("source_text", "")
    if target == "candidate":
        return fixture.get("candidate_text", "")
    return fixture.get("text", "")


def _check_ranked_findings(fixture, impl, profile):
    """Rank correlation for labeled severity ordering."""
    ranked = fixture.get("ranked_findings", [])
    if not ranked:
        return {"state": "unlabeled", "n": 0, "spearman": None}
    labels = []
    by_id = {}
    for item in ranked:
        text = _fixture_text(fixture, item.get("target", "text"))
        if not text:
            continue
        impl_result, _stable = _run_stable(impl, text, profile)
        found = [f for f in impl_result["findings"]
                 if f["rule_id"] == item["rule_id"]]
        if not found:
            continue
        labels.append(item["rule_id"])
        by_id[item["rule_id"]] = found[0]["base_weight"]
    if len(labels) < 2:
        return {"state": "insufficient", "n": len(labels), "spearman": None}
    label_ranks = _rank_with_ties(list(range(len(labels))))
    impl_ranks = _rank_with_ties([-by_id[rid] for rid in labels])
    rho = _spearman_rho(label_ranks, impl_ranks)
    if rho is None:
        return {"state": "ties_only", "n": len(labels), "spearman": None}
    return {"state": "ok", "n": len(labels), "spearman": round(rho, 4)}


def _check_detection_labels(fixture, impl, profile):
    """Recall, exact-span agreement, and false positives for one fixture."""
    expected = fixture.get("expected_findings", [])
    clean_spans = fixture.get("clean_spans", [])
    results = []
    found_count = 0
    exact_count = 0
    for label in expected:
        text = _fixture_text(fixture, label.get("target", "text"))
        impl_result, _stable = _run_stable(impl, text, profile)
        matches = [f for f in impl_result["findings"]
                   if f["rule_id"] == label["rule_id"]]
        found = bool(matches)
        exact = any(f["span"] == label["span"] for f in matches)
        category_ok = (not found) or any(
            f["category"] == label["category"] for f in matches)
        if found:
            found_count += 1
        if exact:
            exact_count += 1
        results.append({
            "target": label.get("target", "text"),
            "rule_id": label["rule_id"],
            "category": label["category"],
            "span": label["span"],
            "found": found,
            "exact": exact,
            "category_match": category_ok,
        })

    hits = []
    spans_hit = 0
    for span in clean_spans:
        text = _fixture_text(fixture, span.get("target", "text"))
        impl_result, _stable = _run_stable(impl, text, profile)
        landing = [f for f in impl_result["findings"]
                   if _overlaps(f["span"], span["span"][0], span["span"][1])]
        hit = bool(landing)
        if hit:
            spans_hit += 1
        hits.append({
            "span": span["span"],
            "note": span.get("note", ""),
            "category": span.get("category"),
            "hit": hit,
            "rule_ids": [f["rule_id"] for f in landing],
            "finding_categories": [f["category"] for f in landing],
        })

    return {
        "label_results": results,
        "recall": {
            "found": found_count,
            "expected": len(expected),
            "rate": (round(found_count / len(expected), 4)
                     if expected else None),
        },
        "exact_span_agreement": {
            "exact": exact_count,
            "expected": len(expected),
            "rate": (round(exact_count / len(expected), 4)
                     if expected else None),
        },
        "false_positives": {
            "spans_hit": spans_hit,
            "clean_spans": len(clean_spans),
            "rate": (round(spans_hit / len(clean_spans), 4)
                     if clean_spans else None),
            "hits": hits,
        },
    }


def _check_preservation(fixture, registry_path):
    """Preservation and integrity for a rewrite fixture, reusing fidelity."""
    source = fixture["source_text"]
    candidate = fixture["candidate_text"]
    profile = fixture["profile"]
    obligation_failures = []
    for item in fixture.get("preservation", []):
        if item["kind"] == "fact":
            if not drift.contains_fact(candidate, item["value"]):
                obligation_failures.append({"kind": "fact",
                                            "value": item["value"]})
        else:
            pattern = r"\b" + re.escape(item["value"]) + r"\b"
            if not re.search(pattern, candidate):
                obligation_failures.append({"kind": "term",
                                            "value": item["value"]})

    fidelity_report = fidelity.check_fidelity(
        source, candidate,
        required_terms=(),
        authorized_changes=(),
        hot_zones=[],
        churn_limit=0.5,
        registry_path=registry_path,
        profile=profile,
    )
    hard_failures = fidelity_report["preservation"]["hard_failures"]
    integrity_failures = list(fidelity_report["integrity"]["failures"])

    forbidden_found = [term for term in fixture.get("forbidden_additions", [])
                       if drift.contains_fact(candidate, term)]
    for term in forbidden_found:
        integrity_failures.append({
            "kind": "forbidden_addition", "value": term,
        })

    all_failures = (obligation_failures + hard_failures)
    return {
        "obligation_failures": obligation_failures,
        "fidelity_hard_failures": hard_failures,
        "integrity_failures": integrity_failures,
        "forbidden_additions_found": forbidden_found,
        "total": len(all_failures),
    }


def run_calibration_fixture(fixture, impl, registry_path, config):
    """Evaluate one fixture against one implementation."""
    profile = fixture["profile"]
    kind = "rewrite" if fixture.get("source_text") else "detection"
    result = {
        "impl_name": getattr(impl, "name", "implementation"),
    }
    score_stable = True
    scores = {}

    detection = _check_detection_labels(fixture, impl, profile)
    result.update(detection)
    result["rank"] = _check_ranked_findings(fixture, impl, profile)

    if kind == "detection":
        text = fixture["text"]
        impl_result, stable = _run_stable(impl, text, profile)
        score_stable = score_stable and stable
        scores["text"] = impl_result["score"]
    else:
        source = fixture["source_text"]
        candidate = fixture["candidate_text"]
        source_result, source_stable = _run_stable(impl, source, profile)
        candidate_result, candidate_stable = _run_stable(impl, candidate, profile)
        score_stable = score_stable and source_stable and candidate_stable
        scores["source"] = source_result["score"]
        scores["candidate"] = candidate_result["score"]
        delta = None
        direction_improvement = None
        if scores["source"] is not None and scores["candidate"] is not None:
            delta = scores["candidate"] - scores["source"]
            if config["score_direction"] == "higher_is_better":
                direction_improvement = delta > 0
            else:
                direction_improvement = delta < 0
        result["score_delta"] = {
            "source": scores["source"],
            "candidate": scores["candidate"],
            "delta": delta,
            "direction_improvement": direction_improvement,
        }

    target = fixture.get("score_target")
    result["mae"] = None
    if target is not None:
        text = _fixture_text(fixture, target.get("target", "text"))
        impl_result, _stable = _run_stable(impl, text, profile)
        score = impl_result["score"]
        error = None if score is None else abs(score - target["value"])
        result["mae"] = {
            "target": target.get("target", "text"),
            "labeled_value": target["value"],
            "score": score,
            "error": error,
            "label_provenance": target["label_provenance"],
        }
    result["score_stable"] = score_stable
    return result, kind


def _flatten_impl(fixture_results, impl_key):
    """Merge fixture-level provenance with one implementation's per-fixture
    result so the aggregator sees a single flat entry per fixture."""
    flattened = []
    for entry in fixture_results:
        merged = {key: value for key, value in entry.items()
                  if key not in ("baseline", "candidate")}
        merged.update(entry[impl_key])
        flattened.append(merged)
    return flattened


def _rate_bucket(found, total, found_key="found", total_key="expected"):
    if total == 0:
        return {"state": "unlabeled", found_key: 0, total_key: 0,
                "rate": None}
    return {"state": "ok", found_key: found, total_key: total,
            "rate": round(found / total, 4)}


def _pool_rates(entries, key):
    """Pool per-fixture counts into overall, by-category, and by-profile."""
    overall_found = sum(entry[key]["found"] for entry in entries)
    overall_total = sum(entry[key]["expected"] for entry in entries)
    by_category = {}
    for entry in entries:
        for label in entry["label_results"]:
            category = label["category"]
            bucket = by_category.setdefault(
                category, {"found": 0, "expected": 0})
            bucket["found"] += 1 if label["found"] else 0
            bucket["expected"] += 1
    for category in ALL_CATEGORIES:
        if category not in by_category:
            by_category[category] = {"found": 0, "expected": 0}
    by_profile = {}
    for entry in entries:
        profile = entry["profile"]
        bucket = by_profile.setdefault(profile, {"found": 0, "expected": 0})
        bucket["found"] += entry[key]["found"]
        bucket["expected"] += entry[key]["expected"]
    return {
        "overall": _rate_bucket(overall_found, overall_total),
        "by_category": {cat: _rate_bucket(v["found"], v["expected"])
                        for cat, v in sorted(by_category.items())},
        "by_profile": {prof: _rate_bucket(v["found"], v["expected"])
                       for prof, v in sorted(by_profile.items())},
    }


def _pool_exact(entries):
    overall_exact = sum(entry["exact_span_agreement"]["exact"]
                        for entry in entries)
    overall_total = sum(entry["exact_span_agreement"]["expected"]
                        for entry in entries)
    return _rate_bucket(overall_exact, overall_total, "exact", "expected")


def _pool_fp(entries):
    overall_hit = sum(entry["false_positives"]["spans_hit"]
                      for entry in entries)
    overall_total = sum(entry["false_positives"]["clean_spans"]
                        for entry in entries)
    by_category = {}
    for entry in entries:
        for hit in entry["false_positives"]["hits"]:
            category = hit["category"] or "unlabeled"
            bucket = by_category.setdefault(
                category, {"spans_hit": 0, "clean_spans": 0})
            bucket["clean_spans"] += 1
            if hit["hit"]:
                bucket["spans_hit"] += 1
    by_profile = {}
    for entry in entries:
        profile = entry["profile"]
        bucket = by_profile.setdefault(
            profile, {"spans_hit": 0, "clean_spans": 0})
        bucket["spans_hit"] += entry["false_positives"]["spans_hit"]
        bucket["clean_spans"] += entry["false_positives"]["clean_spans"]
    return {
        "overall": _rate_bucket(overall_hit, overall_total, "spans_hit",
                                "clean_spans"),
        "by_category": {cat: _rate_bucket(v["spans_hit"], v["clean_spans"],
                                          "spans_hit", "clean_spans")
                        for cat, v in sorted(by_category.items())
                        if v["clean_spans"] > 0},
        "by_profile": {prof: _rate_bucket(v["spans_hit"], v["clean_spans"],
                                          "spans_hit", "clean_spans")
                       for prof, v in sorted(by_profile.items())},
    }


def _pool_mae(entries):
    errors = [entry["mae"]["error"] for entry in entries
              if entry["mae"] is not None and entry["mae"]["error"] is not None]
    if not errors:
        return {"state": "insufficient", "n": 0, "mae": None}
    return {"state": "ok", "n": len(errors),
            "mae": round(sum(errors) / len(errors), 4)}


def _pool_rank(entries):
    values = [entry["rank"]["spearman"] for entry in entries
              if entry["rank"].get("state") == "ok"
              and entry["rank"]["spearman"] is not None]
    if not values:
        return {"state": "insufficient", "n": 0, "mean": None}
    return {"state": "ok", "n": len(values),
            "mean": round(sum(values) / len(values), 4)}


def _pool_deltas(entries):
    deltas = [entry["score_delta"]["delta"] for entry in entries
              if entry.get("score_delta")
              and entry["score_delta"]["delta"] is not None]
    if not deltas:
        return {"state": "insufficient", "n": 0, "mean": None}
    return {"state": "ok", "n": len(deltas),
            "mean": round(sum(deltas) / len(deltas), 4)}


def aggregate_fixtures(fixture_results):
    """Aggregate per-fixture results into one implementation's metrics."""
    rewrite = [entry for entry in fixture_results if entry["kind"] == "rewrite"]
    labeled = [entry for entry in fixture_results if entry["labels_present"]]

    if labeled:
        recall = _pool_rates(labeled, "recall")
    else:
        recall = {"overall": _rate_bucket(0, 0),
                  "by_category": {cat: _rate_bucket(0, 0)
                                  for cat in ALL_CATEGORIES},
                  "by_profile": {prof: _rate_bucket(0, 0)
                                 for prof in PROFILES}}

    exact = _pool_exact(fixture_results)
    fp = _pool_fp(fixture_results)
    mae = _pool_mae(fixture_results)
    rank = _pool_rank(fixture_results)
    deltas = _pool_deltas(rewrite)

    stable_entries = [entry for entry in fixture_results
                      if entry["score_stable"]]
    preservation = {
        "total": sum(entry["preservation_total"] for entry in fixture_results),
        "obligation_failures": sum(
            len(entry["obligation_failures"]) for entry in fixture_results),
        "fidelity_hard_failures": sum(
            len(entry["fidelity_hard_failures"]) for entry in fixture_results),
    }
    integrity = {
        "total": sum(len(entry["integrity_failures"])
                     for entry in fixture_results),
        "forbidden_additions": sum(
            len(entry["forbidden_additions_found"]) for entry in fixture_results),
    }

    per_profile = {}
    for profile in PROFILES:
        entries = [entry for entry in fixture_results
                   if entry["profile"] == profile]
        if not entries:
            continue
        labeled_entries = [entry for entry in entries
                           if entry["labels_present"]]
        if labeled_entries:
            pooled = _pool_rates(labeled_entries, "recall")
        else:
            pooled = {"overall": _rate_bucket(0, 0)}
        fp_pooled = _pool_fp(entries)
        per_profile[profile] = {
            "fixtures": len(entries),
            "recall": pooled["overall"],
            "false_positive_rate": fp_pooled["overall"],
        }

    return {
        "recall": recall,
        "exact_span_agreement": exact,
        "false_positive_rate": fp,
        "mae": mae,
        "rank_correlation": rank,
        "score_delta": deltas,
        "score_stability": {
            "stable_fixtures": len(stable_entries),
            "checked_fixtures": len(fixture_results),
            "stable": len(stable_entries) == len(fixture_results),
        },
        "preservation_failures": preservation,
        "integrity_failures": integrity,
        "per_profile": per_profile,
    }


def _rate_value(bucket):
    return bucket.get("rate")


def _compare(baseline, candidate):
    """Per-metric baseline/candidate comparison and regression list."""
    regressions = []
    comparison = {}

    def compare_bucket(label, base, cand):
        base_rate = _rate_value(base)
        cand_rate = _rate_value(cand)
        entry = {"baseline": base_rate, "candidate": cand_rate}
        if base_rate is not None and cand_rate is not None:
            entry["delta"] = round(cand_rate - base_rate, 4)
        return entry

    recall = {"overall": compare_bucket(
        "recall", baseline["recall"]["overall"],
        candidate["recall"]["overall"])}
    for category, base in baseline["recall"]["by_category"].items():
        cand = candidate["recall"]["by_category"].get(category)
        if cand is None:
            continue
        recall[category] = compare_bucket("recall", base, cand)
        base_rate = _rate_value(base)
        cand_rate = _rate_value(cand)
        if (base_rate is not None and cand_rate is not None
                and cand_rate < base_rate):
            regressions.append({"kind": "recall", "category": category,
                                "baseline": base_rate,
                                "candidate": cand_rate})
    comparison["recall"] = recall

    fp = {"overall": compare_bucket(
        "false_positive", baseline["false_positive_rate"]["overall"],
        candidate["false_positive_rate"]["overall"])}
    for category, base in baseline["false_positive_rate"]["by_category"].items():
        cand = candidate["false_positive_rate"]["by_category"].get(category)
        if cand is None:
            continue
        fp[category] = compare_bucket("false_positive", base, cand)
        base_rate = _rate_value(base)
        cand_rate = _rate_value(cand)
        if (base_rate is not None and cand_rate is not None
                and cand_rate > base_rate):
            regressions.append({"kind": "false_positive", "category": category,
                                "baseline": base_rate,
                                "candidate": cand_rate})
    comparison["false_positive_rate"] = fp

    base_pres = baseline["preservation_failures"]["total"]
    cand_pres = candidate["preservation_failures"]["total"]
    comparison["preservation_failures"] = {
        "baseline": base_pres, "candidate": cand_pres,
        "delta": cand_pres - base_pres,
    }
    if cand_pres > base_pres:
        regressions.append({"kind": "preservation", "category": None,
                            "baseline": base_pres, "candidate": cand_pres})

    def compare_value(label, base, cand):
        entry = {"baseline": base, "candidate": cand}
        if base is not None and cand is not None:
            entry["delta"] = round(cand - base, 4)
        return entry

    comparison["mae"] = compare_value("mae", baseline["mae"].get("mae"),
                                      candidate["mae"].get("mae"))
    comparison["rank_correlation"] = compare_value(
        "rank", baseline["rank_correlation"].get("mean"),
        candidate["rank_correlation"].get("mean"))

    return comparison, regressions


def run_experiment(fixtures, baseline, candidate, config,
                   registry_path="rules.json"):
    """Run both implementations over the frozen fixtures and build the report.

    baseline and candidate are callables (text, profile) -> dict. Returns the
    experiment report dict. Raises ValueError on configuration errors.
    """
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_calibration_fixture(fixture, seen_ids))
    config_errors = validate_experiment_config(config)
    if schema_errors or config_errors:
        raise ValueError("\n".join(schema_errors + config_errors))

    config_holdout = set(config.get("holdout_ids", []) or [])
    fixture_holdout = {fixture["id"] for fixture in fixtures
                       if fixture.get("holdout")}
    unknown_holdout = sorted(config_holdout - fixture_holdout - {
        fixture["id"] for fixture in fixtures})
    holdout_ids = sorted(config_holdout | fixture_holdout)
    if not holdout_ids:
        raise ValueError(
            "experiment requires a non-empty holdout set: flag a fixture "
            "'holdout: true' or list it in holdout_ids")
    if unknown_holdout:
        raise ValueError("holdout_ids reference unknown fixtures: %s"
                         % ", ".join(unknown_holdout))

    computed_hash = canonical_hash(fixtures)
    expected_hash = config.get("expected_fixture_hash")
    if expected_hash and computed_hash != expected_hash:
        raise ValueError(
            "fixture revision changed: computed hash %s does not match "
            "expected_fixture_hash %s" % (computed_hash[:12], expected_hash[:12]))

    registry = load_registry(registry_path)
    version = registry.get("version", "unknown")

    baseline_name = getattr(baseline, "name", "baseline")
    candidate_name = getattr(candidate, "name", "candidate")

    fixture_results = []
    for fixture in fixtures:
        fixture_base = {"id": fixture["id"], "profile": fixture["profile"],
                        "genre": fixture["genre"], "locale": fixture["locale"],
                        "source": fixture["source"],
                        "label_provenance": fixture["label_provenance"],
                        "holdout": bool(fixture.get("holdout"))}
        base_result, kind = run_calibration_fixture(
            fixture, baseline, registry_path, config)
        cand_result, _kind = run_calibration_fixture(
            fixture, candidate, registry_path, config)
        entry = dict(fixture_base)
        entry["kind"] = kind
        entry["labels_present"] = bool(fixture.get("expected_findings"))
        entry["baseline"] = base_result
        entry["candidate"] = cand_result
        entry["score_stable"] = (base_result["score_stable"]
                                 and cand_result["score_stable"])
        if kind == "rewrite":
            preservation = _check_preservation(fixture, registry_path)
            entry["obligation_failures"] = preservation["obligation_failures"]
            entry["fidelity_hard_failures"] = preservation[
                "fidelity_hard_failures"]
            entry["integrity_failures"] = preservation["integrity_failures"]
            entry["forbidden_additions_found"] = preservation[
                "forbidden_additions_found"]
            entry["preservation_total"] = preservation["total"]
            entry["preservation"] = preservation
        else:
            entry["obligation_failures"] = []
            entry["fidelity_hard_failures"] = []
            entry["integrity_failures"] = []
            entry["forbidden_additions_found"] = []
            entry["preservation_total"] = 0
            entry["preservation"] = None
        fixture_results.append(entry)

    baseline_agg = aggregate_fixtures(_flatten_impl(fixture_results,
                                                    "baseline"))
    candidate_agg = aggregate_fixtures(_flatten_impl(fixture_results,
                                                     "candidate"))

    comparison, regressions = _compare(baseline_agg, candidate_agg)

    gate_failures = []
    configured = {
        "fail_on_false_positive_regression": bool(
            config.get("fail_on_false_positive_regression")),
        "fail_on_recall_regression": bool(
            config.get("fail_on_recall_regression")),
        "fail_on_preservation_regression": bool(
            config.get("fail_on_preservation_regression")),
        "max_false_positive_rate": config.get("max_false_positive_rate"),
        "max_recall_regression": config.get("max_recall_regression"),
        "max_preservation_failures": config.get("max_preservation_failures"),
        "max_mae": config.get("max_mae"),
    }
    if configured["fail_on_false_positive_regression"]:
        fp_regressions = [reg for reg in regressions
                          if reg["kind"] == "false_positive"]
        for reg in fp_regressions:
            gate_failures.append(
                "false-positive regression in %s: %.4f -> %.4f"
                % (reg["category"], reg["baseline"], reg["candidate"]))
    if configured["fail_on_recall_regression"]:
        recall_regressions = [reg for reg in regressions
                              if reg["kind"] == "recall"]
        for reg in recall_regressions:
            gate_failures.append(
                "recall regression in %s: %.4f -> %.4f"
                % (reg["category"], reg["baseline"], reg["candidate"]))
    if configured["fail_on_preservation_regression"]:
        pres_regressions = [reg for reg in regressions
                            if reg["kind"] == "preservation"]
        for reg in pres_regressions:
            gate_failures.append(
                "preservation regression: baseline %d, candidate %d"
                % (reg["baseline"], reg["candidate"]))
        if not pres_regressions:
            total = candidate_agg["preservation_failures"]["total"]
            if total > 0:
                gate_failures.append(
                    "preservation regression: %d preservation failure(s) in "
                    "the candidate evaluation" % total)

    overall_fp = candidate_agg["false_positive_rate"]["overall"].get("rate")
    if (configured["max_false_positive_rate"] is not None
            and overall_fp is not None
            and overall_fp > configured["max_false_positive_rate"]):
        gate_failures.append(
            "candidate false-positive rate %.4f exceeds limit %.4f"
            % (overall_fp, configured["max_false_positive_rate"]))
    if (configured["max_preservation_failures"] is not None
            and candidate_agg["preservation_failures"]["total"]
            > configured["max_preservation_failures"]):
        gate_failures.append(
            "candidate preservation failures %d exceed limit %d"
            % (candidate_agg["preservation_failures"]["total"],
               configured["max_preservation_failures"]))
    if (configured["max_mae"] is not None
            and candidate_agg["mae"].get("mae") is not None
            and candidate_agg["mae"]["mae"] > configured["max_mae"]):
        gate_failures.append(
            "candidate MAE %.4f exceeds limit %.4f"
            % (candidate_agg["mae"]["mae"], configured["max_mae"]))

    report = {
        "interface": INTERFACE,
        "schema": EXPERIMENT_REPORT_SCHEMA,
        "version": version,
        "fixture_revision": config["fixture_revision"],
        "fixture_hash": computed_hash,
        "frozen": True,
        "score_direction": config["score_direction"],
        "holdout_ids": holdout_ids,
        "holdout_used_for_tuning": False,
        "denominators": {
            "expected_findings": sum(
                len(fixture.get("expected_findings", []))
                for fixture in fixtures),
            "clean_spans": sum(
                len(fixture.get("clean_spans", [])) for fixture in fixtures),
            "score_targets": sum(
                1 for fixture in fixtures
                if fixture.get("score_target") is not None),
            "rewrite_fixtures": sum(
                1 for fixture in fixtures if fixture.get("source_text")),
            "holdout_fixtures": len(holdout_ids),
        },
        "baseline": {
            "name": baseline_name,
            "categories": config["baseline"].get("categories"),
        },
        "candidate": {
            "name": candidate_name,
            "categories": config["candidate"].get("categories"),
        },
        "fixtures": fixture_results,
        "aggregate": {
            "baseline": baseline_agg,
            "candidate": candidate_agg,
        },
        "comparison": comparison,
        "regressions": regressions,
        "gate": {
            "configured": configured,
            "failures": gate_failures,
            "passed": not gate_failures,
        },
        "disclaimer": DISCLAIMER,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--experiment-config",
        default="skills/antislop/evals/calibration-experiment.json",
        help="Path to the experiment configuration artifact",
    )
    parser.add_argument(
        "--output", default=None,
        help="Write the report JSON to this file (reviewable artifact)",
    )
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Print a compact JSON report")
    args = parser.parse_args()

    config_path = args.experiment_config
    if not os.path.exists(config_path):
        print(json.dumps({"error": "experiment config not found: %s"
                                  % config_path}))
        sys.exit(2)

    base_dir = os.path.dirname(os.path.abspath(config_path))
    try:
        config = limits.load_json_file(config_path, "experiment config")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(2)
    if not isinstance(config, dict):
        print(json.dumps({"error": "experiment config must be a JSON object"}))
        sys.exit(2)

    fixture_path = _resolve(config.get("fixture_path", "calibration-fixtures.json"),
                            base_dir)
    if not os.path.exists(fixture_path):
        print(json.dumps({"error": "fixture corpus not found: %s"
                                  % fixture_path}))
        sys.exit(2)
    try:
        data = limits.load_json_file(fixture_path, "calibration fixtures")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(2)
    fixtures = data.get("evals", data) if isinstance(data, dict) else data
    if not isinstance(fixtures, list):
        print(json.dumps({"error": "fixture corpus must be a JSON list or "
                                    "carry an 'evals' list"}))
        sys.exit(2)

    registry_path = _resolve(config.get("registry", "rules.json"), base_dir)
    if not os.path.exists(registry_path):
        print(json.dumps({"error": "registry not found: %s" % registry_path}))
        sys.exit(2)

    try:
        baseline = build_implementation(config["baseline"], base_dir)
        candidate = build_implementation(config["candidate"], base_dir)
    except (KeyError, ValueError, OSError) as exc:
        print(json.dumps({"error": "implementation error: %s" % exc}))
        sys.exit(2)

    try:
        registry_version = load_registry(registry_path).get("version")
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": "registry read error: %s" % exc}))
        sys.exit(2)
    if args.expect_version and registry_version != args.expect_version:
        print(json.dumps({
            "error": "registry version %s does not match --expect-version %s"
                     % (registry_version, args.expect_version),
        }, indent=2))
        sys.exit(2)

    try:
        report = run_experiment(fixtures, baseline, candidate, config,
                                registry_path=registry_path)
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "config": config_path,
                          "fixture_path": fixture_path}, indent=2))
        sys.exit(2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=False)
        print("wrote experiment report to %s" % args.output, file=sys.stderr)

    print(json.dumps(report, indent=None if args.as_json else 2))
    sys.exit(0 if report["gate"]["passed"] else 1)


if __name__ == "__main__":
    main()
