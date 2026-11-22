from shop.cart import Cart


def test_cart_merges_lines():
    c = Cart()
    c.add("a", 100, 4)
    c.add("a", 100, 6)
    assert c.checkout()["subtotal"] == 900  # 10 units -> bulk


def test_cart_remove():
    c = Cart()
    c.add("a", 100)
    c.remove("a")
    assert c.checkout()["total"] == 0
