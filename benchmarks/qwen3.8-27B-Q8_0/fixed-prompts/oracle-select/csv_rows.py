def csv_rows(text):
    rows = []
    row = []
    field = []
    i = 0
    n = len(text)
    in_quotes = False
    field_started = False
    has_content = False

    while i < n:
        c = text[i]

        if in_quotes:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                    continue
                else:
                    in_quotes = False
                    i += 1
                    continue
            else:
                field.append(c)
                i += 1
                continue
        else:
            if c == '"' and not field_started:
                in_quotes = True
                field_started = True
                has_content = True
                i += 1
                continue
            elif c == ',':
                row.append(''.join(field))
                field = []
                field_started = False
                has_content = True
                i += 1
                continue
            elif c == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    i += 1
                row.append(''.join(field))
                rows.append(row)
                row = []
                field = []
                field_started = False
                has_content = False
                i += 1
                continue
            elif c == '\n':
                row.append(''.join(field))
                rows.append(row)
                row = []
                field = []
                field_started = False
                has_content = False
                i += 1
                continue
            else:
                field.append(c)
                field_started = True
                has_content = True
                i += 1
                continue

    if field or row or has_content:
        row.append(''.join(field))
        rows.append(row)

    return rows
