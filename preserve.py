#!/usr/bin/env python3
"""Validate that an Antislop rewrite preserves protected source material."""

import argparse
from collections import Counter
import json
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from analyzer import mask_protected_markdown, protected_text


AI_REFERRER_KEYS = {"utm_source", "ref", "source"}
AI_REFERRER_VALUES = {"chatgpt", "chatgpt.com", "openai", "claude", "perplexity"}


def extract_frontmatter(text):
    matches = protected_text(text, "frontmatter", trim_newlines=True)
    return matches[0] if matches else None


def extract_fenced_blocks(text):
    return protected_text(text, "fenced_code", trim_newlines=True)


def extract_blockquotes(text):
    return protected_text(text, "blockquote", trim_newlines=True)


def extract_inline_code(text):
    return protected_text(text, "inline_code")


def extract_tables(text):
    return protected_text(text, "table", trim_newlines=True)


def extract_urls(text):
    return [
        match.group(0).rstrip(".,;:!?")
        for match in re.finditer(
            r"(?:https?|ftp)://[^\s<>]+|\bwww\.[^\s<>]+", text,
            re.IGNORECASE)
    ]


def extract_numbers(text):
    masked = mask_protected_markdown(text)
    return re.findall(r"\b\d+(?:\.\d+)?%?\b", masked)


def extract_quotations(text):
    masked = mask_protected_markdown(text)
    return [
        match.group(0)
        for match in re.finditer(r'"[^"\n]+"|“[^”\n]+”', masked)
    ]


def extract_attributions(text):
    return [
        match.group(0).strip().rstrip(".")
        for match in re.finditer(
            r"(?im)^[ \t]*(?:by|author|written by):?[ \t]+[A-Z][^\n.]+",
            text,
        )
    ]


def extract_paths(text):
    """Extract absolute, home, Windows, and relative filesystem paths."""
    token = r"[A-Za-z0-9._-]+"
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_.:/-])(?:"
        rf"[A-Za-z]:[\\/](?:{token}[\\/])*{token}(?:[\\/]{token})*"
        rf"|~/(?:{token}/)*{token}(?:/{token})*"
        rf"|/(?:{token}/)*{token}(?:/{token})*"
        rf"|(?!(?:and|or|either)/)(?:\.\.?/|(?:{token}/)+{token}"
        rf"(?:/{token})*)"
        rf")",
        re.IGNORECASE,
    )
    return [
        match.group(0).rstrip(".,;:!?)]}")
        for match in pattern.finditer(text)
    ]


def normalize_url(url):
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.casefold() in AI_REFERRER_KEYS and value.casefold() in AI_REFERRER_VALUES:
            continue
        query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def error(code, message):
    return {"code": code, "message": message}


def compare_exact(original, rewrite, extractor, code, label):
    before = extractor(original)
    after = extractor(rewrite)
    if before == after:
        return []
    return [error(code, f"{label} changed during rewrite.")]


def validate_rewrite(original, rewrite):
    """Return a structured preservation result for two Markdown documents."""
    errors = []
    warnings = []

    if extract_frontmatter(original) != extract_frontmatter(rewrite):
        errors.append(error("frontmatter-modified", "Frontmatter changed during rewrite."))

    errors.extend(compare_exact(
        original,
        rewrite,
        extract_fenced_blocks,
        "code-block-modified",
        "Fenced code",
    ))
    errors.extend(compare_exact(
        original,
        rewrite,
        extract_blockquotes,
        "blockquote-modified",
        "Blockquoted material",
    ))
    errors.extend(compare_exact(
        original,
        rewrite,
        extract_inline_code,
        "inline-code-modified",
        "Inline code",
    ))
    errors.extend(compare_exact(
        original,
        rewrite,
        extract_tables,
        "table-modified",
        "Markdown table",
    ))

    original_urls = Counter(normalize_url(url) for url in extract_urls(original))
    rewrite_urls = Counter(normalize_url(url) for url in extract_urls(rewrite))
    if original_urls != rewrite_urls:
        errors.append(error(
            "url-modified",
            "A source URL or functional query parameter was added, removed, or changed during rewrite.",
        ))

    if Counter(extract_numbers(original)) != Counter(extract_numbers(rewrite)):
        errors.append(error(
            "numeric-literal-modified",
            "A numeric literal changed during rewrite.",
        ))

    if Counter(extract_quotations(original)) != Counter(extract_quotations(rewrite)):
        errors.append(error(
            "quotation-modified",
            "Quoted material changed during rewrite.",
        ))

    if Counter(extract_attributions(original)) != Counter(extract_attributions(rewrite)):
        errors.append(error(
            "attribution-modified",
            "An attribution changed during rewrite.",
        ))

    if Counter(extract_paths(original)) != Counter(extract_paths(rewrite)):
        errors.append(error(
            "path-modified",
            "A filesystem path was added, removed, or changed during rewrite.",
        ))

    original_headings = [
        match.group(1).strip()
        for match in re.finditer(r"(?m)^#{1,6}[ \t]+(.+)$", original)
    ]
    rewrite_headings = [
        match.group(1).strip()
        for match in re.finditer(r"(?m)^#{1,6}[ \t]+(.+)$", rewrite)
    ]
    if original_headings != rewrite_headings:
        errors.append(error(
            "heading-modified",
            "A heading was added, removed, reordered, or changed during rewrite.",
        ))

    valid = not errors
    return {
        "status": "literal_preservation_passed" if valid else "preservation_failed",
        "valid": valid,
        "semantic_review_required": True,
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate rewrite preservation")
    parser.add_argument("original", help="Original Markdown file")
    parser.add_argument("rewrite", help="Rewritten Markdown file")
    args = parser.parse_args()

    try:
        with open(args.original, encoding="utf-8") as f:
            original = f.read()
        with open(args.rewrite, encoding="utf-8") as f:
            rewrite = f.read()
    except OSError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2

    result = validate_rewrite(original, rewrite)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
