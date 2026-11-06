def wrap_(text, width):
    if width <= 0:
        raise ValueError("invalid width")
    
    # Expand tabs to spaces
    expanded = ""
    for ch in text:
        if ch == '\t':
            # Each tab advances to next multiple of 8 columns
            current_pos = len(expanded)
            spaces_needed = 8 - (current_pos % 8)
            expanded += " " * spaces_needed
        else:
            expanded += ch
    
    # Split text into tokens, preserving all whitespace runs as single spaces
    # We need to tokenize: sequences of non-whitespace chars are words,
    # sequences of whitespace chars become single spaces (but runs are NOT collapsed,
    # wait - "each whitespace character becomes one space (runs are NOT collapsed)"
    # This means each individual whitespace char becomes one space. So a run of 
    # multiple whitespace chars becomes multiple spaces? No wait - "runs are NOT collapsed"
    # means we don't collapse runs. But "each whitespace character becomes one space" 
    # means each whitespace char maps to exactly one space. So a run of N whitespace 
    # chars becomes N spaces. But then "whitespace at each line break is dropped" means
    # trailing whitespace on a line and leading whitespace on the next are dropped.
    # "leading whitespace of the whole text is kept"
    
    # Let me re-read: "each whitespace character becomes one space (runs are NOT collapsed)"
    # So every whitespace char (space, tab, newline, etc.) becomes exactly one space.
    # A run of 3 whitespace chars becomes 3 spaces.
    
    # Convert all whitespace characters to single spaces, keeping the count.
    converted = []
    for ch in expanded:
        if ch.isspace():
            converted.append(' ')
        else:
            converted.append(ch)
    converted = ''.join(converted)
    
    # Now we have a string where all whitespace is spaces, with the same number of spaces
    # as original whitespace characters (after tab expansion).
    
    # Tokenize: split into "words" (non-space sequences) and "spaces" (space sequences)
    # We need to keep track of where spaces are to handle line breaks properly.
    
    # Let's tokenize the converted string into tokens:
    # - non-space sequences (words)
    # - space sequences (whitespace)
    
    tokens = []
    i = 0
    n = len(converted)
    while i < n:
        if converted[i] == ' ':
            j = i
            while j < n and converted[j] == ' ':
                j += 1
            tokens.append(('space', i, j - i))  # start index, count
            i = j
        else:
            j = i
            while j < n and converted[j] != ' ':
                j += 1
            tokens.append(('word', i, j - i))  # start index, count
            i = j
    
    # Now build lines. We process tokens sequentially.
    # leading whitespace of whole text is kept.
    # whitespace at line break is dropped: trailing whitespace of current line and 
    # leading whitespace of next line are dropped.
    
    lines = []
    current_line = ""
    current_len = 0
    pending_spaces = 0  # spaces that would be added between tokens but might be dropped at line break
    
    # First, handle leading whitespace: it's kept.
    # We process tokens. When we can fit the next content, we add it.
    # Spaces between words are kept unless they're at a line break.
    
    # Let me think about this differently. We build line by line.
    # For each position, we decide whether to break or not.
    
    # Approach: iterate through tokens, building current line.
    # When adding a word, if it doesn't fit in remaining width, we need to break.
    # But words longer than width ARE broken.
    
    # Let's track: current_line content, its length.
    # When we encounter a space token, we tentatively add spaces.
    # When we encounter a word token, we try to add it. If it fits, add it.
    # If it doesn't fit, we need to break the line.
    
    # The tricky part: spaces at line boundaries are dropped.
    
    # Let's process token by token, maintaining:
    # - current_line: string content of current line
    # - line_len: length of current_line
    
    # For space tokens: we add them to current_line (they're part of the content).
    # For word tokens: we try to add. If line_len + word_len <= width, add word.
    # If not, we need to break. When breaking, trailing spaces on current line are dropped.
    
    # Let me implement step by step:
    
    current_line = ""
    line_len = 0
    # Track if we have pending spaces that haven't been committed yet
    # Actually, let's just build directly.
    
    i = 0
    while i < len(tokens):
        token_type, start, count = tokens[i]
        
        if token_type == 'space':
            # Add spaces to current line
            # But we need to be careful: if current_line is empty and this is leading whitespace,
            # it's kept. Otherwise spaces are just part of content.
            current_line += ' ' * count
            line_len += count
            i += 1
        else:  # word
            word = converted[start:start + count]
            word_len = len(word)
            
            if word_len <= width:
                # Try to fit the word in current line
                if line_len + word_len <= width:
                    # Fits, add it
                    current_line += word
                    line_len += word_len
                    i += 1
                else:
                    # Need to break the line
                    # Drop trailing whitespace from current line
                    stripped_line = current_line.rstrip()
                    if stripped_line:
                        lines.append(stripped_line)
                    # Start new line with this word
                    current_line = word
                    line_len = word_len
                    i += 1
            else:
                # Word longer than width, must be broken
                # First, handle any remaining space in current line
                remaining_space = width - line_len
                
                if remaining_space > 0:
                    # Take part of the word to fill current line
                    part = word[:remaining_space]
                    current_line += part
                    line_len += remaining_space
                    word = word[remaining_space:]
                    word_len = len(word)
                    # Now current line is full, save it
                    stripped_line = current_line.rstrip()
                    if stripped_line:
                        lines.append(stripped_line)
                    # Start new line with remaining word
                    current_line = ""
                    line_len = 0
                
                # Now break the word into chunks of width
                while len(word) > width:
                    part = word[:width]
                    lines.append(part)
                    word = word[width:]
                
                # Remaining part of word (could be empty or <= width)
                if word:
                    current_line = word
                    line_len = len(word)
                
                i += 1
    
    # After processing all tokens, add remaining current line
    if current_line:
        stripped_line = current_line.rstrip()
        if stripped_line:
            lines.append(stripped_line)
    
    return lines
