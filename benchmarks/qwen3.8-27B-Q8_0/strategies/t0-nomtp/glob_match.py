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
                # Check for unterminated [
                # Find the closing ]
                # A ] immediately after [ or [! is a literal
                i = 1
                negated = False
                if i < len(pattern) and pattern[i] == '!':
                    negated = True
                    i += 1
                # If ] is immediately after [ or [!, it's a literal ]
                if i < len(pattern) and pattern[i] == ']':
                    # This ] is a literal, so we need to find the next ]
                    i += 1
                # Now find the closing ]
                start = i
                while i < len(pattern) and pattern[i] != ']':
                    i += 1
                if i >= len(pattern):
                    # Unterminated [ is a literal [
                    if not name:
                        return False
                    if name[0] != '[':
                        return False
                    pattern = pattern[1:]
                    name = name[1:]
                    continue
                # Extract the class content
                class_content = pattern[start:i]
                # Check if the first char in class_content is a literal ]
                # (i.e., if the original pattern had ] right after [ or [!)
                # We already handled that by advancing i past it, so class_content
                # starts after that literal ] if present.
                # Actually, let me re-think. Let me re-parse more carefully.
                
                # Let me redo the parsing:
                # pattern[0] == '['
                # pos = 1
                # negated = False
                # if pos < len(pattern) and pattern[pos] == '!':
                #     negated = True
                #     pos += 1
                # # Check if next char is ]
                # if pos < len(pattern) and pattern[pos] == ']':
                #     # This ] is a literal member of the class
                #     # So the class includes ']'
                #     # We need to find the actual closing ]
                #     # The class content starts with ']'
                #     literal_bracket = True
                #     pos += 1
                # else:
                #     literal_bracket = False
                # # Now find the closing ]
                # start = pos
                # while pos < len(pattern) and pattern[pos] != ']':
                #     pos += 1
                # if pos >= len(pattern):
                #     # Unterminated
                #     if not name:
                #         return False
                #     if name[0] != '[':
                #         return False
                #     pattern = pattern[1:]
                #     name = name[1:]
                #     continue
                # class_content = pattern[start:pos]
                # if literal_bracket:
                #     class_content = ']' + class_content
                # pos += 1  # skip the closing ]
                
                # Let me just re-implement this section cleanly:
                pos = 1
                negated = False
                if pos < len(pattern) and pattern[pos] == '!':
                    negated = True
                    pos += 1
                literal_bracket = False
                if pos < len(pattern) and pattern[pos] == ']':
                    literal_bracket = True
                    pos += 1
                start = pos
                while pos < len(pattern) and pattern[pos] != ']':
                    pos += 1
                if pos >= len(pattern):
                    # Unterminated [ is a literal [
                    if not name:
                        return False
                    if name[0] != '[':
                        return False
                    pattern = pattern[1:]
                    name = name[1:]
                    continue
                class_content = pattern[start:pos]
                if literal_bracket:
                    class_content = ']' + class_content
                pos += 1  # skip the closing ]
                
                if not name:
                    return False
                ch = name[0]
                in_class = False
                # Parse class_content for ranges and individual chars
                j = 0
                while j < len(class_content):
                    if j + 2 < len(class_content) and class_content[j+1] == '-':
                        # Range
                        lo = class_content[j]
                        hi = class_content[j+2]
                        if lo <= ch <= hi:
                            in_class = True
                            break
                        j += 3
                    else:
                        if ch == class_content[j]:
                            in_class = True
                            break
                        j += 1
                if negated:
                    in_class = not in_class
                if not in_class:
                    return False
                pattern = pattern[pos:]
                name = name[1:]
            else:
                # Literal character
                if not name or name[0] != c:
                    return False
                pattern = pattern[1:]
                name = name[1:]
        return not name
    
    return match_here(pattern, name)
