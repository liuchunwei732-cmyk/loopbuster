# LoopBuster

> A unified anti-dead-loop toolkit for LLM agents — loop detection, budget ceiling, state stasis guard, and circuit breaker in one library.

```python
from loopbuster import LoopBuster

# One context manager, four layers of protection
with LoopBuster(budget_usd=5.0, max_repeats=3) as lb:
    for step in my_agent_loop():
        decision = lb.check(tool=step.tool, args=step.args)
        if decision.should_stop:
            print(f"Loop detected: {decision.reason}")
            break
```

---

## Why LoopBuster?

LLM agents get stuck in loops **all the time**. The symptoms are always the same:

- The same tool gets called with the same arguments, over and over
- The agent cycles through A→B→C→A→B→C without making progress
- The output never changes, but the token counter keeps climbing
- You wake up to a $500 API bill from an overnight runaway agent

Existing solutions are fragmented: one library detects cycles, another enforces budgets, a third has circuit breakers. **LoopBuster combines all three** into a single, coherent API — inspired by the best ideas from the ecosystem.

**What LoopBuster gives you that alternatives don't:**

| Feature | LoopBuster | agent-loop-guard | magicrails | agent-guard-mcp |
|---------|:----------:|:----------------:|:----------:|:----------------:|
| Pattern detection (4 strategies) | ✅ | ✅ | ❌ | ❌ |
| Budget ceiling | ✅ | ❌ | ✅ | ❌ |
| State stasis guard | ✅ | ❌ | ✅ | ❌ |
| Circuit breaker (pre-flight) | ✅ | ❌ | ❌ | ✅ |
| Decorator `@buster` | ✅ | ❌ | ✅ | ❌ |
| Context manager | ✅ | ❌ | ✅ | ❌ |
| Framework-agnostic | ✅ | ✅ | ❌ | ❌ (MCP) |
| Callback integration | ✅ | ✅ | ❌ | ❌ |
| Zero dependencies | ✅ | ✅ | ❌ | ✅ (Node) |

---

## Quick Start

### Install

```bash
pip install loopbuster
```

### Pattern Detection (standalone)

```python
from loopbuster import LoopBuster

guard = LoopBuster()

for action in agent_actions:
    decision = guard.check(
        tool=action.name,
        args=action.args,
        output=action.output,  # enables stagnation detection
    )
    if decision.is_loop:
        print(f"🛑 Stopped: {decision.reason}")
        break
    if decision.should_warn:
        print(f"⚠️ Warning: {decision.reason}")
```

### Full Protection (context manager)

```python
from loopbuster import LoopBuster

with LoopBuster(budget_usd=5.0, max_repeats=3) as lb:
    for step in my_agent_loop(task):
        # Pattern detection
        decision = lb.check(tool=step.tool, args=step.args)

        # Budget tracking
        lb.record_tokens(model="gpt-4o", input=100, output=50)

        # Guard monitoring
        lb.record_call(name=step.tool, args=step.args)

        if decision.should_stop:
            print(f"🛑 {decision.reason}")
            break
```

### Decorator

```python
from loopbuster import buster

@buster(budget_usd=10.0, max_repeats=3)
def run_my_agent(task: str):
    # Access the current session:
    from loopbuster import current
    lb = current()
    # ... your agent loop ...
    return result
```

### Circuit Breaker (pre-flight check)

```python
from loopbuster import CircuitBreaker, BreakerAction

breaker = CircuitBreaker(max_repeats=3, action=BreakerAction.BLOCK)

for step in agent_loop:
    # Check before calling
    decision = breaker.check(step.tool, step.args)
    if not decision.proceed:
        print(f"⛔ {decision.reason}")
        print(f"💡 {decision.alternative_suggestion}")
        # Try something else...
        continue

    # Execute the tool
    result = call_tool(step.tool, step.args)
```

---

## Detection Strategies

LoopBuster runs four detection strategies on every action, picking the strongest signal:

| Strategy | What it catches | Example |
|----------|----------------|---------|
| **Exact Repeat** | Same (tool, args) repeated identically | `search("cat")` → `search("cat")` → `search("cat")` |
| **Fuzzy Repeat** | Near-identical args (Jaccard + edit distance) | `search("python error")` → `search("python bug")` → `search("python issue")` |
| **Cycle Detection** | A→B→C→A→B→C repeating sequences | `search → parse → search → parse → search → parse` |
| **Output Stagnation** | Tool returns the same output repeatedly | `search()` returns same 3 links each time |

All four run in parallel; the highest confidence wins.

---

## Decision Escalation

Consecutive detections escalate automatically:

| Consecutive hits | Action | Meaning |
|:----------------:|:------:|---------|
| 0–1 | ALLOW | Everything normal |
| 2–3 | WARN | Suspicious pattern — log it |
| 4–5 | STOP | Stop the agent |
| 6+ | ESCALATE | Emergency — human intervention needed |

Configure thresholds via `ActionConfig`:

```python
from loopbuster import ActionConfig, LoopBuster

config = ActionConfig(
    warn_threshold=3,      # ⚠️ after 3 consecutive hits
    stop_threshold=5,      # 🛑 after 5
    escalate_threshold=8,  # 🚨 after 8
)

lb = LoopBuster(action_config=config)
```

---

## Hard Guards

### BudgetCeiling — dollar cap on LLM API spend

```python
with LoopBuster(budget_usd=5.0) as lb:
    # Auto-instrumented or manual:
    lb.record_tokens(model="claude-sonnet-4", input=500, output=200)
```

Includes a 100+ model pricing table (OpenAI, Anthropic, DeepSeek, Google, Meta, Mistral).

### RepeatCallGuard — hard limit on exact (tool, args) repeats

```python
with LoopBuster(max_repeats=3) as lb:
    # Trips if the exact same (tool, args) appears 3+ times
    ...
```

### StateStasis — detect when agent state hasn't changed

```python
with LoopBuster(stasis_steps=5) as lb:
    # Records state after each step:
    lb.record_state(agent_state)

    # StateStasis auto-detects volatile fields (timestamps, UUIDs)
    # and warns if state_projector is needed.
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Loop                               │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐              │
│  │ T1  │→│ T2  │→│ T3  │→│ T2  │→│ T2  │→ ...              │
│  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘              │
│     │        │        │        │        │                   │
└─────┼────────┼────────┼────────┼────────┼───────────────────┘
      │        │        │        │        │
      ▼        ▼        ▼        ▼        ▼
┌─────────────────────────────────────────────────────────────┐
│                     LoopBuster                              │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Strategies  │  │    Guards    │  │ Circuit Breaker   │  │
│  │              │  │              │  │                   │  │
│  │ • Exact      │  │ • Budget     │  │ • Pre-flight      │  │
│  │ • Fuzzy      │  │ • Repeats    │  │ • Block/Warn      │  │
│  │ • Cycle      │  │ • Stasis     │  │ • Suggestion      │  │
│  │ • Stagnation │  │              │  │                   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘  │
│         │                 │                    │             │
│         ▼                 ▼                    ▼             │
│  ┌──────────────────────────────────────────────────┐       │
│  │           Decision → ALLOW / WARN / STOP / ESCALATE│       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## Integrations

### Generic callback (any framework)

```python
from loopbuster.integrations import LoopBusterCallback

callback = LoopBusterCallback(
    on_warn=lambda d: logger.warning(f"Loop warning: {d.reason}"),
    on_stop=lambda d: raise StopIteration(d),
)

for action in agent_loop:
    decision = callback.before_tool_call(action.tool, action.args)
    if decision.should_stop:
        break
```

---

## Why not just `max_iter`?

| Approach | What it catches | Limitation |
|----------|----------------|------------|
| `max_iter=10` | Runaway agents | Kills long *legitimate* tasks; misses 3-step loops at step 9 |
| **LoopBuster** | Exact repeats, fuzzy repeats, A→B→C→A cycles, output stagnation | — |

`max_iter` is a blunt timeout. LoopBuster detects *behavioral patterns* — the agent doing the same thing over and over, even with slight variations.

---

## License

MIT
