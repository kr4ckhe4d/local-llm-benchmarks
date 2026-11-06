    def shlex_split(s):
        tokens = []
        buffer = ""
        state = "NORMAL" # NORMAL, SINGLE_QUOTE, DOUBLE_QUOTE
        i = 0
        n = len(s)
        
        while i < n:
            char = s[i]
            
            if state == "NORMAL":
                if char.isspace():
                    if buffer:
                        tokens.append(buffer)
                        buffer = ""
                elif char == "'":
                    state = "SINGLE_QUOTE"
                elif char == '"':
                    state = "DOUBLE_QUOTE"
                elif char == "\\":
                    if i + 1 < n:
                        buffer += s[i+1]
                        i += 1
                    else:
                        raise ValueError("No escaped character")
                else:
                    buffer += char
            
            elif state == "SINGLE_QUOTE":
                if char == "'":
                    state = "NORMAL"
                else:
                    buffer += char
            
            elif state == "DOUBLE_QUOTE":
                if char == '"':
                    state = "NORMAL"
                elif char == "\\":
                    if i + 1 < n:
                        next_char = s[i+1]
                        if next_char in ('\\', '"'):
                            buffer += next_char
                            i += 1
                        else:
                            buffer += "\\"
                    else:
                        # Trailing backslash in double quotes? 
                        # shlex behavior: "In double quotes, backslash escapes only backslash and double quote."
                        # If it's at the end, it's just a backslash.
                        buffer += "\\"
                else:
                    buffer += char
            i += 1
            
        if buffer:
            tokens.append(buffer)
        return tokens
    

        import shlex
        shlex.split(r"a'b'c") # ['abc']
        shlex.split(r"a'b'c") # Wait, I just ran it. It is ['abc'].
        

        elif char == "\\":
            if i + 1 < n:
                next_char = s[i+1]
                if next_char in ('\\', '"'):
                    buffer += next_char
                    i += 1
                else:
                    buffer += "\\"
            else:
                buffer += "\\"
        

        elif char == "\\":
            if i + 1 < n:
                buffer += s[i+1]
                i += 1 # This skips the escaped character
            else:
                raise ValueError("No escaped character")
        

        elif char == "\\":
            if i + 1 < n:
                next_char = s[i+1]
                if next_char in ('\\', '"'):
                    buffer += next_char
                    i += 1
                else:
                    buffer += "\\"
            else:
                buffer += "\\"
        