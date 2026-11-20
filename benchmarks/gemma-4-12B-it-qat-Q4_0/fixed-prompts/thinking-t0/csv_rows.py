def csv_rows(text):
    rows = []
    current_row = []
    current_field = ""
    in_quotes = False
    i = 0
    n = len(text)

    while i < n:
        char = text[i]

        if in_quotes:
            if char == '"':
                # Check for escaped quote (double quote)
                if i + 1 < n and text[i + 1] == '"':
                    current_field += '"'
                    i += 1  # Skip the second quote
                else:
                    # Closing quote
                    in_quotes = False
            else:
                current_field += char
        else:
            if char == '"':
                # Start of a quoted field
                in_quotes = True
            elif char == ',':
                # Field separator
                current_row.append(current_field)
                current_field = ""
            elif char == '\n':
                # Line separator
                current_row.append(current_field)
                rows.append(current_row)
                current_row = []
                current_field = ""
            elif char == '\r':
                # Handle CRLF or just CR
                if i + 1 < n and text[i + 1] == '\n':
                    current_row.append(current_field)
                    rows.append(current_row)
                    current_row = []
                    current_field = ""
                    i += 1  # Skip the \n
                else:
                    # Treat CR as a newline if not followed by \n
                    current_row.append(current_field)
                    rows.append(current_row)
                    current_row = []
                    current_field = ""
            else:
                current_field += char
        i += 1

    # Handle the last field/row if the file doesn't end with a newline
    if current_field or (len(current_row) > 0 or i == n):
        # If we have content left in the buffer, add it.
        # Note: If text is empty, this won't trigger.
        if not (i == n and len(current_row) == 0 and current_field == ""):
            current_row.append(current_field)
            rows.append(current_row)

    return rows
