def wrap_(text, width):
    if width <= 0:
        raise ValueError("width must be a positive integer")
    
    # Expand tabs to spaces (tabsize=8 by default)
    expanded = ""
    col = 0
    for ch in text:
        if ch == '\t':
            spaces = 8 - (col % 8)
            expanded += ' ' * spaces
            col += spaces
        elif ch == '\n':
            expanded += '\n'
            col = 0
        else:
            expanded += ch
            col += 1
    
    # Replace each whitespace character with a single space (runs are NOT collapsed)
    # But we need to preserve newlines? The problem says "each whitespace character becomes one space"
    # and "whitespace at each line break is dropped"
    # Let's interpret: all whitespace (space, tab, newline, etc.) becomes a single space.
    # But newlines are special - they represent line breaks in the original text.
    # Actually, re-reading: "tabs are expanded and each whitespace character becomes one space (runs are NOT collapsed)"
    # So every whitespace char (space, tab, newline, \r, etc.) becomes exactly one space.
    # Then "whitespace at each line break is dropped" means when we wrap, leading/trailing whitespace on lines is stripped.
    
    # First, expand tabs, then replace all whitespace with single spaces
    result = []
    i = 0
    # We already expanded tabs above. Now replace all whitespace chars with single space.
    # But we need to track word boundaries. Let's build a normalized string.
    
    # Actually, let me re-think. The standard textwrap:
    # 1. Expand tabs (tabsize=8)
    # 2. Each whitespace char becomes one space (so multiple spaces remain as multiple spaces, but tabs become spaces)
    #    Wait, "each whitespace character becomes one space" - so a tab becomes one space? No, tabs are expanded first.
    #    After tab expansion, each remaining whitespace char (space, newline, etc.) becomes one space.
    #    So "  " (two spaces) stays as "  " (two spaces). " \n " becomes "   " (three spaces)? 
    #    Hmm, but textwrap.wrap with default options: whitespace is normalized such that each whitespace 
    #    character becomes a single space, but consecutive whitespace are not collapsed.
    #    Actually looking at Python docs: "Each whitespace character is replaced with a single space."
    #    So ' ' -> ' ', '\t' -> ' ' (after expansion), '\n' -> ' ', etc. But runs of whitespace: 
    #    if you have "  " (two spaces), each becomes one space, so you still have two spaces.
    #    If you have "\t\t", after tab expansion you get spaces, each becomes one space.
    
    # Let me just do: expand tabs to spaces (tabsize=8), then replace every whitespace character 
    # (including the ones from tab expansion?) No, tab expansion already produces spaces.
    # After tab expansion, replace each whitespace character (space, newline, \r, \f, \v) with a single space.
    # But since tabs are already expanded to spaces, the only whitespace left are spaces and newlines.
    # Each space stays a space, each newline becomes a space.
    
    # Let's redo properly:
    # Step 1: Expand tabs (tabsize=8)
    # Step 2: Replace each whitespace character (space, tab already handled, newline, \r, etc.) with a single space.
    #   Since tabs are already expanded, we just need to handle newlines and other whitespace becoming spaces.
    
    # After step 1, we have a string with spaces and newlines (and possibly other whitespace if input had \r etc.)
    # Let me handle all whitespace in step 2: replace any whitespace char with a single space.
    
    normalized = []
    for ch in expanded:
        if ch.isspace():
            normalized.append(' ')
        else:
            normalized.append(ch)
    normalized = ''.join(normalized)
    
    # Now split into words, preserving spaces as separators but keeping track of them.
    # Actually, we need to break on whitespace but keep the whitespace info for determining line breaks.
    # 
    # Approach: Split the normalized string into tokens where each token is either a word (non-whitespace) 
    # or a single space (since each whitespace became one space, runs of whitespace are multiple consecutive spaces).
    # 
    # When wrapping:
    # - We build lines up to `width` characters.
    # - Leading whitespace of the whole text is kept.
    # - At line breaks, trailing whitespace of current line and leading whitespace of next line are dropped.
    # - Words longer than width are broken.
    
    # Let's split into a list of "chunks" where each chunk is either a word or a single space.
    chunks = []
    current = []
    is_space_mode = None  # True if building a space chunk, False if building a word chunk
    
    for ch in normalized:
        if ch == ' ':
            if is_space_mode is None:
                is_space_mode = True
                current = [' ']
            elif is_space_mode:
                current.append(' ')
            else:
                # Was in word mode, finish word, start space chunk
                chunks.append((''.join(current), False))
                current = [' ']
                is_space_mode = True
        else:
            if is_space_mode is None:
                is_space_mode = False
                current = [ch]
            elif not is_space_mode:
                current.append(ch)
            else:
                # Was in space mode, finish space chunk, start word chunk
                chunks.append((''.join(current), True))
                current = [ch]
                is_space_mode = False
    
    if current:
        chunks.append((''.join(current), is_space_mode))
    
    # Now we have chunks: (text, is_whitespace)
    # We need to form lines. Each line is built by adding chunks.
    # Leading whitespace of the whole text is kept.
    # At each line break, trailing whitespace (spaces) at end of current line and leading whitespace at start of next line are dropped.
    # Words longer than width are broken.
    
    lines = []
    current_line_parts = []
    current_line_len = 0
    
    for chunk_text, is_ws in chunks:
        if is_ws:
            # This is a whitespace chunk (one or more spaces)
            # If current_line_len + len(chunk_text) <= width, add it
            # Otherwise, we need to break the line. But whitespace at line break is dropped.
            if current_line_len + len(chunk_text) <= width:
                current_line_parts.append(chunk_text)
                current_line_len += len(chunk_text)
            else:
                # Line break needed. Drop trailing whitespace from current line.
                # Remove trailing space chunks from current_line_parts
                while current_line_parts and current_line_parts[-1].isspace():
                    removed = current_line_parts.pop()
                    current_line_len -= len(removed)
                if current_line_parts:
                    lines.append(''.join(current_line_parts))
                # Start new line. Drop leading whitespace (this chunk).
                current_line_parts = []
                current_line_len = 0
                # The whitespace chunk is dropped entirely at the break.
                # Next chunk (if any) will be a word, so no leading whitespace issue.
        else:
            # This is a word chunk
            if current_line_len + len(chunk_text) <= width:
                current_line_parts.append(chunk_text)
                current_line_len += len(chunk_text)
            else:
                # Need to break the word if it's longer than width, or break before it.
                # First, finalize current line (dropping trailing whitespace)
                while current_line_parts and current_line_parts[-1].isspace():
                    removed = current_line_parts.pop()
                    current_line_len -= len(removed)
                if current_line_parts:
                    lines.append(''.join(current_line_parts))
                current_line_parts = []
                current_line_len = 0
                
                # Now break the word if necessary
                remaining = chunk_text
                while len(remaining) > width:
                    # Take width characters
                    lines.append(remaining[:width])
                    remaining = remaining[width:]
                # remaining has length <= width, add to new line
                if remaining:
                    current_line_parts.append(remaining)
                    current_line_len += len(remaining)
    
    # Finalize last line
    while current_line_parts and current_line_parts[-1].isspace():
        removed = current_line_parts.pop()
        current_line_len -= len(removed)
    if current_line_parts:
        lines.append(''.join(current_line_parts))
    
    # Handle edge case: if text starts with whitespace, leading whitespace is kept.
    # Our algorithm: if the first chunk is whitespace and current_line_parts is empty, 
    # we need to handle it specially. Let me reconsider.
    
    # Actually, let me re-examine. If the whole text starts with spaces, those should be kept.
    # In our loop, if the first chunk is whitespace and current_line_len is 0, 
    # we check if 0 + len(chunk) <= width. If yes, we add it. That's correct.
    # If no (chunk longer than width), we'd enter the else branch, drop trailing whitespace 
    # (none), finalize empty line (skip), drop leading whitespace (the chunk), and start new line.
    # But we should keep leading whitespace of the whole text.
    
    # Hmm, the condition "whitespace at each line break is dropped" means at line BREAKS, not at the very beginning.
    # So leading whitespace at the start of the whole text should be kept.
    
    # Let me adjust: when we're at the very beginning (no line finalized yet, and this is the first content),
    # leading whitespace should be kept.
    
    # I think my current approach mostly works but let me trace through an example.
    # text = "  hello world", width = 5
    # normalized = "  hello world"
    # chunks = [("  ", True), ("hello", False), (" ", True), ("world", False)]
    # 
    # chunk 1: "  ", is_ws=True. current_line_len=0, 0+2=2<=5, add. parts=["  "], len=2.
    # chunk 2: "hello", is_ws=False. 2+5=7>5. Finalize: drop trailing ws? "  " is trailing ws. Drop it. 
    #   parts=[], finalize empty (skip). Break word "hello" (len 5 <= 5? No, 5<=5 is ok... wait 2+5=7>5).
    #   After dropping trailing ws, len=0. Now 0+5=5<=5, add "hello". parts=["hello"], len=5.
    # chunk 3: " ", is_ws=True. 5+1=6>5. Finalize: drop trailing ws? "hello" is not ws. Finalize "hello". 
    #   Drop leading ws (this chunk). parts=[], len=0.
    # chunk 4: "world", is_ws=False. 0+5=5<=5, add. parts=["world"], len=5.
    # Final: finalize "world".
    # Result: ["hello", "world"]
    # But expected: leading whitespace "  " should be kept! So first line should start with "  ".
    # 
    # The issue is we dropped the leading whitespace "  " when breaking. We should not drop leading whitespace 
    # at the very first break if it's the beginning of the text.
    
    # Let me revise: only drop leading whitespace at a break if there's already a finalized line.
    # If we're creating the first line, leading whitespace is kept.
    
    # Actually, re-reading the problem: "whitespace at each line break is dropped (trailing whitespace of a line 
    # and leading whitespace of the next; leading whitespace of the whole text is kept)"
    # So at each break, we drop trailing ws of current and leading ws of next. But the very first line's 
    # leading whitespace (if any) is kept.
    
    # So when we break, we drop leading whitespace of the NEXT line. The first line is not "next" - it's the first.
    
    # In my algorithm, when I encounter a whitespace chunk that doesn't fit, I drop it (as leading whitespace 
    # of the next line). But if this is the first line being formed, it shouldn't be dropped.
    
    # Let me track whether any line has been finalized. If no line has been finalized yet, this is the first line, 
    # and leading whitespace should be kept.
    
    # Let me rewrite the logic more carefully.
    
    lines = []
    current_line_parts = []
    current_line_len = 0
    first_line = True  # True if we haven't finalized any line yet
    
    for chunk_text, is_ws in chunks:
        if is_ws:
            if current_line_len + len(chunk_text) <= width:
                current_line_parts.append(chunk_text)
                current_line_len += len(chunk_text)
            else:
                # Need to break. Drop trailing whitespace from current line.
                while current_line_parts and current_line_parts[-1].isspace():
                    removed = current_line_parts.pop()
                    current_line_len -= len(removed)
                if current_line_parts:
                    lines.append(''.join(current_line_parts))
                    first_line = False
                # Drop leading whitespace (this chunk) for the next line.
                # But if first_line is still True and current_line_parts is empty (nothing was on this line),
                # we should keep it? No - if we're breaking before placing any content, and this whitespace 
                # is at the start, it's leading whitespace of the whole text, keep it.
                # Actually, if current_line_parts is empty and first_line is True, this whitespace is the 
                # beginning of the text. Keep it.
                if first_line and not current_line_parts:
                    # Keep this whitespace as start of first line
                    # But it didn't fit! If len(chunk_text) > width, we need to break it.
                    if len(chunk_text) > width:
                        # Break the whitespace chunk
                        remaining = chunk_text
                        while len(remaining) > width:
                            lines.append(remaining[:width])
                            remaining = remaining[width:]
                            first_line = False
                        if remaining:
                            current_line_parts.append(remaining)
                            current_line_len += len(remaining)
                    else:
                        # It fits in a new line
                        current_line_parts.append(chunk_text)
                        current_line_len += len(chunk_text)
                else:
                    # Drop this whitespace chunk (leading whitespace of next line)
                    current_line_parts = []
                    current_line_len = 0
        else:
            if current_line_len + len(chunk_text) <= width:
                current_line_parts.append(chunk_text)
                current_line_len += len(chunk_text)
            else:
                # Finalize current line (drop trailing whitespace)
                while current_line_parts and current_line_parts[-1].isspace():
                    removed = current_line_parts.pop()
                    current_line_len -= len(removed)
                if current_line_parts:
                    lines.append(''.join(current_line_parts))
                    first_line = False
                current_line_parts = []
                current_line_len = 0
                
                # Break the word if necessary
                remaining = chunk_text
                while len(remaining) > width:
                    lines.append(remaining[:width])
                    remaining = remaining[width:]
                    first_line = False
                if remaining:
                    current_line_parts.append(remaining)
                    current_line_len += len(remaining)
    
    # Finalize last line
    while current_line_parts and current_line_parts[-1].isspace():
        removed = current_line_parts.pop()
        current_line_len -= len(removed)
    if current_line_parts:
        lines.append(''.join(current_line_parts))
    
    return lines
