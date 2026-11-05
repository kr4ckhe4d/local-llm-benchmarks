def wrap_(text, width):
    # Expand tabs to spaces (default tabsize=8)
    expanded = text.expandtabs(8)
    
    # Collapse whitespace: replace any run of whitespace with a single space
    # Then strip leading/trailing whitespace
    import re
    collapsed = re.sub(r'\s+', ' ', expanded).strip()
    
    if not collapsed:
        return []
    
    # Split into words
    words = collapsed.split(' ')
    
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        # If the word itself is longer than width, we need to break it
        if len(word) > width:
            # First, if current_line is not empty, flush it
            if current_line:
                lines.append(' '.join(current_line))
                current_line = []
                current_length = 0
            
            # Break the long word into chunks of size width
            i = 0
            while i < len(word):
                chunk = word[i:i+width]
                lines.append(chunk)
                i += width
        else:
            # Check if adding this word would exceed width
            if current_line:
                new_length = current_length + 1 + len(word)
            else:
                new_length = len(word)
            
            if new_length <= width:
                current_line.append(word)
                current_length = new_length
            else:
                # Flush current line
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
    
    # Don't forget the last line
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines
