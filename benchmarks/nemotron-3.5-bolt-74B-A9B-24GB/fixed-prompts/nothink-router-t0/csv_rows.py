def csv_rows(text):
    rows = []
    current_row = []
    current_field = []
    i = 0
    n = len(text)
    in_quotes = False

    while i < n:
        c = text[i]

        if in_quotes:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    current_field.append('"')
                    i += 2
                else:
                    in_quotes = False
                    i += 1
            else:
                current_field.append(c)
                i += 1
        else:
            if c == '"':
                in_quotes = True
                i += 1
            elif c == ',':
                current_row.append(''.join(current_field))
                current_field = []
                i += 1
            elif c == '\r':
                current_row.append(''.join(current_field))
                current_field = []
                rows.append(current_row)
                current_row = []
                i += 1
                if i < n and text[i] == '\n':
                    i += 1
            elif c == '\n':
                current_row.append(''.join(current_field))
                current_field = []
                rows.append(current_row)
                current_row = []
                i += 1
            else:
                current_field.append(c)
                i += 1

    if current_field or current_row:
        current_row.append(''.join(current_field))
        rows.append(current_row)

    return rows
