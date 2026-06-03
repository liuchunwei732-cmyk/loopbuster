"""LoopBuster — the core engine that ties detection strategies, guards, and circuit breaker together.

This is the main entry point for most users.
"""

from __future__ import annotations

import contextvars
import logging
from collections import deque
from typing import Any, Callable

from loopbuster.circuit import BreakerAction, BreakerDecision, CircuitBreaker
from loopbuster.guards import BudgetCeiling, Guard, RepeatCallGuard, StateStasis
from loopbuster.strategies import CompositeStrategy
from loopbuster.types import (
    Action,
    ActionConfig,
    ActionRecord,
    AdaptiveActionConfig,
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
      - Adaptive thresholds (diversity-aware tightening/relaxing)
      - Stuck report (action history, token waste estimate, recommendations)

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

        # Option 3: With adaptive thresholds
        from loopbuster.types import AdaptiveActionConfig

        with LoopBuster(action_config=AdaptiveActionConfig()) as lb:
            for step in agent_loop():
                decision = lb.check(tool=step.tool, args=step.args)
                if decision.should_stop:
                    break

        # Option 4: Generate stuck report
        with LoopBuster() as lb:
            for step in agent_loop():
                ...
            report = lb.report()  # dict with diagnostics
    """

    def __init__(
        self,
        # Strategy config
        window_size: int = 10,
        similarity_threshold: float = 0.85,
        action_config: ActionConfig | AdaptiveActionConfig | None = None,
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
        # --- Detection strategies (pass threshold through to strategies) ---
        self._strategies = CompositeStrategy()
        self._strategies.fuzzy.similarity_threshold = similarity_threshold
        self._strategies.stagnation.similarity_threshold = similarity_threshold
        # --- Action config (supports AdaptiveActionConfig) ---
        self._action_config = action_config or ActionConfig()
        self._is_adaptive = isinstance(self._action_config, AdaptiveActionConfig)
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
        self._action_history: deque[ActionRecord] = deque(maxlen=100)

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

        If AdaptiveActionConfig is active, diversity ratio is tracked
        automatically and thresholds adjust in real time.
        """
        self._step += 1

        # Record for action history (used by report())
        record = ActionRecord(tool=tool, args=args, output=output, step=self._step)
        self._action_history.append(record)

        # Track diversity for adaptive config
        if self._is_adaptive:
            self._action_config.record_action(tool)  # type: ignore[union-attr]

        # Circuit breaker records
        if self._circuit_breaker:
            self._circuit_breaker.record(tool, args)

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
    # Stuck Report
    # ------------------------------------------------------------------

    def report(self) -> dict[str, Any]:
        """Generate a diagnostic report of the agent's execution.

        Includes:
          - Action history summary
          - Diversity ratio
          - Top repeated patterns
          - Token waste estimate
          - Recommendations

        Inspired by agent-guard-mcp's getStuckReport(). Pure Python, no DB.
        """
        history = list(self._action_history)
        total = len(history)

        # Signature frequency
        sig_counts: dict[str, int] = {}
        for r in history:
            sig = f"{r.tool}:{_sig_of(r.args)}"
            sig_counts[sig] = sig_counts.get(sig, 0) + 1

        unique = len(sig_counts)
        diversity = unique / max(total, 1)
        redundant = total - unique

        # Token waste estimate (~500 tokens per redundant action)
        estimated_waste_tokens = redundant * 500
        estimated_waste_usd = estimated_waste_tokens * 0.000003  # ~$3/1M tokens

        # Top repeated patterns
        top_patterns = sorted(
            [(sig, cnt) for sig, cnt in sig_counts.items() if cnt >= 2],
            key=lambda x: -x[1],
        )[:10]

        # Recommendations
        recommendations = []
        if total == 0:
            recommendations.append("No actions recorded yet.")
            if self._tripped:
                recommendations.append(f"IMMEDIATE: Guard tripped: {self._tripped}")
            return {
                "total_actions": 0,
                "unique_signatures": 0,
                "diversity_ratio": 1.0,
                "redundant_actions": 0,
                "estimated_token_waste": 0,
                "estimated_cost_waste_usd": 0.0,
                "consecutive_hits": 0,
                "tripped": str(self._tripped) if self._tripped else None,
                "spent_usd": round(self.spent_usd, 4),
                "top_repeated_patterns": [],
                "recommendations": recommendations,
                "recent_timeline": [],
            }
        if self._tripped:
            recommendations.append(f"IMMEDIATE: Guard tripped: {self._tripped}")
        if diversity < 0.3:
            recommendations.append(
                f"LOW DIVERSITY (ratio={diversity:.2f}): Agent is cycling "
                f"through a small set of actions. Needs a different approach."
            )
        if redundant > 10:
            recommendations.append(
                f"TOKEN WASTE: ~{estimated_waste_tokens:,} tokens "
                f"(~${estimated_waste_usd:.4f}) on {redundant} redundant actions."
            )
        if self._is_adaptive:
            recommendations.append(
                f"Adaptive config active. Current thresholds: "
                f"WARN≥{self._action_config.warn_threshold}, "
                f"STOP≥{self._action_config.stop_threshold}, "
                f"ESC≥{self._action_config.escalate_threshold} "
                f"(diversity={self._action_config.diversity_ratio:.2f})"
            )
        if not recommendations:
            recommendations.append("Agent appears healthy. No intervention needed.")

        # Recent timeline (last 10)
        recent = [
            {"step": r.step, "tool": r.tool, "args": r.args}
            for r in history[-10:]
        ]

        return {
            "total_actions": total,
            "unique_signatures": unique,
            "diversity_ratio": round(diversity, 3),
            "redundant_actions": redundant,
            "estimated_token_waste": estimated_waste_tokens,
            "estimated_cost_waste_usd": round(estimated_waste_usd, 6),
            "consecutive_hits": self._consecutive_hits,
            "tripped": str(self._tripped) if self._tripped else None,
            "spent_usd": round(self.spent_usd, 4),
            "top_repeated_patterns": top_patterns,
            "recommendations": recommendations,
            "recent_timeline": recent,
        }

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
        self._action_history.clear()

    def start_dashboard(self, port: int = 8080):
        """Start the LoopBuster dashboard on the specified port."""
        import uvicorn
        from src.loopbuster.api.server import app
        logger.info(f"Starting LoopBuster dashboard on port {port}...")
        uvicorn.run(app, host="0.0.0.0", port=port)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def step_count(self) -> int:
        return self._step

    @property
    def consecutive_hits(self) -> int:
        return self._consecutive_hits

    @property
    def action_history(self) -> list[ActionRecord]:
        return list(self._action_history)


def _sig_of(args: dict | str | None) -> str:
    """Stable hash of args for signature generation."""
    import hashlib, json

    if args is None:
        return ""
    try:
        return hashlib.sha256(
            json.dumps(args, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]
    except (TypeError, ValueError):
        return repr(args)[:8]
