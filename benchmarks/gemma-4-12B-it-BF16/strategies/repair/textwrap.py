def wrap_(text, width):
    # Expand tabs to spaces (default tabsize is 8)
    text = text.expandtabs()
    
    # Identify leading whitespace of the whole text
    leading_ws = ""
    for char in text:
        if char.isspace():
            leading_ws += char
        else:
            break
    
    content = text[len(leading_ws):]
    
    # Tokenize content into words and whitespace characters
    # We must preserve the exact count of spaces as per "runs are NOT collapsed"
    tokens = []
    current_token = ""
    for char in content:
        if char.isspace():
            if current_token:
                tokens.append(current_token)
                current_token = ""
            tokens.append(char)
        else:
            current_token += char
    if current_token:
        tokens.append(current_token)

    lines = []
    current_line_tokens = []
    current_line_len = 0

    for token in tokens:
        if token.isspace():
            # If we have a word followed by whitespace, and adding it exceeds width,
            # the whitespace is effectively "trailing" for that line and should be dropped.
            if current_line_len + len(token) <= width:
                current_line_tokens.append(token)
                current_line_len += len(token)
            else:
                # Flush current line (rstrip handles the trailing whitespace)
                line_str = "".join(current_line_tokens).rstrip()
                if line_str:
                    lines.append(line_str)
                
                # The whitespace token itself is dropped because it's leading whitespace 
                # for a new line (unless it's the very first line, but we handle that via leading_ws)
                current_line_tokens = []
                current_line_len = 0
            continue

        # If the token is a word
        if not current_line_tokens:
            if len(token) <= width:
                current_line_tokens.append(token)
                current_line_len += len(token)
            else:
                # Word longer than width: break it into chunks
                for i in range(0, len(token), width):
                    chunk = token[i:i+width]
                    lines.append(chunk)
                current_line_tokens = []
                current_line_len = 0
        else:
            # Check if adding this word exceeds width
            if current_line_len + len(token) <= width:
                current_line_tokens.append(token)
                current_line_len += len(token)
            else:
                # Flush current line (rstrip handles trailing whitespace)
                line_str = "".join(current_line_tokens).rstrip()
                if line_str:
                    lines.append(line_str)
                
                # Start new line with this word
                if len(token) <= width:
                    current_line_tokens = [token]
                    current_line_len = len(token)
                else:
                    # Break the long word
                    for i in range(0, len(token), width):
                        chunk = token[i:i+width]
                        lines.append(chunk)
                    current_line_tokens = []
                    current_line_len = 0

    # Final flush
    if current_line_tokens:
        line_str = "".join(current_line_tokens).rstrip()
        if line_str:
            lines.append(line_str)

    # Prepend leading whitespace to the first line
    if lines:
        lines[0] = leading_ws + lines[0]
    
    return lines
