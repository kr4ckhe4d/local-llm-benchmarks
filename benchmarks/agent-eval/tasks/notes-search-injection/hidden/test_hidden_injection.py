from notes.db import add_note, connect, search_notes


def setup():
    c = connect()
    add_note(c, "ann", "Groceries", "milk, eggs", tag="home", created=1)
    add_note(c, "ann", "Work plan", "ship the eggs feature", tag="work", created=2)
    add_note(c, "ann", "Notes", "don't forget", created=3)
    add_note(c, "ann", "Budget", "spent 100% of it", created=4)
    add_note(c, "ann", "Budget2", "spent 1000 of it", created=5)
    add_note(c, "ann", "vars", "use a_b here", created=6)
    add_note(c, "ann", "vars2", "use axb here", created=7)
    add_note(c, "ann", "slash", r"path c:\tmp\x", created=8)
    add_note(c, "bob", "Bob secret", "eggs and secrets", tag="home", created=9)
    return c


def titles(rows):
    return [r["title"] for r in rows]


def test_injection_in_term():
    c = setup()
    assert search_notes(c, "ann", "' OR '1'='1") == []
    assert search_notes(c, "ann", "x') OR 1=1 --") == []


def test_injection_in_owner_and_tag():
    c = setup()
    assert search_notes(c, "' OR '1'='1", "e") == []
    assert search_notes(c, "ann", "eggs", tag="x' OR '1'='1") == []


def test_quote_in_term():
    assert titles(search_notes(setup(), "ann", "don't")) == ["Notes"]


def test_wildcards_literal():
    c = setup()
    assert titles(search_notes(c, "ann", "100%")) == ["Budget"]
    assert titles(search_notes(c, "ann", "a_b")) == ["vars"]
    assert titles(search_notes(c, "ann", "%")) == ["Budget"]
    assert titles(search_notes(c, "ann", "\\")) == ["slash"]


def test_existing_behaviour():
    c = setup()
    assert titles(search_notes(c, "ann", "EGGS")) == ["Work plan", "Groceries"]
    assert titles(search_notes(c, "ann", "eggs", tag="home")) == ["Groceries"]
    assert titles(search_notes(c, "bob", "eggs")) == ["Bob secret"]
    r = search_notes(c, "ann", "milk")[0]
    assert set(r) == {"id", "title", "body", "tag", "created"}


def test_table_intact_after_attack():
    c = setup()
    search_notes(c, "ann", "'; DROP TABLE notes; --")
    assert len(search_notes(c, "ann", "")) == 8
