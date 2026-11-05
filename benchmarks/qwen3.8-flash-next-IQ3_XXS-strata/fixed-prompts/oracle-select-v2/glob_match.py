def glob_match(pattern, name):
    """
    Implement fnmatch.fnmatchcase semantics from scratch.
    Supports *, ?, [abc], [a-z], [!abc], [!]abc] (literal ] after [ or [!),
    and unterminated [ as literal [.
    Match is anchored to the whole string.
    """
    def match_pattern(pat, pat_idx, s, s_idx):
        """
        Match pattern[pat_idx:] against s[s_idx:].
        Returns True if the entire remaining pattern matches the entire remaining string.
        """
        while pat_idx < len(pat):
            c = pat[pat_idx]
            
            if c == '*':
                # Skip consecutive *'s
                while pat_idx + 1 < len(pat) and pat[pat_idx + 1] == '*':
                    pat_idx += 1
                # If * is at end, match rest of string
                if pat_idx + 1 >= len(pat):
                    return True
                # Try matching rest of pattern against every suffix of s
                for k in range(len(s) - s_idx + 1):
                    if match_pattern(pat, pat_idx + 1, s, s_idx + k):
                        return True
                return False
            
            elif c == '?':
                if s_idx >= len(s):
                    return False
                pat_idx += 1
                s_idx += 1
            
            elif c == '[':
                # Parse character class
                pat_idx += 1
                negate = False
                if pat_idx < len(pat) and pat[pat_idx] == '!':
                    negate = True
                    pat_idx += 1
                
                # Build the character class
                chars = set()
                first = True
                while pat_idx < len(pat):
                    ch = pat[pat_idx]
                    
                    # Check for closing ]
                    # A ] immediately after [ or [! is literal
                    if ch == ']' and not first:
                        pat_idx += 1
                        break
                    
                    # Handle ranges [a-z]
                    if pat_idx + 2 < len(pat) and pat[pat_idx + 1] == '-' and pat[pat_idx + 2] != ']':
                        start = pat[pat_idx]
                        end = pat[pat_idx + 2]
                        if start <= end:
                            for ord_c in range(ord(start), ord(end) + 1):
                                chars.add(chr(ord_c))
                        pat_idx += 3
                    else:
                        chars.add(ch)
                        pat_idx += 1
                    
                    first = False
                
                # Check if we found a closing ]
                # If the bracket was unterminated (we reached end of pattern without closing ]),
                # then [ is literal.
                if pat_idx >= len(pat) and not (pat_idx > 0 and pat[pat_idx - 1] == ']'):
                    # Unterminated bracket: treat [ as literal
                    # But we already consumed [. We need to backtrack.
                    # Actually, let's reconsider: the while loop above breaks on ] or reaches end.
                    # If we reach end of pattern without seeing ], it's unterminated.
                    # In that case, [ should be literal.
                    # But we've already advanced past [. Let's handle this differently.
                    pass
                
                # Hmm, let me redo the bracket parsing more carefully.
                # Actually, the approach above has issues with detecting unterminated brackets.
                # Let me rewrite.
                
                # Reset: we need to properly detect if the bracket is terminated.
                # Let me restart the bracket parsing logic.
                pass
            
            else:
                if s_idx >= len(s) or s[s_idx] != c:
                    return False
                pat_idx += 1
                s_idx += 1
        
        return s_idx >= len(s)
    
    # Let me rewrite with a cleaner implementation using recursion and proper bracket parsing
    
    def match(pat_idx, s_idx):
        """Match pattern[pat_idx:] against s[s_idx:]"""
        n_pat = len(pattern)
        n_s = len(name)
        
        while pat_idx < n_pat:
            c = pattern[pat_idx]
            
            if c == '*':
                # Collapse consecutive *
                while pat_idx + 1 < n_pat and pattern[pat_idx + 1] == '*':
                    pat_idx += 1
                
                if pat_idx + 1 >= n_pat:
                    return True
                
                # Try every possible split
                for k in range(n_s - s_idx + 1):
                    if match(pat_idx + 1, s_idx + k):
                        return True
                return False
            
            elif c == '?':
                if s_idx >= n_s:
                    return False
                pat_idx += 1
                s_idx += 1
            
            elif c == '[':
                # Parse character class starting at pat_idx
                start_pat = pat_idx
                pat_idx += 1  # skip [
                
                negate = False
                if pat_idx < n_pat and pattern[pat_idx] == '!':
                    negate = True
                    pat_idx += 1
                
                chars = set()
                first_char = True
                
                while pat_idx < n_pat:
                    ch = pattern[pat_idx]
                    
                    # A ] is the closing bracket unless it's the first char after [ or [!
                    if ch == ']' and not first_char:
                        pat_idx += 1  # skip ]
                        # Bracket is properly terminated
                        break
                    
                    # Check for range: ch - next_ch
                    if pat_idx + 2 < n_pat and pattern[pat_idx + 1] == '-' and pattern[pat_idx + 2] != ']':
                        low = pattern[pat_idx]
                        high = pattern[pat_idx + 2]
                        if low <= high:
                            for ord_c in range(ord(low), ord(high) + 1):
                                chars.add(chr(ord_c))
                        pat_idx += 3
                    else:
                        chars.add(ch)
                        pat_idx += 1
                    
                    first_char = False
                
                # Check if bracket was properly closed
                # If we exited the while loop because pat_idx >= n_pat without seeing a closing ],
                # the bracket is unterminated. The [ should be treated as literal.
                bracket_closed = False
                if pat_idx < n_pat or (pat_idx > start_pat + 1 and pattern[pat_idx - 1] == ']'):
                    # We broke out of the while loop due to finding ]
                    bracket_closed = True
                
                # Actually, let's track whether we found the closing ]
                # The while loop breaks on ] (when not first_char) or when pat_idx >= n_pat.
                # If it broke on ], bracket_closed = True.
                # If it reached end of pattern, bracket_closed = False.
                
                # Let me re-examine: after the while loop,
                # if we broke due to ], then the last consumed char was ].
                # If we reached pat_idx >= n_pat, no ] was found.
                
                # Simpler: let's explicitly track if we found ].
                found_closing = False
                # Redo: I'll restructure.
                
                # OK let me just handle it: if the bracket is unterminated, treat [ as literal.
                # To detect: after parsing, check if the last character parsed before exiting was ].
                
                # Let me use a flag.
                bracket_closed = False
                
                # Re-parse properly:
                # Reset pat_idx to start_pat + 1
                pat_idx = start_pat + 1
                negate = False
                if pat_idx < n_pat and pattern[pat_idx] == '!':
                    negate = True
                    pat_idx += 1
                
                chars = set()
                first_char = True
                bracket_closed = False
                
                while pat_idx < n_pat:
                    ch = pattern[pat_idx]
                    
                    if ch == ']' and not first_char:
                        pat_idx += 1
                        bracket_closed = True
                        break
                    
                    if pat_idx + 2 < n_pat and pattern[pat_idx + 1] == '-' and pattern[pat_idx + 2] != ']':
                        low = pattern[pat_idx]
                        high = pattern[pat_idx + 2]
                        if low <= high:
                            for ord_c in range(ord(low), ord(high) + 1):
                                chars.add(chr(ord_c))
                        pat_idx += 3
                    else:
                        chars.add(ch)
                        pat_idx += 1
                    
                    first_char = False
                
                if not bracket_closed:
                    # Unterminated [ is literal
                    if s_idx >= n_s or name[s_idx] != '[':
                        return False
                    s_idx += 1
                    pat_idx = start_pat + 1  # continue from after [
                    continue
                
                # Check if current char in name matches the character class
                if s_idx >= n_s:
                    return False
                
                matched = name[s_idx] in chars
                if negate:
                    matched = not matched
                
                if not matched:
                    return False
                
                s_idx += 1
            
            else:
                if s_idx >= n_s or name[s_idx] != c:
                    return False
                pat_idx += 1
                s_idx += 1
        
        return s_idx >= n_s
    
    return match(0, 0)
