def parse_qsl_(qs):
    if not qs:
        return []
    
    def unquote(s):
        # Replace '+' with space first
        s = s.replace('+', ' ')
        
        # Decode percent-escapes
        i = 0
        n = len(s)
        result = []
        while i < n:
            if s[i] == '%' and i + 2 < n:
                hex_chars = s[i+1:i+3]
                try:
                    byte_val = int(hex_chars, 16)
                    result.append(chr(byte_val))
                    i += 3
                except ValueError:
                    # Invalid hex, keep as is
                    result.append(s[i])
                    i += 1
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    pairs = []
    # Split only by '&'
    components = qs.split('&')
    
    for comp in components:
        if not comp:
            continue
            
        if '=' in comp:
            key, value = comp.split('=', 1)
        else:
            key = comp
            value = ''
            
        key = unquote(key)
        value = unquote(value)
        
        pairs.append((key, value))
        
    return pairs
