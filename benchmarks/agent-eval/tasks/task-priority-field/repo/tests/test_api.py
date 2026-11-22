import pytest

from todo.api import create_task, list_tasks, update_task
from todo.store import Store


def test_create_and_reload(tmp_path):
    p = str(tmp_path / "s.json")
    s = Store(p)
    create_task(s, {"title": "a"})
    create_task(s, {"title": "b", "done": True})
    s2 = Store(p)
    assert [t["title"] for t in list_tasks(s2)] == ["a", "b"]
    assert [t["title"] for t in list_tasks(s2, done=True)] == ["b"]


def test_empty_title_rejected(tmp_path):
    s = Store(str(tmp_path / "s.json"))
    with pytest.raises(ValueError):
        create_task(s, {"title": "  "})


def test_update(tmp_path):
    s = Store(str(tmp_path / "s.json"))
    t = create_task(s, {"title": "a"})
    assert update_task(s, t["id"], {"done": True})["done"] is True
