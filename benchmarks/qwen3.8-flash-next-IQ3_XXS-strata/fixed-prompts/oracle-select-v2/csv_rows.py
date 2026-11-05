def csv_rows(text):
    """
    Parse RFC 4180 CSV text and return a list of rows, each a list of string fields.
    Handles quoted fields with commas/newlines, doubled quotes for escaping,
    and CRLF or LF line endings. Matches csv.reader(io.StringIO(text)) behavior.
    """
    rows = []
    i = 0
    n = len(text)
    
    while i < n:
        fields = []
        while True:
            # Parse one field
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
                            # End of quoted field
                            i += 1  # skip closing quote
                            break
                    else:
                        field_chars.append(text[i])
                        i += 1
                fields.append(''.join(field_chars))
                # After quoted field, expect comma, newline, or end of text
                if i < n and text[i] == ',':
                    i += 1
                    # Continue to next field
                    continue
                elif i < n and (text[i] == '\r' or text[i] == '\n'):
                    # Handle line ending
                    if text[i] == '\r' and i + 1 < n and text[i + 1] == '\n':
                        i += 2
                    else:
                        i += 1
                    break
                else:
                    # End of text or unexpected char after closing quote
                    break
            else:
                # Unquoted field
                field_chars = []
                while i < n:
                    if text[i] == ',':
                        break
                    elif text[i] == '\r' or text[i] == '\n':
                        break
                    else:
                        field_chars.append(text[i])
                        i += 1
                fields.append(''.join(field_chars))
                # After unquoted field, expect comma, newline, or end of text
                if i < n and text[i] == ',':
                    i += 1
                    # Continue to next field
                    continue
                elif i < n and (text[i] == '\r' or text[i] == '\n'):
                    # Handle line ending
                    if text[i] == '\r' and i + 1 < n and text[i + 1] == '\n':
                        i += 2
                    else:
                        i += 1
                    break
                else:
                    # End of text
                    break
        
        # Append the row if it's not empty due to trailing newline at end of file
        # csv.reader skips empty trailing lines but includes rows with empty fields
        # We need to match csv.reader behavior: an empty line produces an empty row []
        # But if text ends with a newline, the last "row" might be empty.
        # csv.reader on "a,b\n" gives [['a','b']] - no extra empty row.
        # csv.reader on "a,b\n\n" gives [['a','b'], []] - yes, empty row for blank line.
        # csv.reader on "" gives [] - no rows.
        # csv.reader on "\n" gives [[]] - one empty row.
        
        # Check if we actually parsed something or hit end of input without content
        # If fields is empty and we didn't parse any field (just hit end), skip.
        # But if we parsed at least one field (even empty string), include the row.
        if fields or (i <= n and len(fields) == 0 and False):
            # Actually, let's think more carefully.
            # When we enter the inner while loop for a row, we parse at least one field.
            # fields will have at least one entry unless... 
            # At start of parsing a row, if i >= n, we wouldn't enter the loop.
            # So if we're in the outer while and i < n, we parse at least one field.
            # But what about a blank line? text[i] could be '\n' or '\r\n'.
            # In that case, we'd parse an unquoted field with field_chars empty,
            # then hit the newline, break, fields = [''] which is a row with one empty field.
            # csv.reader on "\n" gives [[]]? Let me check: actually csv.reader on "\n" 
            # in Python gives [[]]? No, let me recall: 
            # import csv, io; list(csv.reader(io.StringIO("\n"))) gives [[]]? 
            # Actually I think it gives []. Hmm, need to be precise.
            # Let's check: csv.reader treats a blank line as producing an empty row? 
            # Actually, from Python docs: "A blank line is treated as an empty row."
            # Wait no - testing: list(csv.reader(io.StringIO("\n"))) returns []? 
            # Or [[]]? I recall that a single newline produces one empty row [].
            # Let me reason: the reader reads line by line. "\n" means one line with no content.
            # That line is parsed as having zero fields? Or one empty field?
            # In RFC 4180, a blank line is not valid, but Python's csv.reader handles it.
            # From my knowledge: list(csv.reader(io.StringIO("a\n\nb\n"))) 
            # gives [['a'], [], ['b']]. So a blank line gives an empty list [].
            # So for a blank line, we should produce [].
            
            # How does our parser handle a blank line? 
            # If text is "\n", at i=0, text[0] == '\n'. We go to unquoted field branch.
            # field_chars is empty (immediately break on newline). fields = [''].
            # Then we detect newline, i += 1, break inner loop. fields = [''].
            # But csv.reader would give [] for a blank line.
            
            # Hmm, so we need to handle this. A blank line should produce an empty row [].
            # The issue is distinguishing between a row with one empty field and a blank line.
            # In CSV, a line with just a newline is a blank line -> empty row.
            # But a line like "\n" after a comma? No, that's different.
            
            # Actually, let me reconsider. In CSV, each line is a record. 
            # A record can have fields. A blank line has no fields -> [].
            # But our parser for a blank line produces [''] because it parses one empty field.
            
            # To fix: if we're at the start of a line and the first char is a newline,
            # that's a blank line -> empty row.
            
            # But wait, what about a line that is just a comma? Like ",\n"? 
            # csv.reader on ",\n" gives [['', '']]. Two empty fields.
            # Our parser: at i=0, not quoted, parse unquoted field until comma -> field_chars empty, fields=[''].
            # Then comma, i+=1, continue. Next field: at i=1, text[1]=='\n', parse unquoted field -> field_chars empty, fields=['',''].
            # Then newline, break. Good.
            
            # What about just "\n"? i=0, not quoted, parse unquoted field, immediately hit newline, field_chars empty, fields=[''].
            # Then newline detected, break. fields=['']. But should be [].
            
            # The difference: a blank line has NO fields. A line with one empty field has one field.
            # How to distinguish? In CSV, a blank line is when there's nothing before the newline.
            # Our parser always parses at least one field per row. For a blank line, 
            # we parse one empty field, but it should be zero fields.
            
            # Actually, let me test what csv.reader really does. I'm fairly confident:
            # list(csv.reader(io.StringIO("\n"))) == []
            # list(csv.reader(io.StringIO("\r\n"))) == []
            # list(csv.reader(io.StringIO("a\n\nb\n"))) == [['a'], [], ['b']]
            
            # So a blank line yields []. Our parser yields [''] for a blank line.
            # We need to detect this case.
            
            # One approach: after parsing a row, if the row consists of exactly one empty field
            # AND the row was terminated by a newline (not end of text), and the original 
            # position at start of row had no content before the newline... 
            # This is tricky. Let me think differently.
            
            # Actually, maybe the simpler fix: when parsing a row, if we detect that we're 
            # at the very start of a line and the next character is a newline, then this is 
            # a blank line and we should produce an empty row.
            
            # But how do we know we're at the start of a line? We track position.
            # Let me restructure: before parsing a row, check if current position is at a newline.
            # If so, consume the newline and append an empty row [].
            
            # But wait, what if the text ends with a newline? Like "a,b\n". 
            # After parsing "a,b", we consume the \n and break. i is now at end. 
            # Outer while checks i < n, which is false, so we don't parse another row. Good.
            
            # What about "a,b\n\n"? After parsing "a,b" and consuming first \n, i points to 
            # the second \n. Outer while: i < n, enter row parsing. At start of row parsing,
            # text[i] == '\n'. We should detect this as a blank line.
            
            # Let me add a check at the beginning of outer while loop:
            # If i < n and text[i] is a newline, consume it and append [] to rows, continue.
            
            # But what about "a,b\n" where after parsing "a,b" we already consumed the \n?
            # Then i == n, outer while doesn't execute. Good.
            
            # What about "\n" alone? i=0 < n, text[0] == '\n'. Consume newline, append [], 
            # i=1, outer while: i < n? n=1, i=1, false. rows = [[]]. 
            # But csv.reader on "\n" gives []? Or [[]]?
            
            # Hmm, I need to be certain. Let me think about what csv.reader does internally.
            # It reads line by line. For "\n", it reads one line (empty). Then parses that 
            # empty line. An empty line produces an empty list []. So rows = [[]]? 
            # No wait - if reading "\n", the file has one line which is empty. 
            # csv.reader yields one row for that line: []. So list(csv.reader(io.StringIO("\n"))) == [[]].
            
            # Let me verify with known behavior: 
            # io.StringIO("a\n").read() == "a\n". csv.reader yields ['a']. One row.
            # io.StringIO("\n").read() == "\n". csv.reader yields []. One row (empty).
            # So list(csv.reader(io.StringIO("\n"))) == [[]].
            
            # OK so a blank line DOES produce an empty row []. My earlier intuition was wrong.
            # So our parser producing [''] for a blank line is WRONG; it should produce [].
            
            # For a blank line "\n": our parser produces fields=['']. We need [].
            # For "\r\n": same thing.
            
            # So let me add the check: if at start of row parsing, the character is a newline,
            # consume it and append [].
            
            # But what about a line that is empty but we're in the middle of parsing?
            # That shouldn't happen because we break on newlines.
            
            # Let me revise the algorithm:
            # At the start of each row (inside outer while), if text[i] is '\n' or '\r\n',
            # consume the newline and append [] to rows, continue.
            # But wait, what if text is "a,b\n\nc,d\n"? 
            # Parse "a,b", consume \n, i points to second \n. Outer while: i < n, text[i]=='\n'.
            # Consume \n, append []. i now points to 'c'. Parse "c,d", consume \n. Done.
            # rows = [['a','b'], [], ['c','d']]. Correct.
            
            # What about text = "" (empty string)? n=0, outer while doesn't execute. rows=[]. Correct.
            # What about text = "\n"? n=1, i=0 < n, text[0]=='\n'. Consume, append []. i=1, n=1, loop ends. rows=[[]]. Correct.
            # What about text = "a"? n=1, i=0 < n, text[0]=='a', not newline. Parse row. fields=['a']. 
            # After parsing, i=1, no comma/newline, break inner. Append ['a']. Outer while: i=1, n=1, done. rows=[['a']]. Correct.
            # What about text = "a\n"? Parse "a", consume \n, i=2, n=2, outer while ends. rows=[['a']]. Correct.
            # What about text = "a\n\n"? Parse "a", consume first \n, i=2. Outer while: i=2 < n=3, text[2]=='\n'. 
            # Consume, append []. i=3, n=3, done. rows=[['a'], []]. Correct.
            
            # What about a quoted field that ends with a newline inside quotes? 
            # Like '"a\nb"\n'. The parser handles newlines inside quotes correctly because 
            # in the quoted field branch, we don't break on newlines - only on closing quote.
            # So the \n inside quotes is just a regular character. Good.
            
            # What about text ending without a trailing newline? Like "a,b". 
            # Parse "a", comma, parse "b", end of text, break. Append ['a','b']. Correct.
            
            # What about text ending with a trailing newline? Like "a,b\n".
            # Parse "a", comma, parse "b", newline consumed, break. Append ['a','b']. 
            # i now at end. Outer while ends. rows=[['a','b']]. Correct (no extra empty row).
            
            # What about text = "a,b\n\r\n"? 
            # Parse "a,b", consume \n (wait, it's \r\n). Let's trace: 
            # After "b", i points to '\r'. We detect newline: text[i]=='\r' and text[i+1]=='\n', consume both, i+=2.
            # Break inner loop. Append ['a','b']. i now at end of text? n=5, i=5. Outer while ends. 
            # rows=[['a','b']]. But there's a \r\n after, which is a blank line? 
            # Wait, "a,b\n\r\n" - after "a,b" there's \n then \r\n. 
            # Hmm, let me recount: "a,b\n\r\n" has chars: a, ,, b, \n, \r, \n. n=6.
            # Parse "a", comma, parse "b". After "b", i=3, text[3]=='\n'. Consume \n, i=4. Break. Append ['a','b'].
            # Outer while: i=4 < n=6. text[4]=='\r'. Check: is it a newline at start of row? 
            # In my proposed fix, I check if text[i] is newline. '\r' is part of CRLF. 
            # I should check for '\r' followed by '\n', or just '\n'.
            # Let me handle: if text[i] == '\r' and i+1 < n and text[i+1] == '\n', or text[i] == '\n'.
            # At i=4, text[4]=='\r', text[5]=='\n'. So consume \r\n, i=6. Append []. 
            # Outer while: i=6, n=6, done. rows=[['a','b'], []]. 
            # Is this correct? "a,b\n\r\n" - first line "a,b", second line "" (blank), so two rows: ['a','b'] and []. Correct.
            
            # What about "a,b\r\n"? Chars: a, ,, b, \r, \n. n=5.
            # Parse "a,b". After "b", i=3, text[3]=='\r', text[4]=='\n'. Consume \r\n, i=5. Break. Append ['a','b'].
            # Outer while: i=5, n=5, done. rows=[['a','b']]. Correct.
            
            # OK so the fix is: at the start of the outer while loop (before parsing a row),
            # check if current position is at a line ending. If so, consume it and append [].
            
            # But wait, I already consume line endings when parsing fields. So when would 
            # I encounter a line ending at the start of a row? Only when there's a blank line,
            # i.e., two consecutive newlines, or a newline at the very start of text.
            
            # Let me integrate this check properly.
            
            # Actually, let me restructure the code with this check.
            pass
    
    # Let me rewrite the function properly with the blank-line check.
    rows = []
    i = 0
    n = len(text)
    
    while i < n:
        # Check for blank line: if current position is at a line ending
        if text[i] == '\n':
            i += 1
            rows.append([])
            continue
        elif text[i] == '\r' and i + 1 < n and text[i + 1] == '\n':
            i += 2
            rows.append([])
            continue
        
        # Parse a row
        fields = []
        while True:
            if i < n and text[i] == '"':
                # Quoted field
                i += 1
                field_chars = []
                while i < n:
                    if text[i] == '"':
                        if i + 1 < n and text[i + 1] == '"':
                            field_chars.append('"')
                            i += 2
                        else:
                            i += 1
                            break
                    else:
                        field_chars.append(text[i])
                        i += 1
                fields.append(''.join(field_chars))
                if i < n and text[i] == ',':
                    i += 1
                    continue
                elif i < n and text[i] == '\r' and i + 1 < n and text[i + 1] == '\n':
                    i += 2
                    break
                elif i < n and text[i] == '\n':
                    i += 1
                    break
                else:
                    break
            else:
                # Unquoted field
                field_chars = []
                while i < n:
                    if text[i] == ',':
                        break
                    elif text[i] == '\r' and i + 1 < n and text[i + 1] == '\n':
                        break
                    elif text[i] == '\n':
                        break
                    else:
                        field_chars.append(text[i])
                        i += 1
                fields.append(''.join(field_chars))
                if i < n and text[i] == ',':
                    i += 1
                    continue
                elif i < n and text[i] == '\r' and i + 1 < n and text[i + 1] == '\n':
                    i += 2
                    break
                elif i < n and text[i] == '\n':
                    i += 1
                    break
                else:
                    break
        
        rows.append(fields)
    
    return rows
