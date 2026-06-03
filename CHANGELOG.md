## [0.3.0] - 2026-06-03

### Deep Detection (New)

* **ProgressSignal**: Information-gain tracker that distinguishes **good cycles** (repetition with progress) from **bad cycles** (repetition without progress). Uses token-level overlap, n-gram novelty, and windowed union comparison to compute a per-action novelty score. The key missing piece that separates a toy loop detector from a semantics-aware one.

* **RiskScorer**: Predictive loop risk scoring that warns *before* a full pattern forms. Blends three leading indicators:
  - **Entropy collapse**: tool diversity shrinking over time
  - **State revisitation**: agent circling back to the same (tool, output-fingerprint) states
  - **Progress decay**: information gain per action trending downward
  
  Outputs a composit RiskReport (0.0 safe ~ 1.0 critical) after every action.

* **RootCauseAnalyzer**: When a loop is detected, infers *why* from the action history. Categorizes into 8 root causes (TOOL_STUCK, DATA_STARVED, REASONING_LOOP, OUTPUT_EQUIVALENCE, CYCLE_TRAP, etc.) and generates actionable suggestions.

* **Decision.explain()**: Every Decision now has an `explain(history)` method that returns a LoopExplanation with root cause, detailed analysis, and concrete suggestion.

### Engine Integration

* LoopBuster engine now automatically runs ProgressSignal and RiskScorer on every `check()` call.
* New properties: `lb.risk_score` and `lb.progress_signal` for inline inspection.
* `report()` now includes `risk_score` and `progress_signal` sections.
* `reset()` clears deep detection state.

### Structural Fixes

* **pyproject.toml**: Fixed broken formatting, made redis/fastapi/uvicorn proper optional dependencies instead of hard requirements, added pytest-asyncio for async tests.
* **Storage de-duplication**: Renamed `backends/base.py:RedisBackend` to `AsyncRedisBackend` to resolve naming conflict with `storage/redis.py:RedisBackend`.
* **README**: Complete rewrite to match actual codebase capability. Now documents all features truthfully including deep detection, async, MCP, dashboard, adaptive config, and known limitations.

### Benchmark

* Expanded from 10 to 25 scenarios, including good-cycle-vs-bad-cycle test cases and risk scorer validation.
* New `run_progress_benchmark()` function to quantitatively verify ProgressSignal differentiates progressive from stagnant outputs.

### New Module Exports

```python
from loopbuster import (
    ProgressSignal,    # Information-gain tracking
    ProgressReport,    # Progress signal result
    RiskScorer,        # Predictive risk scorer
    RiskReport,        # Risk scoring result
    RootCauseAnalyzer, # Root cause inference
    RootCause,         # Root cause enum
    LoopExplanation,   # Explainable loop analysis
)
```

## [0.2.1] - 2026-06-02

### Core Changes
* **Dashboard integration**: New `start_dashboard()` interface for real-time monitoring (experimental).
* **Engineering improvements**: Optimized engine.py stability and context management.
* **Honest disclosure**: Acknowledged lack of semantic detection and dashboard test coverage.

## [0.2.0] - 2026-05-???

* Initial public release with 4 detection strategies, circuit breaker, 3 guards, and LangChain integration.
