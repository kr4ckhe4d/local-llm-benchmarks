def wrap_(text, width):
    if width <= 0:
        raise ValueError("invalid width")
    
    # Expand tabs to spaces (tabsize=8 by default)
    expanded = ""
    col = 0
    for ch in text:
        if ch == '\t':
            spaces = 8 - (col % 8)
            expanded += ' ' * spaces
            col += spaces
        else:
            expanded += ch
            col += 1
    
    # Replace each whitespace character with a single space (runs are NOT collapsed)
    # But we need to preserve the structure for splitting.
    # Actually, "each whitespace character becomes one space" means every whitespace char (space, tab already handled, newline, etc.) becomes a single space.
    # So we replace all whitespace characters with a single space.
    # But wait: tabs are already expanded to spaces. Now we need to handle other whitespace like \n, \r, etc.
    # Let's replace all whitespace characters (except those already handled as spaces from tab expansion) with a single space.
    # Actually, the instruction says "each whitespace character becomes one space (runs are NOT collapsed)".
    # So every whitespace character in the original text (after tab expansion) becomes exactly one space.
    # But tab expansion already produced spaces. Let me re-read: "tabs are expanded and each whitespace character becomes one space".
    # I think this means: first expand tabs, then every whitespace character (including the spaces from tab expansion? No, that doesn't make sense.)
    # Let me interpret it as: in the original text, each whitespace character (space, tab, newline, etc.) is replaced by a single space. Tabs are expanded first (to spaces), then all whitespace chars become single spaces. But if tabs are expanded to spaces, those spaces are already spaces. Hmm.
    # Actually, I think the intent is: tabs are expanded to spaces (using tabsize=8), and then every whitespace character in the resulting string is treated as a single space for the purpose of splitting. But "runs are NOT collapsed" means consecutive whitespace characters remain as consecutive spaces.
    # Let me just replace all whitespace characters in the original text with a single space, but first expand tabs.
    # Wait, if we expand tabs first, then replace all whitespace with single space, the spaces from tab expansion would also be replaced by single space (which they already are). So effectively, every whitespace char in original becomes one space.
    
    # Let me redo: expand tabs, then replace every whitespace character with a single space.
    # After tab expansion, we have a string. Now replace every whitespace character (space, \n, \r, \f, \v, etc.) with a single space.
    # But spaces are already spaces, so replacing space with space is no-op. Other whitespace chars become spaces.
    
    result = []
    for ch in expanded:
        if ch.isspace():
            result.append(' ')
        else:
            result.append(ch)
    text_processed = ''.join(result)
    
    # Now split into words and whitespace runs.
    # We need to identify "words" (non-whitespace sequences) and whitespace runs.
    # Since all whitespace is now single spaces, whitespace runs are sequences of spaces.
    
    # Tokenize: split into tokens where each token is either a word (non-space) or a single space.
    # Actually, we need to handle the wrapping logic:
    # - Leading whitespace of the whole text is kept.
    # - Whitespace at line breaks is dropped (trailing whitespace of a line and leading whitespace of the next).
    # - Words longer than width are broken.
    
    # Let's think about how textwrap.wrap works with default options:
    # 1. Expand tabs.
    # 2. Replace whitespace with single spaces (but runs not collapsed).
    # 3. Split into words and whitespace.
    # 4. Build lines: start with empty line. Add words and whitespace. When adding a word would exceed width, break the line.
    # 5. Leading whitespace of the entire text is preserved.
    # 6. Trailing whitespace on a line is dropped. Leading whitespace on the next line is dropped (except for the very first line's leading whitespace).
    # 7. Long words are broken.
    
    # Let me implement step by step.
    
    # First, handle leading whitespace of the whole text.
    # Find the first non-whitespace character.
    first_non_ws = 0
    while first_non_ws < len(text_processed) and text_processed[first_non_ws] == ' ':
        first_non_ws += 1
    
    leading_ws = text_processed[:first_non_ws]
    rest = text_processed[first_non_ws:]
    
    # Now tokenize the rest into words and whitespace runs.
    # A word is a maximal sequence of non-space characters.
    # A whitespace run is a maximal sequence of space characters.
    
    tokens = []
    i = 0
    while i < len(rest):
        if rest[i] == ' ':
            j = i
            while j < len(rest) and rest[j] == ' ':
                j += 1
            tokens.append(('ws', rest[i:j]))
            i = j
        else:
            j = i
            while j < len(rest) and rest[j] != ' ':
                j += 1
            tokens.append(('word', rest[i:j]))
            i = j
    
    # Now build lines.
    lines = []
    current_line = leading_ws  # Start with leading whitespace of the whole text
    
    for token_type, token_val in tokens:
        if token_type == 'ws':
            # Whitespace between words. We need to decide whether to add it to the current line.
            # If current_line is empty (or just leading_ws), we might need to handle carefully.
            # Actually, leading_ws is already added. Now for subsequent whitespace:
            # If we're at the start of a new line (current_line is empty after dropping leading ws?), 
            # Let me think differently.
            
            # The rule: whitespace at line breaks is dropped. So when we break a line, trailing whitespace on that line is dropped, and leading whitespace on the next line is dropped.
            # But leading whitespace of the whole text is kept.
            
            # Let me restructure: 
            # We build lines. Each line starts with some content. When we need to break, we finalize the current line (dropping trailing whitespace) and start a new line (dropping leading whitespace, except for the very first line).
            
            # Let me use a different approach:
            # Process tokens, maintaining current_line.
            # For each token:
            #   If it's whitespace:
            #     If current_line is empty (start of a new line after a break), skip this whitespace (it's leading whitespace of a new line, which should be dropped).
            #     Else, tentatively add it to current_line. But we need to check if adding subsequent words will fit.
            #   If it's a word:
            #     Check if current_line + word fits in width.
            #     If yes, add word to current_line.
            #     If no, break the line: finalize current_line (drop trailing whitespace), start new line with the word (or part of it if word is too long).
            
            # This is getting complex. Let me look at how textwrap actually works.
            
            # Actually, let me try a simpler approach based on the algorithm:
            # 1. Split text into words and whitespace, preserving order.
            # 2. Build lines greedily.
            
            # Let me restart with a cleaner implementation.
            
            pass
    
    # Let me restart with a cleaner approach.
    
    # Re-tokenize including leading whitespace properly.
    # Actually, let me include leading whitespace as part of the token stream.
    
    tokens = []
    i = 0
    while i < len(text_processed):
        if text_processed[i] == ' ':
            j = i
            while j < len(text_processed) and text_processed[j] == ' ':
                j += 1
            tokens.append(('ws', text_processed[i:j]))
            i = j
        else:
            j = i
            while j < len(text_processed) and text_processed[j] != ' ':
                j += 1
            tokens.append(('word', text_processed[i:j]))
            i = j
    
    if not tokens:
        return []
    
    lines = []
    current_line = ""
    is_first_line = True
    
    for token_type, token_val in tokens:
        if token_type == 'ws':
            # Whitespace token
            if current_line == "" and not is_first_line:
                # Leading whitespace on a new line (after a break) - drop it
                continue
            elif current_line == "" and is_first_line:
                # Leading whitespace of the whole text - keep it
                current_line = token_val
            else:
                # Whitespace in the middle of a line - tentatively add
                # But we need to check if the next word fits.
                # For now, add it to current_line.
                current_line += token_val
        else:
            # Word token
            word = token_val
            
            if current_line == "":
                # Start of a line (possibly after dropping leading ws)
                if len(word) <= width:
                    current_line = word
                else:
                    # Word is longer than width, break it
                    # Add as much as fits
                    current_line = word[:width]
                    remaining = word[width:]
                    # Finalize current line
                    lines.append(current_line)
                    current_line = ""
                    # Continue with remaining word on new line(s)
                    while len(remaining) > width:
                        lines.append(remaining[:width])
                        remaining = remaining[width:]
                    if remaining:
                        current_line = remaining
            else:
                # Check if adding word fits
                if len(current_line) + len(word) <= width:
                    current_line += word
                else:
                    # Need to break the line
                    # Drop trailing whitespace from current_line
                    stripped_line = current_line.rstrip(' ')
                    if stripped_line:
                        lines.append(stripped_line)
                    current_line = ""
                    
                    # Now place the word on the new line
                    if len(word) <= width:
                        current_line = word
                    else:
                        # Word is longer than width, break it
                        current_line = word[:width]
                        remaining = word[width:]
                        lines.append(current_line)
                        current_line = ""
                        while len(remaining) > width:
                            lines.append(remaining[:width])
                            remaining = remaining[width:]
                        if remaining:
                            current_line = remaining
    
    # Finalize the last line
    if current_line:
        stripped_line = current_line.rstrip(' ')
        if stripped_line:
            lines.append(stripped_line)
    
    return lines
