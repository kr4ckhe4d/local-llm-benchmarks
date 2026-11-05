def wrap_(text, width):
    # Expand tabs: replace each tab with spaces to next multiple of 8
    expanded = []
    col = 0
    for ch in text:
        if ch == '\t':
            spaces = 8 - (col % 8)
            expanded.append(' ' * spaces)
            col += spaces
        else:
            expanded.append(ch)
            col += 1
    text = ''.join(expanded)
    
    # Collapse whitespace: replace any sequence of whitespace with a single space
    # But we need to be careful: textwrap.wrap splits on whitespace and joins with single space
    # First, let's split into words (sequences of non-whitespace)
    # Actually, let's do it more carefully like textwrap does
    
    # Replace all whitespace sequences with single space
    import re
    # Wait, we can't import re? The problem says "without importing textwrap". 
    # It doesn't say we can't import other modules. But to be safe, let's do it manually.
    
    # Collapse whitespace: replace any run of whitespace chars with a single space
    collapsed = []
    in_whitespace = False
    for ch in text:
        if ch.isspace():
            if not in_whitespace:
                collapsed.append(' ')
                in_whitespace = True
        else:
            collapsed.append(ch)
            in_whitespace = False
    text = ''.join(collapsed).strip()
    
    if not text:
        return []
    
    words = text.split(' ')
    
    lines = []
    current_line = []
    current_len = 0
    
    for word in words:
        word_len = len(word)
        
        if not current_line:
            # First word on this line
            if word_len <= width:
                current_line.append(word)
                current_len = word_len
            else:
                # Word longer than width: break it
                # Add as many full chunks as possible
                while word_len > width:
                    lines.append(word[:width])
                    word = word[width:]
                    word_len = len(word)
                # Now word_len <= width, treat as normal
                if word_len > 0:
                    current_line.append(word)
                    current_len = word_len
        else:
            # Adding this word with a preceding space
            if current_len + 1 + word_len <= width:
                current_line.append(word)
                current_len += 1 + word_len
            else:
                # Can't fit, finalize current line
                lines.append(' '.join(current_line))
                current_line = []
                current_len = 0
                # Now try to add word to new line
                if word_len <= width:
                    current_line.append(word)
                    current_len = word_len
                else:
                    # Break the word
                    while word_len > width:
                        lines.append(word[:width])
                        word = word[width:]
                        word_len = len(word)
                    if word_len > 0:
                        current_line.append(word)
                        current_len = word_len
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines
