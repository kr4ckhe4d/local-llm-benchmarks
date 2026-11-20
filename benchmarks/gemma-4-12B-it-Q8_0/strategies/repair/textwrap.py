def wrap_(text, width):
    # 1. Expand tabs (default 8)
    text = text.expandtabs()
    
    # 2. Handle line breaks: split into lines
    raw_lines = text.splitlines()
    if not raw_lines:
        return []
        
    processed_lines = []
    for i, line in enumerate(raw_lines):
        if i == 0:
            # Keep leading whitespace of the whole text
            processed_lines.append(line)
        else:
            # Drop leading and trailing whitespace of subsequent lines
            processed_lines.append(line.strip())
    
    # Join with a single space to represent the "dropped" newline whitespace
    # This creates a continuous stream where newlines are replaced by a space
    combined = " ".join(processed_lines)
    
    # 3. Process character by character to respect "runs are NOT collapsed"
    # and "each whitespace character becomes one space" (already handled by join/strip)
    res = []
    current_line = ""
    
    i = 0
    while i < len(combined):
        char = combined[i]
        
        if char.isspace():
            # If we can fit the space, add it
            if len(current_line) + 1 <= width:
                current_line += " "
                i += 1
            else:
                # Cannot fit the space, finish current line
                if current_line:
                    res.append(current_line)
                current_line = "" # Start new line empty (space will be handled next)
                i += 1
        else:
            # It's a non-space character (part of a word)
            j = i
            while j < len(combined) and not combined[j].isspace():
                j += 1
            word = combined[i:j]
            
            if len(current_line) + len(word) <= width:
                current_line += word
                i = j
            else:
                # Word doesn't fit in current line
                if not current_line:
                    # Word is longer than width and we are at start of a line
                    # Break the word into chunks of 'width'
                    for k in range(0, len(word), width):
                        chunk = word[k:k+width]
                        res.append(chunk)
                    i = j
                else:
                    # Current line has content, finish it and try word again
                    res.append(current_line)
                    current_line = ""
                    # Do not increment i, re-process word in next loop
                    
    if current_line:
        res.append(current_line)
        
    # Final cleanup: remove any empty strings and strip trailing whitespace 
    # from lines (as per "whitespace at line break is dropped")
    final = []
    for line in res:
        stripped = line.rstrip()
        if stripped:
            final.append(stripped)
            
    return final
