"""Pricing rules.

All money is in integer cents. Rules (agreed with finance, see tests):
  1. Line subtotal = unit price x quantity.
  2. Bulk discount: 10% off a line when quantity is 10 or more.
  3. Coupon: a percentage off the order total *before* tax.
  4. GST of 10% is charged on the discounted total.
  5. Every rounding step rounds half up to the nearest cent (finance rounds 0.5 cents up).
"""
from decimal import ROUND_HALF_UP, Decimal

BULK_MIN_QTY = 10
BULK_RATE = Decimal("0.10")
GST_RATE = Decimal("0.10")


def _cents(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def line_total(unit_cents: int, qty: int) -> int:
    subtotal = unit_cents * qty
    if qty >= BULK_MIN_QTY:
        subtotal = _cents(Decimal(subtotal) * (1 - BULK_RATE))
    return subtotal


def order_total(lines, coupon_pct: float = 0.0) -> dict:
    subtotal = sum(line_total(u, q) for u, q in lines)
    discount = _cents(Decimal(subtotal) * Decimal(str(coupon_pct)) / 100)
    tax = _cents((Decimal(subtotal) - discount) * GST_RATE)
    total = subtotal - discount + tax
    return {"subtotal": subtotal, "discount": discount, "tax": tax, "total": total}
