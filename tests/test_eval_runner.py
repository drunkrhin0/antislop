#!/usr/bin/env python3
"""Public evaluation-runner tests for skill intent routing."""

import json
import os
import subprocess
import sys
import unittest

from route import route_request


ROOT = os.path.join(os.path.dirname(__file__), "..")
EVAL = os.path.join(ROOT, "eval.py")


class TestEvaluationRunner(unittest.TestCase):
    def test_declared_trigger_fixtures_execute(self):
        result = subprocess.run(
            [sys.executable, EVAL, "--router-only"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["total"], 27)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["model_status"], "not_run")

    def test_explicit_prose_modes_are_routed(self):
        self.assertEqual(
            route_request("detect patterns in this prose"),
            {"skill": "antislop", "mode": "detect"},
        )
        self.assertEqual(
            route_request("edit draft.md in place to remove slop"),
            {"skill": "antislop", "mode": "edit"},
        )
        self.assertEqual(
            route_request("rewrite this paragraph"),
            {"skill": "antislop", "mode": "rewrite"},
        )


if __name__ == "__main__":
    unittest.main()
