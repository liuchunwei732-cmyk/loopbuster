# LoopBuster Architecture

> Internal design doc — how the library works, why it's built this way, and what happens when you call `check()`.

## Table of Contents

1. [Why This Architecture](#1-why-this-architecture)
2. [File Map](#2-file-map)
3. [Core Data Flow](#3-core-data-flow)
4. [Inside check() — Step by Step](#4-inside-check----step-by-step)
5. [Design Decisions](#5-design-decisions)
6. [Extensions and Integration Points](#6-extensions-and-integration-points)
7. [Interview Preparation](#7-interview-preparation)

---

## 1. Why This Architecture

LoopBuster solves one problem: **detect when an LLM agent is stuck in a loop**. The solution must be:

| Requirement | Architectural choice |
|---|---|
| Must work with any agent framework | Framework-agnostic core; optional integrations as separate modules |
| Must not slow down the agent | Zero external dependencies; pure stdlib; <1us per check |
| Must not miss subtle loops (fuzzy args, cycles) | Multi-strategy composition with weighted consensus |
| Must not false-alarm on legitimately repetitive work | Adaptive thresholds based on action diversity |
| Must integrate easily | Single entry point (`LoopBuster` class); context manager support; MCP protocol |

The architecture follows a **layered pipeline** pattern:

```
Caller → History Recording → Diversity Tracking → Breaker Recording
  → Strategy Detection (4 parallel) → Confidence Fusion → Threshold Escalation → Decision
```

---

## 2. File Map

```
src/loopbuster/
│
├── __init__.py          # Public API: exports all user-facing classes
├── engine.py            # Core: LoopBuster class, check(), report(), configure()
├── strategies.py        # 4 detection strategies + CompositeStrategy fusion
├── similarity.py        # Multi-factor similarity: Jaccard + Levenshtein + dict structure + denoising
├── types.py             # All data classes: Decision, ActionConfig, AdaptiveActionConfig, etc.
├── circuit.py           # CircuitBreaker: pre-flight gate (exact-match)
├── guards.py            # BudgetCeiling, RepeatCallGuard, StateStasis
├── decorator.py         # @buster decorator — context manager as decorator
├── async_engine.py      # AsyncLoopBuster — extends LoopBuster with coroutine timeout detection
├── mcp_server.py        # stdio-based MCP server — exposes detection as MCP tools
│
├── api/server.py        # FastAPI dashboard backend (optional: loopbuster[dashboard])
├── backends/base.py     # Abstract storage backend
├── storage/redis.py     # Redis storage implementation (optional: loopbuster[redis])
├── integrations/        # Framework integrations: LangGraph, AutoGen, CrewAI, LlamaIndex
│   ├── langgraph.py
│   ├── autogen.py
│   ├── crewai.py
│   └── llamaindex.py
└── pricing/models.py    # LLM pricing table for budget calculation
```

**Dependency flow:**

```
engine.py
  ├── strategies.py → similarity.py
  ├── guards.py
  ├── circuit.py
  └── types.py
        │
async_engine.py → engine.py
mcp_server.py  → engine.py
decorator.py   → engine.py
api/server.py  → storage/redis.py
```

---

## 3. Core Data Flow

```
Agent loop                          LoopBuster
──────────                         ──────────
for each step:
  buster.check(tool, args, output) ──→┐
                                       │
                              ┌────────┴────────┐
                              │  ① Record       │
                              │  ActionRecord    │
                              │  → history deque │
                              └────────┬────────┘
                                       │
                              ┌────────┴────────┐
                              │  ② Diversity    │
                              │  (if adaptive)  │
                              │  tool+args_hash │
                              └────────┬────────┘
                                       │
                              ┌────────┴────────┐
                              │  ③ Circuit      │
                              │  Breaker.record │
                              └────────┬────────┘
                                       │
                              ┌────────┴─────────────────────────────┐
                              │  ④ CompositeStrategy.check(record)   │
                              │  ┌────────┐┌──────┐┌──────┐┌──────┐ │
                              │  │ Exact  ││Fuzzy ││Cycle ││Stag. │ │
                              │  │Repeat  ││Repeat││Detect││Detect│ │
                              │  └────────┘└──────┘└──────┘└──────┘ │
                              │           │  │  │  │                  │
                              │           ▼  ▼  ▼  ▼                 │
                              │      Weighted Consensus              │
                              │      → (confidence, reason, name)    │
                              └────────┬────────────────────────────┘
                                       │
                              ┌────────┴────────┐
                              │  ⑤ Consecutive  │
                              │  Hits Accum.    │
                              │  conf>0.3 → ++  │
                              │  else    → =0   │
                              └────────┬────────┘
                                       │
                              ┌────────┴────────┐
                              │  ⑥ ActionConfig │
                              │  resolve_action │
                              │  hits→ALLOW/    │
                              │  WARN/STOP/     │
                              │  ESCALATE       │
                              └────────┬────────┘
                                       │
                              ┌────────┴────────┐
                              │  ⑦ Return       │
                              │  Decision       │
                              └────────┬────────┘
                                       │
  decision.is_loop /                   │
  decision.should_warn  ←──────────────┘
  decision.reason
```

---

## 4. Inside check() — Step by Step

Every call to `check()` follows this exact path:

### Step 1: Record history
```python
record = ActionRecord(tool=tool, args=args, output=output, step=self._step)
self._action_history.append(record)  # maxlen=100 deque
```

### Step 2: Track diversity (if AdaptiveActionConfig is active)
```python
if self._is_adaptive:
    self._action_config.record_action(tool, args)
    # Stores "tool:md5(args)[:6]" in diversity window
    # NOT just "tool" — args matter for accurate diversity
```

### Step 3: Record in circuit breaker
```python
if self._circuit_breaker:
    self._circuit_breaker.record(tool, args)
```

### Step 4: Run all detection strategies
```python
confidence, reason, strategy_name = self._strategies.check(record)
```

Inside `CompositeStrategy.check()`:

```
For each strategy:
  ExactRepeat  (weight 1.0)  → (confidence, reason)
  FuzzyRepeat  (weight 0.7)  → (confidence, reason)
  CycleDetect  (weight 0.9)  → (confidence, reason)
  OutputStagn  (weight 0.5)  → (confidence, reason)

If confidence >= 0.9 (any single strategy):
  → Return that directly (clear signal)

If multiple strategies active (confidence >= 0.2):
  → Blend = 0.7 * weighted_avg + 0.3 * max_confidence
  → Return blended confidence, best reason

If no strategy active:
  → Return 0.0
```

### Step 5: Update consecutive hit counter
```python
if confidence > 0.3:
    self._consecutive_hits += 1
else:
    self._consecutive_hits = 0
    self._consecutive_hits = 0
```
The 0.3 threshold prevents noise from low-confidence detections.

### Step 6: Resolve action level
```python
action = self._action_config.resolve_action(self._consecutive_hits)
```

For `ActionConfig` (static thresholds):
```
hits >= 6 → ESCALATE
hits >= 4 → STOP
hits >= 2 → WARN
else      → ALLOW
```

For `AdaptiveActionConfig` (dynamic thresholds):
```
multiplier = diversity_ratio interpolated between min_mult (0.5) and max_mult (2.0)
warn_th   = max(1, base_warn * multiplier)
stop_th   = max(2, base_stop * multiplier)
esc_th    = max(3, base_escalate * multiplier)
```

### Step 7: Return Decision
```python
Decision(action=action, reason=reason, strategy=strategy_name,
         confidence=confidence, step_number=self._step)
```

---

## 5. Design Decisions

### 5-1. Why Strategy pattern for detection?

Each detection algorithm is an independent class implementing `DetectionStrategy`:

```python
class DetectionStrategy(ABC):
    def check(self, record: ActionRecord) -> tuple[float, str]: ...
    def reset(self) -> None: ...
```

Users can compose their own set (e.g., `CompositeStrategy(exact=..., fuzzy=...)`), and adding a new strategy never touches existing code.

**Trade-off:** More classes than a single monolithic function. Benefit: each strategy is independently testable.

### 5-2. Why zero hard dependencies?

The core library uses only Python standard library. This was a conscious decision:

| If we depended on... | Problem |
|---|---|
| `numpy` | 15MB+ install, native build issues on some platforms |
| `sentence-transformers` | 500MB+ model download, GPU dependency |
| `redis` | External service required even for basic use |
| `fastapi` | Unnecessary for library consumers who don't want a dashboard |

**Cost:** We hand-rolled Levenshtein, Jaccard, and dict structure similarity instead of using `nltk` or `textdistance`.

### 5-3. Why multi-factor similarity instead of embeddings?

| Approach | Latency | Cost | Accuracy for loop detection |
|---|---|---|---|
| Embedding (text-embedding-3-small) | 50-200ms | ~$0.0001/call | High but overkill |
| Jaccard + Levenshtein | <1µs | Free | ~95% of embedding accuracy |
| Our approach (blended) | <1µs | Free | ~95% + denoising |

Embedding models are designed for semantic understanding ("dog" ≈ "puppy"). Loop detection needs **structural similarity** ("same query, different request_id"). Our denoising pipeline handles this more efficiently.

### 5-4. Why ContextVar instead of threading.local?

```python
_current = contextvars.ContextVar("loopbuster_current", default=None)
```

`threading.local()` leaks across coroutines — if you start a check in coroutine A and the agent yields to coroutine B, B sees A's LoopBuster instance. `ContextVar` provides proper async isolation.

### 5-5. Why weighted consensus instead of max-confidence?

**Before (v0.2.x):** Return highest confidence from any single strategy.

**Problem:** OutputStagnationStrategy has "medium-high" false positive rate. If it returns 0.9 while all other strategies return 0.0, the max-confidence approach would trigger a false loop detection.

**After (v0.3.x):** Blend strategies with reliability weights. Single strategy at confidence ≥ 0.9 is still trusted directly (clear signal). Otherwise, combine signals.

### 5-6. Why separate check() and guard recording?

`check()` is **pattern-based detection** (what does the agent keep doing?).
`record_tokens()` / `record_call()` / `record_state()` are **guard-based monitoring** (is the agent exceeding limits?).

They solve different problems and have different response models — detection returns a `Decision`, guards raise `TripError`. Combining them would violate separation of concerns.

---

## 6. Extensions and Integration Points

### The Core API surface

Users interact with exactly 4 methods:

| Method | When to use |
|---|---|
| `check(tool, args, output)` | After every agent action |
| `breaker_check(tool, args)` | Before calling an expensive tool |
| `record_tokens(model, input, output)` | After every LLM API call |
| `report()` | After the agent run |

### Integration point: Custom strategies

```python
class MyStrategy(DetectionStrategy):
    def check(self, record):
        # Your custom logic
        return confidence, reason

composite = CompositeStrategy()
composite.custom = MyStrategy()
# Or replace a default: composite.exact = MyStrategy()
```

### Integration point: Custom guards

```python
class MyGuard(Guard):
    def observe_call(self, event): ...
    def observe_tokens(self, event): ...
    def observe_state(self, state): ...

LoopBuster(guards=[MyGuard()])
```

### Integration point: Callbacks

```python
LoopBuster(
    on_warn=lambda d: send_alert(d),
    on_stop=lambda d: switch_to_fallback(),
    on_trip=lambda r: log_trip(r),
)
```

### Integration point: MCP protocol

Any MCP-compatible host (Claude Desktop, Claude Code, Cursor) can connect via stdio:

```bash
python -m loopbuster.mcp_server
```

Exposed tools: `check_cycle`, `get_report`, `reset_session`, `configure`.

---

## 7. Interview Preparation

### Core narrative (3-minute version)

> "LoopBuster is a zero-dependency Python library that detects when LLM agents get stuck in loops. The core is a `check()` method that takes the agent's current tool call and runs it through four parallel detection strategies — exact repeat, fuzzy repeat, cycle detection, and output stagnation. Each strategy returns a confidence score, which gets blended using a weighted consensus. If the blended confidence exceeds a threshold, the engine increments a consecutive hit counter and maps it to an action level: ALLOW, WARN, STOP, or ESCALATE. The thresholds can adapt automatically based on how diverse the agent's actions are — a coding agent that calls `read_file` 50 times should be treated differently from a search agent that calls `web_search` 50 times. There's also a circuit breaker for pre-flight checks, budget guards for cost control, and a stuck report for post-mortem diagnostics. The whole library is framework-agnostic — it works with LangGraph, AutoGen, CrewAI, or anything else."

### Likely follow-up questions

1. **"How is this different from a simple rate limiter?"** — Rate limiters count calls per time window. LoopBuster looks at *what* the agent is calling, not just *how often*. Two calls per minute with different query intents is fine; 20 calls per second with the same query is a loop.

2. **"Have you tested this against real agent traces?"** — The 20-scenario benchmark uses synthetic data. Real-world validation would require replaying logged agent executions. I ran it against traces from my medical diagnosis agent project, where it caught a cycle the team hadn't noticed.

3. **"What's the most common false positive scenario?"** — An agent legitimately calling the same tool with slightly different pagination parameters (page 1, page 2, page 3). The fuzzy strategy with default 0.85 threshold would flag this. Solution: lower the threshold or set `action_config` to require more consecutive hits before escalating.

4. **"Why not integrate this as a LangGraph middleware instead of a standalone library?"** — I wanted it to work with any framework, not just LangGraph. The trade-off is that LangGraph users need one extra line to wrap their loop. I've published integration examples for the three most common frameworks.

5. **"How would you handle an agent that intentionally varies its behavior to avoid detection?"** — The cycle detection strategy catches A→B→C→A→B→C patterns regardless of arg variation. The stagnation strategy catches when outputs don't change even if inputs vary. The adaptive threshold tightens when diversity drops. A truly adversarial agent would need to vary both tools AND outputs AND maintain high diversity — at which point it's no longer "stuck," it's deliberately evading, which is a different problem.

---

*Last updated: 2026-06-03 — LoopBuster v0.3.0*
