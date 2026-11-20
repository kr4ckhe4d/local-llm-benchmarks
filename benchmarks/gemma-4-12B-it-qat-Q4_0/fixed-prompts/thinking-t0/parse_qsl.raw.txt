def parse_qsl_(qs):
    def unquote(s):
        # Replace '+' with space
        s = s.replace('+', ' ')
        res = []
        i = 0
        while i < len(s):
            if s[i] == '%' and i + 2 < len(s):
                try:
                    # Try to convert the next two characters to an integer
                    hex_val = s[i+1:i+3]
                    # Check if they are valid hex digits manually to avoid 
                    # catching other errors, though int(x, 16) is standard.
                    if all(c in '0123456789abcdefABCDEF' for c in hex_val):
                        res.append(chr(int(hex_val, 16)))
                        i += 3
                        continue
                except ValueError:
                    pass
            res.append(s[i])
            i += 1
        return "".join(res)

    if not qs:
        return []

    result = []
    # Split by '&' only as per instructions
    parts = qs.split('&')
    for part in parts:
        if not part:
            continue
        if '=' in part:
            key, value = part.split('=', 1)
            result.append((unquote(key), unquote(value)))
        else:
            result.append((unquote(part), ""))
    return result