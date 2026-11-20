def parse_qsl_(qs, keep_blank_values=True):
    def unquote(s):
        # Handle '+' as space
        s = s.replace('+', ' ')
        # Handle percent-escapes
        res = bytearray()
        i = 0
        while i < len(s):
            if s[i] == '%' and i + 2 < len(s):
                try:
                    # Convert hex to integer
                    byte = int(s[i+1:i+3], 16)
                    res.append(byte)
                    i += 3
                except ValueError:
                    res.append(ord(s[i]))
                    i += 1
            else:
                res.append(ord(s[i]))
                i += 1
        return res.decode('utf-8', errors='replace')

    result = []
    if not qs:
        return result

    # Split by '&' only
    parts = qs.split('&')
    for part in parts:
        if not part:
            continue
        if '=' in part:
            key, value = part.split('=', 1)
            if keep_blank_values:
                result.append((unquote(key), unquote(value)))
            else:
                if value:
                    result.append((unquote(key), unquote(value)))
        else:
            # Component with no '=' yields a pair with an empty value
            if keep_blank_values:
                result.append((unquote(part), ""))
            else:
                # If keep_blank_values is False, components without '=' 
                # are treated as having an empty value and thus omitted.
                pass
    return result
