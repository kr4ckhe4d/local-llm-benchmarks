def parse_qsl_(qs):
    def unquote_plus(s):
        s = s.replace('+', ' ')
        result = []
        i = 0
        n = len(s)
        while i < n:
            if s[i] == '%':
                if i + 2 < n:
                    hex_chars = s[i+1:i+3]
                    try:
                        char = chr(int(hex_chars, 16))
                        result.append(char)
                        i += 3
                        continue
                    except ValueError:
                        pass
            result.append(s[i])
            i += 1
        return ''.join(result)

    if not qs:
        return []
    
    pairs = []
    parts = qs.split('&')
    
    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
        else:
            key = part
            value = ''
        
        pairs.append((unquote_plus(key), unquote_plus(value)))
    
    return pairs
