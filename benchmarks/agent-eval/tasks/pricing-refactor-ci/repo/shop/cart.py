from .pricing import order_total


class Cart:
    def __init__(self):
        self.lines = {}

    def add(self, sku: str, unit_cents: int, qty: int = 1):
        u, q = self.lines.get(sku, (unit_cents, 0))
        self.lines[sku] = (unit_cents, q + qty)

    def remove(self, sku: str):
        self.lines.pop(sku, None)

    def checkout(self, coupon_pct: float = 0.0) -> dict:
        return order_total(self.lines.values(), coupon_pct)
