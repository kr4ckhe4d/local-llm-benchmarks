def urljoin_(base, url):
    """Reproduce urllib.parse.urljoin from scratch following RFC 3986."""
    
    def parse_url(url):
        """Parse a URL into components: (scheme, authority, path, query, fragment)."""
        # Split off fragment
        if '#' in url:
            url, fragment = url.split('#', 1)
        else:
            fragment = None
        
        # Split off query
        if '?' in url:
            url, query = url.split('?', 1)
        else:
            query = None
        
        # Split off scheme
        scheme = None
        if ':' in url:
            potential_scheme, rest = url.split(':', 1)
            # Check if it looks like a valid scheme (starts with alpha, contains only valid chars)
            if potential_scheme and potential_scheme[0].isalpha() and all(c.isalnum() or c in '+-.' for c in potential_scheme):
                scheme = potential_scheme
                url = rest
            else:
                # Not a valid scheme, treat as part of path
                pass
        
        # Check for authority (starts with //)
        authority = None
        if url.startswith('//'):
            # Authority follows
            rest = url[2:]
            # Find end of authority: next /, ?, or # (but ? and # already removed)
            idx = rest.find('/')
            if idx == -1:
                authority = rest
                path = ''
            else:
                authority = rest[:idx]
                path = rest[idx:]
        else:
            path = url
        
        return (scheme, authority, path, query, fragment)
    
    def remove_dot_segments(path):
        """Remove dot segments from a path per RFC 3986 Section 5.2.4."""
        if not path:
            return ''
        
        # Working through the algorithm from RFC 3986
        output = []
        input_path = path
        
        while input_path:
            # A: if input begins with '../' or './'
            if input_path.startswith('./'):
                input_path = input_path[2:]
            elif input_path.startswith('../'):
                input_path = input_path[3:]
            # B: if input begins with '/./' or '/.' at end
            elif input_path.startswith('/./'):
                input_path = '/' + input_path[3:]
            elif input_path == '/.':
                input_path = '/'
            # C: if input begins with '/../' or '/..' at end
            elif input_path.startswith('/../'):
                input_path = '/' + input_path[4:]
                if output:
                    output.pop()
            elif input_path == '/..':
                input_path = '/'
                if output:
                    output.pop()
            # D: if input is '.' or '..'
            elif input_path == '.' or input_path == '..':
                input_path = ''
            # E: if input begins with '/' followed by segment (not '.' or '..')
            else:
                # Find next '/'
                idx = input_path.find('/', 1)
                if idx == -1:
                    # No more slashes, take rest
                    output.append(input_path)
                    input_path = ''
                else:
                    output.append(input_path[:idx])
                    input_path = input_path[idx:]
        
        return ''.join(output)
    
    def merge_paths(base_path, ref_path):
        """Merge base path with relative reference path per RFC 3986."""
        if ref_path.startswith('/'):
            # Absolute path reference
            return ref_path
        
        # Relative path: append to base directory
        # Find last / in base_path
        idx = base_path.rfind('/')
        if idx != -1:
            base_dir = base_path[:idx + 1]
        else:
            base_dir = ''
        
        merged = base_dir + ref_path
        return merged
    
    def rebuild_url(scheme, authority, path, query, fragment):
        """Rebuild a URL from its components."""
        result = ''
        if scheme is not None:
            result += scheme + ':'
        if authority is not None:
            result += '//' + authority
        if path:
            result += path
        if query is not None:
            result += '?' + query
        if fragment is not None:
            result += '#' + fragment
        return result
    
    # Parse base and reference URLs
    base_scheme, base_authority, base_path, base_query, base_fragment = parse_url(base)
    ref_scheme, ref_authority, ref_path, ref_query, ref_fragment = parse_url(url)
    
    # Apply RFC 3986 Section 5.2.2 Transform References algorithm
    
    # Step 1: If ref has scheme, use it as-is (absolute URL)
    if ref_scheme is not None:
        scheme = ref_scheme
        authority = ref_authority
        path = remove_dot_segments(ref_path)
        query = ref_query
        fragment = ref_fragment
    # Step 2: If ref has authority (starts with //), use it
    elif ref_authority is not None:
        scheme = base_scheme
        authority = ref_authority
        path = remove_dot_segments(ref_path)
        query = ref_query
        fragment = ref_fragment
    else:
        # No scheme or authority in ref
        if ref_path == '':
            # Empty path reference
            scheme = base_scheme
            authority = base_authority
            path = base_path
            if ref_query is not None:
                query = ref_query
            else:
                query = base_query
            # Fragment: if ref has fragment, use it; otherwise use base fragment
            if ref_fragment is not None:
                fragment = ref_fragment
            else:
                fragment = base_fragment
        else:
            # Relative path reference
            if ref_path.startswith('/'):
                path = remove_dot_segments(ref_path)
            else:
                # Merge paths
                merged = merge_paths(base_path, ref_path)
                path = remove_dot_segments(merged)
            
            scheme = base_scheme
            authority = base_authority
            
            if ref_query is not None:
                query = ref_query
            else:
                query = base_query
            
            if ref_fragment is not None:
                fragment = ref_fragment
            else:
                fragment = base_fragment
    
    return rebuild_url(scheme, authority, path, query, fragment)
