def wrap_(text, width):
    # Expand tabs and collapse whitespace
    # First, handle tabs: replace each tab with spaces to align to next multiple of 8
    # But textwrap's default is to expand tabs based on tabsize=8, counting from the start of the line
    # Actually, textwrap.wrap by default does NOT expand tabs in the same way as textwrap.expandtabs
    # Let me check: textwrap.wrap default options:
    # - whitespace is collapsed (multiple spaces become one)
    # - tabs are expanded (using tabsize=8)
    # - words longer than width are broken
    # - break_long_words=True, break_on_hyphens=True by default
    
    # First, expand tabs. The tab expansion in textwrap is done per-line after splitting.
    # Actually, let's look at how textwrap works:
    # 1. It first splits the text into lines (by newlines)
    # 2. For each line, it expands tabs
    # 3. Then it collapses whitespace
    # 4. Then it wraps
    
    # Let me re-read the textwrap source behavior:
    # textwrap.wrap calls _whitespace_split after expanding tabs
    # The _whitespace_split function splits on whitespace and collapses
    
    # Step 1: Split text into lines by newline
    lines = text.split('\n')
    
    # Step 2: For each line, expand tabs and collapse whitespace
    def expand_and_collapse(line):
        # Expand tabs: replace each tab with spaces to reach next multiple of 8
        expanded = []
        col = 0
        for ch in line:
            if ch == '\t':
                spaces = 8 - (col % 8)
                expanded.append(' ' * spaces)
                col += spaces
            else:
                expanded.append(ch)
                col += 1
        expanded_str = ''.join(expanded)
        
        # Collapse whitespace: split on whitespace and join with single space
        # But we need to be careful: textwrap's _whitespace_split splits on whitespace
        # and returns the words. Multiple whitespace becomes a single space.
        words = expanded_str.split()
        return ' '.join(words)
    
    # Process each line
    processed_lines = []
    for line in lines:
        collapsed = expand_and_collapse(line)
        if collapsed:  # Only add non-empty lines
            processed_lines.append(collapsed)
    
    # Now wrap each processed line
    result = []
    for line in processed_lines:
        # Wrap this line
        words = line.split()
        current_line = []
        current_len = 0
        
        for word in words:
            if not word:
                continue
            
            # If word is longer than width, we need to break it
            if len(word) > width:
                # First, if current_line is not empty, add it
                if current_line:
                    result.append(' '.join(current_line))
                    current_line = []
                    current_len = 0
                
                # Break the word into chunks of width
                i = 0
                while i < len(word):
                    chunk = word[i:i+width]
                    result.append(chunk)
                    i += width
                continue
            
            # Check if adding this word would exceed width
            if current_line:
                new_len = current_len + 1 + len(word)
            else:
                new_len = len(word)
            
            if new_len <= width:
                if current_line:
                    current_len = new_len
                else:
                    current_len = len(word)
                current_line.append(word)
            else:
                # Add current line and start new one
                if current_line:
                    result.append(' '.join(current_line))
                current_line = [word]
                current_len = len(word)
        
        # Add remaining words
        if current_line:
            result.append(' '.join(current_line))
    
    return result
