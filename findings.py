"""Shared finding helpers for the executable rule modules.

The audit and repair modules each build JSON findings with the same signal
classification and excerpt shapes. Keeping them here means a change to the
report shape lands in one place instead of being copied across modules.
"""


def signal(rule):
    """Strict when the rule is deterministic, advisory otherwise."""
    return "strict" if rule.get("review_mode") == "deterministic" else "advisory"


def short_excerpt(text, start, end, limit=120):
    """The matched span itself, truncated to a readable bound."""
    span = text[start:end].strip()
    if len(span) > limit:
        return span[:limit].rstrip() + "..."
    return span


def excerpt(text, start, end, window=20):
    """The matched span plus surrounding context, ellipsized at cut points."""
    excerpt = text[max(0, start - window):min(len(text), end + window)].strip()
    if excerpt and not excerpt.startswith((" ", "\t")):
        excerpt = "..." + excerpt
    if excerpt and not excerpt.endswith((" ", "\t")):
        excerpt = excerpt + "..."
    return excerpt
