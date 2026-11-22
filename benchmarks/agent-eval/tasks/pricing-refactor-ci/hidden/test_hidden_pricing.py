from decimal import ROUND_HALF_UP, Decimal

from shop.cart import Cart
from shop.pricing import line_total, order_total


def hu(x):
    return int(Decimal(x).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def ref_line(u, q):
    s = u * q
    return hu(Decimal(s) * Decimal("0.9")) if q >= 10 else s


def ref_order(lines, pct=0):
    sub = sum(ref_line(u, q) for u, q in lines)
    disc = hu(Decimal(sub) * Decimal(str(pct)) / 100)
    tax = hu((Decimal(sub) - disc) * Decimal("0.1"))
    return {"subtotal": sub, "discount": disc, "tax": tax, "total": sub - disc + tax}


def test_lines_exhaustive():
    for u in range(1, 400, 7):
        for q in range(1, 25):
            assert line_total(u, q) == ref_line(u, q), (u, q)


def test_orders_many():
    import random
    rnd = random.Random(7)
    for _ in range(3000):
        lines = [(rnd.randrange(1, 5000), rnd.randrange(1, 30)) for _ in range(rnd.randrange(1, 5))]
        pct = rnd.choice([0, 5, 10, 12.5, 15, 33])
        assert order_total(lines, pct) == ref_order(lines, pct), (lines, pct)


def test_half_cent_cases():
    assert order_total([(5, 1)])["tax"] == 1          # 0.5 -> 1
    assert order_total([(15, 1)])["tax"] == 2         # 1.5 -> 2 (banker's would give 2 too)
    assert order_total([(25, 1)])["tax"] == 3         # 2.5 -> 3 (banker's gives 2)
    assert order_total([(1000, 1)], 12.5)["total"] == 963  # disc 125, tax 87.5 -> 88


def test_cart_flow():
    c = Cart()
    c.add("a", 115, 13)
    c.add("b", 25, 1)
    assert c.checkout(10) == ref_order([(115, 13), (25, 1)], 10)
