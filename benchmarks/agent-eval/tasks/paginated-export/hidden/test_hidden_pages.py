import pytest

from crm.client import ContactClient
from crm.export import export_csv


def fake_api(n):
    data = [{"id": i, "name": f"n{i}", "email": f"e{i}@x"} for i in range(n)]
    calls = []

    def transport(path, params):
        assert path == "/contacts"
        calls.append((params["offset"], params["limit"]))
        o, l = params["offset"], params["limit"]
        return {"total": n, "items": data[o:o + l]}
    return transport, calls


@pytest.mark.parametrize("n,ps", [(120, 50), (100, 50), (80, 50), (50, 50), (51, 50), (1, 50), (999, 10), (7, 3)])
def test_all_records_one_request_per_page(n, ps):
    t, calls = fake_api(n)
    got = ContactClient(t, page_size=ps).fetch_all()
    assert [c["id"] for c in got] == list(range(n))
    pages = -(-n // ps)
    assert len(calls) == pages
    assert [o for o, _ in calls] == [i * ps for i in range(pages)]
    assert all(l == ps for _, l in calls)


def test_empty():
    t, calls = fake_api(0)
    assert ContactClient(t).fetch_all() == []
    assert len(calls) == 1


def test_export_has_every_row():
    t, _ = fake_api(120)
    assert len(export_csv(ContactClient(t)).splitlines()) == 121
