from dataclasses import dataclass


@dataclass
class Task:
    id: int
    title: str
    done: bool = False

    def validate(self):
        if not self.title.strip():
            raise ValueError("title must not be empty")
