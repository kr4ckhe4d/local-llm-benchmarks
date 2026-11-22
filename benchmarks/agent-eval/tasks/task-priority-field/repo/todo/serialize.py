from .model import Task


def task_to_dict(t: Task) -> dict:
    return {"id": t.id, "title": t.title, "done": t.done}
