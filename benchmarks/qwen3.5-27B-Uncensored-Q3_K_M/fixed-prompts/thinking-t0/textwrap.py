def wrap_(text, width):
    # 1. Preprocess: Expand tabs to spaces (default tabsize is 8)
    # The prompt says "tabs are expanded and each whitespace character becomes one space".
    # However, it also says "runs are NOT collapsed".
    # Standard textwrap default behavior: expand_tabs=True, replace_whitespace=True.
    # But the prompt constraint "runs are NOT collapsed" suggests we should NOT collapse multiple spaces.
    # Let's interpret "each whitespace character becomes one space" as: 
    # Tabs become spaces, Newlines become spaces (or breaks), but multiple spaces remain multiple spaces.
    # Actually, standard textwrap with default options collapses whitespace runs. 
    # The prompt says "runs are NOT collapsed". This is a specific deviation from standard textwrap defaults 
    # regarding whitespace normalization, OR it implies that the input text's whitespace structure is preserved 
    # except for tabs and newlines handling.
    # Let's stick to the most literal interpretation of the constraints provided:
    # - Tabs expanded (to spaces).
    # - Whitespace characters (like \n, \t) become spaces.
    # - Runs of spaces are NOT collapsed (so "a  b" stays "a  b").
    # - Trailing/Leading whitespace at line breaks dropped.
    
    # Step 1: Normalize tabs to spaces.
    # Since "runs are NOT collapsed", we treat \t as a sequence of spaces. 
    # Standard textwrap expands \t to 8 spaces. Let's assume 8 spaces for "expanded".
    # But the prompt says "each whitespace character becomes one space". 
    # This might mean \t -> ' ' (1 space). 
    # Given "tabs are expanded", usually implies 8 spaces. 
    # But "each whitespace character becomes one space" suggests normalization.
    # Let's assume \t -> ' ' (1 space) to satisfy "each whitespace character becomes one space".
    # Wait, if \t becomes 1 space, is it "expanded"? 
    # Let's assume the prompt means: Convert all whitespace (including \t, \n) to ' '.
    # But "runs are NOT collapsed" means if input is "a  b", output is "a  b".
    # If input is "a\tb", output is "a b".
    
    # Step 2: Handle line breaks.
    # "whitespace at each line break is dropped (trailing whitespace of a line and leading whitespace of the next)"
    # This implies we split by \n, strip trailing/leading whitespace of chunks, then join with ' '.
    # "leading whitespace of the whole text is kept".
    
    # Step 3: Break words longer than width.
    
    # Let's implement based on this logic:
    
    # 1. Replace tabs with spaces.
    # 2. Split text by newlines to handle line breaks.
    # 3. For each line, strip trailing whitespace.
    # 4. Join lines with a space (representing the newline break).
    # 5. Strip leading whitespace of the whole text? No, "leading whitespace of the whole text is kept".
    #    So we only strip leading whitespace of *subsequent* lines.
    
    # Refined Plan:
    # 1. Replace \t with ' '.
    # 2. Split by \n.
    # 3. Process each chunk: strip trailing whitespace.
    # 4. Join chunks with ' '.
    # 5. Strip leading whitespace of the *joined* result? No, "leading whitespace of the whole text is kept".
    #    So we don't strip the very first chunk's leading whitespace.
    #    But we strip leading whitespace of subsequent chunks.
    
    # 6. Wrap logic:
    #    Iterate through characters. Accumulate current line.
    #    If adding a char exceeds width:
    #       If current char is whitespace: break line here.
    #       Else: break line before this char (break word).
    #    Handle "words longer than width ARE broken".
    
    # Let's write the code.
    
    lines = []
    current_line = []
    
    # Preprocessing:
    # Replace tabs with spaces.
    text = text.replace('\t', ' ')
    
    # Split by newlines to handle line break whitespace dropping rules.
    raw_lines = text.split('\n')
    
    # Process raw lines:
    # Drop trailing whitespace of each line.
    # Drop leading whitespace of lines after the first one.
    # Join with a space (representing the newline).
    
    processed_text_parts = []
    for i, line in enumerate(raw_lines):
        line = line.rstrip()
        if i > 0:
            line = line.lstrip()
        processed_text_parts.append(line)
    
    # Join with space to represent the newline break (whitespace character becomes one space)
    # This effectively treats \n as a space separator.
    full_text = ' '.join(processed_text_parts)
    
    # Now wrap full_text
    # "words longer than width ARE broken"
    # "result is a list of lines none longer than width"
    
    result = []
    current_line = []
    
    # We need to handle the "runs are NOT collapsed" rule.
    # Since we joined with ' ', we might have introduced spaces.
    # But the original spaces are preserved.
    # The "whitespace at each line break is dropped" rule was handled by rstrip/lstrip.
    # The "leading whitespace of the whole text is kept" rule is handled by not lstrip on index 0.
    
    # Now iterate through full_text characters to wrap.
    # We need to detect word boundaries? 
    # "runs are NOT collapsed" implies we treat spaces as characters that can be line breaks.
    # If we hit a space and adding it exceeds width, we break.
    # If we hit a non-space and adding it exceeds width, we break before it (break word).
    
    i = 0
    n = len(full_text)
    
    while i < n:
        # Find the end of the current line
        # We want to fit as much as possible <= width
        
        # Check if current_line is empty
        if not current_line:
            # Start new line
            pass
        
        # Try to extend current_line
        # We need to find the break point.
        
        # Let's look ahead.
        # If current_line + char <= width: add char.
        # Else:
        #   If char is space: break here (space is dropped from end of line).
        #   Else: break before char (word break).
        
        # However, we need to handle the "runs are NOT collapsed" carefully.
        # If we have "a  b", and width is 2.
        # Line: "a " (len 2). Next char ' '.
        # If we add ' ', len 3 > 2. Break.
        # Line becomes "a ". Next line starts with " b".
        
        # Let's implement a simple greedy approach.
        
        line_chars = []
        
        while i < n:
            char = full_text[i]
            
            # Check if adding this char exceeds width
            if len(line_chars) + 1 > width:
                break
            
            line_chars.append(char)
            i += 1
            
            # If char is whitespace, it's a potential break point.
            # But we only break if the *next* char would exceed width.
            # The loop condition handles the length check.
            # If we hit a space and the next char would exceed, we break.
            # But the loop breaks when len > width.
            # So if we have "a b", width 2.
            # i=0, 'a', len 1.
            # i=1, ' ', len 2.
            # i=2, 'b', len 3 > 2. Break.
            # Line is "a ".
            # Next iteration starts at 'b'.
            # This handles "whitespace at each line break is dropped" (trailing space of line).
            # Because the space is included in line_chars, but if we break *after* the space,
            # the space is at the end of the line.
            # The prompt says "trailing whitespace of a line ... is dropped".
            # So if line ends with space, we should strip it.
            
            # Wait, if I break *after* adding the space, the space is in the line.
            # I need to strip trailing whitespace from the line before appending to result.
            
        # If we broke because of length, we need to finalize the line.
        # If we broke because i == n, we finalize.
        
        # Logic adjustment:
        # We accumulate chars. If adding next char exceeds width:
        #   If current char is space: break here (space is trailing, so drop it).
        #   Else: break before current char (word break).
        
        # Let's restart the loop logic for wrapping.
        
        # Actually, simpler approach:
        # Iterate chars.
        # If adding char exceeds width:
        #   If char is space:
        #       Finalize line (strip trailing space).
        #       Start new line.
        #       Skip this space (it's the break).
        #   Else:
        #       Finalize line.
        #       Start new line with this char.
        # Else:
        #   Add char.
        
        # But "runs are NOT collapsed".
        # If I have "a  b", width 2.
        # 'a' -> line "a"
        # ' ' -> line "a "
        # ' ' -> len 3 > 2.
        # Char is space. Break.
        # Line "a ". Strip trailing -> "a".
        # New line starts with ' '.
        # Next 'b' -> " b".
        # Result: ["a", " b"].
        # This preserves the second space at start of next line.
        # This matches "runs are NOT collapsed".
        
        # One edge case: "leading whitespace of the whole text is kept".
        # My preprocessing joined lines with ' '.
        # If original text was "  a", processed is "  a".
        # Wrapping "  a", width 2.
        # ' ' -> " "
        # ' ' -> "  "
        # 'a' -> "  a" (len 3 > 2).
        # Break. Line "  ". Strip trailing -> "  ".
        # Next line "a".
        # Result ["  ", "a"].
        # This keeps leading whitespace.
        
        # Wait, "whitespace at each line break is dropped".
        # This refers to the input text's line breaks (\n).
        # My preprocessing handled that by rstrip/lstrip and joining with ' '.
        # The wrapping logic handles the output line breaks.
        # "trailing whitespace of a line [output line] ... is dropped".
        # So I must strip trailing whitespace from the wrapped line.
        
        # Let's code this.
        
        # Re-evaluating "tabs are expanded and each whitespace character becomes one space".
        # If I replace \t with ' ', then \t is one space.
        # If I have "a\tb", it becomes "a b".
        # If I have "a  b", it stays "a  b".
        # This matches "runs are NOT collapsed".
        
        # One detail: "whitespace at each line break is dropped".
        # This refers to the input \n.
        # My preprocessing: split \n, rstrip, lstrip (except first), join ' '.
        # This effectively drops the \n and surrounding whitespace, replacing with ' '.
        # This matches "each whitespace character becomes one space" (for \n).
        
        # So the plan:
        # 1. Replace \t with ' '.
        # 2. Split \n.
        # 3. Strip trailing of all, leading of all except first.
        # 4. Join with ' '.
        # 5. Wrap with logic:
        #    - Accumulate chars.
        #    - If adding char exceeds width:
        #      - If char is space: break, drop trailing space from line.
        #      - Else: break, start new line with char.
        #    - Else: add char.
        # 6. Strip trailing whitespace from final line.
        
        # Wait, if I break on space, I drop the space from the current line.
        # The space is consumed as the break.
        # The next line starts with the next char.
        # This ensures no trailing space on output lines.
        
        # What if the line is empty?
        # If I have "   ", width 2.
        # ' ' -> " "
        # ' ' -> "  "
        # ' ' -> len 3 > 2.
        # Break. Line "  ". Strip trailing -> "  ".
        # Next line empty.
        # Result ["  "].
        # Correct.
        
        # What if width is 0?
        # "a" -> len 1 > 0. Break.
        # Line empty.
        # Next line "a".
        # Result ["a"].
        # Correct.
        
        # What if word > width?
        # "abc", width 2.
        # 'a' -> "a"
        # 'b' -> "ab"
        # 'c' -> len 3 > 2.
        # Char 'c' is not space.
        # Break. Line "ab".
        # Next line "c".
        # Result ["ab", "c"].
        # Correct ("words longer than width ARE broken").
        
        # One detail: "leading whitespace of the whole text is kept".
        # My preprocessing keeps it.
        # My wrapping logic keeps it (unless it gets stripped as trailing).
        # If text is "  a", width 1.
        # ' ' -> " "
        # ' ' -> "  " (len 2 > 1).
        # Break. Line " ". Strip trailing -> " ".
        # Next line " a".
        # ' ' -> " "
        # 'a' -> " a" (len 2 > 1).
        # Break. Line " ". Strip -> " ".
        # Next line "a".
        # Result [" ", " ", "a"].
        # This preserves the leading spaces as separate lines if width is small.
        # This seems consistent.
        
        # Wait, "whitespace at each line break is dropped".
        # Does this apply to the *output* lines?
        # "trailing whitespace of a line ... is dropped".
        # Yes, I strip trailing whitespace from the wrapped line.
        
        # Let's write the function.
        
        # Preprocessing
        text = text.replace('\t', ' ')
        raw_lines = text.split('\n')
        processed_parts = []
        for i, line in enumerate(raw_lines):
            line = line.rstrip()
            if i > 0:
                line = line.lstrip()
            processed_parts.append(line)
        full_text = ' '.join(processed_parts)
        
        # Wrapping
        result = []
        current_line = []
        
        i = 0
        n = len(full_text)
        
        while i < n:
            char = full_text[i]
            
            # Check if adding char exceeds width
            if len(current_line) + 1 > width:
                # Need to break
                if char == ' ':
                    # Break here, drop trailing space
                    # Finalize current_line
                    line_str = ''.join(current_line).rstrip()
                    if line_str:
                        result.append(line_str)
                    current_line = []
                    i += 1 # Skip the space
                else:
                    # Break before char
                    line_str = ''.join(current_line).rstrip()
                    if line_str:
                        result.append(line_str)
                    current_line = [char]
                    i += 1
            else:
                current_line.append(char)
                i += 1
        
        # Finalize last line
        line_str = ''.join(current_line).rstrip()
        if line_str:
            result.append(line_str)
            
        return result

    # Wait, I need to output ONLY the function in one code block.
    # I should remove comments and clean up.
    # Also, need to ensure "tabs are expanded" logic is correct.
    # "tabs are expanded" usually means \t -> 8 spaces.
    # But "each whitespace character becomes one space" suggests \t -> 1 space.
    # Given "runs are NOT collapsed", if \t -> 8 spaces, then "a\tb" -> "a        b".
    # If \t -> 1 space, "a\tb" -> "a b".
    # The prompt says "tabs are expanded AND each whitespace character becomes one space".
    # This is contradictory if "expanded" means 8 spaces.
    # However, "each whitespace character becomes one space" is a strong constraint.
    # It likely overrides the standard tab expansion size.
    # So \t -> ' '.
    
    # One more check: "whitespace at each line break is dropped".
    # My preprocessing handles input \n.
    # My wrapping handles output line trailing whitespace.
    # This seems consistent.
    
    # Wait, "leading whitespace of the whole text is kept".
    # My preprocessing: `if i > 0: line = line.lstrip()`.
    # So index 0 is NOT lstriped.
    # This preserves leading whitespace of the whole text.
    
    # One edge case: Empty text.
    # full_text = "".
    # Loop doesn't run.
    # Finalize: line_str = "".
    # result = [].
    # Correct.
    
    # One edge case: Text with only whitespace.
    # "   ".
    # full_text = "   ".
    # i=0, ' '. current_line=[' '].
    # i=1, ' '. len 2.
    # i=2, ' '. len 3 > width (assume 2).
    # Break. char is space.
    # Finalize " ". rstrip -> "".
    # current_line = [].
    # i=3.
    # Loop ends.
    # Finalize "".
    # result = [].
    # Is this correct?
    # If text is "   ", width 2.
    # Output should be empty list?
    # Or should it contain lines of spaces?
    # "trailing whitespace of a line ... is dropped".
    # If a line is all spaces, rstrip makes it empty.
    # So empty lines are not added.
    # This seems correct for "whitespace ... is dropped".
    
    # Wait, "leading whitespace of the whole text is kept".
    # If text is "  a", width 1.
    # Preprocessed: "  a".
    # Wrap:
    # ' ' -> " "
    # ' ' -> "  " (len 2 > 1). Break.
    # Line " ". rstrip -> " ". Add " ".
    # Next line " a".
    # ' ' -> " ".
    # 'a' -> " a" (len 2 > 1). Break.
    # Line " ". rstrip -> " ". Add " ".
    # Next line "a".
    # Add "a".
    # Result [" ", " ", "a"].
    # This keeps the leading spaces.
    
    # Looks good.
    
    # Wait, I need to make sure I don't import textwrap.
    # The function signature is wrap_(text, width).
    
    # One detail: "words longer than width ARE broken".
    # My logic: if char is not space and exceeds width, break before char.
    # This breaks the word.
    # Example: "abc", width 2.
    # "ab", "c".
    # Correct.
    
    # Final check on "tabs are expanded".
    # If I use replace('\t', ' '), is that "expanded"?
    # In the context of "each whitespace character becomes one space", yes.
    # It expands the tab character into a space character.
    
    # Code structure:
    # def wrap_(text, width):
    #     ...
    #     return result
    
    # I will write the code now.


def wrap_(text, width):
    # Preprocess: Expand tabs to spaces (1 space per tab as per "each whitespace character becomes one space")
    text = text.replace('\t', ' ')
    
    # Handle line breaks: split by \n, strip trailing of all, strip leading of subsequent
    raw_lines = text.split('\n')
    processed_parts = []
    for i, line in enumerate(raw_lines):
        line = line.rstrip()
        if i > 0:
            line = line.lstrip()
        processed_parts.append(line)
    
    # Join with space to represent newline breaks (whitespace character becomes one space)
    full_text = ' '.join(processed_parts)
    
    result = []
    current_line = []
    i = 0
    n = len(full_text)
    
    while i < n:
        char = full_text[i]
        
        # Check if adding char exceeds width
        if len(current_line) + 1 > width:
            if char == ' ':
                # Break here, drop trailing space
                line_str = ''.join(current_line).rstrip()
                if line_str:
                    result.append(line_str)
                current_line = []
                i += 1
            else:
                # Break before char (word break)
                line_str = ''.join(current_line).rstrip()
                if line_str:
                    result.append(line_str)
                current_line = [char]
                i += 1
        else:
            current_line.append(char)
            i += 1
    
    # Finalize last line
    line_str = ''.join(current_line).rstrip()
    if line_str:
        result.append(line_str)
        
    return result
