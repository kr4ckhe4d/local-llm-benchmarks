def parse_qsl_(qs):
    """
    Parse a query string into a list of (key, value) pairs.
    
    - Separates components by '&' only.
    - Decodes percent-escapes and '+' as space in both keys and values.
    - Keeps blank values (i.e., 'key=' produces ('key', '')).
    - A component with no '=' yields (component, '').
    """
    result = []
    if not qs:
        return result
    
    # Split by '&'
    pairs = qs.split('&')
    
    for pair in pairs:
        if not pair:
            continue
        
        # Check for '=' separator
        if '=' in pair:
            key, value = pair.split('=', 1)
        else:
            key = pair
            value = ''
        
        # Decode key and value
        decoded_key = _unquote_plus(key)
        decoded_value = _unquote_plus(value)
        
        result.append((decoded_key, decoded_value))
    
    return result


def _unquote_plus(s):
    """
    Decode a percent-encoded string, treating '+' as space.
    """
    # Replace '+' with space first
    s = s.replace('+', ' ')
    
    # Then decode percent-escapes
    result = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '%' and i + 2 < n:
            hex_str = s[i+1:i+3]
            try:
                byte_val = int(hex_str, 16)
                # Append the character
                result.append(chr(byte_val))
                i += 3
            except ValueError:
                # Invalid hex, keep the % as-is
                result.append(c)
                i += 1
        else:
            result.append(c)
            i += 1
    
    return ''.join(result)
