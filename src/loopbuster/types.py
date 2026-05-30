"""Core types and decision models for LoopBuster."""

from __future__ import annotations

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
