from notes.db import add_note, connect, search_notes


def setup():
    c = connect()
    add_note(c, "ann", "Groceries", "milk, eggs", tag="home", created=1)
    add_note(c, "ann", "Work plan", "ship the eggs feature", tag="work", created=2)
    add_note(c, "bob", "Bob eggs", "secret", created=3)
    return c


def test_substring_case_insensitive_newest_first():
    rows = search_notes(setup(), "ann", "EGGS")
    assert [r["title"] for r in rows] == ["Work plan", "Groceries"]


def test_tag_filter():
    assert [r["title"] for r in search_notes(setup(), "ann", "eggs", tag="home")] == ["Groceries"]


def test_owner_isolation():
    assert search_notes(setup(), "bob", "milk") == []
