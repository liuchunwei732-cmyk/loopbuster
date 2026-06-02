# AGC (Agent Governance Core)

**An Industrial-Grade Governance Framework for AI Agents.**

AGC 是一个专为生产级 AI Agent 系统设计的治理与编排中间件。它旨在解决 Agent 在复杂生产环境下出现的「死循环爆炸」、「账单失控」以及「执行状态不可追溯」等工程难题，将原本不可控的 LLM 调用转化为可治理、可恢复、可观测的标准化执行单元 (Task Unit)。

## 核心架构哲学
AGC 的核心理念是**「治理与编排解耦」**。我们认为 Agent 的逻辑编排应当发散灵活，但其执行行为必须受到严格的工程化约束：

*   **状态后端分布式化**：支持从 SQLite 到 Redis 的平滑切换，为多节点 Agent 集群提供一致的状态快照。
*   **全链路可观测性**：原生集成 **OpenTelemetry**，实现对每一个 Agent Action 的全链路性能追踪与行为溯源。
*   **契约化治理**：利用 **Zod** 进行严苛的运行时类型校验，确保所有工具调用 (Skill Call) 在执行前即符合 Schema 契约。
*   **异步语义审计**：在不阻塞主流程的前提下，异步触发语义指纹检查，识别隐藏的“语义死循环”。

## 为什么选择 AGC？
| 特性 | 传统 Agent 开发 | 使用 AGC 治理 |
| :--- | :--- | :--- |
| **错误治理** | 依赖手动 try-catch | **内置指数退避重试 (Exponential Backoff)** |
| **状态持久化** | 内存存储，崩溃即丢失 | **基于 Redis/SQLite 的原子快照** |
| **死循环检测** | 编辑距离，误判率高 | **语义指纹 (Embedding-based) 检测** |
| **运维观测** | 零散日志，无法溯源 | **全链路 OTel 跟踪，标准 API 接入** |

## 快速上手
```typescript
import { AGCCore } from '@loopbuster/agc';

// 1. 初始化治理内核 (支持分布式 Redis 配置)
const agc = new AGCCore({
  storage: new RedisBackend('redis://localhost:6379'),
  telemetry: 'otel-exporter'
});

// 2. 注册具备契约约束的 Skill
agc.registerSkill('oral_report_gen', {
  schema: OralReportSchema, // Zod 定义
  handler: async (data) => { /* 业务逻辑 */ }
});

// 3. 运行已治理的任务
await agc.execute('oral_report_gen', data);
```

## 技术深度亮点
*   **幂等执行机制**：通过事务锁 (Transaction Locking) 与幂等控制，保障 Agent 在断点续跑时数据的一致性。
*   **Sidecar 治理模式**：支持以独立服务部署，隔离治理逻辑与业务代码，极大降低了对现有 Agent 执行流的侵入性。
*   **生产级 Telemetry**：定义了 `agc_governance_failure_rate` 与 `agc_semantic_cycle_detect_total` 等核心指标，实现了对 AI 执行能力的量化观测。
