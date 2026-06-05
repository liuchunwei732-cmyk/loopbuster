"""
templates.py — 所有场景模板定义。

每个模板是一个 dict:
  - category:     场景大类
  - loop_type:    循环类型（None 表示无循环）
  - severity:     严重程度 1~5
  - description:  人类可读的描述
  - count:        要生成多少条变体
  - generator:    生成函数名（在 generator.py 中定义）
  - config:       传给生成函数的配置参数

这种设计让模板和生成逻辑分离：模板只描述"要什么"，
generator 负责"怎么生成"。
"""

from __future__ import annotations

import random

# ======================================================================
# 辅助常量
# ======================================================================

_ERROR_TYPES = ["TypeError", "ValueError", "KeyError", "AttributeError", "IndexError"]
_LANGUAGES = ["Python", "JavaScript", "TypeScript", "Rust", "Go", "Java"]
_CITIES = ["Beijing", "Shanghai", "Tokyo", "London", "Paris", "New York", "Sydney", "Berlin"]

# ======================================================================
# 模板定义
# ======================================================================

TEMPLATES = [

    # ------------------------------------------------------------------
    # 1. 无循环 — 正常多步
    # ------------------------------------------------------------------
    {
        "category": "normal",
        "loop_type": None,
        "severity": 0,
        "description": "不同工具、不同参数、逐步推进的正常 agent 行为",
        "count": 40,
        "generator": "gen_normal_progressive",
        "config": {
            "min_steps": 3,
            "max_steps": 8,
            "tool_count_range": (3, 6),
        },
    },
    {
        "category": "normal",
        "loop_type": None,
        "severity": 0,
        "description": "长序列正常行为（10+ 步）",
        "count": 20,
        "generator": "gen_normal_progressive",
        "config": {
            "min_steps": 10,
            "max_steps": 20,
            "tool_count_range": (5, 10),
        },
    },
    {
        "category": "normal",
        "loop_type": None,
        "severity": 0,
        "description": "单步 action",
        "count": 20,
        "generator": "gen_normal_progressive",
        "config": {
            "min_steps": 1,
            "max_steps": 1,
            "tool_count_range": (1, 1),
        },
    },

    # ------------------------------------------------------------------
    # 2. Exact Repeat — 连续相同
    # ------------------------------------------------------------------
    {
        "category": "exact_repeat",
        "loop_type": "exact_repeat",
        "severity": 3,
        "description": "同 (tool, args) 连续重复 3~5 次",
        "count": 30,
        "generator": "gen_exact_repeat",
        "config": {
            "repeat_count_range": (3, 5),
            "tools": ["web_search", "api_call", "read_file", "python_repl", "get_weather"],
        },
    },
    {
        "category": "exact_repeat",
        "loop_type": "exact_repeat",
        "severity": 4,
        "description": "同 (tool, args) 连续重复 6~10 次",
        "count": 20,
        "generator": "gen_exact_repeat",
        "config": {
            "repeat_count_range": (6, 10),
            "tools": ["web_search", "api_call", "bash_shell", "send_email"],
        },
    },
    {
        "category": "exact_repeat",
        "loop_type": "exact_repeat",
        "severity": 3,
        "description": "间隔重复：中间有其他工具调用，但最终回到相同 (tool, args)",
        "count": 20,
        "generator": "gen_interleaved_repeat",
        "config": {
            "repeat_count_range": (3, 5),
            "tools": ["web_search", "read_file", "python_repl"],
        },
    },

    # ------------------------------------------------------------------
    # 3. Fuzzy Repeat — 参数微调循环
    # ------------------------------------------------------------------
    {
        "category": "fuzzy_repeat",
        "loop_type": "fuzzy_repeat",
        "severity": 3,
        "description": "同一工具，参数只有微小的文字差异（编辑距离小）",
        "count": 30,
        "generator": "gen_fuzzy_repeat",
        "config": {
            "repeat_count_range": (3, 6),
            "tools": ["web_search", "search_database"],
            "arg_variation": "minor",  # 参数只有 1~2 个词不同
        },
    },
    {
        "category": "fuzzy_repeat",
        "loop_type": "fuzzy_repeat",
        "severity": 2,
        "description": "同一工具，参数变化较大但意图相同",
        "count": 20,
        "generator": "gen_fuzzy_repeat",
        "config": {
            "repeat_count_range": (3, 5),
            "tools": ["web_search", "search_wikipedia"],
            "arg_variation": "major",
        },
    },

    # ------------------------------------------------------------------
    # 4. Cycle — 循环模式
    # ------------------------------------------------------------------
    {
        "category": "cycle",
        "loop_type": "cycle",
        "severity": 3,
        "description": "2-tool 循环：A→B→A→B",
        "count": 25,
        "generator": "gen_cycle",
        "config": {
            "cycle_length": 2,
            "min_repetitions": 2,
            "max_repetitions": 4,
            "tool_pairs": [
                ("web_search", "web_fetch"),
                ("read_file", "write_file"),
                ("search_database", "parse_data"),
                ("api_call", "summarize_text"),
            ],
        },
    },
    {
        "category": "cycle",
        "loop_type": "cycle",
        "severity": 4,
        "description": "3-tool 循环：A→B→C→A→B→C",
        "count": 20,
        "generator": "gen_cycle",
        "config": {
            "cycle_length": 3,
            "min_repetitions": 2,
            "max_repetitions": 4,
            "tool_pairs": [
                ("web_search", "web_fetch", "summarize_text"),
                ("read_file", "python_repl", "write_file"),
                ("search_database", "api_call", "parse_data"),
            ],
        },
    },
    {
        "category": "cycle",
        "loop_type": "cycle",
        "severity": 4,
        "description": "4-tool 循环",
        "count": 10,
        "generator": "gen_cycle",
        "config": {
            "cycle_length": 4,
            "min_repetitions": 2,
            "max_repetitions": 3,
            "tool_pairs": [
                ("web_search", "web_fetch", "parse_data", "summarize_text"),
                ("read_file", "python_repl", "bash_shell", "write_file"),
            ],
        },
    },

    # ------------------------------------------------------------------
    # 5. Output Stagnation — 输出停滞
    # ------------------------------------------------------------------
    {
        "category": "stagnation",
        "loop_type": "output_stagnation",
        "severity": 3,
        "description": "同一工具，输出完全相同（每次返回一样的结果）",
        "count": 25,
        "generator": "gen_output_stagnation",
        "config": {
            "repeat_count_range": (3, 6),
            "tools": ["web_search", "get_weather", "read_file", "api_call"],
            "output_variation": "identical",
        },
    },
    {
        "category": "stagnation",
        "loop_type": "output_stagnation",
        "severity": 2,
        "description": "同一工具，输出仅有时间戳/UUID 等噪音不同",
        "count": 20,
        "generator": "gen_output_stagnation",
        "config": {
            "repeat_count_range": (3, 5),
            "tools": ["web_search", "get_weather", "read_news", "api_call"],
            "output_variation": "timestamp_only",
        },
    },

    # ------------------------------------------------------------------
    # 6. Good Cycle — 好循环
    # ------------------------------------------------------------------
    {
        "category": "good_cycle",
        "loop_type": "good_cycle",
        "severity": 0,
        "description": "渐进式搜索：每次搜索不同 query，信息逐步累积",
        "count": 25,
        "generator": "gen_good_cycle_progressive",
        "config": {
            "tools": ["web_search"],
            "min_steps": 3,
            "max_steps": 6,
            "variation": "different_query_each_time",
        },
    },
    {
        "category": "good_cycle",
        "loop_type": "good_cycle",
        "severity": 0,
        "description": "迭代优化：每次修改代码/文本，逐步改善",
        "count": 15,
        "generator": "gen_good_cycle_progressive",
        "config": {
            "tools": ["python_repl", "write_file"],
            "min_steps": 3,
            "max_steps": 5,
            "variation": "iterative_improvement",
        },
    },

    # ------------------------------------------------------------------
    # 7. 混合 — 前段正常 + 后段循环
    # ------------------------------------------------------------------
    {
        "category": "mixed",
        "loop_type": "exact_repeat",
        "severity": 3,
        "description": "前 3~5 步正常，后 3~5 步 exact repeat",
        "count": 15,
        "generator": "gen_mixed",
        "config": {
            "warmup_steps_range": (3, 5),
            "loop_steps_range": (3, 5),
            "loop_type": "exact_repeat",
        },
    },
    {
        "category": "mixed",
        "loop_type": "cycle",
        "severity": 3,
        "description": "前 3~5 步正常，后段进入 cycle",
        "count": 15,
        "generator": "gen_mixed",
        "config": {
            "warmup_steps_range": (3, 5),
            "loop_steps_range": (4, 8),
            "loop_type": "cycle",
        },
    },

    # ------------------------------------------------------------------
    # 8. 边界情况
    # ------------------------------------------------------------------
    {
        "category": "edge",
        "loop_type": None,
        "severity": 0,
        "description": "超大参数（args 含 50+ 字段）",
        "count": 10,
        "generator": "gen_edge_large_args",
        "config": {
            "field_count_range": (50, 100),
        },
    },
    {
        "category": "edge",
        "loop_type": None,
        "severity": 0,
        "description": "超大输出（output > 10K chars）",
        "count": 10,
        "generator": "gen_edge_large_output",
        "config": {
            "output_length_range": (10000, 50000),
        },
    },
    {
        "category": "edge",
        "loop_type": "exact_repeat",
        "severity": 2,
        "description": "空参数重复（tool 被调但没有 args）",
        "count": 10,
        "generator": "gen_edge_empty_args",
        "config": {
            "repeat_count_range": (3, 5),
            "tools": ["get_current_time", "list_directory"],
        },
    },
    {
        "category": "edge",
        "loop_type": None,
        "severity": 0,
        "description": "空轨迹（没有任何 action）",
        "count": 10,
        "generator": "gen_empty_trajectory",
        "config": {},
    },
]

# ======================================================================
# 按类别统计
# ======================================================================

def summary() -> dict[str, int]:
    """返回各类别的场景计数。"""
    counts: dict[str, int] = {}
    for t in TEMPLATES:
        cat = t["category"]
        counts[cat] = counts.get(cat, 0) + t["count"]
    return counts


if __name__ == "__main__":
    total = sum(t["count"] for t in TEMPLATES)
    print(f"Total templates: {len(TEMPLATES)}")
    print(f"Total scenarios: {total}")
    for cat, count in summary().items():
        print(f"  {cat}: {count}")
