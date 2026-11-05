def glob_match(pattern, name):
    """
    Match pattern against name using fnmatch.fnmatchcase semantics.
    Supports:
      * - any run of characters (including empty)
      ? - exactly one character
      [abc] - character class
      [a-z] - range
      [!abc] - negated character class
      ] immediately after [ or [! is a literal
      unterminated [ is a literal [
    Matching is anchored (whole string).
    """
    # We'll use a recursive approach with memoization or iterative with backtracking.
    # Since * can match any number of characters, we need backtracking.
    
    # Let's use a recursive function with two pointers: pattern index and name index.
    # To handle * efficiently, we can use a standard backtracking approach.
    
    def match_here(p_idx, n_idx):
        """
        Try to match pattern[p_idx:] against name[n_idx:].
        Returns True if match succeeds.
        """
        # If we've consumed the pattern, check if name is also consumed
        if p_idx == len(pattern):
            return n_idx == len(name)
        
        p_char = pattern[p_idx]
        
        if p_char == '*':
            # * matches any sequence (including empty)
            # Try matching 0, 1, 2, ... characters
            # Optimization: skip consecutive *
            while p_idx < len(pattern) and pattern[p_idx] == '*':
                p_idx += 1
            
            # Now try to match the rest of the pattern starting from various positions in name
            # Try n_idx, n_idx+1, ..., len(name)
            for i in range(n_idx, len(name) + 1):
                if match_here(p_idx, i):
                    return True
            return False
        
        elif p_char == '?':
            # ? matches exactly one character
            if n_idx < len(name):
                return match_here(p_idx + 1, n_idx + 1)
            return False
        
        elif p_char == '[':
            # Parse character class
            # Check for ] immediately after [ or [!
            p_idx_start = p_idx
            p_idx += 1  # skip '['
            
            negate = False
            if p_idx < len(pattern) and pattern[p_idx] == '!':
                negate = True
                p_idx += 1
            
            # If ] is immediately after [ or [!, it's a literal ]
            if p_idx < len(pattern) and pattern[p_idx] == ']':
                # This ] is a literal, so we need to find the closing ]
                # The class includes this literal ]
                # Continue parsing to find the real closing ]
                pass  # We'll handle it in the class parsing below
            
            # Parse the character class
            # Find the closing ]
            # The first ] that is not immediately after [ or [! closes the class
            # But we need to be careful: if ] is the first char after [ or [!, it's literal
            # So we need to find the next ] that is not in that position
            
            # Let's collect the characters in the class
            # Start from current p_idx
            start = p_idx
            end = -1
            
            # If the first char is ], it's a literal, so we need to look for the next ]
            # Actually, the rule is: ] immediately after [ or [! is a literal
            # So if pattern[start] == ']', it's a literal, and we need to find the closing ] after it
            # Otherwise, the first ] we encounter closes the class
            
            if p_idx < len(pattern):
                if pattern[p_idx] == ']':
                    # This ] is a literal, so we need to find the next ]
                    # Look for the next ] starting from p_idx + 1
                    j = p_idx + 1
                    while j < len(pattern) and pattern[j] != ']':
                        j += 1
                    if j < len(pattern):
                        end = j
                    else:
                        # Unterminated [, treat as literal [
                        # Fall through to treat [ as literal
                        if n_idx < len(name) and name[n_idx] == '[':
                            return match_here(p_idx_start + 1, n_idx + 1)
                        return False
                else:
                    # Find the first ]
                    j = p_idx
                    while j < len(pattern) and pattern[j] != ']':
                        j += 1
                    if j < len(pattern):
                        end = j
                    else:
                        # Unterminated [, treat as literal [
                        if n_idx < len(name) and name[n_idx] == '[':
                            return match_here(p_idx_start + 1, n_idx + 1)
                        return False
            
            if end == -1:
                # Unterminated [, treat as literal [
                if n_idx < len(name) and name[n_idx] == '[':
                    return match_here(p_idx_start + 1, n_idx + 1)
                return False
            
            # Extract the class content (between start and end, exclusive of the closing ])
            class_content = pattern[start:end]
            new_p_idx = end + 1  # position after the closing ]
            
            # Check if name[n_idx] is in the class
            if n_idx >= len(name):
                return False
            
            ch = name[n_idx]
            in_class = match_char_class(ch, class_content)
            
            if negate:
                in_class = not in_class
            
            if in_class:
                return match_here(new_p_idx, n_idx + 1)
            return False
        
        else:
            # Literal character
            if n_idx < len(name) and name[n_idx] == p_char:
                return match_here(p_idx + 1, n_idx + 1)
            return False
    
    def match_char_class(ch, class_content):
        """
        Check if ch is in the character class defined by class_content.
        class_content is the string between [ and ] (excluding them).
        Handles ranges like a-z.
        """
        i = 0
        while i < len(class_content):
            if i + 2 < len(class_content) and class_content[i + 1] == '-':
                # Range
                start_char = class_content[i]
                end_char = class_content[i + 2]
                if ord(start_char) <= ord(ch) <= ord(end_char):
                    return True
                i += 3
            else:
                if class_content[i] == ch:
                    return True
                i += 1
        return False
    
    return match_here(0, 0)
