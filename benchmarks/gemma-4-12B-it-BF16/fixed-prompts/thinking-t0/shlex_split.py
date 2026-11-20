def shlex_split(s):
    tokens = []
    current_token = ""
    in_single_quote = False
    in_double_quote = False
    i = 0
    n = len(s)

    while i < n:
        char = s[i]

        if in_single_quote:
            if char == "'":
                in_single_quote = False
            else:
                current_token += char
            i += 1
        elif in_double_quote:
            if char == '"':
                in_double_quote = False
                i += 1
            elif char == '\\':
                if i + 1 < n and s[i + 1] in ('\\', '"'):
                    current_token += s[i + 1]
                    i += 2
                else:
                    current_token += '\\'
                    i += 1
            else:
                current_token += char
                i += 1
        else:
            if char.isspace():
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                i += 1
            elif char == "'":
                in_single_quote = True
                i += 1
            elif char == '"':
                in_double_quote = True
                i += 1
            elif char == '\\':
                if i + 1 < n:
                    current_token += s[i + 1]
                    i += 2
                else:
                    current_token += '\\'
                    i += 1
            else:
                current_token += char
                i += 1

    if current_token:
        tokens.append(current_token)

    return tokens
