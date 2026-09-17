#!/usr/bin/env python3
"""Tagore-style substance report (issue #102).

Reviewed apurvrdx1/tagore at 1238743 (MIT). Tagore is already credited for
vocabulary and punchy closure; this ticket covers only its incremental
substance and contribution mechanisms. A passage can avoid every known
mechanical tell while remaining vague, consequence-free, or untrustworthy.
Folding that judgment into the Formulaic Writing Risk Score would change the
score's meaning and imply precision the evidence does not support, so this
runner keeps the substance group unscored and separate.

The opt-in report preserves Tagore's two groups:

  mechanics   Directness, Rhythm, Trust, Authenticity, Density
  substance   Specificity, Restraint, Voice

Every dimension result cites evidence, permits `unknown` and
`not-applicable`, and offers a question or repair direction without inventing
material. `unknown` is used when author facts or intent are missing (a quoted
opinion, a sample too short to measure). `not-applicable` is used when a
dimension is not owed by the medium (point of view and rhythm in a terse
reference entry). No result labels the text human or AI, and substance
results never enter the risk score or its score bands.

The runner also adopts the change-contribution contract from Tagore's
contributor guide: evidence of a distinct tell, one narrow rule, before and
after text, model and frequency context where known, and paired regression
fixtures (a positive case and a clean false-positive case). Tagore's scored
examples are candidate cases only; their thresholds are self-defined and are
not imported as Antislop targets.

Usage:
    python3 tools/substance.py --source-text "..." --medium argument
    cat text.txt | python3 tools/substance.py --medium reference
    python3 tools/substance.py --file text.txt --profile technical
    python3 tools/substance.py --proposal proposal.json
    python3 tools/substance.py --fixtures skills/antislop/evals/substance-fixtures.json
    python3 tools/substance.py --help

Exit codes:
    0 -- the report ran, or every fixture decision matched its expectation
    1 -- a fixture decision failed
    2 -- usage or input error
"""

import argparse
import json
import os
import re
import sys

import limits
from registry import load_registry
import drift
import fidelity
import score as scoring

INTERFACE = "antislop.substance"
SCHEMA = "tagore-substance-report-1"
CONTRIBUTION_SCHEMA = "tagore-contribution-contract-1"
FIXTURE_SCHEMA = "tagore-substance-fixtures-1"

MECHANICS = ("directness", "rhythm", "trust", "authenticity", "density")
SUBSTANCE_DIMS = ("specificity", "restraint", "voice")
DIMENSIONS = MECHANICS + SUBSTANCE_DIMS
STATUSES = ("evidenced", "unsupported", "unknown", "not-applicable")
MEDIUMS = ("argument", "explanation", "evocation", "narrative", "guide",
           "reference", "message")
PROFILES = ("general", "technical", "fiction")
FIXTURE_KINDS = ("report", "contribution")
CONTRACT_ITEMS = ("distinct_tell", "narrow_rule", "before_after", "context",
                  "regression_fixture")
CONTRACT_SOURCE = (
    "https://github.com/apurvrdx1/tagore/blob/"
    "1238743725cb2d731b780f237c82e0041c9b4c67/CONTRIBUTING.md"
)
SOURCE_NOTE = (
    "Reviewed apurvrdx1/tagore at 1238743 (MIT), CONTRIBUTING.md and "
    "SKILL.md two-group rubric."
)
SCORED_EXAMPLES_NOTE = (
    "Tagore scored examples are candidate cases only; their thresholds are "
    "self-defined and are not imported as Antislop targets."
)
LABEL_RULE = "No dimension result labels text human or AI."
SUBSTANCE_DISCLAIMER = (
    "Substance results report evidence for eight dimensions; they never "
    "prove AI authorship, never label text human or AI, and never change "
    "the Formulaic Writing Risk Score."
)
CONTRIBUTION_DISCLAIMER = (
    "Contribution validation checks a proposed rule change against the "
    "contribution contract; it never proves authorship and never accepts "
    "a change without paired fixtures."
)

# A metronomic run: RHYTHM_RUN consecutive sentences whose word counts all
# fall within RHYTHM_TOLERANCE words of each other.
RHYTHM_RUN = 3
RHYTHM_TOLERANCE = 2

# Dimensions a medium does not owe. Terse reference prose needs no point of
# view and no rhythm variation.
NOT_APPLICABLE = {
    "reference": ("rhythm", "voice"),
}

# Author-gap questions follow review.py's [TK: ...] marker convention.
# --------------------------------------------------------------------------

ANNOUNCEMENT_RE = re.compile(
    r"\b(?:let'?s\s+(?:dive in|dive into|explore|break (?:this|it) down|"
    r"walk through|look at|take a look at|see how|talk about)|"
    r"here'?s\s+(?:what you need to know|what we'?ll cover|what to expect|"
    r"the thing)|"
    r"in this (?:article|post|guide|essay|blog post|note)|"
    r"the rest of this (?:article|post|essay)|"
    r"without further ado|now let'?s|first,? let'?s|let me (?:walk|take|show|"
    r"share)|i wanted to (?:provide|share|give|walk)|"
    r"i'?d like to (?:provide|share|walk)|"
    r"this (?:article|post|essay) (?:will|aims to|covers)|"
    r"we'?ll (?:cover|look at|explore|discuss)|"
    r"(?:we are|we'?re) (?:excited|thrilled) to announce)\b",
    re.IGNORECASE,
)

HANDHOLD_RE = re.compile(
    r"\b(?:let me (?:explain|spell it out|be clear|put it simply)|"
    r"in other words|simply put|put simply|to put it simply|"
    r"what this means? is|what that means is|in layman'?s terms|"
    r"as you know|as we all know|needless to say|it goes without saying|"
    r"let'?s be clear|to be clear|for those unfamiliar|for the uninitiated|"
    r"to make a long story short|the point is|the takeaway is|"
    r"let me reiterate|in essence|at the end of the day)\b",
    re.IGNORECASE,
)

INAUTHENTIC_RE = re.compile(
    r"\b(?:i hope this helps|hope this helps|"
    r"let me know if (?:you have any questions|i can help|you'?d like)|"
    r"if you have any questions,? (?:please )?don'?t hesitate|"
    r"of course!?|certainly!?|great question!?|excellent question!?|"
    r"you'?re absolutely right|that'?s an excellent point|"
    r"as (?:an|the) (?:ai|language model|assistant)|"
    r"up to my last (?:training|update)|as of my last (?:training|update|"
    r"knowledge)|based on available information|"
    r"while specific details are (?:limited|scarce)|"
    r"i do not have (?:access to|information about))\b",
    re.IGNORECASE,
)

CUTTABLE_RE = re.compile(
    r"\b(?:in order to|due to the fact that|at this point in time|"
    r"it is important to note|it'?s important to note|it is worth noting|"
    r"it'?s worth noting|as we move forward|going forward|"
    r"at the end of the day|when it comes to|the fact that|"
    r"overall|in conclusion|in summary|as a whole|all in all|"
    r"we remain committed|we are committed|we believe in|"
    r"it is essential to|it is crucial to|it is critical to|"
    r"stands? as a testament|serves as a testament)\b",
    re.IGNORECASE,
)

VAGUE_RE = re.compile(
    r"\b(?:industry (?:observers|reports|leaders|analysts)|"
    r"experts (?:argue|say|believe|note|agree)|observers (?:have )?cited|"
    r"studies (?:show|suggest|indicate)|research (?:shows|indicates|"
    r"suggests)|many (?:organizations|companies|teams|people|developers)|"
    r"some (?:organizations|companies|teams|people|critics|developers)|"
    r"several (?:organizations|companies|teams|studies)|"
    r"a number of|numerous|various|certain\b|a range of|and more|and beyond|"
    r"things like that|and stuff|and things|this and that|"
    r"the (?:implications|significance|importance|landscape|ecosystem|space|"
    r"journey|future|power|potential|industry|sector) (?:are|is|of)\b|"
    r"it is (?:important|essential|crucial|critical|vital) (?:to|that)|"
    r"the results are (?:significant|remarkable|promising)|"
    r"significant progress|substantial progress|remarkable resilience|"
    r"important to us all|everyone involved|the whole team)\b",
    re.IGNORECASE,
)

PUFFERY_RE = re.compile(
    r"\b(?:groundbreaking|revolutioniz(?:e|ing)|transformative|"
    r"game[- ]changing|cutting[- ]edge|state[- ]of[- ]the[- ]art|"
    r"world[- ]class|industry[- ]leading|best[- ]in[- ]class|"
    r"unprecedented|remarkable|extraordinary|unmatched|revolutionary|"
    r"paradigm[- ]shift|next[- ]generation|seamless(?:ly)?|effortlessly|"
    r"effortless|powerful\s+(?:solution|platform|tool)|"
    r"robust\s+(?:set|suite|features)|comprehensive\s+(?:solution|suite|"
    r"platform)|production[- ]ready|enterprise[- ]grade|blazing[- ]fast|"
    r"stands? as a (?:testament|monument|witness)|a testament to|"
    r"marks? a (?:pivotal|milestone)|pivotal moment|key turning point|"
    r"paves? the way|heralds?|unlock(?:ing)? (?:the full|its|your)|"
    r"empowers? (?:individuals|teams|you|users)|"
    r"at the (?:forefront|cutting edge) of|important step forward|"
    r"significant milestone|crucial role|vital role|essential role|"
    r"integral part)\b",
    re.IGNORECASE,
)

STANCE_RE = re.compile(
    r"\b(?:i think|i believe|i find|i'?d rather|i prefer|i keep|"
    r"i'?m\s+(?:skeptical|convinced|not sure|torn|bothered|impressed)|"
    r"in my view|in my experience|from my perspective|as i see it|"
    r"we should|we shouldn'?t|we'?d rather|the problem is|"
    r"the real problem is|what gets me|what bothers me|what strikes me|"
    r"i genuinely|i don'?t know|i suspect|i'?m convinced|i want|"
    r"i wanted|my take|the way i see it|here'?s what gets me|"
    r"i was wrong|i should have|i'?m sorry|i keep coming back to|"
    r"the best option|the wrong call)\b",
    re.IGNORECASE,
)

STAKES_RE = re.compile(
    r"\b(?:without (?:it|this|that)|if\s+(?:we|it|this|that|the)|"
    r"the result|results? in|leads? to|this means|that would|the cost|"
    r"the risk|the stakes|consequences?|depends? on|because of this|"
    r"that'?s why|which (?:means|leaves)|no buffer|rollback|blocker|"
    r"deadline|slip a week|i should have caught|the on-call|paged|outage|"
    r"downtime|if anything goes wrong|when something fails|stalls|"
    r"grinds to a halt)\b",
    re.IGNORECASE,
)

DIGIT_RE = re.compile(r"\$\d+(?:[.,]\d+)?\b|\b\d+(?:[.,]\d+)?\s*(?:%|x|\u00d7)?\b")
LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
URL_RE = re.compile(r"https?://\S+")
CODE_RE = re.compile(r"`[^`\n]*`")
PROPER_RE = re.compile(
    r"\b(?:[A-Z][a-z0-9]+|[A-Z]{2,}[A-Za-z0-9]*|[A-Z][a-z0-9]*[A-Z][A-Za-z0-9]*)\b"
)
CONCRETE_STOP = frozenset((
    "the", "it", "we", "i", "a", "an", "this", "that", "they", "he", "she",
    "and", "but", "in", "on", "at", "as", "so", "or", "for", "you", "our",
    "my", "your", "to", "of", "is", "are", "was", "were", "these", "those",
    "each", "every", "all", "no", "not", "if", "when", "while", "there",
    "here", "everything", "everyone", "everybody", "nobody", "somebody",
    "someone", "something", "anything", "nothing", "who", "what", "which",
    "why", "how", "we're", "we've", "i'm", "i've", "it's", "that's", "one",
))

AUTHORSHIP_PHRASE_RE = re.compile(
    r"sounds human|is human\b|written by a human|written by an ai|"
    r"ai-generated|proves human|proves ai\b|human-authored|reads as human|"
    r"clearly human|definitely human|definitely ai\b|is not human\b",
    re.IGNORECASE,
)

EM_DASH_RE = re.compile(r"\u2014|\u2013| -- |->")


def _quoted_spans(text):
    return [(match.start(), match.end())
            for match in fidelity.QUOTED_RE.finditer(text)]


def _overlaps(start, end, spans):
    return any(span_start < end and start < span_end
               for span_start, span_end in spans)


def _excerpts(text, matches, limit=4):
    excerpts = []
    for match in matches[:limit]:
        excerpt = text[match.start():min(len(text), match.end() + 100)]
        excerpt = excerpt.strip()
        if match.start() > 0 and not excerpt.startswith((" ", "\t")):
            excerpt = "..." + excerpt
        if len(excerpt) > 120:
            excerpt = excerpt[:120].rstrip() + "..."
        excerpts.append(excerpt)
    return excerpts


def _concrete_spans(text):
    """Concrete referents: numbers, links, URLs, code, and non-stopword
    capitalized tokens. Sentence-initial common words are never concrete."""
    spans = []
    for pattern in (DIGIT_RE, LINK_RE, URL_RE, CODE_RE):
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end(), match.group(0)))
    for match in PROPER_RE.finditer(text):
        token = match.group(0)
        if token.lower() in CONCRETE_STOP:
            continue
        spans.append((match.start(), match.end(), token))
    spans.sort(key=lambda span: span[0])
    return spans


def _concrete_tokens(spans, limit=4):
    seen = []
    for _start, _end, token in spans:
        if token not in seen:
            seen.append(token)
        if len(seen) >= limit:
            break
    return seen


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part for part in parts if part.strip()]


def _word_count(sentence):
    return len(re.findall(r"[A-Za-z0-9']+", sentence))


def _not_applicable(text, medium, registry, profile, quoted_spans):
    return ("not-applicable",
            ["The %s medium does not owe this dimension; no judgment is "
             "forced." % medium],
            "Not applicable to this medium; nothing to fix.")


def detect_directness(text, medium, registry, profile, quoted_spans):
    """Statements or announcements? Signposting and throat-clearing openers
    announce instead of stating the thing."""
    matches = [m for m in ANNOUNCEMENT_RE.finditer(text)
               if not _overlaps(m.start(), m.end(), quoted_spans)]
    if matches:
        return ("unsupported", _excerpts(text, matches),
                "Cut the announcement or signposting; state the thing "
                "directly.")
    return ("evidenced",
            ["No announcement or signposting spans found; the prose opens "
             "with statements."],
            "Keep statements; open with the point.")


def detect_rhythm(text, medium, registry, profile, quoted_spans):
    """Varied or metronomic? A uniform run of consecutive sentence lengths is
    metronomic; terse reference prose does not owe variation."""
    if "rhythm" in NOT_APPLICABLE.get(medium, ()):
        return _not_applicable(text, medium, registry, profile, quoted_spans)
    sentences = _sentences(text)
    lengths = [_word_count(sentence) for sentence in sentences]
    if len(lengths) < RHYTHM_RUN:
        return ("unknown",
                ["Only %d sentence(s) in the sample; rhythm variation "
                 "cannot be measured." % len(lengths)],
                "[TK: is the passage meant to stay this short, or should "
                "sentence length vary?]")
    for index in range(len(lengths) - RHYTHM_RUN + 1):
        window = lengths[index:index + RHYTHM_RUN]
        if max(window) - min(window) <= RHYTHM_TOLERANCE:
            run = sentences[index:index + RHYTHM_RUN]
            return ("unsupported",
                    ["Sentence lengths %s form a uniform run: %s"
                     % (window, " | ".join(run))],
                    "Vary sentence length; break the uniform run so no three "
                    "consecutive sentences share one length.")
    return ("evidenced",
            ["Sentence lengths vary (min %d, max %d words)."
             % (min(lengths), max(lengths))],
            "Keep the varied rhythm.")


def detect_trust(text, medium, registry, profile, quoted_spans):
    """Respects reader intelligence? Hand-holding and over-explanation tell
    the reader what they already know."""
    matches = [m for m in HANDHOLD_RE.finditer(text)
               if not _overlaps(m.start(), m.end(), quoted_spans)]
    if matches:
        return ("unsupported", _excerpts(text, matches),
                "Cut the hand-holding or over-explanation; trust the reader "
                "to follow.")
    return ("evidenced",
            ["No hand-holding or over-explanation spans found."],
            "Keep the direct register.")


def detect_authenticity(text, medium, registry, profile, quoted_spans):
    """Avoids detectable correspondence, disclosure, or sycophancy markers?
    The review cites the markers it can see and never claims the text sounds
    human."""
    matches = [m for m in INAUTHENTIC_RE.finditer(text)
               if not _overlaps(m.start(), m.end(), quoted_spans)]
    if matches:
        return ("unsupported", _excerpts(text, matches),
                "Cut the correspondence, disclosure, or sycophancy "
                "artifact; write as the author.")
    return ("evidenced",
            ["No correspondence, disclosure, or sycophancy markers found."],
            "Keep the direct voice.")


def detect_density(text, medium, registry, profile, quoted_spans):
    """Anything cuttable? Filler and ceremony spans carry no information."""
    findings, _skipped, _metrics = scoring.detect_findings(
        text, registry, profile)
    excerpts = [finding["excerpt"] for finding in findings
                if finding["category"] in ("filler", "chatbot")]
    matches = [m for m in CUTTABLE_RE.finditer(text)
               if not _overlaps(m.start(), m.end(), quoted_spans)]
    excerpts.extend(_excerpts(text, matches))
    if excerpts:
        return ("unsupported", excerpts[:4],
                "Cut the filler, ceremony, or padding; keep only what "
                "carries information.")
    return ("evidenced",
            ["No cuttable filler or ceremony spans found."],
            "Keep the density.")


def detect_specificity(text, medium, registry, profile, quoted_spans):
    """Names the actual thing, or gestures at categories? Vague attributions
    and category gestures are unsupported; named referents are evidenced;
    neither signal is an author-intent gap."""
    vague = [m for m in VAGUE_RE.finditer(text)
             if not _overlaps(m.start(), m.end(), quoted_spans)]
    concrete = [span for span in _concrete_spans(text)
                if not _overlaps(span[0], span[1], quoted_spans)]
    if vague:
        return ("unsupported", _excerpts(text, vague),
                "[TK: name the actual thing, number, person, or event "
                "instead of the category.]")
    if concrete:
        tokens = _concrete_tokens(concrete)
        return ("evidenced",
                ["Concrete referents present: %s." % ", ".join(tokens)],
                "Keep naming the actual thing.")
    return ("unknown",
            ["No concrete referent and no vague gesture found; the review "
             "cannot tell what the passage names."],
            "[TK: what is the actual thing or example this passage points "
            "at?]")


def detect_restraint(text, medium, registry, profile, quoted_spans):
    """States things at their actual size, or puffs them up? Superlatives and
    significance inflation are unsupported; specific facts are evidenced."""
    puffery = [m for m in PUFFERY_RE.finditer(text)
               if not _overlaps(m.start(), m.end(), quoted_spans)]
    concrete = _concrete_spans(text)
    if puffery:
        return ("unsupported", _excerpts(text, puffery),
                "State the thing at its actual size; cut the superlative or "
                "significance inflation.")
    if concrete:
        return ("evidenced",
                ["No puffery spans found; specific facts carry the claims."],
                "Keep the measured register.")
    return ("unknown",
            ["No puffery and no specific fact to anchor the claim."],
            "[TK: what is the actual size or basis of this claim?]")


def detect_voice(text, medium, registry, profile, quoted_spans):
    """Has a point of view, or neutral wire-copy? A stance with a consequence
    is evidenced; a stance without stakes is thin; stance hidden behind
    quotes is unknown because the author's intent is missing."""
    if "voice" in NOT_APPLICABLE.get(medium, ()):
        return _not_applicable(text, medium, registry, profile, quoted_spans)
    stance_matches = list(STANCE_RE.finditer(text))
    stakes_matches = list(STAKES_RE.finditer(text))
    outside_stance = [m for m in stance_matches
                      if not _overlaps(m.start(), m.end(), quoted_spans)]
    outside_stakes = [m for m in stakes_matches
                      if not _overlaps(m.start(), m.end(), quoted_spans)]
    if outside_stance:
        if outside_stakes:
            evidence = (_excerpts(text, outside_stance)
                        + _excerpts(text, outside_stakes))
            return ("evidenced", evidence[:4],
                    "Keep the opinion and its consequence; the position is "
                    "grounded.")
        return ("unsupported", _excerpts(text, outside_stance),
                "[TK: what depends on this opinion, and what would change "
                "if it failed?]")
    inside_stance = [m for m in stance_matches
                     if _overlaps(m.start(), m.end(), quoted_spans)]
    inside_stakes = [m for m in stakes_matches
                     if _overlaps(m.start(), m.end(), quoted_spans)]
    if inside_stance or inside_stakes:
        return ("unknown",
                ["Stance and stakes appear only inside quoted material; the "
                 "author's own position is not established."],
                "[TK: what is the author's own position here?]")
    return ("unsupported",
            ["No first-person stance or value judgment found; the prose "
             "reports without a position."],
            "[TK: what is the author's position on this?]")


DETECTORS = {
    "directness": detect_directness,
    "rhythm": detect_rhythm,
    "trust": detect_trust,
    "authenticity": detect_authenticity,
    "density": detect_density,
    "specificity": detect_specificity,
    "restraint": detect_restraint,
    "voice": detect_voice,
}


def report_text(text, medium, registry, profile="general"):
    """One passage's two-group substance report, separate from risk."""
    limits.check_input_size(text)
    if medium not in MEDIUMS:
        raise ValueError("unknown medium %r" % medium)
    quoted_spans = _quoted_spans(text)
    results = []
    for dimension in DIMENSIONS:
        status, evidence, next_step = DETECTORS[dimension](
            text, medium, registry, profile, quoted_spans)
        results.append({
            "dimension": dimension,
            "group": "mechanics" if dimension in MECHANICS else "substance",
            "status": status,
            "evidence": evidence,
            "next_step": next_step,
        })

    risk = {}
    try:
        risk_result = scoring.score_text(text, registry, profile)
        risk = {
            "score": risk_result["score"],
            "band": risk_result["band"],
            "separate": True,
            "advisory": True,
            "authorship_evidence": False,
            "disclaimer": drift.OBSERVATION_DISCLAIMER,
        }
    except Exception:  # noqa: BLE001 -- risk is advisory, never a gate
        risk = {"score": None, "band": None, "separate": True,
                "advisory": True, "authorship_evidence": False,
                "disclaimer": drift.OBSERVATION_DISCLAIMER}

    return {
        "interface": INTERFACE,
        "schema": SCHEMA,
        "version": registry.get("version", "unknown"),
        "mode": "substance",
        "medium": medium,
        "profile": profile,
        "groups": {
            "mechanics": [r for r in results if r["group"] == "mechanics"],
            "substance": [r for r in results if r["group"] == "substance"],
        },
        "risk": risk,
        "label": None,
        "meta": {
            "disclaimer": SUBSTANCE_DISCLAIMER,
            "source": SOURCE_NOTE,
            "scored_examples_note": SCORED_EXAMPLES_NOTE,
            "label_rule": LABEL_RULE,
        },
    }


def _contains_pattern(text, pattern):
    if not pattern:
        return False
    try:
        return re.search(pattern, text, re.IGNORECASE) is not None
    except re.error:
        return pattern.lower() in text.lower()


def validate_contribution(proposal, registry):
    """Check a proposed rule change against the Tagore contribution contract.

    Each contract item must be satisfied: evidence of a distinct tell, one
    narrow rule, a real before and after pair that proves the pattern is
    gone, model and frequency context where known, and paired regression
    fixtures (a positive case and a clean false-positive case).
    """
    failures = []
    items = {}

    tell = proposal.get("distinct_tell")
    if isinstance(tell, str) and tell.strip():
        items["distinct_tell"] = {
            "item": "distinct_tell", "satisfied": True,
            "evidence": "evidence of a distinct tell recorded",
        }
    else:
        items["distinct_tell"] = {
            "item": "distinct_tell", "satisfied": False,
            "evidence": "missing evidence that the pattern is a distinct "
                        "tell",
        }
        failures.append("distinct_tell: evidence of a distinct tell is "
                        "missing")

    rule = proposal.get("rule")
    narrow = (isinstance(rule, dict)
              and all(isinstance(rule.get(field), str) and rule[field].strip()
                      for field in ("id", "name", "pattern", "rewrite")))
    extra_rules = proposal.get("rules")
    if isinstance(extra_rules, list) and len(extra_rules) > 1:
        narrow = False
        failures.append("narrow_rule: more than one rule in one proposal")
    if narrow:
        items["narrow_rule"] = {
            "item": "narrow_rule", "satisfied": True,
            "evidence": "one narrow rule with a single rewrite instruction",
        }
    else:
        items["narrow_rule"] = {
            "item": "narrow_rule", "satisfied": False,
            "evidence": "missing one narrow rule with id, name, pattern, and "
                        "a single rewrite",
        }
        if not any("narrow_rule" in failure for failure in failures):
            failures.append("narrow_rule: one narrow rule with id, name, "
                            "pattern, and a single rewrite is required")

    before = proposal.get("before_text")
    after = proposal.get("after_text")
    pattern = rule.get("pattern", "") if isinstance(rule, dict) else ""
    before_after_ok = True
    if not (isinstance(before, str) and before.strip()):
        failures.append("before_after: before text is missing")
        before_after_ok = False
    if not (isinstance(after, str) and after.strip()):
        failures.append("before_after: after text is missing")
        before_after_ok = False
    if before_after_ok and before == after:
        failures.append("before_after: before and after text are identical")
        before_after_ok = False
    if before_after_ok and pattern:
        if not _contains_pattern(before, pattern):
            failures.append("before_after: the before text does not contain "
                            "the rule pattern")
            before_after_ok = False
        if _contains_pattern(after, pattern):
            failures.append("before_after: the after text still contains the "
                            "rule pattern")
            before_after_ok = False
    items["before_after"] = {
        "item": "before_after", "satisfied": before_after_ok,
        "evidence": ("a real before and after pair with the pattern gone in "
                     "the after text" if before_after_ok
                     else "the before and after pair does not satisfy the "
                          "contract"),
    }

    model_ctx = proposal.get("model_context")
    freq_ctx = proposal.get("frequency_context")
    context_unknown = proposal.get("context_unknown", False) is True
    context_ok = bool((isinstance(model_ctx, str) and model_ctx.strip())
                      or (isinstance(freq_ctx, str) and freq_ctx.strip())
                      or context_unknown)
    if not context_ok:
        failures.append("context: model and frequency context are missing; "
                        "record them or mark context_unknown")
    items["context"] = {
        "item": "context", "satisfied": context_ok,
        "evidence": ("model and frequency context recorded" if context_ok
                     else "no model or frequency context recorded"),
    }

    fixtures = proposal.get("fixtures")
    positive = fixtures.get("positive", []) if isinstance(fixtures, dict) \
        else []
    clean = fixtures.get("clean", []) if isinstance(fixtures, dict) else []
    fix_ok = True
    fix_messages = []
    if not isinstance(positive, list) or not positive:
        fix_messages.append("a positive fixture (the pattern present) is "
                            "missing")
        fix_ok = False
    if not isinstance(clean, list) or not clean:
        fix_messages.append("a clean false-positive fixture is missing")
        fix_ok = False
    if pattern and fix_ok:
        for index, fixture in enumerate(positive):
            text = fixture.get("text", "") if isinstance(fixture, dict) else ""
            if not _contains_pattern(text, pattern):
                fix_messages.append("positive fixture %d does not contain the "
                                    "pattern" % index)
                fix_ok = False
        for index, fixture in enumerate(clean):
            text = fixture.get("text", "") if isinstance(fixture, dict) else ""
            if _contains_pattern(text, pattern):
                fix_messages.append("clean fixture %d contains the pattern; "
                                    "it is not a false-positive case" % index)
                fix_ok = False
    for message in fix_messages:
        failures.append("regression_fixture: " + message)
    items["regression_fixture"] = {
        "item": "regression_fixture", "satisfied": fix_ok,
        "evidence": ("paired positive and clean fixtures" if fix_ok
                     else "; ".join(fix_messages)),
    }

    accepted = all(item["satisfied"] for item in items.values())
    return {
        "interface": INTERFACE,
        "schema": CONTRIBUTION_SCHEMA,
        "version": registry.get("version", "unknown"),
        "accepted": accepted,
        "items": [items[name] for name in CONTRACT_ITEMS],
        "failures": failures,
        "label": None,
        "meta": {
            "source": CONTRACT_SOURCE,
            "disclaimer": CONTRIBUTION_DISCLAIMER,
        },
    }


def label_errors(report):
    """Check no report result labels the text human or AI."""
    errors = []
    if report.get("label") is not None:
        errors.append("report label must be null")
    for group in ("mechanics", "substance"):
        for result in report.get("groups", {}).get(group, []):
            dimension = result.get("dimension")
            status = result.get("status")
            if status not in STATUSES:
                errors.append("%s status %r is not a substance status"
                              % (dimension, status))
            for field in ("evidence", "next_step"):
                for value in result.get(field, []):
                    if AUTHORSHIP_PHRASE_RE.search(value):
                        errors.append("%s %s labels the text: %r"
                                      % (dimension, field, value))
    return errors


def validate_fixture(fixture, seen_ids):
    """Schema-validate one substance fixture. Returns error strings."""
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
        return errors

    for field in ("label_provenance", "source"):
        if not (isinstance(fixture.get(field), str) and fixture[field].strip()):
            errors.append("%s: %s must be a non-empty string" % (where, field))

    if kind == "report":
        text = fixture.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append("%s: 'text' must be a non-empty string" % where)
        medium = fixture.get("medium", "argument")
        if medium not in MEDIUMS:
            errors.append("%s: medium must be one of %s"
                          % (where, ", ".join(MEDIUMS)))
        profile = fixture.get("profile", "general")
        if profile not in PROFILES:
            errors.append("%s: profile must be one of %s"
                          % (where, ", ".join(PROFILES)))
        statuses = fixture.get("expected_statuses", {})
        if not isinstance(statuses, dict):
            errors.append("%s: expected_statuses must be an object" % where)
        else:
            for dimension, status in statuses.items():
                if dimension not in DIMENSIONS:
                    errors.append("%s: expected_statuses names unknown "
                                  "dimension '%s'" % (where, dimension))
                if status not in STATUSES:
                    errors.append("%s: expected_statuses['%s'] must be one "
                                  "of %s" % (where, dimension,
                                             ", ".join(STATUSES)))
        score = fixture.get("expected_risk_score")
        if score is not None and (not isinstance(score, int)
                                  or isinstance(score, bool)):
            errors.append("%s: expected_risk_score must be an integer"
                          % where)
        if not isinstance(fixture.get("expected_label_none", True), bool):
            errors.append("%s: expected_label_none must be a boolean" % where)
        rationale = fixture.get("false_positive_rationale")
        if rationale is not None and (not isinstance(rationale, str)
                                      or not rationale.strip()):
            errors.append("%s: false_positive_rationale must be a non-empty "
                          "string" % where)
        notes = fixture.get("reviewer_notes")
        if notes is not None and (not isinstance(notes, str)
                                  or not notes.strip()):
            errors.append("%s: reviewer_notes must be a non-empty string"
                          % where)
    else:
        if not isinstance(fixture.get("expected_accepted"), bool):
            errors.append("%s: expected_accepted must be a boolean" % where)
        expected_failures = fixture.get("expected_failures", [])
        if not isinstance(expected_failures, list) or any(
                not isinstance(item, str) or not item
                for item in expected_failures):
            errors.append("%s: expected_failures must be a list of non-empty "
                          "strings" % where)
        rule = fixture.get("rule")
        if rule is not None and not isinstance(rule, dict):
            errors.append("%s: rule must be an object" % where)
        fixtures = fixture.get("fixtures")
        if fixtures is not None and not isinstance(fixtures, dict):
            errors.append("%s: fixtures must be an object" % where)
    return errors


def fixture_failures(report, fixture):
    """Compare a computed report against its fixture expectations."""
    failures = []
    if fixture["kind"] == "report":
        expected = fixture.get("expected_statuses", {})
        by_dimension = {result["dimension"]: result
                        for result in (report["groups"]["mechanics"]
                                       + report["groups"]["substance"])}
        for dimension, status in expected.items():
            result = by_dimension.get(dimension)
            if result is None:
                failures.append("dimension '%s' missing from the report"
                                % dimension)
            elif result["status"] != status:
                failures.append("dimension '%s' expected status %s, got %s"
                                % (dimension, status, result["status"]))
        for dimension in DIMENSIONS:
            result = by_dimension.get(dimension)
            if result is None:
                continue
            if not result.get("evidence"):
                failures.append("dimension '%s' has no evidence" % dimension)
            if not result.get("next_step"):
                failures.append("dimension '%s' has no next step" % dimension)
        if fixture.get("expected_label_none", True) and report["label"] \
                is not None:
            failures.append("report label is not null")
        score = fixture.get("expected_risk_score")
        if score is not None and report["risk"].get("score") != score:
            failures.append("expected risk score %s, got %s"
                            % (score, report["risk"].get("score")))
        for error in label_errors(report):
            failures.append(error)
    else:
        if report["accepted"] != fixture["expected_accepted"]:
            failures.append("expected accepted %s, got %s"
                            % (fixture["expected_accepted"],
                               report["accepted"]))
        for expected in fixture.get("expected_failures", []):
            if not any(expected in failure for failure in report["failures"]):
                failures.append("missing expected failure containing %r"
                                % expected)
    return failures


def run_report_fixture(fixture, registry):
    report = report_text(fixture["text"], fixture.get("medium", "argument"),
                         registry, fixture.get("profile", "general"))
    report["id"] = fixture["id"]
    report["failures"] = fixture_failures(report, fixture)
    return report


def run_contribution_fixture(fixture, registry):
    report = validate_contribution(fixture, registry)
    report["id"] = fixture["id"]
    report["failures"] = fixture_failures(report, fixture)
    return report


def run_corpus(fixtures, registry, registry_path="rules.json"):
    """Validate and evaluate the substance fixture corpus."""
    schema_errors = []
    seen_ids = set()
    for fixture in fixtures:
        schema_errors.extend(validate_fixture(fixture, seen_ids))

    if schema_errors:
        return {
            "interface": INTERFACE,
            "schema": FIXTURE_SCHEMA,
            "version": registry.get("version", "unknown"),
            "fixture_count": len(fixtures),
            "passed": 0,
            "failed": len(fixtures),
            "failing_ids": [fixture.get("id", "?") for fixture in fixtures],
            "schema_errors": schema_errors,
            "gate_pass": False,
            "disclaimer": SUBSTANCE_DISCLAIMER,
            "fixtures": [],
        }

    reports = []
    for fixture in fixtures:
        if fixture["kind"] == "report":
            reports.append(run_report_fixture(fixture, registry))
        else:
            reports.append(run_contribution_fixture(fixture, registry))
    failed = [report for report in reports if report["failures"]]
    failure_rows = []
    for report in failed:
        fixture = next((f for f in fixtures if f.get("id") == report["id"]), {})
        if fixture.get("kind") == "contribution":
            expected = fixture.get("expected_accepted")
            got = report.get("accepted")
        else:
            expected = fixture.get("expected_statuses", {})
            got = {result["dimension"]: result["status"]
                   for result in (report["groups"]["mechanics"]
                                  + report["groups"]["substance"])}
        failure_rows.append({
            "id": report["id"],
            "kind": fixture.get("kind", "?"),
            "expected": expected,
            "got": got,
            "findings": report["failures"],
        })
    return {
        "interface": INTERFACE,
        "schema": FIXTURE_SCHEMA,
        "version": registry.get("version", "unknown"),
        "fixture_count": len(reports),
        "passed": len(reports) - len(failed),
        "failed": len(failed),
        "failing_ids": [report["id"] for report in failed],
        "failures": failure_rows,
        "schema_errors": schema_errors,
        "gate_pass": not schema_errors and not failed,
        "disclaimer": SUBSTANCE_DISCLAIMER,
        "fixtures": reports,
    }


def load_json(path):
    return limits.load_json_file(path)


def _read_document(path):
    text = limits.read_text_file(path, "document %s" % path)
    if not text.strip():
        raise ValueError("empty input: %s" % path)
    return text


def main():
    parser = argparse.ArgumentParser(description="Antislop Tagore-style "
                                                 "substance report")
    parser.add_argument("--source-text", default=None,
                        help="Text to report on (never edited)")
    parser.add_argument("--file", default=None,
                        help="Path to a single artifact to report on")
    parser.add_argument("--medium", default="argument",
                        help="Medium routing: one of %s (default: argument)"
                             % ", ".join(MEDIUMS))
    parser.add_argument("--profile", default="general",
                        help="Writing profile (default: general)")
    parser.add_argument("--proposal", default=None,
                        help="Path to a JSON rule-change proposal to validate "
                             "against the contribution contract")
    parser.add_argument("--registry", default="rules.json",
                        help="Path to rule registry (default: rules.json)")
    parser.add_argument("--expect-version", default=None,
                        help="Require the registry to be at this version")
    parser.add_argument("--fixtures", default=None,
                        help="Run the substance fixture corpus instead of "
                             "reporting on input")
    args = parser.parse_args()

    registry = load_registry(args.registry)
    if args.expect_version and registry.get("version") != args.expect_version:
        print(json.dumps({
            "error": "registry version %s does not match --expect-version %s"
                     % (registry.get("version"), args.expect_version),
        }, indent=2))
        sys.exit(2)

    if args.profile not in registry.get("profiles", {}):
        print(json.dumps({
            "error": "unknown profile '%s'. Valid: %s"
                     % (args.profile, sorted(registry.get("profiles", {}))),
        }, indent=2))
        sys.exit(2)

    if args.fixtures:
        if not os.path.exists(args.fixtures):
            print(json.dumps({"error": "fixture corpus not found: %s"
                              % args.fixtures}, indent=2))
            sys.exit(2)
        fixtures = load_json(args.fixtures)
        report = run_corpus(fixtures.get("evals", fixtures), registry,
                            args.registry)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["gate_pass"] else 1)

    if args.proposal:
        if not os.path.exists(args.proposal):
            print(json.dumps({"error": "proposal file not found: %s"
                              % args.proposal}, indent=2))
            sys.exit(2)
        proposal = load_json(args.proposal)
        report = validate_contribution(proposal, registry)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["accepted"] else 1)

    if args.source_text is not None:
        try:
            text = limits.check_input_size(args.source_text)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
    elif args.file:
        if not os.path.exists(args.file):
            print(json.dumps({"error": "file not found: %s" % args.file},
                             indent=2))
            sys.exit(2)
        try:
            text = _read_document(args.file)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
    elif not sys.stdin.isatty():
        try:
            text = limits.read_text(sys.stdin)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            sys.exit(2)
        if not text.strip():
            print(json.dumps({"error": "Empty input"}, indent=2))
            sys.exit(2)
    else:
        print(json.dumps({"error": "No input. Use --source-text, --file, "
                                    "--proposal, --fixtures, or pipe text."},
                         indent=2))
        sys.exit(2)

    report = report_text(text, args.medium, registry, args.profile)
    print(json.dumps(report, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
