def shlex_split(s):
    tokens = []
    token = []
    in_single = False
    in_double = False
    i = 0
    n = len(s)
    has_token = False  # whether we have started accumulating a current token

    while i < n:
        c = s[i]

        if in_single:
            if c == "'":
                in_single = False
                has_token = True
                i += 1
            else:
                token.append(c)
                has_token = True
                i += 1
        elif in_double:
            if c == '"':
                in_double = False
                has_token = True
                i += 1
            elif c == '\\':
                # Backslash in double quotes: escapes only \, ", $, `
                if i + 1 < n:
                    next_c = s[i + 1]
                    if next_c in ('\\', '"', '$', '`'):
                        token.append(next_c)
                        has_token = True
                        i += 2
                    else:
                        # Backslash is literal
                        token.append('\\')
                        has_token = True
                        i += 1
                else:
                    # Trailing backslash
                    token.append('\\')
                    has_token = True
                    i += 1
            else:
                token.append(c)
                has_token = True
                i += 1
        else:
            # Not in quotes
            if c in (' ', '\t', '\n', '\r'):
                if has_token:
                    tokens.append(''.join(token))
                    token = []
                    has_token = False
                i += 1
            elif c == "'":
                in_single = True
                has_token = True
                i += 1
            elif c == '"':
                in_double = True
                has_token = True
                i += 1
            elif c == '\\':
                if i + 1 < n:
                    next_c = s[i + 1]
                    # In POSIX mode, backslash escapes any character except newline
                    if next_c != '\n':
                        token.append(next_c)
                        has_token = True
                        i += 2
                    else:
                        # Backslash followed by newline is line continuation; skip both
                        i += 2
                else:
                    # Trailing backslash: in POSIX mode, this is an error, but we can just append it
                    token.append('\\')
                    has_token = True
                    i += 1
            else:
                token.append(c)
                has_token = True
                i += 1

    if has_token:
        tokens.append(''.join(token))

    return tokens
