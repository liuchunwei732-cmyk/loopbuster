"""RiskScorer — predictive loop risk scoring for early warning.

Instead of waiting for a full pattern to repeat before flagging a loop,
RiskScorer computes a *per-action risk score* based on leading indicators:

  1. **Entropy collapse**: when the agent's tool choices become less
     diverse over time, the risk of entering a loop increases.
  2. **Revisitation rate**: how often the agent returns to previously
     visited (tool, output-hash) states — a proxy for state-space
     exploration efficiency.
  3. **Progress decay**: when information gain per action is trending
     downward over the last N steps.

The final risk score is a weighted blend of these three signals,
output as a float in [0.0, 1.0] alongside a human-readable summary.

Usage:
    scorer = RiskScorer(window=10)
    scorer.observe(tool="search", args={"q": "python"}, output="...")
    report = scorer.score()  # RiskReport(gain=0.3, ...)
    if report.overall > 0.7:
        logger.warning(f"High loop risk: {report.summary}")
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any

from loopbuster.progress import ProgressSignal, token_overlap
from loopbuster.types import ActionRecord


@dataclass
class RiskReport:
    """Result of a RiskScorer computation."""

    overall: float        # 0.0 (safe) ~ 1.0 (likely looping)
    entropy: float        # tool-diversity component
    revisitation: float   # state-revisiting component
    progress: float       # information-gain decay component (inverted: low gain = high risk)
    summary: str          # human-readable interpretation

    @property
    def is_warning(self) -> bool:
        return self.overall >= 0.5

    @property
    def is_critical(self) -> bool:
        return self.overall >= 0.8


@dataclass
class RiskScorer:
    """Computes per-action loop risk from entropy, revisitation, and progress.

    Designed to be called after every action in the agent loop. The score
    is a leading indicator — it can warn before any strategy fires.
    """

    window: int = 10
    _tools: deque[str] = field(default_factory=deque, init=False, repr=False)
    _states: deque[str] = field(default_factory=deque, init=False, repr=False)
    _state_counts: Counter = field(default_factory=Counter, init=False, repr=False)
    _progress: ProgressSignal = field(
        default_factory=lambda: ProgressSignal(window=5), init=False, repr=False
    )
    _gain_history: deque[float] = field(
        default_factory=lambda: deque(maxlen=10), init=False, repr=False
    )

    # Weights for the three signal components
    entropy_weight: float = 0.30
    revisitation_weight: float = 0.35
    progress_weight: float = 0.35

    def observe(self, record: ActionRecord) -> None:
        """Record an action and update risk indicators."""

        # --- Tool diversity ---
        self._tools.append(record.tool)
        if len(self._tools) > self.window:
            self._tools.popleft()

        # --- State revisitation ---
        state_key = self._state_fingerprint(record)
        self._states.append(state_key)
        if len(self._states) > self.window:
            old = self._states.popleft()
            self._state_counts[old] -= 1
            if self._state_counts[old] <= 0:
                del self._state_counts[old]
        self._state_counts[state_key] += 1

        # --- Progress ---
        if record.output:
            self._progress.record(record.output)
            pr = self._progress.score()
            self._gain_history.append(pr.gain)

    def score(self) -> RiskReport:
        """Compute a composite risk score from current indicators."""
        if not self._tools:
            return RiskReport(
                overall=0.0, entropy=0.0, revisitation=0.0,
                progress=0.0, summary="No data yet.",
            )

        e = self._entropy_risk()
        r = self._revisitation_risk()
        p = self._progress_risk()

        overall = (
            self.entropy_weight * e
            + self.revisitation_weight * r
            + self.progress_weight * p
        )
        overall = max(0.0, min(1.0, overall))

        # Build summary
        parts = []
        if e > 0.6:
            parts.append(f"tool diversity collapsing ({e:.2f})")
        if r > 0.6:
            parts.append(f"revisiting same states ({r:.2f})")
        if p > 0.6:
            parts.append(f"information gain declining ({p:.2f})")

        if overall < 0.3:
            summary = "Agent appears healthy."
        elif overall < 0.5:
            summary = "Mild risk signals detected."
        elif overall < 0.7:
            summary = "Moderate loop risk. " + "; ".join(parts)
        elif overall < 0.85:
            summary = "HIGH loop risk. " + "; ".join(parts)
        else:
            summary = "CRITICAL loop risk — immediate intervention advised. " + "; ".join(parts)

        return RiskReport(
            overall=round(overall, 3),
            entropy=round(e, 3),
            revisitation=round(r, 3),
            progress=round(p, 3),
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Component scores
    # ------------------------------------------------------------------

    def _entropy_risk(self) -> float:
        """Risk from low tool diversity.

        Uses normalized Shannon entropy of the tool distribution over the
        window. Entropy near 0 (all the same tool) → risk 1.0.
        """
        n = len(self._tools)
        if n < 2:
            return 0.0
        counter = Counter(self._tools)
        # Shannon entropy
        entropy = 0.0
        for tool in counter:
            p = counter[tool] / n
            if p > 0:
                entropy -= p * __import__("math").log2(p)
        # Normalize: max entropy for n items is log2(n)
        max_entropy = __import__("math").log2(min(n, len(counter)))
        if max_entropy == 0:
            return 0.0
        normalized = entropy / max_entropy
        # Invert: low entropy → high risk
        risk = 1.0 - normalized
        return max(0.0, min(1.0, risk))

    def _revisitation_risk(self) -> float:
        """Risk from repeatedly visiting the same (tool, output-fingerprint) states.

        If any state key appears more than once in the window, that's a sign
        the agent is circling back to where it's been.
        """
        n = len(self._states)
        if n < 2:
            return 0.0
        max_count = max(self._state_counts.values()) if self._state_counts else 1
        if max_count <= 1:
            return 0.0
        # Risk scales with how many times the most-visited state repeats
        risk = (max_count - 1) / (n - 1)
        return max(0.0, min(1.0, risk))

    def _progress_risk(self) -> float:
        """Risk from declining information gain.

        If the recent gain trend is "falling", risk climbs.
        If the absolute gain is very low, risk is high regardless of trend.
        """
        if len(self._gain_history) < 2:
            return 0.0
        recent = list(self._gain_history)[-5:]
        avg_gain = sum(recent) / len(recent)
        # Low gain → high risk (invert)
        gain_risk = 1.0 - avg_gain

        # Trend penalty: if gain has been consistently dropping
        if len(recent) >= 3:
            half = len(recent) // 2
            first_half = sum(recent[:half]) / half
            second_half = sum(recent[half:]) / (len(recent) - half)
            if second_half < first_half * 0.8:
                # Falling trend adds a penalty
                gain_risk = min(1.0, gain_risk * 1.3)

        return max(0.0, min(1.0, gain_risk))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _state_fingerprint(record: ActionRecord) -> str:
        """Create a stable fingerprint of the action's (tool, output-semantics).

        Used to detect when the agent revisits the same state.
        """
        tool = record.tool or ""
        if record.output:
            # Use first ~100 chars of normalized output as a proxy for
            # "semantic state". This is intentionally coarse.
            out_sig = record.output.strip().lower()[:100]
        else:
            out_sig = ""
        return f"{tool}::{out_sig}"

    def reset(self) -> None:
        self._tools.clear()
        self._states.clear()
        self._state_counts.clear()
        self._progress.reset()
        self._gain_history.clear()
