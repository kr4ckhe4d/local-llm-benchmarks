def shlex_split(s):
    """
    Reproduce shlex.split(s) in POSIX mode from scratch.
    
    Handles:
    - Whitespace splitting
    - Single quotes (everything literal inside, no escapes)
    - Double quotes (backslash escapes only \\, \", \$, \` and is otherwise literal)
    - Backslash escaping outside quotes
    - Adjacent quoted and unquoted runs concatenating into ONE token
    """
    tokens = []
    i = 0
    n = len(s)
    
    while i < n:
        # Skip whitespace
        if s[i] in ' \t\n\r':
            i += 1
            continue
        
        # Start building a token
        token = []
        while i < n:
            c = s[i]
            
            # Check for whitespace (end of token)
            if c in ' \t\n\r':
                break
            
            # Single quote
            if c == "'":
                i += 1
                while i < n and s[i] != "'":
                    token.append(s[i])
                    i += 1
                if i < n:
                    i += 1  # skip closing quote
                # else: unterminated quote, just stop
                continue
            
            # Double quote
            if c == '"':
                i += 1
                while i < n and s[i] != '"':
                    c2 = s[i]
                    if c2 == '\\' and i + 1 < n:
                        next_c = s[i + 1]
                        if next_c in ('"', '\\', '$', '`'):
                            token.append(next_c)
                            i += 2
                            continue
                    # Otherwise, literal character
                    token.append(c2)
                    i += 1
                if i < n:
                    i += 1  # skip closing quote
                # else: unterminated quote, just stop
                continue
            
            # Backslash escaping outside quotes
            if c == '\\':
                if i + 1 < n:
                    token.append(s[i + 1])
                    i += 2
                else:
                    # Trailing backslash, ignore
                    i += 1
                continue
            
            # Regular character
            token.append(c)
            i += 1
        
        # Append the token
        tokens.append(''.join(token))
    
    return tokens
