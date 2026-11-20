def csv_rows(text):
    rows = []
    current_row = []
    current_field = []
    in_quotes = False
    i = 0
    n = len(text)

    while i < n:
        char = text[i]

        if in_quotes:
            if char == '"':
                # Check for escaped quote (double quote)
                if i + 1 < n and text[i + 1] == '"':
                    current_field.append('"')
                    i += 1  # Skip the second quote
                else:
                    # End of quoted field
                    in_quotes = False
            else:
                current_field.append(char)
        else:
            if char == '"':
                # Start of quoted field
                in_quotes = True
            elif char == '\r':
                # Handle CRLF
                if i + 1 < n and text[i + 1] == '\n':
                    if current_field or current_row:
                        current_row.append("".join(current_field))
                        rows.append(current_row)
                        current_row = []
                        current_field = []
                    i += 2
                    continue
                else:
                    # Lone \r (rare, but handled as part of field or line end)
                    current_field.append(char)
            elif char == '\n':
                # End of line
                current_row.append("".join(current_field))
                rows.append(current_row)
                current_row = []
                current_field = []
            else:
                current_field.append(char)
        i += 1

    # Handle last line if not terminated by newline
    if current_field or current_row:
        current_row.append("".join(current_field))
        rows.append(current_row)

    return rows
