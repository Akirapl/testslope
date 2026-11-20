"""Order timestamps. Deliberately fragile: it depends on the wall clock, so the report flags it."""
from datetime import datetime

from shop.cart import Cart


def test_cart_is_created_today():
    created = datetime.now()
    cart = Cart()
    assert cart.total() == 0.0
    assert (datetime.now() - created).total_seconds() < 5
