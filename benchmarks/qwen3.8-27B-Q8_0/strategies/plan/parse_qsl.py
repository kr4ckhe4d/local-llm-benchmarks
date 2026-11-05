def parse_qsl_(qs):
    if not qs:
        return []
    
    def _unquote_plus(s):
        if not s:
            return s
        # Check if there are any percent escapes or plus signs
        has_plus = '+' in s
        has_percent = '%' in s
        if not has_plus and not has_percent:
            return s
        
        result_bytes = bytearray()
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == '+':
                result_bytes.append(0x20)
                i += 1
            elif c == '%':
                if i + 2 < n:
                    hex1 = s[i + 1]
                    hex2 = s[i + 2]
                    # Check if both are valid hex digits
                    h1 = _hex_val(hex1)
                    h2 = _hex_val(hex2)
                    if h1 is not None and h2 is not None:
                        result_bytes.append(h1 * 16 + h2)
                        i += 3
                    else:
                        result_bytes.extend(c.encode('utf-8'))
                        i += 1
                else:
                    result_bytes.extend(c.encode('utf-8'))
                    i += 1
            else:
                result_bytes.extend(c.encode('utf-8'))
                i += 1
        
        return result_bytes.decode('utf-8', errors='replace')
    
    def _hex_val(c):
        if '0' <= c <= '9':
            return ord(c) - ord('0')
        if 'a' <= c <= 'f':
            return ord(c) - ord('a') + 10
        if 'A' <= c <= 'F':
            return ord(c) - ord('A') + 10
        return None
    
    components = qs.split('&')
    result = []
    for comp in components:
        if '=' in comp:
            idx = comp.index('=')
            key = comp[:idx]
            value = comp[idx + 1:]
        else:
            key = comp
            value = ''
        result.append((_unquote_plus(key), _unquote_plus(value)))
    return result
