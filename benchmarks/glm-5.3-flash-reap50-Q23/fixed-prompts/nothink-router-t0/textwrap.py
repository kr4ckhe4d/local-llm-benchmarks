def wrap_(text, width):
    lines = []
    current = ""
    i = 0
    n = len(text)
    while i < n:
        # expand tabs and collapse whitespace runs
        if text[i] == '\t':
            j = i
            k = 0
            while j < n and text[j] == '\t':
                k += 8 - (k % 8)
                j += 1
            i = j
            for _ in range(k):
                if len(current) >= width:
                    lines.append(current)
                    current = ""
                current += " "
            continue
        if text[i] in ' \n\r\v\f':
            j = i
            while j < n and text[j] in ' \n\r\v\f':
                j += 1
            run = j - i
            i = j
            if run > width:
                lines.append(current)
                current = ""
                continue
            for _ in range(run):
                if len(current) >= width:
                    lines.append(current)
                    current = ""
                current += " "
            continue
        # word chunk
        j = i
        while j < n and text[j] not in ' \t\n\r\v\f':
            j += 1
        chunk = text[i:j]
        i = j
        if len(chunk) >= width:
            if current:
                lines.append(current)
                current = ""
            k = 0
            while k < len(chunk):
                lines.append(chunk[k:k+width])
                k += width
        else:
            if not current:
                current = chunk
            elif len(current) + 1 + len(chunk) <= width:
                current = current + " " + chunk
            else:
                lines.append(current)
                current = chunk
    if current:
        lines.append(current)
    return lines
