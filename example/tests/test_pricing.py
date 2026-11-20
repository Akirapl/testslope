"""Pricing totals and discounts: a clean test, deterministic and fast."""
from shop import pricing


def test_total_without_discount():
    assert pricing.total([1.0, 2.5]) == 3.5


def test_total_with_discount():
    assert pricing.total([10.0, 10.0], discount=0.25) == 15.0
