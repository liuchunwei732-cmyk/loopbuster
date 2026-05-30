"""@buster decorator — wrap any agent-running function with LoopBuster protection.

Inspired by magicrails' `@guard` decorator.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from loopbuster.engine import LoopBuster
from loopbuster.types import TripReason


def buster(
    budget_usd: float | None = None,
    max_repeats: int | None = None,
    stasis_steps: int | None = None,
    state_projector: Callable[[Any], Any] | None = None,
    on_trip: Callable[[TripReason], None] | None = None,
    pricing: dict | None = None,
    repeat_window: int = 32,
    window_size: int = 10,
    similarity_threshold: float = 0.85,
    auto_halt: bool = True,
) -> Callable:
    """Decorator that wraps a function with LoopBuster protection.

    The decorated function runs inside a LoopBuster context manager.
    If any guard trips and auto_halt is True (default), a TripError is
    raised automatically.

    Usage:
        @buster(budget_usd=5.0, max_repeats=3)
        def run_my_agent(task: str):
            for step in agent_loop(task):
                current().check(tool=step.tool, args=step.args)
                current().record_tokens(...)
                current().record_call(name=step.tool, args=step.args)
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with LoopBuster(
                budget_usd=budget_usd,
                max_repeats=max_repeats,
                stasis_steps=stasis_steps,
                state_projector=state_projector,
                on_trip=on_trip,
                pricing=pricing,
                repeat_window=repeat_window,
                window_size=window_size,
                similarity_threshold=similarity_threshold,
                auto_halt=auto_halt,
            ):
                return fn(*args, **kwargs)

        return wrapper

    return decorator
