def parse_qsl_(qs):
    def _unquote_plus(s):
        if not s:
            return s

        s = s.replace('+', ' ')

        i = 0
        n = len(s)
        out = []
        while i < n:
            c = s[i]
            if c == '%' and i + 2 < n:
                hex_digits = s[i + 1:i + 3]
                try:
                    b = int(hex_digits, 16)
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
        if not part:
            continue

        if '=' in part:
            key, value = part.split('=', 1)
        else:
            key, value = part, ''

        result.append((_unquote_plus(key), _unquote_plus(value)))

    return result
