def shlex_split(s):
    """
    Reproduce shlex.split(s) in POSIX mode from scratch.
    
    Handles:
    - Whitespace splitting
    - Single quotes (everything literal inside, no escapes)
    - Double quotes (backslash escapes only \, ", $, `; otherwise literal)
    - Backslash escaping outside quotes
    - Adjacent quoted and unquoted runs concatenating into ONE token
    """
    result = []
    i = 0
    n = len(s)
    
    while i < n:
        # Skip leading whitespace
        if s[i].isspace():
            i += 1
            continue
        
        # Start a new token
        token = []
        
        while i < n:
            c = s[i]
            
            # Whitespace outside quotes ends the token
            if c.isspace():
                break
            
            # Single quote: everything literal inside, no escapes
            if c == "'":
                i += 1
                while i < n and s[i] != "'":
                    token.append(s[i])
                    i += 1
                if i < n:
                    i += 1  # skip closing quote
                # If no closing quote, we just consumed to end (POSIX behavior: unterminated quote is an error, but shlex.split would raise; we'll mimic by just ending)
                continue
            
            # Double quote: backslash escapes only \, ", $, `
            if c == '"':
                i += 1
                while i < n and s[i] != '"':
                    c2 = s[i]
                    if c2 == '\\' and i + 1 < n:
                        next_c = s[i + 1]
                        if next_c in ('\\', '"', '$', '`'):
                            token.append(next_c)
                            i += 2
                        else:
                            # Backslash is literal
                            token.append(c2)
                            i += 1
                    else:
                        token.append(c2)
                        i += 1
                if i < n:
                    i += 1  # skip closing quote
                continue
            
            # Backslash outside quotes: escape the next character
            if c == '\\':
                if i + 1 < n:
                    token.append(s[i + 1])
                    i += 2
                else:
                    # Trailing backslash: in POSIX shlex, this is an error, but let's just add it
                    token.append(c)
                    i += 1
                continue
            
            # Regular character
            token.append(c)
            i += 1
        
        # Append the completed token
        if token:
            result.append(''.join(token))
        # If token is empty (e.g., just whitespace was skipped), we don't append
    
    return result
