def csv_rows(text):
    rows = []
    row = []
    field = []
    in_quotes = False
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if in_quotes:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                else:
                    in_quotes = False
                    i += 1
            else:
                field.append(ch)
                i += 1
        else:
            if ch == '"':
                in_quotes = True
                i += 1
            elif ch == ',':
                row.append(''.join(field))
                field = []
                i += 1
            elif ch == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    row.append(''.join(field))
                    field = []
                    rows.append(row)
                    row = []
                    i += 2
                else:
                    row.append(''.join(field))
                    field = []
                    rows.append(row)
                    row = []
                    i += 1
            elif ch == '\n':
                row.append(''.join(field))
                field = []
                rows.append(row)
                row = []
                i += 1
            else:
                field.append(ch)
                i += 1

    if field or row:
        row.append(''.join(field))
        rows.append(row)

    return rows
