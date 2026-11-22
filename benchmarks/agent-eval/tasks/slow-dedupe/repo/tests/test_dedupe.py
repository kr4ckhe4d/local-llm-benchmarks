from etl.dedupe import dedupe
from etl.pipeline import run


def test_keeps_first_in_order():
    rs = [{"id": 1, "v": "a"}, {"id": 2}, {"id": 1, "v": "a"}, {"id": 3}]
    assert dedupe(rs) == [{"id": 1, "v": "a"}, {"id": 2}, {"id": 3}]


def test_key():
    rs = [{"id": 1, "v": "a"}, {"id": 1, "v": "b"}]
    assert dedupe(rs, key=lambda r: r["id"]) == [{"id": 1, "v": "a"}]


def test_pipeline():
    lines = ['{"source": "s", "id": 1}', '{"source": "s", "id": 1, "x": 2}', '{"source": "t", "id": 1}']
    assert len(run(lines)) == 2
