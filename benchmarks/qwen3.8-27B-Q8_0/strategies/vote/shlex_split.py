def shlex_split(s):
    """
    Split a string into a list of tokens, similar to shlex.split(s) in POSIX mode.
    Handles:
    - Whitespace splitting
    - Single quotes (literal content, no escapes)
    - Double quotes (backslash escapes only \, ", $, `; otherwise literal)
    - Backslash escaping outside quotes
    - Adjacent quoted/unquoted runs concatenate into one token
    """
    result = []
    current_token = []
    i = 0
    n = len(s)
    in_token = False  # whether we've started building a current token

    while i < n:
        c = s[i]

        # Skip whitespace (space, tab, newline, etc.) only if not in a token
        if c in (' ', '\t', '\n', '\r', '\f', '\v'):
            if in_token:
                # End of current token
                result.append(''.join(current_token))
                current_token = []
                in_token = False
            i += 1
            continue

        # Backslash outside quotes: escape next character
        if c == '\\':
            if i + 1 < n:
                next_c = s[i + 1]
                # If next is whitespace, it's escaped and becomes literal
                if next_c in (' ', '\t', '\n', '\r', '\f', '\v'):
                    current_token.append(next_c)
                    in_token = True
                else:
                    current_token.append(next_c)
                    in_token = True
                i += 2
            else:
                # Trailing backslash: treat as literal backslash
                current_token.append('\\')
                in_token = True
                i += 1
            continue

        # Single quote: everything until next single quote is literal
        if c == "'":
            in_token = True
            i += 1
            while i < n:
                if s[i] == "'":
                    i += 1
                    break
                current_token.append(s[i])
                i += 1
            continue

        # Double quote: backslash escapes only \, ", $, `
        if c == '"':
            in_token = True
            i += 1
            while i < n:
                if s[i] == '"':
                    i += 1
                    break
                if s[i] == '\\':
                    if i + 1 < n and s[i + 1] in ('\\', '"', '$', '`'):
                        current_token.append(s[i + 1])
                        i += 2
                    else:
                        # Backslash is literal if not escaping one of the special chars
                        current_token.append(s[i])
                        i += 1
                else:
                    current_token.append(s[i])
                    i += 1
            continue

        # Regular character
        current_token.append(c)
        in_token = True
        i += 1

    # Append last token if any
    if in_token and current_token:
        result.append(''.join(current_token))

    return result
