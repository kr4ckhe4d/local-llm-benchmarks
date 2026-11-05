def shlex_split(s):
    tokens = []
    i = 0
    n = len(s)
    current_token = []
    in_token = False

    while i < n:
        c = s[i]

        if c in ' \t\n\r':
            # Whitespace: ends current token
            if in_token:
                tokens.append(''.join(current_token))
                current_token = []
                in_token = False
            i += 1
        elif c == "'":
            # Single quote: everything literal until next single quote
            in_token = True
            i += 1
            while i < n and s[i] != "'":
                current_token.append(s[i])
                i += 1
            if i < n:
                # Skip the closing single quote
                i += 1
            else:
                # Unterminated single quote: raise ValueError like shlex
                raise ValueError("No closing quotation")
        elif c == '"':
            # Double quote: backslash escapes only backslash or double quote
            in_token = True
            i += 1
            while i < n and s[i] != '"':
                if s[i] == '\\' and i + 1 < n and s[i + 1] in ('"', '\\'):
                    current_token.append(s[i + 1])
                    i += 2
                else:
                    current_token.append(s[i])
                    i += 1
            if i < n:
                # Skip the closing double quote
                i += 1
            else:
                # Unterminated double quote: raise ValueError like shlex
                raise ValueError("No closing quotation")
        elif c == '\\':
            # Backslash outside quotes: escapes next character
            in_token = True
            if i + 1 < n:
                current_token.append(s[i + 1])
                i += 2
            else:
                # Trailing backslash: raise ValueError like shlex
                raise ValueError("No escaped character")
        else:
            # Regular character
            in_token = True
            current_token.append(c)
            i += 1

    if in_token:
        tokens.append(''.join(current_token))

    return tokens
