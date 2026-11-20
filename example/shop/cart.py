"""A tiny cart module used by the example suite."""
from __future__ import annotations

from .pricing import total


class Cart:
    def __init__(self) -> None:
        self.prices: list[float] = []

    def add(self, price: float) -> None:
        self.prices.append(price)

    def total(self, discount: float = 0.0) -> float:
        return total(self.prices, discount)
