def parse_qsl_(qs):
    if not qs:
        return []

    result = []
    parts = qs.split('&')

    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
        else:
            key, value = part, ''

        # Decode '+' as space
        key = key.replace('+', ' ')
        value = value.replace('+', ' ')

        # Decode percent-escapes
        def decode_percent(s):
            i = 0
            decoded = []
            while i < len(s):
                if s[i] == '%' and i + 2 < len(s):
                    try:
                        hex_val = s[i+1:i+3]
                        char = chr(int(hex_val, 16))
                        decoded.append(char)
                        i += 3
                        continue
                    except ValueError:
                        pass
                decoded.append(s[i])
                i += 1
            return ''.join(decoded)

        key = decode_percent(key)
        value = decode_percent(value)

        result.append((key, value))

    return result
