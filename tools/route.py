#!/usr/bin/env python3
"""Intent routing shared by skill evaluations and tool clients."""

import re


AUDIT_PATTERNS = (
    r"\baudit\b",
    r"\bdetect\b.*\b(?:patterns?|prose|writing|slop)\b",
    r"\bdoes this pass\b",
    r"\bflag (?:the )?(?:ai |formulaic )?patterns?\b",
    r"\breview\b.*\b(?:ai patterns?|formulaic structure|formulaic writing|slop)\b",
    r"\b(?:score|grade)\b.*\b(?:writing|text|draft|slop)\b",
    r"\bscan\b.*\b(?:draft|text|writing|prose|slop|patterns?)\b",
)

STYLE_PATTERNS = (
    r"\b(?:write|rewrite|edit|polish|phrase|clean)\b",
    r"\breview\b.*\b(?:abstract|post|email|draft|article|copy)\b",
)

NON_PROSE_PATTERNS = (
    r"\b(?:python|bash|shell|javascript|typescript|rust|go)\b.*\b(?:function|script|code)\b",
    r"\b(?:yaml|json|toml)\b.*\b(?:configuration|config)\b",
    r"\bwhat is \d+\s*[+*/-]\s*\d+\b",
    r"\bwhat is the capital of\b",
    r"\b(?:explain|what is|how does)\b.*\b(?:cve|cvss|api|protocol)\b",
)


def matches_any(patterns, text):
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def route_intent(prompt):
    """Return antislop or none for a user prompt."""
    return route_request(prompt)["skill"]


def route_request(prompt):
    """Return both the selected skill and explicit operating mode."""
    if matches_any(NON_PROSE_PATTERNS, prompt):
        return {"skill": "none", "mode": "none"}
    if matches_any(AUDIT_PATTERNS, prompt):
        mode = "detect" if re.search(r"\b(?:detect|flag only|audit only|scan)\b", prompt, re.I) else "audit"
        return {"skill": "antislop", "mode": mode}
    if matches_any(STYLE_PATTERNS, prompt):
        edit_file = re.search(
            r"\b(?:edit|clean|fix)\b.*\b[\w.-]+\.(?:md|mdx|txt|rst|adoc)\b",
            prompt,
            re.I,
        )
        return {"skill": "antislop", "mode": "edit" if edit_file else "rewrite"}
    return {"skill": "none", "mode": "none"}
