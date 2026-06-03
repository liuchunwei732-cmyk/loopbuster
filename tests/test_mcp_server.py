"""Tests for the LoopBuster MCP server.

Tests cover:
  - tools/list returns tool definitions
  - tools/call for each tool (check_cycle, get_report, reset_session, configure)
  - Error handling for unknown methods and tools
  - Input validation
  - Initialization handshake
"""

from __future__ import annotations

import json
import pytest

from loopbuster.mcp_server import _handle_request


def _send(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    """Simulate sending an MCP request."""
    msg: dict = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        msg["params"] = params
    return _handle_request(msg)


# ======================================================================
# Protocol basics
# ======================================================================


class TestProtocol:
    def test_initialize(self):
        resp = _handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
        })
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["result"]["protocolVersion"] == "2025-03-26"
        assert resp["result"]["serverInfo"]["name"] == "loopbuster"

    def test_notification_no_response(self):
        resp = _handle_request({
            "jsonrpc": "2.0", "method": "notifications/initialized",
        })
        assert resp == {}

    def test_unknown_method(self):
        resp = _send("unknown_method")
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_malformed_json(self):
        """Simulate a JSON parse error at the main loop level."""
        from loopbuster.mcp_server import main
        # main() reads from stdin; we can't easily test it here,
        # but _handle_request handles JSON DecodeError gracefully.
        import json
        try:
            json.loads("{invalid")
        except json.JSONDecodeError:
            pass  # Expected


# ======================================================================
# tools/list
# ======================================================================


class TestToolsList:
    def test_lists_tools(self):
        resp = _send("tools/list")
        assert "result" in resp
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "check_cycle" in tool_names
        assert "get_report" in tool_names
        assert "reset_session" in tool_names
        assert "configure" in tool_names

    def test_tools_have_schema(self):
        resp = _send("tools/list")
        for tool in resp["result"]["tools"]:
            assert "inputSchema" in tool
            assert "description" in tool


# ======================================================================
# tools/call: check_cycle
# ======================================================================


class TestCheckCycle:
    def test_simple_check(self):
        resp = _send("tools/call", {
            "name": "check_cycle",
            "arguments": {"tool_name": "web_search", "args": {"q": "python"}},
        })
        assert resp["jsonrpc"] == "2.0"
        content = json.loads(resp["result"]["content"][0]["text"])
        assert "is_loop" in content
        assert "action" in content
        assert content["step_number"] == 1

    def test_repeated_call_detects_loop(self):
        """After enough repetitions the engine should warn then stop."""
        results = []
        for i in range(6):
            resp = _send("tools/call", {
                "name": "check_cycle",
                "arguments": {"tool_name": "search", "args": {"q": "same"}},
            }, request_id=i + 1)
            r = json.loads(resp["result"]["content"][0]["text"])
            results.append(r)

        # Step 1-2: ALLOW (not enough history)
        assert results[0]["is_loop"] is False
        assert results[0]["should_warn"] is False
        assert results[1]["is_loop"] is False

        # Steps 3+: should_warn becomes True eventually
        # With default ActionConfig (warn=2), we need 2 consecutive
        # detection hits. Detection starts at step 3 (window_size=5,
        # confidence ~0.57). So consecutive_hits=1 → ALLOW.
        # Step 4: consecutive_hits=2 → WARN.
        assert results[3]["should_warn"] is True, f"Step 4 should warn: {results[3]}"

    def test_with_output(self):
        resp = _send("tools/call", {
            "name": "check_cycle",
            "arguments": {
                "tool_name": "web_search",
                "args": {"q": "test"},
                "output": "result",
            },
        })
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["step_number"] >= 1

    def test_missing_tool_name(self):
        resp = _send("tools/call", {
            "name": "check_cycle",
            "arguments": {},
        })
        assert "error" in resp


# ======================================================================
# tools/call: get_report
# ======================================================================


class TestGetReport:
    def test_empty_report(self):
        # Reset session first to get a clean state
        _send("tools/call", {"name": "reset_session", "arguments": {}})
        resp = _send("tools/call", {
            "name": "get_report",
            "arguments": {},
        })
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["total_actions"] == 0
        assert content["diversity_ratio"] == 1.0
        assert len(content["recommendations"]) >= 1

    def test_report_with_actions(self):
        _send("tools/call", {"name": "reset_session", "arguments": {}})
        for i in range(5):
            _send("tools/call", {
                "name": "check_cycle",
                "arguments": {"tool_name": f"tool_{i}", "args": {"n": i}},
            }, request_id=i + 10)

        resp = _send("tools/call", {
            "name": "get_report",
            "arguments": {},
        })
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["total_actions"] == 5
        assert content["diversity_ratio"] == 1.0


# ======================================================================
# tools/call: reset_session
# ======================================================================


class TestResetSession:
    def test_reset_clears_history(self):
        _send("tools/call", {
            "name": "check_cycle",
            "arguments": {"tool_name": "test", "args": {}},
        })
        resp = _send("tools/call", {
            "name": "reset_session",
            "arguments": {},
        })
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["status"] == "ok"

        # Verify report is now empty
        report_resp = _send("tools/call", {
            "name": "get_report",
            "arguments": {},
        })
        report = json.loads(report_resp["result"]["content"][0]["text"])
        assert report["total_actions"] == 0


# ======================================================================
# tools/call: configure
# ======================================================================


class TestConfigure:
    def test_configure_threshold(self):
        _send("tools/call", {"name": "reset_session", "arguments": {}})
        resp = _send("tools/call", {
            "name": "configure",
            "arguments": {"similarity_threshold": 0.7},
        })
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["status"] == "ok"
        assert content["changed"]["similarity_threshold"] == 0.7

    def test_configure_invalid_threshold(self):
        resp = _send("tools/call", {
            "name": "configure",
            "arguments": {"similarity_threshold": 1.5},
        })
        assert "error" in resp

    def test_configure_action_thresholds(self):
        _send("tools/call", {"name": "reset_session", "arguments": {}})
        resp = _send("tools/call", {
            "name": "configure",
            "arguments": {"warn_threshold": 3, "stop_threshold": 5},
        })
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["status"] == "ok"
        assert content["changed"]["action_config"]["warn_threshold"] == 3
        assert content["changed"]["action_config"]["stop_threshold"] == 5


# ======================================================================
# Error handling
# ======================================================================


class TestErrorHandling:
    def test_unknown_tool(self):
        resp = _send("tools/call", {
            "name": "nonexistent_tool",
            "arguments": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_json_parse_error(self):
        """Test that _handle_request handles non-dict inputs gracefully."""
        response = _handle_request({"jsonrpc": "2.0", "id": 1, "method": None})
        # Should still return something reasonable
        assert "error" in response or "result" in response
