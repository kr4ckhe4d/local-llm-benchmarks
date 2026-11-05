def parse_qsl_(qs):
    def unquote_plus(s):
        # Replace '+' with ' '
        s = s.replace('+', ' ')
        
        # Decode percent-escapes as bytes, then decode as UTF-8
        byte_list = []
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == '%':
                if i + 2 < n:
                    hex_str = s[i+1:i+3]
                    if all(ch in '0123456789abcdefABCDEF' for ch in hex_str):
                        byte_val = int(hex_str, 16)
                        byte_list.append(byte_val)
                        i += 3
                    else:
                        # Invalid %XX, encode % as UTF-8
                        byte_list.extend('%'.encode('utf-8'))
                        i += 1
                else:
                    byte_list.extend('%'.encode('utf-8'))
                    i += 1
            else:
                # Encode the character as UTF-8 bytes
                byte_list.extend(c.encode('utf-8'))
                i += 1
        
        # Decode the byte list as UTF-8 with replacement for invalid sequences
        try:
            return bytes(byte_list).decode('utf-8')
        except UnicodeDecodeError:
            return bytes(byte_list).decode('utf-8', errors='replace')
    
    if not qs:
        return []
    
    pairs = []
    components = qs.split('&')
    
    for component in components:
        if not component:
            continue
        
        eq_pos = component.find('=')
        if eq_pos == -1:
            key = unquote_plus(component)
            value = ''
        else:
            key = unquote_plus(component[:eq_pos])
            value = unquote_plus(component[eq_pos+1:])
        
        pairs.append((key, value))
    
    return pairs
