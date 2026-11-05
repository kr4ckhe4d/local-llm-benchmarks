def glob_match(pattern, name):
    """
    Implement fnmatch.fnmatchcase semantics from scratch.
    Supports:
    - * : match any run of characters (including empty)
    - ? : match exactly one character
    - [seq] : match any character in seq
    - [!seq] : match any character NOT in seq
    - [a-z] : ranges
    - ] immediately after [ or [! is a literal ]
    - Unterminated [ is a literal [
    Anchored match (whole string).
    """
    import sys
    sys.setrecursionlimit(10000)
    
    def match_here(pat_idx, name_idx):
        """
        Match pattern[pat_idx:] against name[name_idx:].
        Returns True if it matches.
        """
        # Base case: pattern exhausted
        if pat_idx >= len(pattern):
            return name_idx >= len(name)
        
        p = pattern[pat_idx]
        
        if p == '*':
            # * matches any run of characters (including empty)
            n_len = len(name)
            for end_idx in range(name_idx, n_len + 1):
                if match_here(pat_idx + 1, end_idx):
                    return True
            return False
        
        elif p == '?':
            if name_idx >= len(name):
                return False
            return match_here(pat_idx + 1, name_idx + 1)
        
        elif p == '[':
            # Parse the character class
            negated = False
            idx = pat_idx + 1
            if idx < len(pattern) and pattern[idx] == '!':
                negated = True
                idx += 1
            
            # Check if the class is valid
            if idx >= len(pattern):
                # Unterminated [, treat as literal [
                if name_idx >= len(name):
                    return False
                return name[name_idx] == '[' and match_here(pat_idx + 1, name_idx + 1)
            
            # Find the closing bracket
            # If pattern[idx] == ']', it's a literal ], so the closing ] must be later
            if pattern[idx] == ']':
                # This ] is a literal, find the next ]
                end_idx = idx + 1
                while end_idx < len(pattern) and pattern[end_idx] != ']':
                    end_idx += 1
            else:
                end_idx = idx
                while end_idx < len(pattern) and pattern[end_idx] != ']':
                    end_idx += 1
            
            if end_idx >= len(pattern):
                # No closing ], so [ is a literal
                if name_idx >= len(name):
                    return False
                return name[name_idx] == '[' and match_here(pat_idx + 1, name_idx + 1)
            
            # Now the class is from idx to end_idx (inclusive of the chars between)
            # The closing ] is at end_idx
            # The class body is pattern[idx:end_idx]
            
            # Check if name_idx is within bounds
            if name_idx >= len(name):
                return False
            
            c = name[name_idx]
            
            # Check if c is in the class
            in_class = False
            body = pattern[idx:end_idx]
            
            # Parse the body for ranges and individual chars
            i = 0
            while i < len(body):
                if i + 2 < len(body) and body[i + 1] == '-':
                    # Range: body[i] - body[i+2]
                    start_c = body[i]
                    end_c = body[i + 2]
                    if start_c <= c <= end_c:
                        in_class = True
                        break
                    i += 3
                else:
                    if body[i] == c:
                        in_class = True
                        break
                    i += 1
            
            if negated:
                in_class = not in_class
            
            if in_class:
                return match_here(end_idx + 1, name_idx + 1)
            else:
                return False
        
        else:
            # Literal character
            if name_idx >= len(name):
                return False
            if name[name_idx] != p:
                return False
            return match_here(pat_idx + 1, name_idx + 1)
    
    return match_here(0, 0)
