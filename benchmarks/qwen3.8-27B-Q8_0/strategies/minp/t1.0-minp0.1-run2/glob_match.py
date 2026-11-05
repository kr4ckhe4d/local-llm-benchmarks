def glob_match(pattern, name):
    # Parse pattern into a list of (type, value) tokens
    # Types: 'char', 'star', 'q', 'set'
    # 'char': single literal char
    # 'star': *
    # 'q': ?
    # 'set': (chars, negated) for [abc], [!abc]
    
    tokens = []
    i = 0
    n = len(pattern)
    
    while i < n:
        c = pattern[i]
        if c == '*':
            tokens.append(('star', None))
            i += 1
        elif c == '?':
            tokens.append(('q', None))
            i += 1
        elif c == '[':
            # Check for unterminated bracket
            j = i + 1
            negated = False
            if j < n and pattern[j] == '!':
                negated = True
                j += 1
            # If ] is immediately after [ or [!, it's a literal ]
            if j < n and pattern[j] == ']':
                # This ] is part of the set
                chars = set()
                chars.add(']')
                j += 1
                # Now look for closing ]
                while j < n and pattern[j] != ']':
                    if pattern[j] == '-':
                        # Could be a range or literal -
                        # Look ahead to see if it's a range
                        if j + 2 < n and pattern[j + 2] != ']':
                            start_char = pattern[j - 1]
                            end_char = pattern[j + 1]
                            if ord(start_char) <= ord(end_char):
                                for k in range(ord(start_char), ord(end_char) + 1):
                                    chars.add(chr(k))
                            j += 2
                        else:
                            # Literal -
                            chars.add('-')
                            j += 1
                    else:
                        chars.add(pattern[j])
                        j += 1
                if j < n and pattern[j] == ']':
                    tokens.append(('set', (chars, negated)))
                    i = j + 1
                    continue
                else:
                    # Unterminated [
                    tokens.append(('char', '['))
                    i += 1
                    continue
            else:
                # Normal case, look for ]
                if j >= n:
                    # Unterminated
                    tokens.append(('char', '['))
                    i += 1
                    continue
                # Check if immediately after [ or [! there's a ]
                # We already handled that case above
                # Now collect characters until ]
                chars = set()
                while j < n and pattern[j] != ']':
                    if pattern[j] == '-':
                        # Could be a range
                        if j > i + 1 and j + 1 < n and pattern[j + 1] != ']':
                            start_char = pattern[j - 1]
                            end_char = pattern[j + 1]
                            if ord(start_char) <= ord(end_char):
                                for k in range(ord(start_char), ord(end_char) + 1):
                                    chars.add(chr(k))
                            j += 2
                        else:
                            chars.add('-')
                            j += 1
                    else:
                        chars.add(pattern[j])
                        j += 1
                if j < n and pattern[j] == ']':
                    tokens.append(('set', (chars, negated)))
                    i = j + 1
                    continue
                else:
                    # Unterminated
                    tokens.append(('char', '['))
                    i += 1
                    continue
        else:
            tokens.append(('char', c))
            i += 1
    
    # Now match name against tokens using recursion with memoization or backtracking
    # Use dynamic programming / backtracking
    # State: (token_idx, name_idx)
    
    from functools import lru_cache
    
    @lru_cache(maxsize=None)
    def match(idx_t, idx_n):
        if idx_t == len(tokens):
            return idx_n == len(name)
        if idx_n == len(name):
            # Remaining tokens must all be stars
            for k in range(idx_t, len(tokens)):
                if tokens[k][0] != 'star':
                    return False
            return True
        
        t_type, t_val = tokens[idx_t]
        
        if t_type == 'star':
            # * matches any number of characters
            # Try matching 0, 1, 2, ... characters
            for skip in range(len(name) - idx_n + 1):
                if match(idx_t + 1, idx_n + skip):
                    return True
            return False
        elif t_type == 'q':
            return match(idx_t + 1, idx_n + 1)
        elif t_type == 'char':
            if name[idx_n] == t_val:
                return match(idx_t + 1, idx_n + 1)
            return False
        elif t_type == 'set':
            chars, negated = t_val
            c = name[idx_n]
            if negated:
                if c not in chars:
                    return match(idx_t + 1, idx_n + 1)
                return False
            else:
                if c in chars:
                    return match(idx_t + 1, idx_n + 1)
                return False
    
    return match(0, 0)
