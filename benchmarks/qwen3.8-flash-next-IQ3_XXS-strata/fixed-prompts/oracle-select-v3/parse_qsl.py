def parse_qsl_(qs):
    """
    Parse a query string into a list of (key, value) pairs.
    
    - Splits on '&' only.
    - Decodes percent-escapes (%XX) and '+' as space.
    - Keeps blank values.
    - A component with no '=' yields a pair with an empty value.
    """
    def decode(s):
        """Decode percent-escapes and '+' as space, handling UTF-8 properly."""
        # First, replace '+' with space
        s = s.replace('+', ' ')
        
        # Now handle percent-escapes by collecting bytes and decoding as UTF-8
        result_bytes = []
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == '%' and i + 2 < n:
                hex_str = s[i+1:i+3]
                # Check if both characters are valid hex digits
                if all(ch in '0123456789abcdefABCDEF' for ch in hex_str):
                    byte_val = int(hex_str, 16)
                    result_bytes.append(byte_val)
                    i += 3
                else:
                    # Invalid percent-escape, keep '%' as literal
                    result_bytes.append(ord('%'))
                    i += 1
            else:
                result_bytes.append(ord(c))
                i += 1
        
        # Decode the collected bytes as UTF-8 with replacement for invalid sequences
        try:
            return bytes(result_bytes).decode('utf-8', errors='replace')
        except Exception:
            return bytes(result_bytes).decode('latin-1')
    
    if not qs:
        return []
    
    pairs = []
    # Split on '&' only
    components = qs.split('&')
    
    for component in components:
        if not component:
            continue
        
        # Find the first '=' to split key and value
        eq_index = component.find('=')
        if eq_index == -1:
            # No '=' means key is the whole component, value is empty
            key = decode(component)
            value = ''
        else:
            key = decode(component[:eq_index])
            value = decode(component[eq_index+1:])
        
        pairs.append((key, value))
    
    return pairs
