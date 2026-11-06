def parse_qsl_(qs):
    def _unquote_plus(s):
        if not s:
            return s
        s = s.replace('+', ' ')
        if '%' not in s:
            return s
        out = []
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == '%' and i + 2 < n:
                hexdigits = s[i + 1:i + 3]
                try:
                    b = int(hexdigits, 16)
                except ValueError:
                    out.append(c)
                    i += 1
                    continue
                out.append(chr(b))
                i += 3
            else:
                out.append(c)
                i += 1
        return ''.join(out)

    result = []
    for part in qs.split('&'):
        if '=' in part:
            key, value = part.split('=', 1)
        else:
            key, value = part, ''
        result.append((_unquote_plus(key), _unquote_plus(value)))
    return result
