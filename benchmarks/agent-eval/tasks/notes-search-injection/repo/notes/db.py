"""SQLite storage for notes."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    owner TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tag TEXT,
    created INTEGER NOT NULL
);
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_note(conn, owner, title, body, tag=None, created=0) -> int:
    cur = conn.execute("INSERT INTO notes (owner, title, body, tag, created) VALUES (?, ?, ?, ?, ?)",
                       (owner, title, body, tag, created))
    conn.commit()
    return cur.lastrowid


def search_notes(conn, owner: str, term: str, tag: str | None = None) -> list[dict]:
    sql = (f"SELECT id, title, body, tag, created FROM notes WHERE owner = '{owner}' "
           f"AND (title LIKE '%{term}%' OR body LIKE '%{term}%')")
    if tag:
        sql += f" AND tag = '{tag}'"
    sql += " ORDER BY created DESC, id DESC"
    return [dict(r) for r in conn.execute(sql)]
