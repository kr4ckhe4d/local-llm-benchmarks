def glob_match(pattern, name):
    # Parse the pattern into a list of matchers
    # Each matcher is a function that takes a character and returns True/False
    # or a special 'any' marker.
    tokens = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == '*':
            tokens.append(('any',))
            i += 1
        elif char == '?':
            tokens.append(('one',))
            i += 1
        elif char == '[':
            i += 1
            negate = False
            if i < len(pattern) and pattern[i] == '!':
                negate = True
                i += 1
            
            # Check for literal ']' immediately after '[' or '[!'
            if i < len(pattern) and pattern[i] == ']':
                tokens.append(('literal', ']'))
                i += 1
                continue

            chars = set()
            closed = False
            while i < len(pattern):
                if pattern[i] == ']':
                    closed = True
                    break
                elif pattern[i] == '\\': # Standard glob usually handles \, but not requested. 
                    # However, we must ensure we don't break on escaped chars if they existed.
                    pass
                elif i + 1 < len(pattern) and pattern[i+1] == '-':
                    # Range [a-z]
                    start = ord(pattern[i])
                    end = ord(pattern[i+1])
                    for code in range(start, end + 1):
                        chars.add(chr(code))
                    i += 2
                else:
                    chars.add(pattern[i])
                    i += 1
            
            if not closed:
                # Unterminated [ is a literal [
                tokens.append(('literal', '['))
            else:
                i += 1 # Skip the closing ]
                if negate:
                    # Negation logic: match if char NOT in set
                    tokens.append(('set', chars, True))
                else:
                    tokens.append(('set', chars, False))
        else:
            tokens.append(('literal', char))
            i += 1

    # Recursive matching with memoization to handle the '*' backtracking
    memo = {}

    def solve(t_idx, s_idx):
        state = (t_idx, s_idx)
        if state in memo:
            return memo[state]
        
        # Base case: reached end of pattern
        if t_idx == len(tokens):
            return s_idx == len(name)
        
        token = tokens[t_idx]
        res = False
        
        if token[0] == 'any':
            # * can match empty string or any sequence
            # Try matching empty first (greedy/backtracking)
            if solve(t_idx + 1, s_idx):
                res = True
            else:
                # Try matching one char and stay on *
                if s_idx < len(name):
                    if solve(t_idx, s_idx + 1):
                        res = True
        elif token[0] == 'one':
            if s_idx < len(name):
                res = solve(t_idx + 1, s_idx + 1)
        elif token[0] == 'literal':
            if s_idx < len(name) and name[s_idx] == token[1]:
                res = solve(t_idx + 1, s_idx + 1)
        elif token[0] == 'set':
            char_set, negate = token[1], token[2]
            if s_idx < len(name):
                is_in = name[s_idx] in char_set
                if (is_in and not negate) or (not is_in and negate):
                    res = solve(t_idx + 1, s_idx + 1)
        
        memo[state] = res
        return res

    return solve(0, 0)
