"""LangChain integration for LoopBuster.

Provides a drop-in callback handler that wires LoopBuster into
LangChain's tool-execution flow without boilerplate.
"""

from __future__ import annotations

from typing import Any

from loopbuster import LoopBuster

# LangChain is optional; fail gracefully if not installed
try:
    from langchain.callbacks.base import BaseCallbackHandler
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "langchain is required for this integration. "
        "Install it with: pip install langchain"
    ) from _exc


class LoopBusterCallback(BaseCallbackHandler):
    """LangChain callback that runs LoopBuster on every tool call.

    Usage:
        from loopbuster.integrations.langchain import LoopBusterCallback

        lb = LoopBuster(budget_usd=5.0, max_repeats=3)
        callback = LoopBusterCallback(lb)

        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, callbacks=[callback]
        )
        result = agent_executor.run("Find the capital of France")
    """

    def __init__(self, loopbuster: LoopBuster) -> None:
        self.lb = loopbuster

    def on_tool_start(
        self,
        serialized: dict[str, Any] | None,
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Called before a tool is invoked."""
        tool_name = ""
        if serialized and "name" in serialized:
            tool_name = serialized["name"]
        elif kwargs.get("name"):
            tool_name = kwargs["name"]

        args = kwargs.get("tool_input") or input_str or {}
        decision = self.lb.check(tool=tool_name, args=args)
        if decision.should_stop:
            raise ToolLoopError(
                f"LoopBuster stopped tool '{tool_name}': {decision.reason}"
            )

    def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """Called after a tool returns.

        Feeds the output back for stagnation detection.
        """
        # LoopBuster already recorded the action in on_tool_start;
        # we can enrich the last record with output if desired.
        # For simplicity, we rely on the user passing output via check()
        # in the next iteration or call record_call directly.
        pass


class ToolLoopError(RuntimeError):
    """Raised when LoopBuster decides a tool call should not proceed."""


# Convenience helper

def wrap_agent_executor(agent_executor: Any, loopbuster: LoopBuster) -> Any:
    """Attach LoopBuster to an existing LangChain AgentExecutor.

    Returns the same executor with the callback registered.
    """
    if not hasattr(agent_executor, "callbacks"):
        agent_executor.callbacks = []
    agent_executor.callbacks.append(LoopBusterCallback(loopbuster))
    return agent_executor
