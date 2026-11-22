from datetime import date

import pytest

from ledger.importer import import_csv


def test_basic_rows():
    txs = import_csv("Date,Description,Amount,Memo\n2026-01-05,Rent,-1200.00,Jan\n2026-01-06,Salary,3000,\n")
    assert [t.amount for t in txs] == [-1200.0, 3000.0]
    assert txs[0].day == date(2026, 1, 5)
    assert txs[0].memo == "Jan"


def test_column_order_and_case():
    txs = import_csv("amount,DATE,description\n-5,2026-02-01,Tea\n")
    assert txs[0].description == "Tea" and txs[0].amount == -5.0


def test_parenthesised_negative_and_dollar():
    txs = import_csv("Date,Description,Amount\n2026-02-02,Fee,($3.50)\n")
    assert txs[0].amount == -3.5


def test_blank_lines_skipped():
    txs = import_csv("Date,Description,Amount\n\n2026-02-03,A,1\n\n")
    assert len(txs) == 1


def test_missing_column():
    with pytest.raises(ValueError):
        import_csv("Date,Description\n2026-02-03,A\n")
