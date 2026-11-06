def glob_match(pattern, name):
    n = len(name)
    m = len(pattern)

    def class_matches(ch, negated, items):
        ok = False
        for item in items:
            if isinstance(item, tuple):
                lo, hi = item
                if lo <= ch <= hi:
                    ok = True
                    break
            elif item == ch:
                ok = True
                break
        return (not ok) if negated else ok

    def match(i, j):
        if i == m:
            return j == n
        c = pattern[i]

        if c == '*':
            i2 = i
            while i2 < m and pattern[i2] == '*':
                i2 += 1
            if i2 == m:
                return True
            for k in range(j, n + 1):
                if match(i2, k):
                    return True
            return False

        if j == n:
            return False

        if c == '?':
            return match(i + 1, j + 1)

        if c == '[':
            i2 = i + 1
            negated = False
            if i2 < m and pattern[i2] == '!':
                negated = True
                i2 += 1
            if i2 < m and pattern[i2] == ']':
                items = [']']
                i2 += 1
            else:
                items = []
            closed = False
            while i2 < m and pattern[i2] != ']':
                ch = pattern[i2]
                if (
                    i2 + 2 < m
                    and pattern[i2 + 1] == '-'
                    and pattern[i2 + 2] != ']'
                ):
                    items.append((ch, pattern[i2 + 2]))
                    i2 += 3
                else:
                    items.append(ch)
                    i2 += 1
            if i2 < m:
                closed = True
                i2 += 1

            if not closed:
                return match(i + 1, j + 1) if name[j] == '[' else False

            return match(i2, j + 1) if class_matches(name[j], negated, items) else False

        return match(i + 1, j + 1) if name[j] == c else False

    return match(0, 0)
