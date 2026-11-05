def wrap_(text, width):
    if width <= 0:
        raise ValueError(f"invalid width {width!r} (must be > 0)")
    
    expanded = []
    col = 0
    for ch in text:
        if ch == '\t':
            spaces = 8 - (col % 8)
            expanded.append(' ' * spaces)
            col += spaces
        else:
            expanded.append(ch)
            col += 1
    text = ''.join(expanded)
    
    if not text:
        return []
    
    units = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] in ' \n\r\f\v':
            units.append(('ws', text[i]))
            i += 1
        else:
            j = i
            while j < n and text[j] not in ' \n\r\f\v':
                j += 1
            units.append(('word', text[i:j]))
            i = j
    
    lines = []
    current_line = []
    current_len = 0
    
    for idx, (utype, uval) in enumerate(units):
        ulen = len(uval)
        
        if utype == 'word':
            if current_len + ulen <= width:
                current_line.append((utype, uval))
                current_len += ulen
            else:
                break_idx = -1
                for k in range(len(current_line) - 1, -1, -1):
                    if current_line[k][0] == 'ws':
                        break_idx = k
                        break
                
                if break_idx >= 0:
                    line_units = current_line[:break_idx]
                    while line_units and line_units[-1][0] == 'ws':
                        line_units.pop()
                    line_str = ''.join(u[1] for u in line_units)
                    lines.append(line_str)
                    
                    current_line = current_line[break_idx+1:]
                    while current_line and current_line[0][0] == 'ws':
                        current_line.pop(0)
                    current_len = sum(len(u[1]) for u in current_line)
                    
                    if current_len + ulen <= width:
                        current_line.append((utype, uval))
                        current_len += ulen
                    else:
                        if current_line:
                            line_str = ''.join(u[1] for u in current_line)
                            lines.append(line_str)
                            current_line = []
                            current_len = 0
                        
                        remaining = uval
                        while len(remaining) > width:
                            lines.append(remaining[:width])
                            remaining = remaining[width:]
                        current_line.append(('word', remaining))
                        current_len = len(remaining)
                else:
                    if current_line:
                        line_str = ''.join(u[1] for u in current_line)
                        lines.append(line_str)
                        current_line = []
                        current_len = 0
                    
                    remaining = uval
                    while len(remaining) > width:
                        lines.append(remaining[:width])
                        remaining = remaining[width:]
                    current_line.append(('word', remaining))
                    current_len = len(remaining)
        else:
            current_line.append((utype, uval))
            current_len += ulen
    
    if current_line:
        line_str = ''.join(u[1] for u in current_line)
        lines.append(line_str)
    
    return lines
