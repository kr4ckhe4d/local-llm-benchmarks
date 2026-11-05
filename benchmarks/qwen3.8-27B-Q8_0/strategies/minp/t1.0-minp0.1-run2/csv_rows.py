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
                # Check for doubled quote
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                    continue
                else:
                    # End of quoted field
                    in_quotes = False
                    i += 1
                    continue
            else:
                field.append(ch)
                i += 1
                continue
        else:
            if ch == '"':
                # Start of quoted field
                in_quotes = True
                i += 1
                continue
            elif ch == ',':
                # End of field
                row.append(''.join(field))
                field = []
                i += 1
                continue
            elif ch == '\r':
                # Handle CRLF or CR
                if i + 1 < n and text[i + 1] == '\n':
                    # CRLF
                    row.append(''.join(field))
                    field = []
                    rows.append(row)
                    row = []
                    i += 2
                    continue
                else:
                    # Just CR
                    row.append(''.join(field))
                    field = []
                    rows.append(row)
                    row = []
                    i += 1
                    continue
            elif ch == '\n':
                # LF
                row.append(''.join(field))
                field = []
                rows.append(row)
                row = []
                i += 1
                continue
            else:
                field.append(ch)
                i += 1
                continue
    
    # End of input: if we have any remaining data in field or row
    # If we're in a quoted field that wasn't closed, we just finish
    if in_quotes or field or row:
        # If we have content in field or row, finalize
        row.append(''.join(field))
        rows.append(row)
    
    # Handle the case where the last row is empty (trailing newline)
    # Actually, csv.reader doesn't add an empty row for trailing newline
    # Let's check: if text ends with \n, csv.reader doesn't produce an extra empty row
    # But our logic above: when we hit \n, we append the row and reset. So no extra row.
    
    return rows
