def csv_rows(text):
    """
    Parses RFC 4180 CSV text and returns a list of rows, each a list of string fields.
    Handles quoted fields containing commas and newlines, doubled quotes as escaped quotes,
    and CRLF or LF line endings.
    """
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
                # Check if next char is also a quote (escaped quote)
                if i + 1 < n and text[i + 1] == '"':
                    current_field.append('"')
                    i += 2
                    continue
                else:
                    # End of quoted field
                    in_quotes = False
                    i += 1
                    continue
            else:
                # Any character inside quotes is literal
                current_field.append(char)
                i += 1
                continue
        else:
            if char == '"' and not current_field:
                # Start of quoted field (only if field is empty so far)
                in_quotes = True
                i += 1
                continue
            elif char == ',':
                # End of field
                current_row.append(''.join(current_field))
                current_field = []
                i += 1
                continue
            elif char == '\r':
                # Handle CRLF or CR
                if i + 1 < n and text[i + 1] == '\n':
                    i += 2
                else:
                    i += 1
                current_row.append(''.join(current_field))
                current_field = []
                rows.append(current_row)
                current_row = []
                continue
            elif char == '\n':
                # Handle LF
                i += 1
                current_row.append(''.join(current_field))
                current_field = []
                rows.append(current_row)
                current_row = []
                continue
            else:
                # Regular character
                current_field.append(char)
                i += 1
                continue
    
    # After loop, check if there's a remaining field
    # If we have any content in current_field or current_row, or if text was not empty and ended without newline
    if current_field or current_row:
        current_row.append(''.join(current_field))
        rows.append(current_row)
    elif text == '':
        # Empty text returns empty list
        pass
    else:
        # If text ended with a newline, the last row was already appended
        # But if text doesn't end with newline and has content, it's handled above
        pass
    
    # Special case: if the input is empty string, return empty list
    if text == '':
        return []
    
    # If the last character was a newline, we already appended the last row
    # But if there's no trailing newline and current_field is empty but current_row has items, 
    # it means the last field was empty but already appended when we hit the comma or newline
    
    # Actually, let's reconsider: if the text ends without a newline, and we have content in current_field,
    # we append it. If current_field is empty but current_row is not empty, that means the last field 
    # was empty (e.g., "a,b," -> fields "a", "b", ""), but the empty field would have been added 
    # when we hit the last comma. So current_field would be empty and current_row would have 
    # ["a", "b", ""]. In that case, we should NOT append an empty string again.
    
    # Let me re-examine: when we hit a comma, we append current_field to current_row and reset current_field.
    # So "a,b," -> after 'a': current_field=['a'], hit comma -> current_row=['a'], current_field=[]
    # after 'b': current_field=['b'], hit comma -> current_row=['a','b'], current_field=[]
    # End of string: current_field=[], current_row=['a','b']
    # We should append current_row to rows, but current_field is empty so we append '' to current_row? No.
    # The last field after the last comma is empty, so it should be ''. But we already reset current_field.
    # So current_row is ['a','b'] and we need to add the empty last field.
    
    # Hmm, this is tricky. Let me think again.
    # For "a,b,": the fields are "a", "b", "".
    # When we process: 
    #   i=0: 'a' -> current_field=['a']
    #   i=1: ',' -> current_row=['a'], current_field=[]
    #   i=2: 'b' -> current_field=['b']
    #   i=3: ',' -> current_row=['a','b'], current_field=[]
    #   i=4: end
    # At end, current_field=[], current_row=['a','b']
    # The last field should be '' (empty string after last comma).
    # So we need to append '' to current_row, then append current_row to rows.
    
    # But for "a,b":
    #   i=0: 'a' -> current_field=['a']
    #   i=1: ',' -> current_row=['a'], current_field=[]
    #   i=2: 'b' -> current_field=['b']
    #   i=3: end
    # At end, current_field=['b'], current_row=['a']
    # We append 'b' to current_row -> ['a','b'], then append to rows.
    
    # So the logic should be:
    # If current_field is non-empty OR (current_row is non-empty and the last character was a comma or we're at end after a comma)
    # Actually, simpler: if we have any content in current_field, append it. Then if current_row has content OR 
    # we just ended a field, append current_row.
    
    # Let me just check: if current_field is not empty, append to current_row. Then if current_row is not empty, append to rows.
    # But this would miss the case where current_row is ['a','b'] and current_field is [] (from "a,b,")
    
    # I think the issue is that we need to track whether we've seen any content or if we're in the middle of a row.
    
    # Let me restart with a cleaner approach.

def csv_rows(text):
    """
    Parses RFC 4180 CSV text and returns a list of rows, each a list of string fields.
    Handles quoted fields containing commas and newlines, doubled quotes as escaped quotes,
    and CRLF or LF line endings.
    """
    if text == '':
        return []
    
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
                    i += 2
                    continue
                else:
                    in_quotes = False
                    i += 1
                    continue
            else:
                current_field.append(char)
                i += 1
                continue
        else:
            if char == '"' and not current_field:
                in_quotes = True
                i += 1
                continue
            elif char == ',':
                current_row.append(''.join(current_field))
                current_field = []
                i += 1
                continue
            elif char == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    i += 2
                else:
                    i += 1
                current_row.append(''.join(current_field))
                current_field = []
                rows.append(current_row)
                current_row = []
                continue
            elif char == '\n':
                i += 1
                current_row.append(''.join(current_field))
                current_field = []
                rows.append(current_row)
                current_row = []
                continue
            else:
                current_field.append(char)
                i += 1
                continue
    
    # Handle the last field/row
    # If we ended with a newline, current_row is already empty and the last row was appended.
    # If we didn't end with a newline, we need to check if there's remaining content.
    if current_field or current_row:
        current_row.append(''.join(current_field))
        rows.append(current_row)
    
    return rows
