def glob_match(pattern, name):
    """
    Match pattern against name using fnmatch.fnmatchcase semantics.
    Supports *, ?, [seq], [!seq], with ] immediately after [ or [! being literal.
    Unterminated [ is treated as literal [.
    """
    # Preprocess pattern into a list of tokens
    # Each token is one of:
    #   ('star',)
    #   ('question',)
    #   ('char', c)
    #   ('set', negated, chars_set)  where chars_set is a set of chars, negated is bool
    #   ('literal', c)
    
    tokens = []
    i = 0
    n = len(pattern)
    
    while i < n:
        c = pattern[i]
        if c == '*':
            tokens.append(('star',))
            i += 1
        elif c == '?':
            tokens.append(('question',))
            i += 1
        elif c == '[':
            # Check for ] immediately after [ or [!
            # Look for the closing ]
            j = i + 1
            negated = False
            if j < n and pattern[j] == '!':
                negated = True
                j += 1
            # If the next char is ], it's a literal ]
            if j < n and pattern[j] == ']':
                # ] is literal, so we need to find the next ]
                j += 1
                # Now look for the closing ]
                close_j = j
                while close_j < n and pattern[close_j] != ']':
                    close_j += 1
                if close_j >= n:
                    # No closing ] found, treat [ as literal
                    tokens.append(('literal', '['))
                    i += 1
                else:
                    # We have a set from j to close_j-1, but the first ] at position i+1 (or i+2 if negated) is literal
                    # Wait, let me reconsider. The spec says "A ] immediately after [ or [! is a literal."
                    # So if pattern is [!], the ] is literal, and we need to find another ] to close the set.
                    # Let me re-parse:
                    # i points to [
                    # j was i+1, if pattern[j] == '!', negated=True, j=i+2
                    # if pattern[j] == ']', this ] is literal
                    # So we need to find the next ] starting from j+1
                    close_j = j + 1
                    while close_j < n and pattern[close_j] != ']':
                        close_j += 1
                    if close_j >= n:
                        # No closing ] found, treat [ as literal
                        tokens.append(('literal', '['))
                        i += 1
                    else:
                        # The set content is from j to close_j-1, but the ] at position j is literal
                        # Actually, the chars in the set are pattern[j:close_j]
                        # But the first char (at position j) is ']' which is literal
                        # So the set contains ']' and any other chars between j+1 and close_j-1
                        set_chars = set()
                        # Parse the set content from j to close_j-1
                        k = j
                        while k < close_j:
                            ch = pattern[k]
                            if k + 2 < close_j and pattern[k+1] == '-':
                                start_c = ch
                                end_c = pattern[k+2]
                                # Add range
                                for code in range(ord(start_c), ord(end_c) + 1):
                                    set_chars.add(chr(code))
                                k += 3
                            else:
                                set_chars.add(ch)
                                k += 1
                        tokens.append(('set', negated, set_chars))
                        i = close_j + 1
            else:
                # Normal case: find the closing ]
                close_j = j
                while close_j < n and pattern[close_j] != ']':
                    close_j += 1
                if close_j >= n:
                    # No closing ] found, treat [ as literal
                    tokens.append(('literal', '['))
                    i += 1
                else:
                    # Parse the set content from j to close_j-1
                    set_chars = set()
                    k = j
                    while k < close_j:
                        ch = pattern[k]
                        if k + 2 < close_j and pattern[k+1] == '-':
                            start_c = ch
                            end_c = pattern[k+2]
                            for code in range(ord(start_c), ord(end_c) + 1):
                                set_chars.add(chr(code))
                            k += 3
                        else:
                            set_chars.add(ch)
                            k += 1
                    tokens.append(('set', negated, set_chars))
                    i = close_j + 1
        else:
            tokens.append(('char', c))
            i += 1
    
    # Now match tokens against name using backtracking
    # We'll use a recursive approach with memoization or iterative backtracking
    # Since * can match any run, we need backtracking.
    
    # Use iterative backtracking with a stack
    # State: (token_index, name_index)
    # We'll use a DFS approach
    
    from collections import defaultdict
    
    # Memoization for visited states to avoid exponential blowup
    # But since we need to handle * properly, let's use a different approach
    
    # Actually, let's use a recursive function with memoization
    # But to avoid recursion depth issues, let's think about this more carefully
    
    # For simplicity and correctness, let's use a recursive approach with memoization
    # The state is (token_idx, name_idx)
    
    memo = {}
    
    def match(token_idx, name_idx):
        if (token_idx, name_idx) in memo:
            return memo[(token_idx, name_idx)]
        
        if token_idx == len(tokens):
            result = name_idx == len(name)
            memo[(token_idx, name_idx)] = result
            return result
        
        if name_idx == len(name):
            # No more name to match
            # Check if remaining tokens can all match empty string
            # Only * can match empty
            result = True
            for t in tokens[token_idx:]:
                if t[0] != 'star':
                    result = False
                    break
            memo[(token_idx, name_idx)] = result
            return result
        
        token = tokens[token_idx]
        result = False
        
        if token[0] == 'star':
            # * can match any run including empty
            # Try matching 0, 1, 2, ... characters
            # First try matching 0 characters (move to next token)
            if match(token_idx + 1, name_idx):
                result = True
            else:
                # Try matching 1 or more characters
                for k in range(name_idx, len(name)):
                    if match(token_idx + 1, k + 1):
                        result = True
                        break
        elif token[0] == 'question':
            # ? matches exactly one char
            if match(token_idx + 1, name_idx + 1):
                result = True
        elif token[0] == 'char':
            if name[name_idx] == token[1]:
                if match(token_idx + 1, name_idx + 1):
                    result = True
        elif token[0] == 'literal':
            if name[name_idx] == token[1]:
                if match(token_idx + 1, name_idx + 1):
                    result = True
        elif token[0] == 'set':
            _, negated, set_chars = token
            ch = name[name_idx]
            if negated:
                if ch not in set_chars:
                    if match(token_idx + 1, name_idx + 1):
                        result = True
            else:
                if ch in set_chars:
                    if match(token_idx + 1, name_idx + 1):
                        result = True
        
        memo[(token_idx, name_idx)] = result
        return result
    
    return match(0, 0)
