def csv_rows(text):
    rows = []
    i = 0
    n = len(text)
    
    while i < n:
        # If the line is empty (just a newline), produce an empty row
        if text[i] == '\r':
            if i + 1 < n and text[i + 1] == '\n':
                i += 2
            else:
                i += 1
            rows.append([])
            continue
        elif text[i] == '\n':
            i += 1
            rows.append([])
            continue
        
        row = []
        while True:
            # Parse a single field
            if i < n and text[i] == '"':
                # Quoted field
                i += 1  # skip opening quote
                field_chars = []
                while i < n:
                    if text[i] == '"':
                        if i + 1 < n and text[i + 1] == '"':
                            # Doubled quote -> escaped quote
                            field_chars.append('"')
                            i += 2
                        else:
                            # Closing quote
                            i += 1
                            break
                    else:
                        field_chars.append(text[i])
                        i += 1
                field = ''.join(field_chars)
            else:
                # Unquoted field
                field_chars = []
                while i < n and text[i] != ',' and text[i] != '\r' and text[i] != '\n':
                    field_chars.append(text[i])
                    i += 1
                field = ''.join(field_chars)
            
            row.append(field)
            
            # Check what comes after the field
            if i >= n:
                break
            elif text[i] == ',':
                i += 1  # skip comma, continue to next field
                # If the next character is end of input, we still need to add an empty field
                if i >= n:
                    row.append('')
                    break
            elif text[i] == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    i += 2  # skip CRLF
                else:
                    i += 1  # skip lone CR
                break
            elif text[i] == '\n':
                i += 1  # skip LF
                break
            else:
                # Should not happen in valid CSV, but break to be safe
                break
        
        rows.append(row)
        
        # If we're at end of text, stop
        if i >= n:
            break
    
    return rows
