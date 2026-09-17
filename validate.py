#!/usr/bin/env python3
"""Validate Antislop repository invariants.

Checks:
  1. SKILL.md frontmatter completeness (name, description, metadata.version)
  2. Version consistency (metadata.version vs body **Version:**)
  3. Required sections (When NOT to use)
  4. Line count (warn at 500)
  5. Emoji-free headings
  6. --expect-version: all artifacts at the specified version
  7. Audit output uses "Formulaic Writing Risk Score"
  8. Audit includes authorship disclaimer
  9. Antithesis rule mentions load-bearing distinction
  10. No ASCII dash or arrow substitutes (' -- ', '->') outside code spans
  11. Shared lines carry the same marks across shipped artifacts
  12. Root plugin.json (agent-plugins.org) matches .claude-plugin/plugin.json
  13. Claude Code plugin manifest version matches --expect-version
  14. Native Codex plugin manifest version matches --expect-version
  15. marketplace.json plugin description matches plugin.json
  16. The hand-maintained opencode agent matches
      --expect-version
  17. rules.json semantic rule types, review modes, and source provenance
  18. Drift fixtures and the false-positive corpus validate and match their
      expected decisions (issue #91)
  19. Registry review statuses and medium routing, and the clarity-review
      fixtures validate and match their expected decisions (issue #96)
  20. Protected repair fixtures validate and match their expected decisions
      (issue #92)
  21. The calibration experiment validates and its gate passes (issue #89)
  22. The staged-scan fixtures validate and match their expected stages
      (issue #98)
  23. The density-precision fixtures validate and match their expected
      density, precision, and review results (issue #100)
  24. The rule-registry evidence metadata schema, the stale-lexical review
      queue, and the provenance fixtures validate (issue #101)
  25. The bounded repair-loop fixtures validate and match their attempt
      traces, decisions, retry counts, budgets, rollback state, and
      execution flags (issue #93)
  26. The evidence-bound delivery envelope fixtures validate and match
      their decisions and typed failure kinds (issue #95)
  27. The claim evidence classes and zh-CN locale profile registry schema,
      and the say-human fixtures validate and match their decisions and
      evidence classes (issue #97)
  28. The substance dimensions, substance statuses, and contribution
      contract registry schema, and the substance fixtures validate and
      match their dimension statuses, risk separation, no-label rule, and
      contribution acceptance (issue #102)
  29. Lint workflow --expect-version pins agree with the canonical version
      (issue #70)
  30. --check-rule-content: registry writing rules appear in the style skill
      (issue #84)

--expect-version-from reads the expected version out of rules.json, the
canonical source. The lint workflows and the production test assertion derive
the expected version from that file instead of hardcoding it, so a version
bump edits the shipped artifacts only.

Usage:
    python3 validate.py --skills-dir skills
    python3 validate.py --skills-dir skills --expect-version-from rules.json
    python3 validate.py --skills-dir skills --expect-version 3.0.0
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
RULE_CONTENT_CATEGORIES = ("vocabulary", "phrase", "filler", "chatbot")
RULE_TEXT_SPLIT_RE = re.compile(r"\s*/\s*")
RULE_TEXT_DASH_TRAIL_RE = re.compile(r"\s+[—–-]\s+")
RULE_TEXT_QUOTE_CHARS = "\"'‘’“”"
RULE_TEXT_TRAILING_PUNCT = "!?."


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


def validate_frontmatter_yaml_scalars(text):
    """Catch YAML-invalid colon-space sequences in unquoted scalar values."""
    errors = []
    lines = text.split("\n")
    in_frontmatter = False
    for line_number, line in enumerate(lines, 1):
        if line.strip() == "---":
            if in_frontmatter:
                break
            in_frontmatter = True
            continue
        if not in_frontmatter:
            continue
        match = re.match(r"^\s*[\w-]+:\s+(.+)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if value[:1] not in ('"', "'") and ": " in value:
            errors.append(
                "frontmatter line %d has an unquoted colon in a scalar" % line_number
            )
    return errors


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

    with open(path, encoding="utf-8") as f:
        text = f.read()

    fm = parse_frontmatter(text)
    for yaml_error in validate_frontmatter_yaml_scalars(text):
        errors.append(f"{relpath}: {yaml_error}")

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
    with open(path, encoding="utf-8") as f:
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


def check_expected_version(skills_dir, expected):
    """Check that all version-bearing shipped artifacts use expected."""
    errors = []
    skill_files = find_skill_files(skills_dir)

    for path in skill_files:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        fm = parse_frontmatter(text)
        ver = (fm.get("metadata") or {}).get("version")
        body_ver = extract_version_from_body(text)
        relpath = os.path.relpath(path)
        if ver and ver != expected:
            errors.append(f"{relpath}: metadata version={ver}, expected {expected}")
        if body_ver and body_ver != expected:
            errors.append(f"{relpath}: body version={body_ver}, expected {expected}")

    root = repo_root_for(skills_dir)
    power_path = os.path.join(root, "powers", "antislop", "POWER.md")
    if os.path.exists(power_path):
        with open(power_path, encoding="utf-8") as f:
            power_version = extract_version_from_body(f.read())
        if power_version and power_version != expected:
            errors.append(f"{os.path.relpath(power_path)}: version={power_version}, expected {expected}")
    else:
        errors.append(f"{os.path.relpath(power_path)}: missing")

    # Claude-compatible and native Codex plugin manifests
    for manifest_relpath in (
        os.path.join(".claude-plugin", "plugin.json"),
        os.path.join(".codex-plugin", "plugin.json"),
    ):
        manifest_path = os.path.join(root, manifest_relpath)
        if not os.path.exists(manifest_path):
            continue
        with open(manifest_path, encoding="utf-8") as f:
            manifest_version = json.load(f).get("version")
        if manifest_version and manifest_version != expected:
            errors.append(
                f"{manifest_relpath}: version={manifest_version}, expected {expected}"
            )

    return errors


def check_root_plugin_manifest(skills_dir, expected=None):
    """Check the agent-plugins.org root plugin.json against .claude-plugin/plugin.json.

    Absent root manifest is not an error: repos (and fixture runs) that
    haven't opted into the agent-plugins.org standard don't have one.
    """
    errors = []
    root = repo_root_for(skills_dir)
    root_manifest_path = os.path.join(root, "plugin.json")
    if not os.path.exists(root_manifest_path):
        return errors

    relpath = os.path.relpath(root_manifest_path)
    with open(root_manifest_path) as f:
        root_manifest = json.load(f)

    root_version = root_manifest.get("version")
    if expected:
        if not root_version:
            errors.append(f"{relpath}: missing 'version' field, expected {expected}")
        elif root_version != expected:
            errors.append(f"{relpath}: version={root_version}, expected {expected}")

    claude_manifest_path = os.path.join(root, ".claude-plugin", "plugin.json")
    if os.path.exists(claude_manifest_path):
        rel_claude = os.path.relpath(claude_manifest_path)
        with open(claude_manifest_path) as f:
            claude_manifest = json.load(f)

        claude_version = claude_manifest.get("version")
        if claude_version and root_version != claude_version:
            root_display = root_version if root_version else "(missing)"
            errors.append(
                f"{relpath}: version={root_display} disagrees with {rel_claude}={claude_version}"
            )

        root_desc = root_manifest.get("description")
        claude_desc = claude_manifest.get("description")
        if root_desc and claude_desc and root_desc != claude_desc:
            errors.append(f"{relpath}: description disagrees with {rel_claude}")

    return errors


def check_audit_output_format(skills_dir):
    """Check that audit skill uses 'Formulaic Writing Risk Score' in output format."""
    errors = []
    audit_path = os.path.join(skills_dir, "antislop", "SKILL.md")
    if not os.path.exists(audit_path):
        return errors

    with open(audit_path, encoding="utf-8") as f:
        text = f.read()

    if "## Audit mode" not in text and "## How to run an audit" not in text:
        errors.append(f"{os.path.relpath(audit_path)}: missing audit mode contract")
        return errors

    if "Formulaic Writing Risk Score" not in text:
        errors.append(
            f"{os.path.relpath(audit_path)}: output format must use 'Formulaic Writing Risk Score'"
        )

    return errors


def check_authorship_disclaimer(skills_dir):
    """Check that audit skill states the score cannot prove AI authorship."""
    errors = []
    audit_path = os.path.join(skills_dir, "antislop", "SKILL.md")
    if not os.path.exists(audit_path):
        return errors

    with open(audit_path, encoding="utf-8") as f:
        text = f.read()

    if "## Audit mode" not in text and "## How to run an audit" not in text:
        return errors

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
        with open(path, encoding="utf-8") as f:
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
    os.path.join("powers", "antislop", "POWER.md"),
    "README.md",
]

VALID_SEMANTIC_TYPES = {"forbidden", "discouraged", "preferred", "structural",
                        "integrity", "evaluation"}
VALID_REVIEW_MODES = {"deterministic", "advisory", "human"}
MACHINE_CHECKABLE_DETECTION = {"exact_match", "phrase_match", "pattern_match"}
SEMANTIC_REQUIRED_FIELDS = ("semantic_type", "correction", "sources", "evidence",
                            "false_positive_boundary", "review_mode")


def check_registry_semantics(skills_dir):
    """Check rules.json semantic rule types and rule metadata.

    The rule registry gains a semantic layer (issue #86): each rule carries a
    semantic type, correction, source provenance, evidence expectation,
    false-positive boundary, and review mode. This check guards the schema so
    an unknown semantic type, a forbidden rule without deterministic evidence,
    or a rule without source provenance cannot ship.
    """
    errors = []
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors

    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    for rule in registry.get("rules", []):
        rid = rule.get("id", "?")

        semantic_type = rule.get("semantic_type")
        if semantic_type not in VALID_SEMANTIC_TYPES:
            errors.append(
                f"{os.path.relpath(registry_path)}: rule '{rid}': unknown "
                f"semantic_type '{semantic_type}' (expected one of "
                f"{sorted(VALID_SEMANTIC_TYPES)})"
            )

        review_mode = rule.get("review_mode")
        if review_mode not in VALID_REVIEW_MODES:
            errors.append(
                f"{os.path.relpath(registry_path)}: rule '{rid}': invalid "
                f"review_mode '{review_mode}' (expected one of "
                f"{sorted(VALID_REVIEW_MODES)})"
            )

        for field in SEMANTIC_REQUIRED_FIELDS:
            if field == "sources":
                sources = rule.get("sources")
                if not isinstance(sources, list) or not sources or any(
                    not isinstance(s, str) or not s for s in sources
                ):
                    errors.append(
                        f"{os.path.relpath(registry_path)}: rule '{rid}': adopted "
                        "rule without source provenance (sources must be a "
                        "non-empty list of non-empty strings)"
                    )
            elif not rule.get(field):
                errors.append(
                    f"{os.path.relpath(registry_path)}: rule '{rid}': missing "
                    f"'{field}'"
                )

        if semantic_type == "forbidden":
            if review_mode != "deterministic":
                errors.append(
                    f"{os.path.relpath(registry_path)}: rule '{rid}': forbidden "
                    "rule must be deterministic (review_mode 'deterministic')"
                )
            if rule.get("detection_class") not in MACHINE_CHECKABLE_DETECTION:
                errors.append(
                    f"{os.path.relpath(registry_path)}: rule '{rid}': forbidden "
                    "rule without deterministic evidence (detection_class "
                    f"'{rule.get('detection_class')}')"
                )

    return errors

# ASCII stand-ins a bulk find-and-replace leaves behind in place of the real
# marks: ' -- ' for an em dash, '->' for an arrow.
DASH_SUBSTITUTE = re.compile(r' -- |"-- |->')

# Every mark plus its ASCII stand-in, for comparing the same line across files.
MARK_OR_SUBSTITUTE = re.compile(r'—|–|→| -- |"-- |->')

# Slopkit-style drift corpora under skills/ (issue #91). Each is read only
# when present, so a fixture run pointed at a bare skills dir skips them.
DRIFT_CORPUS_PATHS = (
    os.path.join("skills", "antislop", "evals", "drift-fixtures.json"),
    os.path.join("skills", "antislop", "evals", "false-positive-corpus.json"),
)

# Edit-integrity operation fixtures under skills/ (issue #87).
EDIT_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                "edit-integrity-fixtures.json")

# Clarity-style review fixtures under skills/ (issue #96).
REVIEW_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                  "clarity-review-fixtures.json")

# Protected repair fixtures under skills/ (issue #92).
REPAIR_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                  "repair-fixtures.json")

# Bounded repair-loop fixtures under skills/ (issue #93).
REPAIR_LOOP_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                       "repair-loop-fixtures.json")

# Staged-scan fixtures under skills/ (issue #98).
STAGED_SCAN_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                       "staged-scan-fixtures.json")

# Output-integrity fixtures under skills/ (issue #99).
OUTPUT_INTEGRITY_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                            "output-integrity-fixtures.json")

# Density-precision fixtures under skills/ (issue #100).
DENSITY_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                   "density-precision-fixtures.json")

# Provenance fixtures under skills/ (issue #101).
PROVENANCE_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                      "provenance-fixtures.json")

# Calibration experiment and fixture corpus under skills/ (issue #89).
CALIBRATION_EXPERIMENT_PATH = os.path.join("skills", "antislop", "evals",
                                           "calibration-experiment.json")
CALIBRATION_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                       "calibration-fixtures.json")

# Sepia-style operation and venue routing fixtures under skills/ (issue #94).
SEPIA_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                 "sepia-routing-fixtures.json")

# Evidence-bound delivery envelope fixtures under skills/ (issue #95).
DELIVERY_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                    "delivery-envelope-fixtures.json")

# Say-It-Human evidence and locale routing fixtures under skills/ (issue #97).
SAY_HUMAN_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                     "say-human-fixtures.json")

# Tagore-style substance report fixtures under skills/ (issue #102).
SUBSTANCE_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                     "substance-fixtures.json")

# LinkedIn social profile fixtures under skills/ (issue #103).
LINKEDIN_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                    "linkedin-profile-fixtures.json")

CLAIM_EVIDENCE_ORDER = ("source", "logic", "experience", "inference",
                        "unknown")
LOCALE_ORDER = ("zh-CN",)
ZH_CN_RULE_ORDER = ("zh-cn-punct-width", "zh-cn-spacing",
                    "zh-cn-translationese")

SUBSTANCE_MECHANICS_ORDER = ("directness", "rhythm", "trust", "authenticity",
                             "density")
SUBSTANCE_ORDER = SUBSTANCE_MECHANICS_ORDER + ("specificity", "restraint",
                                               "voice")
SUBSTANCE_STATUS_ORDER = ("evidenced", "unsupported", "unknown",
                          "not-applicable")
CONTRIBUTION_ITEM_ORDER = ("distinct_tell", "narrow_rule", "before_after",
                           "context", "regression_fixture")

SOCIAL_POST_FEATURE_ORDER = (
    "setup", "challenge", "action", "result", "lesson", "position",
    "announcement", "steps",
)
SOCIAL_POST_TYPE_ORDER = ("lesson", "case-study", "announcement", "opinion",
                          "practical-guide")
SOCIAL_RULE_IDS = ("social-reach-promise", "social-mobile-paragraphs",
                   "social-optional-cta", "social-optional-hook",
                   "social-optional-hashtags", "social-scarl-optional")

OPERATION_ORDER = ("draft", "revise", "audit", "transform")

REVIEW_STATUSES = ("keep", "revise", "ask-author", "cut", "no-finding")
MEDIUM_ORDER = ("argument", "explanation", "evocation", "narrative", "guide",
                "reference", "message")
SEPIA_STATUSES = ("keep", "revise", "ask-author", "cut", "n/a",
                  "over-correction")
VENUE_ORDER = ("ticket", "developer-reply", "postmortem",
               "technical-article", "release-note")
VENUE_FEATURE_ORDER = (
    "timeline", "impact", "contributing-factors", "uncertainty", "repro",
    "acceptance", "answer-first", "breaking-changes", "problem-first",
    "reflection-tail",
)


def check_drift_fixtures(skills_dir):
    """Check the drift fixtures and false-positive corpus validate and pass.

    The runner (drift.py) validates the fixture schema and evaluates every
    source/candidate pair against its preservation contract, comparing each
    computed decision with the fixture's expected decision. The check imports
    the runner lazily so a fixture run pointed at a bare skills dir stays
    cheap. A corpus file that is absent is skipped, matching how the
    shipped-artifact checks behave.
    """
    errors = []
    root = repo_root_for(skills_dir)
    paths = [os.path.join(root, rel) for rel in DRIFT_CORPUS_PATHS]
    if not any(os.path.exists(path) for path in paths):
        return errors

    drift_path = os.path.join(root, "drift.py")
    if not os.path.exists(drift_path):
        return errors
    try:
        import drift  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(drift_path)}: could not import "
                      f"drift runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    for rel, is_drift in ((DRIFT_CORPUS_PATHS[0], True),
                          (DRIFT_CORPUS_PATHS[1], False)):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        relpath = os.path.relpath(path)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            errors.append(f"{relpath}: {exc}")
            continue
        entries = data.get("evals", data)
        if not isinstance(entries, list):
            errors.append(f"{relpath}: must be a JSON list or carry an "
                          "'evals' list")
            continue
        if is_drift:
            report = drift.run_drift_corpus(entries, registry, registry_path)
        else:
            report = drift.run_false_positive_corpus(entries, registry,
                                                     registry_path)

        for schema_error in report["schema_errors"]:
            errors.append(f"{relpath}: {schema_error}")
        for failure in report.get("failures", []):
            fid = failure.get("id", "?")
            if "expected" in failure and "got" in failure:
                errors.append(
                    f"{relpath}: fixture '{fid}' expected decision "
                    f"{failure['expected']}, got {failure['got']}: "
                    f"{'; '.join(failure.get('reasons', []))}"
                )
            else:
                errors.append(
                    f"{relpath}: entry '{fid}' failed: "
                    f"{', '.join(failure.get('entry_failures', []))}"
                )
        for corpus_failure in report.get("corpus_failures", []):
            errors.append(f"{relpath}: {corpus_failure}")

    return errors


def check_registry_operations(skills_dir):
    """Check rules.json carries the edit operations and inventory contract.

    The registry gains an operation layer (issue #87): four named operations
    with an authority and a boundary, plus the inventory categories that a
    revise or transform must preserve. This check guards the schema so a
    missing operation, a missing authority or boundary, or an empty inventory
    cannot ship.
    """
    errors = []
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors

    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    relpath = os.path.relpath(registry_path)
    operations = registry.get("operations")
    if not isinstance(operations, dict):
        errors.append(f"{relpath}: missing 'operations' object with draft, "
                      "revise, audit, and transform")
    else:
        for name in OPERATION_ORDER:
            op = operations.get(name)
            if not isinstance(op, dict):
                errors.append(f"{relpath}: operations missing '{name}'")
                continue
            for field in ("authority", "boundary"):
                if not (isinstance(op.get(field), str)
                        and op[field].strip()):
                    errors.append(f"{relpath}: operations.{name} missing "
                                  f"non-empty '{field}'")

    categories = registry.get("inventory_categories")
    if not isinstance(categories, list) or not categories or any(
            not isinstance(c, str) or not c.strip() for c in categories):
        errors.append(f"{relpath}: inventory_categories must be a non-empty "
                      "list of non-empty strings")
    return errors


def check_operation_skill_guidance(skills_dir):
    """Check the routed skill surface states the edit operations explicitly.

    Operation selection must be explicit in skill behavior (issue #87). The
    public router may delegate the full contract to a linked reference, but
    the combined runtime surface must name all four operations so an audit
    cannot drift into a rewrite and a revise cannot change claim scope.
    """
    errors = []
    skill_dir = os.path.join(skills_dir, "antislop")
    skill_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_path):
        return []
    preservation_path = os.path.join(
        skill_dir, "references", "preservation-contract.md"
    )
    paths = [skill_path]
    if os.path.exists(preservation_path):
        paths.append(preservation_path)
    content = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            content.append(f.read())
    text = "\n".join(content)
    relpath = os.path.relpath(skill_path)
    if "## Edit operations" not in text:
        errors.append(f"{relpath}: routed surface missing '## Edit operations' section")
    missing = [name for name in OPERATION_ORDER
               if re.search(rf"\b{name}\b", text, re.IGNORECASE) is None]
    if missing:
        errors.append(f"{relpath}: routed surface missing operation names: "
                      f"{', '.join(missing)}")
    return errors


def check_edit_integrity_fixtures(skills_dir):
    """Check the edit-integrity fixtures validate and match their decisions.

    The runner (edit.py) validates the fixture schema and evaluates every
    source/candidate pair against its operation's authority, comparing each
    computed decision with the fixture's expected decision. The check imports
    the runner lazily so a fixture run pointed at a bare skills dir stays
    cheap. A corpus file that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, EDIT_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    edit_path = os.path.join(root, "edit.py")
    if not os.path.exists(edit_path):
        return errors
    try:
        import edit  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(edit_path)}: could not import edit "
                      f"runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = edit.run_edit_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('operation', '?')}) "
            f"expected decision {failure['expected']}, got "
            f"{failure['got']}: {'; '.join(failure.get('reasons', []))}"
        )
    return errors


def check_registry_review(skills_dir):
    """Check rules.json carries the review statuses and medium routing.

    The registry gains a review layer (issue #96): five review statuses and
    seven mediums whose routing changes structural expectations without
    weakening absolute rules. This check guards the schema so a missing
    status, a missing medium, or an empty medium routing cannot ship.
    """
    errors = []
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors

    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    relpath = os.path.relpath(registry_path)

    statuses = registry.get("review_statuses")
    if not isinstance(statuses, dict):
        errors.append(f"{relpath}: missing 'review_statuses' object with the "
                      "five statuses")
    else:
        for name in REVIEW_STATUSES:
            status = statuses.get(name)
            if not (isinstance(status, str) and status.strip()):
                errors.append(f"{relpath}: review_statuses missing non-empty "
                              f"'{name}'")

    mediums = registry.get("mediums")
    if not isinstance(mediums, dict):
        errors.append(f"{relpath}: missing 'mediums' object with the seven "
                      "mediums")
    else:
        for name in MEDIUM_ORDER:
            medium = mediums.get(name)
            if not isinstance(medium, dict):
                errors.append(f"{relpath}: mediums missing '{name}'")
                continue
            for field in ("description", "optimize", "preserve", "avoid"):
                if not (isinstance(medium.get(field), str)
                        and medium[field].strip()):
                    errors.append(f"{relpath}: mediums.{name} missing "
                                  f"non-empty '{field}'")
    return errors


def check_registry_venues(skills_dir):
    """Check rules.json carries the sepia venue routing and its statuses.

    The registry gains a Sepia-style routing layer (issue #94): the n/a and
    over-correction statuses, a fiction profile that never affects general
    or technical scoring, the deterministic venue features, and five venues
    whose applicable and not-applicable feature lists activate distinct
    expectations. This check guards the schema so a missing status, venue,
    feature, or an incomplete feature routing cannot ship.
    """
    errors = []
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors

    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    relpath = os.path.relpath(registry_path)

    for name in SEPIA_STATUSES:
        status = registry.get("review_statuses", {}).get(name)
        if not (isinstance(status, str) and status.strip()):
            errors.append(f"{relpath}: review_statuses missing non-empty "
                          f"'{name}'")

    fiction = registry.get("profiles", {}).get("fiction")
    if not (isinstance(fiction, dict) and fiction.get("description")):
        errors.append(f"{relpath}: profiles missing the opt-in 'fiction' "
                      "profile with a description")

    features = registry.get("venue_features")
    if not isinstance(features, dict):
        errors.append(f"{relpath}: missing 'venue_features' object")
    else:
        for name in VENUE_FEATURE_ORDER:
            feature = features.get(name)
            if not isinstance(feature, dict):
                errors.append(f"{relpath}: venue_features missing '{name}'")
                continue
            for field in ("name", "description", "deterministic"):
                if not (isinstance(feature.get(field), str)
                        and feature[field].strip()):
                    errors.append(f"{relpath}: venue_features.{name} missing "
                                  f"non-empty '{field}'")

    venues = registry.get("venues")
    if not isinstance(venues, dict):
        errors.append(f"{relpath}: missing 'venues' object with the five "
                      "venues")
    else:
        known = set(VENUE_FEATURE_ORDER)
        for name in VENUE_ORDER:
            venue = venues.get(name)
            if not isinstance(venue, dict):
                errors.append(f"{relpath}: venues missing '{name}'")
                continue
            for field in ("description", "optimize", "preserve", "avoid"):
                if not (isinstance(venue.get(field), str)
                        and venue[field].strip()):
                    errors.append(f"{relpath}: venues.{name} missing "
                                  f"non-empty '{field}'")
            for field in ("applicable", "not_applicable"):
                value = venue.get(field)
                if not isinstance(value, list):
                    errors.append(f"{relpath}: venues.{name}.{field} must be "
                                  "a list")
                    continue
                for feature_id in value:
                    if feature_id not in known:
                        errors.append(f"{relpath}: venues.{name}.{field} "
                                      f"references unknown feature "
                                      f"'{feature_id}'")
            applicable = set(venue.get("applicable", []))
            not_applicable = set(venue.get("not_applicable", []))
            if applicable & not_applicable:
                errors.append(f"{relpath}: venues.{name} lists the same "
                              "feature as both applicable and not_applicable")
    return errors


def check_review_fixtures(skills_dir):
    """Check the clarity-review fixtures validate and match their decisions.

    The runner (review.py) validates the fixture schema and evaluates every
    single-artifact review against its expected statuses, author questions,
    and no-invention guarantees, comparing each computed decision with the
    fixture's expected decision. The check imports the runner lazily so a
    fixture run pointed at a bare skills dir stays cheap. A corpus file that
    is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, REVIEW_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    review_path = os.path.join(root, "review.py")
    if not os.path.exists(review_path):
        return errors
    try:
        import review  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(review_path)}: could not import "
                      f"review runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = review.run_review_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('medium', '?')}) "
            f"expected decision {failure['expected']}, got "
            f"{failure['got']}: {'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_repair_fixtures(skills_dir):
    """Check the protected repair fixtures validate and match their decisions.

    The runner (repair.py) validates the fixture schema and evaluates every
    source against its expected decision, exact text, replacement records,
    integrity removals, and preserved regions, comparing each computed
    decision with the fixture's expected decision. The check imports the
    runner lazily so a fixture run pointed at a bare skills dir stays cheap. A
    corpus file that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, REPAIR_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    repair_path = os.path.join(root, "repair.py")
    if not os.path.exists(repair_path):
        return errors
    try:
        import repair  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(repair_path)}: could not import "
                      f"repair runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = repair.run_repair_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('profile', '?')}) "
            f"expected decision {failure['expected']}, got "
            f"{failure['got']}: {'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_repair_loop_fixtures(skills_dir):
    """Check the bounded repair-loop fixtures validate and match their traces.

    The runner (repair_loop.py) validates the fixture schema and evaluates
    every source through the bounded detect, select, apply, verify, gate,
    decide loop, comparing each computed decision, attempt and retry count,
    replaced rule IDs, unchanged spans, rollback state, and execution flags
    with the fixture expectations. The check imports the runner lazily so a
    fixture run pointed at a bare skills dir stays cheap. A corpus file that
    is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, REPAIR_LOOP_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "repair_loop.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import repair_loop  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"repair_loop runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = repair_loop.run_repair_loop_corpus(entries, registry,
                                                registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('profile', '?')}) "
            f"expected decision {failure['expected']}, got "
            f"{failure['got']}: {'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_calibration_fixtures(skills_dir):
    """Check the calibration experiment validates and its gate passes.

    The runner (calibration.py) validates the fixture schema and the
    experiment config, runs the baseline and candidate implementations over
    the same frozen fixture revision, and reports a gate result. The check
    imports the runner lazily so a fixture run pointed at a bare skills dir
    stays cheap. A corpus file that is absent is skipped. Reported per-category
    regressions are data, not gate failures; only a failing gate (configured
    false-positive, recall, or preservation regressions, or a threshold
    breach) fails the validation.
    """
    errors = []
    root = repo_root_for(skills_dir)
    config_path = os.path.join(root, CALIBRATION_EXPERIMENT_PATH)
    if not os.path.exists(config_path):
        return errors

    calibration_path = os.path.join(root, "calibration.py")
    if not os.path.exists(calibration_path):
        return errors
    try:
        import calibration  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(calibration_path)}: could not import "
                      f"calibration runner: {exc}")
        return errors

    base_dir = os.path.dirname(config_path)
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(config_path)}: {exc}")
        return errors

    config_errors = calibration.validate_experiment_config(config)
    for config_error in config_errors:
        errors.append(f"{os.path.relpath(config_path)}: {config_error}")
    if config_errors:
        return errors

    fixture_path = calibration._resolve(
        config.get("fixture_path", "calibration-fixtures.json"), base_dir)
    if not os.path.exists(fixture_path):
        errors.append(f"{os.path.relpath(fixture_path)}: missing calibration "
                      "fixture corpus")
        return errors
    try:
        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(fixture_path)}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{os.path.relpath(fixture_path)}: must be a JSON list "
                      "or carry an 'evals' list")
        return errors

    registry_path = calibration._resolve(
        config.get("registry", "rules.json"), base_dir)
    if not os.path.exists(registry_path):
        registry_path = config.get("registry", "rules.json")

    try:
        baseline = calibration.build_implementation(config["baseline"], base_dir)
        candidate = calibration.build_implementation(config["candidate"],
                                                     base_dir)
    except (KeyError, ValueError, OSError) as exc:
        errors.append(f"{os.path.relpath(config_path)}: implementation "
                      f"error: {exc}")
        return errors

    try:
        report = calibration.run_experiment(entries, baseline, candidate,
                                            config,
                                            registry_path=registry_path)
    except ValueError as exc:
        errors.append(f"{os.path.relpath(config_path)}: {exc}")
        return errors

    for failure in report["gate"]["failures"]:
        errors.append(f"{os.path.relpath(config_path)}: gate failure: "
                      f"{failure}")
    return errors


def check_staged_scan_fixtures(skills_dir):
    """Check the staged-scan fixtures validate and match their stages.

    The runner (scan.py) validates the fixture schema and evaluates every
    fixture against its expected surface counts, structural decision and
    bound, and corpus state, comparing each computed result with the fixture
    expectations. The check imports the runner lazily so a fixture run pointed
    at a bare skills dir stays cheap. A corpus file that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, STAGED_SCAN_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    scan_path = os.path.join(root, "scan.py")
    if not os.path.exists(scan_path):
        return errors
    try:
        import scan  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(scan_path)}: could not import "
                      f"scan runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = scan.run_staged_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('profile', '?')}): "
            f"{'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_output_integrity_fixtures(skills_dir):
    """Check the output-integrity fixtures validate and match their kinds.

    The runner (output_integrity.py) validates the fixture schema and
    evaluates every fixture against its expected per-kind counts, finding
    count, and sample status, comparing each computed result with the
    fixture expectations. The check imports the runner lazily so a fixture
    run pointed at a bare skills dir stays cheap. A corpus file that is
    absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, OUTPUT_INTEGRITY_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "output_integrity.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import output_integrity  # noqa: F401 -- lazy import
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"output_integrity runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = output_integrity.run_output_integrity_corpus(
        entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('profile', '?')}): "
            f"{'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_density_precision_fixtures(skills_dir):
    """Check the density-precision fixtures validate and match their results.

    The runner (density.py) validates the fixture schema and evaluates every
    fixture against its expected density count, precision count, exempt and
    unsourced statistics, review decision, statuses, and author questions,
    comparing each computed result with the fixture expectations. The check
    imports the runner lazily so a fixture run pointed at a bare skills dir
    stays cheap. A corpus file that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, DENSITY_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "density.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import density  # noqa: F401 -- lazy import
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"density runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = density.run_density_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('medium', '?')}): "
            f"{'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_sepia_fixtures(skills_dir):
    """Check the sepia-routing fixtures validate and match their decisions.

    The runner (sepia.py) validates the fixture schema and evaluates every
    fixture under its operation (review, refactor, or recreate) against its
    expected decision, statuses, venue checks, applied, rejected, and
    unresolved findings, and preserved inventory. The check imports the
    runner lazily so a fixture run pointed at a bare skills dir stays cheap.
    A corpus file that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, SEPIA_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "sepia.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import sepia  # noqa: F401 -- lazy import
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"sepia runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = sepia.run_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('operation', '?')} "
            f"/ {failure.get('venue') or failure.get('profile', '?')}): "
            f"{'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_delivery_fixtures(skills_dir):
    """Check the delivery-envelope fixtures validate and match their decisions.

    The runner (delivery.py) validates the fixture schema and evaluates every
    fixture as a verify, chunked, or envelope case against its expected
    decision and typed failure kinds. The check imports the runner lazily so
    a fixture run pointed at a bare skills dir stays cheap. A corpus file
    that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, DELIVERY_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "delivery.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import delivery  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"delivery runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = delivery.run_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('kind', '?')}) "
            f"expected decision {failure['expected']}, got "
            f"{failure['got']}: {'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_registry_say_human(skills_dir):
    """Check rules.json carries the claim evidence classes and locale profile.

    The registry gains a Say-It-Human layer (issue #97): five claim evidence
    classes (source, logic, experience, inference, unknown) and an opt-in
    zh-CN locale profile with advisory punctuation-width, spacing, and
    translationese rules. This check guards the schema so a missing evidence
    class, an unknown locale, or a locale rule without a deterministic
    condition and a false-positive boundary cannot ship.
    """
    errors = []
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors

    runner_path = os.path.join(root, "say_human.py")
    if not os.path.exists(runner_path):
        return errors

    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    relpath = os.path.relpath(registry_path)

    claim_evidence = registry.get("claim_evidence_classes")
    if not isinstance(claim_evidence, dict):
        errors.append(f"{relpath}: missing 'claim_evidence_classes' object")
    else:
        for name in CLAIM_EVIDENCE_ORDER:
            description = claim_evidence.get(name)
            if not (isinstance(description, str) and description.strip()):
                errors.append(f"{relpath}: claim_evidence_classes missing "
                              f"non-empty '{name}'")

    locales = registry.get("locales")
    if not isinstance(locales, dict):
        errors.append(f"{relpath}: missing 'locales' object")
        return errors
    for name in LOCALE_ORDER:
        locale = locales.get(name)
        if not isinstance(locale, dict):
            errors.append(f"{relpath}: locales missing '{name}'")
            continue
        if not (isinstance(locale.get("description"), str)
                and locale["description"].strip()):
            errors.append(f"{relpath}: locales.{name} missing non-empty "
                          "'description'")
        rules = locale.get("rules")
        if not isinstance(rules, dict):
            errors.append(f"{relpath}: locales.{name} missing 'rules' object")
            continue
        for rule_id in ZH_CN_RULE_ORDER:
            rule = rules.get(rule_id)
            if not isinstance(rule, dict):
                errors.append(f"{relpath}: locales.{name}.rules missing "
                              f"'{rule_id}'")
                continue
            for field in ("name", "deterministic", "false_positive_boundary"):
                if not (isinstance(rule.get(field), str)
                        and rule[field].strip()):
                    errors.append(f"{relpath}: locales.{name}.rules.{rule_id} "
                                  f"missing non-empty '{field}'")
    return errors


def check_say_human_fixtures(skills_dir):
    """Check the say-human fixtures validate and match their decisions.

    The runner (say_human.py) validates the fixture schema and evaluates
    every fixture as a label, repair, or locale case against its expected
    evidence, decision, protected spans, needs-source requests, locale
    findings, and venue checks. The check imports the runner lazily so a
    fixture run pointed at a bare skills dir stays cheap. A corpus file that
    is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, SAY_HUMAN_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "say_human.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import say_human  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"say_human runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = say_human.run_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('kind', '?')}) "
            f"expected decision {failure['expected']}, got "
            f"{failure['got']}: {'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_registry_substance(skills_dir):
    """Check rules.json carries the substance dimensions and statuses.

    The registry gains a Tagore-style layer (issue #102): two groups of
    dimensions (mechanics and substance), four substance statuses, and the
    change-contribution contract items from Tagore's contributor guide. This
    check guards the schema so a missing dimension, an unknown status, or a
    missing contribution-contract item cannot ship.
    """
    errors = []
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors

    runner_path = os.path.join(root, "substance.py")
    if not os.path.exists(runner_path):
        return errors

    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    relpath = os.path.relpath(registry_path)

    dimensions = registry.get("substance_dimensions")
    if not isinstance(dimensions, dict):
        errors.append(f"{relpath}: missing 'substance_dimensions' object "
                      "with mechanics and substance groups")
    else:
        mechanics = dimensions.get("mechanics")
        if not isinstance(mechanics, dict):
            errors.append(f"{relpath}: substance_dimensions missing the "
                          "'mechanics' group")
        else:
            for name in SUBSTANCE_MECHANICS_ORDER:
                if not (isinstance(mechanics.get(name), str)
                        and mechanics[name].strip()):
                    errors.append(f"{relpath}: "
                                  "substance_dimensions.mechanics missing "
                                  f"non-empty '{name}'")
        substance = dimensions.get("substance")
        if not isinstance(substance, dict):
            errors.append(f"{relpath}: substance_dimensions missing the "
                          "'substance' group")
        else:
            for name in SUBSTANCE_ORDER[len(SUBSTANCE_MECHANICS_ORDER):]:
                if not (isinstance(substance.get(name), str)
                        and substance[name].strip()):
                    errors.append(f"{relpath}: "
                                  "substance_dimensions.substance missing "
                                  f"non-empty '{name}'")

    statuses = registry.get("substance_statuses")
    if not isinstance(statuses, dict):
        errors.append(f"{relpath}: missing 'substance_statuses' object")
    else:
        for name in SUBSTANCE_STATUS_ORDER:
            if not (isinstance(statuses.get(name), str)
                    and statuses[name].strip()):
                errors.append(f"{relpath}: substance_statuses missing "
                              f"non-empty '{name}'")

    contract = registry.get("contribution_contract")
    if not isinstance(contract, dict):
        errors.append(f"{relpath}: missing 'contribution_contract' object")
    else:
        source = contract.get("source")
        if not (isinstance(source, str)
                and "1238743725cb2d731b780f237c82e0041c9b4c67" in source):
            errors.append(f"{relpath}: contribution_contract missing the "
                          "pinned Tagore contributor-guide source")
        items = contract.get("items")
        if not isinstance(items, list):
            errors.append(f"{relpath}: contribution_contract.items must be "
                          "a list")
        else:
            seen = []
            for item in items:
                if not isinstance(item, dict):
                    errors.append(f"{relpath}: contribution_contract item "
                                  "must be an object")
                    continue
                if not (isinstance(item.get("id"), str)
                        and item["id"].strip()):
                    errors.append(f"{relpath}: contribution_contract item "
                                  "missing non-empty 'id'")
                    continue
                seen.append(item["id"])
                if not (isinstance(item.get("description"), str)
                        and item["description"].strip()):
                    errors.append(f"{relpath}: "
                                  "contribution_contract item '%s' missing "
                                  "non-empty 'description'" % item["id"])
                if not isinstance(item.get("required"), bool):
                    errors.append(f"{relpath}: "
                                  "contribution_contract item '%s' missing "
                                  "boolean 'required'" % item["id"])
            if seen != list(CONTRIBUTION_ITEM_ORDER):
                errors.append(f"{relpath}: contribution_contract.items must "
                              "be exactly %s in order"
                              % ", ".join(CONTRIBUTION_ITEM_ORDER))
    return errors


def check_substance_fixtures(skills_dir):
    """Check the substance fixtures validate and match their expectations.

    The runner (substance.py) validates the fixture schema and evaluates
    every report fixture against its expected dimension statuses and risk
    score, every contribution fixture against its expected acceptance and
    failure items, and every report against the no-human-or-AI label rule.
    The check imports the runner lazily so a fixture run pointed at a bare
    skills dir stays cheap. A corpus file that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, SUBSTANCE_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "substance.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import substance  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"substance runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = substance.run_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('kind', '?')}) "
            f"expected {failure['expected']}, got {failure['got']}: "
            f"{'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_registry_provenance(skills_dir):
    """Check rules.json carries the evidence metadata and review queue.

    The registry gains a provenance layer (issue #101): per-rule evidence
    metadata with an evidence class, decay state, review dates, and pinned
    external sources, plus a stale-lexical review queue and fixture-backed
    candidate metrics. This check guards the schema so an unknown evidence
    class, an adopted concept without an exact commit and permalink, a strict
    rule with an unsourced numeric threshold, or a review-queue entry that
    would silently disable a rule cannot ship. The runner owns the schema, so
    it is imported lazily and reused here.
    """
    errors = []
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors

    provenance_path = os.path.join(root, "provenance.py")
    if not os.path.exists(provenance_path):
        return errors
    try:
        import provenance  # noqa: F401 -- lazy import keeps fixture runs cheap
    except ImportError as exc:
        errors.append(f"{os.path.relpath(provenance_path)}: could not import "
                      f"provenance runner: {exc}")
        return errors

    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    for schema_error in provenance.validate_evidence_schema(registry):
        errors.append(f"{os.path.relpath(registry_path)}: {schema_error}")
    return errors


def check_provenance_fixtures(skills_dir):
    """Check the provenance fixtures validate and match their expectations.

    The runner (provenance.py) validates the evidence metadata schema and the
    fixture corpus, runs every rule fixture's detection against the registry,
    and verifies each candidate's matched-length and matched-profile clean
    cases. The check imports the runner lazily so a fixture run pointed at a
    bare skills dir stays cheap. A corpus file that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, PROVENANCE_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "provenance.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import provenance  # noqa: F401 -- lazy import
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"provenance runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = provenance.run_provenance_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('kind', '?')}): "
            f"{'; '.join(failure.get('findings', []))}"
        )
    return errors


def check_humanizer_review_fixtures(skills_dir):
    """Check paired fixtures for the pinned Humanizer 3.0 review."""
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, HUMANIZER_REVIEW_CORPUS_PATH)
    if not os.path.exists(path):
        return errors
    provenance_path = os.path.join(root, "provenance.py")
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(provenance_path) or not os.path.exists(registry_path):
        return errors
    try:
        import provenance  # noqa: F401 -- lazy import
        with open(path, encoding="utf-8") as f:
            corpus = json.load(f)
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (ImportError, OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(path)}: could not load review corpus: {exc}")
        return errors
    entries = corpus.get("evals", corpus) if isinstance(corpus, dict) else corpus
    for schema_error in provenance.validate_source_review_fixtures(entries, registry):
        errors.append(f"{os.path.relpath(path)}: {schema_error}")
    return errors

def check_registry_social_linkedin(skills_dir):
    """Check rules.json carries the opt-in social-linkedin profile and its
    post-type routing.

    The registry gains a LinkedIn social layer (issue #103): an opt-in
    `social-linkedin` profile, deterministic social post features, five post
    types whose applicable and not-applicable feature lists route which
    structural elements fit, and profile-scoped social rules that must never
    fire under general or technical scoring. This check guards the schema so
    a missing profile, an unknown post type or feature, an overlapping
    routing, or a social rule leaking into the general profile cannot ship.
    """
    errors = []
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors

    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    relpath = os.path.relpath(registry_path)

    social = registry.get("profiles", {}).get("social-linkedin")
    if not (isinstance(social, dict) and social.get("description")):
        errors.append(f"{relpath}: profiles missing the opt-in "
                      "'social-linkedin' profile with a description")
    elif social.get("default"):
        errors.append(f"{relpath}: profiles.social-linkedin must not be the "
                      "default profile")

    features = registry.get("social_post_features")
    if not isinstance(features, dict):
        errors.append(f"{relpath}: missing 'social_post_features' object")
    else:
        for name in SOCIAL_POST_FEATURE_ORDER:
            feature = features.get(name)
            if not isinstance(feature, dict):
                errors.append(f"{relpath}: social_post_features missing "
                              f"'{name}'")
                continue
            for field in ("name", "description", "deterministic"):
                if not (isinstance(feature.get(field), str)
                        and feature[field].strip()):
                    errors.append(f"{relpath}: social_post_features.{name} "
                                  f"missing non-empty '{field}'")

    post_types = registry.get("social_post_types")
    if not isinstance(post_types, dict):
        errors.append(f"{relpath}: missing 'social_post_types' object with "
                      "the five post types")
    else:
        known = set(SOCIAL_POST_FEATURE_ORDER)
        for name in SOCIAL_POST_TYPE_ORDER:
            post_type = post_types.get(name)
            if not isinstance(post_type, dict):
                errors.append(f"{relpath}: social_post_types missing "
                              f"'{name}'")
                continue
            for field in ("description", "optimize", "preserve", "avoid"):
                if not (isinstance(post_type.get(field), str)
                        and post_type[field].strip()):
                    errors.append(f"{relpath}: social_post_types.{name} "
                                  f"missing non-empty '{field}'")
            for field in ("applicable", "not_applicable"):
                value = post_type.get(field)
                if not isinstance(value, list):
                    errors.append(f"{relpath}: social_post_types.{name}."
                                  f"{field} must be a list")
                    continue
                for feature_id in value:
                    if feature_id not in known:
                        errors.append(f"{relpath}: social_post_types.{name}."
                                      f"{field} references unknown feature "
                                      f"'{feature_id}'")
            applicable = set(post_type.get("applicable", []))
            not_applicable = set(post_type.get("not_applicable", []))
            if applicable & not_applicable:
                errors.append(f"{relpath}: social_post_types.{name} lists "
                              "the same feature as both applicable and "
                              "not_applicable")

    rules_by_id = {rule["id"]: rule for rule in registry.get("rules", [])}
    for rule_id in SOCIAL_RULE_IDS:
        rule = rules_by_id.get(rule_id)
        if rule is None:
            errors.append(f"{relpath}: missing social rule '{rule_id}'")
            continue
        profiles = set(rule.get("profiles", []))
        if "social-linkedin" not in profiles:
            errors.append(f"{relpath}: rule '{rule_id}' must be scoped to "
                          "the social-linkedin profile")
        if "*" in profiles:
            errors.append(f"{relpath}: rule '{rule_id}' must not be "
                          "universal")

    active_general = {
        rule["id"] for rule in registry.get("rules", [])
        if "*" in rule.get("profiles", ["general"])
        or "general" in rule.get("profiles", ["general"])
    }
    leaked = active_general & set(SOCIAL_RULE_IDS)
    if leaked:
        errors.append(f"{relpath}: social rule(s) {sorted(leaked)} fire "
                      "under the general profile")
    return errors


def check_social_linkedin_fixtures(skills_dir):
    """Check the linkedin-profile fixtures validate and match their decisions.

    The runner (linkedin.py) validates the fixture schema and evaluates
    every fixture under its post type against its expected decision, route,
    statuses, leaked voice-sample facts, and missing preserved facts. The
    check imports the runner lazily so a fixture run pointed at a bare
    skills dir stays cheap. A corpus file that is absent is skipped.
    """
    errors = []
    root = repo_root_for(skills_dir)
    path = os.path.join(root, LINKEDIN_CORPUS_PATH)
    if not os.path.exists(path):
        return errors

    runner_path = os.path.join(root, "linkedin.py")
    if not os.path.exists(runner_path):
        return errors
    try:
        import linkedin  # noqa: F401 -- lazy import
    except ImportError as exc:
        errors.append(f"{os.path.relpath(runner_path)}: could not import "
                      f"linkedin runner: {exc}")
        return errors

    registry_path = os.path.join(root, "rules.json")
    if not os.path.exists(registry_path):
        return errors
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{os.path.relpath(registry_path)}: {exc}")
        return errors

    relpath = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        errors.append(f"{relpath}: {exc}")
        return errors
    entries = data.get("evals", data)
    if not isinstance(entries, list):
        errors.append(f"{relpath}: must be a JSON list or carry an 'evals' "
                      "list")
        return errors

    report = linkedin.run_corpus(entries, registry, registry_path)
    for schema_error in report["schema_errors"]:
        errors.append(f"{relpath}: {schema_error}")
    for failure in report.get("failures", []):
        fid = failure.get("id", "?")
        errors.append(
            f"{relpath}: fixture '{fid}' ({failure.get('post_type', '?')}): "
            f"{'; '.join(failure.get('findings', []))}"
        )
    return errors


def repo_root_for(skills_dir):
    """Repository root, taken as the parent of skills_dir."""
    return os.path.dirname(os.path.abspath(skills_dir)) or "."


def version_from_json(path):
    """Read the 'version' field out of a rules.json-style file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("version")


def canonical_version(root):
    """Read the canonical version from rules.json at the repo root.

    rules.json is the single source for the version every shipped artifact
    must carry (AGENTS.md). The lint workflows pass --expect-version-from
    rules.json and the production test assertion derives its expected version
    through this helper, so neither hardcodes the version. Returns None when
    rules.json is absent, which leaves a bare --skills-dir run version-free.
    """
    path = os.path.join(root, "rules.json")
    if not os.path.exists(path):
        return None
    return version_from_json(path)


# Humanizer 3.0 source-review fixtures under skills/ (issue #139).
HUMANIZER_REVIEW_CORPUS_PATH = os.path.join("skills", "antislop", "evals",
                                            "humanizer-3-fixtures.json")

LINT_WORKFLOWS = (
    os.path.join(".forgejo", "workflows", "lint-skills.yml"),
    os.path.join(".github", "workflows", "lint-skills.yml"),
)


def check_expect_version_declarations(skills_dir, expected):
    """Flag a lint workflow that hardcodes a stale --expect-version pin.

    Both lint-skills.yml workflows pass --expect-version-from rules.json, so
    any hardcoded --expect-version value they carry must agree with the
    canonical version. A pin left behind by a version bump fails here instead
    of silently re-declaring an old version. Files are read only when present,
    so a fixture run pointed at a bare skills dir skips them.
    """
    errors = []
    if not expected:
        return errors
    root = repo_root_for(skills_dir)
    for rel in LINT_WORKFLOWS:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for version in re.findall(r"--expect-version\s+(\S+)", text):
            if version != expected:
                errors.append(
                    f"{rel}: --expect-version {version} disagrees with canonical version {expected}"
                )
    return errors


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
        with open(path, encoding="utf-8") as f:
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

    The agent file and both SKILL.md files restate some of the same rules
    and examples. A bulk replace applied to one derivative and not its siblings
    shows up here as one sentence carrying different marks in different files.
    """
    errors = []
    seen = {}

    for path in find_shipped_artifacts(skills_dir):
        with open(path, encoding="utf-8") as f:
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


def check_derivative_versions(skills_dir, expected=None):
    """Check the hand-maintained rule derivatives carry the expected version.

    .opencode/agents/antislop.md is a hand-synced copy of rules that a version
    bump must touch alongside the skills. ADR 0002 records a bump that missed
    files and left the test suite failing on a clean tree. Checking this here
    turns that class of miss into a gate failure. POWER.md is already covered by
    check_expected_version. Each file is read only when present, so a fixture
    run pointed at a bare skills dir skips it.
    """
    errors = []
    if not expected:
        return errors
    root = repo_root_for(skills_dir)
    for rel in (os.path.join(".opencode", "agents", "antislop.md"),):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            version = extract_version_from_body(f.read())
        if version and version != expected:
            errors.append(
                f"{os.path.relpath(path)}: version={version}, expected {expected}"
            )
    return errors


def normalize_rule_text_variants(text):
    """Return punctuation-tolerant literal variants from registry rule text.

    This matches judge.py's presence-check normalization. It is still an exact
    substring comparison after slash-separated variants, dash commentary,
    surrounding quotes, and trailing sentence punctuation are removed.
    """
    variants = []
    for part in RULE_TEXT_SPLIT_RE.split(text):
        part = RULE_TEXT_DASH_TRAIL_RE.split(part)[0].strip()
        changed = True
        while changed and part:
            changed = False
            if part[-1] in RULE_TEXT_TRAILING_PUNCT:
                part = part[:-1]
                changed = True
            if part and part[0] in RULE_TEXT_QUOTE_CHARS:
                part = part[1:]
                changed = True
            if part and part[-1] in RULE_TEXT_QUOTE_CHARS:
                part = part[:-1]
                changed = True
            stripped = part.strip()
            if stripped != part:
                part = stripped
                changed = True
        if part:
            variants.append(part.lower())
    return variants


def check_rule_content(skills_dir):
    """Check literal writing rules against the complete style-skill surface."""
    root = repo_root_for(skills_dir)
    registry_path = os.path.join(root, "rules.json")
    style_dir = os.path.join(skills_dir, "antislop")
    source_paths = (
        os.path.join(style_dir, "SKILL.md"),
        os.path.join(style_dir, "references", "vocabulary.md"),
    )
    errors = []

    if not os.path.isfile(registry_path):
        return [
            f"rule-content: registry not found at {os.path.relpath(registry_path, root)}"
        ]

    missing_sources = [path for path in source_paths if not os.path.isfile(path)]
    if missing_sources:
        return [
            f"rule-content: source not found at {os.path.relpath(path, root)}"
            for path in missing_sources
        ]

    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    # SKILL.md delegates the literal vocabulary, phrase, filler, and chatbot
    # lists to this reference. Other references contain structural guidance and
    # examples, where incidental mentions would hide missing literal rules.
    content = []
    for path in source_paths:
        with open(path, encoding="utf-8") as f:
            content.append(f.read())
    content_lower = "\n".join(content).lower()
    source_names = " or ".join(os.path.relpath(path, root) for path in source_paths)

    for rule in registry.get("rules", []):
        category = rule.get("category")
        if category not in RULE_CONTENT_CATEGORIES:
            continue
        # Profile-scoped rules (marketing, social-linkedin, fiction) live in
        # their own generated reference, not the general vocabulary surface.
        rule_profiles = rule.get("profiles", ["general"])
        if "*" not in rule_profiles and "general" not in rule_profiles:
            continue
        rule_id = rule.get("id", "?")
        rule_text = rule.get("text", "")
        variants = normalize_rule_text_variants(rule_text)
        if variants and any(variant in content_lower for variant in variants):
            continue
        errors.append(
            f"rule-content: rule '{rule_id}' ({category}: {rule_text!r}) has no "
            f"detectable trace in {source_names}"
        )

    return errors


def check_plugin_manifest(skills_dir, expected=None):
    """Guard the Claude Code plugin manifests against silent drift.

    .claude-plugin/plugin.json carries a version a release bump must touch,
    but no other check covered it, so it drifted silently (AGENTS.md).
    marketplace.json restates the plugin description and was kept in sync by
    hand. Both are checked here: the version against --expect-version (when
    given), and the marketplace description against plugin.json. Each file is
    read only when present, so a fixture run pointed at a bare skills dir
    skips it, matching how the shipped-artifact checks behave.
    """
    errors = []
    root = repo_root_for(skills_dir)
    plugin_path = os.path.join(root, ".claude-plugin", "plugin.json")
    if not os.path.exists(plugin_path):
        return errors

    with open(plugin_path, encoding="utf-8") as f:
        plugin = json.load(f)

    plugin_version = plugin.get("version")
    if expected and plugin_version and plugin_version != expected:
        errors.append(
            f"{os.path.relpath(plugin_path)}: version={plugin_version}, expected {expected}"
        )

    marketplace_path = os.path.join(root, ".claude-plugin", "marketplace.json")
    if os.path.exists(marketplace_path):
        with open(marketplace_path, encoding="utf-8") as f:
            marketplace = json.load(f)
        plugin_name = plugin.get("name")
        plugin_desc = plugin.get("description")
        entry = next(
            (p for p in marketplace.get("plugins", []) if p.get("name") == plugin_name),
            None,
        )
        if entry is None:
            errors.append(
                f"{os.path.relpath(marketplace_path)}: no plugins[] entry named '{plugin_name}'"
            )
        elif plugin_desc and entry.get("description") != plugin_desc:
            errors.append(
                f"{os.path.relpath(marketplace_path)}: plugin '{plugin_name}' description "
                f"does not match {os.path.relpath(plugin_path)}"
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
        "--expect-version-from",
        default=None,
        help=(
            "Require all artifacts to be at the version read from this "
            "rules.json-style file (mutually exclusive with --expect-version)"
        ),
    )
    parser.add_argument(
        "--powers-dir",
        default="powers",
        help="Path to Kiro Powers directory (default: powers)",
    )
    parser.add_argument(
        "--check-rule-content",
        action="store_true",
        help="Check registry writing rules against the style skill",
    )
    args = parser.parse_args()

    skills_dir = args.skills_dir
    if not os.path.isdir(skills_dir):
        print(f"ERROR: skills directory not found: {skills_dir}", file=sys.stderr)
        sys.exit(2)

    if args.expect_version and args.expect_version_from:
        parser.error("--expect-version and --expect-version-from are mutually exclusive")
    if args.expect_version_from:
        try:
            args.expect_version = version_from_json(args.expect_version_from)
        except (OSError, json.JSONDecodeError) as e:
            print(
                f"ERROR: --expect-version-from {args.expect_version_from}: {e}",
                file=sys.stderr,
            )
            sys.exit(2)

    all_errors = []

    # Per-file checks
    skill_files = find_skill_files(skills_dir)
    for path in skill_files:
        all_errors.extend(validate_skill_file(path))

    for path in find_power_files(args.powers_dir):
        all_errors.extend(validate_power_file(path))

    # Cross-file checks
    all_errors.extend(check_root_plugin_manifest(skills_dir, args.expect_version))

    # Version-specific checks
    if args.expect_version:
        all_errors.extend(check_expected_version(skills_dir, args.expect_version))
        all_errors.extend(check_expect_version_declarations(skills_dir, args.expect_version))

    # Audit content checks (always run)
    all_errors.extend(check_audit_output_format(skills_dir))
    all_errors.extend(check_authorship_disclaimer(skills_dir))
    all_errors.extend(check_antithesis_consistency(skills_dir))
    all_errors.extend(check_dash_substitutes(skills_dir))
    all_errors.extend(check_dash_parity(skills_dir))
    # check_expected_version() owns manifest version checks; this handles marketplace drift.
    all_errors.extend(check_plugin_manifest(skills_dir))
    all_errors.extend(check_derivative_versions(skills_dir, args.expect_version))
    all_errors.extend(check_registry_semantics(skills_dir))
    all_errors.extend(check_registry_operations(skills_dir))
    all_errors.extend(check_registry_review(skills_dir))
    all_errors.extend(check_registry_venues(skills_dir))
    all_errors.extend(check_operation_skill_guidance(skills_dir))
    all_errors.extend(check_drift_fixtures(skills_dir))
    all_errors.extend(check_edit_integrity_fixtures(skills_dir))
    all_errors.extend(check_review_fixtures(skills_dir))
    all_errors.extend(check_repair_fixtures(skills_dir))
    all_errors.extend(check_repair_loop_fixtures(skills_dir))
    all_errors.extend(check_calibration_fixtures(skills_dir))
    all_errors.extend(check_staged_scan_fixtures(skills_dir))
    all_errors.extend(check_output_integrity_fixtures(skills_dir))
    all_errors.extend(check_density_precision_fixtures(skills_dir))
    all_errors.extend(check_registry_provenance(skills_dir))
    all_errors.extend(check_provenance_fixtures(skills_dir))
    all_errors.extend(check_humanizer_review_fixtures(skills_dir))
    all_errors.extend(check_sepia_fixtures(skills_dir))
    all_errors.extend(check_delivery_fixtures(skills_dir))
    all_errors.extend(check_registry_say_human(skills_dir))
    all_errors.extend(check_say_human_fixtures(skills_dir))
    all_errors.extend(check_registry_substance(skills_dir))
    all_errors.extend(check_substance_fixtures(skills_dir))
    all_errors.extend(check_registry_social_linkedin(skills_dir))
    all_errors.extend(check_social_linkedin_fixtures(skills_dir))

    # Rule content check (opt-in)
    if args.check_rule_content:
        all_errors.extend(check_rule_content(skills_dir))

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
