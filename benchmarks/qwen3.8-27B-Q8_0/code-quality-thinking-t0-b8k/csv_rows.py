def csv_rows(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    rows = []
    row = []
    field = []

    i = 0
    n = len(text)

    while i < n:
        if text[i] == '"':
            i += 1
            while i < n:
                c = text[i]
                if c == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        field.append('"')
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    field.append(c)
                    i += 1

            while i < n and text[i] != "," and text[i] != "\n":
                field.append(text[i])
                i += 1
        else:
            while i < n and text[i] != "," and text[i] != "\n":
                field.append(text[i])
                i += 1

        row.append("".join(field))

        if i < n:
            if text[i] == ",":
                i += 1
                continue
            if text[i] == "\n":
                i += 1
                rows.append(row)
                row = []
                continue

        rows.append(row)
        break

    return rows
