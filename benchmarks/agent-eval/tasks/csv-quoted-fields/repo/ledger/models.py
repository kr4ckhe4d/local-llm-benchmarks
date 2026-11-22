from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Transaction:
    day: date
    description: str
    amount: float
    memo: str = ""

    @property
    def is_debit(self) -> bool:
        return self.amount < 0
