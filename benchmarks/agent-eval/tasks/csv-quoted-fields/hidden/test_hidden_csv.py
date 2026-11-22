from datetime import date

from ledger.importer import import_csv, import_file


def test_quoted_comma_and_escaped_quote():
    txs = import_csv('Date,Description,Amount,Memo\n2026-03-02,"ACME, Inc.",-42.50,"Invoice ""Q1"" settlement"\n'
                     '2026-03-03,Coffee,-4.20,\n')
    assert len(txs) == 2
    assert txs[0].description == "ACME, Inc."
    assert txs[0].amount == -42.5
    assert txs[0].memo == 'Invoice "Q1" settlement'
    assert txs[1].memo == "" and txs[1].amount == -4.2


def test_newline_inside_quoted_field():
    txs = import_csv('Date,Description,Amount,Memo\n2026-03-04,Shop,-10,"line one\nline two"\n2026-03-05,B,2,\n')
    assert len(txs) == 2
    assert txs[0].memo == "line one\nline two"
    assert txs[1].day == date(2026, 3, 5)


def test_quoted_amount_with_thousands_separator_is_not_split():
    txs = import_csv('Date,Description,Amount\n2026-03-06,Car,"-1,250.00"\n')
    assert txs[0].amount == -1250.0


def test_existing_behaviour_kept():
    txs = import_csv("amount,DATE,description\n\n($3.50),2026-02-01,Tea\n\n")
    assert len(txs) == 1 and txs[0].amount == -3.5 and txs[0].description == "Tea"


def test_bom_file(tmp_path):
    p = tmp_path / "m.csv"
    p.write_bytes('﻿Date,Description,Amount\n2026-03-07,"X, Y",1\n'.encode("utf-8"))
    txs = import_file(str(p))
    assert txs[0].description == "X, Y"
