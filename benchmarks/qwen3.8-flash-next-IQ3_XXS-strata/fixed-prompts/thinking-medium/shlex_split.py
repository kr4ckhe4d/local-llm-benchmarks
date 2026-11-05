def shlex_split(s):
    """Reproduce shlex.split(s) in POSIX mode from scratch."""
    whitespace = ' \t\n\r\x0b\x0c'
    result = []
    token = []
    in_token = False
    in_single = False
    in_double = False
    i = 0
    n = len(s)

    while i < n:
        c = s[i]

        if in_single:
            if c == "'":
                in_single = False
            else:
                token.append(c)
            i += 1
            continue

        if in_double:
            if c == '"':
                in_double = False
            elif c == '\\' and i + 1 < n and s[i + 1] in ('"', '\\'):
                token.append(s[i + 1])
                i += 2
            else:
                token.append(c)
                i += 1
            continue

        # Outside any quotes
        if c in whitespace:
            if in_token:
                result.append(''.join(token))
                token = []
                in_token = False
            i += 1
            continue

        if c == '\\':
            if i + 1 < n:
                token.append(s[i + 1])
                in_token = True
                i += 2
            else:
                raise ValueError("No escaped character")
            continue

        if c == "'":
            in_single = True
            in_token = True
            i += 1
            continue

        if c == '"':
            in_double = True
            in_token = True
            i += 1
            continue

        token.append(c)
        in_token = True
        i += 1

    if in_single or in_double:
        raise ValueError("No closing quotation")

    if in_token:
        result.append(''.join(token))

    return result
