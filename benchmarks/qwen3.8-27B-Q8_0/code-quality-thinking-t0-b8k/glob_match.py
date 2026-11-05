def glob_match(pattern, name):
    def parse_class(start, end, negated):
        items = []
        length = end - start
        for offset in range(length):
            ch = pattern[start + offset]
            if ch == "-":
                if offset == 0 or offset == length - 1:
                    items.append((ch, ch))
                else:
                    left = pattern[start + offset - 1]
                    right = pattern[start + offset + 1]
                    if ord(left) <= ord(right):
                        items.append((left, right))
                    else:
                        items.append((ch, ch))
            else:
                items.append((ch, ch))
        return negated, items

    tokens = []
    i = 0
    n = len(pattern)

    while i < n:
        c = pattern[i]

        if c == "*":
            while i < n and pattern[i] == "*":
                i += 1
            tokens.append(("star",))

        elif c == "?":
            tokens.append(("question",))
            i += 1

        elif c == "[":
            j = i + 1
            negated = False

            if j < n and pattern[j] == "!":
                negated = True
                j += 1

            if j < n and pattern[j] == "]":
                j += 1

            while j < n and pattern[j] != "]":
                j += 1

            if j >= n:
                tokens.append(("literal", "["))
                i += 1
            else:
                start = i + 1
                if negated:
                    start += 1
                tokens.append(("class",) + parse_class(start, j, negated))
                i = j + 1

        else:
            tokens.append(("literal", c))
            i += 1

    m = len(name)
    t = len(tokens)
    dp = [[False] * (m + 1) for _ in range(t + 1)]
    dp[0][0] = True

    for pi in range(t):
        if tokens[pi][0] == "star":
            for ni in range(m + 1):
                dp[pi + 1][ni] = dp[pi][ni] or dp[pi + 1][ni - 1] if ni else dp[pi][ni]

    for pi in range(t):
        token = tokens[pi]
        kind = token[0]

        for ni in range(1, m + 1):
            ch = name[ni - 1]

            if kind == "literal":
                dp[pi + 1][ni] = dp[pi][ni - 1] and ch == token[1]

            elif kind == "question":
                dp[pi + 1][ni] = dp[pi][ni - 1] and ch != "\n"

            elif kind == "class":
                negated = token[1]
                items = token[2]
                code = ord(ch)
                matched = any(
                    ord(a) <= code <= ord(b)
                    for a, b in items
                )
                dp[pi + 1][ni] = dp[pi][ni - 1] and (not matched if negated else matched)

            elif kind == "star":
                dp[pi + 1][ni] = dp[pi][ni] or dp[pi + 1][ni - 1]

    return dp[t][m]
