"""A test nobody runs: the runner script never mentions it, so the report marks it 'not in runner'."""
from shop.pricing import total


def test_empty_cart_costs_nothing():
    assert total([]) == 0.0
