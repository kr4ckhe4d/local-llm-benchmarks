"""Import bank CSV exports into Transaction objects.

Expected columns (any order, header row required): Date, Description, Amount, Memo (optional).
"""
from datetime import date

from .models import Transaction

REQUIRED = ("date", "description", "amount")


def _parse_amount(text: str) -> float:
    text = text.strip().replace("$", "").replace(" ", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    return float(text)


def parse_rows(text: str):
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    header = [h.strip().lower() for h in lines[0].split(",")]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    rows = []
    for line in lines[1:]:
        cells = line.split(",")
        rows.append(dict(zip(header, cells)))
    return rows


def import_csv(text: str) -> list[Transaction]:
    out = []
    for row in parse_rows(text):
        out.append(Transaction(
            day=date.fromisoformat(row["date"].strip()),
            description=row["description"].strip(),
            amount=_parse_amount(row["amount"]),
            memo=(row.get("memo") or "").strip(),
        ))
    return out


def import_file(path: str) -> list[Transaction]:
    with open(path, encoding="utf-8-sig") as f:
        return import_csv(f.read())
