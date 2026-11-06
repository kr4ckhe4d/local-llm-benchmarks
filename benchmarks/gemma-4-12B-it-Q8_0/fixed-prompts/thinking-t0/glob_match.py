def glob_match(pattern, name):
    matchers = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == '*':
            matchers.append(('wildcard', None))
            i += 1
        elif char == '?':
            matchers.append(('single', None))
            i += 1
        elif char == '[':
            # Check for literal "]" immediately after "["
            if i + 1 < len(pattern) and pattern[i+1] == ']':
                matchers.append(('literal', ']'))
                i += 2
            # Check for negated set "[!"
            elif i + 1 < len(pattern) and pattern[i+1] == '!':
                i += 2
                negated = True
                chars = set()
                while i < len(pattern) and pattern[i] != ']':
                    if i + 1 < len(pattern) and pattern[i] != pattern[i+1] and pattern[i+1] == '-':
                        # Handle range like a-z
                        start = ord(pattern[i])
                        end = ord(pattern[i+2])
                        for code in range(start, end + 1):
                            chars.add(chr(code))
                        i += 3
                    else:
                        chars.add(pattern[i])
                        i += 1
                matchers.append(('set', (chars, negated)))
                if i < len(pattern): i += 1 # skip closing ]
            else:
                # Standard set [...]
                i += 1
                chars = set()
                while i < len(pattern) and pattern[i] != ']':
                    if i + 1 < len(pattern) and pattern[i] != pattern[i+1] and pattern[i+1] == '-':
                        start = ord(pattern[i])
                        end = ord(pattern[i+2])
                        for code in range(start, end + 1):
                            chars.add(chr(code))
                        i += 3
                    else:
                        chars.add(pattern[i])
                        i += 1
                
                if i >= len(pattern): # Unterminated [
                    matchers.append(('literal', '['))
                else:
                    matchers.append(('set', (chars, False)))
                    i += 1 # skip closing ]
        else:
            matchers.append(('literal', char))
            i += 1

    memo = {}

    def solve(m_idx, n_idx):
        state = (m_idx, n_idx)
        if state in memo:
            return memo[state]
        
        if m_idx == len(matchers):
            return n_idx == len(name)
        
        m_type, m_val = matchers[m_idx]
        
        res = False
        if m_type == 'wildcard':
            # Try matching 0 characters (skip wildcard)
            if solve(m_idx + 1, n_idx):
                res = True
            # Try matching 1 character and stay on wildcard to match more
            elif n_idx < len(name) and solve(m_idx, n_idx + 1):
                res = True
        elif m_type == 'single':
            if n_idx < len(name):
                res = solve(m_idx + 1, n_idx + 1)
        elif m_type == 'literal':
            if n_idx < len(name) and name[n_idx] == m_val:
                res = solve(m_idx + 1, n_idx + 1)
        elif m_type == 'set':
            chars, negated = m_val
            if n_idx < len(name):
                is_in = name[n_idx] in chars
                if (is_in and not negated) or (not is_in and negated):
                    res = solve(m_idx + 1, n_idx + 1)
        
        memo[state] = res
        return res

    return solve(0, 0)
