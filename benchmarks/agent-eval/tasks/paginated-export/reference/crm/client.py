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
        offset = self.page_size
        while offset < total:
            items.extend(self._page(offset)["items"])
            offset += self.page_size
        return items

    def count(self) -> int:
        return self.transport("/contacts", {"offset": 0, "limit": 1})["total"]
