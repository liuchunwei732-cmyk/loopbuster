"""LoopBuster — A unified anti-dead-loop toolkit for LLM agents.

Combines pattern-based loop detection, budget ceilings, state stasis guards,
and circuit breakers into a single, easy-to-use library.

Core components:
    - LoopBuster:    Main engine (context manager)
    - @buster:       Decorator form
    - CircuitBreaker: Pre-flight gate for tool calls

Detection strategies (4):
    - Exact Repeat:    Same (tool, args) repeated identically
    - Fuzzy Repeat:    Near-identical args via similarity scoring
    - Cycle Detection: A→B→C→A→B→C repeating sequences
    - Output Stagnation: Tool returns the same output repeatedly

Hard guards (3):
    - BudgetCeiling:    Dollar cap on LLM API spend
    - RepeatCallGuard:  Hard limit on exact (tool, args) repeats
    - StateStasis:      Agent state hasn't changed for N steps
"""

from __future__ import annotations

from . import integrations
from .async_engine import AsyncLoopBuster
from .circuit import BreakerAction, BreakerDecision, CircuitBreaker
from .decorator import buster
from .engine import LoopBuster, current
from .explain import LoopExplanation, RootCause, RootCauseAnalyzer
from .guards import BudgetCeiling, Guard, RepeatCallGuard, StateStasis
from .progress import ProgressReport, ProgressSignal
from .risk import RiskReport, RiskScorer
from .similarity import args_similarity
from .similarity_backend import (
    BACKENDS,
    DefaultSimilarityBackend,
    EmbeddingSimilarityBackend,
    SimilarityBackend,
    get_backend,
)
from .strategies import (
    CompositeStrategy,
    CycleDetectionStrategy,
    ExactRepeatStrategy,
    FuzzyRepeatStrategy,
    OutputStagnationStrategy,
)
from .types import (
    Action,
    ActionConfig,
    AdaptiveActionConfig,
    Decision,
    TripError,
    TripReason,
)

__version__ = "0.3.0"

__all__ = [
    # Main API
    "LoopBuster",
    "AsyncLoopBuster",
    "buster",
    "current",
    # Detection strategies
    "CompositeStrategy",
    "ExactRepeatStrategy",
    "FuzzyRepeatStrategy",
    "CycleDetectionStrategy",
    "OutputStagnationStrategy",
    # Similarity
    "args_similarity",
    # Guards
    "Guard",
    "BudgetCeiling",
    "RepeatCallGuard",
    "StateStasis",
    # Circuit breaker
    "CircuitBreaker",
    "BreakerAction",
    "BreakerDecision",
    # Deep detection
    "ProgressSignal",
    "ProgressReport",
    "RiskScorer",
    "RiskReport",
    "RootCauseAnalyzer",
    "RootCause",
    "LoopExplanation",
    # Types
    "Action",
    "ActionConfig",
    "AdaptiveActionConfig",
    "Decision",
    "TripError",
    "TripReason",
    # Integrations
    "integrations",
]
