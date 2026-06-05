# LoopBuster Benchmark Specification

## 目标

建立一个可复现、可扩展的 Agent 轨迹评估基准，用于：
1. 定量评估 LoopBuster 的 precision / recall / F1
2. 对比不同策略组合的效果
3. 定位误报和漏报的模式
4. 为后续引入 ML 模型提供训练/验证数据

## 数据集设计

### 数据来源（两阶段）

**Phase 1 — 合成轨迹（目标 500+ 条）**
- 程序化生成的 agent 行为序列
- 每条轨迹包含：工具名、参数、输出文本、执行顺序
- 已知 ground truth label（因为是我们注入的循环）
- 覆盖全部 4 种循环模式 + good cycle + 无循环正常场景

**Phase 2 — 真实轨迹（目标 200+ 条）**
- 通过 LangGraph / CrewAI 运行真实 agent 任务收集
- 人工标注 ground truth
- 覆盖 5 种任务类型：搜索聚合、数据分析、代码生成、文件操作、API 编排

### 轨迹格式

每条轨迹是一个 JSON 对象：

```json
{
  "trajectory_id": "synth_0001",
  "source": "synthetic",
  "task_description": "搜索多个城市的天气信息并汇总",
  "task_category": "web_search",
  "ground_truth": {
    "is_loop": false,
    "loop_type": null,
    "severity": 0,
    "description": "每次搜索不同城市，信息逐步累积 — good cycle"
  },
  "actions": [
    {
      "step": 1,
      "tool": "search",
      "args": {"query": "weather Paris"},
      "output": "It is 20°C in Paris, sunny"
    },
    {
      "step": 2,
      "tool": "search",
      "args": {"query": "weather Tokyo"},
      "output": "It is 25°C in Tokyo, cloudy"
    }
  ],
  "metadata": {
    "agent_framework": "synthetic",
    "model": null,
    "total_steps": 5,
    "total_tokens_estimate": null
  }
}
```

### Label Schema

| 字段 | 类型 | 可选值 |
|---|---|---|
| `is_loop` | bool | true / false |
| `loop_type` | string 或 null | "exact_repeat" / "fuzzy_repeat" / "cycle" / "output_stagnation" / "good_cycle" / null |
| `severity` | int 1~5 | 1=轻微重复  ~  5=灾难性循环（成本 > $100） |
| `description` | string | 人工阅读的说明 |

### 场景分类矩阵

| 类别 | 子类 | 数量目标 | 说明 |
|---|---|---|---|
| **无循环** | 正常多步 | 80 | 不同工具、不同参数、逐步推进 |
| | 单步 | 20 | 只有一个 action，无循环可能 |
| | 空 | 10 | 没有任何 action |
| **Exact Repeat** | 连续相同 | 60 | 同 (tool, args) 连续重复 3~10 次 |
| | 间隔相同 | 30 | 同 (tool, args) 间隔重复（中间有其他工具） |
| **Fuzzy Repeat** | 参数微调 | 50 | 同工具，参数编辑距离 < threshold |
| | 参数大幅改变 | 20 | 同工具，参数差异大但意图相同 |
| **Cycle** | 2-tool 循环 | 40 | A→B→A→B |
| | 3-tool 循环 | 30 | A→B→C→A→B→C |
| | 4+ tool 循环 | 15 | 更长的循环模式 |
| **Output Stagnation** | 输出完全相同 | 40 | 每次 output 一模一样 |
| | 输出高度相似 | 30 | output 只有时间戳等噪音不同 |
| **Good Cycle** | 搜索渐进 | 40 | 每次搜索不同 query，信息累积 |
| | 迭代优化 | 20 | 每次修改代码/文本，逐步改善 |
| **混合** | 无循环 + 有循环混合 | 30 | 前 5 步正常，后 5 步循环 |
| **边界** | 大参数 | 15 | args 包含 100+ 字段 |
| | 超大输出 | 15 | output 长度 > 100K chars |
| | 空参数/空输出 | 10 | tool 被调但没有 args 或 output |

**合计: 500+ 条**

## 评估框架

### 指标

```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * Precision * Recall / (Precision + Recall)
```

其中：
- TP: 有循环 → LoopBuster 判定为 STOP/ESCALATE
- FP: 无循环 → LoopBuster 判定为 STOP/ESCALATE
- FN: 有循环 → LoopBuster 判定为 ALLOW/WARN
- TN: 无循环 → LoopBuster 判定为 ALLOW/WARN

### 分层评估

评估脚本应输出三组指标：

1. **总体指标** — 所有 500+ 轨迹的整体表现
2. **按循环类型** — 每种 loop_type 各自的指标
3. **按严重程度** — severity 1~5 各自的指标

### 对比基线

LoopBuster 应与以下基线对比：
- 纯 ExactRepeat 策略
- 纯 CycleDetection 策略
- max_iter 兜底（固定步数上限）
- agent-loop-guard（如果有条件）

## 可扩展性要求

- 新增场景不需要修改评估脚本（扫描目录加载 JSON）
- 场景文件按目录组织：`benchmark/scenarios/<category>/<scenario_id>.json`
- 评估结果输出为 JSON 和 Markdown 两种格式
- CI 中可运行 subset（如 `--quick` 只跑 50 条）

## 输出产物

1. `benchmark/scenarios/` — 500+ 条 JSON 轨迹文件
2. `benchmark/evaluate.py` — 评估脚本
3. `benchmark/RESULTS.md` — 评估结果（git 跟踪，每次更新后重新生成）
4. `benchmark/scenarios/README.md` — 数据集文档
