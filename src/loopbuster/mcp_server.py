"""MCP server for LoopBuster.

Usage:
    pip install loopbuster[mcp]
    python -m loopbuster.mcp_server
"""

from loopbuster import LoopBuster
import json
import sys

_buster = None

def check_cycle(tool_name: str, args: str = "{}") -> dict:
    global _buster
    if _buster is None:
        _buster = LoopBuster(similarity_threshold=0.85)
    try:
        args_dict = json.loads(args) if args else {}
    except json.JSONDecodeError:
        args_dict = {"raw": args}
    decision = _buster.check(tool=tool_name, args=args_dict)
    return {
        "is_loop": decision.is_loop,
        "reason": decision.reason,
        "confidence": decision.confidence,
    }

def _handle_request(request: dict) -> dict:
    method = request.get("method", "")
    if method == "tools/list":
        return {
            "tools": [{
                "name": "check_cycle",
                "description": "检测 Agent action 是否陷入循环",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string"},
                        "args": {"type": "string"}
                    },
                    "required": ["tool_name"]
                }
            }]
        }
    elif method == "tools/call":
        params = request.get("params", {})
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if name == "check_cycle":
            result = check_cycle(
                arguments.get("tool_name", ""),
                arguments.get("args", "{}")
            )
            return {"content": [{"type": "text", "text": json.dumps(result)}]}
        return {"error": f"Unknown tool: {name}"}
    return {"error": f"Unknown method: {method}"}

if __name__ == "__main__":
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = _handle_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
