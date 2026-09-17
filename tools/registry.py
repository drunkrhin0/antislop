#!/usr/bin/env python3
"""Shared rule-registry loading and profile filtering.

Used by generate.py and score.py so the two don't carry independent copies
of the same registry-reading logic.
"""

import limits


class RegistryError(ValueError):
    """The rule registry contains an invalid profile definition."""


def load_registry(path="rules.json"):
    try:
        registry = limits.load_json_file(path, "rule registry")
    except (OSError, ValueError) as exc:
        raise RegistryError(f"cannot load registry: {exc}") from exc
    if not isinstance(registry, dict):
        raise RegistryError("registry root must be an object")
    return registry


def _resolve_profile_names(profiles, profile):
    """Return a profile and its ancestors, rejecting invalid graphs."""
    resolved = set()
    visiting = []

    def visit(name):
        if name not in profiles:
            raise RegistryError(f"unknown profile '{name}'")
        if name in visiting:
            cycle = visiting[visiting.index(name):] + [name]
            raise RegistryError("profile inheritance cycle: " + " -> ".join(cycle))
        if name in resolved:
            return
        visiting.append(name)
        parents = profiles[name].get("extends", [])
        if not isinstance(parents, list) or not all(isinstance(parent, str) for parent in parents):
            raise RegistryError(f"profile '{name}' extends must be a list of profile names")
        for parent in parents:
            visit(parent)
        visiting.pop()
        resolved.add(name)

    visit(profile)
    return resolved


def validate_profile_definitions(registry):
    """Reject malformed inheritance and rule profile references."""
    if not isinstance(registry, dict):
        raise RegistryError("registry root must be an object")
    profiles = registry.get("profiles", {})
    if not isinstance(profiles, dict):
        raise RegistryError("profiles must be an object")
    for name, definition in profiles.items():
        if not isinstance(definition, dict):
            raise RegistryError(f"profile '{name}' must be an object")
    for name in profiles:
        _resolve_profile_names(profiles, name)

    rules = registry.get("rules", [])
    if not isinstance(rules, list):
        raise RegistryError("rules must be a list")
    known_profiles = set(profiles)
    for rule in rules:
        if not isinstance(rule, dict):
            raise RegistryError("every rule must be an object")
        raw_profiles = rule.get("profiles", ["general"])
        if not isinstance(raw_profiles, list):
            raise RegistryError(
                f"rule '{rule.get('id', '?')}' profiles must be a list"
            )
        if not all(isinstance(name, str) for name in raw_profiles):
            raise RegistryError(
                f"rule '{rule.get('id', '?')}' profiles must contain names"
            )
        unknown_profiles = set(raw_profiles) - known_profiles - {"*"}
        if unknown_profiles:
            unknown = sorted(unknown_profiles)[0]
            raise RegistryError(
                f"rule '{rule.get('id', '?')}' references unknown profile "
                f"'{unknown}'"
            )


def filter_rules_by_profile(source, profile):
    """Return active rules, resolving profile inheritance for a registry.

    A plain list remains supported for existing callers that do not need
    inheritance. New entry points should pass the complete registry.
    """
    if isinstance(source, dict):
        rules = source.get("rules", [])
        profiles = source.get("profiles", {})
        if not isinstance(rules, list) or not isinstance(profiles, dict):
            raise RegistryError("registry rules and profiles must be objects of the expected shape")
        effective_profiles = _resolve_profile_names(profiles, profile)
    else:
        rules = source
        effective_profiles = {profile}
    active = []
    for rule in rules:
        rule_profiles = rule.get("profiles", ["general"])
        if "*" in rule_profiles or set(rule_profiles) & effective_profiles:
            active.append(rule)
    return active
