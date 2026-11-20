"""A tiny pricing module used by the example suite."""
from __future__ import annotations


def total(prices: list[float], discount: float = 0.0) -> float:
    return round(sum(prices) * (1 - discount), 2)
