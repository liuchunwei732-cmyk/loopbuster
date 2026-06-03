"""LoopBuster benchmark: 20 test scenarios with diverse edge cases.

Run:  python -m benchmark.scenarios

Tests cover:
  - Exact repeat detection (3 scenarios)
  - Cycle detection (2 scenarios)
  - Fuzzy repeat detection (2 scenarios)
  - Output stagnation (2 scenarios)
  - Noise denoising with volatile fields (2 scenarios)
  - Normal / non-looping behavior (5 scenarios)
  - Edge cases (4 scenarios)

Each scenario tests the full LoopBuster engine pipeline:
detection strategy → confidence scoring → escalation logic.
"""

from loopbuster import LoopBuster
from loopbuster.types import Action, ActionConfig
from loopbuster.strategies import (
    CycleDetectionStrategy,
    ExactRepeatStrategy,
    FuzzyRepeatStrategy,
    OutputStagnationStrategy,
)
from loopbuster.similarity import args_similarity
from loopbuster.types import ActionRecord


def run_benchmark():
    # Each scenario: (check_fn, expected_loop, description)
    scenarios = [
        # === Exact Repeat (3) — identity detection ===
        (
            lambda b: _check_seq(b, [("search", {"q": "a"}, None)] * 3),
            True,
            "3× identical search: exact repeat via engine escalation",
        ),
        (
            lambda b: _check_seq(b, [("search", {"q": "x"}, None)] * 5),
            True,
            "5× identical search: window fills, confidence=1.0",
        ),
        (
            lambda b: _check_seq(b, [("api_call", {"id": 1}, None)] * 3),
            True,
            "3× identical API call: exact repeat via engine escalation",
        ),
        # === Cycle Detection (2) — tool sequence patterns ===
        (
            lambda b: _check_seq(b,
                [("a", {}, None), ("b", {}, None)] * 4 + [("a", {}, None)]
            ),
            True,
            "A→B cycle × 4.5: cycle pattern recognized and escalated",
        ),
        (
            lambda b: _check_seq(b,
                [("a", {}, None), ("b", {}, None), ("c", {}, None)] * 3
            ),
            True,
            "A→B→C cycle × 3: 3-tool repeating sequence",
        ),
        # === Fuzzy Repeat (2) — args similarity after denoising ===
        (
            lambda b: _check_seq(b,
                [("search", {"q": "python error", "page": 1}, None),
                 ("search", {"q": "python error", "page": 2}, None),
                 ("search", {"q": "python error", "page": 3}, None),
                 ("search", {"q": "python error", "page": 4}, None)]
            ),
            True,
            "Same query with incrementing page: fuzzy similarity ≥0.85",
        ),
        (
            lambda b: _check_seq(b,
                [("search", {"q": "weather Tokyo", "locale": "en"}, None),
                 ("search", {"q": "weather Tokyo", "locale": "en-US"}, None),
                 ("search", {"q": "weather Tokyo", "locale": "en"}, None),
                 ("search", {"q": "weather Tokyo", "locale": "en-GB"}, None)]
            ),
            True,
            "Same query, different locale: structure + text similarity ≥0.85",
        ),
        # === Output Stagnation (2) — same output across calls ===
        (
            lambda b: _check_seq(b,
                [("search", {"q": "test"}, "same result")] * 3
            ),
            True,
            "3× same output: stagnation detected via OutputStagnation strategy",
        ),
        (
            lambda b: _check_seq(b,
                [("search", {"q": "test"}, "same result")] * 5
            ),
            True,
            "5× same output: stagnation confidence escalates to STOP",
        ),
        # === Noise Denoising (2) — volatile fields stripped ===
        (
            lambda b: _check_seq(b,
                [("search", {"q": "python",
                             "request_id": f"550e8400-e29b-41d4-a716-{i:012d}"}, None)
                 for i in range(4)]
            ),
            True,
            "4× same query with different UUIDs → denoised to 1.0 similarity",
        ),
        (
            lambda b: _check_seq(b,
                [("search", {"q": "python",
                             "ts": f"2024-01-{i:02d}T09:00:00Z"}, None)
                 for i in range(15, 19)]
            ),
            True,
            "4× same query with different timestamps → denoised to 1.0 sim",
        ),
        # === Normal / No Loop (5) ===
        (
            lambda b: _check_seq(b, [("search", {"q": "a"}, None)]),
            False,
            "Single call: no pattern to detect",
        ),
        (
            lambda b: _check_seq(b,
                [("search", {"q": str(i)}, None) for i in range(5)]
            ),
            False,
            "5 diverse search queries: no repeat, no cycle",
        ),
        (
            lambda b: _check_seq(b,
                [("search", {"q": "a"}, None),
                 ("search", {"q": "b"}, None),
                 ("search", {"q": "c"}, None)]
            ),
            False,
            "3 explore-mode queries: low confidence, no escalation",
        ),
        (
            lambda b: _check_seq(b,
                [("read", {"file": "a.txt"}, None),
                 ("write", {"file": "b.txt"}, None)]
            ),
            False,
            "Read+write different files: different tools, no pattern",
        ),
        (
            lambda b: _check_seq(b,
                [("search", {"q": "a"}, "result_a"),
                 ("search", {"q": "b"}, "result_b"),
                 ("search", {"q": "c"}, "result_c")]
            ),
            False,
            "Diverse outputs: no stagnation",
        ),
        # === Edge Cases (4) — robustness ===
        (
            lambda b: _check_seq(b, []),
            False,
            "Empty sequence: no actions, no detection",
        ),
        (
            lambda b: _check_seq(b,
                [("search", {"q": "python", "req_id": "req-1"}, None),
                 ("search", {"q": "machine learning", "req_id": "req-2"}, None)]
            ),
            False,
            "Different queries with volatile IDs: no false positive",
        ),
        (
            lambda b: _check_seq(b,
                [("search", {"query": "python",
                             "filters": {"location": "上海",
                                         "timestamp": "2024-01-15T09:00:00Z"}}, None),
                 ("search", {"query": "python",
                             "filters": {"location": "上海",
                                         "timestamp": "2024-01-16T10:00:00Z"}}, None),
                 ("search", {"query": "python",
                             "filters": {"location": "上海",
                                         "timestamp": "2024-06-15T08:30:00Z"}}, None),
                 ("search", {"query": "python",
                             "filters": {"location": "上海",
                                         "timestamp": "2025-01-01T00:00:00Z"}}, None)]
            ),
            True,
            "Nested dict with volatile timestamps→denoised identical→loop",
        ),
        (
            lambda b: _check_seq(b,
                [("api", {"ids": list(range(25))}, None),
                 ("api", {"ids": list(range(24, -1, -1))}, None),
                 ("api", {"ids": list(range(0, 25))}, None),
                 ("api", {"ids": list(range(24, -1, -1))}, None)]
            ),
            True,
            "Long list args reversed→set comparison→detected as loop",
        ),
    ]

    print("=" * 80)
    print("LoopBuster Benchmark — 20 Scenarios")
    print("=" * 80)

    tp, fp, fn, tn = 0, 0, 0, 0
    results = []

    for check_fn, expected, desc in scenarios:
        buster = LoopBuster(
            similarity_threshold=0.75,
            action_config=ActionConfig(
                warn_threshold=1,
                stop_threshold=2,
                escalate_threshold=3,
            ),
        )
        detected = check_fn(buster)

        status = "LOOP" if detected else "OK  "
        match = detected == expected

        if detected and expected:
            tp += 1
        elif detected and not expected:
            fp += 1
        elif not detected and expected:
            fn += 1
        else:
            tn += 1

        results.append((desc, status, match, expected))

    print()
    print(f"{'Scenario':<60} {'Status':<8} {'Match':<6} {'Expected':<8}")
    print("-" * 92)
    for desc, status, match, expected in results:
        exp_label = "LOOP" if expected else "NO  "
        match_mark = "✓" if match else "✗"
        print(f"{desc:<60} {status:<8} {match_mark:<6} {exp_label:<8}")

    print()
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print("-" * 92)
    print(f"Total scenarios: {len(scenarios)}")
    print(f"TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"Precision: {precision:.1%}")
    print(f"Recall:    {recall:.1%}")
    print(f"F1 Score:  {f1:.1%}")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")

    # ── Strategy-level diagnostics ──
    print()
    print("=" * 80)
    print("Strategy-Level Diagnostics (raw confidence ≥ 0.5)")
    print("=" * 80)
    _run_strategy_checks()


def _check_seq(buster, calls):
    """Run a sequence of tool calls through buster.
    Returns True if any call triggers is_loop (STOP or ESCALATE)."""
    if not calls:
        return False
    for tool, args, output in calls:
        d = buster.check(tool=tool, args=args, output=output)
        if d.is_loop:
            return True
    return False


def _run_strategy_checks():
    diagnostics = [
        ("ExactRepeat: 3× same (tool, args)", lambda: _check_exact(3)),
        ("ExactRepeat: 5× same (tool, args)", lambda: _check_exact(5)),
        ("FuzzyRepeat: page-variant args → denoised identical",
         _check_fuzzy_page),
        ("FuzzyRepeat: UUID-denoised args → identical",
         _check_fuzzy_uuid),
        ("CycleDetection: A-B-A-B-A-B sequence",
         _check_cycle),
        ("OutputStagnation: same output 3×",
         lambda: _check_stagnation(3)),
        ("OutputStagnation: same output 5×",
         lambda: _check_stagnation(5)),
        ("NoFP: different queries with volatile keys",
         _check_fp_diff_queries),
        ("NoFP: diverse tool set",
         _check_fp_diverse),
    ]

    for label, fn in diagnostics:
        try:
            result = fn()
            flag = "✓" if result else "✗"
        except Exception as e:
            result = False
            flag = "!"
            print(f"  {flag} {label:<55} ERROR: {e}")
            continue
        print(f"  {flag} {label:<57} {'pass' if result else 'FAIL'}")


def _check_exact(count):
    s = ExactRepeatStrategy(window_size=5)
    last = 0.0
    for i in range(count):
        c, _ = s.check(ActionRecord(tool="s", args={"q": "x"}, step=i))
        if c > 0:
            last = c
    return last >= 0.4


def _check_fuzzy_page():
    s = FuzzyRepeatStrategy(window_size=5, similarity_threshold=0.85)
    calls = [("search", {"q": "python error", "page": i}) for i in range(1, 5)]
    last = 0.0
    for i, (t, a) in enumerate(calls):
        c, _ = s.check(ActionRecord(tool=t, args=a, step=i))
        if c > 0:
            last = c
    return last >= 0.5


def _check_fuzzy_uuid():
    s = FuzzyRepeatStrategy(window_size=5, similarity_threshold=0.85)
    calls = [
        ("search", {"q": "python", "rid": "550e8400-e29b-41d4-a716-446655440000"}),
        ("search", {"q": "python", "rid": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"}),
        ("search", {"q": "python", "rid": "6ba7b811-9dad-11d1-80b4-00c04fd430c8"}),
    ]
    last = 0.0
    for i, (t, a) in enumerate(calls):
        c, _ = s.check(ActionRecord(tool=t, args=a, step=i))
        if c > 0:
            last = c
    return last >= 0.5


def _check_cycle():
    s = CycleDetectionStrategy(max_cycle_length=5, min_repetitions=2)
    pat = ["a", "b", "a", "b", "a", "b"]
    last = 0.0
    for i, t in enumerate(pat):
        c, _ = s.check(ActionRecord(tool=t, step=i))
        if c > 0:
            last = c
    return last >= 0.5


def _check_stagnation(count):
    s = OutputStagnationStrategy(window_size=4, similarity_threshold=0.8)
    last = 0.0
    for i in range(count):
        c, _ = s.check(ActionRecord(tool="search", output="same", step=i))
        if c > 0:
            last = c
    return last >= 0.5


def _check_fp_diff_queries():
    s = FuzzyRepeatStrategy(window_size=5, similarity_threshold=0.85)
    calls = [("search", {"q": "python", "rid": "r1"}),
             ("search", {"q": "machine learning", "rid": "r2"})]
    for i, (t, a) in enumerate(calls):
        c, _ = s.check(ActionRecord(tool=t, args=a, step=i))
        if c >= 0.5:
            return False
    return True


def _check_fp_diverse():
    s = FuzzyRepeatStrategy(window_size=5, similarity_threshold=0.85)
    calls = [("search", {"q": "a"}), ("read", {"f": "x.txt"}),
             ("write", {"f": "y.txt"}), ("api", {"id": 1})]
    for i, (t, a) in enumerate(calls):
        c, _ = s.check(ActionRecord(tool=t, args=a, step=i))
        if c >= 0.5:
            return False
    return True


if __name__ == "__main__":
    run_benchmark()
