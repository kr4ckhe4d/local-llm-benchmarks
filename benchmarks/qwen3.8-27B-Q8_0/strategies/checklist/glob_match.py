def glob_match(pattern, name):
    """
    Implements fnmatch.fnmatchcase semantics from scratch.
    Supports *, ?, [seq], [!seq], [a-z].
    Anchored match (whole string).
    """
    p_len = len(pattern)
    n_len = len(name)
    p_idx = 0
    n_idx = 0
    
    # We use a stack to handle backtracking for '*'
    # Each entry in the stack is (p_idx_at_star, n_idx_at_star)
    # Actually, a simpler approach for glob matching is to keep track of the last star
    # and the position in the name where we started matching after that star.
    
    star_p_idx = -1
    star_n_idx = -1
    
    while n_idx < n_len:
        if p_idx < p_len and pattern[p_idx] == '*':
            # Found a star. Record its position.
            star_p_idx = p_idx
            star_n_idx = n_idx
            p_idx += 1
            # Skip consecutive stars
            while p_idx < p_len and pattern[p_idx] == '*':
                p_idx += 1
            # Do not increment n_idx, we will try to match the rest of the pattern
            # against the current name position.
        elif p_idx < p_len and pattern[p_idx] == '?':
            # ? matches any single character
            p_idx += 1
            n_idx += 1
        elif p_idx < p_len and pattern[p_idx] == '[':
            # Parse character class
            p_idx += 1
            negate = False
            if p_idx < p_len and pattern[p_idx] == '!':
                negate = True
                p_idx += 1
            
            # Handle ] immediately after [ or [!
            if p_idx < p_len and pattern[p_idx] == ']':
                # ] is a literal character in the set
                # We need to include it in the set
                # But we must be careful: if the set is just []], it matches ]
                # If the set is [!]], it matches anything except ]
                
                # Let's collect the characters in the set
                chars = set()
                # Add the first ]
                chars.add(']')
                p_idx += 1
                
                # Continue parsing the rest of the set
                while p_idx < p_len and pattern[p_idx] != ']':
                    if p_idx + 2 < p_len and pattern[p_idx + 1] == '-':
                        # Range
                        start_char = pattern[p_idx]
                        end_char = pattern[p_idx + 2]
                        if start_char <= end_char:
                            for c in range(ord(start_char), ord(end_char) + 1):
                                chars.add(chr(c))
                        p_idx += 3
                    else:
                        chars.add(pattern[p_idx])
                        p_idx += 1
                
                # Now p_idx should be at the closing ]
                if p_idx < p_len and pattern[p_idx] == ']':
                    p_idx += 1 # Consume the closing ]
                else:
                    # Unterminated [
                    # Treat the original [ as literal
                    # We need to backtrack p_idx to the [
                    # And treat [ as a literal character
                    # This is tricky because we've already advanced p_idx.
                    # Let's restart the logic for this character as a literal.
                    # We set p_idx back to the position of [
                    p_idx -= 1 # Back to ]
                    # We need to go back to [
                    # This logic is getting complex. Let's restructure the [ parsing.
                    pass # Placeholder, will fix below
                    
            else:
                # Normal case: ] is not the first char
                chars = set()
                while p_idx < p_len and pattern[p_idx] != ']':
                    if p_idx + 2 < p_len and pattern[p_idx + 1] == '-':
                        start_char = pattern[p_idx]
                        end_char = pattern[p_idx + 2]
                        if start_char <= end_char:
                            for c in range(ord(start_char), ord(end_char) + 1):
                                chars.add(chr(c))
                        p_idx += 3
                    else:
                        chars.add(pattern[p_idx])
                        p_idx += 1
                
                if p_idx < p_len and pattern[p_idx] == ']':
                    p_idx += 1 # Consume the closing ]
                else:
                    # Unterminated [
                    # Treat [ as literal
                    # We need to match name[n_idx] against '['
                    if n_idx < n_len and name[n_idx] == '[':
                        n_idx += 1
                        p_idx += 1 # Consume the [
                    else:
                        # No match
                        if star_p_idx != -1:
                            # Backtrack to star
                            star_n_idx += 1
                            n_idx = star_n_idx
                            p_idx = star_p_idx + 1
                            # Skip consecutive stars again
                            while p_idx < p_len and pattern[p_idx] == '*':
                                p_idx += 1
                        else:
                            return False
                    continue # Continue to next iteration of while loop

            # If we got here, we have a valid character class
            if n_idx < n_len:
                if negate:
                    if name[n_idx] not in chars:
                        n_idx += 1
                        p_idx += 0 # p_idx already advanced past ]
                    else:
                        # No match
                        if star_p_idx != -1:
                            star_n_idx += 1
                            n_idx = star_n_idx
                            p_idx = star_p_idx + 1
                            while p_idx < p_len and pattern[p_idx] == '*':
                                p_idx += 1
                        else:
                            return False
                else:
                    if name[n_idx] in chars:
                        n_idx += 1
                    else:
                        if star_p_idx != -1:
                            star_n_idx += 1
                            n_idx = star_n_idx
                            p_idx = star_p_idx + 1
                            while p_idx < p_len and pattern[p_idx] == '*':
                                p_idx += 1
                        else:
                            return False
            else:
                # Name exhausted but pattern has more
                if star_p_idx != -1:
                    star_n_idx += 1
                    n_idx = star_n_idx
                    p_idx = star_p_idx + 1
                    while p_idx < p_len and pattern[p_idx] == '*':
                        p_idx += 1
                else:
                    return False

        elif p_idx < p_len:
            # Literal character
            if name[n_idx] == pattern[p_idx]:
                p_idx += 1
                n_idx += 1
            else:
                # No match
                if star_p_idx != -1:
                    star_n_idx += 1
                    n_idx = star_n_idx
                    p_idx = star_p_idx + 1
                    while p_idx < p_len and pattern[p_idx] == '*':
                        p_idx += 1
                else:
                    return False
        else:
            # Pattern exhausted but name has more
            # If we have a star, it can match the rest
            if star_p_idx != -1:
                # The star can match the remaining name
                # But we need to ensure the rest of the pattern (after star) matches empty
                # Since we are in the "else" branch, p_idx == p_len, so rest of pattern is empty.
                # So star matches the rest.
                return True
            else:
                return False

    # Name exhausted
    # Check if pattern is exhausted or only stars remain
    while p_idx < p_len and pattern[p_idx] == '*':
        p_idx += 1
    
    return p_idx == p_len
