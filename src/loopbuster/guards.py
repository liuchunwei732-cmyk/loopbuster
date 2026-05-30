"""Guards that monitor various aspects of agent execution.

Each Guard subclass implements `observe_*` hooks and optionally returns
a TripReason if the guard condition is violated.

These are the three "emergency brakes" that complement the loop detection
strategies with hard boundary enforcement.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Callable

from loopbuster.pricing import estimate_cost, load_default_pricing
from loopbuster.types import TokenUsage, ToolCall, TripReason

logger = logging.getLogger("loopbuster")


class Guard(ABC):
    """Base class for execution guards."""

    def observe_call(self, event: ToolCall) -> TripReason | None:
        return None

    def observe_tokens(self, event: TokenUsage) -> TripReason | None:
        return None

    def observe_state(self, state: Any) -> TripReason | None:
        return None


# ---------------------------------------------------------------------------
# Guard 1: BudgetCeiling
# ---------------------------------------------------------------------------


class BudgetCeiling(Guard):
    """Trip when cumulative estimated cost crosses `limit_usd`.

    Tracks per-session spend against a hard dollar ceiling, pricing each
    token usage event against a community-maintained pricing table.
    """

    def __init__(self, limit_usd: float, pricing: dict | None = None):
        if limit_usd <= 0:
            raise ValueError("limit_usd must be > 0")
        self.limit_usd = limit_usd
        self.pricing = pricing or load_default_pricing()
        self.spent_usd: float = 0.0

    def observe_tokens(self, event: TokenUsage) -> TripReason | None:
        cost = estimate_cost(event.model, event.input_tokens, event.output_tokens, self.pricing)
        self.spent_usd += cost
        if self.spent_usd >= self.limit_usd:
            return TripReason(
                detector="BudgetCeiling",
                message=(
                    f"Budget ceiling ${self.limit_usd:.2f} reached "
                    f"(spent ${self.spent_usd:.4f})"
                ),
                details={
                    "limit_usd": self.limit_usd,
                    "spent_usd": self.spent_usd,
                    "last_model": event.model,
                    "last_input_tokens": event.input_tokens,
                    "last_output_tokens": event.output_tokens,
                },
            )
        return None


# ---------------------------------------------------------------------------
# Guard 2: RepeatCallGuard
# ---------------------------------------------------------------------------


class RepeatCallGuard(Guard):
    """Trip when the same (tool, args) appears `max_repeats` times in a window.

    Uses a stable hash of (tool, args) as a fingerprint for exact matching.
    This is the "circuit breaker" layer on top of the pattern-based strategies.
    """

    def __init__(self, max_repeats: int, window: int = 32):
        if max_repeats < 2:
            raise ValueError("max_repeats must be >= 2")
        self.max_repeats = max_repeats
        self.window = window
        self.recent: deque[tuple[str, str]] = deque(maxlen=window)

    def observe_call(self, event: ToolCall) -> TripReason | None:
        fingerprint = (event.name, _stable_hash(event.args))
        self.recent.append(fingerprint)
        count = sum(1 for fp in self.recent if fp == fingerprint)
        if count >= self.max_repeats:
            return TripReason(
                detector="RepeatCallGuard",
                message=(
                    f"Tool {event.name!r} called {count} times "
                    f"with identical arguments"
                ),
                details={"tool": event.name, "args": event.args, "count": count},
            )
        return None


# ---------------------------------------------------------------------------
# Guard 3: StateStasis
# ---------------------------------------------------------------------------


class StateStasis(Guard):
    """Trip when agent state hash does not change across `max_steps` observations.

    Pass a `state_projector` callable to strip volatile fields (timestamps, UUIDs)
    before hashing. Without this, a state containing e.g. a timestamp will never
    trip stasis because the hash changes every step.
    """

    def __init__(
        self,
        max_steps: int,
        state_projector: Callable[[Any], Any] | None = None,
    ):
        if max_steps < 2:
            raise ValueError("max_steps must be >= 2")
        self.max_steps = max_steps
        self.state_projector = state_projector
        self.last_hash: str | None = None
        self.same_count = 0
        self._heuristic_checked = False

    def observe_state(self, state: Any) -> TripReason | None:
        if not self._heuristic_checked:
            self._heuristic_checked = True
            if self.state_projector is None:
                finding = _find_volatile_field(state)
                if finding is not None:
                    logger.warning(
                        "loopbuster.StateStasis: state contains %s — stasis will "
                        "likely never trip because the hash changes every step. "
                        "Pass `state_projector=fn` to filter such fields.",
                        finding,
                    )

        projected = self.state_projector(state) if self.state_projector else state
        h = _stable_hash(projected)
        if h == self.last_hash:
            self.same_count += 1
        else:
            self.same_count = 1
            self.last_hash = h
        if self.same_count >= self.max_steps:
            return TripReason(
                detector="StateStasis",
                message=f"Agent state unchanged for {self.same_count} iterations",
                details={"steps": self.same_count, "state_hash": h},
            )
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_hash(obj: Any) -> str:
    try:
        payload = json.dumps(obj, sort_keys=True, default=str).encode()
    except TypeError:
        payload = repr(obj).encode()
    return hashlib.sha256(payload).hexdigest()


_TIMESTAMP_FIELD_NAMES = frozenset(
    {
        "timestamp", "ts", "time", "now", "date", "datetime",
        "created", "updated", "modified",
    }
)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def _looks_like_unix_timestamp(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    if 1_500_000_000 <= value <= 2_000_000_000:
        return True
    if 1_500_000_000_000 <= value <= 2_000_000_000_000:
        return True
    return False


def _looks_like_unique_string_id(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if _UUID_RE.match(value):
        return True
    if _ISO8601_RE.match(value):
        return True
    return False


def _find_volatile_field(state: Any, path: str = "") -> str | None:
    return _find_volatile_field_bounded(state, path, depth_left=6)


def _find_volatile_field_bounded(
    state: Any, path: str, depth_left: int
) -> str | None:
    if depth_left <= 0:
        return None
    if isinstance(state, dict):
        for k, v in state.items():
            kp = f"{path}.{k}" if path else str(k)
            kl = str(k).lower()
            if kl in _TIMESTAMP_FIELD_NAMES or kl.endswith("_at"):
                return f"key {kp!r} (looks like a timestamp by name)"
            if _looks_like_unix_timestamp(v):
                return f"key {kp!r} = {v!r} (looks like a UNIX timestamp)"
            if _looks_like_unique_string_id(v):
                return f"key {kp!r} = {v!r} (looks like a UUID or ISO datetime)"
            child = _find_volatile_field_bounded(v, kp, depth_left - 1)
            if child is not None:
                return child
        return None
    if isinstance(state, (list, tuple)):
        for i, v in enumerate(state):
            ip = f"{path}[{i}]" if path else f"[{i}]"
            if _looks_like_unix_timestamp(v):
                return f"value at {ip} = {v!r} (looks like a UNIX timestamp)"
            if _looks_like_unique_string_id(v):
                return f"value at {ip} = {v!r} (looks like a UUID or ISO datetime)"
            child = _find_volatile_field_bounded(v, ip, depth_left - 1)
            if child is not None:
                return child
        return None
    if path == "":
        if _looks_like_unix_timestamp(state):
            return f"top-level value {state!r} (looks like a UNIX timestamp)"
        if _looks_like_unique_string_id(state):
            return f"top-level value {state!r} (looks like a UUID or ISO datetime)"
    return None
