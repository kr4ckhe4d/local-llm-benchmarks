def wrap_(text, width):
    if width <= 0:
        return []
    
    # Expand tabs (default tab size 8)
    # Python's textwrap uses expandtabs(8) by default
    text = text.expandtabs(8)
    
    # Collapse whitespace
    # Replace any sequence of whitespace with a single space
    import re
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading and trailing whitespace
    text = text.strip()
    
    if not text:
        return []
    
    # Split into words
    words = text.split(' ')
    
    lines = []
    current_line = ""
    
    for word in words:
        # If the word itself is longer than width, we need to break it
        if len(word) > width:
            # If there's already something in current_line, finalize it
            if current_line:
                lines.append(current_line)
                current_line = ""
            
            # Break the word into chunks of size 'width'
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            
            # If there's a remainder, it becomes the start of the new current_line
            if word:
                current_line = word
            else:
                current_line = ""
        else:
            # Word fits in width
            if not current_line:
                current_line = word
            else:
                # Check if adding this word fits in the current line
                # We need a space between words
                if len(current_line) + 1 + len(word) <= width:
                    current_line += " " + word
                else:
                    # Doesn't fit, finalize current line and start new one
                    lines.append(current_line)
                    current_line = word
    
    # Finalize the last line
    if current_line:
        lines.append(current_line)
        
    return lines
