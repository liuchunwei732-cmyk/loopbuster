"""LlamaIndex integration for LoopBuster.

Provides a callback handler that plugs LoopBuster into LlamaIndex's
agent/tool execution pipeline.
"""

from __future__ import annotations

from typing import Any

from loopbuster import LoopBuster

try:
    from llama_index.core.callbacks.base_handler import BaseCallbackHandler
    from llama_index.core.callbacks.schema import CBEventType
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "llama-index is required for this integration. "
        "Install it with: pip install llama-index"
    ) from _exc


class LoopBusterCallback(BaseCallbackHandler):
    """LlamaIndex callback that runs LoopBuster on tool calls.

    Usage:
        from loopbuster.integrations.llamaindex import LoopBusterCallback

        lb = LoopBuster(budget_usd=5.0, max_repeats=3)
        callback = LoopBusterCallback(lb)

        # Attach to LlamaIndex settings or agent
        from llama_index.core import Settings
        Settings.callback_manager.add_handler(callback)
    """

    def __init__(self, loopbuster: LoopBuster) -> None:
        self.lb = loopbuster

    def start_trace(self, trace_id: str | None = None) -> None:
        pass

    def end_trace(
        self,
        trace_id: str | None = None,
        trace_map: dict[str, list[str]] | None = None,
    ) -> None:
        pass

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Intercept tool start events."""
        if event_type == CBEventType.FUNCTION_CALL and payload:
            tool_name = payload.get("name") or payload.get("tool_name") or ""
            tool_args = payload.get("arguments") or payload.get("tool_args") or {}
            decision = self.lb.check(tool=str(tool_name), args=tool_args)
            if decision.should_stop:
                raise ToolLoopError(
                    f"LoopBuster stopped tool '{tool_name}': {decision.reason}"
                )
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        pass


class ToolLoopError(RuntimeError):
    """Raised when LoopBuster decides a tool call should not proceed."""
