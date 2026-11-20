"""Cart behaviour. Deliberately sloppy: it sleeps and uses randomness without a seed, so the report flags it."""
import random
import time

from shop.cart import Cart


def test_cart_adds_items():
    cart = Cart()
    price = round(random.random() * 10, 2)
    cart.add(price)
    time.sleep(0.01)
    assert cart.total() == price


def test_cart_applies_discount():
    cart = Cart()
    cart.add(100.0)
    assert cart.total(discount=0.1) == 90.0
