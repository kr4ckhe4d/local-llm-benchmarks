def urljoin_(base, url):
    def parse_url(u):
        scheme = ''
        authority = ''
        path = ''
        query = ''
        fragment = ''
        
        # Remove fragment
        if '#' in u:
            u, fragment = u.split('#', 1)
        
        # Remove query
        if '?' in u:
            u, query = u.split('?', 1)
        
        # Remove scheme
        if '://' in u:
            scheme, u = u.split('://', 1)
        
        # Remove authority
        if u.startswith('//'):
            u = u[2:]
            if '/' in u:
                authority, path = u.split('/', 1)
                path = '/' + path
            else:
                authority = u
                path = ''
        else:
            path = u
            
        return scheme, authority, path, query, fragment

    def remove_dot_segments(path):
        if not path:
            return path
        
        # Split path into segments
        segments = path.split('/')
        output = []
        
        for seg in segments:
            if seg == '.':
                continue
            elif seg == '..':
                if output:
                    output.pop()
            else:
                output.append(seg)
                
        # Reconstruct path
        # If the original path started with '/', we need to ensure the result does too
        # If the original path was empty, result is empty
        # If the original path didn't start with '/', result shouldn't either (unless it becomes absolute via ..)
        
        # RFC 3986 says:
        # If the input path is absolute (starts with /), the output must be absolute.
        # If the input path is relative, the output is relative unless .. pops past the root.
        
        # A simpler approach for standard web URLs:
        # If path starts with '/', join with '/' and ensure leading '/'
        # If path doesn't start with '/', join with '/'
        
        # However, if we pop past the beginning, we might end up with an empty list.
        # Example: /a/.. -> /
        # Example: a/.. -> '' (relative)
        
        # Let's handle the leading slash explicitly.
        is_absolute = path.startswith('/')
        
        # Filter out empty strings that might result from splitting
        # But we need to preserve the structure.
        
        # Re-join
        result = '/'.join(output)
        
        if is_absolute:
            if not result:
                return '/'
            return '/' + result
        else:
            return result

    base_scheme, base_authority, base_path, base_query, base_fragment = parse_url(base)
    url_scheme, url_authority, url_path, url_query, url_fragment = parse_url(url)

    # 1. If url has a scheme, it is absolute
    if url_scheme:
        return f"{url_scheme}://{url_authority}{url_path}" + (f"?{url_query}" if url_query else "") + (f"#{url_fragment}" if url_fragment else "")

    # 2. If url is scheme-relative (starts with //)
    if url_path.startswith('//') or (url_authority and not url_path.startswith('/')):
        # Note: parse_url puts //host/path into authority and path
        # If url starts with //, url_scheme is empty, url_authority is set.
        # We use base scheme.
        return f"{base_scheme}://{url_authority}{url_path}" + (f"?{url_query}" if url_query else "") + (f"#{url_fragment}" if url_fragment else "")

    # 3. If url is absolute path (starts with /)
    if url_path.startswith('/'):
        return f"{base_scheme}://{base_authority}{url_path}" + (f"?{url_query}" if url_query else "") + (f"#{url_fragment}" if url_fragment else "")

    # 4. If url is query-only
    if url_path == '' and url_query:
        # Keep base path, replace query and fragment
        return f"{base_scheme}://{base_authority}{base_path}?{url_query}" + (f"#{url_fragment}" if url_fragment else "")

    # 5. If url is fragment-only
    if url_path == '' and url_query == '' and url_fragment:
        # Keep base path and query, replace fragment
        return f"{base_scheme}://{base_authority}{base_path}" + (f"?{base_query}" if base_query else "") + f"#{url_fragment}"

    # 6. If url is empty
    if url_path == '' and url_query == '' and url_fragment == '':
        # Return base without fragment
        return f"{base_scheme}://{base_authority}{base_path}" + (f"?{base_query}" if base_query else "")

    # 7. Relative path
    # Merge base path and url path
    # Base path must be treated as a directory if it doesn't end with /
    # If base path is /a/b/c, the directory is /a/b/
    # If base path is /a/b/, the directory is /a/b/
    
    if base_path.endswith('/'):
        merged_path = base_path + url_path
    else:
        # Remove the last segment of base path
        last_slash = base_path.rfind('/')
        if last_slash == -1:
            base_dir = ''
        else:
            base_dir = base_path[:last_slash + 1]
        merged_path = base_dir + url_path

    # Normalize dot segments
    normalized_path = remove_dot_segments(merged_path)

    # Construct final URL
    # Use base scheme and authority
    # Use normalized path
    # Use url query and fragment (if present, else empty)
    
    result = f"{base_scheme}://{base_authority}{normalized_path}"
    if url_query:
        result += f"?{url_query}"
    if url_fragment:
        result += f"#{url_fragment}"
        
    return result
