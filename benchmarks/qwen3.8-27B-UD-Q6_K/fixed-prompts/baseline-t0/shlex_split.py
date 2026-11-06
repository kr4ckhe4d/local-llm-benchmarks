def shlex_split(s):
    tokens = []
    i = 0
    n = len(s)
    while i < n:
        # Skip whitespace
        if s[i].isspace():
            i += 1
            continue
        
        # Start building a token
        token = []
        while i < n:
            c = s[i]
            if c.isspace():
                break
            elif c == "'":
                # Single quote: everything literal until next single quote
                i += 1
                while i < n and s[i] != "'":
                    token.append(s[i])
                    i += 1
                if i < n:
                    i += 1  # skip closing quote
                # else: unterminated quote, just stop
            elif c == '"':
                # Double quote: backslash escapes only backslash or double quote
                i += 1
                while i < n and s[i] != '"':
                    if s[i] == '\\' and i + 1 < n and s[i + 1] in ('\\', '"'):
                        token.append(s[i + 1])
                        i += 2
                    else:
                        token.append(s[i])
                        i += 1
                if i < n:
                    i += 1  # skip closing quote
            elif c == '\\':
                # Backslash outside quotes: escape next character
                if i + 1 < n:
                    token.append(s[i + 1])
                    i += 2
                else:
                    # Trailing backslash, ignore or treat as literal? shlex would error, but let's just skip
                    i += 1
            else:
                token.append(c)
                i += 1
        
        tokens.append(''.join(token))
    
    return tokens
