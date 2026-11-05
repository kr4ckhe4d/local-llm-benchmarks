def parse_qsl_(qs):
    if not qs:
        return []
    
    def unquote(s):
        result = []
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == '+':
                result.append(' ')
                i += 1
            elif c == '%' and i + 2 < n:
                hex_chars = s[i+1:i+3]
                try:
                    byte_val = int(hex_chars, 16)
                    result.append(chr(byte_val))
                    i += 3
                except ValueError:
                    result.append(c)
                    i += 1
            else:
                result.append(c)
                i += 1
        return ''.join(result)
    
    pairs = []
    components = qs.split('&')
    for component in components:
        if not component:
            continue
        if '=' in component:
            key, value = component.split('=', 1)
        else:
            key = component
            value = ''
        key = unquote(key)
        value = unquote(value)
        pairs.append((key, value))
    
    return pairs
