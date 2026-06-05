"""Detection strategies for identifying loop patterns in agent behavior.

Each strategy implements a `check()` method that returns a confidence score
(0.0 = no loop, 1.0 = definite loop) and an explanation string.

All strategies are framework-agnostic and work with any agent loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field

from loopbuster.similarity import args_similarity
from loopbuster.types import ActionRecord


class DetectionStrategy(ABC):
    """Base class for all loop detection strategies."""

    @abstractmethod
    def check(self, record: ActionRecord) -> tuple[float, str]:
        """Returns (confidence, reason). Higher confidence = more likely a loop."""
        ...

    def reset(self) -> None:
        ...


# ---------------------------------------------------------------------------
# Strategy 1: Exact Repeat
# ---------------------------------------------------------------------------


@dataclass
class ExactRepeatStrategy(DetectionStrategy):
    """Detect exact (tool, args) repetitions within the window.

    Confidence climbs linearly from 0 to 1 as consecutive identical
    actions fill the window.
    """

    window_size: int = 5
    _history: deque[ActionRecord] = field(default_factory=deque, init=False, repr=False)

    def check(self, record: ActionRecord) -> tuple[float, str]:
        self._history.append(record)
        if len(self._history) > self.window_size:
            self._history.popleft()

        if len(self._history) < 2:
            return 0.0, ""

        first = self._history[0]
        all_same = all(
            r.tool == first.tool and r.args == first.args for r in self._history
        )

        if all_same and len(self._history) >= self.window_size:
            return 1.0, (
                f"Exact repeat: '{first.tool}' called "
                f"{len(self._history)} times with identical args"
            )

        prev = self._history[-2]
        if record.tool == prev.tool and record.args == prev.args:
            count = 0
            for r in reversed(self._history):
                if r.tool == record.tool and r.args == record.args:
                    count += 1
                else:
                    break
            confidence = min(1.0, count / self.window_size)
            return confidence, (
                f"Exact repeat: '{record.tool}' repeated {count} times consecutively"
            )

        return 0.0, ""

    def reset(self) -> None:
        self._history.clear()


# ---------------------------------------------------------------------------
# Strategy 2: Fuzzy Repeat
# ---------------------------------------------------------------------------


@dataclass
class FuzzyRepeatStrategy(DetectionStrategy):
    """Detect near-identical actions using hybrid tool-frequency + similarity scoring.

    Two signals blended:
      1. Tool-frequency: how often this tool appears in the window (high = stuck
         on a tool even if args change)
      2. Args-similarity: how similar recent args are to current args

    Previous version only used args-similarity as a gate, which meant agents
    calling the same tool with genuinely different args (e.g. different search
    queries) were never flagged. Blending both signals catches both cases.
    """

    window_size: int = 5
    similarity_threshold: float = 0.85
    # Weight of tool-frequency signal vs args-similarity in the final blend
    tool_frequency_weight: float = 0.6
    _history: deque[ActionRecord] = field(default_factory=deque, init=False, repr=False)

    def check(self, record: ActionRecord) -> tuple[float, str]:
        self._history.append(record)
        if len(self._history) > self.window_size:
            self._history.popleft()

        if len(self._history) < 2:
            return 0.0, ""

        # --- Signal 1: tool-frequency ---
        same_tool_count = sum(1 for r in self._history if r.tool == record.tool)
        tool_freq_conf = (same_tool_count - 1) / (self.window_size - 1)  # 0~1

        # --- Signal 2: args-similarity (only for same-tool prev calls) ---
        high_sim_count = 0
        max_sim = 0.0
        total_same_tool = 0
        for prev in list(self._history)[:-1]:
            if record.tool != prev.tool:
                continue
            total_same_tool += 1
            sim = args_similarity(record.args, prev.args)
            max_sim = max(max_sim, sim)
            if sim >= self.similarity_threshold:
                high_sim_count += 1

        # Args-similarity confidence: fraction of same-tool prev calls above threshold
        args_conf = high_sim_count / max(total_same_tool, 1)

        # --- Blend ---
        # High tool frequency + low args sim = stuck on a tool (moderate confidence)
        # Low tool frequency + high args sim = unlikely to be a loop (low confidence)
        # Both high = definite fuzzy repeat (high confidence)
        w = self.tool_frequency_weight
        confidence = w * tool_freq_conf + (1 - w) * args_conf
        confidence = max(0.0, min(1.0, confidence))

        # 保底：如果同一种工具占据 window 过半，至少给 0.35 的置信度
        # （引擎的阈值是 > 0.3，所以保底必须大于 0.3 才能触发 consecutive_hits）
        if same_tool_count > self.window_size // 2:
            confidence = max(confidence, 0.35)
        elif confidence < 0.1:
            return 0.0, ""

        # Build detail string
        parts = []
        if tool_freq_conf > 0.3:
            parts.append(f"used {same_tool_count}/{self.window_size} times")
        if args_conf > 0.3:
            parts.append(f"args sim {max_sim:.2f}")

        return confidence, (
            f"Fuzzy repeat: '{record.tool}' " + ", ".join(parts)
        )

    def reset(self) -> None:
        self._history.clear()


# ---------------------------------------------------------------------------
# Strategy 3: Cycle Detection (A→B→C→A→B→C)
# ---------------------------------------------------------------------------


@dataclass
class CycleDetectionStrategy(DetectionStrategy):
    """Detect repeating cycles of tool sequences (e.g., A→B→C→A→B→C).

    Distinguishes cycles from simple repeats by requiring at least two
    distinct tools in the pattern (avoiding overlap with ExactRepeat).
    """

    max_cycle_length: int = 5
    min_repetitions: int = 2
    _tool_sequence: list[str] = field(default_factory=list, init=False, repr=False)

    def check(self, record: ActionRecord) -> tuple[float, str]:
        self._tool_sequence.append(record.tool)

        min_needed = 2 * 2
        if len(self._tool_sequence) < min_needed:
            return 0.0, ""

        seq = self._tool_sequence
        best_confidence = 0.0
        best_reason = ""

        for cycle_len in range(2, self.max_cycle_length + 1):
            if len(seq) < cycle_len * self.min_repetitions:
                continue

            pattern = seq[-cycle_len:]

            if len(set(pattern)) < 2:
                continue

            reps = 0
            for i in range(len(seq) - cycle_len, -1, -cycle_len):
                segment = seq[i : i + cycle_len]
                if segment == pattern:
                    reps += 1
                else:
                    break

            if reps >= self.min_repetitions:
                confidence = min(1.0, reps / (self.min_repetitions + 2))
                cycle_str = " → ".join(pattern)
                reason = f"Cycle detected: [{cycle_str}] repeated {reps} times"
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_reason = reason

        max_len = self.max_cycle_length * (self.min_repetitions + 3)
        if len(self._tool_sequence) > max_len:
            self._tool_sequence = self._tool_sequence[-max_len:]

        return best_confidence, best_reason

    def reset(self) -> None:
        self._tool_sequence.clear()


# ---------------------------------------------------------------------------
# Strategy 4: Output Stagnation
# ---------------------------------------------------------------------------


@dataclass
class OutputStagnationStrategy(DetectionStrategy):
    """Detect when tool outputs stop changing.

    An agent that keeps calling different tools but getting the same
    result is stuck — this catches that case.
    """

    window_size: int = 4
    similarity_threshold: float = 0.90
    _outputs: deque[tuple[str, str]] = field(default_factory=deque, init=False, repr=False)

    def check(self, record: ActionRecord) -> tuple[float, str]:
        if record.output is None:
            return 0.0, ""

        self._outputs.append((record.tool, record.output))
        if len(self._outputs) > self.window_size:
            self._outputs.popleft()

        if len(self._outputs) < 2:
            return 0.0, ""

        same_tool_outputs = [o for t, o in self._outputs if t == record.tool]
        if len(same_tool_outputs) < 2:
            return 0.0, ""

        stagnant_count = 0
        for prev_out in same_tool_outputs[:-1]:
            sim = args_similarity(prev_out, record.output)
            if sim >= self.similarity_threshold:
                stagnant_count += 1

        if stagnant_count == 0:
            return 0.0, ""

        confidence = min(1.0, stagnant_count / (len(same_tool_outputs) - 1))
        return confidence, (
            f"Output stagnation: '{record.tool}' returned similar output "
            f"{stagnant_count + 1} times (threshold: {self.similarity_threshold:.2f})"
        )

    def reset(self) -> None:
        self._outputs.clear()


# ---------------------------------------------------------------------------
# Strategy 5: Combined / Meta Strategy
# ---------------------------------------------------------------------------


@dataclass
class CompositeStrategy(DetectionStrategy):
    """Run all sub-strategies and return the highest-confidence result.

    This is the default strategy used by LoopBuster — it orchestrates all
    four detection strategies and picks the strongest signal.
    """

    exact: ExactRepeatStrategy = field(default_factory=ExactRepeatStrategy)
    fuzzy: FuzzyRepeatStrategy = field(default_factory=FuzzyRepeatStrategy)
    cycle: CycleDetectionStrategy = field(default_factory=CycleDetectionStrategy)
    stagnation: OutputStagnationStrategy = field(
        default_factory=OutputStagnationStrategy
    )

    def check(self, record: ActionRecord) -> tuple[float, str]:
        results = [
            ("exact_repeat", *self.exact.check(record)),
            ("fuzzy_repeat", *self.fuzzy.check(record)),
            ("cycle_detection", *self.cycle.check(record)),
            ("output_stagnation", *self.stagnation.check(record)),
        ]

        # Collect strategies that exceeded minimum threshold
        active = [
            (name, conf, reason)
            for name, conf, reason in results
            if conf >= 0.2
        ]

        if not active:
            return 0.0, "", ""

        if len(active) == 1:
            name, conf, reason = active[0]
            return conf, reason, name

        # Multi-strategy consensus: blend confidences weighted by each
        # strategy's reliability. ExactRepeat and CycleDetection are
        # lower-noise; FuzzyRepeat and OutputStagnation are weighted down.
        weights = {
            "exact_repeat": 1.0,
            "cycle_detection": 0.9,
            "fuzzy_repeat": 0.7,
            "output_stagnation": 0.5,
        }

        total_weight = 0.0
        weighted_conf = 0.0
        for name, conf, _ in active:
            w = weights.get(name, 0.5)
            weighted_conf += conf * w
            total_weight += w

        # Single very high confidence → trust directly (avoids blurring
        # a clear signal with noisy strategies)
        max_conf_name, max_conf, max_reason = max(active, key=lambda x: x[1])
        if max_conf >= 0.9:
            return max_conf, max_reason, max_conf_name

        # Blend: 70% weighted average + 30% max confidence
        blended = 0.7 * (weighted_conf / total_weight) + 0.3 * max_conf

        if blended >= 0.5:
            return blended, max_reason, max_conf_name

        return 0.0, "", ""

    def reset(self) -> None:
        for s in (self.exact, self.fuzzy, self.cycle, self.stagnation):
            s.reset()
