#!/usr/bin/env python3
"""Shared rule-registry loading and profile filtering.

Used by generate.py and score.py so the two don't carry independent copies
of the same registry-reading logic.
"""

import json


def load_registry(path="rules.json"):
    with open(path) as f:
        return json.load(f)


def filter_rules_by_profile(rules, profile):
    """Return rules active in the given profile.

    A rule is active if:
    - Its profiles list contains '*' (universal), OR
    - Its profiles list contains the requested profile name.
    """
    active = []
    for rule in rules:
        rule_profiles = rule.get("profiles", ["general"])
        if "*" in rule_profiles or profile in rule_profiles:
            active.append(rule)
    return active
