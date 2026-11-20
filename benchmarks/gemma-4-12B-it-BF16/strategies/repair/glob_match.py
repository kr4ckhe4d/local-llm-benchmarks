def glob_match(pattern, name):
    memo = {}

    def solve(p_idx, n_idx):
        state = (p_idx, n_idx)
        if state in memo:
            return memo[state]
        
        if p_idx == len(pattern):
            return n_idx == len(name)
        
        res = False
        p = pattern[p_idx]
        
        if p == '*':
            # Try matching zero characters
            if solve(p_idx + 1, n_idx):
                res = True
            # Try matching one or more characters
            elif n_idx < len(name) and solve(p_idx, n_idx + 1):
                res = True
        elif n_idx < len(name):
            if p == '?':
                res = solve(p_idx + 1, n_idx + 1)
            elif p == '[':
                # Find the closing bracket
                end_bracket = -1
                for j in range(p_idx + 1, len(pattern)):
                    if pattern[j] == ']':
                        end_bracket = j
                        break
                
                if end_bracket == -1:
                    # Unterminated [ is a literal [
                    res = (name[n_idx] == '[') and solve(p_idx + 1, n_idx + 1)
                else:
                    content = pattern[p_idx + 1 : end_bracket]
                    negate = False
                    start_idx = p_idx + 1
                    if content.startswith('!'):
                        negate = True
                        start_idx += 1
                    
                    # Rule: A ] immediately after [ or [! is a literal ]
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
                                start_c = char
                                end_c = content[j+2]
                                for code in range(ord(start_c), ord(end_c) + 1):
                                    allowed.add(chr(code))
                                j += 2
                            else:
                                allowed.add(char)
                            j += 1
                        
                        is_match = name[n_idx] in allowed
                        if negate:
                            is_match = not is_match
                        res = is_match and solve(end_bracket + 1, n_idx + 1)
            else:
                # Literal character match
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
