import pytest

from nexusagent.infrastructure.utils import is_prime


def test_is_prime_negative_numbers():
    assert is_prime(-100) is False
    assert is_prime(-5) is False
    assert is_prime(-1) is False

def test_is_prime_zero_and_one():
    assert is_prime(0) is False
    assert is_prime(1) is False

def test_is_prime_small_primes():
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 97]
    for p in primes:
        assert is_prime(p) is True

def test_is_prime_small_composites():
    composites = [4, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20, 21, 22, 24, 25, 26, 27, 28, 30]
    for c in composites:
        assert is_prime(c) is False

def test_is_prime_large_primes():
    large_primes = [7919, 104729, 9999991]
    for p in large_primes:
        assert is_prime(p) is True

def test_is_prime_large_composites():
    large_composites = [7920, 104730, 9999993]
    for c in large_composites:
        assert is_prime(c) is False

def test_is_prime_invalid_types():
    with pytest.raises(TypeError):
        is_prime(3.0)  # float
    with pytest.raises(TypeError):
        is_prime("7")  # string
    with pytest.raises(TypeError):
        is_prime(None)  # None
