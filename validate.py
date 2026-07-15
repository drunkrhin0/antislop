#!/usr/bin/env python3
"""Validate Antislop repository invariants.

Checks:
  1. SKILL.md frontmatter completeness (name, description, metadata.version)
  2. Version consistency (metadata.version vs body **Version:**)
  3. Required sections (When NOT to use)
  4. Cross-file version consistency (SKILL.md vs gemini-extension.json)
  5. Line count (warn at 500)
  6. Emoji-free headings
  7. --expect-version: all artifacts at the specified version
  8. Audit output uses "Formulaic Writing Risk Score"
  9. Audit includes authorship disclaimer
  10. Antithesis rule mentions load-bearing distinction

Usage:
    python3 validate.py --skills-dir skills
    python3 validate.py --skills-dir skills --expect-version 1.8.0
    python3 validate.py --skills-dir tests/fixtures
    python3 validate.py --help
"""

import argparse
import json
import os
import re
import sys


def parse_frontmatter(text):
    """Extract YAML frontmatter between --- delimiters as a dict.

    Hand-written parser — no PyYAML dependency. Handles the simple
    key: value and nested key structures used in SKILL.md files.
    """
    lines = text.split("\n")
    in_frontmatter = False
    fm_lines = []
    for line in lines:
        if line.strip() == "---":
            if in_frontmatter:
                break
            in_frontmatter = True
            continue
        if in_frontmatter:
            fm_lines.append(line)

    result = {}
    current_key = None

    for line in fm_lines:
        stripped = line.strip()
        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())

        # Top-level key: value
        m = re.match(r"^(\w[\w-]*):\s*(.*)", stripped)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            if indent == 0:
                if val:
                    result[key] = val
                    current_key = key
                else:
                    # Nested block (e.g., metadata:)
                    result[key] = {}
                    current_key = key
                continue

        # Nested key under current block
        if current_key and isinstance(result.get(current_key), dict):
            m2 = re.match(r"^(\w[\w-]*):\s*(.*)", stripped)
            if m2:
                k2, v2 = m2.group(1), m2.group(2).strip().strip('"').strip("'")
                result[current_key][k2] = v2
                continue

    return result


def extract_version_from_body(text):
    """Extract **Version:** X.Y.Z from the body (after frontmatter)."""
    # Skip frontmatter
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text
    m = re.search(r"\*\*Version:\*\*\s*([0-9][0-9a-z.\-]*)", body)
    return m.group(1) if m else None


def find_skill_files(skills_dir):
    """Find all SKILL.md files under skills_dir."""
    found = []
    for root, dirs, files in os.walk(skills_dir):
        # Skip .opencode directories (not skill files)
        if ".opencode" in root.split(os.sep):
            continue
        for f in files:
            if f == "SKILL.md":
                found.append(os.path.join(root, f))
    return sorted(found)


def validate_skill_file(path):
    """Validate a single SKILL.md file. Returns list of error strings."""
    errors = []
    relpath = os.path.relpath(path)

    with open(path) as f:
        text = f.read()

    fm = parse_frontmatter(text)

    # 1. Frontmatter completeness
    if not fm.get("name"):
        errors.append(f"{relpath}: missing frontmatter 'name:'")
    if not fm.get("description"):
        errors.append(f"{relpath}: missing frontmatter 'description:'")

    metadata = fm.get("metadata", {})
    if not isinstance(metadata, dict) or not metadata.get("version"):
        errors.append(f"{relpath}: missing metadata.version")
        metadata_version = None
    else:
        metadata_version = metadata["version"]

    # 2. Version consistency: metadata vs body
    body_version = extract_version_from_body(text)
    if metadata_version and body_version:
        if metadata_version != body_version:
            errors.append(
                f"{relpath}: version mismatch — metadata={metadata_version}, body={body_version}"
            )

    # 3. Required sections
    if "## When NOT to use" not in text:
        errors.append(f"{relpath}: missing '## When NOT to use' section")

    # 4. Line count
    line_count = len(text.splitlines())
    if line_count > 500:
        errors.append(f"{relpath}: {line_count} lines (over 500 limit)")

    # 5. Emoji-free headings
    for i, line in enumerate(text.splitlines(), 1):
        if re.match(r"^#{1,6}\s", line):
            # Check for common emoji ranges
            if re.search(r"[\U0001F300-\U0001F9FF\U00002702-\U000027B0]", line):
                errors.append(f"{relpath}: emoji in heading at line {i}")

    return errors


def check_cross_file_versions(skills_dir):
    """Check version consistency between SKILL.md and gemini-extension.json."""
    errors = []
    skill_files = find_skill_files(skills_dir)

    for skill_path in skill_files:
        skill_dir = os.path.dirname(skill_path)
        gemini_json = os.path.join(skill_dir, "gemini-extension.json")
        if not os.path.exists(gemini_json):
            continue

        with open(skill_path) as f:
            skill_text = f.read()
        fm = parse_frontmatter(skill_text)
        skill_ver = (fm.get("metadata") or {}).get("version")

        with open(gemini_json) as f:
            gemini_data = json.load(f)
        gemini_ver = gemini_data.get("version")

        if skill_ver and gemini_ver and skill_ver != gemini_ver:
            rel_skill = os.path.relpath(skill_path)
            rel_gemini = os.path.relpath(gemini_json)
            errors.append(
                f"cross-file version drift: {rel_skill}={skill_ver}, {rel_gemini}={gemini_ver}"
            )

    return errors


def check_expected_version(skills_dir, expected):
    """Check that all SKILL.md files and gemini-extension.json are at expected version."""
    errors = []
    skill_files = find_skill_files(skills_dir)

    for path in skill_files:
        with open(path) as f:
            text = f.read()
        fm = parse_frontmatter(text)
        ver = (fm.get("metadata") or {}).get("version")
        body_ver = extract_version_from_body(text)
        relpath = os.path.relpath(path)
        if ver and ver != expected:
            errors.append(f"{relpath}: metadata version={ver}, expected {expected}")
        if body_ver and body_ver != expected:
            errors.append(f"{relpath}: body version={body_ver}, expected {expected}")

    # Check gemini-extension.json files
    for path in skill_files:
        skill_dir = os.path.dirname(path)
        gemini_json = os.path.join(skill_dir, "gemini-extension.json")
        if not os.path.exists(gemini_json):
            continue
        with open(gemini_json) as f:
            data = json.load(f)
        ver = data.get("version")
        if ver and ver != expected:
            errors.append(f"{os.path.relpath(gemini_json)}: version={ver}, expected {expected}")

    return errors


def check_audit_output_format(skills_dir):
    """Check that audit skill uses 'Formulaic Writing Risk Score' in output format."""
    errors = []
    audit_path = os.path.join(skills_dir, "antislop-audit", "SKILL.md")
    if not os.path.exists(audit_path):
        return errors

    with open(audit_path) as f:
        text = f.read()

    if "Formulaic Writing Risk Score" not in text:
        errors.append(
            f"{os.path.relpath(audit_path)}: output format must use 'Formulaic Writing Risk Score'"
        )

    return errors


def check_authorship_disclaimer(skills_dir):
    """Check that audit skill states the score cannot prove AI authorship."""
    errors = []
    audit_path = os.path.join(skills_dir, "antislop-audit", "SKILL.md")
    if not os.path.exists(audit_path):
        return errors

    with open(audit_path) as f:
        text = f.read()

    # Check for authorship disclaimer language
    has_disclaimer = (
        "cannot prove" in text.lower()
        or "cannot establish" in text.lower()
        or "does not prove" in text.lower()
        or "does not establish" in text.lower()
    )
    if not has_disclaimer:
        errors.append(
            f"{os.path.relpath(audit_path)}: missing authorship disclaimer "
            "(score cannot prove/establish AI authorship)"
        )

    return errors


def check_antithesis_consistency(skills_dir):
    """Check that antithesis rule uses the load-bearing distinction consistently."""
    errors = []
    skill_files = find_skill_files(skills_dir)

    for path in skill_files:
        with open(path) as f:
            text = f.read()

        # Find lines mentioning antithesis
        for i, line in enumerate(text.splitlines(), 1):
            if "antithesis" in line.lower():
                # The rule should mention "load-bearing" or "decorative when"
                line_lower = line.lower()
                has_nuance = "load-bearing" in line_lower or "decorative when" in line_lower
                # Flag if the line is a bare "antithesis = always bad" statement
                if not has_nuance and "decorative" in line_lower:
                    # This is a blanket statement without the load-bearing distinction
                    relpath = os.path.relpath(path)
                    errors.append(
                        f"{relpath}:{i}: antithesis rule lacks load-bearing distinction"
                    )

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate Antislop repository invariants")
    parser.add_argument(
        "--skills-dir",
        default="skills",
        help="Path to skills directory (default: skills)",
    )
    parser.add_argument(
        "--expect-version",
        default=None,
        help="Require all artifacts to be at this version (e.g. 1.8.0)",
    )
    args = parser.parse_args()

    skills_dir = args.skills_dir
    if not os.path.isdir(skills_dir):
        print(f"ERROR: skills directory not found: {skills_dir}", file=sys.stderr)
        sys.exit(2)

    all_errors = []

    # Per-file checks
    skill_files = find_skill_files(skills_dir)
    for path in skill_files:
        all_errors.extend(validate_skill_file(path))

    # Cross-file checks
    all_errors.extend(check_cross_file_versions(skills_dir))

    # Version-specific checks
    if args.expect_version:
        all_errors.extend(check_expected_version(skills_dir, args.expect_version))

    # Audit content checks (always run)
    all_errors.extend(check_audit_output_format(skills_dir))
    all_errors.extend(check_authorship_disclaimer(skills_dir))
    all_errors.extend(check_antithesis_consistency(skills_dir))

    # Report
    if all_errors:
        print(f"\nFAILED — {len(all_errors)} error(s):\n")
        for err in all_errors:
            print(f"  FAIL  {err}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
