def glob_match(pattern, name):
    """
    Implement fnmatch.fnmatchcase semantics from scratch.
    
    Supports:
    - * : matches any run of characters (including empty)
    - ? : matches exactly one character
    - [seq] : matches any character in seq
    - [!seq] : matches any character NOT in seq
    - ] immediately after [ or [! is a literal ]
    - Unterminated [ is a literal [
    
    Matching is anchored to the whole string.
    """
    def match_here(pattern, name):
        """
        Match pattern against name, both starting at their current positions.
        Returns True if the entire remaining pattern matches the entire remaining name.
        """
        while pattern:
            c = pattern[0]
            if c == '*':
                # Skip consecutive stars
                while pattern and pattern[0] == '*':
                    pattern = pattern[1:]
                if not pattern:
                    return True
                # Try matching the rest of the pattern against every possible
                # suffix of name (including empty)
                for i in range(len(name) + 1):
                    if match_here(pattern, name[i:]):
                        return True
                return False
            elif c == '?':
                if not name:
                    return False
                pattern = pattern[1:]
                name = name[1:]
            elif c == '[':
                # Parse the character class
                pos = 1
                negated = False
                if pos < len(pattern) and pattern[pos] == '!':
                    negated = True
                    pos += 1
                
                # Check if the next character is ']'
                if pos < len(pattern) and pattern[pos] == ']':
                    # This ']' is a literal member of the class
                    # Find the actual closing ']'
                    pos += 1
                    while pos < len(pattern) and pattern[pos] != ']':
                        pos += 1
                    if pos >= len(pattern):
                        # Unterminated
                        if not name:
                            return False
                        if name[0] != '[':
                            return False
                        pattern = pattern[1:]
                        name = name[1:]
                        continue
                    class_content = pattern[1:pos]
                    closing_pos = pos
                else:
                    # Normal case
                    pos2 = pos
                    while pos2 < len(pattern) and pattern[pos2] != ']':
                        pos2 += 1
                    if pos2 >= len(pattern):
                        # Unterminated
                        if not name:
                            return False
                        if name[0] != '[':
                            return False
                        pattern = pattern[1:]
                        name = name[1:]
                        continue
                    class_content = pattern[pos:pos2]
                    closing_pos = pos2
                
                # Now check if name is empty
                if not name:
                    return False
                
                ch = name[0]
                
                # Check if ch is in the class
                in_class = False
                j = 0
                while j < len(class_content):
                    if class_content[j] == '-':
                        # Check for range: need previous char and next char
                        if j >= 1 and j + 1 < len(class_content):
                            low = class_content[j - 1]
                            high = class_content[j + 1]
                            if low <= ch <= high:
                                in_class = True
                                break
                            # Skip past the range
                            j += 2
                            continue
                        # If not a valid range, treat '-' as literal
                        if ch == '-':
                            in_class = True
                            break
                        j += 1
                    else:
                        if ch == class_content[j]:
                            in_class = True
                            break
                        j += 1
                
                if negated:
                    in_class = not in_class
                
                if not in_class:
                    return False
                
                pattern = pattern[closing_pos + 1:]
                name = name[1:]
            else:
                # Literal character
                if not name or name[0] != c:
                    return False
                pattern = pattern[1:]
                name = name[1:]
        
        return not name
    
    return match_here(pattern, name)
