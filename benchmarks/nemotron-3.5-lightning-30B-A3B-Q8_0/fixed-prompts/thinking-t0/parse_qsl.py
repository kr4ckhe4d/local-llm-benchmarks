def parse_qsl_(qs):
    def _percent_decode(s):
        i = 0
        res = []
        while i < len(s):
            if s[i] == '%' and i + 2 < len(s):
                hex_str = s[i+1:i+3]
                try:
                    res.append(chr(int(hex_str, 16)))
                    i += 3
                    continue
                except ValueError:
                    pass
            res.append(s[i])
            i += 1
        return ''.join(res)

    if not qs:
        return []

    parts = qs.split('&')
    result = []
    for part in parts:
        if '=' in part:
            idx = part.index('=')
            key = part[:idx]
            value = part[idx+1:]
        else:
            key = part
            value = ''
        # Replace '+' with space first, then decode percent-escapes
        key = key.replace('+', ' ')
        value = value.replace('+', ' ')
        key = _percent_decode(key)
        value = _percent_decode(value)
        result.append((key, value))
    return result
