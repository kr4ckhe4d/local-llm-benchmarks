def glob_match(pattern, name):
    def match_here(p_idx, s_idx):
        if p_idx == len(pattern):
            return s_idx == len(name)
        
        p_char = pattern[p_idx]
        
        if p_char == '*':
            # Skip consecutive stars
            while p_idx < len(pattern) and pattern[p_idx] == '*':
                p_idx += 1
            if p_idx == len(pattern):
                return True
            # Try matching rest of pattern at each position in s
            for k in range(s_idx, len(name) + 1):
                if match_here(p_idx, k):
                    return True
            return False
        
        elif p_char == '?':
            if s_idx >= len(name):
                return False
            return match_here(p_idx + 1, s_idx + 1)
        
        elif p_char == '[':
            # Check for negation
            negated = False
            idx = p_idx + 1
            if idx < len(pattern) and pattern[idx] == '!':
                negated = True
                idx += 1
            
            # Check if ] is immediately after [ or [! (literal ])
            if idx < len(pattern) and pattern[idx] == ']':
                # ] is literal, so we need to find the closing ]
                # The set includes the first ] as literal
                literal_close = idx
                idx += 1
                # Now look for the actual closing ]
                while idx < len(pattern) and pattern[idx] != ']':
                    idx += 1
                if idx >= len(pattern):
                    # Unterminated [ - treat [ as literal
                    if s_idx >= len(name) or name[s_idx] != '[':
                        return False
                    return match_here(p_idx + 1, s_idx + 1)
                
                # Build the set of characters
                chars = []
                start = idx  # start of the content (after the literal ])
                # Actually, let me re-think this. The content between [ and ] includes the literal ] and everything up to the closing ]
                # Let me parse properly
                pass
            
            # Let me restructure: parse the bracket expression properly
            idx = p_idx + 1
            negated = False
            if idx < len(pattern) and pattern[idx] == '!':
                negated = True
                idx += 1
            
            # Check if first char in bracket is ]
            if idx < len(pattern) and pattern[idx] == ']':
                # ] is literal, part of the set
                # Find the closing ]
                close_idx = idx + 1
                while close_idx < len(pattern) and pattern[close_idx] != ']':
                    close_idx += 1
                if close_idx >= len(pattern):
                    # Unterminated, treat [ as literal
                    if s_idx >= len(name) or name[s_idx] != '[':
                        return False
                    return match_here(p_idx + 1, s_idx + 1)
                
                # The set content is from idx to close_idx-1
                # Parse the set
                if s_idx >= len(name):
                    return False
                
                ch = name[s_idx]
                matched = parse_bracket_set(pattern, idx, close_idx)
                if negated:
                    matched = not matched
                if not matched:
                    return False
                return match_here(close_idx + 1, s_idx + 1)
            else:
                # Normal case: no literal ] at start
                close_idx = idx
                while close_idx < len(pattern) and pattern[close_idx] != ']':
                    close_idx += 1
                if close_idx >= len(pattern):
                    # Unterminated, treat [ as literal
                    if s_idx >= len(name) or name[s_idx] != '[':
                        return False
                    return match_here(p_idx + 1, s_idx + 1)
                
                if s_idx >= len(name):
                    return False
                
                ch = name[s_idx]
                matched = parse_bracket_set(pattern, idx, close_idx)
                if negated:
                    matched = not matched
                if not matched:
                    return False
                return match_here(close_idx + 1, s_idx + 1)
        
        else:
            if s_idx >= len(name) or name[s_idx] != p_char:
                return False
            return match_here(p_idx + 1, s_idx + 1)
    
    def parse_bracket_set(pattern, start, end):
        """Parse the bracket set content from pattern[start:end] and return a function or set of chars."""
        # Build a set of characters or handle ranges
        chars = set()
        i = start
        while i < end:
            c = pattern[i]
            if c == '\\' and i + 1 < end:
                # Escaped character
                chars.add(pattern[i + 1])
                i += 2
            elif i + 2 < end and pattern[i + 1] == '-':
                # Range
                start_c = c
                end_c = pattern[i + 2]
                for code in range(ord(start_c), ord(end_c) + 1):
                    chars.add(chr(code))
                i += 3
            else:
                chars.add(c)
                i += 1
        return chars
    
    return match_here(0, 0)
