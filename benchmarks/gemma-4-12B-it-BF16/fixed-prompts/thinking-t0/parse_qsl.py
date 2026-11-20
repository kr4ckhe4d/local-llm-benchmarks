def parse_qsl_(qs):
    def unquote(s):
        # Replace '+' with space as per query string rules
        s = s.replace('+', ' ')
        res = []
        i = 0
        while i < len(s):
            if s[i] == '%' and i + 2 < len(s):
                try:
                    # Attempt to decode the hex value
                    hex_val = s[i+1:i+3]
                    char_code = int(hex_val, 16)
                    res.append(chr(char_code))
                    i += 3
                except ValueError:
                    # If not valid hex, treat '%' as literal
                    res.append(s[i])
                    i += 1
            else:
                res.append(s[i])
                i += 1
        return "".join(res)

    result = []
    if not qs:
        return result

    # Split by '&' only
    parts = qs.split('&')
    for part in parts:
        if not part:
            continue
        if '=' in part:
            # Split only on the first '='
            key, value = part.split('=', 1)
            result.append((unquote(key), unquote(value)))
        else:
            # Component with no '=' yields a pair with an empty value
            result.append((unquote(part), ""))
    return result
