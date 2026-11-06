import re

def wrap_(text, width):
    if width <= 0:
        raise ValueError("width must be > 0")
    text = text.expandtabs()
    text = re.sub(r'\s', ' ', text)
    tokens = re.findall(r'\S+| +', text)
    lines = []
    current = []
    cur_len = 0
    line_start = True
    text_start = True
    i = 0
    n = len(tokens)
    while i < n:
        token = tokens[i]
        if token == '':
            i += 1
            continue
        if token[0] == ' ':
            if line_start:
                if text_start:
                    if len(token) > width:
                        current.append(token[:width])
                        cur_len = width
                        line = ''.join(current).rstrip(' ')
                        if line:
                            lines.append(line)
                        current = []
                        cur_len = 0
                        line_start = True
                        text_start = False
                        i += 1
                        continue
                    else:
                        current.append(token)
                        cur_len = len(token)
                        text_start = False
                        line_start = False
                        i += 1
                        continue
                else:
                    i += 1
                    continue
            else:
                if cur_len + len(token) <= width:
                    current.append(token)
                    cur_len += len(token)
                    i += 1
                    continue
                else:
                    line = ''.join(current).rstrip(' ')
                    if line:
                        lines.append(line)
                    current = []
                    cur_len = 0
                    line_start = True
                    i += 1
                    continue
        else:
            if line_start:
                if len(token) > width:
                    current.append(token[:width])
                    cur_len = width
                    line = ''.join(current).rstrip(' ')
                    if line:
                        lines.append(line)
                    current = []
                    cur_len = 0
                    line_start = True
                    text_start = False
                    remainder = token[width:]
                    if remainder:
                        tokens.insert(i + 1, remainder)
                    i += 1
                    continue
                else:
                    current.append(token)
                    cur_len = len(token)
                    line_start = False
                    text_start = False
                    i += 1
                    continue
            else:
                if cur_len + len(token) <= width:
                    current.append(token)
                    cur_len += len(token)
                    i += 1
                    continue
                else:
                    line = ''.join(current).rstrip(' ')
                    if line:
                        lines.append(line)
                    current = []
                    cur_len = 0
                    line_start = True
                    continue
    if current:
        line = ''.join(current).rstrip(' ')
        if line:
            lines.append(line)
    return lines