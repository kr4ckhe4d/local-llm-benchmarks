def parse_qsl_(qs):
    """
    Parse a query string into a list of (key, value) pairs.
    
    - Separates components by '&' only.
    - Decodes percent-escapes and '+' as space.
    - Keeps blank values (e.g., 'key=' becomes ('key', '')).
    - A component with no '=' yields (component, '').
    """
    def unquote(s):
        """Decode percent-escapes and '+' as space."""
        result = []
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == '+':
                result.append(' ')
                i += 1
            elif c == '%':
                if i + 2 < n + 1 and i + 2 <= n - 1:
                    hex_chars = s[i+1:i+3]
                    try:
                        code = int(hex_chars, 16)
                        result.append(chr(code))
                        i += 3
                    except (ValueError, IndexError):
                        result.append(c)
                        i += 1
                else:
                    result.append(c)
                    i += 1
            else:
                result.append(c)
                i += 1
        return ''.join(result)
    
    if not qs:
        return []
    
    pairs = []
    # Split by '&'
    components = qs.split('&')
    
    for component in components:
        if not component:
            continue
        if '=' in component:
            key, value = component.split('=', 1)
            pairs.append((unquote(key), unquote(value)))
        else:
            pairs.append((unquote(component), ''))
    
    return pairs
