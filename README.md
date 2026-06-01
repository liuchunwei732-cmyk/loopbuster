# LoopBuster 🛑

> Break the infinite loops of your AI Agents. Stop burning tokens on dead-ends.

![LoopBuster Demo](docs/loopbuster-demo.gif)

*In this scenario, LoopBuster detects that the agent is trapped in a rate-limit retry cycle, interrupts the flow, and forces the agent to use the `Wait` tool instead of burning API credits.*

## What is LoopBuster?
LoopBuster is an industrial-grade, pluggable middleware for LLM Agents that detects and interrupts semantic and structural infinite loops.

## Features
- **Semantic Cycle Detection**: Goes beyond exact string matching. Detects when an agent is "rephrasing the same failing action" using fast embedding similarities.
- **Pluggable Backend**: Move beyond memory-only states.
  - `InMemoryBackend`: For local scripts.
  - `RedisBackend`: For distributed, enterprise-grade agent fleets.
- **Native Integrations**:
  - `LangChain` / `LangGraph`
  - `AutoGen`
  - `CrewAI`
  - `MCP (Model Context Protocol)`

## Installation
```bash
pip install loopbuster
```

## Quick Start
```python
from loopbuster import LoopBuster
from loopbuster.storage.redis import RedisBackend

# Enterprise setup: Distributed state tracking
buster = LoopBuster(
    backend=RedisBackend(redis_url="redis://localhost:6379"),
    threshold=0.85
)

# Intercept loops before making expensive LLM calls
if buster.check_cycle(agent_current_action):
    print("🛑 Loop detected! Intervention:", buster.get_suggestion())
else:
    execute_agent_action()
```

## Supported Integrations

### LangGraph
```python
from loopbuster.integrations.langgraph import loopbuster_middleware
# Add to your graph definition...
```

### AutoGen
```python
from loopbuster.integrations.autogen import apply_loopbuster
apply_loopbuster(assistant_agent, buster)
```
