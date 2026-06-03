# LoopBuster 🛑

> Break the infinite loops of your AI Agents. Stop burning tokens on dead-ends.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

LoopBuster is a **framework-agnostic** anti-dead-loop toolkit for LLM agents. It detects when agents get stuck in repetitive patterns—exact repeats, fuzzy repeats, cycles, output stagnation—and takes action before you burn through your API budget.

## What makes LoopBuster different?

| Feature | What it does |
|---------|-------------|
| **4 detection strategies** | Exact Repeat, Fuzzy Repeat, Cycle Detection, Output Stagnation |
| **Good vs Bad cycle** | ProgressSignal tracks information gain—repetition with progress is OK, repetition without progress is not |
| **Predictive risk scoring** | RiskScorer warns *before* a full pattern forms (entropy collapse, state revisitation, progress decay) |
| **Root cause analysis** | When a loop is detected, RootCauseAnalyzer infers *why* and suggests what to do |
| **3 hard guards** | BudgetCeiling ($$ cap), RepeatCallGuard, StateStasis |
| **Adaptive thresholds** | Tightens when diversity drops, relaxes when exploration is healthy |
| **Circuit breaker** | Pre-flight hard gate against exact (tool, args) repeats |
| **Async support** | AsyncLoopBuster with hung coroutine detection |
| **5 framework integrations** | LangChain, AutoGen, CrewAI, LangGraph, LlamaIndex |
| **MCP server** | Drop-in for MCP-compatible environments |
| **REST API + Dashboard** | FastAPI dashboard with live intercept logs |
| **Distributed state** | Redis backend for multi-process deployments |
| **0 hard dependencies** | Core is pure Python—extras are optional |

## Architecture

```
Agent Action
    ↓
┌─────────────────────────────────────┐
│         LoopBuster Engine           │
│  ┌───────┐ ┌──────────┐ ┌────────┐ │
│  │4 Strat.│ │RiskScorer│ │Guards  │ │
│  │(pattern│ │(predict) │ │(hard   │ │
│  │ match) │ │          │ │limit)  │ │
│  └───┬───┘ └────┬─────┘ └───┬────┘ │
│      └──────────┼────────────┘      │
│                 ↓                   │
│          Decision                    │
└─────────────────────────────────────┘
    ↓         ↓         ↓
  Allow     Warn      Stop/EScalate
```

## Quick Start

```bash
pip install loopbuster
```

```python
from loopbuster import LoopBuster

with LoopBuster(budget_usd=5.0) as lb:
    for step in agent_loop(task):
        decision = lb.check(
            tool=step.tool,
            args=step.args,
            output=step.output,
        )
        if decision.should_stop:
            # React: break, log, ask user
            expl = decision.explain(lb.action_history)
            print(f"🛑 {expl.summary}")
            print(f"💡 {expl.suggestion}")
            break
```

## Detection Strategies

| Strategy | What it detects | False positive rate |
|---|---|---|
| **ExactRepeat** | Identical (tool, args) consecutive calls | Low |
| **FuzzyRepeat** | Near-identical args (Jaccard + edit distance) | Medium |
| **CycleDetection** | A→B→C→A repeating sequences | Low |
| **OutputStagnation** | Tool returns same output repeatedly | Medium |

## Deep Detection (v0.3+)

### ProgressSignal — Good vs Bad Cycles

```python
from loopbuster import ProgressSignal

ps = ProgressSignal(window=5)

# Good cycle: each call produces new information
ps.record("Paris population: 2.1M")
ps.record("Tokyo population: 14M")       # gain ≈ 0.85 (new info)
ps.record("London population: 8.9M")      # gain ≈ 0.85

# Bad cycle: same output repeatedly
ps.record("Paris population: 2.1M")
ps.record("Paris population: 2.1M")       # gain < 0.1 (stagnation)
ps.record("Paris population: 2.1M")       # gain ≈ 0.0
```

### RiskScorer — Predictive Warning

```python
from loopbuster import LoopBuster, Action

lb = LoopBuster()
for step in agent_loop:
    decision = lb.check(step.tool, step.args, step.output)

    # Check risk BEFORE any strategy fires
    risk = lb.risk_score
    if risk and risk.is_warning:
        print(f"⚠️ {risk.summary}")
        # entropy=0.8 → tool set collapsing
        # revisitation=0.7 → revisiting same states
```

### RootCauseAnalyzer — Why it happened

```python
decision = lb.check(tool="search", args={"q": "python"})
if decision.is_loop:
    expl = decision.explain(lb.action_history)
    # expl.root_cause_label = "Exact Tool Repeat"
    # expl.suggestion = "Consider adding a termination condition..."
    print(f"🔍 {expl.detail}")
    print(f"💡 {expl.suggestion}")
```

### Decision.explain()

Every `Decision` now has an `explain()` method:

```python
if decision.is_loop:
    expl = decision.explain(lb.action_history)
    print(expl.summary)       # High-level summary
    print(expl.detail)        # Detailed analysis
    print(expl.suggestion)    # Actionable next step
    print(expl.root_cause)    # RootCause enum
```

## Guards (Hard Limits)

Three guards complement pattern detection with hard boundaries:

| Guard | Trigger |
|---|---|
| **BudgetCeiling** | Cumulative LLM API spend exceeds `$limit` |
| **RepeatCallGuard** | Same (tool, args) appears N times in a window |
| **StateStasis** | Agent state unchanged for N consecutive steps |

```python
lb = LoopBuster(
    budget_usd=5.0,       # BudgetCeiling
    max_repeats=3,        # RepeatCallGuard
    stasis_steps=5,       # StateStasis
)
```

## Adaptive Thresholds

Instead of fixed WARN/STOP/ESCALATE counts, `AdaptiveActionConfig` adjusts thresholds in real time based on action diversity:

```python
from loopbuster import AdaptiveActionConfig, LoopBuster

config = AdaptiveActionConfig(
    base_warn=3, base_stop=5, base_escalate=8,
)
with LoopBuster(action_config=config) as lb:
    ...
```

- Low diversity (agent stuck on 2-3 tools) → thresholds tighten (faster intervention)
- High diversity (agent exploring many tools) → thresholds relax (fewer false positives)

## Framework Integrations

### LangChain

```python
from loopbuster import LoopBuster
from loopbuster.integrations.langchain import LoopBusterCallback

lb = LoopBuster(budget_usd=5.0)
callback = LoopBusterCallback(lb)
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent, tools=tools, callbacks=[callback],
)
```

### LlamaIndex

```python
from loopbuster import LoopBuster
from loopbuster.integrations.llamaindex import LoopBusterCallback

lb = LoopBuster(budget_usd=5.0)
callback = LoopBusterCallback(lb)
from llama_index.core import Settings
Settings.callback_manager.add_handler(callback)
```

### Generic

```python
from loopbuster.integrations import LoopBusterCallback

callback = LoopBusterCallback(on_stop=lambda d: raise StopException(d))
for action in agent_loop:
    decision = callback.before_tool_call(action.tool, action.args)
    if not decision.should_stop:
        result = execute_tool(action.tool, action.args)
```

## Async Support

```python
from loopbuster import AsyncLoopBuster

async with AsyncLoopBuster(budget_usd=5.0) as lb:
    async for step in agent_async_loop():
        decision = await lb.acheck(tool=step.tool, args=step.args)
        if decision.should_stop:
            break
```

Hung coroutine detection:

```python
async with AsyncLoopBuster(action_timeout=30.0, max_slow_actions=3) as lb:
    # If an action takes >30s, it's flagged as hung
    # After 3 consecutive hangs → ESCALATE
    ...
```

## Decorator

```python
from loopbuster import buster

@buster(budget_usd=5.0, max_repeats=3)
def run_my_agent(task):
    from loopbuster import current
    for step in agent_loop(task):
        decision = current().check(tool=step.tool, args=step.args)
        if decision.should_stop:
            break
```

## MCP Server

```bash
python -m loopbuster.mcp_server
```

## REST API + Dashboard

```python
from loopbuster import LoopBuster

lb = LoopBuster()
# ... run agent ...
lb.start_dashboard(port=8080)
```

Or standalone:

```bash
pip install loopbuster[dashboard]
# Requires REDIS_URL env var for persistence
uvicorn loopbuster.api.server:app --port 8000
```

## Stuck Report

```python
with LoopBuster(budget_usd=5.0) as lb:
    for step in agent_loop():
        lb.check(tool=step.tool, args=step.args)

report = lb.report()
print(report["risk_score"]["summary"])
print(report["recommendations"])
```

## CLI Benchmark

```bash
python benchmark/scenarios.py
```

## Design Decisions

- **Strategy pattern**: Each detection algorithm is an independent class. Users compose their own.
- **Zero core dependencies**: The detection engine is pure Python. Optional features bring their own deps.
- **ContextVar for context**: Thread-safe, async-safe, no leaky global state.
- **Decision object**: The engine detects; the caller decides how to react.
- **Deep detection as opt-in**: ProgressSignal and RiskScorer add no overhead if you don't use them directly—they're always running, but you choose whether to inspect the output.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT
