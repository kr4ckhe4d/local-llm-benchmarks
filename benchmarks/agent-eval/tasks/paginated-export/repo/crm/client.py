"""Client for the CRM contacts API."""


class ContactClient:
    def __init__(self, transport, page_size: int = 50):
        """transport(path: str, params: dict) -> dict  (decoded JSON)"""
        self.transport = transport
        self.page_size = page_size

    def _page(self, offset: int) -> dict:
        return self.transport("/contacts", {"offset": offset, "limit": self.page_size})

    def fetch_all(self) -> list[dict]:
        first = self._page(0)
        total = first["total"]
        items = list(first["items"])
        pages = total // self.page_size
        for p in range(1, pages):
            items.extend(self._page(p * self.page_size)["items"])
        return items

    def count(self) -> int:
        return self.transport("/contacts", {"offset": 0, "limit": 1})["total"]
