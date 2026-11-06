def shlex_split(s):
    tokens = []
    current = []
    state = 0  # 0: unquoted, 1: single-quoted, 2: double-quoted
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if state == 0:
            if c in ' \t':
                if current:
                    tokens.append(''.join(current))
                    current = []
                i += 1
            elif c == "'":
                state = 1
                i += 1
            elif c == '"':
                state = 2
                i += 1
            elif c == '\\':
                if i + 1 < n:
                    current.append(s[i + 1])
                    i += 2
                else:
                    current.append(c)
                    i += 1
            else:
                current.append(c)
                i += 1
        elif state == 1:
            if c == "'":
                state = 0
                i += 1
            else:
                current.append(c)
                i += 1
        elif state == 2:
            if c == '\\':
                if i + 1 < n:
                    nxt = s[i + 1]
                    if nxt in ('\\', '"'):
                        current.append(nxt)
                        i += 2
                    else:
                        current.append(c)
                        current.append(nxt)
                        i += 2
                else:
                    current.append(c)
                    i += 1
            elif c == '"':
                state = 0
                i += 1
            else:
                current.append(c)
                i += 1
    if current:
        tokens.append(''.join(current))
    return tokens
