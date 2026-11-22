import random
import time

from etl.dedupe import dedupe


def make(n, seed=1):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        j = rnd.randrange(n // 2)
        out.append({"id": j, "source": "crm" if j % 3 else "erp", "tags": [j % 5, "x"],
                    "meta": {"owner": f"u{j % 7}", "flags": {"a": j % 2 == 0}}})
    return out


def reference(records, key=None):
    seen, out = [], []
    for r in records:
        k = key(r) if key else r
        if k not in seen:
            seen.append(k); out.append(r)
    return out


def test_fast_whole_record():
    rs = make(200_000)
    t = time.perf_counter()
    got = dedupe(rs)
    assert time.perf_counter() - t < 5
    ids = [r["id"] for r in got]
    assert len(ids) == len(set(ids))
    seen = set(); want = []
    for r in rs:
        if r["id"] not in seen:
            seen.add(r["id"]); want.append(r)
    assert got == want


def test_fast_unhashable_key():
    import json
    rs = make(200_000, seed=2)
    key = lambda r: [r["source"], r["meta"]]
    t = time.perf_counter()
    got = dedupe(rs, key=key)
    assert time.perf_counter() - t < 5
    seen = set(); want = []
    for r in rs:  # JSON-canonical form is an exact equality proxy for these int/str/bool values
        s = json.dumps(key(r), sort_keys=True)
        if s not in seen:
            seen.add(s); want.append(r)
    assert [id(x) for x in got] == [id(x) for x in want]


def test_matches_reference_on_tricky_values():
    rs = [{"a": 1}, {"a": 1.0}, {"a": True}, {"a": [1, 2]}, {"a": [1, 2]}, {"a": (1, 2)}, {"a": {"b": [1]}},
          {"a": {"b": [1]}}, {"a": None}, {}, {}, {"a": "1"}, {"a": [2, 1]}, {"b": 1, "a": 2}, {"a": 2, "b": 1}]
    assert dedupe(rs) == reference(rs)
    k = lambda r: r.get("a")
    assert dedupe(rs, key=k) == reference(rs, key=k)


def test_order_and_identity():
    rs = make(5000, seed=3)
    got = dedupe(rs)
    want = reference(rs)
    assert [id(x) for x in got] == [id(x) for x in want]
