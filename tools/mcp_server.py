#!/usr/bin/env python3
"""Dependency-free, read-only MCP server for Antislop analysis tools."""

import json
import os
import sys

from preserve import validate_rewrite
from profiles import prepare_rewrite
from registry import load_registry
from score import score_text, validate_score_options


PROTOCOL_VERSION = "2025-06-18"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_INPUT_CHARACTERS = 250000


TOOLS = [
    {
        "name": "score_text",
        "title": "Score text against Antislop",
        "description": (
            "Return deterministic writing findings and disclose rules that still "
            "require manual review. This is not an authorship detector."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "profile": {"type": "string", "default": "general"},
                "voice": {"type": "string", "default": "professional"},
                "context": {"type": "string", "default": "docs"},
                "mechanics": {"type": "string", "default": "house"},
                "detail": {"type": "string", "enum": ["compact", "full"], "default": "compact"},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "validate_rewrite",
        "title": "Validate rewrite preservation",
        "description": (
            "Compare an original Markdown document with a rewrite and reject "
            "changes to protected source material."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "original": {"type": "string"},
                "rewrite": {"type": "string"},
            },
            "required": ["original", "rewrite"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "prepare_rewrite",
        "title": "Prepare a bounded rewrite contract",
        "description": (
            "Resolve voice, publication context, and mechanics into instructions "
            "for a rewrite-capable model without changing the source."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "voice": {"type": "string", "default": "professional"},
                "context": {"type": "string", "default": "docs"},
                "mechanics": {"type": "string", "default": "house"},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "review_rewrite",
        "title": "Review a candidate rewrite",
        "description": (
            "Block literal preservation failures and score a candidate rewrite "
            "before it is accepted by a caller."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "original": {"type": "string"},
                "rewrite": {"type": "string"},
                "profile": {"type": "string", "default": "general"},
                "voice": {"type": "string", "default": "professional"},
                "context": {"type": "string", "default": "docs"},
                "mechanics": {"type": "string", "default": "house"},
            },
            "required": ["original", "rewrite"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
]


def tool_result(value):
    return {
        "content": [{"type": "text", "text": json.dumps(value, separators=(",", ":"))}],
        "structuredContent": value,
        "isError": False,
    }


def compact_score(result):
    compact = dict(result)
    compact["findings"] = result["findings"][:20]
    compact["metadata"] = dict(result["metadata"])
    compact["metadata"]["findings_truncated"] = max(0, len(result["findings"]) - 20)
    return compact


def validate_tool_arguments(name, arguments):
    """Enforce the input contract advertised by tools/list."""
    schemas = {tool["name"]: tool["inputSchema"] for tool in TOOLS}
    if name not in schemas:
        raise ValueError(f"Unknown tool: {name}")
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")

    schema = schemas[name]
    properties = schema["properties"]
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        raise ValueError(f"unknown argument(s): {', '.join(unknown)}")
    missing = [key for key in schema.get("required", []) if key not in arguments]
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(missing)}")
    for key, value in arguments.items():
        definition = properties[key]
        if definition.get("type") == "string" and not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        allowed = definition.get("enum")
        if allowed is not None and value not in allowed:
            raise ValueError(f"{key} must be one of: {', '.join(allowed)}")


def call_tool(name, arguments):
    validate_tool_arguments(name, arguments)
    for key, value in arguments.items():
        if isinstance(value, str) and len(value) > MAX_INPUT_CHARACTERS:
            raise ValueError(
                f"{key} exceeds the maximum of {MAX_INPUT_CHARACTERS} characters"
            )
    if name == "score_text":
        registry = load_registry(os.path.join(ROOT, "rules.json"))
        profile = arguments.get("profile", "general")
        voice = arguments.get("voice", "professional")
        context = arguments.get("context", "docs")
        mechanics = arguments.get("mechanics", "house")
        validate_score_options(registry, profile, voice, context, mechanics)
        result = score_text(
            arguments.get("text", ""),
            registry,
            profile=profile,
            voice=voice,
            context=context,
            mechanics=mechanics,
        )
        if arguments.get("detail", "compact") == "compact":
            result = compact_score(result)
        return tool_result(result)

    if name == "validate_rewrite":
        return tool_result(validate_rewrite(
            arguments.get("original", ""),
            arguments.get("rewrite", ""),
        ))

    if name == "prepare_rewrite":
        registry = load_registry(os.path.join(ROOT, "rules.json"))
        voice = arguments.get("voice", "professional")
        context = arguments.get("context", "docs")
        mechanics = arguments.get("mechanics", "house")
        validate_score_options(registry, "general", voice, context, mechanics)
        return tool_result(prepare_rewrite(
            arguments.get("text", ""),
            registry,
            voice=voice,
            context=context,
            mechanics=mechanics,
        ))

    if name == "review_rewrite":
        registry = load_registry(os.path.join(ROOT, "rules.json"))
        profile = arguments.get("profile", "general")
        voice = arguments.get("voice", "professional")
        context = arguments.get("context", "docs")
        mechanics = arguments.get("mechanics", "house")
        validate_score_options(registry, profile, voice, context, mechanics)
        preservation = validate_rewrite(
            arguments.get("original", ""),
            arguments.get("rewrite", ""),
        )
        audit = score_text(
            arguments.get("rewrite", ""),
            registry,
            profile=profile,
            voice=voice,
            context=context,
            mechanics=mechanics,
        )
        accepted = preservation["valid"]
        return tool_result({
            "status": (
                "accepted_for_semantic_review"
                if accepted
                else "blocked_by_preservation"
            ),
            "accepted": accepted,
            "semantic_review_required": True,
            "preservation": preservation,
            "audit": audit,
        })

def dispatch(request):
    method = request.get("method")
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "antislop", "version": "3.0.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        params = request.get("params", {})
        return call_tool(params.get("name"), params.get("arguments", {}))
    if method and method.startswith("notifications/"):
        return None
    raise ValueError(f"Unknown method: {method}")


def serve(stdin=sys.stdin, stdout=sys.stdout):
    for line in stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            request_id = request.get("id")
            result = dispatch(request)
            if request_id is None or result is None:
                continue
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        except (KeyError, TypeError, ValueError) as exc:
            if request_id is None:
                continue
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            }
        stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        stdout.flush()


if __name__ == "__main__":
    serve()
