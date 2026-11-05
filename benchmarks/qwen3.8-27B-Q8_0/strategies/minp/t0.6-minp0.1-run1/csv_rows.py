def csv_rows(text):
    """Parse RFC 4180 CSV text and return a list of rows, each a list of string fields."""
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
                # Check for doubled quote (escaped quote)
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                else:
                    # End of quoted field
                    in_quotes = False
                    i += 1
            else:
                # Any character inside quotes is part of the field
                field.append(c)
                i += 1
        else:
            if c == '"':
                # Start of quoted field (only valid at start of field)
                in_quotes = True
                i += 1
            elif c == ',':
                # End of field, start new field
                row.append(''.join(field))
                field = []
                i += 1
            elif c == '\r':
                # Check for CRLF
                if i + 1 < n and text[i + 1] == '\n':
                    # End of row
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    i += 2
                else:
                    # Lone CR, treat as end of row (or just add to field? RFC 4180 says CRLF)
                    # For robustness, treat lone CR as line ending
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    i += 1
            elif c == '\n':
                # End of row (LF)
                row.append(''.join(field))
                rows.append(row)
                row = []
                field = []
                i += 1
            else:
                # Regular character
                field.append(c)
                i += 1
    
    # After the loop, if there's any remaining content in field or row
    if field or row:
        row.append(''.join(field))
        rows.append(row)
    
    return rows
