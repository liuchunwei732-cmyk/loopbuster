"""Tests for ProgressSignal, RiskScorer, RootCauseAnalyzer, and enhanced Decision."""

from __future__ import annotations

import pytest

from loopbuster import (
    Action,
    ActionConfig,
    Decision,
    LoopBuster,
    LoopExplanation,
    ProgressReport,
    ProgressSignal,
    RiskReport,
    RiskScorer,
    RootCause,
    RootCauseAnalyzer,
)
from loopbuster.types import ActionRecord


# ======================================================================
# ProgressSignal tests
# ======================================================================


class TestProgressSignal:
    def test_no_data(self):
        ps = ProgressSignal()
        r = ps.score()
        assert r.gain == 1.0
        assert "Not enough data" in r.detail

    def test_single_record(self):
        ps = ProgressSignal()
        ps.record("hello world")
        r = ps.score()
        assert r.gain == 1.0

    def test_identical_outputs_low_gain(self):
        ps = ProgressSignal()
        ps.record("the capital of France is Paris")
        ps.record("the capital of France is Paris")
        r = ps.score()
        assert r.gain < 0.2, f"Expected low gain for identical outputs, got {r.gain}"
        assert "low information gain" in r.detail or "Very low" in r.detail

    def test_different_outputs_high_gain(self):
        ps = ProgressSignal()
        ps.record("the capital of France is Paris")
        ps.record("the population of Tokyo is 14 million")
        r = ps.score()
        assert r.gain > 0.5, f"Expected high gain for different outputs, got {r.gain}"
        assert "Healthy" in r.detail

    def test_intermediate_similarity(self):
        ps = ProgressSignal()
        ps.record("Paris France London UK")
        ps.record("Paris France Tokyo Japan")
        r = ps.score()
        assert 0.2 <= r.gain <= 0.8, f"Expected moderate gain, got {r.gain}"

    def test_empty_output(self):
        ps = ProgressSignal()
        ps.record("")
        r = ps.score()
        assert r.gain == 1.0  # empty output skipped, still 1 record

    def test_multiple_outputs_rising_trend(self):
        ps = ProgressSignal(window=5)
        ps.record("hello")
        ps.record("hello world")
        ps.record("hello world foo bar baz qux")
        r = ps.score()
        # Each subsequent output adds new tokens → rising novelty
        assert r.trend in ("rising", "steady")

    def test_multiple_outputs_falling_trend(self):
        ps = ProgressSignal(window=5)
        ps.record("hello world foo bar baz qux")
        ps.record("hello world foo bar")
        ps.record("hello world")
        r = ps.score()
        assert r.trend in ("falling", "steady")

    def test_reset(self):
        ps = ProgressSignal()
        ps.record("hello")
        ps.record("world")
        ps.reset()
        r = ps.score()
        assert r.gain == 1.0  # reset clears state

    def test_token_overlap_identical(self):
        from loopbuster.progress import token_overlap
        assert token_overlap("a b c", "a b c") == 0.0  # nothing new

    def test_token_overlap_completely_different(self):
        from loopbuster.progress import token_overlap
        assert token_overlap("a b c", "d e f") == 1.0  # everything new

    def test_token_overlap_partial(self):
        from loopbuster.progress import token_overlap
        assert token_overlap("a b c", "a d e") == 0.5  # 2/4 new

    def test_ngram_novelty(self):
        from loopbuster.progress import ngram_novelty
        assert ngram_novelty("hello world", "hello world", n=2) == 0.0
        assert ngram_novelty("hello", "world", n=2) == 1.0


# ======================================================================
# RiskScorer tests
# ======================================================================


class TestRiskScorer:
    def test_no_data(self):
        rs = RiskScorer()
        r = rs.score()
        assert r.overall == 0.0
        assert "No data yet" in r.summary

    def test_single_action_no_risk(self):
        rs = RiskScorer()
        rs.observe(ActionRecord(tool="search", args={"q": "hello"}, output="result"))
        r = rs.score()
        assert r.overall < 0.5

    def test_diverse_actions_low_risk(self):
        rs = RiskScorer(window=10)
        for i in range(10):
            rs.observe(ActionRecord(
                tool=f"tool_{i}",
                args={"n": i},
                output=f"result_{i}",
            ))
        r = rs.score()
        assert r.overall < 0.5
        assert r.entropy < 0.5  # diverse tools → high entropy → low risk

    def test_repeating_same_action_high_risk(self):
        rs = RiskScorer(window=10)
        for _ in range(10):
            rs.observe(ActionRecord(
                tool="search",
                args={"q": "same"},
                output="same result",
            ))
        r = rs.score()
        assert r.overall > 0.5, f"Expected high risk for repeats, got {r.overall}"
        assert r.entropy > 0.5  # all same tool → low entropy → high risk

    def test_revisitation_risk(self):
        rs = RiskScorer(window=10)
        # Two different tools but same output pattern
        for _ in range(5):
            rs.observe(ActionRecord(tool="search", args={"q": "a"}, output="same result"))
            rs.observe(ActionRecord(tool="read", args={"path": "b"}, output="same result"))

        r = rs.score()
        # The state fingerprint includes the output, so revisitation should catch this
        assert r.revisitation > 0, f"Expected revisitation risk > 0, got {r.revisitation}"

    def test_risk_report_properties(self):
        r = RiskReport(overall=0.3, entropy=0.2, revisitation=0.1, progress=0.4, summary="ok")
        assert not r.is_warning
        assert not r.is_critical

        r2 = RiskReport(overall=0.6, entropy=0.5, revisitation=0.5, progress=0.5, summary="warn")
        assert r2.is_warning
        assert not r2.is_critical

        r3 = RiskReport(overall=0.9, entropy=0.8, revisitation=0.8, progress=0.8, summary="crit")
        assert r3.is_warning
        assert r3.is_critical

    def test_reset(self):
        rs = RiskScorer(window=5)
        for _ in range(5):
            rs.observe(ActionRecord(tool="search", args={"q": "x"}, output="y"))
        r1 = rs.score()
        assert r1.overall > 0.5
        rs.reset()
        r2 = rs.score()
        assert r2.overall < 0.3


# ======================================================================
# RootCauseAnalyzer tests
# ======================================================================


class TestRootCauseAnalyzer:
    def make_history(self, tools: list[str], outputs: list[str] | None = None) -> list[ActionRecord]:
        """Helper to create action history."""
        if outputs is None:
            outputs = [f"result_{i}" for i in range(len(tools))]
        return [
            ActionRecord(tool=t, output=o, step=i + 1)
            for i, (t, o) in enumerate(zip(tools, outputs))
        ]

    def test_exact_repeat(self):
        analyzer = RootCauseAnalyzer()
        history = self.make_history(["search"] * 5)
        decision = Decision(
            action=Action.STOP,
            reason="Exact repeat: 'search' repeated 5 times",
            strategy="exact_repeat",
            confidence=1.0,
            step_number=5,
        )
        expl = analyzer.explain(decision, history)
        assert expl.root_cause in (RootCause.EXACT_REPEAT,)
        assert expl.suggestion

    def test_fuzzy_repeat(self):
        analyzer = RootCauseAnalyzer()
        history = self.make_history(["search"] * 5)
        decision = Decision(
            action=Action.WARN,
            reason="Fuzzy repeat: 'search' similar to 3 recent calls",
            strategy="fuzzy_repeat",
            confidence=0.8,
            step_number=5,
        )
        expl = analyzer.explain(decision, history)
        assert expl.root_cause == RootCause.TOOL_STUCK
        assert expl.suggestion

    def test_cycle_detection(self):
        analyzer = RootCauseAnalyzer()
        history = self.make_history(["a", "b", "c", "a", "b", "c"])
        decision = Decision(
            action=Action.STOP,
            reason="Cycle detected: [a → b → c] repeated 2 times",
            strategy="cycle_detection",
            confidence=0.85,
            step_number=6,
        )
        expl = analyzer.explain(decision, history)
        assert expl.root_cause == RootCause.CYCLE_TRAP
        assert "Cycle Trap" in expl.root_cause_label

    def test_output_stagnation(self):
        analyzer = RootCauseAnalyzer()
        history = self.make_history(
            ["search"] * 3,
            outputs=["Paris has 2.1M people"] * 3,
        )
        decision = Decision(
            action=Action.STOP,
            reason="Output stagnation: 'search' returned similar output 3 times",
            strategy="output_stagnation",
            confidence=0.9,
            step_number=3,
        )
        expl = analyzer.explain(decision, history)
        assert expl.root_cause == RootCause.OUTPUT_EQUIVALENCE
        assert expl.suggestion

    def test_hung_coroutine(self):
        analyzer = RootCauseAnalyzer()
        history = self.make_history(["search"])
        decision = Decision(
            action=Action.ESCALATE,
            reason="Hung coroutine detected: action 'search' took 35.0s",
            strategy="hung_coroutine",
            confidence=1.0,
            step_number=2,
        )
        expl = analyzer.explain(decision, history)
        assert expl.root_cause == RootCause.REASONING_LOOP
        assert "Coroutine" in expl.root_cause_label

    def test_empty_history(self):
        analyzer = RootCauseAnalyzer()
        decision = Decision(action=Action.STOP, reason="test", strategy="exact_repeat", confidence=1.0)
        expl = analyzer.explain(decision, [])
        assert expl.root_cause == RootCause.UNKNOWN
        assert expl.confidence < 0.5

    def test_fallback(self):
        analyzer = RootCauseAnalyzer()
        history = self.make_history(["a", "b", "c"])
        decision = Decision(
            action=Action.WARN,
            reason="some unknown pattern",
            strategy="unknown_strategy",
            confidence=0.5,
            step_number=3,
        )
        expl = analyzer.explain(decision, history)
        assert expl.root_cause == RootCause.UNKNOWN

    def test_loop_explanation_dataclass(self):
        expl = LoopExplanation(
            root_cause=RootCause.TOOL_STUCK,
            root_cause_label="Stuck on a Tool",
            summary="Agent is stuck",
            detail="More details here",
            suggestion="Try something else",
            confidence=0.85,
        )
        assert expl.root_cause == RootCause.TOOL_STUCK
        assert expl.suggestion == "Try something else"


# ======================================================================
# Enhanced Decision.explain() tests
# ======================================================================


class TestDecisionExplain:
    def test_decision_explain(self):
        """Decision.explain() should return a LoopExplanation."""
        decision = Decision(
            action=Action.STOP,
            reason="Cycle detected: [a → b] repeated 3 times",
            strategy="cycle_detection",
            confidence=0.9,
            step_number=10,
        )
        history = [
            ActionRecord(tool=t, step=i + 1)
            for i, t in enumerate(["a", "b"] * 5)
        ]
        expl = decision.explain(history)
        assert isinstance(expl, LoopExplanation)
        assert expl.suggestion

    def test_decision_explain_empty_history(self):
        """Should return a reasonable fallback even without history."""
        decision = Decision(
            action=Action.STOP,
            reason="Loop detected",
            strategy="exact_repeat",
            confidence=1.0,
            step_number=5,
        )
        expl = decision.explain(history=[])
        assert isinstance(expl, LoopExplanation)
        assert expl.summary


# ======================================================================
# Integration: LoopBuster with deep detection
# ======================================================================


class TestLoopBusterDeepDetection:
    def test_risk_score_property_early(self):
        """risk_score should be None before enough data."""
        lb = LoopBuster()
        lb.check(tool="search", args={"q": "a"})
        assert lb.risk_score is None or lb.risk_score.overall <= 0.5

    def test_progress_signal_property(self):
        """progress_signal should always be accessible."""
        lb = LoopBuster()
        ps = lb.progress_signal
        assert ps is not None

    def test_risk_score_after_many_repeats(self):
        """After many repeated actions, risk_score should be elevated."""
        lb = LoopBuster()
        for _ in range(10):
            lb.check(tool="search", args={"q": "same"}, output="same result")

        risk = lb.risk_score
        assert risk is not None
        assert risk.overall > 0.3, f"Expected elevated risk, got {risk.overall}"

    def test_report_includes_risk_and_progress(self):
        """report() should include risk_score and progress_signal."""
        lb = LoopBuster()
        for i in range(5):
            lb.check(tool=f"tool_{i}", args={"n": i}, output=f"result_{i}")

        report = lb.report()
        assert "risk_score" in report
        assert "progress_signal" in report

    def test_report_without_output(self):
        """report() should handle actions without output gracefully."""
        lb = LoopBuster()
        for i in range(5):
            lb.check(tool=f"tool_{i}", args={"n": i})

        report = lb.report()
        assert "risk_score" in report
        # progress_signal may be None if no outputs recorded
        assert "progress_signal" in report
