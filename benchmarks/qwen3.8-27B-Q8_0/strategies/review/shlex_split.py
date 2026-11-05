def shlex_split(s):
    """
    Split a string into a list of tokens, similar to shlex.split(s) in POSIX mode.
    
    Handles:
    - Whitespace splitting
    - Single quotes (everything literal inside, no escapes)
    - Double quotes (backslash escapes only \\, \", $, `; otherwise literal)
    - Backslash escaping outside quotes
    - Adjacent quoted and unquoted runs concatenating into ONE token
    """
    tokens = []
    current_token = []
    i = 0
    n = len(s)
    
    while i < n:
        c = s[i]
        
        # Skip whitespace (only when not in a token)
        if c in ' \t\n\r':
            if current_token:
                tokens.append(''.join(current_token))
                current_token = []
            i += 1
            continue
        
        # Single quote: everything literal until next single quote
        if c == "'":
            i += 1
            while i < n and s[i] != "'":
                current_token.append(s[i])
                i += 1
            if i < n:
                i += 1  # skip closing quote
            # If no closing quote, we've reached end of string
            continue
        
        # Double quote: backslash escapes only \\, \", $, `
        if c == '"':
            i += 1
            while i < n and s[i] != '"':
                if s[i] == '\\' and i + 1 < n:
                    next_c = s[i + 1]
                    if next_c in ('\\', '"', '$', '`'):
                        current_token.append(next_c)
                        i += 2
                    else:
                        # Backslash is literal, append both backslash and next char
                        current_token.append('\\')
                        current_token.append(next_c)
                        i += 2
                else:
                    current_token.append(s[i])
                    i += 1
            if i < n:
                i += 1  # skip closing quote
            continue
        
        # Backslash outside quotes: escape next character
        if c == '\\':
            if i + 1 < n:
                current_token.append(s[i + 1])
                i += 2
            else:
                # Trailing backslash, treat as literal
                current_token.append('\\')
                i += 1
            continue
        
        # Regular character
        current_token.append(c)
        i += 1
    
    # Append last token if any
    if current_token:
        tokens.append(''.join(current_token))
    
    return tokens
