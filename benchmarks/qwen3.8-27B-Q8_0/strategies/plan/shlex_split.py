def shlex_split(s):
    words = []
    i = 0
    n = len(s)
    whitespace = {' ', '\t', '\r', '\n'}
    
    while i < n:
        # Skip unquoted whitespace
        while i < n and s[i] in whitespace:
            i += 1
        if i >= n:
            break
        
        current = []
        seen = False
        
        while i < n:
            c = s[i]
            
            if c in whitespace:
                break
            
            elif c == "'":
                # Single-quoted run: everything literal until next single quote
                i += 1
                start = i
                while i < n and s[i] != "'":
                    i += 1
                if i >= n:
                    raise ValueError("No closing quotation")
                current.append(s[start:i])
                i += 1  # skip closing quote
                seen = True
            
            elif c == '"':
                # Double-quoted run with restricted backslash escaping
                i += 1
                buf = []
                while i < n:
                    c2 = s[i]
                    if c2 == '"':
                        i += 1
                        break
                    elif c2 == '\\':
                        if i + 1 < n:
                            nxt = s[i + 1]
                            if nxt in ('\\', '"', '$', '`'):
                                buf.append(nxt)
                                i += 2
                            else:
                                buf.append('\\')
                                buf.append(nxt)
                                i += 2
                        else:
                            # Backslash at end of input inside double quotes
                            buf.append('\\')
                            i += 1
                            # This is actually an unterminated quote scenario? 
                            # No, the backslash is literal here per spec: "A backslash immediately before the closing double quote is literal"
                            # But if it's at end of input, there's no closing quote.
                            # Actually, if we're at end of input and see a backslash, we append it and then the loop continues,
                            # but i >= n so we exit the while loop without finding closing quote.
                            # We need to check for closing quote after the loop.
                            pass
                    else:
                        buf.append(c2)
                        i += 1
                else:
                    # Loop ended because i >= n, meaning no closing double quote found
                    raise ValueError("No closing quotation")
                current.append(''.join(buf))
                seen = True
            
            elif c == '\\':
                # Backslash escaping outside quotes
                if i + 1 >= n:
                    raise ValueError("No escaped character")
                current.append(s[i + 1])
                i += 2
                seen = True
            
            else:
                current.append(c)
                i += 1
                seen = True
        
        if seen:
            words.append(''.join(current))
    
    return words
