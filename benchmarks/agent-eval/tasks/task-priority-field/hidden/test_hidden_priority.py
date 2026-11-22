import json

import pytest

from todo.api import create_task, list_tasks, update_task
from todo.store import Store


def mk(tmp_path):
    return Store(str(tmp_path / "s.json")), str(tmp_path / "s.json")


def test_default_and_explicit(tmp_path):
    s, p = mk(tmp_path)
    assert create_task(s, {"title": "a"})["priority"] == "normal"
    assert create_task(s, {"title": "b", "priority": "high"})["priority"] == "high"
    assert [t["priority"] for t in list_tasks(Store(p))] == ["normal", "high"]


def test_invalid_not_saved(tmp_path):
    s, p = mk(tmp_path)
    create_task(s, {"title": "a"})
    with pytest.raises(ValueError):
        create_task(s, {"title": "b", "priority": "urgent"})
    assert len(list_tasks(Store(p))) == 1
    assert len(list_tasks(s)) == 1


def test_update_priority(tmp_path):
    s, p = mk(tmp_path)
    t = create_task(s, {"title": "a"})
    assert update_task(s, t["id"], {"priority": "low"})["priority"] == "low"
    with pytest.raises(ValueError):
        update_task(s, t["id"], {"priority": "HIGHEST"})
    assert list_tasks(Store(p))[0]["priority"] == "low"


def test_old_store_loads(tmp_path):
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"version": 1, "tasks": [{"id": 1, "title": "x", "done": False},
                                                     {"id": 2, "title": "y", "done": True}]}))
    s = Store(str(p))
    assert [t["priority"] for t in list_tasks(s)] == ["normal", "normal"]
    create_task(s, {"title": "z", "priority": "low"})
    assert [t["priority"] for t in list_tasks(Store(str(p)))] == ["normal", "normal", "low"]


def test_filter_and_sort(tmp_path):
    s, _ = mk(tmp_path)
    for title, pr in [("a", "low"), ("b", "high"), ("c", "normal"), ("d", "high"), ("e", "low")]:
        create_task(s, {"title": title, "priority": pr})
    assert [t["title"] for t in list_tasks(s)] == ["a", "b", "c", "d", "e"]
    assert [t["title"] for t in list_tasks(s, sort="priority")] == ["b", "d", "c", "a", "e"]
    assert [t["title"] for t in list_tasks(s, priority="low")] == ["a", "e"]
    assert [t["title"] for t in list_tasks(s, priority="high", sort="priority")] == ["b", "d"]
