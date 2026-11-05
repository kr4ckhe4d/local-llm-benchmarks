def urljoin_(base, url):
    """
    Reproduce urllib.parse.urljoin behavior from scratch per RFC 3986.
    """
    # Helper: parse a URL into components
    def parse_url(u):
        if not u:
            return None
        # Check for scheme
        scheme = None
        rest = u
        if ':' in u:
            # Find first colon
            idx = u.index(':')
            potential_scheme = u[:idx]
            # Scheme must start with a letter and contain only letters, digits, +, -, .
            if potential_scheme and potential_scheme[0].isalpha():
                valid = True
                for c in potential_scheme[1:]:
                    if not (c.isalnum() or c in '+-.'):
                        valid = False
                        break
                if valid:
                    scheme = potential_scheme
                    rest = u[idx + 1:]
        
        # Now parse rest
        netloc = None
        path = ''
        query = None
        fragment = None
        
        # Check for fragment
        if '#' in rest:
            hash_idx = rest.index('#')
            fragment = rest[hash_idx + 1:]
            rest = rest[:hash_idx]
        
        # Check for query
        if '?' in rest:
            q_idx = rest.index('?')
            query = rest[q_idx + 1:]
            rest = rest[:q_idx]
        
        # Check for netloc
        if rest.startswith('//'):
            # Find end of netloc
            netloc_end = len(rest)
            for i, c in enumerate(rest[2:], start=2):
                if c in '/?#':
                    netloc_end = i
                    break
            netloc = rest[2:netloc_end]
            rest = rest[netloc_end:]
        
        path = rest
        
        return {
            'scheme': scheme,
            'netloc': netloc,
            'path': path,
            'query': query,
            'fragment': fragment
        }
    
    # Helper: remove_dot_segments per RFC 3986 section 5.2.4
    def remove_dot_segments(path):
        if not path:
            return path
        input_buffer = path
        output_buffer = ''
        
        while input_buffer:
            # A. If the input buffer begins with a prefix of "../" or "./", then remove that prefix from the input buffer; otherwise,
            # B. If the input buffer begins with a prefix of "/./" or "/.", where "." is a complete path segment, then replace that prefix with "/" in the input buffer; otherwise,
            # C. If the input buffer begins with a prefix of "/../" or "/..", where ".." is a complete path segment, then replace that prefix with "/" in the input buffer and remove the last segment and any preceding "/" (if any) from the output buffer; otherwise,
            # D. If the input buffer consists only of "." or "..", then remove that from the input buffer; otherwise,
            # E. move the first path segment in the input buffer to the end of the output buffer, including the initial "/" character (if any) and any subsequent characters up to, but not including, the next "/" character or the end of the input buffer.
            # F. If the input buffer is not empty, then remove the first character from the input buffer, which must be a "/" character.
            
            if input_buffer.startswith('../'):
                input_buffer = input_buffer[3:]
            elif input_buffer.startswith('./'):
                input_buffer = input_buffer[2:]
            elif input_buffer.startswith('/./'):
                input_buffer = '/' + input_buffer[3:]
            elif input_buffer == '/.':
                input_buffer = '/'
            elif input_buffer.startswith('/../'):
                input_buffer = '/' + input_buffer[4:]
                # Remove last segment from output
                if output_buffer:
                    last_slash = output_buffer.rfind('/')
                    if last_slash > 0:
                        output_buffer = output_buffer[:last_slash]
                    else:
                        output_buffer = ''
            elif input_buffer == '/..':
                input_buffer = '/'
                if output_buffer:
                    last_slash = output_buffer.rfind('/')
                    if last_slash > 0:
                        output_buffer = output_buffer[:last_slash]
                    else:
                        output_buffer = ''
            elif input_buffer == '.' or input_buffer == '..':
                input_buffer = ''
            else:
                # E. Move first path segment to output
                if input_buffer.startswith('/'):
                    next_slash = input_buffer.find('/', 1)
                    if next_slash == -1:
                        output_buffer += input_buffer
                        input_buffer = ''
                    else:
                        output_buffer += input_buffer[:next_slash]
                        input_buffer = input_buffer[next_slash:]
                else:
                    next_slash = input_buffer.find('/')
                    if next_slash == -1:
                        output_buffer += input_buffer
                        input_buffer = ''
                    else:
                        output_buffer += input_buffer[:next_slash]
                        input_buffer = input_buffer[next_slash:]
        
        return output_buffer
    
    # Parse base
    base_parsed = parse_url(base)
    if base_parsed is None:
        base_parsed = {'scheme': None, 'netloc': None, 'path': '', 'query': None, 'fragment': None}
    
    # Parse url
    url_parsed = parse_url(url)
    if url_parsed is None:
        url_parsed = {'scheme': None, 'netloc': None, 'path': '', 'query': None, 'fragment': None}
    
    # RFC 3986 section 5.2: Combining references
    # If the reference URI has a scheme:
    if url_parsed['scheme'] is not None:
        # The reference is absolute; use it as-is
        target = url_parsed
    else:
        # Otherwise, the reference is relative; combine with base
        target = {
            'scheme': base_parsed['scheme'],
            'netloc': base_parsed['netloc'],
            'path': base_parsed['path'],
            'query': base_parsed['query'],
            'fragment': base_parsed['fragment']
        }
        
        # If the reference has a network location:
        if url_parsed['netloc'] is not None:
            target['netloc'] = url_parsed['netloc']
            target['path'] = remove_dot_segments(url_parsed['path'])
            target['query'] = url_parsed['query']
        else:
            # If the reference is empty:
            if not url_parsed['path'] and url_parsed['query'] is None and url_parsed['fragment'] is None:
                # The target is the same as the base, but with the fragment removed
                target['fragment'] = None
            else:
                # If the reference consists solely of a fragment:
                if not url_parsed['path'] and url_parsed['query'] is None and url_parsed['fragment'] is not None:
                    target['fragment'] = url_parsed['fragment']
                # If the reference has a query but no path:
                elif not url_parsed['path'] and url_parsed['query'] is not None:
                    target['path'] = base_parsed['path']
                    target['query'] = url_parsed['query']
                # If the reference path is absolute:
                elif url_parsed['path'] and url_parsed['path'].startswith('/'):
                    target['path'] = remove_dot_segments(url_parsed['path'])
                    target['query'] = url_parsed['query']
                # Otherwise, merge paths:
                else:
                    # If the base URI has a network location and an empty path:
                    if base_parsed['netloc'] is not None and not base_parsed['path']:
                        target['path'] = '/' + url_parsed['path']
                    else:
                        # Take the base path up to the last slash
                        last_slash = base_parsed['path'].rfind('/')
                        if last_slash >= 0:
                            base_dir = base_parsed['path'][:last_slash + 1]
                        else:
                            base_dir = ''
                        target['path'] = base_dir + url_parsed['path']
                    target['path'] = remove_dot_segments(target['path'])
                    target['query'] = url_parsed['query']
        
        # Fragment logic: if reference has fragment, use it; else keep base's fragment
        # Except when reference is empty, fragment is None
        if url_parsed['fragment'] is not None:
            target['fragment'] = url_parsed['fragment']
        else:
            if not url_parsed['path'] and url_parsed['query'] is None and url_parsed['fragment'] is None:
                target['fragment'] = None
            else:
                target['fragment'] = base_parsed['fragment']
    
    # Now construct the URL string
    parts = []
    if target['scheme'] is not None:
        parts.append(target['scheme'] + ':')
    if target['netloc'] is not None:
        parts.append('//')
        parts.append(target['netloc'])
    parts.append(target['path'])
    if target['query'] is not None:
        parts.append('?' + target['query'])
    if target['fragment'] is not None:
        parts.append('#' + target['fragment'])
    
    return ''.join(parts)

