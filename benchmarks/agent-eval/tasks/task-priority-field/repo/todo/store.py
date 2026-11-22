"""JSON-file persistence."""
import json
import os

from .model import Task


class Store:
    def __init__(self, path: str):
        self.path = path
        self.tasks: dict[int, Task] = {}
        if os.path.exists(path):
            with open(path) as f:
                raw = json.load(f)
            for d in raw["tasks"]:
                t = Task(id=d["id"], title=d["title"], done=d.get("done", False))
                self.tasks[t.id] = t

    def next_id(self) -> int:
        return max(self.tasks, default=0) + 1

    def save(self):
        data = {"version": 1, "tasks": [{"id": t.id, "title": t.title, "done": t.done}
                                        for t in sorted(self.tasks.values(), key=lambda t: t.id)]}
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, self.path)
