"""Circuit breaker for preventing repetitive tool calls.

Inspired by agent-guard-mcp's design but implemented as a pure Python
component without external dependencies.

The circuit breaker provides pre-flight checks: before calling a tool,
an agent can check whether that call would trigger the breaker.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class BreakerAction(Enum):
    """What the circuit breaker does when triggered."""

    WARN = auto()
    BLOCK = auto()
    SUGGEST_ALTERNATIVE = auto()


@dataclass
class BreakerDecision:
    """Result of a circuit breaker check."""

    proceed: bool
    reason: str
    times_repeated: int = 0
    alternative_suggestion: str | None = None

    @property
    def blocked(self) -> bool:
        return not self.proceed


def _signature(tool: str, args: dict[str, Any] | str | None) -> str:
    """Create a stable signature for a (tool, args) pair."""
    if isinstance(args, str):
        raw = args
    elif args:
        raw = json.dumps(args, sort_keys=True, default=str)
    else:
        raw = ""
    h = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"{tool}:{h}"


@dataclass
class CircuitBreaker:
    """Circuit breaker that tracks action repetition and enforces limits.

    Unlike the detection strategies (which use fuzzy matching), the circuit
    breaker is a *hard* gate: it uses exact (tool, args) signatures and
    either warns, blocks, or suggests alternatives.

    Usage:
        breaker = CircuitBreaker(max_repeats=3, action=BreakerAction.WARN)
        decision = breaker.check("web_search", {"query": "python"})
        if not decision.proceed:
            # try something else
            ...
    """

    max_repeats: int = 3
    action: BreakerAction = BreakerAction.WARN
    _counts: dict[str, int] = field(default_factory=lambda: defaultdict(int), init=False, repr=False)

    def check(
        self, tool: str, args: dict[str, Any] | str | None = None
    ) -> BreakerDecision:
        """Pre-flight check: should this action be allowed?"""
        sig = _signature(tool, args)
        count = self._counts.get(sig, 0)

        # Always count the proposed action
        next_count = count + 1

        if next_count < self.max_repeats:
            return BreakerDecision(
                proceed=True,
                reason=f"Action seen {count}/{self.max_repeats} times — within limit",
                times_repeated=count,
            )

        times = count + 1  # include the proposed call

        if self.action == BreakerAction.BLOCK:
            return BreakerDecision(
                proceed=False,
                reason=(
                    f"BLOCKED: '{tool}' called {times} times "
                    f"with identical args (limit: {self.max_repeats})"
                ),
                times_repeated=times,
                alternative_suggestion=(
                    f"Do NOT call {tool} again with these arguments. "
                    f"Try different parameters, a different tool, or report a blocker."
                ),
            )

        if self.action == BreakerAction.SUGGEST_ALTERNATIVE:
            return BreakerDecision(
                proceed=True,
                reason=(
                    f"SUGGEST_ALTERNATIVE: '{tool}' repeated {times} times "
                    f"— an alternative approach is recommended"
                ),
                times_repeated=times,
                alternative_suggestion=(
                    f"Consider: (1) changing input arguments, "
                    f"(2) using a different tool, "
                    f"(3) asking the user for clarification."
                ),
            )

        # WARN (default)
        return BreakerDecision(
            proceed=True,
            reason=(
                f"WARNING: '{tool}' called {times} times "
                f"with same arguments — possible infinite loop"
            ),
            times_repeated=times,
            alternative_suggestion=(
                f"This action is becoming repetitive. "
                f"Consider whether you are making progress or stuck in a loop."
            ),
        )

    def record(self, tool: str, args: dict[str, Any] | str | None = None) -> None:
        """Record a tool call (for use when not doing a pre-flight check)."""
        sig = _signature(tool, args)
        self._counts[sig] += 1

    def reset(self) -> None:
        """Clear all recorded counts."""
        self._counts.clear()
