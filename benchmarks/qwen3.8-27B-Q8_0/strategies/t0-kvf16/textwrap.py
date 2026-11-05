def wrap_(text, width):
    # Expand tabs to spaces (default tabsize=8)
    expanded = []
    col = 0
    for ch in text:
        if ch == '\t':
            next_tab = ((col // 8) + 1) * 8
            expanded.append(' ' * (next_tab - col))
            col = next_tab
        else:
            expanded.append(ch)
            col += 1
    text = ''.join(expanded)
    
    # Collapse whitespace: replace any run of whitespace with a single space
    # But we need to be careful: textwrap.wrap splits on whitespace and joins with single space
    # First, let's split into words (sequences of non-whitespace)
    words = []
    current = []
    for ch in text:
        if ch.isspace():
            if current:
                words.append(''.join(current))
                current = []
        else:
            current.append(ch)
    if current:
        words.append(''.join(current))
    
    # Now wrap the words
    lines = []
    current_line = []
    current_len = 0
    
    for word in words:
        if not word:
            continue
        
        if current_len == 0:
            # Start a new line with this word
            if len(word) <= width:
                current_line.append(word)
                current_len = len(word)
            else:
                # Word is longer than width, break it
                # First, if there's already a current line, flush it
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = []
                    current_len = 0
                
                # Break the word into chunks of width
                remaining = word
                while remaining:
                    if len(remaining) <= width:
                        lines.append(remaining)
                        remaining = ''
                    else:
                        lines.append(remaining[:width])
                        remaining = remaining[width:]
                # After breaking, current_line is empty
                current_line = []
                current_len = 0
        else:
            # There's already content on the current line
            # Check if adding this word (with a space) fits
            if current_len + 1 + len(word) <= width:
                current_line.append(word)
                current_len += 1 + len(word)
            else:
                # Doesn't fit, flush current line
                lines.append(' '.join(current_line))
                current_line = []
                current_len = 0
                
                # Now try to add the word to a new line
                if len(word) <= width:
                    current_line.append(word)
                    current_len = len(word)
                else:
                    # Word is longer than width, break it
                    remaining = word
                    while remaining:
                        if len(remaining) <= width:
                            lines.append(remaining)
                            remaining = ''
                        else:
                            lines.append(remaining[:width])
                            remaining = remaining[width:]
                    current_line = []
                    current_len = 0
    
    # Flush the last line if there's anything
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines
