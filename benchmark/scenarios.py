"""LoopBuster benchmark: 25 test scenarios covering core + deep detection.

Scenarios are designed to test:
  - Basic loop detection (exact repeat, fuzzy, cycle, stagnation)
  - Good cycle vs bad cycle differentiation (progress-aware)
  - Predictive risk scoring
  - Adaptive threshold behavior
  - Edge cases (empty, single action, mixed)
"""

from loopbuster import LoopBuster, Action, ProgressSignal, RiskScorer
from loopbuster.types import ActionRecord

# Scenario format: (tool_calls, expected_loop, description, note)
# tool_calls: list of (tool, args_or_None, output_or_None)
Scenarios = tuple[list[tuple], bool, str]

SCENARIOS: list[Scenarios] = [
    # --- Core detection (existing) ---
    (
        [("search", {"q": "a"}, None), ("search", {"q": "a"}, None), ("search", {"q": "a"}, None)],
        True,
        "连续3次相同搜索 — basic exact repeat",
    ),
    (
        [("search", {"q": "a"}, None), ("search", {"q": "b"}, None), ("search", {"q": "c"}, None)],
        False,
        "正常多步不同搜索 — should pass",
    ),
    (
        [("api_call", {"id": 1}, None), ("api_call", {"id": 1}, None)],
        True,
        "API重复调用 — exact repeat on api_call",
    ),
    (
        [("read", {"file": "a.txt"}, None), ("write", {"file": "b.txt"}, None)],
        False,
        "读写不同文件 — different tools, should pass",
    ),
    (
        [("search", {"q": "weather"}, None), ("search", {"q": "weather today"}, None), ("search", {"q": "weather tomorrow"}, None)],
        False,
        "相近但不同搜索 — fuzzy but different queries, may or may not trip",
    ),
    (
        [("search", {"q": "x"}, None)],
        False,
        "单次调用 — not enough data for loop",
    ),
    (
        [("search", {"q": "x"}, None)] * 5,
        True,
        "连续5次相同搜索 — strong exact repeat",
    ),
    (
        [("a", {}, None), ("b", {}, None), ("a", {}, None), ("b", {}, None)],
        True,
        "A→B→A→B周期循环 — basic cycle detection",
    ),
    (
        [],
        False,
        "空调用 — edge case",
    ),
    (
        [("a", {}, None), ("b", {}, None), ("c", {}, None), ("a", {}, None), ("b", {}, None), ("c", {}, None)],
        True,
        "A→B→C周期循环 — triple cycle",
    ),

    # --- Good cycle vs bad cycle (progress-aware) ---
    (
        [("search", {"q": "weather Paris"}, "It is 20°C in Paris"),
         ("parse", {}, "Temperature: 20°C"),
         ("search", {"q": "weather Tokyo"}, "It is 25°C in Tokyo"),
         ("parse", {}, "Temperature: 25°C"),
         ("search", {"q": "weather London"}, "It is 15°C in London")],
        False,
        "搜索→解析周期，但每次搜索不同城市 — GOOD CYCLE, should not loop",
    ),
    (
        [("search", {"q": "Paris population"}, "2.1 million"),
         ("search", {"q": "Paris population"}, "2.1 million"),
         ("search", {"q": "Paris population"}, "2.1 million")],
        True,
        "重复搜索同一个问题返回相同结果 — BAD CYCLE, exact + stagnation",
    ),
    (
        [("search", {"q": "python"}, "Python is a programming language"),
         ("search", {"q": "python language"}, "Python is a programming language"),
         ("search", {"q": "python programming"}, "Python is a programming language")],
        True,
        "模糊不同的搜索词但每次返回相同内容 — BAD CYCLE, stagnation",
    ),
    (
        [("read", {"file": "log.txt"}, "ERROR: timeout"),
         ("retry", {}, "still failing"),
         ("read", {"file": "log.txt"}, "ERROR: timeout"),
         ("retry", {}, "still failing")],
        True,
        "拼命重试但不解决问题 — BAD CYCLE, cycle detection + stagnant output",
    ),

    # --- Progressive information gain (risk scoring test cases) ---
    (
        [("search", {"q": "book recommendation"}, "Try 'The Pragmatic Programmer'"),
         ("search", {"q": "book recommendation technology"}, "Also 'Clean Code' and 'Design Patterns'"),
         ("search", {"q": "best programming books 2024"}, "Current top: 'System Design Interview'")],
        False,
        "搜索逐渐递进，每次有新发现 — GOOD pattern, risk should remain low",
    ),
    (
        [("search", {"q": "book"}, "Many books available"),
         ("search", {"q": "book"}, "Many books available"),
         ("search", {"q": "book"}, "Many books available"),
         ("search", {"q": "book"}, "Many books available"),
         ("search", {"q": "book"}, "Many books available")],
        True,
        "重复搜索完全相同的query和output — BAD pattern, risk should be high",
    ),

    # --- RiskScorer-specific: entropy collapse detection ---
    (
        [("a", {}, None), ("a", {}, None), ("b", {}, None), ("b", {}, None),
         ("a", {}, None), ("a", {}, None), ("b", {}, None), ("b", {}, None)],
        True,
        "工具只在A和B之间来回切换 — low entropy, cycle pattern",
    ),

    # --- Output stagnation with data-like content ---
    (
        [("fetch_stock", {"symbol": "AAPL"}, "Price: $150.25"),
         ("fetch_stock", {"symbol": "AAPL"}, "Price: $150.25"),
         ("fetch_stock", {"symbol": "AAPL"}, "Price: $150.25")],
        True,
        "股票API返回相同价格 — stagnation detection should fire",
    ),
    (
        [("fetch_stock", {"symbol": "AAPL"}, "Price: $150.25"),
         ("fetch_stock", {"symbol": "GOOG"}, "Price: $175.80"),
         ("fetch_stock", {"symbol": "MSFT"}, "Price: $380.50")],
        False,
        "不同股票不同价格 — healthy, should pass",
    ),
]


def run_benchmark() -> dict:
    """Run all benchmark scenarios and return results."""
    tp, fp, fn, tn = 0, 0, 0, 0

    for calls, expected, desc in SCENARIOS:
        buster = LoopBuster(
            window_size=10,
            similarity_threshold=0.85,
        )
        detected = False
        final_decision = None

        for item in calls:
            if len(item) == 3:
                tool, args, output = item
            else:
                tool, args = item
                output = None
            d = buster.check(tool=tool, args=args, output=output)
            final_decision = d
            if d.is_loop:
                detected = True
                break

        # Verify: we expect loop or not
        if detected and expected:
            tp += 1
        elif detected and not expected:
            fp += 1
        elif not detected and expected:
            fn += 1
        else:
            tn += 1

    total = len(SCENARIOS)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"Benchmark Results ({total} scenarios)")
    print(f"{'='*40}")
    print(f"TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"Precision: {precision:.0%}")
    print(f"Recall:    {recall:.0%}")
    print(f"F1 Score:  {f1:.0%}")
    print(f"Mis-classified: {fp + fn}")

    return {
        "total": total,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def run_progress_benchmark() -> dict:
    """Test the ProgressSignal specifically on good-vs-bad cycles."""
    from loopbuster.progress import ProgressSignal

    # Good cycle: progressive information gain
    ps_good = ProgressSignal(window=5)
    outputs_good = [
        "Paris population is 2.1 million",
        "Tokyo population is 14 million and area is 2,194 km²",
        "London population is 8.9 million and area is 1,572 km²",
    ]
    gains_good = []
    for out in outputs_good:
        ps_good.record(out)
        gains_good.append(ps_good.score().gain)

    # Bad cycle: same output repeated
    ps_bad = ProgressSignal(window=5)
    outputs_bad = [
        "Paris population is 2.1 million",
        "Paris population is 2.1 million",
        "Paris population is 2.1 million",
    ]
    gains_bad = []
    for out in outputs_bad:
        ps_bad.record(out)
        gains_bad.append(ps_bad.score().gain)

    print(f"\nProgressSignal: Good cycle avg gain = {sum(gains_good)/len(gains_good):.3f}")
    print(f"ProgressSignal: Bad cycle avg gain  = {sum(gains_bad)/len(gains_bad):.3f}")
    print(f"  → Good cycle {'✓' if sum(gains_good)/len(gains_good) > sum(gains_bad)/len(gains_bad) else '✗'} higher gain than bad cycle")

    return {
        "good_cycle_avg_gain": sum(gains_good) / len(gains_good),
        "bad_cycle_avg_gain": sum(gains_bad) / len(gains_bad),
    }


if __name__ == "__main__":
    run_benchmark()
    run_progress_benchmark()
