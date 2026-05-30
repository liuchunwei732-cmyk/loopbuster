"""Core types and decision models for LoopBuster."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class Action(Enum):
    """What to do when a loop pattern is detected."""

    ALLOW = auto()
    WARN = auto()
    STOP = auto()
    ESCALATE = auto()


@dataclass(frozen=True)
class Decision:
    """Result of a loop guard check."""

    action: Action
    reason: str = ""
    strategy: str = ""
    confidence: float = 0.0
    step_number: int = 0

    @property
    def is_loop(self) -> bool:
        return self.action in (Action.STOP, Action.ESCALATE)

    @property
    def should_warn(self) -> bool:
        return self.action == Action.WARN

    @property
    def should_stop(self) -> bool:
        return self.action in (Action.STOP, Action.ESCALATE)


@dataclass
class ActionConfig:
    """Configure escalation thresholds for consecutive loop detections."""

    warn_threshold: int = 2
    stop_threshold: int = 4
    escalate_threshold: int = 6
    reflection_message: str = (
        "You appear to be stuck in a loop. Try a different approach."
    )

    def resolve_action(self, consecutive_hits: int) -> Action:
        """Map consecutive hit count to action level."""
        if consecutive_hits >= self.escalate_threshold:
            return Action.ESCALATE
        if consecutive_hits >= self.stop_threshold:
            return Action.STOP
        if consecutive_hits >= self.warn_threshold:
            return Action.WARN
        return Action.ALLOW


@dataclass
class AdaptiveActionConfig:
    """Action config that adapts thresholds based on action diversity.

    When the agent is trying diverse actions (high diversity ratio),
    thresholds are relaxed to avoid false positives. When it's stuck
    on a small set of actions (low diversity), thresholds tighten.

    Diversity ratio = unique action signatures / total actions in window
    """

    # Base thresholds (used at diversity == 0.5)
    base_warn: int = 3
    base_stop: int = 5
    base_escalate: int = 8

    # How much thresholds scale with diversity (multiplier range)
    min_multiplier: float = 0.5  # tighten at low diversity
    max_multiplier: float = 2.0  # relax at high diversity

    # Window for diversity calculation
    diversity_window: int = 20

    reflection_message: str = (
        "You appear to be stuck in a loop. Try a different approach."
    )

    # Internal state (not config)
    _action_history: deque[str] = field(
        default_factory=lambda: deque(maxlen=20), init=False, repr=False
    )

    def record_action(self, tool: str) -> None:
        """Record an action for diversity tracking."""
        self._action_history.append(tool)

    @property
    def diversity_ratio(self) -> float:
        """Ratio of unique actions to total actions in the window."""
        if not self._action_history:
            return 1.0
        return len(set(self._action_history)) / len(self._action_history)

    def _multiplier(self) -> float:
        """Map diversity ratio [0..1] to multiplier [min..max]."""
        d = self.diversity_ratio
        # Linear interpolation: low diversity → tighten, high → relax
        return self.min_multiplier + (self.max_multiplier - self.min_multiplier) * d

    @property
    def warn_threshold(self) -> int:
        return max(1, int(self.base_warn * self._multiplier()))

    @property
    def stop_threshold(self) -> int:
        return max(2, int(self.base_stop * self._multiplier()))

    @property
    def escalate_threshold(self) -> int:
        return max(3, int(self.base_escalate * self._multiplier()))

    def resolve_action(self, consecutive_hits: int) -> Action:
        if consecutive_hits >= self.escalate_threshold:
            return Action.ESCALATE
        if consecutive_hits >= self.stop_threshold:
            return Action.STOP
        if consecutive_hits >= self.warn_threshold:
            return Action.WARN
        return Action.ALLOW

    def reset(self) -> None:
        self._action_history.clear()


@dataclass
class ActionRecord:
    """A single agent action in the detection history."""

    tool: str
    args: dict[str, Any] | str | None = None
    output: str | None = None
    step: int = 0


@dataclass
class ToolCall:
    """An agent tool call event."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    """LLM token usage event."""

    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class TripReason:
    """Reason why a guard was tripped."""

    detector: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.detector}] {self.message}"


class TripError(RuntimeError):
    """Raised when a LoopBuster guard trips."""

    def __init__(self, reason: TripReason):
        super().__init__(str(reason))
        self.reason = reason
