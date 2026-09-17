#!/usr/bin/env python3
"""Tests for issue 39: check.sh wired into the Forgejo lint workflow.

The Forgejo lint workflow runs the two canonical propagation commands as
separate authoritative gates. Issue 39 adds one bash check.sh step so the
combined readable report is available to reviewers on the same commit the
gates run against. These tests pin the workflow contract:

- check.sh runs on the checked-out commit, after the hardened checkout step.
- The individual generate.py --check, validate.py, and unit-suite steps remain.
- The workflow never re-introduces propagate.sh, judge.py, or an exit-2 path.
- check.sh itself has only success/failure outcomes.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FORGEJO_LINT = os.path.join(ROOT, ".forgejo", "workflows", "lint-skills.yml")


def workflow_text():
    with open(FORGEJO_LINT, encoding="utf-8") as f:
        return f.read()


def steps(text):
    """Split the workflow into step blocks by their `- name:` headings."""
    blocks = []
    current = []
    for line in text.splitlines():
        if line.startswith("      - "):
            if current:
                blocks.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def step_with(blocks, needle):
    for block in blocks:
        if needle in block:
            return block
    return None


class TestCheckStepWired(unittest.TestCase):
    """The Forgejo lint workflow runs bash check.sh on the checked-out commit."""

    def test_workflow_has_check_sh_step(self):
        block = step_with(steps(workflow_text()), "bash check.sh")
        self.assertIsNotNone(block, "workflow has no bash check.sh step")
        self.assertIn("run:", block)

    def test_check_step_fails_workflow_on_error(self):
        block = step_with(steps(workflow_text()), "bash check.sh")
        self.assertIsNotNone(block)
        self.assertNotIn("continue-on-error", block, "check.sh must fail the job on error")
        self.assertNotIn("if:", block, "check.sh step must not be conditional")

    def test_check_step_runs_after_checkout(self):
        blocks = steps(workflow_text())
        checkout = step_with(blocks, "name: Checkout")
        check = step_with(blocks, "bash check.sh")
        self.assertIsNotNone(checkout)
        self.assertIsNotNone(check)
        self.assertLess(blocks.index(checkout), blocks.index(check))

    def test_authoritative_steps_remain(self):
        text = workflow_text()
        self.assertIn(
            "python3 validate.py --skills-dir skills --expect-version-from rules.json",
            text,
        )
        self.assertIn("python3 generate.py --check", text)
        self.assertIn("python3 -m unittest discover -s tests -v", text)

    def test_no_retired_propagation_tooling(self):
        text = workflow_text()
        self.assertNotIn("propagate.sh", text)
        self.assertNotIn("judge.py", text)
        self.assertNotIn("exit 2", text)


class TestCheckScriptContract(unittest.TestCase):
    """check.sh reports success or failure only, no judgment-call exit code."""

    def _run_in_copy(self, generate_exit, validate_exit):
        tmp = tempfile.mkdtemp(prefix="antislop-check-sh-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copy(os.path.join(ROOT, "check.sh"), os.path.join(tmp, "check.sh"))
        with open(os.path.join(tmp, "generate.py"), "w", encoding="utf-8") as f:
            f.write("import sys\nsys.exit(%d)\n" % generate_exit)
        with open(os.path.join(tmp, "validate.py"), "w", encoding="utf-8") as f:
            f.write("import sys\nsys.exit(%d)\n" % validate_exit)
        return subprocess.run(["bash", "check.sh"], cwd=tmp, capture_output=True, text=True)

    def test_all_pass_exits_zero(self):
        result = self._run_in_copy(0, 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Overall: PASSED", result.stdout)

    def test_generate_failure_exits_one(self):
        result = self._run_in_copy(1, 0)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Overall: FAILED", result.stdout)
        self.assertIn("generate.py --check", result.stdout)

    def test_validate_failure_exits_one(self):
        result = self._run_in_copy(0, 1)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Overall: FAILED", result.stdout)
        self.assertIn("validate.py", result.stdout)

    def test_validate_crash_keeps_diagnostic_output(self):
        tmp = tempfile.mkdtemp(prefix="antislop-check-sh-diagnostic-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copy(os.path.join(ROOT, "check.sh"), os.path.join(tmp, "check.sh"))
        with open(os.path.join(tmp, "generate.py"), "w", encoding="utf-8") as f:
            f.write("import sys\nsys.exit(0)\n")
        with open(os.path.join(tmp, "validate.py"), "w", encoding="utf-8") as f:
            f.write(
                "import sys\n"
                "print('synthetic validator traceback', file=sys.stderr)\n"
                "sys.exit(1)\n"
            )

        result = subprocess.run(
            ["bash", "check.sh"], cwd=tmp, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("synthetic validator traceback", result.stdout)

    def test_no_exit_2_warning_path(self):
        for generate_exit, validate_exit in ((1, 0), (0, 1), (1, 1)):
            with self.subTest(generate_exit=generate_exit, validate_exit=validate_exit):
                result = self._run_in_copy(generate_exit, validate_exit)
                self.assertNotEqual(result.returncode, 2, "check.sh must never exit 2")


if __name__ == "__main__":
    unittest.main()
