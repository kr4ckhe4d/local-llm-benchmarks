def csv_rows(text):
    rows = []
    row = []
    field = []
    in_quotes = False
    i = 0
    n = len(text)

    def end_field():
        row.append(''.join(field))
        field.clear()

    def end_row():
        if field or row:
            end_field()
        rows.append(list(row))
        row.clear()

    while i < n:
        c = text[i]
        if in_quotes:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                    continue
                in_quotes = False
                i += 1
                continue
            field.append(c)
            i += 1
        else:
            if c == '"':
                in_quotes = True
                i += 1
            elif c == ',':
                end_field()
                i += 1
            elif c == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    i += 2
                else:
                    i += 1
                end_row()
            elif c == '\n':
                i += 1
                end_row()
            else:
                field.append(c)
                i += 1

    if field or row or in_quotes:
        end_field()
        rows.append(list(row))
    return rows


def csv_rows(text):
    rows = []
    row = []
    field = []
    in_quotes = False
    started = False  # a field has been started (quote seen or chars seen)
    i = 0
    n = len(text)

    def end_field():
        nonlocal started
        row.append(''.join(field))
        field.clear()
        started = False

    def end_row():
        nonlocal started
        if field or started or row:
            end_field()
        rows.append(list(row))
        row.clear()
        started = False

    while i < n:
        c = text[i]
        if in_quotes:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                    continue
                in_quotes = False
                i += 1
                continue
            field.append(c)
            i += 1
        else:
            if c == '"':
                in_quotes = True
                started = True
                i += 1
            elif c == ',':
                end_field()
                started = True  # a new (possibly empty) field begins after comma
                i += 1
            elif c == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    i += 2
                else:
                    i += 1
                end_row()
            elif c == '\n':
                i += 1
                end_row()
            else:
                field.append(c)
                started = True
                i += 1

    if field or started or row:
        end_field()
        rows.append(list(row))
    return rows
