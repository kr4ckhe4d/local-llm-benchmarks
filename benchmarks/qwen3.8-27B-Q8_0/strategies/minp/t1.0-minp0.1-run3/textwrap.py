def wrap_(text, width):
    # Expand tabs to spaces (default tab size 8)
    expanded = text.expandtabs(8)
    # Collapse whitespace: replace runs of whitespace with single space
    words = []
    current_word = []
    in_whitespace = False
    for ch in expanded:
        if ch.isspace():
            if not in_whitespace and current_word:
                words.append(''.join(current_word))
                current_word = []
            in_whitespace = True
        else:
            if in_whitespace and current_word:
                # This shouldn't happen because we flush on whitespace transition
                pass
            in_whitespace = False
            current_word.append(ch)
    if current_word:
        words.append(''.join(current_word))

    # Now wrap the words
    lines = []
    current_line = []
    current_len = 0

    for word in words:
        if not word:
            continue
        # If the word itself is longer than width, we need to break it
        if len(word) > width:
            # First, if we have a current line, flush it
            if current_line:
                lines.append(' '.join(current_line))
                current_line = []
                current_len = 0
            # Break the word into chunks of length width
            i = 0
            while i < len(word):
                chunk = word[i:i + width]
                lines.append(chunk)
                i += width
        else:
            if current_line:
                # Check if adding this word would exceed width
                if current_len + 1 + len(word) <= width:
                    current_line.append(word)
                    current_len += 1 + len(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_len = len(word)
            else:
                current_line = [word]
                current_len = len(word)

    if current_line:
        lines.append(' '.join(current_line))

    return lines
