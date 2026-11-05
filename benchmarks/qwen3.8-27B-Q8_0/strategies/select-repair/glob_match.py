def glob_match(pattern, name):
    """
    Implement fnmatch.fnmatchcase semantics from scratch.
    
    Supported patterns:
    - * : matches any run of characters (including empty)
    - ? : matches exactly one character
    - [seq] : matches any single character in seq
    - [!seq] : matches any single character NOT in seq
    - ] immediately after [ or [! is a literal ]
    - unterminated [ is a literal [
    
    Matching is anchored to the whole string.
    """
    
    def parse_pattern(pattern):
        """
        Parse the pattern into a list of tokens.
        Each token is a tuple:
        - ('star',) for *
        - ('question',) for ?
        - ('char', c) for literal character c
        - ('class', chars, negated) for [seq] or [!seq]
        """
        tokens = []
        i = 0
        n = len(pattern)
        
        while i < n:
            c = pattern[i]
            
            if c == '*':
                tokens.append(('star',))
                i += 1
            elif c == '?':
                tokens.append(('question',))
                i += 1
            elif c == '[':
                # Parse character class
                j = i + 1
                negated = False
                if j < n and pattern[j] == '!':
                    negated = True
                    j += 1
                
                # Check if ] is immediately after [ or [!
                if j < n and pattern[j] == ']':
                    # ] is a literal, so include it in the class
                    chars = set()
                    chars.add(']')
                    j += 1
                else:
                    chars = set()
                
                # Parse the rest of the class until closing ]
                found_close = False
                while j < n:
                    if pattern[j] == ']':
                        found_close = True
                        j += 1
                        break
                    else:
                        # Handle ranges like a-z
                        if (j + 2 < n and pattern[j + 1] == '-' and pattern[j + 2] != ']'):
                            start_c = pattern[j]
                            end_c = pattern[j + 2]
                            if ord(start_c) <= ord(end_c):
                                for k in range(ord(start_c), ord(end_c) + 1):
                                    chars.add(chr(k))
                            j += 3
                        else:
                            chars.add(pattern[j])
                            j += 1
                
                if found_close:
                    tokens.append(('class', chars, negated))
                    i = j
                else:
                    # Unterminated [, treat as literal [
                    tokens.append(('char', '['))
                    i += 1
            else:
                tokens.append(('char', c))
                i += 1
        
        return tokens
    
    def match_tokens(tokens, token_idx, name, name_idx):
        """
        Recursively match tokens against name starting at given indices.
        Returns True if the remaining tokens match the remaining name.
        """
        # If we've run out of tokens, we need to have consumed the entire name
        if token_idx == len(tokens):
            return name_idx == len(name)
        
        token = tokens[token_idx]
        
        if token[0] == 'star':
            # * can match any number of characters (including zero)
            # Try matching zero characters first, then one, two, etc.
            # We need to try all possible lengths for the star
            for skip in range(len(name) - name_idx + 1):
                if match_tokens(tokens, token_idx + 1, name, name_idx + skip):
                    return True
            return False
        elif token[0] == 'question':
            # ? matches exactly one character
            if name_idx < len(name):
                return match_tokens(tokens, token_idx + 1, name, name_idx + 1)
            else:
                return False
        elif token[0] == 'char':
            # Literal character
            if name_idx < len(name) and name[name_idx] == token[1]:
                return match_tokens(tokens, token_idx + 1, name, name_idx + 1)
            else:
                return False
        elif token[0] == 'class':
            _, chars, negated = token
            if name_idx < len(name):
                ch = name[name_idx]
                if negated:
                    if ch not in chars:
                        return match_tokens(tokens, token_idx + 1, name, name_idx + 1)
                else:
                    if ch in chars:
                        return match_tokens(tokens, token_idx + 1, name, name_idx + 1)
            return False
        
        return False
    
    tokens = parse_pattern(pattern)
    return match_tokens(tokens, 0, name, 0)

