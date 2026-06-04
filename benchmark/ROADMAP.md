# Benchmark 实现路线图

## Phase 1：合成轨迹生成器（你当前所在的位置）

**目标**：5 天内生成 500+ 条带标签的合成轨迹

### 技术方案

写一个 Python 脚本 `benchmark/generator.py`，它不做以下任何事：
- ❌ 不调 LLM API
- ❌ 不启动任何 agent 框架
- ❌ 不需要网络

它只做一件事：**根据配置模板程序化地生成 action 序列**。

核心设计：

```
generator.py
├── templates/              # 轨迹模板（YAML）
│   ├── normal/             # 无循环场景
│   ├── exact_repeat/       # 精确重复
│   ├── fuzzy_repeat/       # 模糊重复
│   ├── cycle/              # 循环模式
│   ├── stagnation/         # 输出停滞
│   ├── good_cycle/         # 好循环
│   └── edge/               # 边界情况
├── tool_lib.py             # 工具名、参数模板、输出模板库
│   ├── tool_names: search, read_file, write_file, python_repl, api_call, ...
│   ├── arg_templates: { "query": "weather ${city}", "query": "${concept} 教程" }
│   └── output_templates: { "search": "关于 ${topic} 的结果: ${result}" }
└── generate.py             # 主入口：读模板 → 生成轨迹 → 写 JSON
```

### 模板示例

```yaml
# templates/exact_repeat/search_same_query.yaml
category: exact_repeat
loop_type: exact_repeat
severity: 3
count: 20                        # 生成 20 条变体
variations:
  - tool: search
    arg_template:
      query: "how to fix ${error_type} in Python"
    arg_values:                  # 这些值随机组合
      error_type: ["TypeError", "ValueError", "KeyError", "AttributeError", "ImportError"]
    output_template: "To fix ${error_type}, you need to..."
    repeat_count: [3, 4, 5, 6, 7]  # 重复次数
    before: []                     # 可选：重复前的一些正常步骤
```

生成器读这个模板后会产生类似这样的轨迹：
```
step 1: search(query="how to fix TypeError in Python") → "To fix TypeError..."
step 2: search(query="how to fix TypeError in Python") → "To fix TypeError..."
step 3: search(query="how to fix TypeError in Python") → "To fix TypeError..."
```

如果 `before` 有值，则前面先插入几个正常步骤：
```
step 1: search(query="Python异常类型") → "Python 的异常类型包括..."
step 2: search(query="how to fix TypeError in Python") → "To fix TypeError..."
step 3: search(query="how to fix TypeError in Python") → "To fix TypeError..."
...
```

### Good Cycle 模板的关键设计

Good cycle 的模板需要让**每次的 output 不同**：

```yaml
# templates/good_cycle/search_progressive.yaml
category: good_cycle
loop_type: good_cycle
severity: 0
count: 30
variations:
  - tool: search
    arg_template:
      query: "${city} weather"
    arg_values:
      city: ["Beijing", "Shanghai", "Tokyo", "London", "Paris", "New York", "Sydney", 
             "Mumbai", "Berlin", "Moscow", "Toronto", "Dubai", "São Paulo", "Seoul", 
             "Bangkok", "Singapore", "Istanbul", "Rome", "Madrid", "Cairo"]
    output_template: "${city} weather: ${temperature}°C, ${condition}"
    output_values:
      temperature: ["12", "15", "18", "20", "22", "25", "28", "30", "32", "35"]
      condition: ["sunny", "cloudy", "rainy", "windy", "foggy"]
    repeat_count: [3, 4, 5]
```

这样每次 search 的 query 不同、output 也不同，属于渐进式搜索。

### 实现步骤

| 步骤 | 内容 | 预计时间 |
|---|---|---|
| 1 | 建目录结构 + tool_lib.py（工具名池、参数模板池、输出模板池） | 半天 |
| 2 | 写 generator.py 核心逻辑（读 YAML → 展开参数 → 生成 action 序列 → 写 JSON） | 1 天 |
| 3 | 写所有模板（7 个目录，每个 5~10 个模板文件） | 2 天 |
| 4 | 生成 500+ 条轨迹，人工抽查 50 条验证标签正确性 | 半天 |
| 5 | 写 evaluate.py 评估脚本 | 1 天 |
| 6 | 跑第一轮评估，调阈值，输出 RESULTS.md | 半天 |

**合计：约 5 天**

---

## Phase 2：真实轨迹采集（可选，面试加分项）

需要在 Phase 1 之后做，依赖外部 API。

### 方案

1. 用 LangGraph 搭建 3 个 agent 任务：
   - 搜索聚合 agent：搜索多个来源，汇总答案
   - 数据分析 agent：读 CSV，做统计，画图
   - 代码生成 agent：写代码，测试，修复

2. 通过 callback 拦截每个 tool call，记录轨迹

3. 故意注入循环条件（如让 search 工具在特定条件下返回相同结果）

4. 收集轨迹，人工标注

5. 与合成轨迹一起跑 eval

### 挑战

- 需要 OpenAI/Claude API key（每次跑约 $1~5）
- 注入循环需要修改 agent 的工具逻辑
- 人工标注耗时（200 条约需要 2~3 小时）

---

## 面试时的价值

做完 Phase 1，你就有了：

```
total scenarios: 500+
precision: 97.2%
recall:     94.5%
f1:         95.8%
```

这组数据放在 README 最上面，配合一个图表说明按循环类型拆分的指标。面试官看到这个就知道你不是在自娱自乐——你有系统化的 eval 流程。

做完 Phase 2，你还有：

```
real trajectory scenarios: 200+
synthetic vs real performance gap: < 3%
```

这就能说明你的合成数据确实是真实情况的合理近似。
