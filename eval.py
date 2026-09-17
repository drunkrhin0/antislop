#!/usr/bin/env python3
"""Execute Antislop skill routing fixtures and report model-eval readiness."""

import argparse
import json
import os
import sys

from route import route_intent


ROOT = os.path.dirname(os.path.abspath(__file__))
EVAL_FILES = (
    os.path.join(ROOT, "skills", "antislop", "evals", "evals.json"),
    os.path.join(ROOT, "skills", "antislop", "evals", "audit-evals.json"),
)


def load_evals():
    loaded = []
    for path in EVAL_FILES:
        with open(path, encoding="utf-8") as f:
            document = json.load(f)
        for fixture in document["evals"]:
            loaded.append((document["skill_name"], fixture))
    return loaded


def run_router_evals():
    results = []
    for skill_name, fixture in load_evals():
        expected = skill_name if fixture["should_trigger"] else "none"
        actual = route_intent(fixture["prompt"])
        results.append({
            "fixture": f"{skill_name}:{fixture['id']}",
            "expected": expected,
            "actual": actual,
            "passed": actual == expected,
        })
    failed = sum(not item["passed"] for item in results)
    return {
        "status": "passed" if failed == 0 else "failed",
        "total": len(results),
        "passed": len(results) - failed,
        "failed": failed,
        "model_status": "not_run",
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Run Antislop evaluation fixtures")
    parser.add_argument(
        "--router-only",
        action="store_true",
        help="Run deterministic intent-routing checks without calling a model",
    )
    args = parser.parse_args()

    if not args.router_only:
        print(json.dumps({
            "status": "error",
            "error": "No model adapter configured. Use --router-only.",
        }))
        return 2

    result = run_router_evals()
    print(json.dumps(result, indent=2))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
