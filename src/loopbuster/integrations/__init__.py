"""Generic callback integration for any agent framework.

Provides a callback class that can be plugged into any agent loop.
"""

from __future__ import annotations

from typing import Any

from loopbuster.types import Decision


class LoopBusterCallback:
    """Generic callback that integrates LoopBuster with any agent framework.

    Usage:
        callback = LoopBusterCallback(
            on_warn=lambda d: print(f"Warning: {d.reason}"),
            on_stop=lambda d: raise StopException(d),
        )

        for action in agent_loop:
            decision = callback.before_tool_call(action.tool, action.args)
            if not decision.should_stop:
                result = execute_tool(action.tool, action.args)
                callback.after_tool_call(output=result)
            else:
                break
    """

    def __init__(
        self,
        window_size: int = 10,
        similarity_threshold: float = 0.85,
        on_warn: Any = None,
        on_stop: Any = None,
        on_escalate: Any = None,
    ):
        from loopbuster.strategies import CompositeStrategy
        from loopbuster.types import ActionConfig

        self._strategies = CompositeStrategy()
        self._action_config = ActionConfig()
        self._step = 0
        self._consecutive_hits = 0
        self._on_warn = on_warn
        self._on_stop = on_stop
        self._on_escalate = on_escalate

    def before_tool_call(
        self, tool: str, args: dict[str, Any] | str | None = None
    ) -> Decision:
        """Check a tool call before executing it. Returns the decision."""
        self._step += 1
        record = type("Record", (), {"tool": tool, "args": args, "output": None, "step": self._step})()

        confidence, reason, strategy_name = self._strategies.check(record)

        if confidence > 0.3:
            self._consecutive_hits += 1
        else:
            self._consecutive_hits = 0

        action = self._action_config.resolve_action(self._consecutive_hits)
        decision = Decision(
            action=action,
            reason=reason,
            strategy=strategy_name,
            confidence=confidence,
            step_number=self._step,
        )

        if decision.action.name == "ESCALATE" and self._on_escalate:
            self._on_escalate(decision)
        elif decision.is_loop and self._on_stop:
            self._on_stop(decision)
        elif decision.should_warn and self._on_warn:
            self._on_warn(decision)

        return decision

    def after_tool_call(
        self, tool: str, args: dict | str | None = None, output: str | None = None
    ) -> Decision:
        """Check a tool call after execution (includes output for stagnation)."""
        self._step += 1
        record = type("Record", (), {"tool": tool, "args": args, "output": output, "step": self._step})()

        confidence, reason, strategy_name = self._strategies.check(record)

        if confidence > 0.3:
            self._consecutive_hits += 1
        else:
            self._consecutive_hits = 0

        action = self._action_config.resolve_action(self._consecutive_hits)
        decision = Decision(
            action=action,
            reason=reason,
            strategy=strategy_name,
            confidence=confidence,
            step_number=self._step,
        )

        if decision.action.name == "ESCALATE" and self._on_escalate:
            self._on_escalate(decision)
        elif decision.is_loop and self._on_stop:
            self._on_stop(decision)
        elif decision.should_warn and self._on_warn:
            self._on_warn(decision)

        return decision

    def reset(self) -> None:
        self._step = 0
        self._consecutive_hits = 0
        self._strategies.reset()
