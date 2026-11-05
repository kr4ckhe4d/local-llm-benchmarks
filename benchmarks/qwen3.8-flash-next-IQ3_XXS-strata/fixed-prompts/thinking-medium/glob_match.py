def glob_match(pattern, name):
    def _match(pi, ni):
        while pi < len(pattern):
            c = pattern[pi]
            if c == '*':
                while pi + 1 < len(pattern) and pattern[pi + 1] == '*':
                    pi += 1
                if pi + 1 >= len(pattern):
                    return True
                for i in range(ni, len(name) + 1):
                    if _match(pi + 1, i):
                        return True
                return False
            elif c == '?':
                if ni >= len(name):
                    return False
                pi += 1
                ni += 1
            elif c == '[':
                pi_save = pi
                pi += 1
                negated = False
                if pi < len(pattern) and pattern[pi] == '!':
                    negated = True
                    pi += 1
                first = True
                if pi < len(pattern) and pattern[pi] == ']':
                    pi += 1
                    first = False
                matched_char = False
                terminated = False
                while pi < len(pattern):
                    if pattern[pi] == ']' and not first:
                        terminated = True
                        pi += 1
                        break
                    first = False
                    if pattern[pi] == '\\':
                        pi += 1
                        if pi >= len(pattern):
                            break
                        if ni < len(name) and name[ni] == pattern[pi]:
                            matched_char = True
                        pi += 1
                    elif (pi + 2 < len(pattern) and
                          pattern[pi + 1] == '-' and
                          pattern[pi + 2] != ']'):
                        lo = pattern[pi]
                        hi = pattern[pi + 2]
                        if ni < len(name) and lo <= name[ni] <= hi:
                            matched_char = True
                        pi += 3
                    else:
                        if ni < len(name) and name[ni] == pattern[pi]:
                            matched_char = True
                        pi += 1
                if not terminated:
                    if ni >= len(name) or name[ni] != '[':
                        return False
                    pi = pi_save + 1
                    ni += 1
                    continue
                if negated:
                    matched_char = not matched_char
                if not matched_char:
                    return False
                ni += 1
            elif c == '\\':
                pi += 1
                if pi >= len(pattern):
                    if ni >= len(name) or name[ni] != '\\':
                        return False
                    ni += 1
                else:
                    if ni >= len(name) or name[ni] != pattern[pi]:
                        return False
                    pi += 1
                    ni += 1
            else:
                if ni >= len(name) or name[ni] != c:
                    return False
                pi += 1
                ni += 1
        return ni >= len(name)
    return _match(0, 0)
