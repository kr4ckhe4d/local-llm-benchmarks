def glob_match(pattern, name):
    i = 0
    n = len(name)
    p = 0
    m = len(pattern)

    while p < m and i < n:
        char = pattern[p]

        if char == '*':
            # Skip '*' and find the first possible match for the rest of the pattern
            # by backtracking or checking if the rest matches.
            # Since we need to handle multiple stars, we use a recursive-style 
            # logic or a simple greedy approach with backtracking.
            # For simplicity in this manual implementation, we check all possible 
            # split points for the '*' match.
            
            # Find the longest suffix of 'name' that matches the remainder of 'pattern'
            # However, to handle multiple stars correctly, we can use a helper.
            def match_from(p_idx, n_idx):
                if p_idx == m:
                    return n_idx == n
                if pattern[p_idx] == '*':
                    # Try matching '*' with 0 to remaining chars
                    for k in range(n - n_idx + 1):
                        if match_from(p_idx + 1, n_idx + k):
                            return True
                    return False
                if n_idx < n and (pattern[p_idx] == name[n_idx] or pattern[p_idx] == '?'):
                    return match_from(p_idx + 1, n_idx + 1)
                return False

            # To avoid recursion depth issues for very long strings, we use a 
            # standard DP-like approach for the remaining part.
            dp = [[False] * (n - i + 1) for _ in range(m - p + 1)]
            for j in range(n - i + 1):
                dp[m - p][j] = True
            
            for row in range(m - p - 1, -1, -1):
                for col in range(n - i, -1, -1):
                    curr_p = pattern[p + row]
                    curr_n = name[i + col] if col > 0 else None
                    
                    if curr_p == '*':
                        dp[row][col] = dp[row+1][col] or (col < n - i and dp[row][col+1])
                    elif col > 0 and (curr_p == '?' or curr_p == curr_n):
                        dp[row][col] = dp[row+1][col+1]
                    else:
                        dp[row][col] = False
            return dp[0][0]

        elif char == '?':
            if i < n:
                i += 1
                p += 1
            else:
                return False
        elif char == '[':
            # Check if it's a valid set or literal
            # Look ahead to see if it's unterminated
            end_bracket = -1
            for k in range(p + 1, m):
                if pattern[k] == ']':
                    end_bracket = k
                    break
            
            if end_bracket == -1: # Unterminated
                if i < n and name[i] == '[':
                    i += 1
                    p += 1
                else:
                    return False
            else:
                # It is a set [abc] or [!abc]
                content = pattern[p+1:end_bracket]
                negate = content.startswith('!')
                set_chars = content[1:] if negate else content
                
                match_found = False
                if i < n:
                    current_char = name[i]
                    for char_in_set in set_chars:
                        if char_in_set == '-':
                            # Handle ranges like a-z
                            # Find start and end of range
                            # This logic assumes standard [a-z] format
                            # We need to find the char before and after '-'
                            # But since we iterate set_chars, we handle it specifically:
                            pass 
                        elif char_in_set == current_char:
                            match_found = True
                            break
                    
                    # Handle ranges specifically
                    k = 0
                    while k < len(set_chars):
                        if set_chars[k] == '-' and k > 0 and k < len(set_chars) - 1:
                            start = set_chars[k-1]
                            end = set_chars[k+1]
                            if ord(start) <= ord(current_char) <= ord(end):
                                match_found = True
                                break
                            k += 2 # skip the range
                        else:
                            k += 1

                    # Re-check logic for ranges more robustly
                    # Let's re-evaluate set_chars for ranges
                    match_found = False
                    idx = 0
                    while idx < len(set_chars):
                        c = set_chars[idx]
                        if c == '-' and idx > 0 and idx < len(set_chars)-1:
                            s = set_chars[idx-1]
                            e = set_chars[idx+1]
                            if ord(s) <= ord(current_char) <= ord(e):
                                match_found = True
                                break
                            idx += 2
                        else:
                            if c == current_char:
                                match_found = True
                                break
                            idx += 1
                
                if negate:
                    match_found = not match_found
                
                if match_found:
                    i += 1
                    p = end_bracket + 1
                else:
                    return False
        else:
            if i < n and name[i] == pattern[p]:
                i += 1
                p += 1
            else:
                return False

    return i == n and p == m
