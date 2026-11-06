def wrap_(text, width):
    if width <= 0:
        raise ValueError("width must be > 0, got %r" % (width,))

    # Expand tabs, then replace every whitespace character with one space.
    # Runs are not collapsed.
    out = []
    col = 0
    for ch in text:
        if ch == "\t":
            out.append(" " * (8 - col % 8))
            col += 8 - col % 8
        elif ch.isspace():
            out.append(" ")
            col += 1
        else:
            out.append(ch)
            col += 1
    text = "".join(out)

    # Split into words and spaces.  A word is a maximal non-space run.
    # Spaces are kept as separate chunks so that line-break whitespace can
    # be dropped while preserving leading whitespace of the whole text.
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == " ":
            chunks.append(" ")
            i += 1
        else:
            j = i
            while j < n and text[j] != " ":
                j += 1
            chunks.append(text[i:j])
            i = j

    # Drop whitespace at line breaks:
    # - trailing spaces before a line break
    # - leading spaces after a line break
    # Leading whitespace of the whole text is kept.
    #
    # We do this by grouping into "words" with their following spaces,
    # except that a leading space before the first word is preserved.
    lines = []
    cur = []
    cur_len = 0

    idx = 0
    first_word_seen = False

    while idx < len(chunks):
        chunk = chunks[idx]

        if chunk == " ":
            # A space chunk.  It may be leading whitespace of the whole text,
            # or it may be whitespace before a word.  In the latter case it is
            # kept only if it fits on the current line and is not at a line
            # break.
            if not first_word_seen:
                # Leading whitespace of the whole text: keep it.
                if cur_len + 1 <= width:
                    cur.append(chunk)
                    cur_len += 1
                else:
                    # If it does not fit, start a new line with it.
                    if cur:
                        lines.append("".join(cur))
                    cur = [chunk]
                    cur_len = 1
                idx += 1
                continue

            # Space after a word.  Keep it only if it fits and there is a
            # following word that can start on the same line.
            if idx + 1 < len(chunks) and chunks[idx + 1] != " ":
                if cur_len + 1 <= width:
                    cur.append(chunk)
                    cur_len += 1
                    idx += 1
                    continue
            # Otherwise drop this space (line break or no following word).
            idx += 1
            continue

        # Non-space chunk: a word.
        first_word_seen = True

        # If the word is longer than the remaining width, break it.
        # If it is longer than the full width, break it into width-sized pieces.
        if len(chunk) > width:
            # Finish current line if it has anything.
            if cur:
                lines.append("".join(cur))
                cur = []
                cur_len = 0

            # Break the long word into pieces of length <= width.
            pos = 0
            while pos < len(chunk):
                piece = chunk[pos:pos + width]
                lines.append(piece)
                pos += width
            idx += 1
            continue

        # Normal word.
        if cur_len == 0:
            # Start a new line with this word.
            cur.append(chunk)
            cur_len = len(chunk)
            idx += 1
            continue

        # Try to fit the word on the current line.
        # We need to account for the space before it if it was kept.
        # In this implementation, the space before a word is only kept if it
        # fits, so cur_len already includes it when present.
        if cur_len + len(chunk) <= width:
            cur.append(chunk)
            cur_len += len(chunk)
            idx += 1
        else:
            # Word does not fit; end the current line.
            lines.append("".join(cur))
            cur = [chunk]
            cur_len = len(chunk)
            idx += 1

    if cur:
        lines.append("".join(cur))

    return lines
