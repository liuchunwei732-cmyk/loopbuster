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

### 核心变更
* **集成 Dashboard**：新增 `start_dashboard()` 接口，支持在 Agent 运行期间实时监控循环检测状态、资源使用及行动历史（实验性功能）。
* **工程化改进**：优化了核心引擎 `engine.py` 的稳定性和上下文管理。

### 安装方式
```bash
pip install loopbuster[dashboard]
```

### 特别致谢
感谢开发者 Hanako 对项目进行的犀利 Review。正是你的坦诚指出了项目在 README 承诺与代码实现之间的差距，帮助我们认清了方向，明确了后续的改进目标。

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
