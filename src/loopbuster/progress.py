"""ProgressSignal — track information gain across agent actions.

The core insight that separates a good cycle from a bad cycle:

  **Good cycle**: agent repeats a tool pattern but each iteration
  produces *new information* — the set of accumulated knowledge grows.

  **Bad cycle**: agent repeats a tool pattern and the output is
  semantically the same — no information gain, just token burn.

ProgressSignal computes an information-gain score for each action
by comparing its output against a sliding window of recent outputs.
Low gain over multiple steps flags a bad cycle even if the tool names
and arguments vary wildly.

Usage:
    ps = ProgressSignal(window=5)
    ps.record(output="Results: Paris population = 2.1M")
    progress = ps.score()  # 0.0 (nothing to compare yet)

    ps.record(output="Results: Paris population = 2.1M")
    progress = ps.score()  # low → stagnation

    ps.record(output="Results: Tokyo population = 14M")
    progress = ps.score()  # high → productive
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loopbuster.types import ActionRecord


# ---------------------------------------------------------------------------
# Information-gain primitives
# ---------------------------------------------------------------------------


def token_overlap(a: str, b: str) -> float:
    """Fraction of tokens in `b` that are *new* relative to `a`.

    Returns 0.0 (all tokens in b already seen in a) to 1.0
    (all tokens in b are new).
    """
    if not a and not b:
        return 1.0
    if not a:
        return 1.0
    if not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_b:
        return 0.0
    new_tokens = tokens_b - tokens_a
    return len(new_tokens) / len(tokens_b)


def ngram_novelty(a: str, b: str, n: int = 3) -> float:
    """NGram-level novelty: fraction of n-grams in b unseen in a.

    Catches subtler repetition than word-level token overlap.
    """
    if not b:
        return 0.0
    a_ngrams = _ngrams(a, n)
    b_ngrams = _ngrams(b, n)
    if not b_ngrams:
        return 0.0
    novel = b_ngrams - a_ngrams
    return len(novel) / len(b_ngrams)


def _ngrams(text: str, n: int) -> set[str]:
    """Build a set of character n-grams from text."""
    text = text.lower()
    if len(text) < n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


# ---------------------------------------------------------------------------
# ProgressSignal
# ---------------------------------------------------------------------------


@dataclass
class ProgressSignal:
    """Tracks information gain across recent agent actions.

    The `score()` method returns a ProgressReport with:
      - `gain`:   0.0 (stagnant) to 1.0 (high novelty)
      - `trend`:  "rising" | "steady" | "falling"
      - `detail`: human-readable explanation

    The signal is computed by comparing each new output against a *union*
    of all outputs in the window. If outputs keep saying the same thing,
    novelty asymptotically approaches 0.
    """

    window: int = 5
    _outputs: deque[str] = field(default_factory=deque, init=False, repr=False)
    _union: set[str] = field(default_factory=set, init=False, repr=False)

    def record(self, output: str) -> None:
        """Record an action output."""
        if not output:
            return
        self._outputs.append(output)
        if len(self._outputs) > self.window:
            old = self._outputs.popleft()
            # Rebuild union on overflow (simpler than tracking per-output sets)
            self._union = set()
            for o in self._outputs:
                self._union.update(o.split())
        self._union.update(output.split())

    def score(self) -> ProgressReport:
        """Compute information-gain score for the most recent output.

        Returns a ProgressReport. If fewer than 2 outputs have been
        recorded, the gain is 1.0 (no basis for comparison yet).
        """
        if len(self._outputs) < 2:
            return ProgressReport(gain=1.0, trend="steady", detail="Not enough data")

        latest = self._outputs[-1]
        prev = self._outputs[-2]

        # Token-level novelty against immediate predecessor
        token_novelty = token_overlap(prev, latest)

        # N-gram novelty against immediate predecessor
        ngram_novel = ngram_novelty(prev, latest, n=4)

        # Novelty against the full window union
        if self._union:
            window_tokens = self._union - set(latest.split())
            window_novelty = token_overlap(" ".join(window_tokens), latest)
        else:
            window_novelty = 0.0

        # Blended gain: immediate novelty weighted more heavily
        gain = 0.5 * token_novelty + 0.3 * ngram_novel + 0.2 * window_novelty
        gain = max(0.0, min(1.0, gain))

        # Trend: compare last two gain values if we have enough history
        trend = self._compute_trend(gain)

        if gain < 0.2:
            detail = (
                f"Very low information gain ({gain:.2f}) — output is nearly "
                f"identical to recent actions. Agent may be stuck."
            )
        elif gain < 0.5:
            detail = (
                f"Moderate information gain ({gain:.2f}) — some new content "
                f"but significant overlap with prior outputs."
            )
        else:
            detail = (
                f"Healthy information gain ({gain:.2f}) — action produced "
                f"substantially new content."
            )

        return ProgressReport(
            gain=round(gain, 3),
            trend=trend,
            detail=detail,
        )

    def _compute_trend(self, current_gain: float) -> str:
        """Compare current gain to a short-term moving average."""
        if len(self._outputs) < 3:
            return "steady"
        recent_gains = []
        for i in range(1, min(4, len(self._outputs))):
            a = self._outputs[-(i + 1)]
            b = self._outputs[-i]
            recent_gains.append(token_overlap(a, b))
        if not recent_gains:
            return "steady"
        avg = sum(recent_gains) / len(recent_gains)
        # A gain higher than average means novelty is increasing
        if current_gain > avg + 0.15:
            return "rising"
        if current_gain < avg - 0.15:
            return "falling"
        return "steady"

    def reset(self) -> None:
        self._outputs.clear()
        self._union.clear()


@dataclass
class ProgressReport:
    """Result of a ProgressSignal score computation."""

    gain: float
    trend: str  # "rising" | "steady" | "falling"
    detail: str
