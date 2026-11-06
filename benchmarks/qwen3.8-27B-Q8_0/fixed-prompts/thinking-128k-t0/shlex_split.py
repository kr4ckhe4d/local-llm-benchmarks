def shlex_split(s):
    tokens = []
    token = []
    in_token = False
    i = 0
    n = len(s)

    while i < n:
        c = s[i]

        if c.isspace():
            if in_token:
                tokens.append("".join(token))
                token = []
                in_token = False
            i += 1
            continue

        if c == "\\":
            if i + 1 < n:
                token.append(s[i + 1])
                in_token = True
                i += 2
            else:
                token.append("\\")
                in_token = True
                i += 1
            continue

        if c == "'":
            in_token = True
            i += 1
            while i < n:
                c = s[i]
                if c == "'":
                    i += 1
                    break
                token.append(c)
                i += 1
            else:
                raise ValueError("No closing quotation")
            continue

        if c == '"':
            in_token = True
            i += 1
            while i < n:
                c = s[i]
                if c == '"':
                    i += 1
                    break
                if c == "\\":
                    if i + 1 < n and s[i + 1] in ('"', "\\"):
                        token.append(s[i + 1])
                        i += 2
                    else:
                        token.append(c)
                        i += 1
                else:
                    token.append(c)
                    i += 1
            else:
                raise ValueError("No closing quotation")
            continue

        token.append(c)
        in_token = True
        i += 1

    if in_token:
        tokens.append("".join(token))

    return tokens
