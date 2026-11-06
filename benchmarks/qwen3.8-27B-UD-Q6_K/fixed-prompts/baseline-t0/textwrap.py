def wrap_(text, width):
    # Expand tabs: replace each tab with spaces to reach next multiple of 8
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
    text = ''.join(expanded)
    
    # Split into words: each whitespace character becomes one space, runs are NOT collapsed
    # But we need to identify "words" as sequences of non-whitespace characters
    # Whitespace between words is dropped at line breaks, but within a line, each whitespace char is one space
    # Actually, re-reading: "each whitespace character becomes one space (runs are NOT collapsed)"
    # This means if there are multiple spaces, they stay as multiple spaces in the output
    # But "whitespace at each line break is dropped (trailing whitespace of a line and leading whitespace of the next)"
    
    # Let me think about this more carefully. The default textwrap.wrap behavior:
    # - Tabs are expanded
    # - Whitespace is normalized: each run of whitespace becomes a single space? No, the problem says "runs are NOT collapsed"
    # Wait, let me re-read: "each whitespace character becomes one space (runs are NOT collapsed)"
    # So if input has "a  b" (two spaces), output has "a  b" (two spaces)
    # But at line breaks, trailing whitespace of a line and leading whitespace of next line are dropped
    
    # So the algorithm:
    # 1. Expand tabs
    # 2. Process the text character by character, building lines
    # 3. Words are sequences of non-whitespace characters
    # 4. Between words, there's whitespace (one or more spaces after tab expansion)
    # 5. When breaking a line, we drop the trailing whitespace of the current line and leading whitespace of the next
    
    # Let me parse the text into tokens: words and whitespace runs
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            tokens.append(('ws', text[i:j]))
            i = j
        else:
            j = i
            while j < n and not text[j].isspace():
                j += 1
            tokens.append(('word', text[i:j]))
            i = j
    
    # Now build lines
    lines = []
    current_line = []  # list of (type, content) for current line
    current_len = 0
    
    def flush_line():
        nonlocal current_line, current_len
        if not current_line:
            return
        # Build the line string
        parts = []
        for t, c in current_line:
            parts.append(c)
        line = ''.join(parts)
        # Strip trailing whitespace
        line = line.rstrip()
        if line:
            lines.append(line)
        current_line = []
        current_len = 0
    
    for t, c in tokens:
        if t == 'ws':
            # Whitespace: add to current line if it fits, otherwise it will be dropped at line break
            # Actually, whitespace is only added if there's already content in the current line
            # and it fits. If the line is empty, leading whitespace is kept (per problem: "leading whitespace of the whole text is kept")
            if current_line:
                # Check if adding this whitespace fits
                if current_len + len(c) <= width:
                    current_line.append((t, c))
                    current_len += len(c)
                else:
                    # Doesn't fit, flush current line (trailing whitespace will be stripped)
                    flush_line()
                    # After flushing, this whitespace is leading whitespace of the new line
                    # But wait, the problem says leading whitespace of the next line is dropped
                    # So we skip this whitespace
            else:
                # Current line is empty, this is leading whitespace
                # "leading whitespace of the whole text is kept" - so if this is the very beginning, keep it
                # But "leading whitespace of the next" line is dropped
                # If current_line is empty and we haven't started any line yet, this is leading whitespace of the whole text
                if not lines:
                    # Leading whitespace of the whole text, keep it
                    current_line.append((t, c))
                    current_len += len(c)
                else:
                    # Leading whitespace of a new line, drop it
                    pass
        else:  # word
            word = c
            if current_line:
                # Check if word fits in current line
                if current_len + len(word) <= width:
                    current_line.append((t, word))
                    current_len += len(word)
                else:
                    # Word doesn't fit, flush current line
                    flush_line()
                    # Now try to add word to new line
                    if len(word) <= width:
                        current_line.append((t, word))
                        current_len += len(word)
                    else:
                        # Word is longer than width, break it
                        # Break the word into chunks of width
                        for k in range(0, len(word), width):
                            chunk = word[k:k+width]
                            if current_line:
                                # Shouldn't happen since we just flushed
                                pass
                            current_line.append((t, chunk))
                            current_len = len(chunk)
                            if k + width < len(word):
                                flush_line()
            else:
                # Current line is empty
                if len(word) <= width:
                    current_line.append((t, word))
                    current_len += len(word)
                else:
                    # Word is longer than width, break it
                    for k in range(0, len(word), width):
                        chunk = word[k:k+width]
                        current_line.append((t, chunk))
                        current_len = len(chunk)
                        if k + width < len(word):
                            flush_line()
    
    # Flush the last line
    flush_line()
    
    return lines
