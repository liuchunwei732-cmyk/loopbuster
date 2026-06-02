
import pytest
from loopbuster.similarity import token_jaccard, normalized_edit_distance

def test_token_jaccard():
    assert token_jaccard("apple banana", "apple banana") == 1.0
    assert token_jaccard("apple", "banana") == 0.0
    assert token_jaccard("apple banana", "apple") == 0.5

def test_normalized_edit_distance():
    assert normalized_edit_distance("abc", "abc") == 0.0
    assert normalized_edit_distance("abc", "def") == 1.0
    assert normalized_edit_distance("abc", "abd") == 1/3
