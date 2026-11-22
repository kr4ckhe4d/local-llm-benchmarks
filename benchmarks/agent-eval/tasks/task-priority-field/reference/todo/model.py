from dataclasses import dataclass

PRIORITIES = ("low", "normal", "high")


@dataclass
class Task:
    id: int
    title: str
    done: bool = False
    priority: str = "normal"

    def validate(self):
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.priority not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
