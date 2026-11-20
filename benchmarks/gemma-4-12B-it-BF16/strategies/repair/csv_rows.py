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
                if i + 1 < n and text[i + 1] == '"':
                    current_field.append('"')
                    i += 1
                else:
                    in_quotes = False
            else:
                current_field.append(char)
        else:
            if char == '"':
                in_quotes = True
            elif char == ',':
                current_row.append("".join(current_field))
                current_field = []
            elif char == '\n' or char == '\r':
                if char == '\r' and i + 1 < n and text[i + 1] == '\n':
                    i += 1
                
                current_row.append("".join(current_field))
                rows.append(current_row)
                current_row = []
                current_field = []
            else:
                current_field.append(char)
        i += 1

    # Handle the last field/row if not terminated by a newline
    # If text is empty, we should return []
    if n == 0:
        return []
        
    # If the string ends with a newline, the loop already appended the row.
    # If it doesn't end with a newline, we need to append the final accumulated row/field.
    if text[-1] != '\n' and text[-1] != '\r':
        current_row.append("".join(current_field))
        rows.append(current_row)
    elif n > 0 and (text[-1] == '\n' or text[-1] == '\r'):
        # If it ends with a newline, but the last character was part of a row 
        # that didn't have a trailing comma, current_row might be empty or have one field.
        # However, the loop logic already appends current_row when it hits \n.
        # The only edge case is if the string is just "\n", which should result in [[]].
        if not rows or (len(rows) > 0 and rows[-1] == []):
            # This handles the case where a newline exists but no content preceded it
            pass

    # Special case for pure newline to match csv.reader behavior:
    # csv.reader(io.StringIO("\n")) -> [[]]
    if text == "\n" or text == "\r\n":
        return [[]]

    return rows
