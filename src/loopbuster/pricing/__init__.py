"""Pricing utilities for estimating LLM API costs."""

from __future__ import annotations

from loopbuster.pricing.models import PRICING as _DEFAULT_PRICING

_UNKNOWN_MODEL_COST = {"input": 3.00, "output": 15.00}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing: dict | None = None,
) -> float:
    """Estimate the USD cost of a token usage event.

    Falls back to a conservative default for unknown models.
    """
    table = pricing if pricing is not None else _DEFAULT_PRICING
    rates = table.get(model, _UNKNOWN_MODEL_COST)
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    return input_cost + output_cost


def load_default_pricing() -> dict:
    """Return a copy of the default pricing table."""
    return dict(_DEFAULT_PRICING)
