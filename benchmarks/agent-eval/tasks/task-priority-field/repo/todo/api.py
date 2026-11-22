"""Service layer used by the HTTP handlers."""
from .model import Task
from .serialize import task_to_dict
from .store import Store


def create_task(store: Store, payload: dict) -> dict:
    t = Task(id=store.next_id(), title=str(payload.get("title", "")), done=bool(payload.get("done", False)))
    t.validate()
    store.tasks[t.id] = t
    store.save()
    return task_to_dict(t)


def update_task(store: Store, task_id: int, payload: dict) -> dict:
    t = store.tasks[task_id]
    if "title" in payload:
        t.title = str(payload["title"])
    if "done" in payload:
        t.done = bool(payload["done"])
    t.validate()
    store.save()
    return task_to_dict(t)


def list_tasks(store: Store, done: bool | None = None) -> list[dict]:
    ts = sorted(store.tasks.values(), key=lambda t: t.id)
    if done is not None:
        ts = [t for t in ts if t.done == done]
    return [task_to_dict(t) for t in ts]
