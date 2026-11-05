def urljoin_(base, url):
    """
    Reproduce urllib.parse.urljoin from scratch without importing urllib.
    Implements RFC 3986 reference resolution.
    """
    def split_url(u):
        """
        Split a URL into (scheme, netloc, path, query, fragment).
        Returns tuple with empty strings for missing parts.
        """
        u = u.strip()
        if not u:
            return ('', '', '', '', '')
        
        scheme = ''
        netloc = ''
        path = ''
        query = ''
        fragment = ''
        
        # Extract fragment
        if '#' in u:
            idx = u.index('#')
            fragment = u[idx+1:]
            u = u[:idx]
        
        # Extract query
        if '?' in u:
            idx = u.index('?')
            query = u[idx+1:]
            u = u[:idx]
        
        # Extract scheme
        if ':' in u:
            idx = u.index(':')
            # Check if it's a valid scheme (letters, digits, +, -, .)
            scheme_candidate = u[:idx]
            if scheme_candidate and all(c.isalnum() or c in '+-.' for c in scheme_candidate) and scheme_candidate[0].isalpha():
                scheme = scheme_candidate
                u = u[idx+1:]
        
        # Extract netloc
        if u.startswith('//'):
            # Find end of netloc
            rest = u[2:]
            # Netloc ends at '/', '?', or '#'
            end_idx = len(rest)
            for i, c in enumerate(rest):
                if c in '/?#':
                    end_idx = i
                    break
            netloc = rest[:end_idx]
            u = rest[end_idx:]
        
        # Remaining is path
        path = u
        
        return (scheme, netloc, path, query, fragment)
    
    def remove_dot_segments(path):
        """
        Remove dot segments from a path as per RFC 3986 section 5.2.4.
        """
        if not path:
            return path
        
        # Handle leading slash
        leading_slash = path.startswith('/')
        segments = path.split('/')
        output = []
        
        for segment in segments:
            if segment == '.':
                continue
            elif segment == '..':
                if output and output[-1] != '':
                    output.pop()
                # If nothing to pop, ignore (or keep if it's the root)
            else:
                output.append(segment)
        
        result = '/'.join(output)
        
        if leading_slash:
            if not result:
                return '/'
            return '/' + result
        else:
            return result
    
    def merge_paths(base_path, relative_path):
        """
        Merge base path with relative path as per RFC 3986 section 5.2.2.
        """
        if base_path:
            # Take base path up to (but not including) last slash
            last_slash = base_path.rfind('/')
            if last_slash != -1:
                base_dir = base_path[:last_slash+1]
            else:
                base_dir = ''
            return base_dir + relative_path
        else:
            return relative_path
    
    # Parse base and url
    base_scheme, base_netloc, base_path, base_query, base_fragment = split_url(base)
    url_scheme, url_netloc, url_path, url_query, url_fragment = split_url(url)
    
    # Handle empty url: return base without fragment
    if not url:
        result = ''
        if base_scheme:
            result += base_scheme + ':'
        if base_netloc:
            result += '//' + base_netloc
        if base_path:
            result += base_path
        if base_query:
            result += '?' + base_query
        # No fragment
        return result
    
    # Determine if url is absolute
    if url_scheme:
        # Absolute URL: use url's scheme, netloc, path, query, fragment
        result = url_scheme + ':'
        if url_netloc:
            result += '//' + url_netloc
        result += url_path
        if url_query:
            result += '?' + url_query
        if url_fragment:
            result += '#' + url_fragment
        return result
    
    # Scheme-relative or relative
    if url_netloc:
        # Scheme-relative: //host/path
        result = ''
        if base_scheme:
            result += base_scheme + ':'
        result += '//' + url_netloc
        result += url_path
        if url_query:
            result += '?' + url_query
        if url_fragment:
            result += '#' + url_fragment
        return result
    
    # No scheme, no netloc in url
    if url_path:
        if url_path.startswith('/'):
            # Absolute path
            result = ''
            if base_scheme:
                result += base_scheme + ':'
            if base_netloc:
                result += '//' + base_netloc
            # Normalize the path
            result += remove_dot_segments(url_path)
            if url_query:
                result += '?' + url_query
            if url_fragment:
                result += '#' + url_fragment
            return result
        else:
            # Relative path
            merged_path = merge_paths(base_path, url_path)
            merged_path = remove_dot_segments(merged_path)
            result = ''
            if base_scheme:
                result += base_scheme + ':'
            if base_netloc:
                result += '//' + base_netloc
            result += merged_path
            if url_query:
                result += '?' + url_query
            elif base_query:
                result += '?' + base_query
            if url_fragment:
                result += '#' + url_fragment
            return result
    
    # No path in url
    if url_query is not None or '?' in url or url_fragment is not None or '#' in url:
        # Query-only or fragment-only
        # Actually, we need to check the original url string for ? or #
        pass
    
    # Check if url has query but no path
    if url_query or url_fragment:
        # Use base path, and url's query/fragment
        result = ''
        if base_scheme:
            result += base_scheme + ':'
        if base_netloc:
            result += '//' + base_netloc
        if base_path:
            result += base_path
        if url_query:
            result += '?' + url_query
        else:
            if base_query:
                result += '?' + base_query
        if url_fragment:
            result += '#' + url_fragment
        return result
    
    # Fallback: return base without fragment
    result = ''
    if base_scheme:
        result += base_scheme + ':'
    if base_netloc:
        result += '//' + base_netloc
    if base_path:
        result += base_path
    if base_query:
        result += '?' + base_query
    return result
