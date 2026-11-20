def shlex_split(s):
    tokens = []
    current_token = []
    state = 'DEFAULT'  # DEFAULT, SINGLE_QUOTE, DOUBLE_QUOTE
    i = 0
    n = len(s)

    while i < n:
        char = s[i]

        if state == 'DEFAULT':
            if char.isspace():
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                i += 1
            elif char == "'":
                state = 'SINGLE_QUOTE'
                i += 1
            elif char == '"':
                state = 'DOUBLE_QUOTE'
                i += 1
            elif char == '\\':
                i += 1
                if i < n:
                    current_token.append(s[i])
                    i += 1
                else:
                    pass # Trailing backslash
            else:
                current_token.append(char)
                i += 1

        elif state == 'SINGLE_QUOTE':
            if char == "'":
                state = 'DEFAULT'
                i += 1
            else:
                current_token.append(char)
                i += 1

        elif state == 'DOUBLE_QUOTE':
            if char == '"':
                state = 'DEFAULT'
                i += 1
            elif char == '\\':
                i += 1
                if i < n:
                    if s[i] in ('"', '\\'):
                        current_token.append(s[i])
                    else:
                        current_token.append('\\')
                        current_token.append(s[i])
                    i += 1
                else:
                    pass
            else:
                current_token.append(char)
                i += 1

    if current_token:
        tokens.append("".join(current_token))
    
    return tokens
