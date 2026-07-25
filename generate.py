#!/usr/bin/env python3
"""Generate and check Antislop rule artifacts from the canonical registry.

The rule registry (rules.json) is the single source of truth. This generator
renders rule sections deterministically and verifies committed files match.

Usage:
    python3 generate.py --check                    # verify committed files match
    python3 generate.py --check --profile technical # verify for specific profile
    python3 generate.py --output-dir out/          # write generated files
    python3 generate.py --output-dir out/ --profile general
    python3 generate.py --help

Check mode exits 0 when all generated artifacts match committed files,
or exits 1 when any differ.
"""

import argparse
import json
import os
import sys


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


def render_vocabulary_section(rules):
    """Render the vocabulary table from registry rules."""
    vocab = [r for r in rules if r["category"] == "vocabulary"]
    lines = ["## Vocabulary — never use", "", "| Word | Severity |", "|---|---|"]
    for r in sorted(vocab, key=lambda x: x["id"]):
        lines.append(f"| {r['text']} | {r['severity']} |")
    return "\n".join(lines)


def render_phrase_section(rules):
    """Render the phrase list from registry rules."""
    phrases = [r for r in rules if r["category"] == "phrase"]
    high = [r for r in phrases if r["severity"] == "high"]
    medium = [r for r in phrases if r["severity"] == "medium"]
    lines = ["## Phrases — never use", ""]
    for r in sorted(high, key=lambda x: x["id"]):
        exception_note = ""
        if r.get("exceptions"):
            exception_note = f" (exception: {'; '.join(r['exceptions'])})"
        lines.append(f'- "{r["text"]}"{exception_note}')
    if medium:
        lines.append("")
        lines.append("## Phrases — medium severity (max once per 800 words)")
        lines.append("")
        for r in sorted(medium, key=lambda x: x["id"]):
            exception_note = ""
            if r.get("exceptions"):
                exception_note = f" (exception: {'; '.join(r['exceptions'])})"
            lines.append(f'- "{r["text"]}"{exception_note}')
    return "\n".join(lines)


def render_filler_section(rules):
    """Render the filler phrases list."""
    fillers = [r for r in rules if r["category"] == "filler"]
    lines = ["## Filler phrases — never use", ""]
    for r in sorted(fillers, key=lambda x: x["id"]):
        lines.append(f'- "{r["text"]}"')
    return "\n".join(lines)


def render_structural_section(rules):
    """Render structural patterns grouped by severity."""
    structural = [r for r in rules if r["category"] == "structural"]
    high = [r for r in structural if r["severity"] == "high"]
    medium = [r for r in structural if r["severity"] == "medium"]
    low = [r for r in structural if r["severity"] == "low"]

    lines = ["## Structural patterns", ""]
    if high:
        lines.append("### High severity")
        lines.append("")
        for r in sorted(high, key=lambda x: x["id"]):
            lines.append(f"- {r['text']}")
        lines.append("")
    if medium:
        lines.append("### Medium severity")
        lines.append("")
        for r in sorted(medium, key=lambda x: x["id"]):
            lines.append(f"- {r['text']}")
        lines.append("")
    if low:
        lines.append("### Low severity")
        lines.append("")
        for r in sorted(low, key=lambda x: x["id"]):
            lines.append(f"- {r['text']}")
    return "\n".join(lines)


def render_formatting_section(rules):
    """Render formatting rules."""
    fmt = [r for r in rules if r["category"] == "formatting"]
    lines = ["## Formatting", ""]
    for r in sorted(fmt, key=lambda x: x["id"]):
        lines.append(f"- {r['text']}")
    return "\n".join(lines)


def render_chatbot_section(rules):
    """Render chatbot artifact rules."""
    chatbot = [r for r in rules if r["category"] == "chatbot"]
    lines = ["## Chatbot artifacts", ""]
    for r in sorted(chatbot, key=lambda x: x["id"]):
        lines.append(f'- "{r["text"]}"')
    return "\n".join(lines)


def render_severity_summary(rules):
    """Render a severity-to-weight mapping summary."""
    lines = ["## Severity weights", "", "| Severity | Base weight |", "|---|---|"]
    for sev in ("high", "medium", "low"):
        match = next((r["base_weight"] for r in rules if r["severity"] == sev), None)
        if match is not None:
            lines.append(f"| {sev} | {match} |")
    return "\n".join(lines)


def render_pattern_reference(registry, profile="general"):
    """Render the full pattern reference document for a given profile."""
    all_rules = registry["rules"]
    rules = filter_rules_by_profile(all_rules, profile)
    profile_name = profile
    profile_info = registry.get("profiles", {}).get(profile, {})
    sections = [
        "# Pattern reference (generated)",
        "",
        "This file is generated from rules.json. Do not edit directly.",
        f"Registry version: {registry['version']}",
        f"Profile: {profile_name}",
        f"Profile description: {profile_info.get('description', '')}",
        "",
        render_vocabulary_section(rules),
        "",
        render_phrase_section(rules),
        "",
        render_filler_section(rules),
        "",
        render_structural_section(rules),
        "",
        render_formatting_section(rules),
        "",
        render_chatbot_section(rules),
        "",
        render_severity_summary(rules),
        "",
    ]
    return "\n".join(sections) + "\n"


def generate_all(registry, profile="general"):
    """Generate all artifacts for a given profile. Returns dict of relative path -> content."""
    return {
        "skills/antislop-audit/references/pattern-reference.md": render_pattern_reference(registry, profile),
    }


def check_mode(registry, repo_root, profile="general"):
    """Compare generated output against committed files. Returns list of diffs."""
    generated = generate_all(registry, profile)
    diffs = []
    for relpath, expected_content in generated.items():
        full_path = os.path.join(repo_root, relpath)
        if not os.path.exists(full_path):
            diffs.append(f"MISSING: {relpath}")
            continue
        with open(full_path) as f:
            actual = f.read()
        if actual != expected_content:
            diffs.append(f"DRIFT: {relpath}")
    return diffs


def write_mode(registry, output_dir, profile="general"):
    """Write generated files to output directory."""
    generated = generate_all(registry, profile)
    for relpath, content in generated.items():
        full_path = os.path.join(output_dir, relpath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        print(f"  WROTE  {relpath}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate and check Antislop rule artifacts"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Verify generated output matches committed files"
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Write generated files to this directory"
    )
    parser.add_argument(
        "--registry", default="rules.json",
        help="Path to rule registry (default: rules.json)"
    )
    parser.add_argument(
        "--profile", default="general",
        help="Writing profile to generate for (default: general)"
    )
    args = parser.parse_args()

    if not os.path.exists(args.registry):
        print(f"ERROR: registry not found: {args.registry}", file=sys.stderr)
        sys.exit(2)

    registry = load_registry(args.registry)
    rules = registry.get("rules", [])
    print(f"Loaded {len(rules)} rules from {args.registry} (v{registry.get('version', '?')})")

    # Validate profile
    valid_profiles = set(registry.get("profiles", {}).keys())
    if args.profile not in valid_profiles:
        print(f"ERROR: unknown profile '{args.profile}'. Valid: {sorted(valid_profiles)}",
              file=sys.stderr)
        sys.exit(2)

    if args.check:
        repo_root = os.path.dirname(os.path.abspath(args.registry))
        diffs = check_mode(registry, repo_root, args.profile)
        if diffs:
            print(f"\nFAILED — {len(diffs)} artifact(s) differ from generated:\n")
            for d in diffs:
                print(f"  {d}")
            sys.exit(1)
        else:
            print("ALL ARTIFACTS MATCH")
            sys.exit(0)
    elif args.output_dir:
        write_mode(registry, args.output_dir, args.profile)
        print(f"\nGenerated {len(generate_all(registry, args.profile))} file(s) to {args.output_dir}")
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
