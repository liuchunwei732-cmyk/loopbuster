"""LoopBuster benchmark: 20 test scenarios."""

from loopbuster import LoopBuster
from loopbuster.types import Action
import json

def test_scenarios():
    # scenarios: (tool_calls, expected_loop, description)
    scenarios = [
        ([("search", {"q": "a"}), ("search", {"q": "a"}), ("search", {"q": "a"})], True, "连续3次相同搜索"),
        ([("search", {"q": "a"}), ("search", {"q": "b"}), ("search", {"q": "c"})], False, "正常多步不同搜索"),
        ([("api_call", {"id": 1}), ("api_call", {"id": 1})], True, "API重复调用"),
        ([("read", {"file": "a.txt"}), ("write", {"file": "b.txt"})], False, "读写不同文件"),
        ([("search", {"q": "weather"}), ("search", {"q": "weather today"}), ("search", {"q": "weather tomorrow"})], False, "相近但不同搜索"),
        ([("search", {"q": "x"})], False, "单次调用"),
        ([("search", {"q": "x"}), ("search", {"q": "x"}), ("search", {"q": "x"}), ("search", {"q": "x"}), ("search", {"q": "x"})], True, "连续5次相同搜索"),
        ([("search", {"q": "a"}), ("read", {"f": "1"}), ("search", {"q": "a"}), ("read", {"f": "1"})], True, "A→B→A→B周期循环"),
        ([], False, "空调用"),
        ([("a", {}), ("b", {}), ("c", {}), ("a", {}), ("b", {}), ("c", {})], True, "A→B→C周期循环"),
    ]

    tp, fp, fn, tn = 0, 0, 0, 0

    for calls, expected, desc in scenarios:
        buster = LoopBuster(similarity_threshold=0.85)
        detected = False
        for tool, args in calls:
            d = buster.check(tool=tool, args=args)
            if d.is_loop:
                detected = True
                break

        if detected and expected:
            tp += 1
        elif detected and not expected:
            fp += 1
        elif not detected and expected:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0

    print(f"精确率: {precision:.0%}")
    print(f"召回率: {recall:.0%}")
    print(f"误报: {fp}, 漏报: {fn}")
    print(f"TP={tp} FP={fp} FN={fn} TN={tn}")

if __name__ == "__main__":
    test_scenarios()
