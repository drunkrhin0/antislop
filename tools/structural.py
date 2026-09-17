#!/usr/bin/env python3
"""Vale-style deterministic structural checks (issue #88).

A standard-library detector interface for selected existence, sequence,
repetition, and document metrics. Each detector maps a stable condition in
the text to a finding carrying an exact span or document-level evidence.

The core rules, Tengo metric scripts, general fixtures, and false-positive
fixtures from tbhb/vale-ai-tells (d888d56, MIT) are design evidence only,
not a runtime dependency.

Findings carry a signal:
  strict   -- deterministic condition; deducts the rule's base weight when
              scored
  advisory -- metric or threshold condition; reported for context and never
              an authorship claim

Every metric states its sample-size minimum. Metrics never prove AI
authorship.

Usage:
    python3 tools/structural.py --file text.txt --profile general
    python3 tools/structural.py --stdin --profile general
    echo "text" | python3 tools/structural.py --profile general
    python3 tools/structural.py --help

Exit codes:
    0 -- no findings
    1 -- advisory findings only
    2 -- at least one strict finding
    3 -- usage or input error
"""

import argparse
import json
import math
import os
import re
import sys

import limits
from findings import signal as _signal, short_excerpt as _short_excerpt

from registry import load_registry, filter_rules_by_profile
import density
import mechanism

SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")
FENCE_RE = re.compile(r"(?s)```.*?```")
COMMENT_RE = re.compile(r"<!--.{0,1000}?-->")
WORD_RE = re.compile(r"[A-Za-z0-9']+")
NON_ALPHA_LEAD_RE = re.compile(r"^[^a-z]+")
LIST_PREFIXES = ("- ", "* ", "1.", "- [", "2.", "3.", "4.", "5.", "6.", "7.",
                 "8.", "9.")

SENTENCE_CV_LIMIT = 0.30
SENTENCE_MIN_COUNT = 5
SENTENCE_MEAN_MIN = 12.0
SENTENCE_MIN_WORDS = 3

PARAGRAPH_CV_LIMIT = 0.25
PARAGRAPH_MIN_COUNT = 4
PARAGRAPH_MIN_WORDS = 30

START_REP_SENTENCE_MIN = 6
START_REP_RATIO = 0.30
START_REP_COUNT_MIN = 3

TRANSITION_REP_COUNT = 3
TRANSITIONS = (
    "in addition", "for instance", "for example", "in particular", "moreover",
    "furthermore", "additionally", "consequently", "subsequently",
    "nevertheless", "conversely", "accordingly", "hence", "thus",
    "therefore", "specifically", "notably", "importantly", "crucially",
    "essentially",
)

SIMILARITY_MIN_WORDS = 8
SIMILARITY_JACCARD = 0.60
SIMILARITY_MIN_SHARED = 6
DUPLICATION_JACCARD = 0.90

TRICOLON_MIN_COUNT = 4
TRICOLON_LIST_RATIO = 0.60
TRICOLON_DENSITY = 0.20

PASSIVE_MIN_SENTENCES = 6
PASSIVE_MIN_COUNT = 3
PASSIVE_RATIO = 0.35

PASSIVE_RE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)"
    r"(?:\s+(?:not|never|[a-z]+ly))?\s+"
    r"([a-z][a-z]+ed|done|made|given|taken|seen|known|shown|found|held|"
    r"kept|left|lost|meant|put|read|run|said|sent|set|told|thought|"
    r"understood|written|built|brought|bought|caught|chosen|drawn|driven|"
    r"eaten|fallen|felt|gotten|gone|grown|heard|hidden|hit|led|paid|"
    r"proven|sold|spent|spoken|spread|stolen|taught|thrown|won|broken|"
    r"begun|cut)\b",
    re.IGNORECASE,
)

PASSIVE_ADJECTIVES = {
    "mixed", "tired", "excited", "interested", "bored", "surprised",
    "worried", "concerned", "prepared", "involved", "related", "located",
    "connected", "designed", "expected", "required", "based", "limited",
    "combined", "committed", "dedicated", "focused", "satisfied", "pleased",
    "confused", "disappointed", "exhausted", "overwhelmed", "annoyed",
    "scared", "frightened", "alarmed", "fascinated", "puzzled", "shocked",
    "embarrassed", "accustomed", "crowded", "qualified", "specialized",
    "educated", "skilled", "trained", "organized", "established", "united",
    "blessed", "alleged", "designated", "determined", "documented",
    "entitled", "intended", "marked", "noted", "painted", "reserved",
    "situated", "stated", "supposed",
}


def _finding(rule, start, end, message, excerpt, signal, evidence, sample=None):
    return {
        "rule_id": rule["id"],
        "category": rule["category"],
        "severity": rule["severity"],
        "base_weight": rule["base_weight"],
        "signal": signal,
        "start": start,
        "end": end,
        "message": message,
        "repair": rule.get("correction", ""),
        "excerpt": excerpt,
        "evidence": evidence,
        "sample": sample or {},
    }


def _insufficient(metric, required, observed):
    return {
        "metric": metric,
        "state": "insufficient-sample",
        "required": required,
        "observed": observed,
        "disclaimer": "Metric never proves AI authorship.",
    }


def _sections(text):
    """Split text into heading-delimited sections with original offsets.

    A section is the prose after a markdown heading (heading excluded), plus
    everything before the first heading. This mirrors Vale's split so format
    diversity across headings does not mask uniformity within a section.
    """
    matches = list(re.finditer(r"(?m)^#{1,6}\s+[^\n]+\n", text))
    if not matches:
        return [(0, len(text), text)]
    sections = []
    prev_end = 0
    for m in matches:
        if m.start() > prev_end:
            sections.append((prev_end, m.start(), text[prev_end:m.start()]))
        prev_end = m.end()
    if prev_end < len(text):
        sections.append((prev_end, len(text), text[prev_end:]))
    return sections


def _prose_flat(section_body):
    """Prose-only text for a section: lists, tables, and headings stripped."""
    cleaned = FENCE_RE.sub(" ", section_body)
    if "-->" in cleaned:
        cleaned = COMMENT_RE.sub(" ", cleaned)
    lines = []
    for line in cleaned.split("\n"):
        t = line.strip()
        if not t:
            continue
        if t.startswith("#") or t.startswith(LIST_PREFIXES) or t.startswith("|"):
            continue
        lines.append(t)
    return " ".join(lines)


def _sentence_spans(flat):
    """Character spans of sentences in flat prose text."""
    spans = []
    start = 0
    for m in SENTENCE_SPLIT_RE.finditer(flat):
        end = m.start()
        if end > start:
            spans.append((start, end))
        start = m.end()
    if start < len(flat):
        spans.append((start, len(flat)))
    return spans


def _sentence_lengths(flat):
    lengths = []
    for a, b in _sentence_spans(flat):
        n = len(WORD_RE.findall(flat[a:b]))
        if n >= SENTENCE_MIN_WORDS:
            lengths.append(n)
    return lengths


def _sentence_first_words(flat):
    words = []
    for a, b in _sentence_spans(flat):
        m = WORD_RE.search(flat[a:b])
        if m is None:
            continue
        w = NON_ALPHA_LEAD_RE.sub("", m.group(0).lower())
        if len(w) >= 2 and not w.isdigit():
            words.append(w)
    return words


def _std_dev(values):
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance), mean


def _paragraph_spans(section_body):
    """Character spans of paragraphs split on blank lines."""
    spans = []
    pos = 0
    for m in re.finditer(r"\n[ \t]*\n", section_body):
        end = m.start()
        if end > pos:
            spans.append((pos, end, section_body[pos:end]))
        pos = m.end()
    if pos < len(section_body):
        spans.append((pos, len(section_body), section_body[pos:]))
    return spans


def _prose_paragraphs(section_body, min_words):
    """(start, end, text, word_count) for prose paragraphs meeting a size."""
    result = []
    for p_start, p_end, p_text in _paragraph_spans(section_body):
        t = p_text.strip()
        if not t:
            continue
        if t.startswith("#") or t.startswith(LIST_PREFIXES) or t.startswith("|"):
            continue
        wc = len(WORD_RE.findall(t))
        if wc >= min_words:
            result.append((p_start, p_end, t, wc))
    return result


def _word_set(text):
    return set(WORD_RE.findall(text.lower()))


def _normalized(text):
    return re.sub(r"[^a-z0-9\s]", "", text.lower())


def detect_sentence_length_variance(text, rule, profile="general"):
    signal = _signal(rule)
    findings, metrics = [], []
    measured = 0
    for s_start, s_end, body in _sections(text):
        lengths = _sentence_lengths(_prose_flat(body))
        measured += len(lengths)
        if len(lengths) >= SENTENCE_MIN_COUNT:
            std, mean = _std_dev(lengths)
            if mean >= SENTENCE_MEAN_MIN and std / mean < SENTENCE_CV_LIMIT:
                cv = round(std / mean, 3)
                message = (
                    "Uniform sentence lengths in a prose section: coefficient "
                    f"of variation {cv} across {len(lengths)} sentences "
                    f"(limit < {SENTENCE_CV_LIMIT}, requires at least "
                    f"{SENTENCE_MIN_COUNT} sentences and a mean of at least "
                    f"{SENTENCE_MEAN_MIN:g} words). Advisory metric; never "
                    "proves AI authorship."
                )
                findings.append(_finding(
                    rule, s_start, s_end, message,
                    _short_excerpt(text, s_start, s_end), signal, "document",
                    {"sentences": len(lengths), "cv": cv,
                     "mean": round(mean, 1),
                     "minimum_sentences": SENTENCE_MIN_COUNT},
                ))
    if measured < SENTENCE_MIN_COUNT:
        metrics.append(_insufficient("sentence_length_variance",
                                     SENTENCE_MIN_COUNT, measured))
    return {"findings": findings, "metrics": metrics}


def detect_paragraph_length_variance(text, rule, profile="general"):
    signal = _signal(rule)
    findings, metrics = [], []
    measured = 0
    for s_start, s_end, body in _sections(text):
        lengths = [wc for _a, _b, _t, wc
                   in _prose_paragraphs(body, PARAGRAPH_MIN_WORDS)]
        measured += len(lengths)
        if len(lengths) >= PARAGRAPH_MIN_COUNT:
            std, mean = _std_dev(lengths)
            if std / mean < PARAGRAPH_CV_LIMIT:
                cv = round(std / mean, 3)
                message = (
                    "Uniform paragraph lengths in a prose section: coefficient "
                    f"of variation {cv} across {len(lengths)} paragraphs "
                    f"(limit < {PARAGRAPH_CV_LIMIT}, requires at least "
                    f"{PARAGRAPH_MIN_COUNT} paragraphs of at least "
                    f"{PARAGRAPH_MIN_WORDS} words). Advisory metric; never "
                    "proves AI authorship."
                )
                findings.append(_finding(
                    rule, s_start, s_end, message,
                    _short_excerpt(text, s_start, s_end), signal, "document",
                    {"paragraphs": len(lengths), "cv": cv,
                     "minimum_paragraphs": PARAGRAPH_MIN_COUNT,
                     "minimum_words": PARAGRAPH_MIN_WORDS},
                ))
    if measured < PARAGRAPH_MIN_COUNT:
        metrics.append(_insufficient("paragraph_length_variance",
                                     PARAGRAPH_MIN_COUNT, measured))
    return {"findings": findings, "metrics": metrics}


def detect_sentence_start_repetition(text, rule, profile="general"):
    signal = _signal(rule)
    findings, metrics = [], []
    measured = 0
    for s_start, s_end, body in _sections(text):
        first_words = _sentence_first_words(_prose_flat(body))
        measured += len(first_words)
        if len(first_words) >= START_REP_SENTENCE_MIN:
            counts = {}
            for w in first_words:
                counts[w] = counts.get(w, 0) + 1
            total = len(first_words)
            offenders = [(w, c) for w, c in counts.items()
                         if c >= START_REP_COUNT_MIN
                         and c / total > START_REP_RATIO]
            if offenders:
                word, count = max(offenders, key=lambda x: x[1])
                message = (
                    f"Repeated sentence openings: '{word}' opens {count} of "
                    f"{total} sentences (limit > {START_REP_RATIO:.0%}, "
                    f"minimum {START_REP_COUNT_MIN} occurrences, requires at "
                    f"least {START_REP_SENTENCE_MIN} sentences). Advisory "
                    "metric; never proves AI authorship."
                )
                findings.append(_finding(
                    rule, s_start, s_end, message,
                    _short_excerpt(text, s_start, s_end), signal, "document",
                    {"opener": word, "count": count, "sentences": total,
                     "ratio": round(count / total, 3),
                     "minimum_sentences": START_REP_SENTENCE_MIN},
                ))
    if measured < START_REP_SENTENCE_MIN:
        metrics.append(_insufficient("sentence_start_repetition",
                                     START_REP_SENTENCE_MIN, measured))
    return {"findings": findings, "metrics": metrics}


def detect_transition_repetition(text, rule, profile="general"):
    signal = _signal(rule)
    findings, metrics = [], []
    for s_start, s_end, body in _sections(text):
        flat = _prose_flat(body).lower()
        for transition in TRANSITIONS:
            count = len(re.findall(
                r"\b" + re.escape(transition) + r"\b", flat))
            if count >= TRANSITION_REP_COUNT:
                message = (
                    f"Repeated transition '{transition}' appears {count} "
                    f"times in one prose section (limit "
                    f"{TRANSITION_REP_COUNT - 1}). Advisory metric; never "
                    "proves AI authorship."
                )
                findings.append(_finding(
                    rule, s_start, s_end, message,
                    _short_excerpt(text, s_start, s_end), signal, "document",
                    {"transition": transition, "count": count,
                     "limit": TRANSITION_REP_COUNT},
                ))
                break
    return {"findings": findings, "metrics": metrics}


def _jaccard(a_words, b_words):
    union = len(a_words | b_words)
    if union == 0:
        return 0.0
    return len(a_words & b_words) / union


def _pair_findings(paragraphs, rule, signal, min_jaccard, strict_duplication):
    """Flag later paragraphs that duplicate or strongly overlap an earlier one.

    paragraphs is a list of (start, end, text, word_count) within a section.
    Only the later paragraph is reported, once, matching the ContentDuplication
    design evidence.
    """
    findings = []
    flagged = set()
    items = [(p_start, p_end, p_text, wc) for p_start, p_end, p_text, wc
             in paragraphs]
    for i, (start, end, p_text, _wc) in enumerate(items):
        if i in flagged:
            continue
        words = _word_set(p_text)
        for j in range(i + 1, len(items)):
            if j in flagged:
                continue
            later_start, later_end, later_text, _lwc = items[j]
            later_words = _word_set(later_text)
            shared = len(words & later_words)
            ratio = _jaccard(words, later_words)
            is_duplicate = (strict_duplication
                            and (_normalized(p_text) == _normalized(later_text)
                                 or ratio > DUPLICATION_JACCARD))
            is_similar = (not strict_duplication
                          and ratio > min_jaccard
                          and shared >= SIMILARITY_MIN_SHARED)
            if is_duplicate or is_similar:
                if strict_duplication:
                    message = (
                        "Paragraph repeats an earlier paragraph almost "
                        f"verbatim (similarity {ratio:.2f}, limit > "
                        f"{DUPLICATION_JACCARD}). Deterministic finding; "
                        "check whether the repetition is load-bearing."
                    )
                else:
                    message = (
                        "Paragraph strongly overlaps an earlier paragraph "
                        f"(similarity {ratio:.2f}, limit > "
                        f"{min_jaccard}, at least {SIMILARITY_MIN_SHARED} "
                        f"shared words). Requires paragraphs of at least "
                        f"{SIMILARITY_MIN_WORDS} words. Advisory metric; "
                        "never proves AI authorship."
                    )
                findings.append(_finding(
                    rule, later_start, later_end, message,
                    _short_excerpt(later_text, 0, len(later_text)),
                    signal, "span",
                    {"similarity": round(ratio, 2),
                     "shared_words": shared,
                     "minimum_words": SIMILARITY_MIN_WORDS},
                ))
                flagged.add(j)
                break
    return findings


def detect_paragraph_similarity(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    for s_start, s_end, body in _sections(text):
        paragraphs = _prose_paragraphs(body, SIMILARITY_MIN_WORDS)
        for finding in _pair_findings(paragraphs, rule, signal,
                                      SIMILARITY_JACCARD, False):
            finding["start"] = s_start + finding["start"]
            finding["end"] = s_start + finding["end"]
            findings.append(finding)
    return {"findings": findings, "metrics": []}


def detect_paragraph_duplication(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    for s_start, s_end, body in _sections(text):
        paragraphs = _prose_paragraphs(body, SIMILARITY_MIN_WORDS)
        for finding in _pair_findings(paragraphs, rule, signal,
                                      SIMILARITY_JACCARD, True):
            finding["start"] = s_start + finding["start"]
            finding["end"] = s_start + finding["end"]
            findings.append(finding)
    return {"findings": findings, "metrics": []}


def _inline_list_items(sentence):
    """Count items in a comma-list sentence, or None when not a list."""
    lower = sentence.lower()
    for conj in (", and ", ", or "):
        idx = lower.find(conj)
        if idx >= 0:
            before = sentence[:idx]
            parts = [p.strip() for p in before.split(",")]
            if len(parts) >= 2 and all(_short_item(p) for p in parts[1:]):
                return len(parts) + 1
            return None
    for conj in (" and ", " or "):
        idx = lower.find(conj)
        if idx > 0 and "," in sentence[:idx]:
            before = sentence[:idx]
            parts = [p.strip() for p in before.split(",")]
            if len(parts) >= 2 and all(_short_item(p) for p in parts[1:]):
                return len(parts) + 1
    return None


def _short_item(text):
    return len(WORD_RE.findall(text)) <= 3


def _count_bullet_lists(section_text):
    """Count 3-item and other bullet runs in a section's raw text."""
    tricolons = 0
    others = 0
    run = 0
    for line in section_text.split("\n"):
        t = line.strip()
        is_item = t.startswith(("- ", "* ")) or bool(
            re.match(r"^[0-9]+\.\s", t))
        if is_item:
            run += 1
        else:
            if run == 3:
                tricolons += 1
            elif run >= 2:
                others += 1
            run = 0
    if run == 3:
        tricolons += 1
    elif run >= 2:
        others += 1
    return tricolons, others


def detect_tricolon_density(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    tricolons = 0
    other_lists = 0
    total_sentences = 0
    for _s_start, _s_end, body in _sections(text):
        fenced = FENCE_RE.sub(" ", body)
        cleaned = COMMENT_RE.sub(" ", fenced) if "-->" in fenced else fenced
        t, o = _count_bullet_lists(cleaned)
        tricolons += t
        other_lists += o
        flat = _prose_flat(cleaned)
        for a, b in _sentence_spans(flat):
            sentence = flat[a:b]
            if len(WORD_RE.findall(sentence)) < 3:
                continue
            total_sentences += 1
            items = _inline_list_items(sentence)
            if items is None:
                continue
            if items == 3:
                tricolons += 1
            else:
                other_lists += 1
    total_lists = tricolons + other_lists
    ratio = tricolons / total_lists if total_lists else 0.0
    density = tricolons / total_sentences if total_sentences else 0.0
    if tricolons >= TRICOLON_MIN_COUNT and ratio > TRICOLON_LIST_RATIO \
            and density >= TRICOLON_DENSITY:
        message = (
            f"Tricolon reflex: {tricolons} three-part constructions among "
            f"{total_lists} enumerated lists (ratio {ratio:.0%}) across "
            f"{total_sentences} sentences (density {density:.0%}). Requires "
            f"at least {TRICOLON_MIN_COUNT} tricolons, more than "
            f"{TRICOLON_LIST_RATIO:.0%} of lists, and at least "
            f"{TRICOLON_DENSITY:.0%} of sentences. Advisory metric; never "
            "proves AI authorship."
        )
        findings.append(_finding(
            rule, 0, len(text), message,
            _short_excerpt(text, 0, len(text)), signal, "document",
            {"tricolons": tricolons, "other_lists": other_lists,
             "list_ratio": round(ratio, 2),
             "sentences": total_sentences,
             "density": round(density, 2),
             "minimum_tricolons": TRICOLON_MIN_COUNT},
        ))
    return {"findings": findings, "metrics": []}


def _has_passive(sentence):
    for m in PASSIVE_RE.finditer(sentence):
        if m.group(1).lower() in PASSIVE_ADJECTIVES:
            continue
        return True
    return False


REACH_PROMISE_RE = re.compile(
    r"\b(?:boost|grow|increase|drive|raise|expand|multiply|get more)\s+"
    r"(?:your\s+)?(?:reach|engagement|impressions|visibility|saves|comments|"
    r"likes|shares|followers|network|traffic|exposure)\b"
    r"|\b(?:go(?:es)? viral|going viral)\b"
    r"|\bthe algorithm (?:loves|rewards|prefers|boosts|picks up)\b"
    r"|\balgorithmic (?:boost|benefit|growth)\b"
    r"|\b(?:opening weight|dwell time)\b"
    r"|\breach (?:a|the) wider audience\b"
    r"|\bseen by more people\b"
    r"|\bgrow your (?:network|audience)\b",
    re.IGNORECASE,
)


def detect_social_reach_promise(text, rule, profile="social-linkedin"):
    """Reach, engagement, or algorithmic-benefit promise (profile-local).

    The social-linkedin rule fires only under that opt-in profile. The
    finding is advisory and reports a promise with no mechanism or measured
    result beside it; it never proves AI authorship and never promises a
    result itself.
    """
    signal = _signal(rule)
    findings = []
    for match in REACH_PROMISE_RE.finditer(text):
        start, end = match.start(), match.end()
        findings.append(_finding(
            rule, start, end,
            "A reach, engagement, or algorithmic-benefit promise with no "
            "mechanism or measured result beside it. Advisory finding; "
            "never proves AI authorship.",
            _short_excerpt(text, start, end), signal, "span",
            {"phrase": match.group(0)},
        ))
    return {"findings": findings, "metrics": []}


def detect_passive_density(text, rule, profile="general"):
    signal = _signal(rule)
    findings, metrics = [], []
    measured = 0
    for s_start, s_end, body in _sections(text):
        flat = _prose_flat(body)
        sentences = [flat[a:b] for a, b in _sentence_spans(flat)
                     if len(WORD_RE.findall(flat[a:b])) >= SENTENCE_MIN_WORDS]
        measured += len(sentences)
        if len(sentences) >= PASSIVE_MIN_SENTENCES:
            passives = sum(1 for s in sentences if _has_passive(s))
            ratio = passives / len(sentences)
            if passives >= PASSIVE_MIN_COUNT and ratio > PASSIVE_RATIO:
                message = (
                    f"Sustained passive voice: {passives} of {len(sentences)} "
                    f"sentences (ratio {ratio:.2f}, limit > {PASSIVE_RATIO}, "
                    f"minimum {PASSIVE_MIN_COUNT} passives and "
                    f"{PASSIVE_MIN_SENTENCES} sentences). Deterministic "
                    "density finding; never proves AI authorship."
                )
                findings.append(_finding(
                    rule, s_start, s_end, message,
                    _short_excerpt(text, s_start, s_end), signal, "document",
                    {"passives": passives, "sentences": len(sentences),
                     "ratio": round(ratio, 3),
                     "minimum_sentences": PASSIVE_MIN_SENTENCES},
                ))
    if measured < PASSIVE_MIN_SENTENCES:
        metrics.append(_insufficient("passive_density",
                                     PASSIVE_MIN_SENTENCES, measured))
    return {"findings": findings, "metrics": metrics}


# --------------------------------------------------------------------------
# Formatting detectors (issue #131)
# --------------------------------------------------------------------------
# Deterministic where the pattern is unambiguous (emoji presence, bolded-term
# inline headers, -ly adverb compounds), advisory where register or degree is
# a judgment call (exclamation and semicolon overuse, compound-modifier
# hyphenation). Code fences, inline code, and quoted material are masked so
# literal examples and technical spans never fire.

EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FAFF\u2B50\u2705\u274C\u274E\u2757\u2764\uFE0F]"
)
EMOJI_BULLET_RE = re.compile(
    r"(?m)^[ \t]*(?:[-*]|\d+[.)])[ \t]*"
    r"[\U0001F000-\U0001FAFF\u2B50\u2705\u274C\u274E\u2757\u2764]"
)
INLINE_HEADER_RE = re.compile(r"\*\*[^*]+?(?::\*\*|\*\*\s*:)")
EXCLAMATION_RE = re.compile(r"!")
SEMICOLON_RE = re.compile(r";")
LY_HYPHEN_RE = re.compile(r"\b[A-Za-z]+ly-\w+\b")
HEADING_RE = re.compile(r"(?m)^#{1,6}\s+(.+)$")
HEADING_STOPWORDS = frozenset(
    "a an the and or but for nor so yet on in at to from of with by as is "
    "are was were be been it its this that these those".split()
)
HEADING_PROPER_NOUNS = frozenset(
    "antislop openai chatgpt codex javascript python json api html css http "
    "https gpt claude gemini kiro forgejo github oauth rfc kubernetes amazon "
    "visual transport".split()
)


def _mask_code_and_quotes(text):
    """Blank code (fenced and inline) and quoted spans with spaces.

    Offsets are preserved, so findings keep valid positions in the original
    text. Code and quotes are never prose for the formatting checks.
    """
    masked = density._mask_code(text)
    chars = list(masked)
    for match in density.QUOTED_RE.finditer(masked):
        for index in range(match.start(), match.end()):
            chars[index] = " "
    return "".join(chars)


def _fmt_paragraph_spans(masked):
    """Yield (start, end) of each paragraph in a masked text."""
    spans = []
    start = None
    pos = 0
    for line in masked.split("\n"):
        if line.strip():
            if start is None:
                start = pos
        else:
            if start is not None:
                spans.append((start, pos - 1 if pos > start else start))
                start = None
        pos += len(line) + 1
    if start is not None:
        spans.append((start, len(masked)))
    return spans


def detect_fmt_emojis(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    masked = _mask_code_and_quotes(text)
    for match in EMOJI_RE.finditer(masked):
        findings.append(_finding(
            rule, match.start(), match.end(),
            "Emoji in prose. Remove the emoji.",
            _short_excerpt(text, match.start(), match.end()),
            signal, "span", {"char": match.group(0)},
        ))
    return {"findings": findings, "metrics": []}


def detect_fmt_emoji_bullets(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    masked = _mask_code_and_quotes(text)
    for match in EMOJI_BULLET_RE.finditer(masked):
        findings.append(_finding(
            rule, match.start(), match.end(),
            "Emoji as a bullet marker. Convert to a plain bullet or prose.",
            _short_excerpt(text, match.start(), match.end()),
            signal, "span", {"marker": match.group(0).strip()},
        ))
    return {"findings": findings, "metrics": []}


def detect_fmt_inline_header(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    masked = _mask_code_and_quotes(text)
    for match in INLINE_HEADER_RE.finditer(masked):
        findings.append(_finding(
            rule, match.start(), match.end(),
            "Inline-header list (bolded term followed by a colon). "
            "Convert to prose.",
            _short_excerpt(text, match.start(), match.end()),
            signal, "span", {},
        ))
    return {"findings": findings, "metrics": []}


def detect_fmt_exclamation(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    masked = _mask_code_and_quotes(text)
    for match in EXCLAMATION_RE.finditer(masked):
        findings.append(_finding(
            rule, match.start(), match.end(),
            "Exclamation mark in prose. Zero in technical or factual "
            "writing; at most one in conversational prose.",
            _short_excerpt(text, match.start(), match.end()),
            signal, "span", {},
        ))
    return {"findings": findings, "metrics": []}


def detect_fmt_semicolon(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    masked = _mask_code_and_quotes(text)
    for start, end in _fmt_paragraph_spans(masked):
        body = masked[start:end]
        count = len(SEMICOLON_RE.findall(body))
        if count >= 2:
            findings.append(_finding(
                rule, start, end,
                "Two or more semicolons in one paragraph. Split into "
                "separate sentences, or keep only in formal or academic "
                "register.",
                _short_excerpt(text, start, end),
                signal, "document", {"count": count},
            ))
    return {"findings": findings, "metrics": []}


def detect_fmt_compound_hyphen(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    masked = _mask_code_and_quotes(text)
    for match in LY_HYPHEN_RE.finditer(masked):
        findings.append(_finding(
            rule, match.start(), match.end(),
            "Hyphenated -ly adverb compound, which is never hyphenated. "
            "Remove the hyphen.",
            _short_excerpt(text, match.start(), match.end()),
            signal, "span", {"compound": match.group(0)},
        ))
    return {"findings": findings, "metrics": []}


def _is_title_case(tokens):
    if len(tokens) < 2:
        return False

    normalized = [word.lower() for word in tokens]
    if normalized[0] in HEADING_PROPER_NOUNS:
        return False

    significant = [
        word for word, lower in zip(tokens[1:], normalized[1:])
        if lower not in HEADING_STOPWORDS
    ]
    if not significant:
        return False
    if any(word.islower() for word in significant):
        return False

    # A gerund followed only by named products is usually a sentence-case
    # heading whose capital letters belong to the names themselves.
    if all(word.lower() in HEADING_PROPER_NOUNS for word in significant):
        return False
    return all(word[0].isupper() for word in significant)


def detect_fmt_title_case(text, rule, profile="general"):
    signal = _signal(rule)
    findings = []
    masked = _mask_code_and_quotes(text)
    for match in HEADING_RE.finditer(masked):
        heading = match.group(1).strip()
        tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", heading)
        if _is_title_case(tokens):
            findings.append(_finding(
                rule, match.start(), match.end(),
                "Title Case heading. Use sentence case.",
                _short_excerpt(text, match.start(), match.end()),
                signal, "span", {"heading": heading},
            ))
    return {"findings": findings, "metrics": []}


# --------------------------------------------------------------------------
# Local structural detectors (issue #131 continuation)
# --------------------------------------------------------------------------
# These checks are deliberately advisory. They expose the registered rule
# signal without pretending that a comma count, line wrap, generic link, or
# colon construction proves anything about authorship.

GENERIC_LINK_LABELS = frozenset({
    "click here", "learn more", "read more", "here", "this link",
})
MARKDOWN_LINK_RE = re.compile(r"\[([^\]\n]{1,120})\]\([^ )\n]{1,2048}\)")
LOCAL_SENTENCE_END_RE = re.compile(r"[.!?](?:\s+|$)")
COLON_REVEAL_RE = re.compile(
    r"\b[A-Z][^.!?\n\[\]]{2,120}:\s+[a-z][^.!?\n\[\]]{1,180}(?:[.!?]|$)"
)
COLON_LABEL_WORDS = frozenset({
    "example", "lesson", "note", "result", "summary", "warning",
})
COLON_CLAUSE_WORDS = frozenset({
    "are", "be", "been", "being", "can", "caused", "could", "cut",
    "did", "do", "does", "had", "has", "have", "is", "made", "makes",
    "ranked", "reduced", "returns", "returned", "should", "was", "were",
    "will", "would",
})


def _colon_reveal_is_load_bearing(before):
    words = re.findall(r"[A-Za-z]+", before.lower())
    if not words:
        return True
    if words[-1] in COLON_LABEL_WORDS:
        return True
    return any(word in COLON_CLAUSE_WORDS for word in words)


def _local_prose_mask(text):
    """Mask code, quotes, links' URLs, and non-prose Markdown lines."""
    masked = list(_mask_code_and_quotes(text))
    for match in re.finditer(r"https?://[^\s)]{1,2048}", "".join(masked)):
        for index in range(match.start(), match.end()):
            masked[index] = "x"
    for match in re.finditer(r"\[[a-z][a-z0-9_-]*:\s*[^\]]*\](?!\()", "".join(masked)):
        for index in range(match.start(), match.end()):
            masked[index] = " "
    line_start = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        stripped = content.lstrip()
        if (stripped.startswith("#") or stripped.startswith(("- ", "* ", ">", "|"))
                or re.match(r"\d+[.)]\s", stripped)):
            for index in range(line_start, line_start + len(content)):
                masked[index] = " "
        line_start += len(line)
    return "".join(masked)


def _sentence_start(masked, position):
    previous = max(masked.rfind(".", 0, position),
                   masked.rfind("!", 0, position),
                   masked.rfind("?", 0, position))
    return previous + 1


def _sentence_end(masked, position):
    match = re.search(r"[.!?]", masked[position:])
    return position + match.end() if match else len(masked)


def detect_struct_overlong_sentence(text, rule, profile="general"):
    signal = _signal(rule)
    masked = _local_prose_mask(text)
    findings = []
    start = 0
    for match in LOCAL_SENTENCE_END_RE.finditer(masked):
        end = match.start() + 1
        sentence = masked[start:end]
        comma_count = sentence.count(",")
        if comma_count >= 5 and len(WORD_RE.findall(sentence)) >= 10:
            findings.append(_finding(
                rule, start, end,
                "Overlong sentence contains at least five prose commas; review "
                "whether it should be split. Advisory finding; never proves AI authorship.",
                _short_excerpt(text, start, end), signal, "span",
                {"commas": comma_count, "minimum_commas": 5},
            ))
        start = match.end()
    if start < len(masked):
        sentence = masked[start:]
        if sentence.count(",") >= 5 and len(WORD_RE.findall(sentence)) >= 10:
            findings.append(_finding(
                rule, start, len(masked),
                "Overlong sentence contains at least five prose commas; review "
                "whether it should be split. Advisory finding; never proves AI authorship.",
                _short_excerpt(text, start, len(masked)), signal, "span",
                {"commas": sentence.count(","), "minimum_commas": 5},
            ))
    return {"findings": findings, "metrics": []}


def detect_struct_artificial_line_breaks(text, rule, profile="general"):
    signal = _signal(rule)
    masked = _local_prose_mask(text)
    findings = []
    for match in re.finditer(r"\n", masked):
        position = match.start()
        raw_before = text[:position]
        before = masked[:position].rstrip(" \t\r")
        after = masked[position + 1:]
        if after.startswith(("\n", "\r")) or text[position - 1:position] in ("\n", "\r"):
            continue
        next_nonspace = re.search(r"\S", after)
        if not before or not next_nonspace:
            continue
        if raw_before.endswith(("  ", "\t")) or before.endswith((".", "!", "?", ":", ";")):
            continue
        continuation = after[next_nonspace.start():]
        if (continuation.startswith(("#", ">", "|", "- ", "* "))
                or re.match(r"\d+[.)]\s", continuation)):
            continue
        start = _sentence_start(masked, position)
        end = _sentence_end(masked, position + 1)
        findings.append(_finding(
            rule, position, min(position + 1, len(text)),
            "Mid-sentence line break in prose; review whether the wrap is "
            "intentional. Advisory finding; never proves AI authorship.",
            _short_excerpt(text, start, end), signal, "span",
            {"line_break": position},
        ))
    return {"findings": findings, "metrics": []}


def detect_struct_link_text(text, rule, profile="general"):
    signal = _signal(rule)
    masked = _local_prose_mask(text)
    findings = []
    for match in MARKDOWN_LINK_RE.finditer(masked):
        label = match.group(1).strip().lower()
        if label in GENERIC_LINK_LABELS:
            label_start = match.start(1) + (len(match.group(1)) - len(match.group(1).lstrip()))
            label_end = label_start + len(label)
            findings.append(_finding(
                rule, label_start, label_end,
                "Generic link text hides the destination; name what the link "
                "points to. Advisory finding; never proves AI authorship.",
                _short_excerpt(text, label_start, label_end), signal, "span",
                {"label": label},
            ))
    return {"findings": findings, "metrics": []}


def detect_struct_colon_reveal(text, rule, profile="general"):
    signal = _signal(rule)
    masked = _local_prose_mask(text)
    findings = []
    for match in COLON_REVEAL_RE.finditer(masked):
        sentence_start = _sentence_start(masked, match.start())
        sentence_end = _sentence_end(masked, match.start())
        sentence = masked[sentence_start:sentence_end]
        if sentence.lstrip().startswith(("Note:", "Example:", "Warning:")):
            continue
        before, _colon, after = sentence.partition(":")
        if (_colon_reveal_is_load_bearing(before)
                or len(WORD_RE.findall(before)) < 2
                or not after.strip()):
            continue
        findings.append(_finding(
            rule, sentence_start, sentence_end,
            "Colon introduces a dramatic explanatory reveal; review whether "
            "the sentence can state the point directly. Advisory finding; "
            "never proves AI authorship.",
            _short_excerpt(text, sentence_start, sentence_end), signal, "span",
            {"construction": "colon-reveal"},
        ))
    return {"findings": findings, "metrics": []}


DETECTORS = {
    "sentence_length_variance": detect_sentence_length_variance,
    "paragraph_length_variance": detect_paragraph_length_variance,
    "sentence_start_repetition": detect_sentence_start_repetition,
    "transition_repetition": detect_transition_repetition,
    "paragraph_similarity": detect_paragraph_similarity,
    "tricolon_density": detect_tricolon_density,
    "paragraph_duplication": detect_paragraph_duplication,
    "passive_density": detect_passive_density,
    "social_reach_promise": detect_social_reach_promise,
    "fmt_emojis": detect_fmt_emojis,
    "fmt_emoji_bullets": detect_fmt_emoji_bullets,
    "fmt_inline_header": detect_fmt_inline_header,
    "fmt_exclamation": detect_fmt_exclamation,
    "fmt_semicolon": detect_fmt_semicolon,
    "fmt_compound_hyphen": detect_fmt_compound_hyphen,
    "fmt_title_case": detect_fmt_title_case,
    "struct_overlong_sentence": detect_struct_overlong_sentence,
    "struct_artificial_line_breaks": detect_struct_artificial_line_breaks,
    "struct_link_text": detect_struct_link_text,
    "struct_colon_reveal": detect_struct_colon_reveal,
}
DETECTORS.update(mechanism.DETECTORS)
DETECTORS.update(density.DETECTORS)


def _span_text(text, span):
    return text[span.start():span.end()]


def detect_numbered_list_inflation(text, rule, profile="general"):
    from analyzer import find_numbered_list_inflation
    findings = []
    for span in find_numbered_list_inflation(text):
        findings.append(_finding(
            rule, span.start(), span.end(),
            rule.get("correction", ""),
            _short_excerpt(text[span.start():span.end()], span.start(), span.end()),
            "advisory", "span",
        ))
    return {"findings": findings, "metrics": []}


def detect_paragraph_reshuffle(text, rule, profile="general"):
    from analyzer import find_paragraph_reshuffle
    findings = []
    for span in find_paragraph_reshuffle(text):
        findings.append(_finding(
            rule, span.start(), span.end(),
            rule.get("correction", ""),
            _short_excerpt(_span_text(text, span), span.start(), span.end()),
            "advisory", "span",
        ))
    return {"findings": findings, "metrics": []}


def detect_treadmill_prose(text, rule, profile="general"):
    from analyzer import find_treadmill_prose
    findings = []
    for span in find_treadmill_prose(text):
        findings.append(_finding(
            rule, span.start(), span.end(),
            rule.get("correction", ""),
            _short_excerpt(_span_text(text, span), span.start(), span.end()),
            "advisory", "span",
        ))
    return {"findings": findings, "metrics": []}


CITATION_LEAK_RE = re.compile(
    r"citeturn\d+\w*|oai_citation|\[attached_file:\d+\]"
)
AI_REFERRER_RE = re.compile(
    r"utm_source=(?:chatgpt|openai|claude|perplexity)\.com"
)
UNFILLED_PLACEHOLDER_RE = re.compile(
    r"\[(?:Your Name|INSERT [A-Z_ ]+|TODO|TBD|YOUR TEXT HERE)\]"
)
EM_DASH_RE = re.compile(r"\u2014|\u2013| -- ")
CURLY_QUOTE_RE = re.compile(r"[\u2018\u2019\u201c\u201d]")


def detect_fmt_em_dash(text, rule, profile="general"):
    findings = []
    for match in EM_DASH_RE.finditer(text):
        findings.append(_finding(
            rule, match.start(), match.end(),
            rule.get("correction", ""),
            _short_excerpt(text, match.start(), match.end()),
            "strict", "span",
        ))
    return {"findings": findings, "metrics": []}


def detect_fmt_curly_quotes(text, rule, profile="general"):
    findings = []
    for match in CURLY_QUOTE_RE.finditer(text):
        findings.append(_finding(
            rule, match.start(), match.end(),
            rule.get("correction", ""),
            _short_excerpt(text, match.start(), match.end()),
            "strict", "span",
        ))
    return {"findings": findings, "metrics": []}


def detect_chat_citation_leaks(text, rule, profile="general"):
    findings = []
    for match in CITATION_LEAK_RE.finditer(text):
        findings.append(_finding(
            rule, match.start(), match.end(),
            rule.get("correction", ""),
            _short_excerpt(text, match.start(), match.end()),
            "strict", "span",
        ))
    return {"findings": findings, "metrics": []}


def detect_ai_url_parameters(text, rule, profile="general"):
    findings = []
    for match in AI_REFERRER_RE.finditer(text):
        findings.append(_finding(
            rule, match.start(), match.end(),
            rule.get("correction", ""),
            _short_excerpt(text, match.start(), match.end()),
            "strict", "span",
        ))
    return {"findings": findings, "metrics": []}


def detect_unfilled_placeholders(text, rule, profile="general"):
    from analyzer import mask_protected_markdown
    masked = mask_protected_markdown(text)
    findings = []
    for match in UNFILLED_PLACEHOLDER_RE.finditer(masked):
        findings.append(_finding(
            rule, match.start(), match.end(),
            rule.get("correction", ""),
            _short_excerpt(text, match.start(), match.end()),
            "strict", "span",
        ))
    return {"findings": findings, "metrics": []}


DETECTORS.update({
    "numbered_list_inflation": detect_numbered_list_inflation,
    "paragraph_reshuffle": detect_paragraph_reshuffle,
    "treadmill_prose": detect_treadmill_prose,
    "chat_citation_leaks": detect_chat_citation_leaks,
    "ai_url_parameters": detect_ai_url_parameters,
    "unfilled_placeholders": detect_unfilled_placeholders,
    "fmt_em_dash": detect_fmt_em_dash,
    "fmt_curly_quotes": detect_fmt_curly_quotes,
})


def detect_rule(text, rule, profile="general"):
    func = DETECTORS.get(rule.get("detector"))
    if func is None:
        return {"findings": [], "metrics": []}
    result = func(text, rule, profile)
    for finding in result["findings"]:
        finding["profile"] = profile
    return result


def run_detectors(text, rules, profile="general"):
    limits.check_input_size(text)
    findings = []
    metrics = []
    for rule in rules:
        result = detect_rule(text, rule, profile)
        findings.extend(result["findings"])
        metrics.extend(result["metrics"])
    findings.sort(key=lambda f: (f["start"], f["end"]))
    return {"findings": findings, "metrics": metrics}


def main():
    parser = argparse.ArgumentParser(description="Antislop structural checks")
    parser.add_argument(
        "--profile", default="general",
        help="Writing profile (default: general)"
    )
    parser.add_argument(
        "--registry", default="rules.json",
        help="Path to rule registry (default: rules.json)"
    )
    parser.add_argument(
        "--file", default=None,
        help="Read text from file instead of stdin"
    )
    parser.add_argument(
        "--stdin", action="store_true",
        help="Read text from stdin"
    )
    args = parser.parse_args()

    if not os.path.exists(args.registry):
        print(json.dumps({"error": f"Registry not found: {args.registry}"}))
        sys.exit(3)

    registry = load_registry(args.registry)
    valid_profiles = set(registry.get("profiles", {}).keys())
    if args.profile not in valid_profiles:
        print(json.dumps({
            "error": f"unknown profile '{args.profile}'. Valid: "
                     f"{sorted(valid_profiles)}"
        }))
        sys.exit(3)

    if args.file:
        try:
            text = limits.read_text_file(args.file)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            sys.exit(3)
    elif args.stdin or not sys.stdin.isatty():
        try:
            text = limits.read_text(sys.stdin)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            sys.exit(3)
    else:
        print(json.dumps({"error": "No input. Use --file, --stdin, or pipe "
                                   "text."}))
        sys.exit(3)

    if not text.strip():
        print(json.dumps({"error": "Empty input"}))
        sys.exit(3)

    active = filter_rules_by_profile(registry, args.profile)
    result = run_detectors(text, active, args.profile)

    report = {
        "interface": "antislop.structural",
        "schema": "structural-report-1",
        "version": registry.get("version", "unknown"),
        "profile": args.profile,
        "word_count": len(text.split()),
        "findings": result["findings"],
        "metrics": result["metrics"],
        "disclaimer": "Structural checks are formulaic-writing risk signals; "
                      "they never prove AI authorship.",
    }
    print(json.dumps(report, indent=2))

    strict = any(f["signal"] == "strict" for f in result["findings"])
    advisory = any(f["signal"] == "advisory" for f in result["findings"])
    if strict:
        sys.exit(2)
    if advisory:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
