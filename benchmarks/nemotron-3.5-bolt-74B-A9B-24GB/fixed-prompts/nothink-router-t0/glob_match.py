def glob_match(pattern, name):
    def parse_class(p, i):
        if i >= len(p) or p[i] != '[':
            return None, i
        j = i + 1
        if j < len(p) and p[j] in ('!', '^'):
            neg = True
            j += 1
        else:
            neg = False
        if j < len(p) and p[j] == ']':
            chars = {']'}
            j += 1
        else:
            chars = set()
            while j < len(p) and p[j] != ']':
                if p[j] == '\\' and j + 1 < len(p):
                    chars.add(p[j + 1])
                    j += 2
                else:
                    chars.add(p[j])
                    j += 1
            if j >= len(p):
                return None, i
            j += 1
        return (neg, chars), j

    def match(p, pi, n, ni):
        if pi == len(p):
            return ni == len(n)
        if p[pi] == '*':
            for k in range(ni, len(n) + 1):
                if match(p, pi + 1, n, k):
                    return True
            return False
        if p[pi] == '?':
            if ni < len(n):
                return match(p, pi + 1, n, ni + 1)
            return False
        if p[pi] == '[':
            cls, nxt = parse_class(p, pi)
            if cls is None:
                if ni < len(n) and p[pi] == n[ni]:
                    return match(p, pi + 1, n, ni + 1)
                return False
            neg, chars = cls
            if ni >= len(n):
                return False
            c = n[ni]
            if (c in chars) == neg:
                return match(p, nxt, n, ni + 1)
            return False
        if ni < len(n) and p[pi] == n[ni]:
            return match(p, pi + 1, n, ni + 1)
        return False

    return match(pattern, 0, name, 0)
