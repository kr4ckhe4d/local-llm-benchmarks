def parse_qsl_(qs):
    def decode_component(s):
        # Replace '+' with space
        s = s.replace('+', ' ')
        # Decode percent-escapes
        result = []
        i = 0
        n = len(s)
        while i < n:
            if s[i] == '%' and i + 2 < n:
                hex_str = s[i+1:i+3]
                try:
                    char_code = int(hex_str, 16)
                    result.append(chr(char_code))
                    i += 3
                except ValueError:
                    result.append(s[i])
                    i += 1
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    if not qs:
        return []

    parts = qs.split('&')
    result = []
    for part in parts:
        if not part:
            continue
        
        if '=' in part:
            key, value = part.split('=', 1)
        else:
            key = part
            value = ''
        
        result.append((decode_component(key), decode_component(value)))
    
    return result
