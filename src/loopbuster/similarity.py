"""Similarity functions for comparing agent actions."""

from __future__ import annotations


def jaccard_similarity(a: set, b: set) -> float:
    """Jaccard index between two sets. Returns 0.0 ~ 1.0."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def token_jaccard(s1: str, s2: str) -> float:
    """Jaccard similarity on whitespace-split tokens."""
    return jaccard_similarity(set(s1.split()), set(s2.split()))


def normalized_edit_distance(s1: str, s2: str) -> float:
    """Normalized Levenshtein distance. Returns 0.0 (identical) ~ 1.0 (totally different).

    Uses O(min(m,n)) space dynamic programming.
    """
    if s1 == s2:
        return 0.0
    n, m = len(s1), len(s2)
    if n == 0 or m == 0:
        return 1.0

    if n > m:
        s1, s2, n, m = s2, s1, m, n

    prev = list(range(n + 1))
    curr = [0] * (n + 1)

    for j in range(1, m + 1):
        curr[0] = j
        for i in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                curr[i] = prev[i - 1]
            else:
                curr[i] = 1 + min(prev[i - 1], prev[i], curr[i - 1])
        prev, curr = curr, prev

    return prev[n] / max(n, m)


def edit_similarity(s1: str, s2: str) -> float:
    """Edit-distance-based similarity. Returns 0.0 (different) ~ 1.0 (identical)."""
    return 1.0 - normalized_edit_distance(s1, s2)


def args_similarity(
    args1: dict | str | None, args2: dict | str | None
) -> float:
    """Compare two action args. Supports dict and str.

    Blends Jaccard (fast, structural) with edit distance (precise, sequential)
    for a balanced similarity score.
    """
    s1 = _normalize_args(args1)
    s2 = _normalize_args(args2)
    if s1 == s2:
        return 1.0
    j = token_jaccard(s1, s2)
    if max(len(s1), len(s2)) <= 2000:
        e = edit_similarity(s1, s2)
        return 0.5 * j + 0.5 * e
    return j


def _normalize_args(args: dict | str | None) -> str:
    """Convert args to a normalized string for comparison."""
    if args is None:
        return ""
    if isinstance(args, str):
        return args
    if isinstance(args, dict):
        parts = []
        for k in sorted(args.keys()):
            v = args[k]
            parts.append(f"{k}={v}")
        return " ".join(parts)
    return str(args)
