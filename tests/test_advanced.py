"""Tests for async engine, adaptive thresholds, and stuck report."""

from __future__ import annotations

import asyncio

import pytest

from loopbuster import AsyncLoopBuster, LoopBuster
from loopbuster.types import Action, AdaptiveActionConfig


# ======================================================================
# Adaptive thresholds
# ======================================================================


class TestAdaptiveActionConfig:
    def test_diversity_high_relaxes(self):
        cfg = AdaptiveActionConfig(diversity_window=10)
        # Diverse actions
        for t in "abcdefghij":
            cfg.record_action(t)
        assert cfg.diversity_ratio == 1.0
        assert cfg.warn_threshold >= cfg.base_warn  # relaxed

    def test_diversity_low_tightens(self):
        cfg = AdaptiveActionConfig(diversity_window=10)
        # All same action
        for _ in range(10):
            cfg.record_action("search")
        assert cfg.diversity_ratio < 0.2
        # At low diversity, thresholds should be tighter (= lower)
        assert cfg.warn_threshold <= cfg.base_warn

    def test_resolve_action_low_diversity(self):
        cfg = AdaptiveActionConfig(base_warn=3, base_stop=5, base_escalate=8)
        for _ in range(10):
            cfg.record_action("search")
        # Tightened thresholds → should escalate earlier
        # At very low diversity, some thresholds may hit floor of 1-2-3
        assert cfg.resolve_action(1) in (Action.ALLOW, Action.WARN)

    def test_resolve_action_high_diversity(self):
        cfg = AdaptiveActionConfig(base_warn=3, base_stop=5, base_escalate=8)
        for t in "abcdefghij":
            cfg.record_action(t)
        # Relaxed thresholds → needs more hits to escalate
        assert cfg.resolve_action(4) == Action.ALLOW  # 4 < relaxed warn threshold

    def test_reset(self):
        cfg = AdaptiveActionConfig()
        for _ in range(5):
            cfg.record_action("same")
        assert cfg.diversity_ratio < 1.0
        cfg.reset()
        assert cfg.diversity_ratio == 1.0


# ======================================================================
# Stuck report
# ======================================================================


class TestStuckReport:
    def test_empty_report(self):
        lb = LoopBuster()
        r = lb.report()
        assert r["total_actions"] == 0
        assert r["diversity_ratio"] == 1.0
        assert len(r["recommendations"]) >= 1
        assert "No actions recorded yet." in r["recommendations"][0]

    def test_report_with_actions(self):
        lb = LoopBuster()
        for i in range(10):
            lb.check(tool=f"tool_{i}", args={"n": i})
        r = lb.report()
        assert r["total_actions"] == 10
        assert r["diversity_ratio"] == 1.0  # all different
        assert r["redundant_actions"] == 0

    def test_report_with_loop(self):
        lb = LoopBuster()
        for _ in range(10):
            lb.check(tool="search", args={"q": "same"})
        r = lb.report()
        assert r["total_actions"] == 10
        assert r["diversity_ratio"] < 0.5
        assert r["redundant_actions"] > 0
        # Should have one signature with high count
        assert len(r["top_repeated_patterns"]) >= 1
        assert r["top_repeated_patterns"][0][1] >= 5

    def test_report_tripped(self):
        lb = LoopBuster(budget_usd=0.001, auto_halt=False)
        lb.record_tokens("gpt-4o", input=100000, output=50000)
        r = lb.report()
        assert r["tripped"] is not None
        assert "BudgetCeiling" in r["tripped"]


# ======================================================================
# AsyncLoopBuster
# ======================================================================


class TestAsyncLoopBuster:
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncLoopBuster() as lb:
            from loopbuster.engine import current
            assert current() is lb
            d = await lb.acheck(tool="test")
            assert d.action == Action.ALLOW
        assert current() is None

    @pytest.mark.asyncio
    async def test_async_detection(self):
        async with AsyncLoopBuster() as lb:
            for i in range(5):
                d = await lb.acheck(tool=f"tool_{i}", args={"n": i})
                assert d.action == Action.ALLOW

    @pytest.mark.asyncio
    async def test_hung_coroutine_detection(self):
        """Simulate slow actions that trigger hung coroutine detection.

        The first acheck() call seeds _last_action_time. The second call
        detects the delay as a timeout. The third call exceeds max_slow_actions.
        """
        async with AsyncLoopBuster(action_timeout=0.01, max_slow_actions=2) as lb:
            # Step 1: seed last_action_time
            d0 = await lb.acheck(tool="setup")
            assert d0.action == Action.ALLOW

            await asyncio.sleep(0.05)  # exceeds timeout
            d1 = await lb.acheck(tool="slow_action_1")
            # slow_count=1, < max_slow_actions=2 → ALLOW
            assert d1.action == Action.ALLOW

            await asyncio.sleep(0.05)
            d2 = await lb.acheck(tool="slow_action_2")
            # slow_count=2 >= max_slow_actions → ESCALATE
            assert d2.is_loop
            assert "Hung coroutine" in d2.reason

    @pytest.mark.asyncio
    async def test_watch(self):
        async def gen():
            for i in range(3):
                yield f"tool_{i}", {"n": i}

        results = []
        async for tool, args, decision in AsyncLoopBuster.watch(gen()):
            results.append((tool, decision.action))
        assert len(results) == 3
        assert all(a == Action.ALLOW for _, a in results)

    @pytest.mark.asyncio
    async def test_watch_stops_early(self):
        """watch() should stop yielding if loop detected."""

        async def looping_gen():
            for _ in range(20):
                yield "search", {"q": "same"}

        results = []
        async for tool, args, decision in AsyncLoopBuster.watch(
            looping_gen(),
            action_config=AdaptiveActionConfig(
                base_warn=1, base_stop=2, base_escalate=3
            ),
        ):
            results.append((tool, decision.action))
            if decision.should_stop:
                break

        # Should have stopped before exhausting the 20-item generator
        assert len(results) < 20
