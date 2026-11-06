def glob_match(pattern, name):
    """
    Implement fnmatch.fnmatchcase semantics from scratch.
    Supports *, ?, [abc], [a-z], [!abc].
    ] immediately after [ or [! is literal.
    Unterminated [ is literal [.
    Match is anchored to the whole string.
    """
    def match(pat_idx, str_idx):
        # If pattern is exhausted, string must also be exhausted
        if pat_idx == len(pattern):
            return str_idx == len(name)

        ch = pattern[pat_idx]

        if ch == '*':
            # '*' matches any sequence including empty
            # Try matching zero characters, then one, two, etc.
            for i in range(str_idx, len(name) + 1):
                if match(pat_idx + 1, i):
                    return True
            return False

        elif ch == '?':
            # '?' matches exactly one character
            if str_idx < len(name):
                return match(pat_idx + 1, str_idx + 1)
            return False

        elif ch == '[':
            # Parse bracket expression
            bracket_start = pat_idx
            pat_idx += 1  # skip '['

            # Check for negation
            negated = False
            if pat_idx < len(pattern) and pattern[pat_idx] == '!':
                negated = True
                pat_idx += 1

            # Collect characters in the bracket set
            # A ']' immediately after '[' or '[!' is a literal ']'
            chars = []
            ranges = []

            # First character: if it's ']', it's literal
            if pat_idx < len(pattern) and pattern[pat_idx] == ']':
                chars.append(']')
                pat_idx += 1

            # Now parse until we find the closing ']'
            found_closing = False
            while pat_idx < len(pattern):
                if pattern[pat_idx] == ']':
                    found_closing = True
                    pat_idx += 1  # skip ']'
                    break

                # Check for range: e.g., a-z
                if (pat_idx + 2 < len(pattern) and
                    pattern[pat_idx + 1] == '-' and
                    pattern[pat_idx + 2] != ']' and
                    pattern[pat_idx + 2] != '\\'):
                    # It's a range
                    start_char = pattern[pat_idx]
                    end_char = pattern[pat_idx + 2]
                    ranges.append((start_char, end_char))
                    pat_idx += 3  # skip start, '-', end
                else:
                    chars.append(pattern[pat_idx])
                    pat_idx += 1

            if not found_closing:
                # Unterminated '[': treat '[' as literal
                # Revert: the '[' at bracket_start is literal, so match it literally
                if str_idx < len(name) and name[str_idx] == '[':
                    return match(bracket_start + 1, str_idx + 1)
                return False

            # Check if current character in name matches the bracket expression
            if str_idx < len(name):
                current_char = name[str_idx]
                in_set = False

                for c in chars:
                    if current_char == c:
                        in_set = True
                        break

                if not in_set:
                    for start, end in ranges:
                        if start <= current_char <= end:
                            in_set = True
                            break

                if negated:
                    in_set = not in_set

                if in_set:
                    return match(pat_idx, str_idx + 1)

            return False

        else:
            # Literal character
            if str_idx < len(name) and name[str_idx] == ch:
                return match(pat_idx + 1, str_idx + 1)
            return False

    return match(0, 0)
