import re

def parse_qsl_(qs):
    """
    Reproduce urllib.parse.parse_qsl(qs, keep_blank_values=True) from scratch.
    
    Rules:
    - Separator: ONLY '&'
    - Key/Value separator: '='
    - Decoding: Percent-escapes (e.g., %20) and '+' as space.
    - Blank values: Kept (e.g., "a=" -> ('a', ''), "a" -> ('a', ''))
    - Order: Preserved.
    """
    if not qs:
        return []

    # Split by '&' only
    components = qs.split('&')
    
    result = []
    
    for component in components:
        # Check if '=' exists
        if '=' in component:
            # Split only on the first '=' to handle values containing '='
            key, value = component.split('=', 1)
        else:
            # No '=' means empty value
            key = component
            value = ''
        
        # Decode '+' as space
        key = key.replace('+', ' ')
        value = value.replace('+', ' ')
        
        # Decode percent-escapes
        # We use a regex to find %XX patterns and decode them
        def percent_decode(s):
            def replace_hex(match):
                try:
                    return chr(int(match.group(1), 16))
                except ValueError:
                    # If not a valid hex, return original (or could raise error)
                    return match.group(0)
            return re.sub(r'%([0-9A-Fa-f]{2})', replace_hex, s)
        
        key = percent_decode(key)
        value = percent_decode(value)
        
        result.append((key, value))
    
    return result
