"""Tests for enhanced similarity and noise reduction."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from loopbuster.similarity import (
    _denoise_string,
    _dict_structure_sim,
    _is_volatile_key,
    _normalize_value,
    args_similarity,
    edit_similarity,
    token_jaccard,
)
from loopbuster.strategies import FuzzyRepeatStrategy, OutputStagnationStrategy
from loopbuster.types import ActionRecord


# ======================================================================
# Noise reduction
# ======================================================================


class TestDenoiseString:
    def test_uuid_replacement(self):
        uid = str(uuid.uuid4())
        s = f"user-{uid}-profile"
        assert _denoise_string(s) == "user-<UUID>-profile"

    def test_short_uuid_replacement(self):
        s = "prefix-1234567890abcdef1234567890abcdef-suffix"
        assert _denoise_string(s) == "prefix-<UUID>-suffix"

    def test_timestamp_replacement(self):
        s = "created_at=2024-01-15T09:30:00Z"
        assert _denoise_string(s) == "created_at=<TIMESTAMP>"

    def test_date_replacement(self):
        s = "date=2024-01-15"
        assert _denoise_string(s) == "date=<DATE>"

    def test_hash_replacement(self):
        h = "a" * 64
        s = f"sha256={h}"
        assert _denoise_string(s) == "sha256=<HASH>"

    def test_multiple_patterns(self):
        uid = str(uuid.uuid4())
        ts = "2024-01-15T09:30:00Z"
        s = f"req-{uid}-at-{ts}"
        assert _denoise_string(s) == "req-<UUID>-at-<TIMESTAMP>"


class TestVolatileKeys:
    def test_exact_match(self):
        assert _is_volatile_key("timestamp")
        assert _is_volatile_key("request_id")
        assert _is_volatile_key("nonce")

    def test_suffix_match(self):
        assert _is_volatile_key("order_id")
        assert _is_volatile_key("created_at")

    def test_non_volatile(self):
        assert not _is_volatile_key("query")
        assert not _is_volatile_key("name")
        assert not _is_volatile_key("limit")


class TestNormalizeValue:
    def test_simple_dict(self):
        d = {"q": "python", "limit": 10}
        assert _normalize_value(d) == {"q": "python", "limit": 10}

    def test_volatile_keys_masked(self):
        d = {"q": "python", "timestamp": "2024-01-15T09:30:00Z", "request_id": str(uuid.uuid4())}
        out = _normalize_value(d)
        assert out["q"] == "python"
        assert out["timestamp"] == "<VOLATILE>"
        assert out["request_id"] == "<VOLATILE>"

    def test_nested_dict(self):
        d = {
            "query": "test",
            "meta": {
                "created_at": "2024-01-15T09:30:00Z",
                "author": "alice",
            },
        }
        out = _normalize_value(d)
        assert out["query"] == "test"
        assert out["meta"]["created_at"] == "<VOLATILE>"
        assert out["meta"]["author"] == "alice"

    def test_string_truncation(self):
        long_str = "x" * 3000
        out = _normalize_value(long_str, max_string_len=2000)
        assert out.endswith("<TRUNC>")
        assert len(out) == 2000 + len("<TRUNC>")

    def test_list_normalization(self):
        d = {"items": ["a", "b", str(uuid.uuid4())]}
        out = _normalize_value(d)
        assert out["items"] == ["a", "b", "<UUID>"]

    def test_long_list_sorted(self):
        d = {"items": list(range(25))}
        out = _normalize_value(d)
        # Should be sorted when length > 20 (sorted by string repr)
        assert out["items"] == sorted(out["items"], key=lambda x: str(x))


# ======================================================================
# Structural similarity
# ======================================================================


class TestDictStructureSim:
    def test_identical_dicts(self):
        d = {"a": 1, "b": "x"}
        assert _dict_structure_sim(d, d) == 1.0

    def test_partial_overlap(self):
        d1 = {"a": 1, "b": 2}
        d2 = {"a": 1, "c": 3}
        sim = _dict_structure_sim(d1, d2)
        assert 0.3 < sim < 0.7

    def test_nested(self):
        d1 = {"q": "test", "meta": {"page": 1}}
        d2 = {"q": "test", "meta": {"page": 2}}
        sim = _dict_structure_sim(d1, d2)
        assert sim > 0.8  # same structure, different scalar values

    def test_empty_dicts(self):
        assert _dict_structure_sim({}, {}) == 1.0

    def test_one_empty(self):
        assert _dict_structure_sim({"a": 1}, {}) == 0.0


# ======================================================================
# Enhanced args_similarity
# ======================================================================


class TestArgsSimilarityEnhanced:
    def test_exact_match_after_denoising(self):
        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        a1 = {"q": "python", "request_id": uid1}
        a2 = {"q": "python", "request_id": uid2}
        assert args_similarity(a1, a2) == 1.0

    def test_different_queries_low_similarity(self):
        a1 = {"q": "python tutorial"}
        a2 = {"q": "machine learning"}
        sim = args_similarity(a1, a2)
        assert sim < 0.5

    def test_nested_dict_similarity(self):
        a1 = {
            "query": "dental",
            "filters": {"location": "嘉兴", "timestamp": "2024-01-15T09:00:00Z"},
        }
        a2 = {
            "query": "dental",
            "filters": {"location": "嘉兴", "timestamp": "2024-01-16T10:00:00Z"},
        }
        sim = args_similarity(a1, a2)
        assert sim > 0.85  # timestamps masked, rest identical

    def test_string_vs_dict(self):
        sim = args_similarity("hello", {"q": "hello"})
        assert 0.0 <= sim <= 1.0

    def test_none_handling(self):
        assert args_similarity(None, None) == 1.0
        assert args_similarity(None, "x") < 1.0

    def test_long_text_truncation(self):
        long1 = "word " * 3000
        long2 = "word " * 3000
        sim = args_similarity(long1, long2, max_string_len=500)
        assert sim == 1.0  # identical after truncation


# ======================================================================
# Strategy integration
# ======================================================================


class TestFuzzyRepeatWithNoise:
    def test_ignores_uuid_in_args(self):
        s = FuzzyRepeatStrategy(window_size=3, similarity_threshold=0.85)
        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())

        s.check(ActionRecord(tool="search", args={"q": "cat", "req_id": uid1}, step=1))
        s.check(ActionRecord(tool="search", args={"q": "cat", "req_id": uid2}, step=2))
        c, r = s.check(ActionRecord(tool="search", args={"q": "cat", "req_id": uid1}, step=3))

        assert c >= 0.85, f"Expected high confidence but got {c}: {r}"
        assert "Fuzzy repeat" in r

    def test_ignores_timestamp_in_args(self):
        s = FuzzyRepeatStrategy(window_size=3, similarity_threshold=0.85)

        s.check(ActionRecord(tool="api", args={"q": "test", "ts": "2024-01-01T00:00:00Z"}, step=1))
        s.check(ActionRecord(tool="api", args={"q": "test", "ts": "2024-01-02T12:00:00Z"}, step=2))
        c, r = s.check(ActionRecord(tool="api", args={"q": "test", "ts": "2024-06-15T08:30:00Z"}, step=3))

        assert c >= 0.85, f"Expected high confidence but got {c}: {r}"


class TestOutputStagnationWithNoise:
    def test_ignores_timestamp_in_output(self):
        s = OutputStagnationStrategy(window_size=4, similarity_threshold=0.90)

        out1 = "Results fetched at 2024-01-01T09:00:00Z: [item1, item2]"
        out2 = "Results fetched at 2024-01-01T09:05:00Z: [item1, item2]"

        s.check(ActionRecord(tool="search", args=None, output=out1, step=1))
        s.check(ActionRecord(tool="search", args=None, output=out2, step=2))
        c, r = s.check(ActionRecord(tool="search", args=None, output=out1, step=3))

        assert c >= 0.90, f"Expected stagnation detection but got {c}: {r}"
        assert "Output stagnation" in r
