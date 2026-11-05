def parse_qsl_(qs):
    """
    Parse a query string into a list of (key, value) pairs.
    
    - Only '&' is used as the separator.
    - '+' is decoded as space.
    - Percent-escapes are decoded.
    - Blank values are kept (e.g., 'key=' yields ('key', '')).
    - A component with no '=' yields a pair with an empty value (e.g., 'key' yields ('key', '')).
    """
    if not qs:
        return []
    
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
            elif c == '%' and i + 2 < n:
                hex_chars = s[i+1:i+3]
                try:
                    byte_val = int(hex_chars, 16)
                    # Check if this is a valid UTF-8 sequence
                    # For simplicity, try to decode as UTF-8
                    # If it's a single byte that's valid ASCII or we can form valid UTF-8
                    # We need to handle multi-byte UTF-8 sequences
                    
                    # Try to decode the byte as part of UTF-8
                    # If byte_val < 128, it's a single ASCII character
                    if byte_val < 128:
                        result.append(chr(byte_val))
                        i += 3
                    else:
                        # Need to check if this is a valid UTF-8 start byte
                        # and collect the appropriate number of continuation bytes
                        if byte_val < 0x80:
                            result.append(chr(byte_val))
                            i += 3
                        elif byte_val < 0xC0:
                            # Continuation byte without start - invalid
                            result.append('\ufffd')
                            i += 3
                        elif byte_val < 0xE0:
                            # 2-byte sequence
                            if i + 5 < n and s[i+3] == '%' and s[i+4:i+6].isalnum():
                                try:
                                    byte2 = int(s[i+4:i+6], 16)
                                    if 0x80 <= byte2 <= 0xBF:
                                        char_code = ((byte_val & 0x1F) << 6) | (byte2 & 0x3F)
                                        result.append(chr(char_code))
                                        i += 6
                                        continue
                                except ValueError:
                                    pass
                            result.append('\ufffd')
                            i += 3
                        elif byte_val < 0xF0:
                            # 3-byte sequence
                            if (i + 8 < n and s[i+3] == '%' and s[i+4:i+6].isalnum() and 
                                s[i+6] == '%' and s[i+7:i+9].isalnum()):
                                try:
                                    byte2 = int(s[i+4:i+6], 16)
                                    byte3 = int(s[i+7:i+9], 16)
                                    if 0x80 <= byte2 <= 0xBF and 0x80 <= byte3 <= 0xBF:
                                        char_code = ((byte_val & 0x0F) << 12) | ((byte2 & 0x3F) << 6) | (byte3 & 0x3F)
                                        result.append(chr(char_code))
                                        i += 9
                                        continue
                                except ValueError:
                                    pass
                            result.append('\ufffd')
                            i += 3
                        else:
                            # 4-byte sequence
                            if (i + 11 < n and s[i+3] == '%' and s[i+4:i+6].isalnum() and 
                                s[i+6] == '%' and s[i+7:i+9].isalnum() and
                                s[i+9] == '%' and s[i+10:i+12].isalnum()):
                                try:
                                    byte2 = int(s[i+4:i+6], 16)
                                    byte3 = int(s[i+7:i+9], 16)
                                    byte4 = int(s[i+10:i+12], 16)
                                    if (0x80 <= byte2 <= 0xBF and 0x80 <= byte3 <= 0xBF and 
                                        0x80 <= byte4 <= 0xBF):
                                        char_code = ((byte_val & 0x07) << 18) | ((byte2 & 0x3F) << 12) | ((byte3 & 0x3F) << 6) | (byte4 & 0x3F)
                                        result.append(chr(char_code))
                                        i += 12
                                        continue
                                except ValueError:
                                    pass
                            result.append('\ufffd')
                            i += 3
                except ValueError:
                    result.append(c)
                    i += 1
            else:
                result.append(c)
                i += 1
        return ''.join(result)
    
    pairs = []
    # Split by '&'
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
