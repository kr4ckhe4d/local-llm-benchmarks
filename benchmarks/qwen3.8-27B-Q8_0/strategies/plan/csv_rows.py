def csv_rows(text):
    """
    Parse RFC 4180 CSV text and return a list of rows, each a list of string fields.
    Matches csv.reader(io.StringIO(text)) behavior without importing csv.
    """
    if not text:
        return []

    rows = []
    row = []
    field = []
    
    # States
    UNQUOTED = 0
    QUOTED = 1
    AFTER_QUOTED = 2
    
    state = UNQUOTED
    i = 0
    n = len(text)
    
    # Track if we've seen any content that should produce a row
    # We'll finalize at the end if there's pending content
    has_pending = False  # whether we have started building a row/field
    
    while i < n:
        c = text[i]
        
        if state == UNQUOTED:
            if c == ',':
                # End current field, start new one
                row.append(''.join(field))
                field = []
                has_pending = True
                i += 1
            elif c == '\r':
                # Check for CRLF
                if i + 1 < n and text[i + 1] == '\n':
                    # CRLF
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    has_pending = True
                    i += 2
                else:
                    # Lone CR
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    has_pending = True
                    i += 1
            elif c == '\n':
                # LF
                row.append(''.join(field))
                rows.append(row)
                row = []
                field = []
                has_pending = True
                i += 1
            elif c == '"' and not field:
                # Start of quoted field (field is empty)
                state = QUOTED
                has_pending = True
                i += 1
            else:
                # Ordinary character
                field.append(c)
                has_pending = True
                i += 1
        
        elif state == QUOTED:
            if c == '"':
                # Check for escaped quote
                if i + 1 < n and text[i + 1] == '"':
                    # Doubled quote: escaped quote
                    field.append('"')
                    i += 2
                else:
                    # Closing quote
                    state = AFTER_QUOTED
                    i += 1
            elif c == '\r':
                # Line terminator inside quoted field: preserve as data
                if i + 1 < n and text[i + 1] == '\n':
                    # CRLF
                    field.append('\r')
                    field.append('\n')
                    i += 2
                else:
                    # Lone CR
                    field.append('\r')
                    i += 1
            elif c == '\n':
                # LF inside quoted field
                field.append('\n')
                i += 1
            else:
                # Ordinary character (including commas)
                field.append(c)
                i += 1
        
        elif state == AFTER_QUOTED:
            if c == ',':
                # End field, start new one
                row.append(''.join(field))
                field = []
                state = UNQUOTED
                has_pending = True
                i += 1
            elif c == '\r':
                # Line terminator
                if i + 1 < n and text[i + 1] == '\n':
                    # CRLF
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    state = UNQUOTED
                    has_pending = True
                    i += 2
                else:
                    # Lone CR
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    state = UNQUOTED
                    has_pending = True
                    i += 1
            elif c == '\n':
                # LF
                row.append(''.join(field))
                rows.append(row)
                row = []
                field = []
                state = UNQUOTED
                has_pending = True
                i += 1
            elif c == '"':
                # Another quoted portion appended to same field
                state = QUOTED
                i += 1
            else:
                # Ordinary character: append to field, return to UNQUOTED
                field.append(c)
                state = UNQUOTED
                i += 1
    
    # Finalize: if we have pending content, emit the last row
    # A trailing line terminator does not create an extra empty row.
    # If has_pending is True, we have a field/row in progress that needs to be emitted.
    # But we need to be careful: if the last thing was a line terminator, 
    # row and field are empty and has_pending is True, but we shouldn't emit an empty row.
    # Actually, let's think about this more carefully.
    
    # The key insight: after processing a line terminator, we reset row=[] and field=[].
    # If the input ends right after a line terminator, we should NOT emit another row.
    # If the input ends with content (no trailing terminator), we SHOULD emit the row.
    
    # How to distinguish? We can check if the last character processed was a line terminator.
    # Alternatively, we can track whether we're in the middle of a row.
    
    # Let's use a different approach: track if we've started a new row after the last terminator.
    # Actually, the simplest way: if field is non-empty OR row is non-empty, we have pending content.
    # But wait: after a line terminator, row=[] and field=[]. So if both are empty, no pending row.
    # If field is non-empty, we have a pending field.
    # If row is non-empty but field is empty, that means we just had a comma and then EOF? 
    # No, because after a comma we set field=[] but row has the previous fields.
    
    # Let me reconsider. The csv.reader behavior:
    # - "a\n" -> [['a']] (trailing newline doesn't create extra row)
    # - "a" -> [['a']]
    # - "\n" -> [[]]
    # - "" -> []
    
    # So the rule is: emit the final row if and only if there is any content in the current 
    # row or field that hasn't been emitted yet. But "\n" should emit [[]], while "a\n" should 
    # emit [['a']] and not [['a'], []].
    
    # The difference: after processing "\n", we have row=[] and field=[]. But we should still 
    # emit [[]] because the newline itself constitutes a row.
    
    # After processing "a\n", we have row=[] and field=[] (because we appended 'a' to row, 
    # then appended row to rows, then reset). So both are empty.
    
    # So we can't just check if row/field are empty. We need to know if the last thing 
    # processed was a line terminator or not.
    
    # Let me track this with a flag: last_was_terminator
    # Actually, let me re-examine the logic.
    
    # When we process a line terminator in UNQUOTED or AFTER_QUOTED:
    #   - We append the current field to row
    #   - We append row to rows
    #   - We reset row=[] and field=[]
    #   - We set has_pending = True
    #
    # When we process a comma in UNQUOTED or AFTER_QUOTED:
    #   - We append the current field to row
    #   - We reset field=[]
    #   - We set has_pending = True
    #
    # When we process an ordinary character:
    #   - We append to field
    #   - We set has_pending = True
    #
    # At EOF:
    #   - If has_pending is False, return rows (empty input case)
    #   - If has_pending is True, we need to decide whether to emit the current row.
    #
    # The issue is distinguishing between:
    #   - Input ended with a line terminator: don't emit extra row
    #   - Input ended with content: emit the row
    #
    # Let me track whether the last action was a line terminator.
    
    # I'll refactor to track this properly. Let me restart with a cleaner approach.
    
    # Actually, let me just check: if the last character in text is a line terminator 
    # (considering CRLF as one), then we don't emit an extra row. Otherwise, we do.
    
    # But this is tricky with CRLF. Let me use a different flag.
    
    # Let me redo this with a cleaner state machine that tracks whether we're 
    # in the middle of a row.
    
    # I'll restart the implementation with a cleaner approach.
    
    # Actually, let me just handle the finalization correctly by tracking 
    # whether we've seen any content since the last row was emitted.
    
    # The cleanest way: track if the current row has any fields or if we're 
    # in the middle of a field.
    
    # Let me just check: if field is non-empty, we definitely need to emit.
    # If field is empty but row is non-empty, we need to emit (e.g., "a," -> row=['a'], field=[]).
    # If both are empty, we only emit if the last thing was NOT a line terminator.
    
    # Wait, for "\n": after processing, row=[], field=[]. But we should emit [[]].
    # For "a\n": after processing, row=[], field=[]. But we should NOT emit extra.
    
    # The difference is that for "\n", the newline itself created a row. For "a\n", 
    # the row was already emitted when we processed the newline.
    
    # So the rule is: at EOF, emit the current row if and only if we are in the 
    # middle of a row (i.e., we haven't just finished a row with a line terminator).
    
    # Let me track this with a flag: in_middle_of_row
    # - Set to True when we start adding content to a row (first field or comma)
    # - Set to False when we emit a row (line terminator)
    
    # Actually, the simplest correct approach: 
    # At EOF, if field is non-empty OR row is non-empty, emit the row.
    # But for "\n", both are empty after processing, yet we need to emit [[]].
    
    # Hmm, let me look at this differently. Let me track whether we've started 
    # a new row that hasn't been emitted yet.
    
    # I think the cleanest solution is to track a flag `row_started` that is True 
    # when we've begun building a row (either by adding a field or encountering a comma) 
    # and False when we've emitted the row.
    
    # Let me just rewrite the whole thing more carefully.
    
    # I'll use a different approach: process the text, and at the end, check if 
    # there's any unemitted content.
    
    # Let me just handle it by checking if the last character was a line terminator.
    
    # For simplicity, let me check: if text ends with '\n' or '\r' (and not part of 
    # a CRLF that was already handled), then no extra row. But this is fragile.
    
    # Let me just use a flag.
    
    # I'll restart the implementation.
    
    pass  # This is getting complicated. Let me write it fresh.


def csv_rows(text):
    if not text:
        return []

    rows = []
    row = []
    field = []
    
    UNQUOTED = 0
    QUOTED = 1
    AFTER_QUOTED = 2
    
    state = UNQUOTED
    i = 0
    n = len(text)
    
    # Track whether we're in the middle of a row (have started but not yet emitted)
    in_row = False
    
    while i < n:
        c = text[i]
        
        if state == UNQUOTED:
            if c == ',':
                row.append(''.join(field))
                field = []
                in_row = True
                i += 1
            elif c == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    in_row = False
                    i += 2
                else:
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    in_row = False
                    i += 1
            elif c == '\n':
                row.append(''.join(field))
                rows.append(row)
                row = []
                field = []
                in_row = False
                i += 1
            elif c == '"' and not field:
                state = QUOTED
                in_row = True
                i += 1
            else:
                field.append(c)
                in_row = True
                i += 1
        
        elif state == QUOTED:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                else:
                    state = AFTER_QUOTED
                    i += 1
            elif c == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    field.append('\r')
                    field.append('\n')
                    i += 2
                else:
                    field.append('\r')
                    i += 1
            elif c == '\n':
                field.append('\n')
                i += 1
            else:
                field.append(c)
                i += 1
        
        elif state == AFTER_QUOTED:
            if c == ',':
                row.append(''.join(field))
                field = []
                state = UNQUOTED
                in_row = True
                i += 1
            elif c == '\r':
                if i + 1 < n and text[i + 1] == '\n':
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    state = UNQUOTED
                    in_row = False
                    i += 2
                else:
                    row.append(''.join(field))
                    rows.append(row)
                    row = []
                    field = []
                    state = UNQUOTED
                    in_row = False
                    i += 1
            elif c == '\n':
                row.append(''.join(field))
                rows.append(row)
                row = []
                field = []
                state = UNQUOTED
                in_row = False
                i += 1
            elif c == '"':
                state = QUOTED
                i += 1
            else:
                field.append(c)
                state = UNQUOTED
                i += 1
    
    # Finalize: if we're in the middle of a row, emit it
    if in_row:
        row.append(''.join(field))
        rows.append(row)
    
    return rows
