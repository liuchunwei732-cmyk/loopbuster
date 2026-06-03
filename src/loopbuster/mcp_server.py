"""MCP server for LoopBuster.

Provides a stdio-based MCP server that exposes loop detection as
callable tools for MCP-compatible LLM hosts (e.g., Claude Desktop,
Claude Code, Cursor, etc.).

Usage:
    pip install loopbuster
    python -m loopbuster.mcp_server

Tools:
    check_cycle     — Detect if an agent action is looping
    get_report      — Generate diagnostic report from current session
    reset_session   — Clear all detection history
    configure       — Update detection parameters at runtime

Protocol:
    stdio transport, JSON-RPC 2.0 message format.
    One JSON object per line for both requests and responses.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any

from loopbuster import LoopBuster

# ── Global session state ─────────────────────────────────────────────

_buster: LoopBuster | None = None

# Registered tool definitions
_TOOLS = [
    {
        "name": "check_cycle",
        "description": "Check an agent tool call for loop patterns. Returns whether the action appears to be stuck in a loop, along with confidence and reason.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool being called (e.g., 'web_search', 'read_file')",
                },
                "args": {
                    "type": "object",
                    "description": "Arguments passed to the tool as a JSON object (optional)",
                },
                "output": {
                    "type": "string",
                    "description": "Output/result from the tool call (optional, used by OutputStagnation strategy)",
                },
            },
            "required": ["tool_name"],
        },
    },
    {
        "name": "get_report",
        "description": "Generate a stuck report for the current session. Returns action history summary, diversity ratio, top repeated patterns, token waste estimate, and recommendations.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "reset_session",
        "description": "Reset all detection history and counters for a fresh session. Preserves configured parameters.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "configure",
        "description": "Update LoopBuster configuration at runtime. Only parameters explicitly provided are changed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "similarity_threshold": {
                    "type": "number",
                    "description": "Similarity threshold for fuzzy matching (0.0-1.0, default: 0.85)",
                },
                "warn_threshold": {
                    "type": "integer",
                    "description": "Consecutive hits before WARN action (default: 2)",
                },
                "stop_threshold": {
                    "type": "integer",
                    "description": "Consecutive hits before STOP action (default: 4)",
                },
                "escalate_threshold": {
                    "type": "integer",
                    "description": "Consecutive hits before ESCALATE action (default: 6)",
                },
            },
            "required": [],
        },
    },
]


# ── Tool handlers ────────────────────────────────────────────────────


def _ensure_buster() -> LoopBuster:
    """Get or create the global LoopBuster instance."""
    global _buster
    if _buster is None:
        _buster = LoopBuster(similarity_threshold=0.85)
    return _buster


def _handle_check_cycle(arguments: dict[str, Any]) -> dict[str, Any]:
    buster = _ensure_buster()
    tool_name = arguments.get("tool_name", "")
    args = arguments.get("args")
    output = arguments.get("output")

    if not tool_name:
        return {"error": "tool_name is required"}

    decision = buster.check(tool=tool_name, args=args, output=output)

    return {
        "is_loop": decision.is_loop,
        "should_stop": decision.should_stop,
        "should_warn": decision.should_warn,
        "action": decision.action.name,
        "reason": decision.reason,
        "confidence": decision.confidence,
        "strategy": decision.strategy,
        "step_number": decision.step_number,
    }


def _handle_get_report(arguments: dict[str, Any]) -> dict[str, Any]:
    buster = _ensure_buster()
    report = buster.report()

    return {
        "total_actions": report.get("total_actions", 0),
        "diversity_ratio": report.get("diversity_ratio", 1.0),
        "redundant_actions": report.get("redundant_actions", 0),
        "top_repeated_patterns": report.get("top_repeated_patterns", []),
        "token_waste_estimate": report.get("token_waste_estimate", "$0.00"),
        "recommendations": report.get("recommendations", []),
        "tripped": report.get("tripped"),
    }


def _handle_reset_session(arguments: dict[str, Any]) -> dict[str, Any]:
    global _buster
    _buster = LoopBuster(similarity_threshold=0.85)
    return {"status": "ok", "message": "Session reset. All detection history cleared."}


def _handle_configure(arguments: dict[str, Any]) -> dict[str, Any]:
    buster = _ensure_buster()
    try:
        changed = buster.configure(
            similarity_threshold=arguments.get("similarity_threshold"),
            warn_threshold=arguments.get("warn_threshold"),
            stop_threshold=arguments.get("stop_threshold"),
            escalate_threshold=arguments.get("escalate_threshold"),
        )
        return {"status": "ok", "changed": changed}
    except (ValueError, TypeError) as e:
        return {"error": str(e)}


# ── Tool dispatch ────────────────────────────────────────────────────

_HANDLERS = {
    "check_cycle": _handle_check_cycle,
    "get_report": _handle_get_report,
    "reset_session": _handle_reset_session,
    "configure": _handle_configure,
}


def _handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Process a single MCP request and return the response."""
    method = request.get("method", "")
    request_id = request.get("id")

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": _TOOLS},
        }

    elif method == "tools/call":
        params = request.get("params", {})
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        handler = _HANDLERS.get(name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            }

        try:
            result = handler(arguments)
            if "error" in result:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": result["error"]},
                }
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, default=str),
                        }
                    ]
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": str(e),
                    "data": traceback.format_exc(),
                },
            }

    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "serverInfo": {
                    "name": "loopbuster",
                    "version": "0.3.0",
                },
                "capabilities": {
                    "tools": {},
                },
            },
        }

    elif method == "notifications/initialized":
        return {}  # No response body for notifications

    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }


# ── Main loop ────────────────────────────────────────────────────────

def main() -> None:
    """Run the MCP server over stdio."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = _handle_request(request)
            if response:  # Skip empty responses (notifications)
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except json.JSONDecodeError as e:
            print(
                json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                }),
                flush=True,
            )
        except Exception as e:
            print(
                json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(e)},
                }),
                flush=True,
            )


if __name__ == "__main__":
    main()
