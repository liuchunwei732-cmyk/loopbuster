
import pytest
from dataclasses import dataclass
from loopbuster.strategies import ExactRepeatStrategy, FuzzyRepeatStrategy
from loopbuster.types import ActionRecord

@dataclass
class MockRecord:
    tool: str
    args: dict
    output: str | None = None

def test_exact_repeat_strategy():
    strategy = ExactRepeatStrategy(window_size=3)
    
    # 连续相同
    record = MockRecord("tool1", {"a": 1})
    strategy.check(record)
    strategy.check(record)
    conf, reason = strategy.check(record)
    assert conf == 1.0
    assert "Exact repeat" in reason
    
    # 不连续相同
    strategy.reset()
    strategy.check(MockRecord("tool1", {"a": 1}))
    strategy.check(MockRecord("tool2", {"b": 2}))
    conf, reason = strategy.check(MockRecord("tool1", {"a": 1}))
    assert conf == 0.0

def test_fuzzy_repeat_strategy():
    strategy = FuzzyRepeatStrategy(window_size=3, similarity_threshold=0.8)
    
    # 类似参数
    strategy.check(MockRecord("tool1", {"a": 1, "b": 10}))
    conf, reason = strategy.check(MockRecord("tool1", {"a": 1, "b": 11}))
    assert conf > 0.0
    assert "Fuzzy repeat" in reason
