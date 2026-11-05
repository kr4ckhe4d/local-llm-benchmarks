def urljoin_(base, url):
    """
    Resolve a URL reference against a base URL according to RFC 3986.
    """
    if not url:
        # Empty reference: return base without fragment
        if '#' in base:
            return base[:base.index('#')]
        return base

    # Helper to parse a URL into components
    def parse_url(u):
        scheme = None
        netloc = None
        path = ''
        query = None
        fragment = None

        # Extract fragment
        if '#' in u:
            u, fragment = u.split('#', 1)

        # Extract query
        if '?' in u:
            idx = u.find('?')
            u, query = u[:idx], u[idx+1:]

        # Extract scheme
        i = 0
        n = len(u)
        if i < n and (u[i].isalpha()):
            j = i + 1
            while j < n and (u[j].isalnum() or u[j] in '+-.'):
                j += 1
            if j < n and u[j] == ':':
                scheme = u[i:j]
                u = u[j+1:]

        if scheme is not None:
            if u.startswith('//'):
                u = u[2:]
                idx = u.find('/')
                if idx == -1:
                    netloc = u
                    path = ''
                else:
                    netloc = u[:idx]
                    path = u[idx:]
            else:
                path = u
                netloc = None
        else:
            if u.startswith('//'):
                u = u[2:]
                idx = u.find('/')
                if idx == -1:
                    netloc = u
                    path = ''
                else:
                    netloc = u[:idx]
                    path = u[idx:]
            else:
                path = u
                netloc = None

        return scheme, netloc, path, query, fragment

    def remove_dot_segments(path):
        """
        Remove dot segments from a path per RFC 3986 Section 5.2.4
        """
        if not path:
            return path

        # Split by '/'
        segments = path.split('/')
        output = []
        
        for seg in segments:
            if seg == '.':
                continue
            elif seg == '..':
                if output and output[-1] != '':
                    output.pop()
            else:
                output.append(seg)
        
        result = '/'.join(output)
        
        # Ensure leading slash is preserved if original had one
        if path.startswith('/') and not result.startswith('/'):
            result = '/' + result
        
        # If the path ended with a dot segment (like '.' or '..'), we need to ensure trailing slash
        last_seg = segments[-1]
        if last_seg in ('.', '..'):
            if not result.endswith('/'):
                result += '/'
        
        return result

    def merge_paths(base_path, ref_path):
        """
        Merge base path and reference path per RFC 3986 Section 5.2.2
        """
        if base_path:
            if base_path.endswith('/'):
                merged = base_path + ref_path
            else:
                idx = base_path.rfind('/')
                if idx == -1:
                    merged = ref_path
                else:
                    merged = base_path[:idx+1] + ref_path
        else:
            merged = ref_path
        return merged

    # Parse base and url
    base_scheme, base_netloc, base_path, base_query, base_fragment = parse_url(base)
    ref_scheme, ref_netloc, ref_path, ref_query, ref_fragment = parse_url(url)

    # RFC 3986 Section 5.3: Transform References
    if ref_scheme is not None:
        new_scheme = ref_scheme
        new_netloc = ref_netloc
        new_path = ref_path
        new_query = ref_query
        new_fragment = ref_fragment
    else:
        if ref_netloc is not None:
            new_scheme = base_scheme
            new_netloc = ref_netloc
            new_path = ref_path
            new_query = ref_query
            new_fragment = ref_fragment
        else:
            new_scheme = base_scheme
            new_netloc = base_netloc
            
            if not ref_path:
                new_path = base_path
                if ref_query is not None:
                    new_query = ref_query
                else:
                    new_query = base_query
                new_fragment = ref_fragment
            else:
                if ref_path.startswith('/'):
                    new_path = ref_path
                else:
                    new_path = merge_paths(base_path, ref_path)
                new_query = ref_query
                new_fragment = ref_fragment

    # Normalize path: remove dot segments
    if new_path:
        new_path = remove_dot_segments(new_path)

    # Construct the result
    result = ''
    if new_scheme is not None:
        result += new_scheme + ':'
    
    if new_netloc is not None:
        result += '//' + new_netloc
    
    result += new_path
    
    if new_query is not None:
        result += '?' + new_query
    
    if new_fragment is not None:
        result += '#' + new_fragment

    return result
