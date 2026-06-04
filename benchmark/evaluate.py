#!/usr/bin/env python3
"""
benchmark/evaluate.py — LoopBuster 评估脚本

从 benchmark/scenarios/ 加载轨迹，用 LoopBuster 逐条检测，
输出 precision / recall / F1（总体 + 按类型分层）。

用法：
    python benchmark/evaluate.py                          # 全量评估
    python benchmark/evaluate.py --quick                  # 快速（只加载 50 条）
    python benchmark/evaluate.py --output results.json    # 输出 JSON 结果
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loopbuster import Action, ActionConfig, LoopBuster
from loopbuster.types import ActionRecord


def load_scenarios(scenarios_dir: str | Path, max_count: int | None = None) -> list[dict]:
    """从目录加载全部轨迹 JSON。"""
    scenarios_path = Path(scenarios_dir)
    if not scenarios_path.exists():
        print(f"Scenario directory not found: {scenarios_path}")
        print(f"Run 'python benchmark/generator.py' first.")
        sys.exit(1)

    trajectories = []
    for fpath in sorted(scenarios_path.glob("synth_*.json")):
        with open(fpath, "r", encoding="utf-8") as f:
            trajectories.append(json.load(f))
        if max_count and len(trajectories) >= max_count:
            break

    print(f"Loaded {len(trajectories)} trajectories from {scenarios_path}/")
    return trajectories


def evaluate_trajectory(trajectory: dict, lb: LoopBuster) -> dict:
    """用 LoopBuster 检测一条轨迹，返回检测结果。"""
    lb.reset()
    ground_truth = trajectory["ground_truth"]
    expected_loop = ground_truth["is_loop"]
    actions = trajectory["actions"]
    total = len(actions)

    detected_warn = False
    detected_stop = False
    final_decision = None
    step_warn_at = None
    step_stop_at = None

    for idx, action in enumerate(actions):
        tool = action["tool"]
        args = action.get("args") or {}
        output = action.get("output")

        decision = lb.check(tool=tool, args=args, output=output)

        if decision.should_warn and not detected_warn:
            detected_warn = True
            step_warn_at = idx + 1
        if decision.is_loop and not detected_stop:
            detected_stop = True
            step_stop_at = idx + 1
            if final_decision is None:
                final_decision = decision

    # detected = WARN 或 STOP。对于短轨迹（<5步），WARN 也算检测到，
    # 因为轨迹在触发 STOP 之前就结束了。
    # 对于长轨迹，只算 STOP/ESCALATE。
    if total < 5:
        detected = detected_warn
    else:
        detected = detected_stop

    # 结果分类
    tp = detected and expected_loop
    fp = detected and not expected_loop
    fn = not detected and expected_loop
    tn = not detected and not expected_loop

    return {
        "trajectory_id": trajectory["trajectory_id"],
        "category": trajectory["task_category"],
        "loop_type": ground_truth["loop_type"],
        "expected_loop": expected_loop,
        "detected": detected,
        "detected_warn": detected_warn,
        "detected_stop": detected_stop,
        "step_warn_at": step_warn_at,
        "step_stop_at": step_stop_at,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "strategy": final_decision.strategy if final_decision else None,
        "reason": final_decision.reason if final_decision else None,
        "total_steps": total,
    }


def compute_metrics(results: list[dict]) -> dict:
    """从逐条结果计算指标。"""
    tp = sum(r["tp"] for r in results)
    fp = sum(r["fp"] for r in results)
    fn = sum(r["fn"] for r in results)
    tn = sum(r["tn"] for r in results)

    denom_prec = tp + fp
    denom_rec = tp + fn
    denom_acc = tp + tn + fp + fn

    precision = tp / denom_prec if denom_prec > 0 else 0.0
    recall = tp / denom_rec if denom_rec > 0 else 1.0  # if no positive, recall=1
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / denom_acc if denom_acc > 0 else 0.0

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "total": len(results),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


def compute_metrics_by(results: list[dict], key: str) -> dict:
    """按某个 key（loop_type / category）分层计算指标。

    将 None key 转换为 "none" 以避免排序和格式化错误。
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        k = r.get(key) or "none"
        groups[k].append(r)

    metrics = {}
    for k, items in sorted(groups.items()):
        metrics[k] = compute_metrics(items)
        metrics[k]["count"] = len(items)
    return metrics


def format_row(label: str, m: dict) -> str:
    """格式化一行指标输出。"""
    prec_s = f"{m['precision']:.0%}" if m['precision'] > 0 else "-"
    rec_s = f"{m['recall']:.0%}" if m['recall'] > 0 else "-"
    f1_s = f"{m['f1']:.0%}" if m['f1'] > 0 else "-"
    return f"  {label:<20} {m['count']:>6} {prec_s:>8} {rec_s:>8} {f1_s:>8} {m['fp']:>4}"


def print_results(overall: dict, by_type: dict, by_category: dict, results_raw: list | None = None) -> None:
    """打印格式化的评估结果。"""
    print()
    print("=" * 60)
    print("  LoopBuster Benchmark Results")
    print("=" * 60)
    print()
    print(f"  Total scenarios:   {overall['total']}")
    print(f"  TP: {overall['tp']}  FP: {overall['fp']}  FN: {overall['fn']}  TN: {overall['tn']}")
    print()
    print(f"  Precision:  {overall['precision']:.2%}")
    print(f"  Recall:     {overall['recall']:.2%}")
    print(f"  F1 Score:   {overall['f1']:.2%}")
    print(f"  Accuracy:   {overall['accuracy']:.2%}")
    print()

    hdr = f"  {'Type':<20} {'Count':>6} {'Prec':>8} {'Recall':>8} {'F1':>8} {'FP':>4}"
    sep = "  " + "-" * 50

    print(sep)
    print("  By Loop Type:")
    print(hdr)
    print(sep)
    for lt, m in sorted(by_type.items(), key=lambda x: str(x[0])):
        print(format_row(lt, m))
    print()

    print(sep)
    print("  By Category:")
    print(hdr)
    print(sep)
    for cat, m in sorted(by_category.items(), key=lambda x: str(x[0])):
        print(format_row(cat, m))
    print()

    # 误报
    fps = [r for r in (results_raw or []) if r["fp"]]
    print(sep)
    print("  False Positives:")
    print(sep)
    if fps:
        for fp in fps[:10]:
            print(f"  ❌ {fp['trajectory_id']} ({fp['category']}, {fp['loop_type']}): "
                  f"reason={fp.get('reason', 'N/A')}")
        if len(fps) > 10:
            print(f"  ... and {len(fps) - 10} more")
    else:
        print("  ✅ None")
    print()

    # 漏报
    fns_list = [r for r in (results_raw or []) if r["fn"]]
    if fns_list:
        print(f"  False Negatives: {len(fns_list)}")
        for fn_item in fns_list[:10]:
            print(f"  ⚠️  {fn_item['trajectory_id']} ({fn_item['category']}, "
                  f"type={fn_item['loop_type']}, steps={fn_item['total_steps']})")
        if len(fns_list) > 10:
            print(f"  ... and {len(fns_list) - 10} more")
    else:
        print("  ✅ No false negatives!")


def save_results(original_results: list[dict], overall: dict, by_type: dict,
                 by_category: dict, output_path: str | None) -> None:
    """保存结果为 JSON（可选）和 Markdown。"""
    if output_path:
        out = {
            "overall": overall,
            "by_loop_type": by_type,
            "by_category": by_category,
            "details": original_results,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"  Results saved to {output_path}")

    # 写 RESULTS.md
    results_dir = Path(__file__).resolve().parent
    md_path = results_dir / "RESULTS.md"

    lines = []
    lines.append("# LoopBuster Benchmark Results\n")
    lines.append(f"*Generated: synthetic benchmark ({overall['total']} scenarios)*\n")
    lines.append("## Overall\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total Scenarios | {overall['total']} |")
    lines.append(f"| TP | {overall['tp']} |")
    lines.append(f"| FP | {overall['fp']} |")
    lines.append(f"| FN | {overall['fn']} |")
    lines.append(f"| TN | {overall['tn']} |")
    lines.append(f"| Precision | {overall['precision']:.2%} |")
    lines.append(f"| Recall | {overall['recall']:.2%} |")
    lines.append(f"| F1 Score | {overall['f1']:.2%} |")
    lines.append(f"| Accuracy | {overall['accuracy']:.2%} |")
    lines.append("")

    lines.append("## By Loop Type\n")
    lines.append("| Type | Count | Precision | Recall | F1 | FP |")
    lines.append("|---|---|---|---|---|---|")
    for lt, m in sorted(by_type.items(), key=lambda x: str(x[0])):
        prec = f"{m['precision']:.0%}" if m['precision'] > 0 else "-"
        rec = f"{m['recall']:.0%}" if m['recall'] > 0 else "-"
        f1 = f"{m['f1']:.0%}" if m['f1'] > 0 else "-"
        lines.append(f"| {lt} | {m['count']} | {prec} | {rec} | {f1} | {m['fp']} |")
    lines.append("")

    lines.append("## By Category\n")
    lines.append("| Category | Count | Precision | Recall | F1 | FP |")
    lines.append("|---|---|---|---|---|---|")
    for cat, m in sorted(by_category.items(), key=lambda x: str(x[0])):
        prec = f"{m['precision']:.0%}" if m['precision'] > 0 else "-"
        rec = f"{m['recall']:.0%}" if m['recall'] > 0 else "-"
        f1 = f"{m['f1']:.0%}" if m['f1'] > 0 else "-"
        lines.append(f"| {cat} | {m['count']} | {prec} | {rec} | {f1} | {m['fp']} |")
    lines.append("")

    fps = [r for r in original_results if r["fp"]]
    if fps:
        lines.append("## False Positives\n")
        for fp in fps:
            lines.append(f"- `{fp['trajectory_id']}` ({fp['category']}, {fp['loop_type']}): {fp.get('reason', 'N/A')}")
        lines.append("")

    fns_list = [r for r in original_results if r["fn"]]
    if fns_list:
        lines.append("## False Negatives\n")
        for fn_item in fns_list:
            lines.append(f"- `{fn_item['trajectory_id']}` ({fn_item['category']}, "
                         f"type={fn_item['loop_type']}, steps={fn_item['total_steps']})")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Results saved to {md_path}")


def main():
    parser = argparse.ArgumentParser(description="LoopBuster benchmark evaluator")
    parser.add_argument("--quick", action="store_true", help="Only evaluate 50 trajectories")
    parser.add_argument("--output", type=str, default=None, help="Save detailed results to JSON")
    parser.add_argument("--scenarios-dir", type=str, default=None,
                        help="Path to scenarios directory")
    args = parser.parse_args()

    scenarios_dir = args.scenarios_dir or (Path(__file__).resolve().parent / "scenarios")
    max_count = 50 if args.quick else None
    trajectories = load_scenarios(scenarios_dir, max_count)

    if not trajectories:
        print("No trajectories found. Run 'python benchmark/generator.py' first.")
        return

    # 使用较宽松的阈值以覆盖短轨迹场景
    # warn=1 意味着任何 >0.3 置信度的检测立即触发 WARN
    lb = LoopBuster(
        similarity_threshold=0.85,
        action_config=ActionConfig(
            warn_threshold=1,
            stop_threshold=4,
            escalate_threshold=6,
        ),
    )

    results = []
    for traj in trajectories:
        result = evaluate_trajectory(traj, lb)
        results.append(result)

    overall = compute_metrics(results)
    by_type = compute_metrics_by(results, "loop_type")
    by_category = compute_metrics_by(results, "category")

    print_results(overall, by_type, by_category, results_raw=results)
    save_results(results, overall, by_type, by_category, args.output)


if __name__ == "__main__":
    main()
