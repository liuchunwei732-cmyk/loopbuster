"""AsyncLoopBuster — async-aware loop detection for coroutine-based agent loops.

Standard LoopBuster works with synchronous agent loops. AsyncLoopBuster
extends the same detection logic to async generators, async iterators,
and coroutine-based agent frameworks.

Key differences from LoopBuster:
  - Async context manager (async with)
  - async check() for awaitable action streams
  - Support for async generator-based agent loops
  - Automatic detection of unresolved awaitables / hung coroutines
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Callable

from loopbuster.circuit import CircuitBreaker
from loopbuster.engine import LoopBuster
from loopbuster.guards import Guard
from loopbuster.types import (
    Action,
    ActionConfig,
    Decision,
    TripReason,
)


class AsyncLoopBuster(LoopBuster):
    """Async-aware agent anti-loop engine.

    Same API as LoopBuster but with async context manager and support
    for detecting hung coroutines / unresolved awaitables.

    Usage:
        async with AsyncLoopBuster(budget_usd=5.0) as lb:
            async for action in agent_async_loop(task):
                decision = await lb.acheck(tool=action.tool, args=action.args)
                if decision.should_stop:
                    break

        # Or with timeout per action:
        async with AsyncLoopBuster(action_timeout=30.0) as lb:
            ...
    """

    def __init__(
        self,
        # Timeout per action (seconds). If an action takes longer than this,
        # it's treated as a hung coroutine → ESCALATE.
        action_timeout: float | None = None,
        # Max consecutive slow actions before tripping
        max_slow_actions: int = 3,
        # Standard LoopBuster params
        window_size: int = 10,
        similarity_threshold: float = 0.85,
        action_config: ActionConfig | None = None,
        budget_usd: float | None = None,
        max_repeats: int | None = None,
        stasis_steps: int | None = None,
        state_projector: Callable[[Any], Any] | None = None,
        pricing: dict | None = None,
        repeat_window: int = 32,
        circuit_breaker: CircuitBreaker | None = None,
        guards: list[Guard] | None = None,
        on_trip: Callable[[TripReason], None] | None = None,
        on_warn: Callable[[Decision], None] | None = None,
        on_stop: Callable[[Decision], None] | None = None,
        auto_halt: bool = False,
    ):
        super().__init__(
            window_size=window_size,
            similarity_threshold=similarity_threshold,
            action_config=action_config,
            budget_usd=budget_usd,
            max_repeats=max_repeats,
            stasis_steps=stasis_steps,
            state_projector=state_projector,
            pricing=pricing,
            repeat_window=repeat_window,
            circuit_breaker=circuit_breaker,
            guards=guards,
            on_trip=on_trip,
            on_warn=on_warn,
            on_stop=on_stop,
            auto_halt=auto_halt,
        )
        self._action_timeout = action_timeout
        self._max_slow_actions = max_slow_actions
        self._slow_count = 0
        self._last_action_time: float | None = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "AsyncLoopBuster":
        self.__enter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.__exit__(exc_type, exc_val, exc_tb)
        return False

    # ------------------------------------------------------------------
    # Async check
    # ------------------------------------------------------------------

    async def acheck(
        self,
        tool: str,
        args: dict[str, Any] | str | None = None,
        output: str | None = None,
    ) -> Decision:
        """Async version of check(). Detects hung coroutines via action timeout."""
        now = time.time()

        # Detect action timeout (hung coroutine detection)
        if self._last_action_time is not None and self._action_timeout is not None:
            elapsed = now - self._last_action_time
            if elapsed > self._action_timeout:
                self._slow_count += 1
                if self._slow_count >= self._max_slow_actions:
                    decision = Decision(
                        action=Action.ESCALATE,
                        reason=(
                            f"Hung coroutine detected: action '{tool}' took "
                            f"{elapsed:.1f}s (timeout: {self._action_timeout}s, "
                            f"consecutive slow: {self._slow_count})"
                        ),
                        strategy="hung_coroutine",
                        confidence=1.0,
                        step_number=self.step_count + 1,
                    )
                    if self._on_stop:
                        self._on_stop(decision)
                    return decision
            else:
                self._slow_count = 0

        self._last_action_time = now

        # Delegate to sync check for pattern detection
        return self.check(tool=tool, args=args, output=output)

    # ------------------------------------------------------------------
    # Async generator wrapper
    # ------------------------------------------------------------------

    @classmethod
    async def watch(
        cls,
        async_iter: AsyncIterator[tuple[str, dict | str | None]],
        **kwargs: Any,
    ) -> AsyncIterator[tuple[str, dict | str | None, Decision]]:
        """Wrap an async generator with loop detection.

        Yields (tool, args, decision) tuples, allowing the caller to
        inspect decisions and stop early if needed.

        Usage:
            async for tool, args, decision in AsyncLoopBuster.watch(
                my_agent_async_gen(task),
                budget_usd=5.0,
            ):
                if decision.should_stop:
                    print(f"🛑 {decision.reason}")
                    break
                # process action...
        """
        async with cls(**kwargs) as lb:
            async for tool, args in async_iter:
                decision = await lb.acheck(tool=tool, args=args)
                yield tool, args, decision
                if decision.should_stop:
                    break

    # ------------------------------------------------------------------
    # Override reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        super().reset()
        self._slow_count = 0
        self._last_action_time = None
