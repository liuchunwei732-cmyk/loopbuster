## v0.3.0 Deep Detection — ProgressSignal, RiskScorer, RootCauseAnalyzer

This release adds a **semantic understanding layer** that goes beyond pattern matching to distinguish *good cycles* (repetition with progress) from *bad cycles* (repetition without progress), predict loops before they fully form, and explain why they happened.

### New Modules

**ProgressSignal** — Information-gain tracker that measures whether each agent action produces genuinely new content. Three-factor scoring: token-level overlap, n-gram novelty, and windowed union comparison. Enables good-cycle vs bad-cycle differentiation.

**RiskScorer** — Predictive loop risk scoring that warns *before* a full pattern forms. Blends three leading indicators: entropy collapse (tool diversity shrinking), state revisitation (agent circling back to same states), and progress decay (information gain trending downward).

**RootCauseAnalyzer** — When a loop is detected, infers *why* from the action history. Categorizes into 8 root causes (TOOL_STUCK, DATA_STARVED, REASONING_LOOP, OUTPUT_EQUIVALENCE, CYCLE_TRAP, etc.) and generates actionable suggestions.

**Decision.explain()** — Every Decision now has an explain(history) method returning a LoopExplanation with root cause, detailed analysis, and concrete suggestion.

### Engine Integration

- LoopBuster engine now auto-runs ProgressSignal and RiskScorer on every check() call
- New properties: lb.risk_score and lb.progress_signal
- eport() now includes isk_score and progress_signal sections

### Structural Fixes

- **pyproject.toml**: Fixed broken formatting, made redis/fastapi/uvicorn proper optional dependencies
- **Storage de-duplication**: Renamed ackends/base.py:RedisBackend to AsyncRedisBackend resolving naming conflict
- **README**: Complete rewrite to match actual codebase capability (was severely outdated)

### Benchmark

- Expanded from 10 to 25 scenarios including good/bad cycle differentiation tests
- New un_progress_benchmark() for quantitative ProgressSignal validation

### Stats

14 files changed, 1844 insertions(+), 124 deletions(-)
