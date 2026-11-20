def wrap_(text, width):
    # 1. Expand tabs to 8 spaces
    text = text.expandtabs(8)
    
    # 2. Handle whitespace and line breaks
    # The prompt specifies: "each whitespace character becomes one space (runs are NOT collapsed)"
    # and "whitespace at each line break is dropped".
    # We split by actual newline characters to identify the "line breaks".
    lines = text.splitlines(keepends=False)
    if not lines and text: # Handle case where text is only newlines
        lines = [""]
    elif not text:
        return []

    processed_lines = []
    for i, line in enumerate(lines):
        # Drop trailing whitespace from every line
        line = line.rstrip()
        if not line and i < len(lines) - 1:
            # If a line was only whitespace, it's effectively dropped 
            # unless it's the last line (which we handle via rstrip)
            continue
        
        # Drop leading whitespace for all lines except the first one
        if i > 0:
            line = line.lstrip()
            
        # Replace internal whitespace characters (\t, \n, \r, \f, \v) with a space
        # Since we already split by \n and rstrip/lstrip, we just need to 
        # ensure any remaining whitespace chars (like \f or \v) become spaces.
        # However, the prompt says "each whitespace character becomes one space".
        # To preserve runs but convert types, we use a generator.
        new_line = "".join(" " if c.isspace() else c for c in line)
        processed_lines.append(new_line)

    # Join the processed lines into one continuous stream of text 
    # because textwrap.wrap treats the input as a paragraph.
    # However, since we dropped whitespace at line breaks, we join with nothing.
    full_text = "".join(processed_lines)
    
    # If the original text started with whitespace, we must preserve it.
    # The prompt: "leading whitespace of the whole text is kept".
    # Let's find the leading whitespace of the original expanded text.
    expanded_original = text.expandtabs(8)
    leading_ws = ""
    for char in expanded_original:
        if char.isspace():
            leading_ws += char
        else:
            break
    
    # Re-construct the text to be wrapped, ensuring leading whitespace is preserved.
    # Since we stripped it during line processing, we prepend it back.
    # But wait, if we join processed_lines, we might have lost the "start" of the first line.
    # Let's refine: The first line's leading whitespace was kept in processed_lines[0].
    # So full_text already contains it.
    
    # 3. Wrap the text
    # We need to break words longer than width and wrap lines.
    words = []
    current_pos = 0
    
    # Because we must preserve whitespace runs, we can't just .split().
    # We iterate through the string and identify "chunks" (words or spaces).
    i = 0
    while i < len(full_text):
        if full_text[i].isspace():
            # Collect a run of whitespace
            start = i
            while i < len(full_text) and full_text[i].isspace():
                i += 1
            words.append(full_text[start:i])
        else:
            # Collect a word
            start = i
            while i < len(full_text) and not full_text[i].isspace():
                i += 1
            words.append(full_text[start:i])

    result = []
    current_line = ""

    for word in words:
        if not current_line:
            # If the first word of a line is longer than width, break it
            if len(word) > width:
                # Keep the part that fits
                first_part = word[:width]
                result.append(first_part)
                # The remainder becomes the start of the next line
                # We need to process the remainder recursively or via a loop
                # To keep it simple, we'll put the remainder back into the word list
                # but since we are iterating, we can just handle it here.
                # Let's use a more robust approach:
                remaining = word[width:]
                # We need to re-process 'remaining' as if it were the next word
                # To do this cleanly, we'll use a helper or a while loop.
                pass # Handled by logic below
            else:
                current_line = word
        else:
            # Check if adding this word (and its preceding space if it's not a run) 
            # exceeds width. Note: 'word' here could be a whitespace run.
            if len(current_line) + len(word) <= width:
                current_line += word
            else:
                # If current_line is not empty, push it
                if current_line:
                    result.append(current_line)
                
                # If the word itself is longer than width, break it
                if len(word) > width:
                    # If it's a whitespace run, it's already "broken" by logic 
                    # but we should treat it as a single chunk if it's one char? 
                    # No, words are broken. Whitespace runs aren't "words".
                    if not word[0].isspace():
                        # Break the long word
                        i_word = 0
                        while i_word < len(word):
                            chunk = word[i_word : i_word + width]
                            result.append(chunk)
                            i_word += width
                        current_line = ""
                    else:
                        # It's a whitespace run longer than width? 
                        # Standard wrap doesn't break whitespace runs, 
                        # but the prompt says "none longer than width (except where a single unbreakable chunk forces it)".
                        # A whitespace run is technically a sequence of spaces.
                        # However, usually, only non-whitespace are "unbreakable".
                        # Let's treat the whole run as one chunk if it's all spaces.
                        result.append(word)
                        current_line = ""
                else:
                    # Word fits in a new line
                    current_line = word

    if current_line:
        result.append(current_line)

    # Final pass: The logic above might create empty strings or 
    # handle whitespace runs slightly differently than textwrap.
    # Let's refine the "word" loop to be more precise.
    
    # RE-IMPLEMENTING WRAP LOGIC FOR PRECISION:
    final_result = []
    current_line = ""
    
    # Re-parse words/spaces into a list of tokens
    tokens = []
    i = 0
    while i < len(full_text):
        if full_text[i].isspace():
            start = i
            while i < len(full_text) and full_text[i].isspace():
                i += 1
            tokens.append(full_text[start:i])
        else:
            start = i
            while i < len(full_text) and not full_text[i].isspace():
                i += 1
            tokens.append(full_text[start:i])

    for token in tokens:
        if not current_line:
            if len(token) > width and not token[0].isspace():
                # Break long word
                for j in range(0, len(token), width):
                    final_result.append(token[j : j + width])
                # If there's a remainder that is exactly width, it's added.
                # If the last chunk was smaller than width, it's also added.
            else:
                current_line = token
        else:
            if len(current_line) + len(token) <= width:
                current_line += token
            else:
                final_result.append(current_line)
                if len(token) > width and not token[0].isspace():
                    for j in range(0, len(token), width):
                        final_result.append(token[j : j + width])
                    current_line = ""
                else:
                    current_line = token
                    
    if current_line:
        final_result.append(current_line)

    # Filter out empty strings that might have been added
    return [line for line in final_result if line != ""]
