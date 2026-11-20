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
                in_quotes = True
            elif char == ',':
                current_row.append("".join(current_field))
                current_field = []
            elif char == '\n' or char == '\r':
                # Handle CRLF by skipping the next \n if current is \r
                if char == '\r' and i + 1 < n and text[i + 1] == '\n':
                    i += 1
                
                current_row.append("".join(current_field))
                if current_row: # Avoid adding empty row if file ends with newline
                    rows.append(current_row)
                current_row = []
                current_field = []
            else:
                current_field.append(char)
        i += 1

    # Handle the last field/row if not terminated by a newline
    if current_field or (len(current_row) > 0 and text[-1] != '\n' and text[-1] != '\r'):
        current_row.append("".join(current_field))
        rows.append(current_row)
    elif current_field: # Case where last field is empty but exists
        current_row.append("".join(current_field))
        rows.append(current_row)
    elif len(current_row) > 0:
        rows.append(current_row)

    # Final cleanup for trailing empty row logic to match csv.reader behavior
    # csv.reader treats a final newline as a terminator, not a new empty row.
    # If the text ends with a newline, the loop above might have already appended 
    # the last row. If it doesn't, we ensure the last partial row is added.
    
    # Refined logic to strictly match csv.reader:
    # The loop above handles most cases, but let's ensure we don't add an extra 
    # empty list if the string ends exactly with a newline.
    if rows and rows[-1] == [""] and text.endswith(('\n', '\r')):
        rows.pop()
        
    return rows
