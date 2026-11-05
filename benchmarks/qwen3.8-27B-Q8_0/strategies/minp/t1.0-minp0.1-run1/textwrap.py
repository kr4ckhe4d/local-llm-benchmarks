def wrap_(text, width):
    # Expand tabs to spaces (tab stop every 8 characters)
    lines = []
    current = []
    current_len = 0

    # First, handle tab expansion: convert tabs to appropriate number of spaces
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

    # Split into tokens: sequences of non-whitespace and whitespace
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            tokens.append(text[i:j])
            i = j
        else:
            j = i
            while j < n and not text[j].isspace():
                j += 1
            tokens.append(text[i:j])
            i = j

    # Now build lines by processing tokens
    # We collapse whitespace: leading/trailing whitespace on lines is removed,
    # multiple whitespace becomes single space, but we need to track that
    # whitespace between words becomes single space.

    # Process: iterate through tokens, building current line
    # A "word" is a non-whitespace token. Whitespace tokens are separators.
    # We collapse all whitespace sequences to a single space.

    # We'll build a list of words (non-whitespace tokens) and then join with single spaces,
    # but we need to handle the breaking properly.

    # Actually, let's think of it as: we have a stream of characters.
    # We want to break lines such that:
    # - No line exceeds `width` characters
    # - Words are broken only if a single word is longer than width
    # - Whitespace is collapsed to single spaces

    # Better approach: tokenize into words (non-whitespace runs) and track them.
    # Then join words with single spaces, breaking lines when adding next word would exceed width.

    words = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace():
                j += 1
            words.append(text[i:j])
            i = j

    # Now join words with single spaces, breaking lines
    lines = []
    current_line = ''
    current_len = 0

    for word in words:
        if not current_line:
            # Start new line with this word
            if len(word) <= width:
                current_line = word
                current_len = len(word)
            else:
                # Word is longer than width, break it
                # First, emit any existing line
                if current_line:
                    lines.append(current_line)
                    current_line = ''
                    current_len = 0
                # Break the word into chunks of width
                for k in range(0, len(word), width):
                    chunk = word[k:k+width]
                    if current_line:
                        lines.append(current_line)
                        current_line = ''
                        current_len = 0
                    if len(chunk) <= width:
                        current_line = chunk
                        current_len = len(chunk)
                        # If this chunk is the last one, we might want to keep it as current_line
                        # But actually, after breaking, the next word will be added with a space
                        # Wait, no. If we broke a word, the next chunk is a continuation.
                        # But actually, each chunk becomes its own line if it's a full width,
                        # except the last chunk which might be partial.
                        # Let me reconsider.
                    else:
                        lines.append(chunk)
                # After breaking, current_line holds the last chunk
                # But if the word was exactly a multiple of width, current_line is empty
                if current_line and len(current_line) >= width:
                    lines.append(current_line)
                    current_line = ''
                    current_len = 0
        else:
            # Current line is non-empty
            # Try to add word with a space
            candidate = current_line + ' ' + word
            if len(candidate) <= width:
                current_line = candidate
                current_len = len(candidate)
            else:
                # Need to break
                # Emit current line
                lines.append(current_line)
                # Now try to fit word on new line
                if len(word) <= width:
                    current_line = word
                    current_len = len(word)
                else:
                    # Break word
                    for k in range(0, len(word), width):
                        chunk = word[k:k+width]
                        if current_line:
                            lines.append(current_line)
                            current_line = ''
                            current_len = 0
                        if len(chunk) <= width:
                            current_line = chunk
                            current_len = len(chunk)
                        else:
                            lines.append(chunk)
                    if current_line and len(current_line) >= width:
                        lines.append(current_line)
                        current_line = ''
                        current_len = 0

    if current_line:
        lines.append(current_line)

    # Filter out empty lines
    lines = [line for line in lines if line]

    return lines
