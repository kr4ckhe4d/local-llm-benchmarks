def shlex_split(s):
    tokens = []
    current_token = []
    quote_type = None  # None, "'", or '"'
    i = 0
    n = len(s)

    while i < n:
        c = s[i]

        # Handle whitespace
        if c in ' \t\n\r':
            if quote_type is None:
                if current_token:
                    tokens.append(''.join(current_token))
                    current_token = []
            else:
                current_token.append(c)
            i += 1
            continue

        # Handle quotes
        if c == "'" and quote_type is None:
            quote_type = "'"
            i += 1
            continue
        elif c == '"' and quote_type is None:
            quote_type = '"'
            i += 1
            continue
        elif c == quote_type:
            quote_type = None
            i += 1
            continue

        # Handle backslash escaping
        if c == '\\':
            if quote_type is None:
                # Outside quotes: escape next char
                if i + 1 < n:
                    current_token.append(s[i + 1])
                    i += 2
                    continue
                else:
                    current_token.append(c)
                    i += 1
            elif quote_type == "'":
                # Inside single quotes: backslash is literal
                current_token.append(c)
                i += 1
            else:
                # Inside double quotes: escape only " or \
                if i + 1 < n:
                    next_c = s[i + 1]
                    if next_c in ('"', '\\'):
                        current_token.append(next_c)
                        i += 2
                        continue
                    else:
                        current_token.append(c)
                        i += 1
                else:
                    current_token.append(c)
                    i += 1
        else:
            current_token.append(c)
            i += 1

    # Finalize last token
    if current_token:
        tokens.append(''.join(current_token))

    return tokens
