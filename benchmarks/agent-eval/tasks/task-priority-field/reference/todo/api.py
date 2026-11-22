"""Service layer used by the HTTP handlers."""
import copy

from .model import Task
from .serialize import task_to_dict
from .store import Store

RANK = {"high": 0, "normal": 1, "low": 2}


def create_task(store: Store, payload: dict) -> dict:
    t = Task(id=store.next_id(), title=str(payload.get("title", "")), done=bool(payload.get("done", False)),
             priority=payload.get("priority", "normal"))
    t.validate()
    store.tasks[t.id] = t
    store.save()
    return task_to_dict(t)


def update_task(store: Store, task_id: int, payload: dict) -> dict:
    t = copy.copy(store.tasks[task_id])
    if "title" in payload:
        t.title = str(payload["title"])
    if "done" in payload:
        t.done = bool(payload["done"])
    if "priority" in payload:
        t.priority = payload["priority"]
    t.validate()
    store.tasks[task_id] = t
    store.save()
    return task_to_dict(t)


def list_tasks(store: Store, done: bool | None = None, priority: str | None = None, sort: str | None = None) -> list[dict]:
    ts = sorted(store.tasks.values(), key=lambda t: t.id)
    if done is not None:
        ts = [t for t in ts if t.done == done]
    if priority is not None:
        ts = [t for t in ts if t.priority == priority]
    if sort == "priority":
        ts.sort(key=lambda t: RANK[t.priority])
    return [task_to_dict(t) for t in ts]
