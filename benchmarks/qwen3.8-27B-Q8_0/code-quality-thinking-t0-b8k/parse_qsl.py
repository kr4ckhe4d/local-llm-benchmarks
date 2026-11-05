def parse_qsl_(qs):
    def _unquote_plus(s):
        s = s.replace("+", " ")
        out = []
        buf = bytearray()

        def flush():
            if buf:
                out.append(bytes(buf).decode("utf-8", "replace"))
                buf.clear()

        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == "%" and i + 2 < n:
                h1, h2 = s[i + 1], s[i + 2]
                try:
                    b = int(h1 + h2, 16)
                except ValueError:
                    flush()
                    out.append(c)
                    i += 1
                    continue
                buf.append(b)
                i += 3
            else:
                flush()
                out.append(c)
                i += 1

        flush()
        return "".join(out)

    result = []
    for part in qs.split("&"):
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
        else:
            key, value = part, ""
        result.append((_unquote_plus(key), _unquote_plus(value)))
    return result
