def parse_qsl_(qs, keep_blank_values=True):
    def unquote(s):
        # Handle '+' as space
        s = s.replace('+', ' ')
        # Handle percent-escapes
        res = []
        i = 0
        while i < len(s):
            if s[i] == '%' and i + 2 < len(s):
                try:
                    # Convert hex to integer
                    hex_val = int(s[i+1:i+3], 16)
                    res.append(chr(hex_val))
                    i += 3
                except ValueError:
                    res.append(s[i])
                    i += 1
            else:
                res.append(s[i])
                i += 1
        return "".join(res)

    result = []
    if not qs:
        return result

    # Split by '&'
    pairs = qs.split('&')
    for pair in pairs:
        if not pair:
            continue
        if '=' in pair:
            k, v = pair.split('=', 1)
            key = unquote(k)
            value = unquote(v) if keep_blank_values else (v if v else "")
            # Note: urllib.parse.parse_qsl behavior for 'key=' is ('key', '')
            # and for 'key' is ('key', ''). 
            # If keep_blank_values is False, 'key=' becomes ('key', '') 
            # but 'key' remains ('key', ''). Actually, in urllib, 
            # if keep_blank_values is False, only keys with NO value at all 
            # (no '=') are omitted.
            if not keep_blank_values and v == "" and "=" not in pair:
                pass # This logic is handled by the split
            
            # Correcting for urllib.parse.parse_qsl specific behavior:
            # If keep_blank_values is False, keys with empty values are omitted.
            if not keep_blank_values and value == "":
                # Only omit if there was no '=' in the original string
                # But since we split by '=', if it's 'key=', v is ""
                # urllib keeps 'key=' but drops 'key'.
                pass
            
            # Re-evaluating standard urllib.parse.parse_qsl:
            # If keep_blank_values=False, "a&b=" -> [('a', ''), ('b', '')] is WRONG.
            # It should be "a&b=" -> [('b', '')] and "a" is dropped.
            # Wait, actually urllib.parse.parse_qsl("a&b=") with keep_blank_values=False 
            # returns [('b', '')]. "a" is dropped because it has no value.
            
            # Let's simplify to the exact standard:
            if not keep_blank_values and v == "" and "=" not in pair:
                continue
            
            result.append((key, value))
        else:
            # Component with no '=' yields a pair with an empty value
            key = unquote(pair)
            if not keep_blank_values:
                continue
            result.append((key, ""))
            
    # Refined logic to match urllib exactly:
    # 1. Split by &
    # 2. For each part:
    #    a. If '=' in part: split once, unquote both, append (k, v)
    #    b. If '=' not in part: unquote k, if keep_blank_values: append (k, ""), else skip
    
    final_res = []
    for pair in qs.split('&'):
        if not pair: continue
        if '=' in pair:
            k, v = pair.split('=', 1)
            final_res.append((unquote(k), unquote(v)))
        else:
            if keep_blank_values:
                final_res.append((unquote(pair), ""))
    return final_res


def parse_qsl_(qs, keep_blank_values=True):
    def unquote(s):
        s = s.replace('+', ' ')
        res = []
        i = 0
        while i < len(s):
            if s[i] == '%' and i + 2 < len(s):
                try:
                    res.append(chr(int(s[i+1:i+3], 16)))
                    i += 3
                except ValueError:
                    res.append(s[i])
                    i += 1
            else:
                res.append(s[i])
                i += 1
        return "".join(res)

    result = []
    if not qs: return result
    for pair in qs.split('&'):
        if not pair: continue
        if '=' in pair:
            k, v = pair.split('=', 1)
            result.append((unquote(k), unquote(v)))
        else:
            if keep_blank_values:
                result.append((unquote(pair), ""))
    return result
