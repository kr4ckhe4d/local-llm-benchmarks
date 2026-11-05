def wrap_(text, width):
    # Expand tabs: replace each tab with spaces to reach next multiple of 8
    def expand_tabs(s):
        result = []
        col = 0
        for ch in s:
            if ch == '\t':
                spaces = 8 - (col % 8)
                result.append(' ' * spaces)
                col += spaces
            else:
                result.append(ch)
                col += 1
        return ''.join(result)
    
    # Collapse whitespace: replace any run of whitespace with a single space
    def collapse_whitespace(s):
        import re
        return re.sub(r'\s+', ' ', s).strip()
    
    text = expand_tabs(text)
    text = collapse_whitespace(text)
    
    if not text:
        return []
    
    if width <= 0:
        return []
    
    words = text.split(' ')
    
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if not word:
            continue
        
        # If the word itself is longer than width, we need to break it
        if len(word) > width:
            # First, flush the current line if it has content
            if current_line:
                lines.append(' '.join(current_line))
                current_line = []
                current_length = 0
            
            # Break the long word into chunks of width
            start = 0
            while start < len(word):
                chunk = word[start:start + width]
                lines.append(chunk)
                start += width
        else:
            # Check if adding this word would exceed width
            if current_length == 0:
                # Empty line, add word
                current_line.append(word)
                current_length = len(word)
            else:
                # Adding word would make current_length + 1 + len(word)
                if current_length + 1 + len(word) <= width:
                    current_line.append(word)
                    current_length += 1 + len(word)
                else:
                    # Flush current line
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)
    
    # Don't forget the last line
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines
