def parse_qsl_(qs, keep_blank_values=True):
    def _unquote(s):
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
            k, v = part.split('=', 1)
            key = _unquote(k)
            val = _unquote(v) if keep_blank_values else (v if v else "")
            # Note: urllib.parse.parse_qsl behavior for 'key=' is ('key', '')
            # and 'key' is ('key', '').
            # If keep_blank_values is False, 'key=' becomes ('key', '') 
            # but 'key' (no =) is skipped or handled differently? 
            # Actually, parse_qsl treats 'key' as ('key', '') regardless of keep_blank_values.
            # The flag only affects whether empty strings in the source are preserved.
            result.append((key, val))
        else:
            key = _unquote(part)
            result.append((key, ""))
            
    return result
