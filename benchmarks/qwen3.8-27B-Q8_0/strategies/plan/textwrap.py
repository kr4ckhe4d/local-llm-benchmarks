def wrap_(text, width):
    if width <= 0:
        raise ValueError("width must be > 0")

    # Expand tabs (tab size 8)
    expanded = []
    col = 0
    for ch in text:
        if ch == '\t':
            # Move to next multiple of 8
            next_tab = ((col // 8) + 1) * 8
            expanded.append(' ' * (next_tab - col))
            col = next_tab
        else:
            expanded.append(ch)
            col += 1
    text = ''.join(expanded)

    # Collapse whitespace: replace runs of whitespace with single space
    # Then strip
    import re
    text = re.sub(r'\s+', ' ', text).strip()

    if not text:
        return []

    # Split into words
    words = text.split(' ')

    lines = []
    current_line = ''
    current_len = 0

    def try_break_word(word, remaining_space):
        """
        Try to break a word that doesn't fit in remaining_space.
        Returns (prefix, suffix) where prefix goes on current line,
        suffix is the remainder to process as next word.
        If remaining_space is 0, returns ('', word) meaning close line and start new.
        """
        if remaining_space <= 0:
            return ('', word)

        # Try hyphen break: find rightmost hyphen where prefix (including hyphen) fits
        # prefix length = index + 1 (since hyphen is at index)
        best_hyphen_idx = -1
        for i in range(len(word)):
            if word[i] == '-':
                prefix_len = i + 1
                if prefix_len <= remaining_space:
                    best_hyphen_idx = i
                else:
                    break  # no further hyphens will fit since prefix only grows

        if best_hyphen_idx != -1:
            prefix = word[:best_hyphen_idx + 1]
            suffix = word[best_hyphen_idx + 1:]
            return (prefix, suffix)

        # No suitable hyphen break: take as many chars as fit
        prefix = word[:remaining_space]
        suffix = word[remaining_space:]
        return (prefix, suffix)

    i = 0
    while i < len(words):
        word = words[i]

        if current_len == 0:
            # Current line is empty
            if len(word) <= width:
                current_line = word
                current_len = len(word)
                i += 1
            else:
                # Word is longer than width, need to break it
                prefix, suffix = try_break_word(word, width)
                if prefix:
                    current_line = prefix
                    current_len = len(prefix)
                # suffix becomes the next word to process
                if suffix:
                    words[i] = suffix
                    # Don't increment i, reprocess
                else:
                    i += 1
        else:
            # Current line is non-empty
            if current_len + 1 + len(word) <= width:
                current_line += ' ' + word
                current_len += 1 + len(word)
                i += 1
            else:
                # Word doesn't fit, close current line
                lines.append(current_line)
                current_line = ''
                current_len = 0
                # Don't increment i, reprocess word on new line

    if current_line:
        lines.append(current_line)

    return lines
