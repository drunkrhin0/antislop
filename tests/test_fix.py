#!/usr/bin/env python3
"""Tests for fix.py — the regenerate-and-reverify auto-fix engine.

Run: python3 -m pytest tests/test_fix.py -v

All fixes run against a throwaway sandbox copy of rules.json, generate.py,
validate.py, fix.py and skills/ so nothing here ever mutates the real
working tree.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def make_sandbox():
    """Copy the pieces fix.py needs into a throwaway directory."""
    tmp = tempfile.mkdtemp(prefix="antislop-fix-test-")
    for name in ("rules.json", "generate.py", "registry.py", "validate.py", "fix.py"):
        shutil.copy(os.path.join(ROOT, name), os.path.join(tmp, name))
    shutil.copytree(os.path.join(ROOT, "skills"), os.path.join(tmp, "skills"))
    return tmp


def sandbox_version(sandbox):
    """Read metadata.version out of the sandbox's antislop SKILL.md.

    Read rather than hardcoded so a version bump on the base branch does not
    break every test in this file.
    """
    path = os.path.join(sandbox, "skills/antislop/SKILL.md")
    with open(path) as f:
        text = f.read()
    m = re.search(r'^\s*version:\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise AssertionError(f"no metadata.version found in {path}")
    return m.group(1)


def patch_bump(version):
    """Return the next patch version, e.g. 2.0.0 becomes 2.0.1."""
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def run_fix(sandbox, *args):
    cmd = [sys.executable, os.path.join(sandbox, "fix.py")] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=sandbox)
    return result.returncode, result.stdout, result.stderr


def run_py(sandbox, script, *args):
    cmd = [sys.executable, os.path.join(sandbox, script)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=sandbox)
    return result.returncode, result.stdout, result.stderr


def snapshot(sandbox):
    """Return {relpath: bytes} for every file under skills/."""
    snap = {}
    for root, _dirs, files in os.walk(os.path.join(sandbox, "skills")):
        for f in files:
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                snap[os.path.relpath(p, sandbox)] = fh.read()
    return snap


class TestCleanRepoIsNoOp(unittest.TestCase):
    """AC4: running the loop on an already-clean repo makes no changes."""

    def test_running_on_clean_sandbox_makes_no_changes(self):
        sandbox = make_sandbox()
        try:
            before = snapshot(sandbox)
            rc, out, err = run_fix(sandbox)
            after = snapshot(sandbox)
            self.assertEqual(rc, 0, f"fix.py should exit 0 on a clean repo: {out}{err}")
            self.assertEqual(before, after, "fix.py modified files on an already-clean repo")
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

    def test_running_twice_in_a_row_is_idempotent(self):
        sandbox = make_sandbox()
        try:
            run_fix(sandbox)
            after_first = snapshot(sandbox)
            rc2, out2, err2 = run_fix(sandbox)
            after_second = snapshot(sandbox)
            self.assertEqual(rc2, 0, f"second run should also exit 0: {out2}{err2}")
            self.assertEqual(after_first, after_second, "second run changed files")
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)


class TestRegeneratePatternReference(unittest.TestCase):
    """AC1: drifted pattern-reference.md gets regenerated to match generate.py."""

    def test_drifted_pattern_reference_is_regenerated_and_matches_generator(self):
        sandbox = make_sandbox()
        try:
            target = os.path.join(sandbox, "skills/antislop-audit/references/pattern-reference.md")
            with open(target, "a") as f:
                f.write("\nDRIFTED LINE — this should get overwritten\n")

            rc, out, err = run_fix(sandbox)
            self.assertEqual(rc, 0, f"fix.py should resolve drift: {out}{err}")

            check_rc, check_out, check_err = run_py(sandbox, "generate.py", "--check")
            self.assertEqual(check_rc, 0, f"generate.py --check should pass after fix: {check_out}{check_err}")

            with tempfile.TemporaryDirectory() as outdir:
                run_py(sandbox, "generate.py", "--output-dir", outdir)
                gen_path = os.path.join(outdir, "skills/antislop-audit/references/pattern-reference.md")
                with open(gen_path) as f:
                    expected = f.read()
            with open(target) as f:
                actual = f.read()
            self.assertEqual(actual, expected, "regenerated file should match generate.py --output-dir output")
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)


class TestVersionPropagation(unittest.TestCase):
    """AC2: a metadata.version bump propagates to body and gemini-extension.json."""

    def test_bumped_metadata_version_propagates_to_body_and_gemini(self):
        sandbox = make_sandbox()
        try:
            current = sandbox_version(sandbox)
            target = patch_bump(current)
            skill_path = os.path.join(sandbox, "skills/antislop/SKILL.md")
            with open(skill_path) as f:
                text = f.read()
            self.assertIn(f'version: "{current}"', text)
            bumped = text.replace(f'version: "{current}"', f'version: "{target}"', 1)
            self.assertNotEqual(bumped, text)
            with open(skill_path, "w") as f:
                f.write(bumped)

            rc, out, err = run_fix(sandbox)
            self.assertEqual(rc, 0, f"fix.py should resolve the drift: {out}{err}")

            with open(skill_path) as f:
                fixed_text = f.read()
            self.assertIn(f"**Version:** {target}", fixed_text)

            gemini_path = os.path.join(sandbox, "skills/antislop/gemini-extension.json")
            with open(gemini_path) as f:
                gemini = json.load(f)
            self.assertEqual(gemini["version"], target)

            val_rc, val_out, val_err = run_py(sandbox, "validate.py", "--skills-dir", "skills")
            self.assertEqual(val_rc, 0, f"validate.py should pass after fix: {val_out}{val_err}")
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)


class TestUnresolvedFixLeavesFileUntouched(unittest.TestCase):
    """AC3: a fix attempt that can't be verified leaves the file byte-for-byte
    unmodified and is reported as unresolved, not silently dropped."""

    def test_corrupt_gemini_json_is_left_untouched_and_reported(self):
        sandbox = make_sandbox()
        try:
            current = sandbox_version(sandbox)
            target = patch_bump(current)
            skill_path = os.path.join(sandbox, "skills/antislop/SKILL.md")
            with open(skill_path) as f:
                text = f.read()
            bumped = text.replace(f'version: "{current}"', f'version: "{target}"', 1)
            bumped = bumped.replace(f"**Version:** {current}", f"**Version:** {target}", 1)
            with open(skill_path, "w") as f:
                f.write(bumped)

            gemini_path = os.path.join(sandbox, "skills/antislop/gemini-extension.json")
            with open(gemini_path) as f:
                gemini_before = f.read()
            # Malformed JSON (dangling comma with no value) — fix.py must not
            # attempt to parse-and-rewrite this.
            corrupt = gemini_before.replace(
                f'"version": "{current}",', f'"version": "{current}",\n  "broken": ,'
            )
            self.assertNotEqual(corrupt, gemini_before)
            with open(gemini_path, "w") as f:
                f.write(corrupt)

            rc, out, err = run_fix(sandbox)
            self.assertEqual(rc, 1, "fix.py should report an unresolved issue")
            self.assertIn("unresolved", (out + err).lower())

            with open(gemini_path) as f:
                gemini_after = f.read()
            self.assertEqual(gemini_after, corrupt, "corrupt file must be left byte-for-byte untouched")
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
