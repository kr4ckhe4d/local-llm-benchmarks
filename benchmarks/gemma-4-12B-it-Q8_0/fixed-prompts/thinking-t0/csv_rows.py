def csv_rows(text):
    rows = []
    current_row = []
    current_field = ""
    in_quotes = False
    i = 0
    n = len(text)

    while i < n:
        char = text[i]

        if char == '"':
            if not in_quotes:
                in_quotes = True
            else:
                # Check if it's a doubled quote (escaped quote)
                if i + 1 < n and text[i + 1] == '"':
                    current_field += '"'
                    i += 1  # Skip the second quote
                else:
                    in_quotes = False
        elif char == ',':
            if in_quotes:
                current_field += ','
            else:
                current_row.append(current_field)
                current_field = ""
        elif char == '\n':
            if in_quotes:
                current_field += '\n'
            else:
                current_row.append(current_field)
                rows.append(current_row)
                current_row = []
                current_field = ""
        elif char == '\r':
            if in_quotes:
                current_field += '\r'
            else:
                # Handle CRLF
                if i + 1 < n and text[i + 1] == '\n':
                    i += 1
                current_row.append(current_field)
                rows.append(current_row)
                current_row = []
                current_field = ""
        else:
            current_field += char
        
        i += 1

    # Handle the last field/row if the string doesn't end with a newline
    if current_field or current_row or (n > 0 and text[-1] == ','):
        current_row.append(current_field)
        rows.append(current_row)
    elif not rows and n == 0:
        # Handle empty input
        pass
    elif not rows and n > 0:
        # Handle case where there's content but no newlines (single row)
        if current_row:
            current_row.append(current_field)
            rows.append(current_row)
        else:
            rows.append([current_field])

    # csv.reader behavior: if the last line is just a newline, 
    # it doesn't add an extra empty row. If there's content, it does.
    # The logic above handles standard cases; we ensure we don't add 
    # an extra empty row if the text ended exactly with \n.
    return rows
