#!/usr/bin/env python3
"""Shared deterministic analysis primitives for Antislop public interfaces."""

from dataclasses import dataclass
import re


EMOJI_PATTERN = re.compile(
    "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF]"
)
EMOJI_BULLET_PATTERN = re.compile(
    r"(?m)^[ \t]*[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF][ \t]+"
)

PROTECTED_PATTERNS = {
    "frontmatter": re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL),
    "fenced_code": re.compile(
        r"(?ms)^(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^(?P=fence)[ \t]*$"
    ),
    "inline_code": re.compile(r"`[^`\n]+`"),
    "blockquote": re.compile(r"(?m)^(?:[ \t]{0,3}>[^\n]*(?:\n|$))+"),
    "table": re.compile(r"(?m)^(?:[ \t]*\|[^\n]*\|[ \t]*(?:\n|$)){2,}"),
}

CONNECTIVE_OPENERS = re.compile(
    r"(?i)^(?:because|but|however|therefore|thus|so|then|instead|that|this|these|"
    r"those|such|after|before|once|while|although|as a result|for that reason)\b"
)
NUMBERED_ITEM_PATTERN = re.compile(r"(?m)^[ \t]*(\d+)[.)][ \t]+(.+)$")
WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*")
URL_PATTERN = re.compile(r"https?://[^\s<>]+")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "but", "by",
    "for", "from", "has", "have", "in", "into", "is", "it", "of", "on",
    "or", "that", "the", "their", "this", "to", "was", "were", "will", "with",
}


@dataclass(frozen=True)
class SpanMatch:
    """Small match interface for detectors that operate above regex level."""

    start_offset: int
    end_offset: int

    def start(self):
        return self.start_offset

    def end(self):
        return self.end_offset

    def span(self):
        return (self.start_offset, self.end_offset)


def protected_matches(text, kind):
    """Return the canonical Markdown literal matches for one protected kind."""
    return list(PROTECTED_PATTERNS[kind].finditer(text))


def protected_text(text, kind, trim_newlines=False):
    """Extract protected text using the same parser used for detector masking."""
    values = [match.group(0) for match in protected_matches(text, kind)]
    if trim_newlines:
        return [value.rstrip("\r\n") for value in values]
    return values


def content_words(text):
    return {
        word.casefold()
        for word in WORD_PATTERN.findall(text)
        if len(word) > 2 and word.casefold() not in STOP_WORDS
    }


def prose_paragraphs(text):
    """Return offset-bearing prose paragraphs, excluding Markdown structures."""
    paragraphs = []
    for match in re.finditer(r"(?ms)(?:\A|\n{2,})([^\n].*?)(?=\n{2,}|\Z)", text):
        body = match.group(1)
        stripped = body.lstrip()
        if not stripped or stripped.startswith(("#", ">", "|", "```", "~~~")):
            continue
        if re.match(r"(?:[-*+]\s+|\d+[.)]\s+)", stripped):
            continue
        start = match.start(1)
        paragraphs.append((start, match.end(1), body, content_words(body)))
    return paragraphs


def find_numbered_list_inflation(text):
    """Find long numbered runs whose items repeat the same small vocabulary."""
    items = list(NUMBERED_ITEM_PATTERN.finditer(text))
    if not items:
        return []

    runs = []
    current = [items[0]]
    for item in items[1:]:
        between = text[current[-1].end():item.start()]
        expected = int(current[-1].group(1)) + 1
        if int(item.group(1)) == expected and between.strip() == "":
            current.append(item)
        else:
            runs.append(current)
            current = [item]
    runs.append(current)

    findings = []
    for run in runs:
        if len(run) < 5:
            continue
        word_sets = [content_words(item.group(2)) for item in run]
        overlapping_pairs = 0
        for left, right in zip(word_sets, word_sets[1:]):
            if left and right and len(left & right) / min(len(left), len(right)) >= 0.5:
                overlapping_pairs += 1
        if overlapping_pairs >= len(run) - 2:
            findings.append(SpanMatch(run[0].start(), run[-1].end()))
    return findings


def find_paragraph_reshuffle(text):
    """Flag three consecutive topic-island paragraphs with no lexical bridge."""
    paragraphs = [p for p in prose_paragraphs(text) if len(p[3]) >= 7]
    if len(paragraphs) < 3:
        return []

    findings = []
    for index in range(len(paragraphs) - 2):
        window = paragraphs[index:index + 3]
        if any(
            "`" in paragraph[2]
            or "http://" in paragraph[2]
            or "https://" in paragraph[2]
            or "<details" in paragraph[2]
            for paragraph in window
        ):
            continue
        linked = False
        for left, right in zip(window, window[1:]):
            right_text = right[2].strip()
            lexical_overlap = len(left[3] & right[3]) / min(len(left[3]), len(right[3]))
            boundary = text[left[1]:right[0]]
            if (
                re.search(r"(?m)^#{1,6}[ \t]+", boundary)
                or CONNECTIVE_OPENERS.match(right_text)
                or lexical_overlap >= 0.12
            ):
                linked = True
                break
        if not linked:
            findings.append(SpanMatch(window[0][0], window[-1][1]))
            break
    return findings


def find_treadmill_prose(text):
    """Find adjacent prose paragraphs that mostly restate the same content words."""
    paragraphs = [p for p in prose_paragraphs(text) if len(p[3]) >= 6]
    findings = []
    for left, right in zip(paragraphs, paragraphs[1:]):
        smaller = min(len(left[3]), len(right[3]))
        if smaller and len(left[3] & right[3]) / smaller >= 0.6:
            findings.append(SpanMatch(right[0], right[1]))
    return findings


STRUCTURAL_DETECTORS = {
    "numbered_list_inflation": find_numbered_list_inflation,
    "paragraph_reshuffle": find_paragraph_reshuffle,
    "treadmill_prose": find_treadmill_prose,
}


def find_registered_pattern_matches(text, rule, detectors):
    """Return matches for an executable registered pattern, or None."""
    detector = detectors.get(rule["id"])
    if detector is None:
        return None
    if detector["type"] == "regex":
        pattern = re.compile(detector["pattern"])
        return list(pattern.finditer(text))
    if detector["type"] == "emoji":
        return list(EMOJI_PATTERN.finditer(text))
    if detector["type"] == "emoji_bullet":
        return list(EMOJI_BULLET_PATTERN.finditer(text))
    analyzer = STRUCTURAL_DETECTORS.get(detector["type"])
    if analyzer is None:
        return None
    return analyzer(text)


def mask_protected_markdown(text):
    """Mask quoted and literal Markdown while preserving source offsets."""
    spans = [
        match.span()
        for kind in PROTECTED_PATTERNS
        for match in protected_matches(text, kind)
    ]

    masked = list(text)
    for start, end in spans:
        for index in range(start, end):
            if masked[index] not in "\r\n":
                masked[index] = " "
    return "".join(masked)


def mask_urls(text):
    """Mask URL literals while preserving offsets for prose-only detectors."""
    masked = list(text)
    for match in URL_PATTERN.finditer(text):
        for index in range(match.start(), match.end()):
            if masked[index] not in "\r\n":
                masked[index] = " "
    return "".join(masked)
