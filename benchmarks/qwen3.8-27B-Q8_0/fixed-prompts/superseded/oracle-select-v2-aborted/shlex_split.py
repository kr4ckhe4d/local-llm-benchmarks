def shlex_split(s):
    """
    Reproduce shlex.split(s) in POSIX mode from scratch.
    
    Handles:
    - Whitespace splitting
    - Single quotes (everything literal inside, no escapes)
    - Double quotes (backslash escapes only backslash or double quote, otherwise literal)
    - Backslash escaping outside quotes
    - Adjacent quoted and unquoted runs concatenating into one token
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
        while i < n and s[i] not in ' \t\n\r':
            c = s[i]
            
            if c == "'":
                # Single quote: everything literal until next single quote
                i += 1
                while i < n and s[i] != "'":
                    token.append(s[i])
                    i += 1
                if i < n:
                    i += 1  # Skip closing single quote
                else:
                    # Unterminated single quote
                    raise ValueError("No closing quotation")
                    
            elif c == '"':
                # Double quote: backslash escapes only backslash or double quote
                i += 1
                while i < n and s[i] != '"':
                    if s[i] == '\\' and i + 1 < n:
                        next_c = s[i + 1]
                        if next_c == '"' or next_c == '\\':
                            token.append(next_c)
                            i += 2
                        else:
                            # Backslash is literal
                            token.append('\\')
                            i += 1
                    else:
                        token.append(s[i])
                        i += 1
                if i < n:
                    i += 1  # Skip closing double quote
                else:
                    # Unterminated double quote
                    raise ValueError("No closing quotation")
                    
            elif c == '\\':
                # Backslash outside quotes: escape next character
                i += 1
                if i < n:
                    token.append(s[i])
                    i += 1
                else:
                    # Trailing backslash
                    raise ValueError("No closing quotation")
                    
            else:
                token.append(c)
                i += 1
        
        tokens.append(''.join(token))
    
    return tokens
