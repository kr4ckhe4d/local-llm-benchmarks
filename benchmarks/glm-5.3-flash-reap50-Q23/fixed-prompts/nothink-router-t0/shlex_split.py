def shlex_split(s):
    tokens = []
    token = []
    in_double = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if not in_double and c in ' \t\n\r\f\v':
            # whitespace: flush current token
            if token:
                tokens.append(''.join(token))
                token = []
            i += 1
            continue
        if not in_double and c == "'":
            # single quote: everything literal, no escapes
            i += 1
            while i < n and s[i] != "'":
                token.append(s[i])
                i += 1
            i += 1  # skip closing quote (or EOF)
            continue
        if not in_double and c == '"':
            in_double = True
            i += 1
            continue
        if in_double and c == '\\':
            # backslash escapes only another backslash or a double quote
            if i + 1 < n and s[i + 1] in ('\\', '"'):
                token.append(s[i + 1])
                i += 2
            else:
                token.append('\\')
                i += 1
            continue
        if in_double and c == '\\':
            pass
        if not in_double and c == '\\':
            # backslash escaping outside quotes
            if i + 1 < n:
                token.append(s[i + 1])
                i += 2
            else:
                token.append('\\')
                i += 1
            continue
        token.append(c)
        i += 1
    if token:
        tokens.append(''.join(token))
    return tokens


def shlex_split(s):
    tokens = []
    token = []
    in_double = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if not in_double and c in ' \t\n\r\f\v':
            if token:
                tokens.append(''.join(token))
                token = []
            i += 1
            continue
        if not in_double and c == "'":
            i += 1
            while i < n and s[i] != "'":
                token.append(s[i])
                i += 1
            i += 1
            continue
        if c == '"' and (in_double or True):
            # toggle double-quote state (handles both entering and leaving)
            in_double = not in_double
            i += 1
            continue
        if c == '\\':
            if in_double:
                if i + 1 < n and s[i + 1] in ('\\', '"'):
                    token.append(s[i + 1])
                    i += 2
                else:
                    token.append('\\')
                    i += 1
            else:
                if i + 1 < n:
                    token.append(s[i + 1])
                    i += 2
                else:
                    token.append('\\')
                    i += 1
            continue
        token.append(c)
        i += 1
    if token:
        tokens.append(''.join(token))
    return tokens


def shlex_split(s):
    tokens = []
    token = []
    in_double = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if not in_double and c in ' \t\n\r\f\v':
            if token:
                tokens.append(''.join(token))
                token = []
            i += 1
            continue
        if not in_double and c == "'":
            i += 1
            while i < n and s[i] != "'":
                token.append(s[i])
                i += 1
            i += 1
            continue
        if c == '"':
            in_double = not in_double
            i += 1
            continue
        if c == '\\':
            if in_double:
                if i + 1 < n and s[i + 1] in ('\\', '"'):
                    token.append(s[i + 1])
                    i += 2
                else:
                    token.append('\\')
                    i += 1
            else:
                if i + 1 < n:
                    token.append(s[i + 1])
                    i += 2
                else:
                    token.append('\\')
                    i += 1
            continue
        token.append(c)
        i += 1
    if token:
        tokens.append(''.join(token))
    return tokens


def shlex_split(s):
    tokens = []
    token = []
    in_double = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        # Whitespace outside quotes ends the current token
        if not in_double and c in ' \t\n\r\f\v':
            if token:
                tokens.append(''.join(token))
                token = []
            i += 1
            continue
        # Single quote outside quotes: everything literal, no escapes
        if not in_double and c == "'":
            i += 1
            while i < n and s[i] != "'":
                token.append(s[i])
                i += 1
            i += 1  # skip closing quote (or EOF)
            continue
        # Double quote: toggle in/out of double-quoted mode
        if c == '"':
            in_double = not in_double
            i += 1
            continue
        # Backslash handling
        if c == '\\':
            if in_double:
                # Inside double quotes: escapes only backslash or double quote
                if i + 1 < n and s[i + 1] in ('\\', '"'):
                    token.append(s[i + 1])
                    i += 2
                else:
                    token.append('\\')
                    i += 1
            else:
                # Outside quotes: escapes the next character
                if i + 1 < n:
                    token.append(s[i + 1])
                    i += 2
                else:
                    token.append('\\')
                    i += 1
            continue
        token.append(c)
        i += 1
    if token:
        tokens.append(''.join(token))
    return tokens
