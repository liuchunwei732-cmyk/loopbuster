"""RootCauseAnalyzer — infer why an agent entered a loop and what to do next.

The goal is not just to say "you're in a loop" but to explain:

  1. **What pattern** was detected (which strategy, which tools)
  2. **Why it happened** (root cause category)
  3. **What to try instead** (actionable suggestion)

Root causes are inferred heuristically from the action history and
the decision that was triggered. The analyzer classifies loops into
several common categories:

  - TOOL_STUCK:   Agent keeps calling the same tool with similar args
  - DATA_STARVED: Agent keeps fetching data but doesn't know when to stop
  - REASONING_LOOP: Agent re-evaluates the same premise repeatedly
  - OUTPUT_EQUIVALENCE: Tool returns same results → agent can't progress
  - CYCLE_TRAP:   Agent entered a predictable A→B→C→A sequence
  - BUDGET_HIT:   Guard tripped due to cost ceiling

Usage:
    from loopbuster.explain import RootCauseAnalyzer
    analyzer = RootCauseAnalyzer()
    explanation = analyzer.explain(decision, action_history)
    print(explanation.root_cause)     # "DATA_STARVED"
    print(explanation.suggestion)     # "Try narrowing the search query"
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from loopbuster.progress import token_overlap
from loopbuster.types import Action, ActionRecord, Decision


class RootCause(Enum):
    UNKNOWN = auto()
    TOOL_STUCK = auto()
    DATA_STARVED = auto()
    REASONING_LOOP = auto()
    OUTPUT_EQUIVALENCE = auto()
    CYCLE_TRAP = auto()
    BUDGET_HIT = auto()
    STATE_STASIS = auto()
    EXACT_REPEAT = auto()
    FUZZY_REPEAT = auto()


@dataclass
class LoopExplanation:
    """Human-readable explanation of a detected loop."""

    root_cause: RootCause
    root_cause_label: str
    summary: str
    detail: str
    suggestion: str
    confidence: float  # 0.0 ~ 1.0 in how confident we are about the root cause


class RootCauseAnalyzer:
    """Analyze action history to infer why a loop happened."""

    def explain(
        self,
        decision: Decision,
        history: list[ActionRecord],
    ) -> LoopExplanation:
        """Generate a root-cause explanation for a detected loop.

        Args:
            decision: The Decision that flagged the loop.
            history: Full action history from the LoopBuster session.

        Returns:
            A LoopExplanation with root cause, summary, and suggestion.
        """
        if not history:
            return LoopExplanation(
                root_cause=RootCause.UNKNOWN,
                root_cause_label="Unknown",
                summary="No action history available.",
                detail="Cannot analyze without action records.",
                suggestion="Ensure the agent has executed at least one action.",
                confidence=0.0,
            )

        return self._infer(decision, history)

    def _infer(
        self, decision: Decision, history: list[ActionRecord]
    ) -> LoopExplanation:
        """Match the situation to a root cause category."""
        recent = history[-20:] if len(history) > 20 else history

        # --- Pattern matching based on strategy and data ---
        strategy = decision.strategy
        last_record = history[-1] if history else None

        # 1. Exact repeat → check if it's TOOL_STUCK or EXACT_REPEAT
        if strategy == "exact_repeat":
            if last_record:
                count = sum(
                    1
                    for r in recent
                    if r.tool == last_record.tool and r.args == last_record.args
                )
                return self._make_explanation(
                    root_cause=RootCause.EXACT_REPEAT,
                    label="Exact Tool Repeat",
                    summary=(
                        f"Agent called '{last_record.tool}' with identical "
                        f"arguments {count} times."
                    ),
                    detail=(
                        f"The most likely cause is that the agent's prompt does not "
                        f"specify when to stop searching, or the tool itself returns "
                        f"data that doesn't change the agent's internal state."
                    ),
                    suggestion=(
                        f"Consider adding a termination condition to the agent's prompt, "
                        f"or modifying '{last_record.tool}' to return a richer result."
                    ),
                    confidence=0.9,
                )
            return self._fallback(decision)

        # 2. Fuzzy repeat → TOOL_STUCK with slight arg variation
        if strategy == "fuzzy_repeat":
            if last_record:
                return self._make_explanation(
                    root_cause=RootCause.TOOL_STUCK,
                    label="Stuck on a Tool",
                    summary=(
                        f"Agent keeps calling '{last_record.tool}' with slightly "
                        f"different parameters but the same intent."
                    ),
                    detail=(
                        "The agent appears to believe it needs more data from this "
                        "tool, but tweaking parameters isn't producing new insights. "
                        "This often happens when the agent lacks a clear decision "
                        "criterion for when it has enough information."
                    ),
                    suggestion=(
                        f"Try giving the agent a checklist: 'After you have X, stop "
                        f"searching and move to the next step.'"
                    ),
                    confidence=0.8,
                )
            return self._fallback(decision)

        # 3. Cycle detection → CYCLE_TRAP
        if strategy == "cycle_detection":
            return self._make_explanation(
                root_cause=RootCause.CYCLE_TRAP,
                label="Action Cycle Trap",
                summary=(
                    f"Agent entered a repeating sequence of tools: "
                    f"{decision.reason}"
                ),
                detail=(
                    "The agent has learned a stable loop of tool calls that keeps "
                    "it busy without making progress. This pattern is common when "
                    "the output of tool A is exactly what tool B expects, and B's "
                    "output triggers A again."
                ),
                suggestion=(
                    "Break the cycle by adding a state variable that tracks whether "
                    "each tool in the sequence has already been called, and skip "
                    "if no new information would be gained."
                ),
                confidence=0.85,
            )

        # 4. Output stagnation → OUTPUT_EQUIVALENCE or DATA_STARVED
        if strategy == "output_stagnation":
            if last_record and last_record.output:
                # Check if output contains data-like content (numbers, lists)
                has_data = any(
                    c.isdigit() for c in last_record.output
                ) or "[" in last_record.output
                if has_data:
                    return self._make_explanation(
                        root_cause=RootCause.OUTPUT_EQUIVALENCE,
                        label="Output Unchanged",
                        summary=(
                            f"Tool '{last_record.tool}' keeps returning the "
                            f"same data."
                        ),
                        detail=(
                            "The tool is returning the same or nearly identical "
                            "output each time. This could mean the input parameters "
                            "don't meaningfully change the result, or the underlying "
                            "data source hasn't been updated."
                        ),
                        suggestion=(
                            "Consider caching the tool result and only calling it "
                            "again with different parameters. If the data source is "
                            "static, the agent should be told it already has the answer."
                        ),
                        confidence=0.85,
                    )
                return self._make_explanation(
                    root_cause=RootCause.DATA_STARVED,
                    label="Data-Starved Agent",
                    summary=(
                        f"Agent keeps requesting data but making no progress."
                    ),
                    detail=(
                        "The output is text-heavy but doesn't contain actionable data. "
                        "The agent may be searching for something that doesn't exist, "
                        "or the search space is too broad."
                    ),
                    suggestion=(
                        "Narrow down the search query or provide the agent with a "
                        "fallback plan for when data is unavailable."
                    ),
                    confidence=0.75,
                )
            return self._fallback(decision)

        # 5. Hung coroutine (async)
        if strategy == "hung_coroutine":
            return self._make_explanation(
                root_cause=RootCause.REASONING_LOOP,
                label="Hung Coroutine / Reasoning Loop",
                summary="Agent action timed out — likely stuck in reasoning.",
                detail=(
                    "The LLM is taking too long to respond, possibly because it's "
                    "trapped in an internal reasoning loop or waiting on an external "
                    "resource that isn't responding."
                ),
                suggestion=(
                    "Increase the timeout, or add a 'max reasoning steps' constraint "
                    "to the LLM call. If the issue persists, check the external "
                    "service the agent is trying to reach."
                ),
                confidence=0.7,
            )

        # Fallback: infer from action diversity
        return self._fallback(decision)

    def _fallback(self, decision: Decision) -> LoopExplanation:
        """Generic explanation when no specific pattern matches."""
        return self._make_explanation(
            root_cause=RootCause.UNKNOWN,
            label="Uncategorized Loop",
            summary=f"Loop detected via {decision.strategy}: {decision.reason}",
            detail=(
                "The specific root cause could not be determined from the "
                "available action history. Consider enabling verbose mode or "
                "adding custom guards for more targeted detection."
            ),
            suggestion=(
                "Try adjusting the similarity threshold or window size. "
                "If loops are frequent, consider adding a BudgetCeiling guard "
                "to limit cost regardless of detection accuracy."
            ),
            confidence=0.5,
        )

    def _make_explanation(
        self,
        root_cause: RootCause,
        label: str,
        summary: str,
        detail: str,
        suggestion: str,
        confidence: float,
    ) -> LoopExplanation:
        return LoopExplanation(
            root_cause=root_cause,
            root_cause_label=label,
            summary=summary,
            detail=detail,
            suggestion=suggestion,
            confidence=confidence,
        )


