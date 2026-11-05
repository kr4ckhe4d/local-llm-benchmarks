def wrap_(text, width):
    if width <= 0:
        raise ValueError("invalid width %r (must be > 0)" % width)
    
    # Expand tabs: replace each tab with spaces to reach next multiple of 8
    # But the problem says "tabs are expanded" - standard textwrap expands tabs to 8 spaces
    # Actually, let me re-read: "tabs are expanded and each whitespace character becomes one space (runs are NOT collapsed)"
    # This is a bit ambiguous. Let me think about what textwrap.wrap does by default.
    # 
    # textwrap.wrap with default options:
    # - expand_tabs=True: tabs are expanded to spaces (tab size 8)
    # - replace_whitespace=True: all whitespace characters are replaced with a single space
    # - But the problem says "runs are NOT collapsed" - wait, that contradicts replace_whitespace=True
    #
    # Let me re-read the problem statement carefully:
    # "tabs are expanded and each whitespace character becomes one space (runs are NOT collapsed)"
    #
    # Hmm, this is saying:
    # 1. Tabs are expanded (to spaces)
    # 2. Each whitespace character becomes one space
    # 3. Runs are NOT collapsed
    #
    # So if we have "a  b" (two spaces), it stays as "a  b" (two spaces), not "a b"
    # But tabs are expanded first.
    #
    # Wait, but textwrap.wrap by default has replace_whitespace=True which DOES collapse runs.
    # The problem says "reproducing textwrap.wrap(text, width) with default options" but then
    # specifies "runs are NOT collapsed". This is contradictory.
    #
    # Let me re-read: "Default options mean: tabs are expanded and each whitespace character becomes one space (runs are NOT collapsed)"
    #
    # I think the problem is defining what "default options" means for this specific implementation, which may differ from actual textwrap.
    # The key behaviors specified are:
    # 1. Tabs are expanded
    # 2. Each whitespace character becomes one space (so \t, \n, \r, \f, \v all become ' ')
    # 3. Runs are NOT collapsed (so multiple spaces stay as multiple spaces)
    # 4. Whitespace at start and end of each OUTPUT line is dropped
    # 5. Words longer than width ARE broken
    # 6. Result is a list of lines, none longer than width (except where a single unbreakable chunk forces it)
    #
    # So the algorithm:
    # 1. Expand tabs to spaces (tab size 8)
    # 2. Replace all other whitespace characters with spaces
    # 3. Split into "words" where words are sequences of non-space characters
    # 4. Greedily pack words into lines of at most `width` characters
    # 5. If a word is longer than width, break it
    # 6. Strip leading/trailing whitespace from each output line
    #
    # Let me implement this step by step.
    
    # Step 1: Expand tabs and normalize whitespace
    # First, expand tabs to spaces (tab size 8)
    expanded = []
    col = 0
    for ch in text:
        if ch == '\t':
            # Expand to next multiple of 8
            spaces = 8 - (col % 8)
            expanded.append(' ' * spaces)
            col += spaces
        else:
            expanded.append(ch)
            col += 1
    
    # Step 2: Replace all whitespace characters with spaces
    # Whitespace characters: space, tab (already handled), newline, carriage return, form feed, vertical tab
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
    # Since we only have spaces as whitespace in our normalized text, strip spaces
    result = []
    for line in lines:
        stripped = line.strip(' ')
        if stripped:
            result.append(stripped)
        # If stripped is empty, we skip it? Or include empty string?
        # The problem says "whitespace at the start and end of each OUTPUT line is dropped"
        # If a line becomes empty after stripping, should we include it?
        # textwrap.wrap doesn't produce empty lines in normal cases.
        # Let's include it only if it's non-empty after strip, or... 
        # Actually, let me think. If the input is all whitespace, what should happen?
        # Probably an empty list or a list with one empty string?
        # Let's just append the stripped line even if empty, but actually textwrap.wrap('   ', 10) returns []
        # So we should skip empty lines.
    
    return result
