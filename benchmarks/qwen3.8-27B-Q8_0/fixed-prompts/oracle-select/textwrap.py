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
    # Whitespace characters: space, tab (already expanded), newline, etc.
    # After tab expansion, whitespace chars are: ' ', '\n', '\r', '\f', '\v'
    
    # We need to parse the text into tokens: words (non-whitespace sequences) and whitespace runs
    # But the spec says: "each whitespace character becomes one space (runs are NOT collapsed)"
    # This means when we reconstruct, each whitespace char is a single space.
    # However, "whitespace at each line break is dropped (trailing whitespace of a line and leading whitespace of the next; leading whitespace of the whole text is kept)"
    
    # Let me re-read: "tabs are expanded and each whitespace character becomes one space (runs are NOT collapsed)"
    # So after tab expansion, every whitespace character (space, newline, etc.) is treated as a single space character.
    # Runs of whitespace are NOT collapsed, so "a  b" has two spaces between a and b.
    
    # "whitespace at each line break is dropped (trailing whitespace of a line and leading whitespace of the next; leading whitespace of the whole text is kept)"
    # This means: when we break a line, we drop trailing whitespace from the current line and leading whitespace from the next line.
    # But leading whitespace of the whole text is kept.
    
    # "words longer than width ARE broken"
    # "the result is a list of lines none longer than width (except where a single unbreakable chunk forces it)"
    
    # Let me think about this more carefully. The textwrap module's default behavior:
    # 1. Expand tabs
    # 2. Split into words (sequences of non-whitespace)
    # 3. Join words with single spaces (collapsing whitespace runs)
    # 4. Wrap lines
    
    # But the spec says "runs are NOT collapsed". So this is different from default textwrap.
    # Let me re-read: "reproducing textwrap.wrap(text, width) with default options"
    # But then it says "each whitespace character becomes one space (runs are NOT collapsed)"
    # This contradicts default textwrap which collapses whitespace.
    
    # Wait, let me re-read the problem statement more carefully:
    # "reproducing textwrap.wrap(text, width) with default options FROM SCRATCH"
    # "Default options mean: tabs are expanded and each whitespace character becomes one space (runs are NOT collapsed)"
    
    # Hmm, this is saying that the "default options" for this function include NOT collapsing runs.
    # So this is a custom specification, not exactly matching textwrap's actual defaults.
    
    # Let me implement according to the spec:
    # 1. Expand tabs
    # 2. Each whitespace character becomes one space (no collapsing)
    # 3. When breaking lines, drop trailing whitespace of current line and leading whitespace of next line
    # 4. Leading whitespace of whole text is kept
    # 5. Words longer than width are broken
    # 6. Result is list of lines, none longer than width (except unbreakable chunks)
    
    # After tab expansion, let's identify whitespace characters.
    # Whitespace: ' ', '\n', '\r', '\f', '\v'
    
    # Parse into tokens: each token is either a word (non-whitespace) or a single whitespace char
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] in ' \n\r\f\v':
            tokens.append(text[i])  # single whitespace char
            i += 1
        else:
            j = i
            while j < n and text[j] not in ' \n\r\f\v':
                j += 1
            tokens.append(text[i:j])  # word
            i = j
    
    # Now we need to wrap. The idea:
    # - We have a sequence of tokens (words and whitespace chars)
    # - We build lines by adding tokens
    # - When we hit a whitespace token, that's a potential break point
    # - At a break point, we drop trailing whitespace from current line and leading whitespace from next line
    # - But leading whitespace of the whole text is kept
    
    # Let me think about this differently. Let's process the tokens and build lines.
    # A "break" happens at a whitespace character. When we break:
    #   - The current line ends before the whitespace (trailing whitespace dropped)
    #   - The next line starts after the whitespace (leading whitespace dropped)
    #   - But if it's the very beginning of the text, leading whitespace is kept
    
    # Actually, let me reconsider. The whitespace characters are part of the text.
    # When we don't break at a whitespace, it stays in the line.
    # When we break at a whitespace, it's dropped (both the trailing part of current line and leading part of next).
    
    # Let me simulate:
    # tokens = [word1, ws1, word2, ws2, word3, ...]
    # We start with an empty line.
    # For each token:
    #   - If it's a word: add it to current line. If current line length > width, we need to break.
    #   - If it's whitespace: it's a potential break point.
    
    # This is getting complex. Let me think of it as: we have a sequence of "items" where items are either words or whitespace.
    # We want to partition this sequence into lines such that:
    #   - Each line's length <= width (except unbreakable)
    #   - Breaks only happen at whitespace positions
    #   - When breaking at a whitespace, that whitespace is dropped
    #   - Leading whitespace of the whole text is kept
    
    # Let me try a greedy approach:
    # - Start with current_line = ""
    # - Iterate through tokens
    # - For each token, check if adding it would exceed width
    # - If it's a word and adding it exceeds width, we need to break before it (at the last whitespace)
    # - If it's whitespace, we can break here
    
    # Actually, let me think about it as: we have a list of "segments" where each segment is either a word or a whitespace char.
    # We want to group them into lines. A line is a sequence of segments.
    # The length of a line is the sum of lengths of its segments, EXCEPT that if we break at a whitespace, that whitespace is not included.
    
    # Let me try a different approach: convert the text into a list of "units" where each unit is either a word or a single space.
    # Then, we greedily add units to the current line. When we encounter a space, we can choose to break there.
    # If we break at a space, the space is dropped.
    
    # Let me code this up:
    
    # First, let's handle the case where width <= 0
    if width <= 0:
        # Each character is its own line? Or handle specially.
        # Let's just return the text as a single line if it fits, else break character by character.
        # Actually, for width <= 0, every character is its own line.
        return list(text)
    
    # Build list of units: each unit is (type, value) where type is 'word' or 'ws'
    units = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] in ' \n\r\f\v':
            units.append(('ws', text[i]))
            i += 1
        else:
            j = i
            while j < n and text[j] not in ' \n\r\f\v':
                j += 1
            units.append(('word', text[i:j]))
            i = j
    
    # Now wrap
    lines = []
    current_line = []  # list of units in current line
    current_len = 0
    first_line = True
    
    for idx, (utype, uval) in enumerate(units):
        ulen = len(uval)
        
        if utype == 'word':
            # Check if adding this word fits
            if current_len + ulen <= width:
                current_line.append((utype, uval))
                current_len += ulen
            else:
                # Need to break before this word
                # Find the last whitespace in current_line to break at
                # If there's no whitespace in current_line, we have to break the word itself
                break_idx = -1
                for k in range(len(current_line) - 1, -1, -1):
                    if current_line[k][0] == 'ws':
                        break_idx = k
                        break
                
                if break_idx >= 0:
                    # Break at break_idx: current line is current_line[:break_idx]
                    # The whitespace at break_idx is dropped
                    # Next line starts with current_line[break_idx+1:] plus the current word
                    line_units = current_line[:break_idx]
                    line_str = ''.join(u[1] for u in line_units)
                    lines.append(line_str)
                    
                    # New current line starts with units from break_idx+1 to end, plus current word
                    current_line = current_line[break_idx+1:]
                    current_len = sum(len(u[1]) for u in current_line)
                    
                    # Now add the current word
                    if current_len + ulen <= width:
                        current_line.append((utype, uval))
                        current_len += ulen
                    else:
                        # Still doesn't fit, need to break the word
                        # This means the word itself is longer than width
                        # Break the word character by character
                        # First, flush current_line
                        if current_line:
                            line_str = ''.join(u[1] for u in current_line)
                            lines.append(line_str)
                            current_line = []
                            current_len = 0
                        
                        # Break the word
                        remaining = uval
                        while len(remaining) > width:
                            lines.append(remaining[:width])
                            remaining = remaining[width:]
                        current_line.append(('word', remaining))
                        current_len = len(remaining)
                else:
                    # No whitespace in current_line, so we have to break the word
                    # Flush current_line
                    if current_line:
                        line_str = ''.join(u[1] for u in current_line)
                        lines.append(line_str)
                        current_line = []
                        current_len = 0
                    
                    # Break the word
                    remaining = uval
                    while len(remaining) > width:
                        lines.append(remaining[:width])
                        remaining = remaining[width:]
                    current_line.append(('word', remaining))
                    current_len = len(remaining)
        else:  # utype == 'ws'
            # Whitespace: can be added to current line, or used as a break point
            # For now, add it to current line. We'll decide to break later if needed.
            current_line.append((utype, uval))
            current_len += ulen
    
    # Flush remaining
    if current_line:
        line_str = ''.join(u[1] for u in current_line)
        lines.append(line_str)
    
    # Now we need to handle the "drop trailing/leading whitespace at breaks" logic
    # The above approach doesn't properly handle dropping whitespace at breaks.
    # Let me reconsider.
    
    # Actually, I think the issue is that when we break at a whitespace, we should drop that whitespace.
    # In my current approach, when I break at break_idx, I take current_line[:break_idx] which excludes the whitespace.
    # And the next line starts with current_line[break_idx+1:] which also excludes the whitespace.
    # So the whitespace is dropped. That seems correct.
    
    # But wait, what about leading whitespace of the whole text? The spec says it's kept.
    # In my approach, if the text starts with whitespace, it's in the first line and kept. Good.
    
    # Let me test with a simple example:
    # text = "hello world", width = 5
    # units = [('word', 'hello'), ('ws', ' '), ('word', 'world')]
    # Process:
    #   'hello': current_line = [('word','hello')], current_len = 5
    #   ' ': current_line = [('word','hello'), ('ws',' ')], current_len = 6
    #   'world': current_len + 5 = 11 > 5, so break.
    #     Find last ws in current_line: index 1
    #     line = current_line[:1] = [('word','hello')] -> "hello"
    #     current_line = current_line[2:] = []
    #     Add 'world': current_line = [('word','world')], current_len = 5
    #   Flush: "world"
    #   Result: ["hello", "world"]
    #   textwrap.wrap("hello world", 5) = ['hello', 'world'] ✓
    
    # Another test: text = "hello  world" (two spaces), width = 5
    # units = [('word','hello'), ('ws',' '), ('ws',' '), ('word','world')]
    # Process:
    #   'hello': current_line = [('word','hello')], current_len = 5
    #   ' ': current_line = [('word','hello'), ('ws',' ')], current_len = 6
    #   ' ': current_line = [('word','hello'), ('ws',' '), ('ws',' ')], current_len = 7
    #   'world': current_len + 5 = 12 > 5, break.
    #     Find last ws: index 2
    #     line = current_line[:2] = [('word','hello'), ('ws',' ')] -> "hello "
    #     But we should drop trailing whitespace! So it should be "hello"
    #     
    # Ah, I see the issue. When we break, we need to drop trailing whitespace from the line.
    # In my current approach, I'm keeping the whitespace before the break point.
    
    # Let me fix: when breaking at break_idx, the line should be current_line[:break_idx] with trailing whitespace removed.
    # But actually, the spec says "trailing whitespace of a line" is dropped. So if the line ends with whitespace, remove it.
    
    # Let me revise: when forming a line from units, strip trailing whitespace.
    # And when starting a new line, strip leading whitespace (except for the first line).
    
    # Let me redo this more carefully.
    
    # I'll restart the implementation with a cleaner approach.
    
    # Let me scrap the above and start fresh.
    
    # Step 1: Expand tabs
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
    
    if width <= 0:
        return list(text)
    
    # Step 2: Parse into words and whitespace
    # We'll work with the string directly, identifying word boundaries
    
    # Let me use a different strategy:
    # - Split the text into "chunks" where each chunk is either a word or a single whitespace char
    # - Greedily build lines
    
    # Actually, let me think about this more simply.
    # The key insight: we can only break at whitespace characters.
    # When we break at a whitespace character, that character is dropped.
    # Leading whitespace of the whole text is kept.
    
    # Let me iterate through the text, tracking position, and decide where to break.
    
    lines = []
    start = 0  # start of current line
    i = 0
    n = len(text)
    
    while i < n:
        # Try to extend the current line as far as possible
        # Find the furthest position where we can break
        # A break can happen at a whitespace character
        
        # First, check if the remaining text fits in one line
        if n - start <= width:
            lines.append(text[start:])
            break
        
        # Find the last whitespace character in text[start:start+width]
        # But we need to be careful: the break happens AT the whitespace, and the whitespace is dropped.
        # So if we break at position j (where text[j] is whitespace), the current line is text[start:j]
        # and the next line starts at j+1.
        
        # Find the last whitespace in text[start:start+width]
        break_pos = -1
        for j in range(start + width, start, -1):
            if j < n and text[j] in ' \n\r\f\v':
                break_pos = j
                break
        
        if break_pos > start:
            # Break at break_pos
            line = text[start:break_pos]
            # Strip trailing whitespace from line
            line = line.rstrip(' \n\r\f\v')
            lines.append(line)
            start = break_pos + 1
            # Skip leading whitespace of next line (but keep if it's the very beginning)
            # Since start > 0, we skip leading whitespace
            while start < n and text[start] in ' \n\r\f\v':
                start += 1
        else:
            # No whitespace in the first width characters, so we have to break a word
            # Take width characters
            line = text[start:start+width]
            lines.append(line)
            start += width
    
    # Handle empty lines
    # If text is empty, return []
    if not text:
        return []
    
    # Filter out empty lines? No, the spec doesn't say to filter.
    # But if we have consecutive breaks, we might get empty lines.
    # Let's keep them as is.
    
    return lines
