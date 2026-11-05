def shlex_split(s):
    """
    Split a string using POSIX shell-like syntax.
    Handles:
    - Whitespace splitting
    - Single quotes (everything literal, no escapes)
    - Double quotes (backslash escapes only backslash or double quote, otherwise literal)
    - Backslash escaping outside quotes
    - Adjacent quoted and unquoted runs concatenate into one token
    """
    tokens = []
    current_token = []
    i = 0
    n = len(s)
    in_single_quote = False
    in_double_quote = False
    token_started = False

    while i < n:
        c = s[i]

        if in_single_quote:
            if c == "'":
                in_single_quote = False
                i += 1
            else:
                current_token.append(c)
                i += 1
        elif in_double_quote:
            if c == '\\':
                if i + 1 < n:
                    next_c = s[i + 1]
                    if next_c == '\\' or next_c == '"':
                        current_token.append(next_c)
                        i += 2
                    else:
                        current_token.append(c)
                        i += 1
                else:
                    current_token.append(c)
                    i += 1
            elif c == '"':
                in_double_quote = False
                i += 1
            else:
                current_token.append(c)
                i += 1
        else:
            if c == "'":
                in_single_quote = True
                token_started = True
                i += 1
            elif c == '"':
                in_double_quote = True
                token_started = True
                i += 1
            elif c == '\\':
                if i + 1 < n:
                    next_c = s[i + 1]
                    current_token.append(next_c)
                    token_started = True
                    i += 2
                else:
                    raise ValueError("No closing quotation")
            elif c.isspace():
                if token_started:
                    tokens.append(''.join(current_token))
                    current_token = []
                    token_started = False
                i += 1
            else:
                current_token.append(c)
                token_started = True
                i += 1

    if in_single_quote or in_double_quote:
        raise ValueError("No closing quotation")

    if token_started:
        tokens.append(''.join(current_token))

    return tokens
