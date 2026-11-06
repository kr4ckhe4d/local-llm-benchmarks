def csv_rows(text):
    rows = []
    row = []
    field = []
    in_quotes = False
    i = 0
    n = len(text)

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

            if c == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    i += 2
                else:
                    i += 1
                continue

            if c == '\n':
                i += 1
                continue

            field.append(c)
            i += 1
            continue

        if c == '"':
            in_quotes = True
            i += 1
            continue

        if c == ',':
            row.append(''.join(field))
            field = []
            i += 1
            continue

        if c == '\r':
            row.append(''.join(field))
            rows.append(row)
            row = []
            field = []
            if i + 1 < n and text[i + 1] == '\n':
                i += 2
            else:
                i += 1
            continue

        if c == '\n':
            row.append(''.join(field))
            rows.append(row)
            row = []
            field = []
            i += 1
            continue

        field.append(c)
        i += 1

    if field or row:
        row.append(''.join(field))
        rows.append(row)

    return rows
