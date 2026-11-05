def wrap_(text, width):
    # Expand tabs: replace each tab with spaces to reach next multiple of 8
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
    
    if width <= 0:
        return list(text)
    
    # Collapse whitespace runs to single spaces, preserving leading whitespace of text
    collapsed = []
    prev_was_ws = False
    for ch in text:
        if ch in ' \n\r\f\v':
            if not prev_was_ws:
                collapsed.append(' ')
            prev_was_ws = True
        else:
            collapsed.append(ch)
            prev_was_ws = False
    
    collapsed_text = ''.join(collapsed)
    
    # Strip leading and trailing whitespace (matching textwrap default behavior)
    collapsed_text = collapsed_text.strip()
    
    if not collapsed_text:
        return []
    
    # Split into words
    words = collapsed_text.split(' ')
    words = [w for w in words if w]
    
    if not words:
        return []
    
    lines = []
    current_line = []
    current_len = 0
    
    for word in words:
        if current_len == 0:
            if len(word) <= width:
                current_line.append(word)
                current_len = len(word)
            else:
                while len(word) > width:
                    lines.append(word[:width])
                    word = word[width:]
                current_line.append(word)
                current_len = len(word)
        else:
            if current_len + 1 + len(word) <= width:
                current_line.append(word)
                current_len += 1 + len(word)
            else:
                lines.append(' '.join(current_line))
                current_line = []
                current_len = 0
                if len(word) <= width:
                    current_line.append(word)
                    current_len = len(word)
                else:
                    while len(word) > width:
                        lines.append(word[:width])
                        word = word[width:]
                    current_line.append(word)
                    current_len = len(word)
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines
