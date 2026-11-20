def glob_match(pattern, name):
    # Convert pattern into a list of "tokens" (matchers)
    tokens = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == '*':
            tokens.append(('any', None))
            i += 1
        elif char == '?':
            tokens.append(('one', None))
            i += 1
        elif char == '[':
            i += 1
            negate = False
            if i < len(pattern) and pattern[i] == '!':
                negate = True
                i += 1
            
            content = ""
            closed = False
            while i < len(pattern):
                if pattern[i] == ']':
                    closed = True
                    break
                content += pattern[i]
                i += 1
            
            if not closed:
                tokens.append(('literal', '['))
            else:
                i += 1 # skip ']'
                # Parse content for ranges and literals
                j = 0
                while j < len(content):
                    if content[j] == '\\': # Optional escape support if needed, but not specified
                        tokens.append(('literal', content[j+1]))
                        j += 2
                    elif content[j] == '[': # Nested brackets not supported by spec, treat as literal
                        tokens.append(('literal', content[j]))
                        j += 1
                    elif content[j] == ']':
                        tokens.append(('literal', content[j]))
                        j += 1
                    elif content[j] == '-':
                        if j + 1 < len(content):
                            start = ord(content[j])
                            end = ord(content[j+1])
                            # This is a simplification; standard glob handles ranges like a-z
                            # We'll handle the specific char before '-' if it exists
                            pass 
                        j += 1
                    else:
                        # Handle range logic
                        if j + 2 < len(content) and content[j+1] == '-' and content[j+2] in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':
                            start_char = content[j]
                            end_char = content[j+2]
                            # This logic is slightly complex for a "from scratch" without regex.
                            # Let's simplify: if it's a range, we check the char.
                            pass
                        j += 1
                
                # Re-evaluating bracket logic to strictly follow [abc] and [a-z]
                # Since we can't use regex, we parse the content into a set of allowed chars
                allowed = set()
                k = 0
                while k < len(content):
                    if k + 2 < len(content) and content[k+1] == '-' and content[k+2] != ']':
                        start = ord(content[k])
                        end = ord(content[k+2])
                        for code in range(start, end + 1):
                            allowed.add(chr(code))
                        k += 3
                    else:
                        allowed.add(content[k])
                        k += 1
                
                tokens.append(('set', (allowed, negate)))
        else:
            tokens.append(('literal', char))
            i += 1

    # Recursive backtracking matcher
    def match_recursive(t_idx, s_idx):
        if t_idx == len(tokens):
            return s_idx == len(name)
        
        token_type, val = tokens[t_idx]
        
        if token_type == 'any':
            # Try matching the rest of the string with the rest of the tokens
            # But we must handle the fact that '*' can match 0 to many chars
            for length in range(len(name) - s_idx + 1):
                if match_recursive(t_idx + 1, s_idx + length):
                    return True
            return False
        
        elif token_type == 'one':
            if s_idx < len(name):
                return match_recursive(t_idx + 1, s_idx + 1)
            return False
        
        elif token_type == 'literal':
            if s_idx < len(name) and name[s_idx] == val:
                return match_recursive(t_idx + 1, s_idx + 1)
            return False
        
        elif token_type == 'set':
            allowed_set, negate = val
            if s_idx < len(name):
                char_match = name[s_idx] in allowed_set
                if (char_match and not negate) or (not char_match and negate):
                    return match_recursive(t_idx + 1, s_idx + 1)
            return False
        
        return False

    # Optimization: Standard backtracking for '*' is slow. 
    # Use a simple DP-like approach or recursive with memoization if needed.
    # For standard glob, we can use a simpler recursive approach:
    memo = {}
    def solve(t_idx, s_idx):
        state = (t_idx, s_idx)
        if state in memo: return memo[state]
        
        if t_idx == len(tokens):
            return s_idx == len(name)
        
        token_type, val = tokens[t_idx]
        res = False
        
        if token_type == 'any':
            for length in range(len(name) - s_idx + 1):
                if solve(t_idx + 1, s_idx + length):
                    res = True
                    break
        elif token_type == 'one':
            if s_idx < len(name):
                res = solve(t_idx + 1, s_idx + 1)
        elif token_type == 'literal':
            if s_idx < len(name) and name[s_idx] == val:
                res = solve(t_idx + 1, s_idx + 1)
        elif token_type == 'set':
            allowed_set, negate = val
            if s_idx < len(name):
                char_match = name[s_idx] in allowed_set
                if (char_match and not negate) or (not char_match and negate):
                    res = solve(t_idx + 1, s_idx + 1)
        
        memo[state] = res
        return res

    return solve(0, 0)
