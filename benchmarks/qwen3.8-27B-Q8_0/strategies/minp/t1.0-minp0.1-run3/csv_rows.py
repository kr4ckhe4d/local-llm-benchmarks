def csv_rows(text):
    """
    Parse RFC 4180 CSV text and return a list of rows, each a list of string fields.
    Matches behavior of csv.reader(io.StringIO(text)) without importing csv.
    """
    rows = []
    i = 0
    n = len(text)
    
    while i < n:
        # Skip empty lines at the end
        if i >= n:
            break
        
        # Start of a new row
        row = []
        
        # Check if the line is empty (just a newline)
        # But we need to handle the case where the file ends without a trailing newline
        
        # Parse fields for this row
        while True:
            # Check if we're at the end of input or at a line ending
            # that is not part of a quoted field
            if i < n:
                if text[i] == '\r' or text[i] == '\n':
                    # This is a line ending, not the start of a field
                    break
                
                # Parse a single field
                if text[i] == '"':
                    # Quoted field
                    i += 1  # Skip opening quote
                    field_chars = []
                    while i < n:
                        if text[i] == '"':
                            if i + 1 < n and text[i + 1] == '"':
                                # Doubled quote: escaped quote
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
                    
                    # After a quoted field, we should have a comma, CRLF, LF, or end of input
                    # If there's unexpected content after the closing quote before a delimiter,
                    # that's technically invalid CSV, but we'll just continue
                    # Skip any whitespace? No, RFC 4180 doesn't specify whitespace handling
                    # We just continue; the next iteration will handle comma or line ending
                    
                else:
                    # Unquoted field
                    field_chars = []
                    while i < n:
                        if text[i] == ',':
                            i += 1
                            break
                        elif text[i] == '\r' or text[i] == '\n':
                            break
                        else:
                            field_chars.append(text[i])
                            i += 1
                    field = ''.join(field_chars)
                
                row.append(field)
                
                # After parsing a field, check if we need to continue with another field
                # We continue if the current character is a comma
                if i < n and text[i] == ',':
                    i += 1
                    # Continue to next field
                else:
                    # End of row
                    break
            
            # If we broke out because i >= n, check if we should stop
            if i >= n:
                break
        
        # Handle line ending after the row
        # After finishing a row, we should be at \r, \n, or end of input
        if i < n:
            if text[i] == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    i += 2
                else:
                    i += 1
            elif text[i] == '\n':
                i += 1
        
        # Add the row if it has at least one field, or handle empty rows
        # csv.reader treats a line with just a newline as an empty row? No, it skips empty lines
        # Actually, csv.reader yields [] for a completely empty line? Let me check:
        # csv.reader(io.StringIO("\n")) yields []
        # csv.reader(io.StringIO("\n\n")) yields [], []
        # So we should add the row even if it's empty
        rows.append(row)
        
        # If we're at end of input, break
        if i >= n:
            break
        
        # If the next character is not the start of a new field (i.e., we're at a line ending
        # that we already handled, or we're at end), we continue the outer loop
        # The outer loop will check if i < n
    
    # Handle the case where the last row might not have a trailing newline
    # This is already handled since we process fields until we hit a line ending or end of input
    
    # Remove trailing empty row if the text ends with a newline?
    # Actually, csv.reader behavior:
    # csv.reader(io.StringIO("a,b\n")) yields [['a', 'b']]
    # csv.reader(io.StringIO("a,b\n\n")) yields [['a', 'b'], []]
    # So we don't remove trailing empty rows
    # But if text is empty, we return []
    # If text is "\n", we return [[]]
    
    # Wait, let me reconsider. If text is "", the while loop doesn't execute, rows = []
    # If text is "\n", the outer loop executes once, row = [], rows = [[]]
    # That matches csv.reader behavior
    
    return rows
