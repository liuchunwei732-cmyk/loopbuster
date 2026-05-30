"""Similarity functions for comparing agent actions."""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Noise reduction patterns
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_SHORT_UUID_RE = re.compile(r"\b[0-9a-f]{32}\b", re.IGNORECASE)
_TS_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_HASH_RE = re.compile(r"\b[0-9a-f]{64}\b|\b[0-9a-f]{40}\b", re.IGNORECASE)
_RAND_ID_RE = re.compile(r"\b[a-zA-Z0-9_-]{20,}\b")

_NOISE_PATTERNS = [
    ("<UUID>", _UUID_RE),
    ("<UUID>", _SHORT_UUID_RE),
    ("<TIMESTAMP>", _TS_RE),
    ("<DATE>", _DATE_RE),
    ("<HASH>", _HASH_RE),
]

# Keys that are commonly volatile (exact match on key name)
_VOLATILE_KEYS = frozenset(
    {
        "timestamp",
        "created_at",
        "updated_at",
        "request_id",
        "trace_id",
        "session_id",
        "id",
        "_id",
        "uuid",
        "nonce",
        "csrf",
        "token",
        "signature",
        "hash",
    }
)


def _denoise_string(value: str) -> str:
    """Replace volatile substrings with placeholders."""
    if not isinstance(value, str):
        return str(value)
    for placeholder, pattern in _NOISE_PATTERNS:
        value = pattern.sub(placeholder, value)
    return value


def _is_volatile_key(key: str) -> bool:
    """Check if a key name indicates volatile data."""
    k = key.lower()
    return k in _VOLATILE_KEYS or k.endswith("_id") or k.endswith("_at")


def _normalize_value(
    value: Any,
    max_string_len: int = 2000,
    _depth: int = 0,
) -> Any:
    """Recursively normalize a value for comparison.

    - Strips volatile noise from strings
    - Replaces volatile dict keys with `<VOLATILE>`
    - Truncates long strings
    - Recurses into dicts and lists
    """
    if _depth > 10:
        return "<DEEP>"

    if value is None:
        return None

    if isinstance(value, str):
        cleaned = _denoise_string(value)
        if len(cleaned) > max_string_len:
            return cleaned[:max_string_len] + "<TRUNC>"
        return cleaned

    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _is_volatile_key(k):
                out[k] = "<VOLATILE>"
            else:
                out[k] = _normalize_value(v, max_string_len, _depth + 1)
        return out

    if isinstance(value, (list, tuple)):
        seq = [_normalize_value(v, max_string_len, _depth + 1) for v in value]
        # For short lists keep order; for very long lists treat as a set to
        # avoid false negatives when order is meaningless.
        if len(seq) > 20:
            try:
                seq = sorted(seq, key=lambda x: str(x))
            except TypeError:
                pass
        return seq

    return str(value)


# ---------------------------------------------------------------------------
# Similarity primitives
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Dict-structure similarity (new)
# ---------------------------------------------------------------------------


def _dict_structure_sim(d1: dict, d2: dict) -> float:
    """Compare two dicts by key overlap and value type matching.

    Returns 0.0 ~ 1.0.  This is cheap and handles nested shapes well.
    """
    if not d1 and not d2:
        return 1.0
    if not d1 or not d2:
        return 0.0

    keys1, keys2 = set(d1.keys()), set(d2.keys())
    key_sim = len(keys1 & keys2) / len(keys1 | keys2)

    matched = 0
    checked = 0
    for k in keys1 & keys2:
        v1, v2 = d1[k], d2[k]
        checked += 1
        if type(v1) is type(v2):
            matched += 1
            if isinstance(v1, dict):
                matched += _dict_structure_sim(v1, v2)
                checked += 1
            elif isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
                matched += 0.5  # vague bonus for same container type
                checked += 1

    type_sim = matched / checked if checked else 1.0
    return 0.6 * key_sim + 0.4 * type_sim


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def args_similarity(
    args1: dict | str | None,
    args2: dict | str | None,
    max_string_len: int = 2000,
) -> float:
    """Compare two action args. Supports dict and str.

    Blends structural similarity (for dicts) with textual similarity
    (Jaccard + edit distance) for a balanced score.
    """
    # Fast path: exact match after normalization
    n1 = _normalize_value(args1, max_string_len)
    n2 = _normalize_value(args2, max_string_len)

    if n1 == n2:
        return 1.0

    # If both are dicts, compute a blended score
    if isinstance(n1, dict) and isinstance(n2, dict):
        struct_sim = _dict_structure_sim(n1, n2)

        s1 = _normalize_args(n1)
        s2 = _normalize_args(n2)
        if s1 == s2:
            return max(0.95, struct_sim)

        j = token_jaccard(s1, s2)
        if max(len(s1), len(s2)) <= max_string_len:
            e = edit_similarity(s1, s2)
            text_sim = 0.5 * j + 0.5 * e
        else:
            text_sim = j

        # Weighted blend: structure matters when args are large / nested
        weight = min(0.5, 0.1 + 0.05 * (len(n1) + len(n2)))
        return (1 - weight) * text_sim + weight * struct_sim

    # Fallback: scalar or mixed types → stringify and compare
    s1 = _normalize_args(n1)
    s2 = _normalize_args(n2)
    if s1 == s2:
        return 1.0

    j = token_jaccard(s1, s2)
    if max(len(s1), len(s2)) <= max_string_len:
        e = edit_similarity(s1, s2)
        return 0.5 * j + 0.5 * e
    return j


def _normalize_args(args: dict | str | None) -> str:
    """Convert args to a normalized string for comparison.

    Kept for backward compatibility; prefer _normalize_value for new code.
    """
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
