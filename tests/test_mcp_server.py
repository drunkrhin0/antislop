#!/usr/bin/env python3
"""End-to-end tests for the packaged read-only MCP server."""

import json
import os
import subprocess
import sys
import unittest

from tests.test_preserve import ORIGINAL, VALID_REWRITE


INVALID_REWRITE = VALID_REWRITE.replace(
    "> Keep the old rollback path.",
    "> Remove the old rollback path.",
)


ROOT = os.path.join(os.path.dirname(__file__), "..")
SERVER = os.path.join(ROOT, "mcp_server.py")


def call_server(requests):
    payload = "".join(json.dumps(request) + "\n" for request in requests)
    result = subprocess.run(
        [sys.executable, SERVER],
        input=payload,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    responses = [json.loads(line) for line in result.stdout.splitlines() if line]
    return result.returncode, responses, result.stderr


class TestPackagedMCPServer(unittest.TestCase):
    def test_tools_are_discoverable_and_call_shared_runtime(self):
        score_text = (
            "By [Your Name], cite citeturn0search0. "
            + "Ordinary facts remain unchanged. " * 130
        )
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "score_text",
                    "arguments": {"text": score_text, "detail": "full"},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "validate_rewrite",
                    "arguments": {"original": ORIGINAL, "rewrite": VALID_REWRITE},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "prepare_rewrite",
                    "arguments": {
                        "text": ORIGINAL,
                        "voice": "blunt",
                        "context": "investor-email",
                        "mechanics": "british",
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "review_rewrite",
                    "arguments": {
                        "original": ORIGINAL,
                        "rewrite": INVALID_REWRITE,
                    },
                },
            },
        ]

        rc, responses, stderr = call_server(requests)

        self.assertEqual(rc, 0, stderr)
        tools = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertEqual(
            tools,
            {"score_text", "validate_rewrite", "prepare_rewrite", "review_rewrite"},
        )

        score = responses[2]["result"]["structuredContent"]
        self.assertIn(
            "struct-unfilled-placeholders",
            {finding["rule_id"] for finding in score["findings"]},
        )
        self.assertEqual(score["status"], "manual_review_required")

        preservation = responses[3]["result"]["structuredContent"]
        self.assertTrue(preservation["valid"])

        prepared = responses[4]["result"]["structuredContent"]
        self.assertEqual(prepared["selection"]["voice"], "blunt")
        self.assertIn("Terse and direct", prepared["guidance"])
        self.assertIn("investor updates", prepared["guidance"])
        self.assertIn("British English", prepared["guidance"])

        review = responses[5]["result"]["structuredContent"]
        self.assertFalse(review["accepted"])
        self.assertEqual(review["status"], "blocked_by_preservation")
        self.assertFalse(review["preservation"]["valid"])

    def test_invalid_profile_axes_return_a_bounded_tool_error(self):
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "score_text",
                    "arguments": {
                        "text": "Ordinary facts remain unchanged. " * 20,
                        "voice": "imaginary",
                    },
                },
            }
        ]

        rc, responses, stderr = call_server(requests)

        self.assertEqual(rc, 0, stderr)
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertIn("unknown voice", responses[0]["error"]["message"])

    def test_oversized_tool_input_is_rejected_before_analysis(self):
        requests = [{
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "score_text",
                "arguments": {"text": "x" * 250001},
            },
        }]

        rc, responses, stderr = call_server(requests)

        self.assertEqual(rc, 0, stderr)
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertIn("250000 characters", responses[0]["error"]["message"])

    def test_required_fields_and_schema_values_are_enforced(self):
        requests = [
            {
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "score_text", "arguments": {}},
            },
            {
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {
                    "name": "score_text",
                    "arguments": {"text": "plain", "detail": "weird"},
                },
            },
            {
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {
                    "name": "validate_rewrite",
                    "arguments": {"original": "plain"},
                },
            },
        ]
        rc, responses, stderr = call_server(requests)
        self.assertEqual(rc, 0, stderr)
        for response in responses:
            self.assertEqual(response["error"]["code"], -32602)

    def test_malformed_json_returns_json_rpc_parse_error(self):
        result = subprocess.run(
            [sys.executable, SERVER],
            input="not-json\n",
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["error"]["code"], -32700)

    def test_plugin_manifest_registers_the_server(self):
        with open(os.path.join(ROOT, ".mcp.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        server = manifest["mcpServers"]["antislop"]
        self.assertEqual(server["command"], "python3")
        self.assertIn("mcp_server.py", server["args"][0])
        self.assertEqual(server["version"], "2025-06-18")

        with open(
            os.path.join(ROOT, ".codex-plugin", "plugin.json"),
            encoding="utf-8",
        ) as f:
            plugin = json.load(f)
        self.assertEqual(plugin["name"], "antislop")
        self.assertEqual(plugin["skills"], "./skills/")
        self.assertNotIn("mcpServers", plugin)


if __name__ == "__main__":
    unittest.main()
