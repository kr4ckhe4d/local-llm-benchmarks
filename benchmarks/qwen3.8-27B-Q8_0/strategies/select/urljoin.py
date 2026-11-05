def urljoin_(base, url):
    """
    Reproduce urllib.parse.urljoin behavior from scratch, following RFC 3986.
    """
    # Edge case: empty url returns base without fragment
    if url == '':
        # Remove fragment from base
        frag_idx = base.find('#')
        if frag_idx != -1:
            return base[:frag_idx]
        return base

    # Determine if url is absolute (has scheme)
    # A scheme is defined as: ALPHA *( ALPHA / DIGIT / "+" / "-" / "." ) ":"
    def has_scheme(s):
        i = 0
        if i >= len(s):
            return False
        # First char must be alpha
        if not (s[i].isalpha()):
            return False
        i += 1
        while i < len(s):
            c = s[i]
            if c.isalpha() or c.isdigit() or c in '+-.':
                i += 1
            elif c == ':':
                return True
            else:
                return False
        return False

    # If url has a scheme, it's absolute
    if has_scheme(url):
        return url

    # Now url is relative. We need to parse base and url.
    # Parse a URL into components: scheme, authority, path, query, fragment
    def parse_url(s):
        # Returns dict with keys: scheme, authority, path, query, fragment
        # scheme may be None if not present
        result = {
            'scheme': None,
            'authority': None,
            'path': '',
            'query': None,
            'fragment': None
        }
        
        rest = s
        
        # Check for scheme
        if has_scheme(rest):
            colon_idx = rest.index(':')
            result['scheme'] = rest[:colon_idx]
            rest = rest[colon_idx + 1:]
        
        # Check for authority (starts with //)
        if rest.startswith('//'):
            rest = rest[2:]
            # Authority ends at first '/', '?', or '#'
            end_idx = len(rest)
            for i, c in enumerate(rest):
                if c in '/?#':
                    end_idx = i
                    break
            result['authority'] = rest[:end_idx]
            rest = rest[end_idx:]
        
        # Now rest starts with path, query, or fragment
        # Path goes until first '?' or '#'
        path_end = len(rest)
        for i, c in enumerate(rest):
            if c in '?#':
                path_end = i
                break
        result['path'] = rest[:path_end]
        rest = rest[path_end:]
        
        # Query goes until first '#'
        if rest.startswith('?'):
            rest = rest[1:]
            frag_idx = rest.find('#')
            if frag_idx != -1:
                result['query'] = rest[:frag_idx]
                rest = rest[frag_idx:]
            else:
                result['query'] = rest
                rest = ''
        
        # Fragment
        if rest.startswith('#'):
            result['fragment'] = rest[1:]
        
        return result

    base_parts = parse_url(base)
    url_parts = parse_url(url)

    # RFC 3986 Section 5.2.2: Transformations
    # If R has a scheme, use R's scheme, authority, path, query, fragment
    # But we already handled absolute URLs above, so url_parts['scheme'] is None

    # If R has an authority:
    if url_parts['authority'] is not None:
        result_scheme = base_parts['scheme']
        result_authority = url_parts['authority']
        result_path = url_parts['path']
        result_query = url_parts['query']
        result_fragment = url_parts['fragment']
    else:
        # If R has no authority
        result_scheme = base_parts['scheme']
        result_authority = base_parts['authority']
        
        if url_parts['path'] == '':
            # R's path is empty
            result_path = base_parts['path']
            if url_parts['query'] is not None:
                result_query = url_parts['query']
            else:
                result_query = base_parts['query']
            result_fragment = url_parts['fragment']
        else:
            # R has a path
            if url_parts['path'].startswith('/'):
                # Absolute path
                result_path = url_parts['path']
            else:
                # Relative path: merge with base path
                if result_authority is not None and base_parts['path'] == '':
                    # If base has authority but no path, use '/' as base path
                    merged = '/' + url_parts['path']
                else:
                    # Merge: take base path up to last '/', append R path
                    last_slash = base_parts['path'].rfind('/')
                    if last_slash != -1:
                        merged = base_parts['path'][:last_slash + 1] + url_parts['path']
                    else:
                        merged = url_parts['path']
                result_path = merged
            result_query = url_parts['query']
            result_fragment = url_parts['fragment']

    # Normalize the path (remove dot segments) per RFC 3986 Section 5.2.4
    def remove_dot_segments(path):
        # RFC 3986 Section 5.2.4
        output = []
        input_list = path.split('/')
        # We need to handle the path carefully
        # Actually, let's use the algorithm from RFC
        # input = path
        # output = []
        # while input:
        #   if input starts with "../" or "./":
        #     input = input[3:] or input[2:]
        #   elif input starts with "/./" or input == "/.":
        #     input = "/" + input[3:] or "/"
        #   elif input starts with "/../" or input == "/..":
        #     input = "/" + input[4:] or "/"
        #     output.pop()
        #   elif input == "." or input == "..":
        #     input = ""
        #   else:
        #     if input starts with "/" or input starts with "//":
        #       # Move the first path segment (including initial "/" if any) to output
        #       if input.startswith('//'):
        #         # Find next '/'
        #         idx = input.find('/', 2)
        #         if idx == -1:
        #           output.append(input)
        #           input = ""
        #         else:
        #           output.append(input[:idx])
        #           input = input[idx:]
        #       else:
        #         idx = input.find('/')
        #         if idx == -1:
        #           output.append(input)
        #           input = ""
        #         else:
        #           output.append(input[:idx])
        #           input = input[idx:]
        # return "".join(output)
        
        # Let me implement this more carefully
        inp = path
        out = []
        
        while inp:
            if inp.startswith('../'):
                inp = inp[3:]
            elif inp.startswith('./'):
                inp = inp[2:]
            elif inp.startswith('/./'):
                inp = '/' + inp[3:]
            elif inp == '/.':
                inp = '/'
            elif inp.startswith('/../'):
                inp = '/' + inp[4:]
                if out:
                    out.pop()
            elif inp == '/..':
                inp = '/'
                if out:
                    out.pop()
            elif inp == '.' or inp == '..':
                inp = ''
            else:
                # Move first path segment to output
                if inp.startswith('//'):
                    idx = inp.find('/', 2)
                    if idx == -1:
                        out.append(inp)
                        inp = ''
                    else:
                        out.append(inp[:idx])
                        inp = inp[idx:]
                elif inp.startswith('/'):
                    idx = inp.find('/', 1)
                    if idx == -1:
                        out.append(inp)
                        inp = ''
                    else:
                        out.append(inp[:idx])
                        inp = inp[idx:]
                else:
                    # No leading slash, so the whole remaining is one segment
                    # But wait, this case shouldn't happen if we're handling properly
                    # Actually for non-absolute paths during merge, we might have this
                    idx = inp.find('/')
                    if idx == -1:
                        out.append(inp)
                        inp = ''
                    else:
                        out.append(inp[:idx])
                        inp = inp[idx:]
        
        return ''.join(out)

    result_path = remove_dot_segments(result_path)

    # Reconstruct the URL
    result = ''
    if result_scheme is not None:
        result += result_scheme + ':'
    if result_authority is not None:
        result += '//' + result_authority
    result += result_path
    if result_query is not None:
        result += '?' + result_query
    if result_fragment is not None:
        result += '#' + result_fragment

    return result
