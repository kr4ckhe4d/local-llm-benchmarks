def wrap_(text, width):
    if width <= 0:
        raise ValueError("invalid width %r (must be > 0)" % width)
    
    # Step 1: Expand tabs to spaces (tab size 8)
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
    
    # Step 2: Replace all whitespace characters with spaces
    normalized = []
    for ch in expanded:
        if ch in ' \t\n\r\f\v':
            normalized.append(' ')
        else:
            normalized.append(ch)
    
    text_normalized = ''.join(normalized)
    
    # Step 3: Split into words (sequences of non-space characters)
    words = []
    current_word = []
    for ch in text_normalized:
        if ch == ' ':
            if current_word:
                words.append(''.join(current_word))
                current_word = []
        else:
            current_word.append(ch)
    if current_word:
        words.append(''.join(current_word))
    
    # Step 4: Greedily pack words into lines
    lines = []
    current_line = []
    current_len = 0
    
    for word in words:
        if not word:
            continue
        
        # If the word itself is longer than width, we need to break it
        if len(word) > width:
            # First, if current_line is not empty, flush it
            if current_line:
                line = ' '.join(current_line)
                lines.append(line)
                current_line = []
                current_len = 0
            
            # Break the word into chunks of at most width
            i = 0
            while i < len(word):
                chunk = word[i:i+width]
                lines.append(chunk)
                i += width
            continue
        
        # Check if adding this word would exceed width
        if current_line:
            # Adding a space + word
            new_len = current_len + 1 + len(word)
        else:
            new_len = len(word)
        
        if new_len <= width:
            current_line.append(word)
            current_len = new_len
        else:
            # Flush current line
            if current_line:
                line = ' '.join(current_line)
                lines.append(line)
                current_line = []
                current_len = 0
            # Start new line with this word
            current_line.append(word)
            current_len = len(word)
    
    # Flush remaining
    if current_line:
        line = ' '.join(current_line)
        lines.append(line)
    
    # Step 5: Strip leading/trailing whitespace from each line
    result = []
    for line in lines:
        stripped = line.strip(' ')
        if stripped:
            result.append(stripped)
    
    return result
