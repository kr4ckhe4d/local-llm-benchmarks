def shlex_split(s):
    """
    Reproduce shlex.split(s) in POSIX mode from scratch.
    
    Handles:
    - Whitespace splitting
    - Single quotes: everything literal inside, no escapes
    - Double quotes: backslash escapes only another backslash or a double quote,
      otherwise backslash is literal
    - Backslash escaping outside quotes: backslash escapes the next character
    - Adjacent quoted and unquoted runs concatenate into ONE token
    """
    tokens = []
    i = 0
    n = len(s)
    
    while i < n:
        # Skip whitespace
        if s[i].isspace():
            i += 1
            continue
        
        # Start a new token
        token = []
        in_single_quote = False
        in_double_quote = False
        
        while i < n:
            c = s[i]
            
            if in_single_quote:
                if c == "'":
                    in_single_quote = False
                    i += 1
                else:
                    token.append(c)
                    i += 1
            elif in_double_quote:
                if c == '"':
                    in_double_quote = False
                    i += 1
                elif c == '\\':
                    # In double quotes, backslash escapes only backslash or double quote
                    if i + 1 < n:
                        next_c = s[i + 1]
                        if next_c == '\\':
                            token.append('\\')
                            i += 2
                        elif next_c == '"':
                            token.append('"')
                            i += 2
                        else:
                            # Backslash is literal
                            token.append('\\')
                            i += 1
                    else:
                        # Backslash at end of string inside double quote
                        token.append('\\')
                        i += 1
                else:
                    token.append(c)
                    i += 1
            else:
                # Not in any quote
                if c == "'":
                    in_single_quote = True
                    i += 1
                elif c == '"':
                    in_double_quote = True
                    i += 1
                elif c == '\\':
                    # Outside quotes, backslash escapes the next character
                    if i + 1 < n:
                        token.append(s[i + 1])
                        i += 2
                    else:
                        # Backslash at end of string
                        token.append('\\')
                        i += 1
                elif c.isspace():
                    # End of token
                    break
                else:
                    token.append(c)
                    i += 1
        
        tokens.append(''.join(token))
    
    return tokens
