#!/usr/bin/env python3
"""
benchmark/generator.py — 合成轨迹生成器

读 templates.py 中的模板定义，调用 tool_lib.py 生成轨迹，
输出到 benchmark/scenarios/ 目录。

用法：
    python benchmark/generator.py                       # 全部生成
    python benchmark/generator.py --quick                # 只生成 50 条用于测试
    python benchmark/generator.py --category cycle       # 只生成 cycle 类别
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import uuid
from pathlib import Path
from typing import Any

# 添加项目根到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.tool_lib import (
    ARG_TEMPLATES,
    OUTPUT_TEMPLATES,
    PLACEHOLDER_POOL,
    OUTPUT_PLACEHOLDER_POOL,
    resolve_args,
    resolve_output,
    resolve_placeholder,
    pick_random_tool,
)
from benchmark.templates import TEMPLATES

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


# ======================================================================
# 生成器函数
# 每个函数接收 template 和 seed，返回一条轨迹 dict
# ======================================================================


def gen_normal_progressive(template: dict, seed: int) -> dict:
    """生成正常的多步渐进式轨迹。

    config:
        min_steps, max_steps, tool_count_range
    """
    cfg = template["config"]
    random.seed(seed)

    step_count = random.randint(cfg["min_steps"], cfg["max_steps"])
    tool_count = random.randint(*cfg["tool_count_range"])

    # 选工具列表（保证多样性）
    from benchmark.tool_lib import TOOL_NAMES
    tools = random.sample(TOOL_NAMES, min(tool_count, len(TOOL_NAMES)))

    actions = []
    for i in range(step_count):
        tool = tools[i % len(tools)]
        arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{}]))
        args = resolve_args(arg_tmpl)
        output = resolve_output(tool, args)
        actions.append({
            "step": i + 1,
            "tool": tool,
            "args": args,
            "output": output,
        })

    return _make_trajectory(template, seed, actions, description_suffix=f"{step_count}步渐进")


def gen_exact_repeat(template: dict, seed: int) -> dict:
    """生成连续 exact repeat 轨迹。

    config:
        repeat_count_range, tools
    """
    cfg = template["config"]
    random.seed(seed)

    repeat_count = random.randint(*cfg["repeat_count_range"])
    tool = random.choice(cfg["tools"])
    arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{}]))
    args = resolve_args(arg_tmpl)
    output = resolve_output(tool, args)

    actions = []
    for i in range(repeat_count):
        actions.append({
            "step": i + 1,
            "tool": tool,
            "args": dict(args),  # 相同 args
            "output": output,    # 相同 output
        })

    return _make_trajectory(template, seed, actions, description_suffix=f"{tool}x{repeat_count}")


def gen_interleaved_repeat(template: dict, seed: int) -> dict:
    """生成间隔重复轨迹：中间有其他工具调用。

    config:
        repeat_count_range, tools
    """
    cfg = template["config"]
    random.seed(seed)

    repeat_count = random.randint(*cfg["repeat_count_range"])
    tool = random.choice(cfg["tools"])
    arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{}]))
    args = resolve_args(arg_tmpl)
    output = resolve_output(tool, args)

    from benchmark.tool_lib import TOOL_NAMES
    filler_tools = [t for t in TOOL_NAMES if t != tool]
    filler_count = min(3, len(filler_tools))

    actions = []
    step = 1
    for i in range(repeat_count):
        # 每次重复前插入 1~2 个 filler 工具
        if i > 0:
            for _ in range(random.randint(1, 2)):
                filler = random.choice(filler_tools)
                f_arg_tmpl = random.choice(ARG_TEMPLATES.get(filler, [{}]))
                f_args = resolve_args(f_arg_tmpl)
                f_output = resolve_output(filler, f_args)
                actions.append({
                    "step": step,
                    "tool": filler,
                    "args": f_args,
                    "output": f_output,
                })
                step += 1
        # 重复的 tool
        actions.append({
            "step": step,
            "tool": tool,
            "args": dict(args),
            "output": output,
        })
        step += 1

    return _make_trajectory(template, seed, actions, description_suffix=f"{tool}x{repeat_count}间隔重复")


def gen_fuzzy_repeat(template: dict, seed: int) -> dict:
    """生成 fuzzy repeat 轨迹。

    config:
        repeat_count_range, tools, arg_variation ("minor" | "major")
    """
    cfg = template["config"]
    random.seed(seed)

    repeat_count = random.randint(*cfg["repeat_count_range"])
    tool = random.choice(cfg["tools"])

    # 生成一个基础参数集，然后每次微调
    arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{"query": "${query}"}]))
    base_args = resolve_args(arg_tmpl)

    actions = []
    for i in range(repeat_count):
        # 每次只微调参数
        args = dict(base_args)
        if cfg.get("arg_variation") == "minor":
            # 只改一个参数里的 1~2 个词
            for k in args:
                words = args[k].split()
                if len(words) > 2:
                    idx = random.randint(0, len(words) - 1)
                    words[idx] = random.choice([
                        "guide", "tutorial", "overview", "basics", "advanced",
                        "beginner", "tips", "examples", "best", "simple",
                    ])
                    args[k] = " ".join(words)
                    break
        else:
            # 大幅变化：全部换参数值
            args = resolve_args(arg_tmpl)

        # 每次 output 可以相同也可以不同（fuzzy repeat 只看 args）
        output = resolve_output(tool, args)
        actions.append({
            "step": i + 1,
            "tool": tool,
            "args": args,
            "output": output,
        })

    return _make_trajectory(template, seed, actions, description_suffix=f"{tool}x{repeat_count}fuzzy")


def gen_cycle(template: dict, seed: int) -> dict:
    """生成 cycle 轨迹。

    config:
        cycle_length, min_repetitions, max_repetitions, tool_pairs
    """
    cfg = template["config"]
    random.seed(seed)

    cycle_tools = random.choice(cfg["tool_pairs"])
    repetitions = random.randint(cfg["min_repetitions"], cfg["max_repetitions"])

    actions = []
    step = 1
    for rep in range(repetitions):
        for tool in cycle_tools:
            arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{}]))
            args = resolve_args(arg_tmpl)
            output = resolve_output(tool, args)
            actions.append({
                "step": step,
                "tool": tool,
                "args": args,
                "output": output,
            })
            step += 1

    cycle_str = "→".join(cycle_tools)
    return _make_trajectory(template, seed, actions, description_suffix=f"[{cycle_str}]x{repetitions}")


def gen_output_stagnation(template: dict, seed: int) -> dict:
    """生成 output stagnation 轨迹。

    config:
        repeat_count_range, tools, output_variation ("identical" | "timestamp_only")
    """
    cfg = template["config"]
    random.seed(seed)

    repeat_count = random.randint(*cfg["repeat_count_range"])
    tool = random.choice(cfg["tools"])

    # 首先生成一个基准输出
    arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{}]))
    base_args = resolve_args(arg_tmpl)
    base_output = resolve_output(tool, base_args)

    actions = []
    for i in range(repeat_count):
        args = dict(base_args)
        if cfg["output_variation"] == "identical":
            output = base_output
        else:
            # timestamp_only: 只在输出中加入不同的时间戳
            ts = f"2024-01-{15 + i:02d} {9 + i:02d}:30:00"
            output = f"[{ts}] {base_output}"

        actions.append({
            "step": i + 1,
            "tool": tool,
            "args": args,
            "output": output,
        })

    return _make_trajectory(template, seed, actions, description_suffix=f"{tool}x{repeat_count}stagnation")


def gen_good_cycle_progressive(template: dict, seed: int) -> dict:
    """生成好循环：每次产生新信息。

    config:
        tools, min_steps, max_steps, variation
    """
    cfg = template["config"]
    random.seed(seed)

    step_count = random.randint(cfg["min_steps"], cfg["max_steps"])
    tool = random.choice(cfg["tools"])

    # 预生成不同的 query/城市，确保每次 output 不同
    # 从 PLACEHOLDER_POOL 中取不同值
    cities = random.sample(PLACEHOLDER_POOL.get("city", ["Beijing", "Tokyo", "London"]),
                           min(step_count, 10))
    topics = random.sample(PLACEHOLDER_POOL.get("topic", ["AI", "ML", "DL"]),
                           min(step_count, 10))
    languages = random.sample(PLACEHOLDER_POOL.get("language", ["Python", "JS", "Rust"]),
                              min(step_count, 10))

    actions = []
    for i in range(step_count):
        args = {}
        output = ""

        if cfg["variation"] == "different_query_each_time":
            # 每次搜不同的城市/主题
            if i < len(cities):
                args = {"query": f"{cities[i]} population"}
                output = f"{cities[i]} population: {random.randint(1, 40)} million"
            else:
                args = {"query": f"{topics[i % len(topics)]} tutorial"}
                output = f"{topics[i % len(topics)]}: {random.choice(['great intro', 'comprehensive guide', 'hands-on examples'])}"

        elif cfg["variation"] == "iterative_improvement":
            # 迭代改进：每次代码更完善
            if tool == "python_repl":
                code_snippets = [
                    "print('hello world')",
                    "import random\nprint(random.randint(1, 100))",
                    "import random\nfor i in range(5):\n    print(random.randint(1, 100))",
                ]
                idx = min(i, len(code_snippets) - 1)
                args = {"code": code_snippets[idx]}
                output = f"Output {idx + 1}: {random.choice(['3.14', '42', 'hello'])}"
            else:
                args = {"path": f"/output/draft_v{i + 1}.md"}
                output = f"Written version {i + 1} ({random.randint(100, 500)} words)"

        actions.append({
            "step": i + 1,
            "tool": tool,
            "args": args,
            "output": output,
        })

    return _make_trajectory(template, seed, actions, description_suffix=f"good_cycle_{cfg['variation']}")


def gen_mixed(template: dict, seed: int) -> dict:
    """生成前段正常 + 后段循环的混合轨迹。

    config:
        warmup_steps_range, loop_steps_range, loop_type
    """
    cfg = template["config"]
    random.seed(seed)

    warmup_steps = random.randint(*cfg["warmup_steps_range"])
    loop_steps = random.randint(*cfg["loop_steps_range"])
    loop_type = cfg["loop_type"]

    # 前段：正常
    from benchmark.tool_lib import TOOL_NAMES
    tools = random.sample(TOOL_NAMES, min(warmup_steps, len(TOOL_NAMES)))
    actions = []
    for i in range(warmup_steps):
        tool = tools[i % len(tools)]
        arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{}]))
        args = resolve_args(arg_tmpl)
        output = resolve_output(tool, args)
        actions.append({"step": i + 1, "tool": tool, "args": args, "output": output})

    # 后段：循环
    step_offset = warmup_steps
    if loop_type == "exact_repeat":
        tool = random.choice(["web_search", "api_call", "read_file"])
        arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{}]))
        args = resolve_args(arg_tmpl)
        output = resolve_output(tool, args)
        for i in range(loop_steps):
            actions.append({
                "step": step_offset + i + 1,
                "tool": tool,
                "args": dict(args),
                "output": output,
            })
    elif loop_type == "cycle":
        cycle_tools = random.choice([
            ("web_search", "web_fetch"),
            ("read_file", "write_file"),
        ])
        for i in range(loop_steps):
            tool = cycle_tools[i % len(cycle_tools)]
            arg_tmpl = random.choice(ARG_TEMPLATES.get(tool, [{}]))
            args = resolve_args(arg_tmpl)
            output = resolve_output(tool, args)
            actions.append({
                "step": step_offset + i + 1,
                "tool": tool,
                "args": args,
                "output": output,
            })

    return _make_trajectory(template, seed, actions,
                            description_suffix=f"warmup{warmup_steps}+loop{loop_steps}")


def gen_edge_large_args(template: dict, seed: int) -> dict:
    """生成超大参数的轨迹。"""
    cfg = template["config"]
    random.seed(seed)

    field_count = random.randint(*cfg["field_count_range"])
    args = {}
    for i in range(field_count):
        args[f"field_{i}"] = f"value_{random.randint(0, 10000)}"

    actions = [{
        "step": 1,
        "tool": "api_call",
        "args": args,
        "output": f"Processed {field_count} fields.",
    }]

    return _make_trajectory(template, seed, actions,
                            description_suffix=f"{field_count}fields")


def gen_edge_large_output(template: dict, seed: int) -> dict:
    """生成超大输出的轨迹。"""
    cfg = template["config"]
    random.seed(seed)

    output_length = random.randint(*cfg["output_length_range"])
    output_text = "Lorem ipsum dolor sit amet. " * (output_length // 30)

    actions = [{
        "step": 1,
        "tool": "read_file",
        "args": {"path": "/data/large_file.txt"},
        "output": output_text,
    }]

    return _make_trajectory(template, seed, actions,
                            description_suffix=f"{output_length}chars")


def gen_edge_empty_args(template: dict, seed: int) -> dict:
    """生成空参数的重复轨迹。"""
    cfg = template["config"]
    random.seed(seed)

    repeat_count = random.randint(*cfg["repeat_count_range"])
    tool = random.choice(cfg["tools"])

    actions = []
    for i in range(repeat_count):
        actions.append({
            "step": i + 1,
            "tool": tool,
            "args": {},
            "output": resolve_output(tool),
        })

    return _make_trajectory(template, seed, actions,
                            description_suffix=f"{tool}x{repeat_count}_empty_args")


def gen_empty_trajectory(template: dict, seed: int) -> dict:
    """生成空轨迹（0 个 action）。"""
    return _make_trajectory(template, seed, [], description_suffix="empty")


# ======================================================================
# 生成器注册表
# ======================================================================

GENERATORS = {
    "gen_normal_progressive": gen_normal_progressive,
    "gen_exact_repeat": gen_exact_repeat,
    "gen_interleaved_repeat": gen_interleaved_repeat,
    "gen_fuzzy_repeat": gen_fuzzy_repeat,
    "gen_cycle": gen_cycle,
    "gen_output_stagnation": gen_output_stagnation,
    "gen_good_cycle_progressive": gen_good_cycle_progressive,
    "gen_mixed": gen_mixed,
    "gen_edge_large_args": gen_edge_large_args,
    "gen_edge_large_output": gen_edge_large_output,
    "gen_edge_empty_args": gen_edge_empty_args,
    "gen_empty_trajectory": gen_empty_trajectory,
}


# ======================================================================
# 辅助
# ======================================================================


def _make_trajectory(
    template: dict,
    seed: int,
    actions: list[dict],
    description_suffix: str = "",
) -> dict:
    """从模板和生成的 actions 组装完整轨迹对象。"""
    tid = f"synth_{template['category']}_{seed:04d}"
    label = template["loop_type"] or "none"
    desc = template["description"]
    if description_suffix:
        desc += f" ({description_suffix})"

    return {
        "trajectory_id": tid,
        "source": "synthetic",
        "task_description": desc,
        "task_category": template["category"],
        "ground_truth": {
            "is_loop": template["loop_type"] is not None
                       and template["loop_type"] != "good_cycle",
            "loop_type": template["loop_type"],
            "severity": template["severity"],
            "description": desc,
        },
        "actions": actions,
        "metadata": {
            "agent_framework": "synthetic",
            "model": None,
            "total_steps": len(actions),
            "generator": template["generator"],
        },
    }


# ======================================================================
# 主入口
# ======================================================================


def generate(
    *,
    quick: bool = False,
    category: str | None = None,
    output_dir: str | Path | None = None,
) -> list[dict]:
    """生成轨迹。

    Args:
        quick: 如果为 True，每个模板只生成 2 条（用于测试）
        category: 如果指定，只生成该类别的轨迹
        output_dir: 输出目录，默认为 benchmark/scenarios/

    Returns:
        生成的轨迹列表
    """
    output_path = Path(output_dir) if output_dir else SCENARIOS_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    selected_templates = TEMPLATES
    if category:
        selected_templates = [t for t in TEMPLATES if t["category"] == category]
        if not selected_templates:
            print(f"Error: unknown category '{category}'")
            print(f"Available: {_available_categories()}")
            return []

    all_trajectories = []
    total_expected = sum(
        min(t["count"], 2 if quick else t["count"]) for t in selected_templates
    )

    print(f"Generating {total_expected} trajectories...")
    print(f"  Output: {output_path}")
    print(f"  Quick mode: {quick}")
    if category:
        print(f"  Category filter: {category}")
    print()

    seed = 0
    generated = 0
    for template in selected_templates:
        count = min(template["count"], 2 if quick else template["count"])
        gen_fn = GENERATORS.get(template["generator"])
        if gen_fn is None:
            print(f"  ⚠️  Unknown generator: {template['generator']}, skipping")
            continue

        for _ in range(count):
            seed += 1
            try:
                trajectory = gen_fn(template, seed)
                all_trajectories.append(trajectory)
                generated += 1
            except Exception as e:
                print(f"  ❌ Error generating (seed={seed}): {e}")

    # 写入 JSON 文件（每个轨迹单独一个文件）
    for traj in all_trajectories:
        filepath = output_path / f"{traj['trajectory_id']}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(traj, f, ensure_ascii=False, indent=2)

    # 也写一个合并的 JSON（方便评估脚本一次性加载）
    manifest = {
        "total": len(all_trajectories),
        "generated_at": "synthetic",
        "categories": _category_counts(all_trajectories),
        "files": [t["trajectory_id"] + ".json" for t in all_trajectories],
    }
    with open(output_path / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Generated {generated} trajectories to {output_path}/")
    for cat, cnt in _category_counts(all_trajectories).items():
        print(f"   {cat}: {cnt}")

    return all_trajectories


def _available_categories() -> list[str]:
    cats = sorted(set(t["category"] for t in TEMPLATES))
    return cats


def _category_counts(trajectories: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in trajectories:
        cat = t["task_category"]
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def main():
    parser = argparse.ArgumentParser(description="LoopBuster benchmark trajectory generator")
    parser.add_argument("--quick", action="store_true", help="Generate only 2 per template (test mode)")
    parser.add_argument("--category", type=str, default=None, help="Filter by category")
    args = parser.parse_args()

    generate(quick=args.quick, category=args.category)


if __name__ == "__main__":
    main()
