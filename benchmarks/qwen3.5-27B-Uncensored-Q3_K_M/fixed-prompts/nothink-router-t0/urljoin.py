def urljoin_(base, url):
    if not url:
        # Empty string returns base without its fragment
        if '#' in base:
            return base.split('#')[0]
        return base

    # Parse base components
    base_scheme = ''
    base_netloc = ''
    base_path = ''
    base_query = ''
    base_fragment = ''

    if base:
        # Extract scheme
        if ':' in base:
            scheme_part, rest = base.split(':', 1)
            base_scheme = scheme_part
            # Check if it's a scheme or just a colon in path (RFC 3986)
            if not rest.startswith('//'):
                # If no // after colon, it might be a path with colon, but standard urljoin treats first : as scheme
                # However, strict RFC 3986 says scheme must be followed by // or nothing for absolute URI.
                # For urljoin behavior: if base has scheme, we treat it as absolute unless url is absolute.
                pass
        else:
            rest = base
        
        # Extract netloc (host)
        if rest.startswith('//'):
            rest = rest[2:]
            if '/' in rest:
                netloc_part, rest = rest.split('/', 1)
                base_netloc = netloc_part
                base_path = '/' + rest
            else:
                base_netloc = rest
                base_path = ''
        else:
            # No netloc, rest is path/query/fragment
            if '/' in rest:
                path_part, rest = rest.split('/', 1)
                base_path = '/' + path_part + '/' + rest
            else:
                base_path = '/' + rest
        
        # Split path, query, fragment
        if '?' in base_path:
            base_path, base_query = base_path.split('?', 1)
        if '#' in base_path:
            base_path, base_fragment = base_path.split('#', 1)
        elif '#' in base_query:
            base_query, base_fragment = base_query.split('#', 1)
        else:
            base_fragment = ''

    # Parse url components
    url_scheme = ''
    url_netloc = ''
    url_path = ''
    url_query = ''
    url_fragment = ''

    if url.startswith('//'):
        # Scheme-relative
        url_netloc = url[2:]
        if '/' in url_netloc:
            url_netloc, url_path = url_netloc.split('/', 1)
            url_path = '/' + url_path
        else:
            url_path = ''
    elif url.startswith('/'):
        # Absolute path
        url_path = url
    elif url.startswith('?'):
        # Query-only
        url_query = url[1:]
    elif url.startswith('#'):
        # Fragment-only
        url_fragment = url[1:]
    else:
        # Relative path or full URL
        if ':' in url and not url.startswith('.'):
            # Check if it's a scheme
            scheme_part, rest = url.split(':', 1)
            if not rest.startswith('//'):
                # It's a path with a colon, not a scheme
                url_path = url
            else:
                url_scheme = scheme_part
                url_netloc = rest.split('/', 1)[0] if '/' in rest else rest
                url_path = '/' + rest.split('/', 1)[1] if '/' in rest else ''
        else:
            url_path = url

    # Determine result components
    if url_scheme:
        # Absolute URL: replace everything
        result = f"{url_scheme}:{url_netloc}{url_path}"
        if url_query: result += f"?{url_query}"
        if url_fragment: result += f"#{url_fragment}"
        return result
    elif url_netloc:
        # Scheme-relative: replace netloc and path
        result = f"{base_scheme}:{url_netloc}{url_path}"
        if url_query: result += f"?{url_query}"
        elif base_query: result += f"?{base_query}"
        if url_fragment: result += f"#{url_fragment}"
        elif base_fragment: result += f"#{base_fragment}"
        return result
    elif url_path.startswith('/'):
        # Absolute path: replace path
        result = f"{base_scheme}:{base_netloc}{url_path}"
        if url_query: result += f"?{url_query}"
        elif base_query: result += f"?{base_query}"
        if url_fragment: result += f"#{url_fragment}"
        elif base_fragment: result += f"#{base_fragment}"
        return result
    else:
        # Relative path: append to base path
        # Normalize base path
        if not base_path:
            base_path = '/'
        if not base_path.endswith('/'):
            # If base path is not a directory (no trailing slash), remove last segment
            if '/' in base_path:
                base_path = base_path.rsplit('/', 1)[0] + '/'
            else:
                base_path = '/'
        
        full_path = base_path + url_path
        # Normalize . and ..
        segments = full_path.split('/')
        normalized = []
        for seg in segments:
            if seg == '.':
                continue
            elif seg == '..':
                if normalized and normalized[-1] != '':
                    normalized.pop()
            else:
                normalized.append(seg)
        
        # Reconstruct path
        if not normalized:
            result_path = '/'
        else:
            result_path = '/'.join(normalized)
            if not result_path.startswith('/'):
                result_path = '/' + result_path
        
        result = f"{base_scheme}:{base_netloc}{result_path}"
        if url_query: result += f"?{url_query}"
        elif base_query: result += f"?{base_query}"
        if url_fragment: result += f"#{url_fragment}"
        elif base_fragment: result += f"#{base_fragment}"
        return result
