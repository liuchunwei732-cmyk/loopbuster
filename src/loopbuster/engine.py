"""LoopBuster — the core engine that ties detection strategies, guards, and circuit breaker together.

This is the main entry point for most users.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any, Callable

from loopbuster.circuit import BreakerAction, BreakerDecision, CircuitBreaker
from loopbuster.guards import BudgetCeiling, Guard, RepeatCallGuard, StateStasis
from loopbuster.strategies import CompositeStrategy
from loopbuster.types import (
    Action,
    ActionConfig,
    ActionRecord,
    Decision,
    TokenUsage,
    ToolCall,
    TripError,
    TripReason,
)

logger = logging.getLogger("loopbuster")

_current: contextvars.ContextVar["LoopBuster | None"] = contextvars.ContextVar(
    "loopbuster_current", default=None
)


def current() -> LoopBuster | None:
    """Return the active LoopBuster session in this context, or None."""
    return _current.get()


class LoopBuster:
    """Unified agent anti-loop engine.

    Combines:
      - Pattern-based loop detection (4 strategies)
      - Guard-based boundaries (budget, repeat limit, state stasis)
      - Circuit breaker (exact-match pre-flight gate)

    Usage:
        # Option 1: Context manager (recommended)
        with LoopBuster(budget_usd=5.0, warn_threshold=2) as lb:
            for step in agent_loop():
                decision = lb.check(tool=step.tool, args=step.args, output=step.output)
                if decision.should_stop:
                    break

        # Option 2: Direct detection only
        guard = LoopBuster()
        for action in actions:
            d = guard.check(action.tool, action.args, action.output)
            if d.is_loop:
                handle_loop(d)
    """

    def __init__(
        self,
        # Strategy config
        window_size: int = 10,
        similarity_threshold: float = 0.85,
        action_config: ActionConfig | None = None,
        # Guard config
        budget_usd: float | None = None,
        max_repeats: int | None = None,
        stasis_steps: int | None = None,
        state_projector: Callable[[Any], Any] | None = None,
        pricing: dict | None = None,
        repeat_window: int = 32,
        # Circuit breaker config
        circuit_breaker: CircuitBreaker | None = None,
        # Custom guards
        guards: list[Guard] | None = None,
        # Callbacks
        on_trip: Callable[[TripReason], None] | None = None,
        on_warn: Callable[[Decision], None] | None = None,
        on_stop: Callable[[Decision], None] | None = None,
        # Auto-halt on ESCALATE
        auto_halt: bool = False,
    ):
        # --- Detection strategies ---
        self._strategies = CompositeStrategy()
        # --- Action config ---
        self._action_config = action_config or ActionConfig()
        self._window_size = window_size
        self._similarity_threshold = similarity_threshold

        # --- Guards ---
        self._guards: list[Guard] = list(guards or [])
        if budget_usd is not None:
            self._guards.append(BudgetCeiling(limit_usd=budget_usd, pricing=pricing))
        if max_repeats is not None:
            self._guards.append(RepeatCallGuard(max_repeats=max_repeats, window=repeat_window))
        if stasis_steps is not None:
            self._guards.append(StateStasis(max_steps=stasis_steps, state_projector=state_projector))

        # --- Circuit breaker ---
        self._circuit_breaker = circuit_breaker

        # --- State ---
        self._step: int = 0
        self._consecutive_hits: int = 0
        self._tripped: TripReason | None = None
        self._auto_halt = auto_halt

        # --- Callbacks ---
        self._on_trip = on_trip
        self._on_warn = on_warn
        self._on_stop = on_stop

        # --- Context var ---
        self._ctx_token: contextvars.Token | None = None

    # ------------------------------------------------------------------
    # Context manager support (like magicrails)
    # ------------------------------------------------------------------

    def __enter__(self) -> "LoopBuster":
        self._ctx_token = _current.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._ctx_token is not None:
            _current.reset(self._ctx_token)
            self._ctx_token = None
        # Don't suppress exceptions
        return False

    @property
    def tripped(self) -> TripReason | None:
        return self._tripped

    @property
    def spent_usd(self) -> float:
        for g in self._guards:
            if isinstance(g, BudgetCeiling):
                return g.spent_usd
        return 0.0

    # ------------------------------------------------------------------
    # Main check method — pattern-based detection
    # ------------------------------------------------------------------

    def check(
        self,
        tool: str,
        args: dict[str, Any] | str | None = None,
        output: str | None = None,
    ) -> Decision:
        """Check an agent action for loop patterns.

        Runs all detection strategies and returns a decision with
        the highest-confidence pattern found.
        """
        self._step += 1

        # Also record in circuit breaker if active
        if self._circuit_breaker:
            self._circuit_breaker.record(tool, args)

        record = ActionRecord(tool=tool, args=args, output=output, step=self._step)

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

        # Fire callbacks
        if decision.is_loop and self._on_stop:
            self._on_stop(decision)
        elif decision.should_warn and self._on_warn:
            self._on_warn(decision)

        return decision

    # ------------------------------------------------------------------
    # Guard-based recording
    # ------------------------------------------------------------------

    def record_call(self, name: str, args: dict[str, Any] | None = None) -> None:
        """Record a tool call for guard monitoring."""
        event = ToolCall(name=name, args=args or {})
        for g in self._guards:
            reason = g.observe_call(event)
            if reason is not None:
                self._trip(reason)

    def record_tokens(self, model: str, input: int, output: int) -> None:
        """Record token usage for budget tracking."""
        event = TokenUsage(model=model, input_tokens=input, output_tokens=output)
        for g in self._guards:
            reason = g.observe_tokens(event)
            if reason is not None:
                self._trip(reason)

    def record_state(self, state: Any) -> None:
        """Record agent state for stasis detection."""
        for g in self._guards:
            reason = g.observe_state(state)
            if reason is not None:
                self._trip(reason)

    # ------------------------------------------------------------------
    # Circuit breaker pre-flight check
    # ------------------------------------------------------------------

    def breaker_check(
        self, tool: str, args: dict[str, Any] | str | None = None
    ) -> BreakerDecision:
        """Pre-flight check via circuit breaker.

        Call this BEFORE a tool call to see if it would be blocked.
        """
        if self._circuit_breaker is None:
            return BreakerDecision(
                proceed=True, reason="No circuit breaker configured", times_repeated=0
            )
        return self._circuit_breaker.check(tool, args)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _trip(self, reason: TripReason) -> None:
        if self._tripped is not None:
            return
        self._tripped = reason
        if self._on_trip:
            self._on_trip(reason)
        if self._auto_halt:
            raise TripError(reason)

    def reset(self) -> None:
        """Reset all internal state for reuse."""
        self._step = 0
        self._consecutive_hits = 0
        self._tripped = None
        self._strategies.reset()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def step_count(self) -> int:
        return self._step

    @property
    def consecutive_hits(self) -> int:
        return self._consecutive_hits
