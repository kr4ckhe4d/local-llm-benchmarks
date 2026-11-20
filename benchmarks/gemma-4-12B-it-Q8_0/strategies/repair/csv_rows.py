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
                # Check for escaped quote (double quote "")
                if i + 1 < n and text[i + 1] == '"':
                    current_field.append('"')
                    i += 1
                else:
                    # Closing quote
                    in_quotes = False
            else:
                current_field.append(char)
        else:
            if char == '"':
                # Start of a quoted field
                in_quotes = True
            elif char == ',':
                # End of a field
                current_row.append("".join(current_field))
                current_field = []
            elif char == '\n' or char == '\r':
                # End of a line
                current_row.append("".join(current_field))
                rows.append(current_row)
                current_row = []
                current_field = []
                # Handle CRLF
                if char == '\r' and i + 1 < n and text[i + 1] == '\n':
                    i += 1
            else:
                current_field.append(char)
        i += 1

    # Handle the last field/row if file doesn't end in newline
    if current_field or (len(current_row) > 0 and text[-1] != '\n' and text[-1] != '\r'):
        current_row.append("".join(current_field))
        rows.append(current_row)
    elif current_row:
        # Case where file ends with a newline but has content in the last row
        rows.append(current_row)

    # If the text was empty, return empty list; otherwise ensure we don't 
    # add an extra empty row if the string ended exactly with a newline.
    if not rows and text:
        # This handles cases where the last line was just a newline
        pass
        
    return rows
