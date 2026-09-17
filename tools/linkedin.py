#!/usr/bin/env python3
"""LinkedIn social profile review runner (issue #103).

Antislop's general and technical profiles apply long-form paragraph,
heading, and conclusion expectations that can damage LinkedIn posts, and a
LinkedIn-specific rule set must not leak into general prose. This runner
serves the opt-in `social-linkedin` profile: it reviews a LinkedIn post
against a post type (lesson, case-study, announcement, opinion,
practical-guide) and reports which structural elements fit, which of them
the draft supplies, and the usual lexical, formatting, mechanism, and
author-gap findings.

Everything structural here is optional. Post-type routing decides which
elements fit; a missing element is recorded as `n/a` ("no occasion in the
text; no judgment is forced"), never as a defect. Calls to action, hooks,
hashtags, and short paragraphs are optional and profile-local. A voice
sample transfers style only: personal facts and achievements from a sample
must not migrate into the target. Supplied achievements, metrics, opinions,
and experience are preserved exactly; a required fact that disappears is a
finding. The zero-em-dash rule stays absolute. No rule promises reach,
engagement, or an algorithmic benefit, and the runner asks for a mechanism
when a reach or engagement claim has none nearby.

Reused machinery: review.py (statuses, mechanism entries, author gaps, voice
sample, em-dash spans), mechanism.py (nearby-evidence window), drift.py
(word-stable fact matching), structural.py (detectors), fidelity.py (quoted
spans), score.py (profile-filtered findings).

Usage:
    python3 tools/linkedin.py --fixtures skills/antislop/evals/linkedin-profile-fixtures.json
    python3 tools/linkedin.py review --source-text "..." --post-type lesson
    python3 tools/linkedin.py review --source-text "..." --post-type case-study \
        --voice-sample "..." --sample-fact "..." --required-fact "..."

Exit codes:
    0 -- the run succeeded, or every fixture decision matched its expectation
    1 -- a fixture decision failed
    2 -- usage or input error
"""

import argparse
import json
import os
import re
import sys
from findings import short_excerpt as _short_excerpt

import limits
from registry import load_registry
import drift
import fidelity
import mechanism
import review
import score as scoring
import structural

INTERFACE = "antislop.social-linkedin"
SCHEMA = "linkedin-post-report-1"
FIXTURE_SCHEMA = "linkedin-profile-fixtures-1"
PROFILE = "social-linkedin"
STATUSES = ("keep", "revise", "ask-author", "cut", "n/a", "over-correction")
DECISIONS = ("no-finding", "keep", "over-correction", "revise", "cut",
             "ask-author")
POST_TYPES = ("lesson", "case-study", "announcement", "opinion",
              "practical-guide")

STATUS_WEIGHT = {"n/a": 0, "no-finding": 0, "keep": 1, "over-correction": 1,
                 "revise": 2, "cut": 3, "ask-author": 4}

DISCLAIMER = (
    "The social-linkedin profile reviews LinkedIn post structure and "
    "formulaic-writing risk; it never proves AI authorship, detector "
    "immunity, or any reach or engagement result."
)

WORD_RE = re.compile(r"[A-Za-z0-9']+")

# Deterministic presence conditions for the social post features. Scope is
# per feature: setup checks only the first paragraph; everything else scans
# the whole post. These drive keep / n/a routing only; an absent optional
# feature is never a defect.
FEATURE_PATTERNS = {
    "setup": re.compile(
        r"\b(?:i|we|my|our|me|us|the team|our team|my team)\b",
        re.IGNORECASE,
    ),
    "challenge": re.compile(
        r"\b(?:problem|issue|failed|failure|broke|struggled|challenge|"
        r"hurdle|obstacle|wrong|mistake|error|hard|tough|difficult)\b",
        re.IGNORECASE,
    ),
    "action": re.compile(
        r"\b(?:tried|started|decided|switched|built|changed|reworked|"
        r"rolled out|introduced|implemented|tested|adopted|fixed|replaced|"
        r"automated)\b",
        re.IGNORECASE,
    ),
    "result": re.compile(
        r"\b\d+(?:\.\d+)?\s*%(?!\w)"
        r"|\b\d+(?:\.\d+)?\s*(?:days?|weeks?|months?|years?|people|users|"
        r"customers|hours?|minutes?|requests?|errors?|percent)\b"
        r"|\b(?:cut|reduced|dropped|improved|increased|grew|shortened|"
        r"saved|doubled|halved|went from)\b",
        re.IGNORECASE,
    ),
    "lesson": re.compile(
        r"\b(?:lesson|takeaway|learned|learnt|next time|what i'd|what i "
        r"would|if you|you should|my advice|the advice)\b",
        re.IGNORECASE,
    ),
    "position": re.compile(
        r"\b(?:i think|i believe|i'm convinced|i am convinced|my take|"
        r"in my view|in my opinion|my opinion|i'd argue|i would argue)\b",
        re.IGNORECASE,
    ),
    "announcement": re.compile(
        r"\b(?:announc|launch|releas|ship|shipped|roll out|rolling out|"
        r"introduc|went live|available now|new version)\b",
        re.IGNORECASE,
    ),
    "steps": re.compile(
        r"(?:^\s*\d+\.\s+|\bsteps?\b|\bstep \d|\bfirst,\s|\bsecond,\s|"
        r"\bthird,\s|\bhow to\b)",
        re.IGNORECASE | re.MULTILINE,
    ),
}

_STOP = frozenset((
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "for", "of",
    "to", "in", "on", "at", "by", "with", "from", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those", "it",
    "its", "it's", "we", "our", "you", "your", "they", "their", "he", "his",
    "she", "her", "i", "my", "me", "not", "no", "yes", "do", "does", "did",
    "have", "has", "had",
))


def _paragraphs(text):
    return [para.strip() for para in re.split(r"\n\s*\n", text)
            if para.strip()]


def _quoted_spans(text):
    return [{"start": match.start(), "end": match.end()}
            for match in fidelity.QUOTED_RE.finditer(text)]


def _overlaps_any(start, end, spans):
    return any(span["start"] < end and start < span["end"] for span in spans)


def _span_text(text, finding):
    start = finding.get("position")
    if start is None:
        span = finding.get("span")
        if span and len(span) == 2:
            return text[span[0]:span[1]]
        return ""
    return text[start:start + finding.get("match_length", 6)]


def _author_habit(span_text, author_habits):
    if not author_habits:
        return False
    st = span_text.strip().lower()
    if not st:
        return False
    for habit in author_habits:
        h = habit.strip().lower()
        if not h:
            continue
        if h in st or st in h:
            return True
    return False


def _finding_status(rule, start, end, quoted_spans, span_text, author_habits):
    """One explicit status per review finding."""
    if _overlaps_any(start, end, quoted_spans):
        return "keep"
    if rule is None:
        return "revise"
    rule_id = rule["id"]
    if _author_habit(span_text, author_habits):
        return "over-correction"
    if (rule["semantic_type"] == "forbidden"
            and rule.get("review_mode") == "deterministic"):
        if rule["category"] in ("filler", "chatbot") or rule_id in review.CUT_RULES:
            return "cut"
        return "revise"
    if rule_id in review.CUT_RULES or rule["category"] in ("filler", "chatbot"):
        return "cut"
    return "revise"


def _status_reason(status):
    if status == "cut":
        return ("The passage adds only repetition, ceremony, unsupported "
                "emphasis, or closure.")
    if status == "keep":
        return ("The pattern is quoted material, earned by context, or "
                "required by the post.")
    if status == "over-correction":
        return ("Applying the rule would flatten valid voice or structure, "
                "such as quoted material or the author's verified habit.")
    if status == "ask-author":
        return ("The improvement needs author-owned material the source does "
                "not supply.")
    return ("Deterministic banned pattern; the source can support an honest "
            "improvement.")


def _status_suggestion(rule, status):
    if status == "cut":
        return "Cut it, or keep only what the post needs."
    if status == "keep":
        return "Keep as-is."
    if status == "over-correction":
        return "Keep the voice; the rule does not apply here."
    return rule.get("correction", "") if rule else "Rewrite the passage."


def detect_social_features(text):
    """Deterministic evidence spans for every social post feature.

    Setup is scoped to the first paragraph; every other feature scans the
    whole post.
    """
    paragraphs = _paragraphs(text)
    first_para = paragraphs[0] if paragraphs else ""

    found = {}
    for feature_id, pattern in FEATURE_PATTERNS.items():
        if feature_id == "setup":
            source = first_para
            finder = text.find
        else:
            source = text
            finder = text.find
        spans = []
        if source:
            base = finder(source)
            for match in pattern.finditer(source):
                start = base + match.start()
                spans.append({"start": start,
                              "end": start + len(match.group(0)),
                              "value": match.group(0)})
        found[feature_id] = spans
    return found


def _scored_findings(text, registry, quoted_spans, author_habits):
    """Lexical and structural findings from the scorer, minus mechanism and
    reach-promise, which get their own status logic below."""
    rules = registry.get("rules", [])
    rule_by_id = {rule["id"]: rule for rule in rules}
    mechanism_ids = {rule["id"] for rule in rules
                     if rule["category"] == "mechanism"}
    mechanism_ids.add("social-reach-promise")
    scored, _skipped, _metrics = scoring.detect_findings(
        text, registry, PROFILE)
    scored = [finding for finding in scored
              if finding["rule_id"] not in mechanism_ids]
    scored = scoring.handle_overlaps(scored)

    findings = []
    for finding in scored:
        rule = rule_by_id.get(finding["rule_id"])
        start = finding["position"]
        end = start + finding.get("match_length", 6)
        span_text = _span_text(text, finding)
        status = _finding_status(rule, start, end, quoted_spans, span_text,
                                 author_habits)
        findings.append({
            "status": status,
            "rule_id": finding["rule_id"],
            "pattern": (rule.get("text", "") if rule
                        else finding.get("message", "")),
            "excerpt": finding.get("excerpt", ""),
            "span": [start, end],
            "why": _status_reason(status),
            "suggestion": _status_suggestion(rule, status),
        })
    return findings


def _mechanism_findings(text, registry):
    findings = []
    for entry in review.mechanism_entries(text, registry):
        if entry["evidenced"]:
            status = "keep"
            why = ("The claim is supported by a nearby mechanism or measured "
                   "result.")
            suggestion = ("Keep; the passage names the mechanism, actor, "
                          "result, or limit that earns the claim.")
        else:
            status = "ask-author"
            why = ("The claim names no mechanism, actor, result, or limit "
                   "nearby.")
            suggestion = review.MECHANISM_QUESTIONS[entry["kind"]]
        item = {
            "status": status,
            "rule_id": entry["rule_id"],
            "kind": entry["kind"],
            "pattern": entry["pattern"],
            "excerpt": _short_excerpt(text, entry["start"], entry["end"]),
            "span": [entry["start"], entry["end"]],
            "why": why,
            "suggestion": suggestion,
        }
        if status == "ask-author":
            item["tk"] = suggestion
        findings.append(item)
    return findings


def _reach_promise_findings(text, registry):
    """Reach, engagement, and algorithmic-benefit promises.

    The social-linkedin profile records such promises as unsupported unless
    a mechanism or measured result sits beside them; it never promises a
    result itself. A supplied metric with evidence nearby is keep, a bare
    promise asks the author for the mechanism.
    """
    rule = None
    for candidate in registry.get("rules", []):
        if candidate["id"] == "social-reach-promise":
            rule = candidate
            break
    if rule is None:
        return []
    result = structural.detect_rule(text, rule, PROFILE)
    findings = []
    for f in result["findings"]:
        if mechanism._nearby_evidence(text, f["start"], f["end"]):
            status = "keep"
            why = ("The claim names a mechanism or measured result beside "
                   "it; it is evidenced, not a bare promise.")
            suggestion = ("Keep; the passage names the mechanism, actor, "
                          "result, or limit that earns the claim.")
        else:
            status = "ask-author"
            why = ("The claim promises reach, engagement, or an algorithmic "
                   "benefit with no mechanism or measured result nearby.")
            suggestion = review.MECHANISM_QUESTIONS["impact"]
        findings.append({
            "status": status,
            "rule_id": "social-reach-promise",
            "pattern": rule.get("text", "Reach, engagement, or "
                                         "algorithmic-benefit promise"),
            "excerpt": f["excerpt"],
            "span": [f["start"], f["end"]],
            "why": why,
            "suggestion": suggestion,
        })
        if status == "ask-author":
            findings[-1]["tk"] = suggestion
    return findings


def _em_dash_findings(text, rule, author_habits):
    """Zero-em-dash rule, absolute in the social-linkedin profile too."""
    findings = []
    for match in review.EM_DASH_RE.finditer(text):
        span_text = text[match.start():match.end()]
        status = ("over-correction"
                  if _author_habit(span_text, author_habits) else "revise")
        findings.append({
            "status": status,
            "rule_id": rule["id"],
            "pattern": rule.get("text",
                                "Em-dash, en-dash, or double hyphen"),
            "excerpt": text[max(0, match.start() - 20):
                            min(len(text), match.end() + 20)].strip(),
            "span": [match.start(), match.end()],
            "why": (_status_reason(status)
                    if status == "over-correction"
                    else "The em-dash rule is absolute and applies in every "
                         "profile and post type."),
            "suggestion": (rule.get("correction", "Replace with a period or "
                                                    "comma and break the "
                                                    "sentence.") if rule
                           else "Replace with a period or comma."),
        })
    return findings


def _preservation_check(text, required_facts):
    """Supplied achievements, metrics, opinions, and experience kept exactly.

    Each required fact must survive word-stable in the post. A dropped fact
    is a revise finding; nothing here rewrites or invents material.
    """
    missing = []
    findings = []
    for fact in required_facts:
        if drift.contains_fact(text, fact):
            continue
        missing.append(fact)
        findings.append({
            "status": "revise",
            "rule_id": "evaluation-voice-sample",
            "pattern": "Supplied author fact dropped from the post",
            "excerpt": fact,
            "why": ("The author supplied this achievement, metric, opinion, "
                    "or experience and the post does not keep it exactly."),
            "suggestion": "Restore the supplied fact verbatim.",
        })
    return {
        "required_facts": list(required_facts),
        "missing": missing,
        "findings": findings,
    }


def _post_type_rows(text, post_type, registry):
    """Which structural elements fit this post type, and which the draft has.

    Absence of a fitting element is n/a, never a defect: the SCARL
    structure and every call to action, hook, and hashtag stay optional.
    """
    conf = registry.get("social_post_types", {}).get(post_type, {})
    applicable = conf.get("applicable", [])
    not_applicable = conf.get("not_applicable", [])
    features = registry.get("social_post_features", {})
    evidence = detect_social_features(text)
    rows = []
    for feature_id in applicable:
        description = features.get(feature_id, {}).get(
            "description", feature_id)
        spans = evidence.get(feature_id, [])
        if spans:
            rows.append({
                "feature": feature_id,
                "status": "keep",
                "excerpt": spans[0]["value"],
                "span": [spans[0]["start"], spans[0]["end"]],
                "why": ("This post type fits %s and the draft supplies it."
                        % description),
            })
        else:
            rows.append({
                "feature": feature_id,
                "status": "n/a",
                "excerpt": None,
                "span": None,
                "why": ("%s is optional for %s posts and the draft has no "
                        "occasion for it; no judgment is forced."
                        % (description, post_type)),
            })
    for feature_id in not_applicable:
        description = features.get(feature_id, {}).get(
            "description", feature_id)
        rows.append({
            "feature": feature_id,
            "status": "n/a",
            "excerpt": None,
            "span": None,
            "why": ("This structural element does not fit %s posts: %s"
                    % (post_type, description)),
        })
    return rows


def _overall_decision(findings):
    statuses = [finding["status"] for finding in findings]
    if not statuses:
        return "no-finding"
    return max(statuses, key=lambda status: STATUS_WEIGHT[status])


def review_post(text, post_type, registry, *, voice_sample=None,
                sample_facts=(), required_facts=(), author_habits=(),
                registry_path="rules.json"):
    """Review a LinkedIn post under the opt-in social-linkedin profile.

    Post types are validated against the registry; there is no way to
    activate the profile from ordinary prose. Returns a JSON-serializable
    report with post-type routing, optional-element statuses, findings,
    voice-sample and preservation records, and a decision. The report never
    contains a rewritten passage.
    """
    limits.check_input_size(text, "source text")
    known_post_types = tuple(registry.get("social_post_types", {}).keys())
    if post_type not in known_post_types:
        raise ValueError("unknown post type %r (expected one of %s)"
                         % (post_type, ", ".join(sorted(known_post_types))))

    rules = registry.get("rules", [])
    rule_by_id = {rule["id"]: rule for rule in rules}
    quoted_spans = _quoted_spans(text)

    findings = _scored_findings(text, registry, quoted_spans, author_habits)
    findings.extend(_mechanism_findings(text, registry))
    findings.extend(_reach_promise_findings(text, registry))

    em_dash_rule = rule_by_id.get("fmt-em-dash")
    if em_dash_rule is not None:
        findings.extend(_em_dash_findings(text, em_dash_rule, author_habits))

    for gap in review.detect_author_gaps(text):
        rule = rule_by_id.get(gap["rule_id"])
        findings.append({
            "status": "ask-author",
            "rule_id": gap["rule_id"],
            "kind": gap["kind"],
            "pattern": rule.get("text", "") if rule else gap["kind"],
            "excerpt": gap["excerpt"],
            "span": [gap["start"], gap["end"]],
            "why": ("The example has the grammar of a specific story and no "
                    "specific content." if gap["kind"] == "vague_example"
                    else "The claim asserts significance without saying what "
                         "changed or for whom."),
            "suggestion": gap["tk"],
            "tk": gap["tk"],
        })

    voice = review.check_voice_sample(voice_sample, text, sample_facts)
    findings.extend(voice["findings"])

    preserved = _preservation_check(text, required_facts)
    findings.extend(preserved["findings"])

    findings.sort(key=lambda finding: (finding.get("excerpt", ""),
                                       finding["rule_id"]))

    route = _post_type_rows(text, post_type, registry)
    overall = _overall_decision(findings)

    author_questions = []
    for finding in findings:
        if finding.get("tk"):
            author_questions.append({
                "tk": finding["tk"],
                "rule_id": finding["rule_id"],
                "excerpt": finding.get("excerpt", ""),
            })

    risk = {}
    try:
        risk_result = scoring.score_text(text, registry, PROFILE)
        risk = {
            "score": risk_result["score"],
            "band": risk_result["band"],
            "advisory": True,
            "authorship_evidence": False,
            "disclaimer": drift.OBSERVATION_DISCLAIMER,
        }
    except Exception:  # noqa: BLE001 -- risk is advisory, never a gate
        risk = {"score": None, "band": None, "advisory": True,
                "authorship_evidence": False,
                "disclaimer": drift.OBSERVATION_DISCLAIMER}

    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "profile": PROFILE,
        "post_type": post_type,
        "word_count": len(text.split()),
        "decision": overall,
        "route": route,
        "findings": findings,
        "voice_sample": {
            "provided": bool(voice_sample),
            "sample_facts": list(sample_facts),
            "leaked_personal_facts": voice["leaked_personal_facts"],
            "style_only": True,
        },
        "preservation": {
            "required_facts": preserved["required_facts"],
            "missing": preserved["missing"],
        },
        "author_questions": author_questions,
        "risk": risk,
        "disclaimer": DISCLAIMER,
    }


def validate_fixture(fixture, seen_ids):
    """Validate one LinkedIn post fixture. Returns a list of error strings."""
    errors = []
    if not isinstance(fixture, dict):
        return ["fixture must be a JSON object"]
    where = "fixture '%s'" % fixture.get("id", "?")
    fid = fixture.get("id")
    if not (isinstance(fid, str) and fid.strip()):
        errors.append("%s: missing non-empty 'id'" % where)
    elif fid in seen_ids:
        errors.append("%s: duplicate id" % where)
    seen_ids.add(fid)

    post_type = fixture.get("post_type")
    if post_type not in POST_TYPES:
        errors.append("%s: post_type must be one of %s"
                      % (where, ", ".join(POST_TYPES)))
    source = fixture.get("source")
    if not (isinstance(source, str) and source.strip()):
        errors.append("%s: missing non-empty 'source'" % where)

    decision = fixture.get("expected_decision")
    if decision not in DECISIONS:
        errors.append("%s: expected_decision must be one of %s"
                      % (where, ", ".join(DECISIONS)))

    route = fixture.get("expected_route")
    if route is not None:
        if not isinstance(route, dict):
            errors.append("%s: expected_route must be an object" % where)
        else:
            for feature_id, status in route.items():
                if status not in ("keep", "n/a"):
                    errors.append("%s: expected_route.%s must be 'keep' or "
                                  "'n/a', got %r" % (where, feature_id,
                                                     status))

    statuses = fixture.get("expected_statuses")
    if statuses is not None:
        if not isinstance(statuses, dict):
            errors.append("%s: expected_statuses must be an object" % where)
        else:
            for rule_id, status in statuses.items():
                if status not in STATUSES:
                    errors.append("%s: expected_statuses.%s must be one of "
                                  "%s" % (where, rule_id,
                                          ", ".join(STATUSES)))

    voice_sample = fixture.get("voice_sample")
    if voice_sample is not None and not (isinstance(voice_sample, str)
                                         and voice_sample.strip()):
        errors.append("%s: voice_sample must be a non-empty string" % where)

    for field in ("sample_facts", "required_facts"):
        value = fixture.get(field)
        if value is None:
            continue
        if not isinstance(value, list) or any(not isinstance(v, str) or not v
                                              for v in value):
            errors.append("%s: %s must be a list of non-empty strings"
                          % (where, field))
    return errors


def fixture_failures(report, fixture):
    """Compare a computed report against the fixture expectation."""
    failures = []
    decision = fixture.get("expected_decision")
    if decision and report["decision"] != decision:
        failures.append("decision %s != expected %s"
                        % (report["decision"], decision))

    route = fixture.get("expected_route")
    if route:
        actual = {row["feature"]: row["status"] for row in report["route"]}
        for feature_id, status in route.items():
            if actual.get(feature_id) != status:
                failures.append("route.%s %s != expected %s"
                                % (feature_id, actual.get(feature_id),
                                   status))

    statuses = fixture.get("expected_statuses")
    if statuses:
        actual = {finding["rule_id"]: finding["status"]
                  for finding in report["findings"]}
        for rule_id, status in statuses.items():
            if actual.get(rule_id) != status:
                failures.append("status.%s %s != expected %s"
                                % (rule_id, actual.get(rule_id), status))

    expected_missing = fixture.get("expected_missing_facts", [])
    actual_missing = report["preservation"]["missing"]
    if set(expected_missing) != set(actual_missing):
        failures.append("missing facts %s != expected %s"
                        % (sorted(actual_missing),
                           sorted(expected_missing)))

    expected_leaked = fixture.get("expected_leaked_facts", [])
    actual_leaked = report["voice_sample"]["leaked_personal_facts"]
    if set(expected_leaked) != set(actual_leaked):
        failures.append("leaked facts %s != expected %s"
                        % (sorted(actual_leaked),
                           sorted(expected_leaked)))
    return failures


def run_fixture(fixture, registry, registry_path="rules.json"):
    """Evaluate one linkedin-profile fixture against its expectations."""
    post_type = fixture.get("post_type")
    report = review_post(
        fixture["source"], post_type, registry,
        voice_sample=fixture.get("voice_sample"),
        sample_facts=tuple(fixture.get("sample_facts", ())),
        required_facts=tuple(fixture.get("required_facts", ())),
        author_habits=tuple(fixture.get("author_habits", ())),
        registry_path=registry_path)
    report["id"] = fixture["id"]
    report["expected_decision"] = fixture["expected_decision"]
    report["failures"] = fixture_failures(report, fixture)
    return report


def run_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the linkedin-profile fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "interface": INTERFACE,
            "schema": FIXTURE_SCHEMA,
            "version": registry.get("version", "unknown"),
            "total": len(fixtures),
            "passed": 0,
            "failed": len(fixtures),
            "failing_ids": [f.get("id", "?") if isinstance(f, dict) else "?"
                            for f in fixtures],
            "schema_errors": schema_errors,
            "gate_pass": False,
            "disclaimer": DISCLAIMER,
            "fixtures": [],
        }

    reports = [run_fixture(fixture, registry, registry_path=registry_path)
               for fixture in fixtures]
    failed = [report for report in reports if report["failures"]]
    return {
        "interface": INTERFACE,
        "schema": FIXTURE_SCHEMA,
        "version": registry.get("version", "unknown"),
        "total": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "failures": [{
            "id": report["id"],
            "post_type": report["post_type"],
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
        description="LinkedIn social profile review runner")
    subparsers = parser.add_subparsers(dest="command")

    review_p = subparsers.add_parser("review", help="review a post")
    review_p.add_argument("--source-text", required=True)
    review_p.add_argument("--post-type", required=True)
    review_p.add_argument("--voice-sample", default=None)
    review_p.add_argument("--sample-fact", action="append", default=[])
    review_p.add_argument("--required-fact", action="append", default=[])
    review_p.add_argument("--registry", default="rules.json")

    parser.add_argument("--fixtures", default=None,
                        help="run a fixture corpus and exit")
    parser.add_argument("--registry", default="rules.json")
    args = parser.parse_args()

    if args.fixtures:
        registry = load_registry(args.registry)
        data = load_json(args.fixtures)
        fixtures = data.get("evals", data)
        report = run_corpus(fixtures, registry, args.registry)
        print(json.dumps(report, indent=2))
        if report["schema_errors"] or report["failures"]:
            sys.exit(1)
        sys.exit(0)

    if args.command != "review":
        parser.print_help()
        sys.exit(2)

    registry = load_registry(args.registry)
    report = review_post(
        args.source_text, args.post_type, registry,
        voice_sample=args.voice_sample,
        sample_facts=tuple(args.sample_fact),
        required_facts=tuple(args.required_fact),
        registry_path=args.registry)
    print(json.dumps(report, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
