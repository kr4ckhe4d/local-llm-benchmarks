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
        return _build_url(base_scheme, ref_netloc, ref_path, ref_query, ref_fragment)

    # If the reference path is empty
    if not ref_path:
        # If the reference has a query, use base path with new query
        if ref_query is not None:
            return _build_url(base_scheme, base_netloc, base_path, ref_query, ref_fragment)
        # If the reference has only a fragment, use base without fragment
        if ref_fragment is not None:
            return _build_url(base_scheme, base_netloc, base_path, base_query, ref_fragment)
        # Empty reference: return base without fragment
        return _build_url(base_scheme, base_netloc, base_path, base_query, None)

    # If the reference path starts with '/', it's an absolute path
    if ref_path.startswith('/'):
        return _build_url(base_scheme, base_netloc, ref_path, ref_query, ref_fragment)

    # Relative path: merge with base path
    # Remove the last segment of the base path
    if base_path:
        # Find the last '/' in base_path
        last_slash = base_path.rfind('/')
        if last_slash != -1:
            merged_path = base_path[:last_slash + 1] + ref_path
        else:
            merged_path = ref_path
    else:
        merged_path = ref_path

    # Normalize the path (remove . and ..)
    normalized_path = _normalize_path(merged_path)

    return _build_url(base_scheme, base_netloc, normalized_path, ref_query, ref_fragment)


def _parse_url(url):
    """
    Parse a URL into (scheme, netloc, path, query, fragment).
    Returns None for missing components.
    """
    scheme = None
    netloc = None
    path = ''
    query = None
    fragment = None

    # Extract fragment
    if '#' in url:
        url, fragment = url.split('#', 1)

    # Extract query
    if '?' in url:
        url, query = url.split('?', 1)

    # Extract scheme
    if ':' in url:
        # Check if it's a valid scheme (must be before any '/' or '?')
        colon_pos = url.index(':')
        # Scheme must be at the beginning and followed by valid scheme chars
        potential_scheme = url[:colon_pos]
        if potential_scheme and all(c.isalnum() or c in '+-.' for c in potential_scheme):
            scheme = potential_scheme
            url = url[colon_pos + 1:]

    # Extract netloc
    if url.startswith('//'):
        url = url[2:]
        # Netloc ends at the next '/', '?', or '#'
        end_pos = len(url)
        for i, c in enumerate(url):
            if c in '/?#':
                end_pos = i
                break
        netloc = url[:end_pos]
        url = url[end_pos:]

    # The rest is the path
    path = url

    return scheme, netloc, path, query, fragment


def _normalize_path(path):
    """
    Normalize a path by removing '.' and '..' segments.
    """
    if not path:
        return path

    # Split into segments
    segments = path.split('/')
    output = []

    for segment in segments:
        if segment == '.':
            continue
        elif segment == '..':
            if output and output[-1] != '':
                output.pop()
            # If we're at the root, '..' is ignored
        else:
            output.append(segment)

    # Rejoin
    normalized = '/'.join(output)

    # Preserve leading slash
    if path.startswith('/') and not normalized.startswith('/'):
        normalized = '/' + normalized

    # Preserve trailing slash if the original path ended with '/' and we have segments
    if path.endswith('/') and not normalized.endswith('/') and normalized:
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

    if query is not None:
        result += '?' + query

    if fragment is not None:
        result += '#' + fragment

    return result
