from crm.client import ContactClient
from crm.export import export_csv


def fake_api(n):
    data = [{"id": i, "name": f"n{i}", "email": f"e{i}@x"} for i in range(n)]
    calls = []

    def transport(path, params):
        calls.append(params["offset"])
        o, l = params["offset"], params["limit"]
        return {"total": n, "items": data[o:o + l]}
    return transport, calls


def test_small_export():
    t, _ = fake_api(30)
    assert [c["id"] for c in ContactClient(t).fetch_all()] == list(range(30))


def test_export_csv_header():
    t, _ = fake_api(2)
    assert export_csv(ContactClient(t)).splitlines()[0] == "id,name,email"


def test_count():
    t, _ = fake_api(7)
    assert ContactClient(t).count() == 7
