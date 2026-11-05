def shlex_split(s):
    tokens = []
    current = []
    i = 0
    n = len(s)
    
    while i < n:
        c = s[i]
        
        # Skip whitespace outside quotes
        if c in ' \t\n\r':
            if current:
                tokens.append(''.join(current))
                current = []
            i += 1
            continue
        
        # Handle single quotes
        if c == "'":
            i += 1
            while i < n:
                if s[i] == "'":
                    i += 1
                    break
                current.append(s[i])
                i += 1
            else:
                raise ValueError("No closing quotation")
            continue
        
        # Handle double quotes
        if c == '"':
            i += 1
            while i < n:
                if s[i] == '"':
                    i += 1
                    break
                if s[i] == '\\':
                    if i + 1 < n:
                        next_c = s[i + 1]
                        if next_c in ('\\', '"', '$', '`'):
                            current.append(next_c)
                            i += 2
                            continue
                        else:
                            # Backslash is literal if not escaping special char
                            current.append('\\')
                            current.append(next_c)
                            i += 2
                            continue
                    else:
                        raise ValueError("No closing quotation")
                else:
                    current.append(s[i])
                    i += 1
            else:
                raise ValueError("No closing quotation")
            continue
        
        # Handle backslash outside quotes
        if c == '\\':
            if i + 1 < n:
                current.append(s[i + 1])
                i += 2
            else:
                raise ValueError("No closing quotation")
            continue
        
        # Regular character
        current.append(c)
        i += 1
    
    if current:
        tokens.append(''.join(current))
        
    return tokens
