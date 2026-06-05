<<<<<<< HEAD
# Changelog

## [0.3.0] - 2026-06-03

### 核心变更
* **README 完全重写**：全面展示项目的技术深度，包含完整功能矩阵、架构图、多因子相似度引擎详解、代码示例覆盖所有核心特性（AdaptiveActionConfig、AsyncLoopBuster、Circuit Breaker、Stuck Report、MCP Server、Framework Integrations），以及 20 场景 benchmark 数据。
* **Benchmark 全面升级**：从 10 个场景扩展到 20 个，覆盖 Exact Repeat、Cycle、Fuzzy Repeat、Output Stagnation、Noise Denoising、正常行为和边缘用例，策略级和系统级双验证。
* **engine.py bugfix**：修复 `similarity_threshold` 参数未传递给 FuzzyRepeatStrategy 和 OutputStagnationStrategy 的问题，确保用户指定的阈值生效。
* **MCP Server 重写**：从单工具简易实现升级为完整的 JSON-RPC 2.0 MCP 协议实现，支持 tools/list、tools/call、initialize、notifications 方法，新增 get_report、reset_session、configure 三个工具，包含合理的错误处理和异常 traceback。
* **pyproject.toml 修复**：将 redis、fastapi、uvicorn 从硬依赖移为 optional-dependency，匹配零依赖承诺；修复 Homepage URL（liuchunwei → liuchunwei732-cmyk）；添加 hatchling build-system 配置。
* **版本更新**：0.2.0 → 0.3.0

### 安装方式
```bash
# 核心零依赖
pip install loopbuster

# 可选项
pip install loopbuster[redis]     # Redis 后端
pip install loopbuster[dashboard] # Web Dashboard
pip install loopbuster[all]       # 全部
pip install loopbuster[dev]       # 开发
```

## [0.2.1] - 2026-06-02
=======
## [0.3.0] - 2026-06-03
>>>>>>> codex/deep-detection-v0.3.0

### Deep Detection (New)

<<<<<<< HEAD
### 安装方式
```bash
pip install loopbuster[dashboard]
=======
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
>>>>>>> codex/deep-detection-v0.3.0
```

## [0.2.1] - 2026-06-02

<<<<<<< HEAD
### 已知限制（诚实披露）
* **暂无语义检测**：尽管 README 中提及了"语义循环检测"，但 v0.2.1 版本目前仅支持基于字符编辑距离的模式比对。我们暂未引入 Embedding 模型（以保持轻量级零外部依赖目标），该特性将在后续规划中评估实现。
* **Dashboard 测试缺失**：Dashboard 启动逻辑目前暂未纳入自动化测试体系，建议在生产环境中谨慎使用，或在测试环境中先进行功能验证。

## [0.2.0] - 2026-06-01

### 新特性
* 全面重构的 AsyncLoopBuster 支持异步 context manager 和 hung coroutine 检测
* AdaptiveActionConfig 基于动作多样性动态调整阈值
* Stuck Report 诊断报告（行动历史、多样性比率、Token 浪费估算）
* MCP Server 集成，可在 MCP 兼容环境中直接调用
* Dashboard 实时监控界面（实验性）

### 改进
* 相似度引擎增强：UUID/时间戳噪音归一化、长短列表策略
* 测试覆盖提升：新增 async、adaptive、stuck report 测试

### 修复
* 修复 async 上下文隔离问题
* 修复循环检测策略中窗口计算的边界情况

## [0.1.0] - 2026-05-15

### 初始版本
* 核心 LoopBuster 引擎，支持 4 种检测策略
* Circuit Breaker 预检机制
* BudgetCeiling、RepeatCallGuard、StateStasis 硬性守卫
* 零外部依赖
* LangGraph、CrewAI、AutoGen 集成教程
=======
### Core Changes
* **Dashboard integration**: New `start_dashboard()` interface for real-time monitoring (experimental).
* **Engineering improvements**: Optimized engine.py stability and context management.
* **Honest disclosure**: Acknowledged lack of semantic detection and dashboard test coverage.

## [0.2.0] - 2026-05-???

* Initial public release with 4 detection strategies, circuit breaker, 3 guards, and LangChain integration.
>>>>>>> codex/deep-detection-v0.3.0
