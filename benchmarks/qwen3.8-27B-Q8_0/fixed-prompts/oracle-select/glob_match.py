def glob_match(pattern, name):
    """
    Implement fnmatch.fnmatchcase semantics from scratch.
    
    Supports:
    - * : matches any run of characters (including empty)
    - ? : matches exactly one character
    - [seq] : matches any single character in seq
    - [!seq] : matches any single character not in seq
    - ] immediately after [ or [! is a literal ]
    - Unterminated [ is a literal [
    - Matching is anchored to the whole string
    """
    
    def parse_bracket(pattern, i):
        """
        Parse a bracket expression starting at pattern[i] which is '['.
        Returns (chars_set, is_negated, end_index) where:
        - chars_set is a set of single characters
        - is_negated is True if the bracket was [!...]
        - end_index is the index of the character after ']'
        
        Returns None if the bracket is not properly terminated (unterminated).
        """
        if i >= len(pattern):
            return None
        
        # pattern[i] is '['
        j = i + 1
        is_negated = False
        
        if j < len(pattern) and pattern[j] == '!':
            is_negated = True
            j += 1
        
        # If the next char is ']', it's a literal ']'
        # We need to check if the bracket is properly terminated
        # A bracket expression is: [ [! ] seq ]
        # If j >= len(pattern) or pattern[j] == ']' and j == i+1 or (j == i+2 and is_negated), 
        # then ']' is literal
        
        # Actually, the rule is: ] immediately after [ or [! is a literal ]
        # So if j points to ']' and this is the first character of the seq, it's literal
        
        chars = set()
        found_closing = False
        
        if j >= len(pattern):
            return None
        
        # Check if the first character after [ or [! is ]
        if pattern[j] == ']':
            # This ] is a literal
            chars.add(']')
            j += 1
        
        # Now parse the rest until we find a ]
        while j < len(pattern):
            if pattern[j] == ']':
                found_closing = True
                break
            if j + 2 < len(pattern) and pattern[j+1] == '-':
                # Range
                start = pattern[j]
                end = pattern[j+2]
                if start <= end:
                    for c in range(ord(start), ord(end) + 1):
                        chars.add(chr(c))
                j += 3
            else:
                chars.add(pattern[j])
                j += 1
        
        if not found_closing:
            return None
        
        return (chars, is_negated, j + 1)
    
    # Use recursion with memoization or backtracking
    # Since * can match anything, we need backtracking
    
    def match(pattern_idx, name_idx):
        """
        Check if pattern[pattern_idx:] matches name[name_idx:].
        Returns True if it does.
        """
        # Base case: both exhausted
        if pattern_idx >= len(pattern) and name_idx >= len(name):
            return True
        
        # Pattern exhausted but name not
        if pattern_idx >= len(pattern):
            return False
        
        # Name exhausted but pattern not
        if name_idx >= len(name):
            # Remaining pattern must all be *'s
            for k in range(pattern_idx, len(pattern)):
                if pattern[k] != '*':
                    return False
            return True
        
        p_char = pattern[pattern_idx]
        
        if p_char == '*':
            # * matches any run of characters (including empty)
            # Try matching zero characters first, then one, etc.
            # To avoid O(n^2) in worst case, we can be smart, but let's do simple backtracking
            # Try matching 0 chars
            if match(pattern_idx + 1, name_idx):
                return True
            # Try matching 1+ chars
            for k in range(name_idx, len(name)):
                if match(pattern_idx + 1, k + 1):
                    return True
            return False
        
        elif p_char == '?':
            # Matches exactly one character
            return match(pattern_idx + 1, name_idx + 1)
        
        elif p_char == '[':
            # Try to parse bracket expression
            parsed = parse_bracket(pattern, pattern_idx)
            if parsed is None:
                # Unterminated [ is a literal [
                if name_idx < len(name) and name[name_idx] == '[':
                    return match(pattern_idx + 1, name_idx + 1)
                else:
                    return False
            else:
                chars, is_negated, end_idx = parsed
                if is_negated:
                    matched = name[name_idx] not in chars
                else:
                    matched = name[name_idx] in chars
                if matched:
                    return match(end_idx, name_idx + 1)
                else:
                    return False
        
        else:
            # Literal character
            if name[name_idx] == p_char:
                return match(pattern_idx + 1, name_idx + 1)
            else:
                return False
    
    return match(0, 0)
