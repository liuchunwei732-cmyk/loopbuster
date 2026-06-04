"""
similarity_backend — 可插拔相似度计算后端。

默认后端（DefaultSimilarityBackend）使用 Jaccard + 编辑距离，零依赖。
可选后端（EmbeddingSimilarityBackend）使用 Sentence-Transformers 或
OpenAI Embeddings 实现语义级相似度比较。

用法：
    from loopbuster.similarity_backend import DefaultSimilarityBackend

    backend = DefaultSimilarityBackend()
    score = backend.similarity({"q": "python"}, {"q": "python programming"})

    # Embedding 后端（需要安装 sentence-transformers）
    from loopbuster.similarity_backend import EmbeddingSimilarityBackend
    backend = EmbeddingSimilarityBackend(model_name="all-MiniLM-L6-v2")
    score = backend.similarity("Paris population is 2.1M", "Tokyo population is 14M")
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


# ======================================================================
# 抽象基类
# ======================================================================


class SimilarityBackend(ABC):
    """相似度计算后端抽象基类。所有后端必须实现 similarity() 方法。"""

    @abstractmethod
    def similarity(
        self, a: Any, b: Any, max_string_len: int = 2000
    ) -> float:
        """返回 a 与 b 的相似度，0.0（完全不同）~ 1.0（完全相同）。"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """后端的名称标识。"""
        ...

    def normalize(self, value: Any, max_string_len: int = 2000, _depth: int = 0) -> Any:
        """归一化用于比较的值——替换噪声、截断长字符串、标记易变 key。"""
        return _normalize_value(value, max_string_len, _depth)


# ======================================================================
# 默认后端（Jaccard + 编辑距离）
# ======================================================================


class DefaultSimilarityBackend(SimilarityBackend):
    """零依赖的默认后端。使用 Jaccard 系数 + 归一化编辑距离的混合评分。"""

    @property
    def name(self) -> str:
        return "default"

    def similarity(self, a: Any, b: Any, max_string_len: int = 2000) -> float:
        return _args_similarity(a, b, max_string_len)


# ======================================================================
# Embedding 后端（可选，需要 sentence-transformers）
# ======================================================================


class EmbeddingSimilarityBackend(SimilarityBackend):
    """基于 Sentence-Transformers 的语义相似度后端。

    将输入编码为固定维度的 embedding，然后用余弦相似度计算语义相似度。
    适用于需要理解"不同措辞但相同含义"和"相同措辞但不同含义"的场景。

    Args:
        model_name: Sentence-Transformer 模型名称，默认 "all-MiniLM-L6-v2"
            （384 维，速度与精度的平衡点）

    Raises:
        ImportError: 如果未安装 sentence-transformers
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "EmbeddingSimilarityBackend requires sentence-transformers.\n"
                "Install it with: pip install sentence-transformers"
            )
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name

    @property
    def name(self) -> str:
        return f"embedding({self._model_name})"

    def similarity(self, a: Any, b: Any, max_string_len: int = 2000) -> float:
        from numpy import dot
        from numpy.linalg import norm

        # 先归一化再编码
        a_str = self._to_text(a, max_string_len)
        b_str = self._to_text(b, max_string_len)

        emb_a = self._model.encode(a_str, normalize_embeddings=True)
        emb_b = self._model.encode(b_str, normalize_embeddings=True)

        cos_sim = float(dot(emb_a, emb_b) / (norm(emb_a) * norm(emb_b) + 1e-10))
        return max(0.0, min(1.0, cos_sim))

    @staticmethod
    def _to_text(value: Any, max_string_len: int = 2000) -> str:
        """将任意输入转换为用于编码的文本字符串。"""
        if isinstance(value, str):
            return value[:max_string_len]
        if isinstance(value, dict):
            parts = []
            for k in sorted(value.keys()):
                v = value[k]
                parts.append(f"{k}: {v}")
            return " ".join(parts)[:max_string_len]
        return str(value)[:max_string_len]


# ======================================================================
# 注册表
# ======================================================================

BACKENDS: dict[str, type[SimilarityBackend]] = {
    "default": DefaultSimilarityBackend,
    "embedding": EmbeddingSimilarityBackend,
}


def get_backend(name: str = "default", **kwargs) -> SimilarityBackend:
    """根据名称获取相似度后端实例。"""
    cls = BACKENDS.get(name)
    if cls is None:
        raise ValueError(f"Unknown backend: {name}. Available: {list(BACKENDS.keys())}")
    return cls(**kwargs)


# ======================================================================
# 以下是从 similarity.py 迁移的核心逻辑（保持零依赖默认后端）
# 注意：这是为了消除循环依赖。similarity.py 最终应迁移至此。
# ======================================================================


def _args_similarity(
    args1: dict | str | None,
    args2: dict | str | None,
    max_string_len: int = 2000,
) -> float:
    """比较两个 action args。支持 dict 和 str。"""
    n1 = _normalize_value(args1, max_string_len)
    n2 = _normalize_value(args2, max_string_len)

    if n1 == n2:
        return 1.0

    if isinstance(n1, dict) and isinstance(n2, dict):
        struct_sim = _dict_structure_sim(n1, n2)
        s1 = _normalize_args(n1)
        s2 = _normalize_args(n2)
        if s1 == s2:
            return max(0.95, struct_sim)
        j = _token_jaccard(s1, s2)
        if max(len(s1), len(s2)) <= max_string_len:
            e = _edit_similarity(s1, s2)
            text_sim = 0.5 * j + 0.5 * e
        else:
            text_sim = j
        weight = min(0.5, 0.1 + 0.05 * (len(n1) + len(n2)))
        return (1 - weight) * text_sim + weight * struct_sim

    s1 = _normalize_args(n1)
    s2 = _normalize_args(n2)
    if s1 == s2:
        return 1.0
    j = _token_jaccard(s1, s2)
    if max(len(s1), len(s2)) <= max_string_len:
        e = _edit_similarity(s1, s2)
        return 0.5 * j + 0.5 * e
    return j


# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_SHORT_UUID_RE = re.compile(r"\b[0-9a-f]{32}\b", re.IGNORECASE)
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_HASH_RE = re.compile(r"\b[0-9a-f]{64}\b|\b[0-9a-f]{40}\b", re.IGNORECASE)
_NOISE_PATTERNS = [
    ("<UUID>", _UUID_RE), ("<UUID>", _SHORT_UUID_RE),
    ("<TIMESTAMP>", _TS_RE), ("<DATE>", _DATE_RE), ("<HASH>", _HASH_RE),
]
_VOLATILE_KEYS = frozenset({
    "timestamp", "created_at", "updated_at", "request_id", "trace_id",
    "session_id", "id", "_id", "uuid", "nonce", "csrf", "token", "signature", "hash",
})


def _denoise_string(value: str) -> str:
    if not isinstance(value, str):
        return str(value)
    for placeholder, pattern in _NOISE_PATTERNS:
        value = pattern.sub(placeholder, value)
    return value


def _is_volatile_key(key: str) -> bool:
    k = key.lower()
    return k in _VOLATILE_KEYS or k.endswith("_id") or k.endswith("_at")


def _normalize_value(value: Any, max_string_len: int = 2000, _depth: int = 0) -> Any:
    if _depth > 10:
        return "<DEEP>"
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = _denoise_string(value)
        return cleaned[:max_string_len] + "<TRUNC>" if len(cleaned) > max_string_len else cleaned
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
        if len(seq) > 20:
            try:
                seq = sorted(seq, key=lambda x: str(x))
            except TypeError:
                pass
        return seq
    return str(value)


def _normalize_args(args: dict | str | None) -> str:
    if args is None:
        return ""
    if isinstance(args, str):
        return args
    if isinstance(args, dict):
        return " ".join(f"{k}={v}" for k, v in sorted(args.items()))
    return str(args)


# ---------------------------------------------------------------------------
# 相似度原语
# ---------------------------------------------------------------------------


def _jaccard_similarity(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _token_jaccard(s1: str, s2: str) -> float:
    return _jaccard_similarity(set(s1.split()), set(s2.split()))


def _normalized_edit_distance(s1: str, s2: str) -> float:
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


def _edit_similarity(s1: str, s2: str) -> float:
    return 1.0 - _normalized_edit_distance(s1, s2)


def _dict_structure_sim(d1: dict, d2: dict) -> float:
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
                matched += 0.5
                checked += 1
    type_sim = matched / checked if checked else 1.0
    return 0.6 * key_sim + 0.4 * type_sim
