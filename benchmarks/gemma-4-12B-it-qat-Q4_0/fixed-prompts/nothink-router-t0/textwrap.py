def wrap_(text, width):
    # Expand tabs to spaces (standard tab stop is 8)
    text = text.expandtabs()
    
    # Replace all whitespace characters with a single space
    # Note: The prompt specifies "runs are NOT collapsed", but also says 
    # "each whitespace character becomes one space". This implies ' \t\n' 
    # becomes '   '. However, standard textwrap behavior usually treats 
    # sequences of whitespace as one. To strictly follow "each becomes one":
    chars = []
    for char in text:
        if char.isspace():
            chars.append(' ')
        else:
            chars.append(char)
    
    # Reconstruct string to handle leading/trailing logic
    # The prompt says "whitespace at each line break is dropped".
    # This means we treat the text as a sequence of words and spaces.
    raw_content = "".join(chars)
    
    # Split into tokens (words and spaces)
    # We need to preserve the distinction between words and spaces 
    # because "runs are NOT collapsed".
    tokens = []
    if not raw_content:
        return []
    
    i = 0
    while i < len(raw_content):
        if raw_content[i].isspace():
            # Group consecutive spaces as they are individual tokens
            j = i
            while j < len(raw_content) and raw_content[j].isspace():
                j += 1
            tokens.append(raw_content[i:j])
            i = j
        else:
            j = i
            while j < len(raw_content) and not raw_content[j].isspace():
                j += 1
            tokens.append(raw_content[i:j])
            i = j

    lines = []
    current_line = ""
    
    for token in tokens:
        # If token is whitespace, it's treated as a space for length
        # but we must handle the "dropped at line break" rule.
        if token.isspace():
            # If current_line is empty, this is leading whitespace (keep it)
            if not current_line:
                current_line += token
            else:
                # If adding this space exceeds width, we must drop it 
                # because whitespace at line breaks is dropped.
                if len(current_line) + len(token) <= width:
                    current_line += token
                else:
                    # This space would be at a break, so we drop it
                    pass
        else:
            # It's a word. If it's longer than width, it must be broken.
            if len(token) > width:
                # If there is content in current_line, flush it first
                if current_line:
                    lines.append(current_line.rstrip())
                    current_line = ""
                
                # Break the long word into chunks of 'width'
                for i in range(0, len(token), width):
                    chunk = token[i:i+width]
                    # If it's not the first chunk and we are at the start of a line,
                    # we don't add spaces between chunks of a broken word.
                    lines.append(chunk)
                continue

            # Standard word wrapping logic
            if len(current_line) + len(token) <= width:
                current_line += token
            else:
                # Flush current line (dropping trailing whitespace)
                lines.append(current_line.rstrip())
                current_line = token

    if current_line:
        lines.append(current_line.rstrip())
        
    return lines
