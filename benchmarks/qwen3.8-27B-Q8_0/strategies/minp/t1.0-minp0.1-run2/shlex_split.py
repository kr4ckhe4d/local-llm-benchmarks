def shlex_split(s):
    """
    Reproduce shlex.split(s) in POSIX mode from scratch.
    Handles: whitespace splitting; single quotes (literal inside);
    double quotes (backslash escapes only \\, \", $, `);
    backslash escaping outside quotes; adjacent runs concatenate into one token.
    """
    result = []
    i = 0
    n = len(s)
    token = []
    in_token = False
    
    while i < n:
        c = s[i]
        
        # Whitespace outside quotes
        if c in ' \t\n\r':
            if in_token:
                result.append(''.join(token))
                token = []
                in_token = False
            i += 1
            continue
        
        # Single quote: everything literal inside until next single quote
        if c == "'":
            in_token = True
            i += 1
            while i < n:
                if s[i] == "'":
                    i += 1
                    break
                token.append(s[i])
                i += 1
            continue
        
        # Double quote: backslash escapes only \\, \", $, `; otherwise backslash is literal
        if c == '"':
            in_token = True
            i += 1
            while i < n:
                if s[i] == '"':
                    i += 1
                    break
                if s[i] == '\\':
                    # Check if next char is one of the escapable chars
                    if i + 1 < n and s[i + 1] in ('\\', '"', '$', '`'):
                        token.append(s[i + 1])
                        i += 2
                    else:
                        # Backslash is literal
                        token.append('\\')
                        i += 1
                else:
                    token.append(s[i])
                    i += 1
            continue
        
        # Backslash outside quotes: escapes the next character
        if c == '\\':
            if i + 1 < n:
                in_token = True
                token.append(s[i + 1])
                i += 2
            else:
                # Trailing backslash, treat as literal
                in_token = True
                token.append('\\')
                i += 1
            continue
        
        # Regular character
        in_token = True
        token.append(c)
        i += 1
    
    if in_token:
        result.append(''.join(token))
    
    return result
