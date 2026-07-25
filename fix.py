#!/usr/bin/env python3
"""Regenerate-and-reverify auto-fix for Antislop propagation failures.

Consumes what check.sh (generate.py --check / validate.py) reports and
applies two mechanical fix classes:

  1. Regenerate skills/antislop-audit/references/pattern-reference.md when
     generate.py --check reports drift against rules.json.
  2. Propagate metadata.version (the canonical source — see AGENTS.md's
     "version bumps touch five places") to the body **Version:** string and
     to the paired gemini-extension.json when validate.py reports a
     version-mismatch or cross-file-drift error.

Each fix is applied, then the relevant check is re-run. A fix is kept only
if the check now passes; otherwise the file is restored byte-for-byte and
the issue is reported as unresolved. Nothing outside these two classes is
touched — everything else (including skills/antislop/GEMINI.md and
.opencode/agents/antislop.md, both documented non-mirrors) is left for
manual judgment, which is the seam issue #17 builds on.

Usage:
    python3 fix.py
    python3 fix.py --registry rules.json --skills-dir skills --profile general
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402  — reuse the frontmatter/body parsers, don't duplicate them

PATTERN_REF_RELPATH = "skills/antislop-audit/references/pattern-reference.md"

VERSION_BODY_RE = re.compile(r"(\*\*Version:\*\*\s*)([0-9][0-9a-zA-Z.\-]*)")
VERSION_JSON_RE = re.compile(r'("version"\s*:\s*")([^"]*)(")')


def _run(cmd, cwd):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def _scoped_validate(root, skill_dir):
    """Re-run validate.py scoped to a single skill's own directory."""
    return _run([sys.executable, os.path.join(root, "validate.py"),
                 "--skills-dir", skill_dir], root)


def fix_pattern_reference(root, registry, profile):
    """Regenerate pattern-reference.md if generate.py --check reports drift."""
    generate_py = os.path.join(root, "generate.py")
    target = os.path.join(root, PATTERN_REF_RELPATH)

    rc, _out, _err = _run([sys.executable, generate_py, "--check",
                            "--registry", registry, "--profile", profile], root)
    if rc == 0:
        return {"name": PATTERN_REF_RELPATH, "check": "generate", "status": "clean"}

    backup = None
    if os.path.exists(target):
        with open(target, "rb") as f:
            backup = f.read()

    with tempfile.TemporaryDirectory() as tmp:
        _run([sys.executable, generate_py, "--output-dir", tmp,
              "--registry", registry, "--profile", profile], root)
        generated = os.path.join(tmp, PATTERN_REF_RELPATH)
        if not os.path.exists(generated):
            return {"name": PATTERN_REF_RELPATH, "check": "generate", "status": "unresolved",
                     "detail": "generator did not produce the artifact"}
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(generated, target)

    rc2, out2, err2 = _run([sys.executable, generate_py, "--check",
                             "--registry", registry, "--profile", profile], root)
    if rc2 == 0:
        return {"name": PATTERN_REF_RELPATH, "check": "generate", "status": "fixed"}

    # Re-check failed — restore byte-for-byte and report, don't keep a partial fix.
    if backup is not None:
        with open(target, "wb") as f:
            f.write(backup)
    elif os.path.exists(target):
        os.remove(target)
    return {"name": PATTERN_REF_RELPATH, "check": "generate", "status": "unresolved",
             "detail": (out2 + err2).strip()}


def fix_skill_versions(root, skill_path):
    """Propagate metadata.version to body **Version:** and gemini-extension.json.

    metadata.version is treated as canonical: it's the field a version bump
    touches first (AGENTS.md), and it's the only one of the three that is
    never itself rewritten by this function.
    """
    results = []
    skill_dir = os.path.dirname(skill_path)
    relpath = os.path.relpath(skill_path, root)

    with open(skill_path) as f:
        text = f.read()
    fm = validate.parse_frontmatter(text)
    metadata = fm.get("metadata")
    canonical = metadata.get("version") if isinstance(metadata, dict) else None
    if not canonical:
        return results  # no unambiguous source of truth here — leave for manual review

    # ---- Fix class 1: body **Version:** mismatch ----
    body_version = validate.extract_version_from_body(text)
    if body_version and body_version != canonical:
        new_text, n = VERSION_BODY_RE.subn(r"\g<1>" + canonical, text, count=1)
        if n == 0:
            results.append({"name": relpath, "check": "version-mismatch", "status": "unresolved",
                             "detail": "could not locate a **Version:** string to rewrite"})
        else:
            with open(skill_path, "w") as f:
                f.write(new_text)
            rc, out, err = _scoped_validate(root, skill_dir)
            still_broken = "version mismatch" in (out + err).lower()
            if not still_broken:
                results.append({"name": relpath, "check": "version-mismatch", "status": "fixed"})
                text = new_text  # carry forward so the gemini check below sees the fixed body
            else:
                with open(skill_path, "w") as f:
                    f.write(text)
                results.append({"name": relpath, "check": "version-mismatch", "status": "unresolved",
                                 "detail": (out + err).strip()})

    # ---- Fix class 2: cross-file drift vs gemini-extension.json ----
    gemini_path = os.path.join(skill_dir, "gemini-extension.json")
    if os.path.exists(gemini_path):
        gemini_relpath = os.path.relpath(gemini_path, root)
        with open(gemini_path) as f:
            raw = f.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            results.append({"name": gemini_relpath, "check": "cross-file-drift", "status": "unresolved",
                             "detail": f"invalid JSON, left untouched: {e}"})
            data = None

        if data is not None:
            gem_version = data.get("version")
            if gem_version and gem_version != canonical:
                new_raw, n = VERSION_JSON_RE.subn(r"\g<1>" + canonical + r"\g<3>", raw, count=1)
                if n == 0:
                    results.append({"name": gemini_relpath, "check": "cross-file-drift", "status": "unresolved",
                                     "detail": "could not locate a \"version\" field to rewrite"})
                else:
                    with open(gemini_path, "w") as f:
                        f.write(new_raw)
                    rc, out, err = _scoped_validate(root, skill_dir)
                    still_broken = "cross-file version drift" in (out + err).lower()
                    if not still_broken:
                        results.append({"name": gemini_relpath, "check": "cross-file-drift", "status": "fixed"})
                    else:
                        with open(gemini_path, "w") as f:
                            f.write(raw)
                        results.append({"name": gemini_relpath, "check": "cross-file-drift", "status": "unresolved",
                                         "detail": (out + err).strip()})

    return results


def run_fixes(root, registry="rules.json", skills_dir="skills", profile="general"):
    registry_path = registry if os.path.isabs(registry) else os.path.join(root, registry)
    skills_path = skills_dir if os.path.isabs(skills_dir) else os.path.join(root, skills_dir)

    results = [fix_pattern_reference(root, registry_path, profile)]
    for skill_path in validate.find_skill_files(skills_path):
        results.extend(fix_skill_versions(root, skill_path))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate-and-reverify auto-fix for Antislop propagation failures"
    )
    parser.add_argument("--registry", default="rules.json", help="Path to rule registry")
    parser.add_argument("--skills-dir", default="skills", help="Path to skills directory")
    parser.add_argument("--profile", default="general", help="Writing profile to generate for")
    args = parser.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    results = run_fixes(root, args.registry, args.skills_dir, args.profile)

    fixed = [r for r in results if r["status"] == "fixed"]
    unresolved = [r for r in results if r["status"] == "unresolved"]

    print("")
    print("==============================================")
    print("  Antislop regenerate-and-reverify")
    print("==============================================")
    if not fixed and not unresolved:
        print("Nothing to fix — repo already clean.")
    for r in fixed:
        print(f"FIXED       {r['name']} ({r['check']})")
    for r in unresolved:
        print(f"UNRESOLVED  {r['name']} ({r['check']}): {r.get('detail', '')}")
    print("==============================================")
    if unresolved:
        print(f"{len(unresolved)} issue(s) left unresolved — needs manual review.")
    print("")

    sys.exit(1 if unresolved else 0)


if __name__ == "__main__":
    main()
