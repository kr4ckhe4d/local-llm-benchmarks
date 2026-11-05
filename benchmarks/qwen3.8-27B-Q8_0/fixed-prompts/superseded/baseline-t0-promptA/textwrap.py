def wrap_(text, width):
    if width <= 0:
        raise ValueError("invalid width %r (must be > 0)" % width)
    
    # Expand tabs: replace each tab with spaces to reach next multiple of 8
    # Python's textwrap uses tabsize=8 by default
    expanded = []
    col = 0
    for ch in text:
        if ch == '\t':
            # Move to next multiple of 8
            spaces = 8 - (col % 8)
            expanded.append(' ' * spaces)
            col += spaces
        else:
            expanded.append(ch)
            col += 1
    text = ''.join(expanded)
    
    # Now split into words. In textwrap, a "word" is a maximal run of non-whitespace characters.
    # Whitespace between words is preserved as-is (each whitespace char becomes one space, runs NOT collapsed).
    # But actually, textwrap.wrap with default options: it splits on whitespace, and the whitespace between words
    # is used as the separator. Let me re-read the requirements.
    
    # "each whitespace character becomes one space (runs are NOT collapsed)"
    # This means: when we have "hello   world", the three spaces between hello and world are preserved as three spaces.
    # But wait, textwrap.wrap actually does collapse whitespace by default? Let me think again.
    
    # Actually, the problem says: "reproducing textwrap.wrap(text, width) with default options" and then clarifies:
    # "tabs are expanded and each whitespace character becomes one space (runs are NOT collapsed)"
    # So we should NOT collapse runs of whitespace. Each whitespace char becomes a single space.
    
    # Let me parse the text into tokens: words (non-whitespace runs) and whitespace runs.
    # Then we need to pack them into lines of at most `width` characters.
    
    # First, let's tokenize: alternate between word and whitespace.
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            # Replace each whitespace char with a space
            tokens.append(('ws', ' ' * (j - i)))
            i = j
        else:
            j = i
            while j < n and not text[j].isspace():
                j += 1
            tokens.append(('word', text[i:j]))
            i = j
    
    # Now we need to build lines. A line consists of tokens. The total length of a line must be <= width.
    # Words longer than width are broken.
    
    # Strategy: iterate through tokens, building up a current line.
    # When adding a token would exceed width, we need to handle it.
    # If the token is a word that's too long, we break it.
    # If the token is whitespace, we might need to drop it or handle it.
    
    # Let me think about this more carefully. textwrap.wrap works by:
    # 1. Splitting into words (with their preceding whitespace? or just words?)
    # Actually, textwrap treats whitespace as separators. The default behavior is to use a single space as separator.
    # But the problem says runs are NOT collapsed. So we need to preserve the exact whitespace.
    
    # Let me reconsider. The problem says "each whitespace character becomes one space (runs are NOT collapsed)".
    # So if the input has "a   b", the output should preserve the three spaces between a and b when they fit on the same line.
    
    # Approach:
    # - We have a list of tokens (word or ws).
    # - We build lines by adding tokens one by one.
    # - If adding a word token would make the line exceed width, we break the word.
    # - If adding a ws token would make the line exceed width, we might need to start a new line (dropping the ws? or keeping it?)
    
    # Actually, in textwrap, leading whitespace on a line is typically stripped unless break_on_hyphens or similar.
    # But with default options, textwrap.wrap strips leading whitespace from each line.
    
    # Hmm, let me just implement it step by step:
    
    lines = []
    current_line = []
    current_len = 0
    
    for token_type, token_val in tokens:
        if token_type == 'word':
            word = token_val
            # If the word is longer than width, we need to break it
            if len(word) > width:
                # First, if current_line is not empty, we should flush it
                if current_line:
                    # Strip leading whitespace from current line
                    line_str = ''.join(current_line)
                    line_str = line_str.lstrip()
                    if line_str:
                        lines.append(line_str)
                    current_line = []
                    current_len = 0
                
                # Break the word into chunks of size width
                while len(word) > width:
                    lines.append(word[:width])
                    word = word[width:]
                # Add the remaining part
                if word:
                    current_line.append(word)
                    current_len += len(word)
            else:
                # Check if adding this word fits
                if current_len + len(word) <= width:
                    current_line.append(word)
                    current_len += len(word)
                else:
                    # Need to start a new line
                    if current_line:
                        line_str = ''.join(current_line)
                        line_str = line_str.lstrip()
                        if line_str:
                            lines.append(line_str)
                        current_line = []
                        current_len = 0
                    current_line.append(word)
                    current_len += len(word)
        else:  # whitespace
            ws = token_val
            # Check if adding this whitespace fits
            if current_len + len(ws) <= width:
                current_line.append(ws)
                current_len += len(ws)
            else:
                # The whitespace doesn't fit. We should start a new line.
                # The whitespace is effectively dropped (or we could keep it, but leading whitespace is stripped)
                if current_line:
                    line_str = ''.join(current_line)
                    line_str = line_str.lstrip()
                    if line_str:
                        lines.append(line_str)
                    current_line = []
                    current_len = 0
                # Don't add the whitespace to the new line (it would be leading whitespace)
    
    # Flush the last line
    if current_line:
        line_str = ''.join(current_line)
        line_str = line_str.lstrip()
        if line_str:
            lines.append(line_str)
    
    return lines
