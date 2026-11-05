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
                else:
                    in_quotes = False
                    i += 1
                    continue
            else:
                field.append(c)
                i += 1
                continue
        else:
            if c == '"':
                in_quotes = True
                i += 1
                continue
            elif c == ',':
                row.append(''.join(field))
                field = []
                i += 1
                continue
            elif c == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    if not row and not field:
                        rows.append([])
                    else:
                        row.append(''.join(field))
                        field = []
                        rows.append(row)
                        row = []
                    i += 2
                    continue
                else:
                    if not row and not field:
                        rows.append([])
                    else:
                        row.append(''.join(field))
                        field = []
                        rows.append(row)
                        row = []
                    i += 1
                    continue
            elif c == '\n':
                if not row and not field:
                    rows.append([])
                else:
                    row.append(''.join(field))
                    field = []
                    rows.append(row)
                    row = []
                i += 1
                continue
            else:
                field.append(c)
                i += 1
                continue
    
    # Handle the last field/row
    if field or row:
        row.append(''.join(field))
        rows.append(row)
    
    return rows
