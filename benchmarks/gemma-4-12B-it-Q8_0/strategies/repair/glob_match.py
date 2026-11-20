def glob_match(pattern, name):
    p = len(pattern)
    n = len(name)

    def match_from(p_idx, n_idx):
        if p_idx == p:
            return n_idx == n
        
        char = pattern[p_idx]

        if char == '*':
            for j in range(n_idx, n + 1):
                if match_from(p_idx + 1, j):
                    return True
            return False
        
        elif char == '?':
            if n_idx < n:
                return match_from(p_idx + 1, n_idx + 1)
            return False
        
        elif char == '[':
            close_idx = -1
            for k in range(p_idx + 1, p):
                if pattern[k] == ']':
                    close_idx = k
                    break
            
            if close_idx == -1:
                if n_idx < n and name[n_idx] == '[':
                    return match_from(p_idx + 1, n_idx + 1)
                return False
            
            negate = False
            start_content = 0
            if p_idx + 1 < p and pattern[p_idx + 1] == '!':
                negate = True
                start_content = 1
            
            # The content is between the [ (or [!) and the ]
            content = pattern[p_idx + start_content : close_idx]
            
            # Special case: ] immediately after [ or [!
            if content == ']':
                if n_idx < n and name[n_idx] == ']':
                    return match_from(close_idx + 1, n_idx + 1)
                return False

            allowed = set()
            k = 0
            while k < len(content):
                # Check for range: char followed by '-' and a char that isn't ']'
                if k + 2 < len(content) and content[k+1] == '-' and content[k+2] != ']':
                    start_c = content[k]
                    end_c = content[k+2]
                    for char_code in range(ord(start_c), ord(end_c) + 1):
                        allowed.add(chr(char_code))
                    k += 3
                else:
                    allowed.add(content[k])
                    k += 1
            
            if n_idx < n:
                is_in = name[n_idx] in allowed
                if (negate and not is_in) or (not negate and is_in):
                    return match_from(close_idx + 1, n_idx + 1)
            return False

        else:
            if n_idx < n and name[n_idx] == char:
                return match_from(p_idx + 1, n_idx + 1)
            return False

    return match_from(0, 0)
