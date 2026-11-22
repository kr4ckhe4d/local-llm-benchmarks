from shop.pricing import line_total, order_total


def test_line_no_bulk():
    assert line_total(250, 9) == 2250


def test_bulk_starts_at_ten():
    assert line_total(250, 10) == 2250  # 2500 - 10%


def test_bulk_rounds_half_up():
    assert line_total(105, 10) == 945   # 1050 * 0.9 = 945.0
    assert line_total(115, 13) == 1346  # 1495 * 0.9 = 1345.5 -> 1346


def test_coupon_before_tax():
    r = order_total([(1000, 1)], coupon_pct=10)
    assert r == {"subtotal": 1000, "discount": 100, "tax": 90, "total": 990}


def test_tax_rounds_half_up():
    r = order_total([(25, 1)])
    assert r["tax"] == 3  # 2.5 -> 3
    assert r["total"] == 28
