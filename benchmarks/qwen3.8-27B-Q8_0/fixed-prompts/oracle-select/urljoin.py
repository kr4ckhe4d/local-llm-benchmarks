def urljoin_(base, url):
    """
    Reproduce urllib.parse.urljoin from scratch, implementing RFC 3986 reference resolution.
    """
    if not base:
        return url

    # Parse the base URL into components
    base_scheme, base_netloc, base_path, base_query, base_fragment = _parse_url(base)
    
    # Parse the reference URL into components
    ref_scheme, ref_netloc, ref_path, ref_query, ref_fragment = _parse_url(url)

    # If the reference has a scheme, it's an absolute URL
    if ref_scheme:
        return _build_url(ref_scheme, ref_netloc, ref_path, ref_query, ref_fragment)

    # If the reference has a netloc, it's scheme-relative or absolute path with host
    if ref_netloc:
        # Use base's scheme if ref doesn't have one
        scheme = base_scheme
        return _build_url(scheme, ref_netloc, ref_path, ref_query, ref_fragment)

    # If the reference path is empty
    if not ref_path:
        # If there's a query, use base's path and the new query
        if ref_query:
            return _build_url(base_scheme, base_netloc, base_path, ref_query, ref_fragment)
        # If there's only a fragment, use base's path and query, and the new fragment
        if ref_fragment:
            return _build_url(base_scheme, base_netloc, base_path, base_query, ref_fragment)
        # Empty reference: return base without fragment
        return _build_url(base_scheme, base_netloc, base_path, base_query, base_fragment)

    # If the reference path starts with '/', it's an absolute path
    if ref_path.startswith('/'):
        return _build_url(base_scheme, base_netloc, ref_path, ref_query, ref_fragment)

    # Relative path: merge with base path
    # Remove the last segment of base path
    if base_path:
        # Find the last '/' in base path
        last_slash = base_path.rfind('/')
        if last_slash != -1:
            base_dir = base_path[:last_slash + 1]
        else:
            base_dir = '/'
    else:
        base_dir = '/'

    # Merge base_dir with ref_path
    merged_path = base_dir + ref_path

    # Normalize the path (remove . and ..)
    normalized_path = _normalize_path(merged_path)

    return _build_url(base_scheme, base_netloc, normalized_path, ref_query, ref_fragment)


def _parse_url(url):
    """
    Parse a URL into (scheme, netloc, path, query, fragment).
    """
    scheme = ''
    netloc = ''
    path = ''
    query = ''
    fragment = ''

    # Remove fragment
    if '#' in url:
        url, fragment = url.split('#', 1)

    # Remove query
    if '?' in url:
        url, query = url.split('?', 1)

    # Check for scheme
    # Scheme is defined as: ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
    # followed by ':'
    i = 0
    if i < len(url) and url[i].isalpha():
        j = i + 1
        while j < len(url) and (url[j].isalnum() or url[j] in '+-.'):
            j += 1
        if j < len(url) and url[j] == ':':
            scheme = url[i:j]
            url = url[j+1:]
            i = 0

    # Check for netloc (starts with //)
    if url.startswith('//'):
        url = url[2:]
        # Netloc ends at the next '/', '?', or '#'
        # But we've already stripped query and fragment
        slash_idx = url.find('/')
        if slash_idx == -1:
            netloc = url
            url = ''
        else:
            netloc = url[:slash_idx]
            url = url[slash_idx:]

    # The rest is the path
    path = url

    return scheme, netloc, path, query, fragment


def _normalize_path(path):
    """
    Normalize a path by removing '.' and '..' segments, and collapsing multiple slashes.
    """
    if not path:
        return path

    # Determine if the path is absolute
    is_absolute = path.startswith('/')

    # Split into segments, filtering out empty strings (which come from //)
    # But we need to be careful about preserving the structure
    segments = path.split('/')
    
    # Filter out empty segments that result from double slashes
    # But keep track of whether the path ends with a slash
    ends_with_slash = path.endswith('/') and len(path) > 1

    # For absolute paths, the first segment is empty
    if is_absolute:
        output = []
        for segment in segments[1:]:
            if segment == '':
                continue
            elif segment == '.':
                continue
            elif segment == '..':
                if output:
                    output.pop()
            else:
                output.append(segment)
        
        # Reconstruct
        if output:
            normalized = '/' + '/'.join(output)
        else:
            normalized = '/'
        
        # Preserve trailing slash if original had one and we didn't end up at root
        if ends_with_slash and not normalized.endswith('/'):
            normalized += '/'
        
        return normalized
    else:
        output = []
        for segment in segments:
            if segment == '':
                continue
            elif segment == '.':
                continue
            elif segment == '..':
                if output:
                    output.pop()
            else:
                output.append(segment)
        
        # Reconstruct
        if output:
            normalized = '/'.join(output)
        else:
            normalized = ''
        
        # Preserve trailing slash if original had one
        if ends_with_slash and normalized and not normalized.endswith('/'):
            normalized += '/'
        
        return normalized


def _build_url(scheme, netloc, path, query, fragment):
    """
    Build a URL from components.
    """
    result = ''
    
    if scheme:
        result += scheme + ':'
    
    if netloc:
        result += '//' + netloc
    
    result += path
    
    if query:
        result += '?' + query
    
    if fragment:
        result += '#' + fragment
    
    return result
