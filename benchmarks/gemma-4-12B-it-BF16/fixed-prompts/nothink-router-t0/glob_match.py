def glob_match(pattern, name):
    i = 0
    n = len(name)
    
    def match_char(p_idx, c):
        if p_idx >= len(pattern):
            return False
        p = pattern[p_idx]
        
        if p == '*':
            return True
        if p == '?':
            return n > 0 and c is not None
        
        if p == '[':
            # Check if it's an unterminated [ (literal)
            # We look for the closing ] that isn't escaped or part of a range
            # But the rule says "A ] immediately after [ or [! is a literal"
            # and "An unterminated [ is a literal [".
            # To handle this correctly, we find the matching ].
            
            # Look ahead to see if there is a closing bracket
            # If no closing bracket exists, it's a literal '['
            end_bracket = -1
            for j in range(p_idx + 1, len(pattern)):
                if pattern[j] == ']':
                    end_bracket = j
                    break
            
            if end_bracket == -1:
                return p_idx == len(pattern) - 1 and name[0:1] == '[' # Simplified logic for literal
                # Actually, if unterminated, the [ is just a character.
                # Let's re-evaluate: if no ] exists, pattern[p_idx] is literal '['.
                return False # Placeholder, handled by logic below

            # It is a bracket expression
            content = pattern[p_idx + 1 : end_bracket]
            negate = False
            start_idx = p_idx + 1
            if content.startswith('!'):
                negate = True
                start_idx += 1
            
            # Check if the first char after [ or [! is ]
            if start_idx < len(content) and content[0] == ']':
                # Literal ] case
                return name[0:1] == ']' and (p_idx + 1 == end_bracket)

            # Standard bracket logic
            allowed = set()
            j = start_idx
            while j < len(content):
                char = content[j]
                if char == ']': break # Should not happen based on rules but for safety
                if j + 1 < len(content) and content[j+1] == '-':
                    # Range
                    start_c = char
                    end_c = content[j+2]
                    for code in range(ord(start_c), ord(end_c) + 1):
                        allowed.add(chr(code))
                    j += 2
                else:
                    allowed.add(char)
                j += 1
            
            is_match = c in allowed
            return not is_match if negate else is_match

        return p == c

    # Since we need to handle '*' which can match multiple chars, 
    # and the pattern is anchored, we use recursion with memoization or DP.
    memo = {}

    def solve(p_idx, n_idx):
        state = (p_idx, n_idx)
        if state in memo: return memo[state]
        
        if p_idx == len(pattern):
            return n_idx == n
        
        res = False
        p = pattern[p_idx]
        
        if p == '*':
            # Match empty
            if solve(p_idx + 1, n_idx):
                res = True
            # Match one or more
            if not res and n_idx < n:
                if solve(p_idx, n_idx + 1):
                    res = True
        elif n_idx < n:
            # Handle bracket logic specifically here to manage the "unterminated" rule
            if p == '[':
                end_bracket = -1
                for j in range(p_idx + 1, len(pattern)):
                    if pattern[j] == ']':
                        end_bracket = j
                        break
                
                if end_bracket == -1: # Unterminated
                    if name[n_idx] == '[':
                        res = solve(p_idx + 1, n_idx + 1)
                else:
                    content = pattern[p_idx + 1 : end_bracket]
                    negate = False
                    start_idx = p_idx + 1
                    if content.startswith('!'):
                        negate = True
                        start_idx += 1
                    
                    if start_idx < len(content) and content[0] == ']':
                        if name[n_idx] == ']':
                            res = solve(end_bracket + 1, n_idx + 1)
                    else:
                        allowed = set()
                        j = start_idx
                        while j < len(content):
                            char = content[j]
                            if char == ']': break
                            if j + 1 < len(content) and content[j+1] == '-':
                                for code in range(ord(char), ord(content[j+2]) + 1):
                                    allowed.add(chr(code))
                                j += 2
                            else:
                                allowed.add(char)
                            j += 1
                        
                        is_match = name[n_idx] in allowed
                        if negate: is_match = not is_match
                        res = is_match and solve(end_bracket + 1, n_idx + 1)
            elif p == '?':
                res = solve(p_idx + 1, n_idx + 1)
            else:
                res = (name[n_idx] == p) and solve(p_idx + 1, n_idx + 1)
        else:
            # Pattern remains but name is exhausted
            if p == '*':
                res = solve(p_idx + 1, n_idx)
            else:
                res = False
                
        memo[state] = res
        return res

    return solve(0, 0)
