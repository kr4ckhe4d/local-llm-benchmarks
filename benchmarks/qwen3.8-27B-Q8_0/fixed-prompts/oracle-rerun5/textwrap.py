def wrap_(text, width):
    if width <= 0:
        raise ValueError("invalid width %r (must be a positive integer)" % (width,))
    
    # Expand tabs
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
    
    if not text:
        return []
    
    # Parse into words only, tracking positions
    words = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] not in ' \n\r\f\v':
            j = i
            while j < n and text[j] not in ' \n\r\f\v':
                j += 1
            words.append(text[i:j])
            i = j
        else:
            i += 1
    
    if not words:
        return []
    
    lines = []
    current_words = []
    current_len = 0
    
    for word in words:
        wlen = len(word)
        
        if not current_words:
            # First word on a new line
            if wlen <= width:
                current_words.append(word)
                current_len = wlen
            else:
                # Word is longer than width, break it
                remaining = word
                while len(remaining) > width:
                    lines.append(remaining[:width])
                    remaining = remaining[width:]
                current_words.append(remaining)
                current_len = len(remaining)
        else:
            # Adding this word with a space separator
            needed = current_len + 1 + wlen
            if needed <= width:
                current_words.append(word)
                current_len = needed
            else:
                # Need to break before this word
                # Flush current line
                lines.append(' '.join(current_words))
                current_words = []
                current_len = 0
                
                # Start new line with this word
                if wlen <= width:
                    current_words.append(word)
                    current_len = wlen
                else:
                    # Word is longer than width, break it
                    remaining = word
                    while len(remaining) > width:
                        lines.append(remaining[:width])
                        remaining = remaining[width:]
                    current_words.append(remaining)
                    current_len = len(remaining)
    
    if current_words:
        lines.append(' '.join(current_words))
    
    return lines
