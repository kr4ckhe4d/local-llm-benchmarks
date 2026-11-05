def glob_match(pattern, name):
    """
    Implement fnmatch.fnmatchcase semantics from scratch.
    
    Supports:
    - * : any run of characters (including empty), but not newline
    - ? : exactly one character, but not newline
    - [abc] : character class
    - [a-z] : range
    - [!abc] : negated class
    - ] immediately after [ or [! is literal
    - unterminated [ is literal [
    
    Matching is anchored to the whole string and case-sensitive.
    """
    
    # Pre-parse the pattern into tokens to avoid re-parsing during matching
    # Each token is a tuple:
    #   ('literal', char)
    #   ('star',)
    #   ('question',)
    #   ('class', negated, items) where items is a list of ('char', c) or ('range', start, end)
    
    def parse_pattern(pat):
        tokens = []
        i = 0
        n = len(pat)
        while i < n:
            c = pat[i]
            if c == '*':
                tokens.append(('star',))
                i += 1
            elif c == '?':
                tokens.append(('question',))
                i += 1
            elif c == '[':
                # Try to parse a character class
                # Find the closing ]
                # A ] immediately after [ or [! is literal
                j = i + 1
                negated = False
                if j < n and pat[j] == '!':
                    negated = True
                    j += 1
                # If the next char is ], it's literal, so we need to look further
                if j < n and pat[j] == ']':
                    j += 1  # skip this literal ]
                
                # Now find the closing ]
                close = -1
                k = j
                while k < n:
                    if pat[k] == ']':
                        close = k
                        break
                    k += 1
                
                if close == -1:
                    # No closing ], treat [ as literal
                    tokens.append(('literal', '['))
                    i += 1
                else:
                    # Parse the class body from j to close-1
                    body = pat[j:close]
                    items = parse_class_body(body)
                    tokens.append(('class', negated, items))
                    i = close + 1
            else:
                tokens.append(('literal', c))
                i += 1
        return tokens
    
    def parse_class_body(body):
        """Parse the body of a character class into a list of items."""
        items = []
        i = 0
        n = len(body)
        while i < n:
            c = body[i]
            # Check for range: c - next_char
            if i + 2 < n and body[i + 1] == '-':
                start = c
                end = body[i + 2]
                # Validate range
                if ord(start) > ord(end):
                    raise ValueError(f"Invalid range in character class: {start}-{end}")
                items.append(('range', start, end))
                i += 3
            else:
                items.append(('char', c))
                i += 1
        return items
    
    def char_in_class(ch, negated, items):
        """Check if character ch is in the class defined by items."""
        in_class = False
        for item in items:
            if item[0] == 'char':
                if ch == item[1]:
                    in_class = True
                    break
            elif item[0] == 'range':
                if item[1] <= ch <= item[2]:
                    in_class = True
                    break
        return (not in_class) if negated else in_class
    
    tokens = parse_pattern(pattern)
    num_tokens = len(tokens)
    name_len = len(name)
    
    # Memoization: (token_index, name_index) -> bool
    memo = {}
    
    def match(ti, ni):
        """Return True if tokens[ti:] matches name[ni:]."""
        if (ti, ni) in memo:
            return memo[(ti, ni)]
        
        # Base case: both exhausted
        if ti == num_tokens and ni == name_len:
            memo[(ti, ni)] = True
            return True
        
        # Pattern exhausted but name not
        if ti == num_tokens:
            memo[(ti, ni)] = False
            return False
        
        # Name exhausted but pattern not
        if ni == name_len:
            # Check if remaining tokens can all match empty
            # Only 'star' can match empty
            for t in range(ti, num_tokens):
                if tokens[t][0] != 'star':
                    memo[(ti, ni)] = False
                    return False
            memo[(ti, ni)] = True
            return True
        
        token = tokens[ti]
        result = False
        
        if token[0] == 'star':
            # * can match zero characters
            if match(ti + 1, ni):
                result = True
            else:
                # * can match one character (not newline) and continue as *
                if name[ni] != '\n':
                    if match(ti, ni + 1):
                        result = True
        elif token[0] == 'question':
            # ? matches exactly one character, not newline
            if name[ni] != '\n':
                if match(ti + 1, ni + 1):
                    result = True
        elif token[0] == 'literal':
            if name[ni] == token[1]:
                if match(ti + 1, ni + 1):
                    result = True
        elif token[0] == 'class':
            negated = token[1]
            items = token[2]
            if char_in_class(name[ni], negated, items):
                if match(ti + 1, ni + 1):
                    result = True
        
        memo[(ti, ni)] = result
        return result
    
    return match(0, 0)
