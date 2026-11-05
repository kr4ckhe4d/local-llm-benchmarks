def parse_qsl_(qs):
    def _unquote_plus(s):
        # '+' → space (query-string convention)
        s = s.replace('+', ' ')
        # Percent-decode, collecting raw bytes so multi-byte UTF-8 sequences work
        buf = bytearray()
        i = 0
        n = len(s)
        while i < n:
            if s[i] == '%':
                buf.append(int(s[i + 1:i + 3], 16))
                i += 3
            else:
                buf.extend(s[i].encode('utf-8'))
                i += 1
        return buf.decode('utf-8')

    if not qs:
        return []

    pairs = []
    for component in qs.split('&'):
        if not component:
            continue
        if '=' in component:
            key, value = component.split('=', 1)
        else:
            key, value = component, ''
        pairs.append((_unquote_plus(key), _unquote_plus(value)))
    return pairs
