"""Tests for LoopBuster core functionality."""

from __future__ import annotations

import pytest

from loopbuster import (
    Action,
    ActionConfig,
    BreakerAction,
    BudgetCeiling,
    CircuitBreaker,
    Decision,
    LoopBuster,
    TripError,
    buster,
)
from loopbuster.strategies import (
    CycleDetectionStrategy,
    ExactRepeatStrategy,
    FuzzyRepeatStrategy,
    OutputStagnationStrategy,
)
from loopbuster.types import ActionRecord, TokenUsage, ToolCall


# ======================================================================
# Strategy tests
# ======================================================================


class TestExactRepeatStrategy:
    def test_no_repeat(self):
        s = ExactRepeatStrategy()
        c, r = s.check(ActionRecord(tool="search", args={"q": "a"}, step=1))
        assert c == 0.0

        c, r = s.check(ActionRecord(tool="search", args={"q": "b"}, step=2))
        assert c == 0.0

    def test_exact_repeat_detected(self):
        s = ExactRepeatStrategy(window_size=3)
        s.check(ActionRecord(tool="search", args={"q": "x"}, step=1))
        s.check(ActionRecord(tool="search", args={"q": "x"}, step=2))
        c, r = s.check(ActionRecord(tool="search", args={"q": "x"}, step=3))
        assert c >= 0.5
        assert "Exact repeat" in r

    def test_reset(self):
        s = ExactRepeatStrategy(window_size=3)
        s.check(ActionRecord(tool="search", args={"q": "x"}, step=1))
        s.check(ActionRecord(tool="search", args={"q": "x"}, step=2))
        s.reset()
        c, r = s.check(ActionRecord(tool="search", args={"q": "x"}, step=3))
        # After reset, only 1 item in history -> no repeat
        assert c == 0.0


class TestFuzzyRepeatStrategy:
    def test_fuzzy_repeat_detected(self):
        s = FuzzyRepeatStrategy(window_size=3, similarity_threshold=0.5)
        s.check(ActionRecord(tool="search", args={"q": "how to fix python error"}, step=1))
        s.check(ActionRecord(tool="search", args={"q": "how to fix python bug"}, step=2))
        c, r = s.check(ActionRecord(tool="search", args={"q": "how to fix python issue"}, step=3))
        assert c > 0.0
        assert "Fuzzy repeat" in r

    def test_different_tools_no_fuzzy(self):
        s = FuzzyRepeatStrategy(window_size=3, similarity_threshold=0.5)
        s.check(ActionRecord(tool="search", args={"q": "hello"}, step=1))
        s.check(ActionRecord(tool="read", args={"path": "file.txt"}, step=2))
        s.check(ActionRecord(tool="write", args={"content": "data"}, step=3))
        # No repeats because all different tools
        c, r = s.check(ActionRecord(tool="search", args={"q": "hello"}, step=4))
        assert c == 0.0


class TestCycleDetectionStrategy:
    def test_no_cycle(self):
        s = CycleDetectionStrategy()
        for t in ["a", "b", "c", "d"]:
            c, r = s.check(ActionRecord(tool=t, step=1))
        assert c == 0.0

    def test_cycle_detected(self):
        s = CycleDetectionStrategy(max_cycle_length=3, min_repetitions=2)
        pattern = ["search", "parse", "search", "parse"]
        for t in pattern:
            c, r = s.check(ActionRecord(tool=t, step=1))
        assert c > 0.0
        assert "Cycle detected" in r


class TestOutputStagnationStrategy:
    def test_no_stagnation(self):
        s = OutputStagnationStrategy(window_size=3, similarity_threshold=0.99)
        s.check(ActionRecord(tool="search", output="completely different first result", step=1))
        s.check(ActionRecord(tool="search", output="unrelated second result", step=2))
        c, r = s.check(ActionRecord(tool="search", output="totally unrelated third result", step=3))
        assert c == 0.0

    def test_stagnation_detected(self):
        s = OutputStagnationStrategy(window_size=3, similarity_threshold=0.5)
        s.check(ActionRecord(tool="search", output="the same result", step=1))
        s.check(ActionRecord(tool="search", output="the same result", step=2))
        c, r = s.check(ActionRecord(tool="search", output="the same result", step=3))
        assert c > 0.0
        assert "Output stagnation" in r


# ======================================================================
# Engine tests
# ======================================================================


class TestLoopBuster:
    def test_init(self):
        lb = LoopBuster()
        assert lb.step_count == 0
        assert lb.consecutive_hits == 0

    def test_clean_actions_no_loop(self):
        lb = LoopBuster()
        for i in range(5):
            d = lb.check(tool=f"tool_{i}", args={"n": i})
            assert d.action == Action.ALLOW

    def test_exact_repeat_escalates(self):
        lb = LoopBuster(action_config=ActionConfig(warn_threshold=2, stop_threshold=3))
        for _ in range(5):
            d = lb.check(tool="search", args={"q": "same"})
        assert d.is_loop

    def test_context_manager(self):
        with LoopBuster() as lb:
            from loopbuster.engine import current

            assert current() is lb
            d = lb.check(tool="test")
            assert d.action == Action.ALLOW
        from loopbuster.engine import current

        assert current() is None

    def test_guard_trip(self):
        lb = LoopBuster(budget_usd=0.01, auto_halt=True)
        lb.record_tokens("gpt-4o-mini", input=1000, output=1000)
        # Budget of $0.01 is very small; even one call should survive but
        # the guard tracks cumulative spend. Let's test with deliberate excess.
        with pytest.raises(TripError) as excinfo:
            lb.record_tokens("gpt-4o", input=5000, output=2000)
        assert "BudgetCeiling" in str(excinfo.value)
        assert lb.tripped is not None

    def test_breaker_integration(self):
        breaker = CircuitBreaker(max_repeats=3, action=BreakerAction.BLOCK)
        lb = LoopBuster(circuit_breaker=breaker)

        # Pre-flight: first call should be allowed
        d = lb.breaker_check("search", {"q": "hello"})
        assert d.proceed is True

        # Record two more (breaker tracks via check() internally)
        for _ in range(2):
            lb.check("search", {"q": "hello"})

        # Now breaker should block
        d2 = lb.breaker_check("search", {"q": "hello"})
        assert d2.blocked is True


# ======================================================================
# Decorator tests
# ======================================================================


class TestBusterDecorator:
    def test_decorator_basic(self):
        @buster()
        def my_agent():
            from loopbuster.engine import current

            lb = current()
            assert lb is not None
            return "done"

        assert my_agent() == "done"

    def test_decorator_with_budget(self):
        @buster(budget_usd=100.0)
        def my_agent():
            from loopbuster.engine import current

            current().record_tokens("gpt-4o-mini", input=100, output=50)
            return "ok"

        assert my_agent() == "ok"


# ======================================================================
# Guard tests
# ======================================================================


class TestBudgetCeiling:
    def test_under_budget(self):
        g = BudgetCeiling(limit_usd=10.0)
        r = g.observe_tokens(TokenUsage("gpt-4o-mini", 100, 50))
        assert r is None
        assert g.spent_usd > 0

    def test_over_budget(self):
        g = BudgetCeiling(limit_usd=0.001)
        r = g.observe_tokens(TokenUsage("gpt-4o", 100000, 50000))
        assert r is not None
        assert "BudgetCeiling" in r.detector


# ======================================================================
# Circuit Breaker tests
# ======================================================================


class TestCircuitBreaker:
    def test_under_limit(self):
        cb = CircuitBreaker(max_repeats=3)
        d = cb.check("search", {"q": "hello"})
        assert d.proceed is True

    def test_over_limit_blocks(self):
        cb = CircuitBreaker(max_repeats=3, action=BreakerAction.BLOCK)
        for _ in range(3):
            cb.record("search", {"q": "hello"})
        d = cb.check("search", {"q": "hello"})
        assert d.blocked is True

    def test_warn_does_not_block(self):
        cb = CircuitBreaker(max_repeats=2, action=BreakerAction.WARN)
        for _ in range(3):
            cb.record("search", {"q": "hello"})
        d = cb.check("search", {"q": "hello"})
        assert d.proceed is True  # WARN doesn't block
        assert "WARNING" in d.reason

    def test_reset(self):
        cb = CircuitBreaker(max_repeats=3, action=BreakerAction.BLOCK)
        for _ in range(3):
            cb.record("search", {"q": "hello"})
        cb.reset()
        d = cb.check("search", {"q": "hello"})
        assert d.proceed is True


# ======================================================================
# Decision / ActionConfig tests
# ======================================================================


class TestActionConfig:
    def test_resolve_action(self):
        cfg = ActionConfig(warn_threshold=2, stop_threshold=4, escalate_threshold=6)
        assert cfg.resolve_action(0) == Action.ALLOW
        assert cfg.resolve_action(1) == Action.ALLOW
        assert cfg.resolve_action(2) == Action.WARN
        assert cfg.resolve_action(3) == Action.WARN
        assert cfg.resolve_action(4) == Action.STOP
        assert cfg.resolve_action(6) == Action.ESCALATE
