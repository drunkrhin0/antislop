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
  11. No ASCII dash or arrow substitutes (' -- ', '->') outside code spans
  12. Shared lines carry the same marks across shipped artifacts

Usage:
    python3 validate.py --skills-dir skills
    python3 validate.py --skills-dir skills --expect-version 2.0.3
    python3 validate.py --help

Fixture files under tests/fixtures/ are named SKILL.md.fixture, not SKILL.md
(see tests/test_validate.py's materialize_fixture()), so run the test suite
to exercise them rather than pointing --skills-dir at that directory directly.
"""

import argparse
import json
import os
import re
import sys


EMOJI_RE = re.compile(r"[\U0001F300-\U0001F9FF\U00002702-\U000027B0]")


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
    lines = text.split("\n")
    body_start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                body_start = i + 1
                break
    body = "\n".join(lines[body_start:])
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
            if EMOJI_RE.search(line):
                errors.append(f"{relpath}: emoji in heading at line {i}")

    return errors


ALLOWED_POWER_KEYS = {"name", "displayName", "description", "keywords", "author"}
BROAD_POWER_KEYWORDS = {"test", "api", "data", "help", "debug"}
STEERING_MAP_HEADING = "## When to Load Steering Files"


def parse_keyword_list(raw):
    """Parse bracketed or comma-separated keyword values without PyYAML."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(value).strip() for value in raw]
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    entries = []
    current = []
    quote = None
    for char in value:
        if char in ('"', "'"):
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            else:
                current.append(char)
        elif char == "," and quote is None:
            item = "".join(current).strip()
            if item:
                entries.append(item)
            current = []
        else:
            current.append(char)
    item = "".join(current).strip()
    if item:
        entries.append(item)
    return [item.strip().strip('"').strip("'") for item in entries]


def find_power_files(powers_dir):
    """Find all POWER.md files under powers_dir."""
    return sorted(
        os.path.join(root, filename)
        for root, _dirs, files in os.walk(powers_dir)
        for filename in files
        if filename == "POWER.md"
    )


def validate_power_file(path):
    """Validate Kiro Power frontmatter, body, and steering map."""
    errors = []
    relpath = os.path.relpath(path)
    with open(path) as f:
        text = f.read()
    fm = parse_frontmatter(text)

    for key in ("name", "displayName", "description"):
        if not fm.get(key):
            errors.append(f"{relpath}: missing frontmatter '{key}:'")
    for key in fm:
        if key not in ALLOWED_POWER_KEYS:
            errors.append(
                f"{relpath}: frontmatter key '{key}' is not allowed in a Power "
                "(only name, displayName, description, keywords, author)"
            )

    name = fm.get("name")
    if name:
        dirname = os.path.basename(os.path.dirname(os.path.abspath(path)))
        if name != dirname:
            errors.append(f"{relpath}: frontmatter name '{name}' does not match containing directory '{dirname}'")
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
            errors.append(f"{relpath}: frontmatter name '{name}' is not lowercase kebab-case")

    display_name = fm.get("displayName")
    if display_name:
        words = display_name.split()
        if not 2 <= len(words) <= 5:
            errors.append(f"{relpath}: displayName '{display_name}' must be 2 to 5 words")
        if EMOJI_RE.search(display_name):
            errors.append(f"{relpath}: displayName '{display_name}' contains an emoji")
        minor_words = {"a", "an", "the", "and", "or", "for", "to", "of", "in", "on", "at", "with"}
        title_tokens = [token for word in words for token in word.split("-")]
        title_ok = True
        for index, token in enumerate(title_tokens):
            if token.lower() in minor_words and index > 0:
                continue
            if len(token) > 2 and token.isupper() or not token[:1].isupper():
                title_ok = False
                break
        if not title_ok:
            errors.append(f"{relpath}: displayName '{display_name}' is not Title Case")

    description = fm.get("description")
    if description:
        sentences = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", description.strip()) if s]
        if len(sentences) > 3:
            errors.append(f"{relpath}: description has {len(sentences)} sentences (must be 3 or fewer)")

    keywords = parse_keyword_list(fm.get("keywords"))
    if not 5 <= len(keywords) <= 7:
        errors.append(f"{relpath}: keywords has {len(keywords)} entries (must be 5 to 7)")
    for keyword in keywords:
        if keyword.lower() in BROAD_POWER_KEYWORDS:
            errors.append(f"{relpath}: keyword '{keyword}' is too broad (avoid test, api, data, help, debug)")

    if extract_version_from_body(text) is None:
        errors.append(f"{relpath}: missing '**Version:**' line in body")

    if STEERING_MAP_HEADING not in text:
        errors.append(f"{relpath}: missing '{STEERING_MAP_HEADING}' section")
    else:
        start = text.index(STEERING_MAP_HEADING) + len(STEERING_MAP_HEADING)
        rest = text[start:]
        next_heading = re.search(r"\n##\s", rest)
        section = rest[: next_heading.start()] if next_heading else rest
        referenced = set(re.findall(r"\*\*([\w.\-]+\.md)\*\*", section))
        steering_dir = os.path.join(os.path.dirname(path), "steering")
        actual = set(os.listdir(steering_dir)) if os.path.isdir(steering_dir) else set()
        actual = {filename for filename in actual if filename.endswith(".md")}
        for missing in sorted(referenced - actual):
            errors.append(f"{relpath}: steering file '{missing}' is listed in '{STEERING_MAP_HEADING}' but does not exist under steering/")
        for unlisted in sorted(actual - referenced):
            errors.append(f"{relpath}: steering file '{unlisted}' exists under steering/ but is not listed in '{STEERING_MAP_HEADING}'")

    license_heading = "## License and support"
    if license_heading in text:
        start = text.index(license_heading) + len(license_heading)
        rest = text[start:]
        next_heading = re.search(r"\n##\s", rest)
        section = rest[: next_heading.start()] if next_heading else rest
        requirements = {
            "license": r"\b(?:MIT|Apache|BSD|GPL|ISC)\b|\blicen[cs]e\b",
            "support contact": r"\bsupport\b|\bcontact\b|\bissue(?:s)?\b",
            "privacy statement": r"\bprivacy\b|\btelemetry\b|\bcollects?\b|\bdata leaves\b",
        }
        for label, pattern in requirements.items():
            if not re.search(pattern, section, re.IGNORECASE):
                errors.append(f"{relpath}: license and support section missing {label}")
    else:
        errors.append(f"{relpath}: missing '{license_heading}' section")
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

    root = repo_root_for(skills_dir)
    power_path = os.path.join(root, "powers", "antislop", "POWER.md")
    if os.path.exists(power_path):
        with open(power_path) as f:
            power_version = extract_version_from_body(f.read())
        if power_version and power_version != expected:
            errors.append(f"{os.path.relpath(power_path)}: version={power_version}, expected {expected}")
    else:
        errors.append(f"{os.path.relpath(power_path)}: missing")

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


# Artifacts that ship alongside skills/ and restate the same rules. Paths are
# relative to the repository root, taken as the parent of skills_dir. Each is
# checked only when present, so fixture runs skip them.
EXTRA_ARTIFACTS = [
    os.path.join(".opencode", "agents", "antislop.md"),
    os.path.join("skills", "antislop", "GEMINI.md"),
    os.path.join("powers", "antislop", "POWER.md"),
    "README.md",
]

# ASCII stand-ins a bulk find-and-replace leaves behind in place of the real
# marks: ' -- ' for an em dash, '->' for an arrow.
DASH_SUBSTITUTE = re.compile(r' -- |"-- |->')

# Every mark plus its ASCII stand-in, for comparing the same line across files.
MARK_OR_SUBSTITUTE = re.compile(r'—|–|→| -- |"-- |->')


def repo_root_for(skills_dir):
    """Repository root, taken as the parent of skills_dir."""
    return os.path.dirname(os.path.abspath(skills_dir)) or "."


def find_shipped_artifacts(skills_dir):
    """Skill files plus the shipped derivatives that live outside skills_dir."""
    paths = list(find_skill_files(skills_dir))
    seen = {os.path.normpath(os.path.abspath(p)) for p in paths}
    root = repo_root_for(skills_dir)
    for rel in EXTRA_ARTIFACTS:
        path = os.path.join(root, rel)
        if os.path.isfile(path) and os.path.normpath(os.path.abspath(path)) not in seen:
            paths.append(path)
            seen.add(os.path.normpath(os.path.abspath(path)))
    return paths


def blank_code_spans(line):
    """Blank inline code spans, preserving offsets, so a literal mark
    reference like ` -- ` is not read as dash usage."""
    return re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)


def is_table_or_rule(line):
    """Markdown table separators and horizontal rules are built from hyphens."""
    stripped = line.strip()
    return "-" in stripped and bool(re.match(r"^\|?[\s|:-]+\|?$", stripped))


def check_dash_substitutes(skills_dir):
    """Flag ASCII dash and arrow substitutes in shipped prose.

    Em dashes in rule explanations are meta-context, not violations: the files
    have to quote the marks they ban. What is not allowed is the ASCII stand-in
    a bulk find-and-replace leaves behind. Code spans are exempt, since the
    post-generation scan instruction must name the marks it looks for.
    """
    errors = []

    for path in find_shipped_artifacts(skills_dir):
        with open(path) as f:
            text = f.read()

        relpath = os.path.relpath(path)
        in_fence = False

        for i, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or is_table_or_rule(line):
                continue
            for match in DASH_SUBSTITUTE.finditer(blank_code_spans(line)):
                errors.append(
                    f"{relpath}:{i}: dash substitute {match.group(0).strip()!r} "
                    "outside a code span"
                )

    return errors


def check_dash_parity(skills_dir):
    """Shared lines across shipped artifacts must carry the same marks.

    The agent file, GEMINI.md, and both SKILL.md files restate the same rules
    and examples. A bulk replace applied to one derivative and not its siblings
    shows up here as one sentence carrying different marks in different files.
    """
    errors = []
    seen = {}

    for path in find_shipped_artifacts(skills_dir):
        with open(path) as f:
            text = f.read()

        relpath = os.path.relpath(path)

        for i, line in enumerate(text.splitlines(), 1):
            marks = MARK_OR_SUBSTITUTE.findall(line)
            if not marks:
                continue

            key = MARK_OR_SUBSTITUTE.sub("\x00", " ".join(line.split()))
            if len(key.replace("\x00", "").strip()) < 20:
                continue  # too short to identify a shared line

            signature = tuple(m.strip() for m in marks)
            previous = seen.get(key)
            if previous is None:
                seen[key] = (relpath, i, signature)
            elif previous[2] != signature:
                errors.append(
                    f"{relpath}:{i}: dash drift from {previous[0]}:{previous[1]} "
                    f"({list(signature)} vs {list(previous[2])})"
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
    parser.add_argument(
        "--powers-dir",
        default="powers",
        help="Path to Kiro Powers directory (default: powers)",
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

    for path in find_power_files(args.powers_dir):
        all_errors.extend(validate_power_file(path))

    # Cross-file checks
    all_errors.extend(check_cross_file_versions(skills_dir))

    # Version-specific checks
    if args.expect_version:
        all_errors.extend(check_expected_version(skills_dir, args.expect_version))

    # Audit content checks (always run)
    all_errors.extend(check_audit_output_format(skills_dir))
    all_errors.extend(check_authorship_disclaimer(skills_dir))
    all_errors.extend(check_antithesis_consistency(skills_dir))
    all_errors.extend(check_dash_substitutes(skills_dir))
    all_errors.extend(check_dash_parity(skills_dir))

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
