def urljoin_(base, url):
    """
    Reproduce urllib.parse.urljoin behavior from scratch according to RFC 3986.
    
    Rules:
    1. If url is an absolute URL (has scheme), return url.
    2. If url is scheme-relative (starts with //), return scheme from base + url.
    3. If url is an absolute path (starts with /), return base's scheme + host + url.
    4. Otherwise, resolve relative to base's path, handling . and .. normalization.
    5. Handle query-only (?q) and fragment-only (#f) by replacing base's query/fragment.
    6. If url is empty, return base without its fragment.
    """
    
    def parse_url(u):
        """Parse a URL into components: (scheme, host, port, path, query, fragment)"""
        # Remove fragment first
        frag_start = u.find('#')
        if frag_start != -1:
            frag = u[frag_start:]
            u = u[:frag_start]
        else:
            frag = ''
        
        # Remove query
        query_start = u.find('?')
        if query_start != -1:
            query = u[query_start:]
            u = u[:query_start]
        else:
            query = ''
        
        # Parse scheme
        scheme = ''
        if u and (u[0].isalpha() or u[0] == '+'):
            scheme_end = 1
            while scheme_end < len(u) and (u[scheme_end].isalnum() or u[scheme_end] in '+-.'):
                scheme_end += 1
            if scheme_end > 1:
                scheme = u[:scheme_end]
                u = u[scheme_end:]
        
        # Parse authority (host:port)
        host = ''
        port = ''
        if u and u[0] == '/':
            # Path starts immediately
            path = u
            query = ''
            frag = ''
            # Re-check query and fragment in path
            q_idx = path.find('?')
            if q_idx != -1:
                query = path[q_idx:]
                path = path[:q_idx]
            f_idx = path.find('#')
            if f_idx != -1:
                frag = path[f_idx:]
                path = path[:f_idx]
            return scheme, host, port, path, query, frag
        
        if u:
            # Check for userinfo@host:port
            at_idx = u.find('@')
            if at_idx != -1:
                # Could be user@host or user:pass@host
                # For simplicity, treat everything before @ as userinfo if no slash
                # But we need to find the host part
                # Actually, standard parsing: find the last @ or the start of path
                # If there's a slash, the part after last @ is host:port
                # If no slash, the whole thing is host:port (with optional userinfo)
                
                # Find the start of the path component (first /)
                slash_idx = u.find('/')
                if slash_idx == -1:
                    # No path, so everything is authority
                    auth_part = u
                    path = ''
                else:
                    auth_part = u[:slash_idx]
                    path = u[slash_idx:]
                
                # Parse auth_part
                if '@' in auth_part:
                    user_pass, host_port = auth_part.rsplit('@', 1)
                else:
                    user_pass = ''
                    host_port = auth_part
                
                # Parse host:port
                if ':' in host_port:
                    # Check if it's IPv6 literal [::1]:port
                    if host_port.startswith('['):
                        bracket_end = host_port.find(']')
                        if bracket_end != -1:
                            host = host_port[1:bracket_end]
                            port = host_port[bracket_end+1:]
                        else:
                            host = host_port[1:]
                            port = ''
                    else:
                        # Simple host:port
                        colon_idx = host_port.rfind(':')
                        host = host_port[:colon_idx]
                        port = host_port[colon_idx+1:]
                else:
                    host = host_port
                    port = ''
                
                return scheme, host, port, path, query, frag
            else:
                # No @, so u is just host:port or path
                slash_idx = u.find('/')
                if slash_idx == -1:
                    # Just host:port
                    if ':' in u:
                        colon_idx = u.rfind(':')
                        host = u[:colon_idx]
                        port = u[colon_idx+1:]
                    else:
                        host = u
                        port = ''
                    path = ''
                else:
                    host = u[:slash_idx]
                    port = ''
                    path = u[slash_idx:]
                
                return scheme, host, port, path, query, frag
        else:
            return scheme, host, port, path, query, frag

    def normalize_path(path):
        """Normalize path by resolving . and .."""
        if not path:
            return ''
        
        # Split by /
        segments = path.split('/')
        output = []
        
        for seg in segments:
            if seg == '..':
                if output and output[-1] != '':
                    output.pop()
                # If output is empty or last is '', ignore .. (go above root)
            elif seg == '.':
                continue
            elif seg == '' and len(output) > 0 and output[-1] != '':
                # Consecutive slashes, keep one empty segment? 
                # Actually, RFC 3986: // becomes /, so consecutive slashes are normalized
                # But we need to be careful with leading/trailing
                pass
            else:
                output.append(seg)
        
        # Reconstruct
        if not output:
            return '/'
        
        result = '/'.join(output)
        
        # Ensure it starts with / if original did
        if path.startswith('/') and not result.startswith('/'):
            result = '/' + result
        
        return result

    def parse_base():
        return parse_url(base)
    
    def parse_url_():
        return parse_url(url)

    base_scheme, base_host, base_port, base_path, base_query, base_frag = parse_base()
    url_scheme, url_host, url_port, url_path, url_query, url_frag = parse_url_()
    
    # 1. Absolute URL
    if url_scheme:
        return f"{url_scheme}://{url_host}:{url_port}/{url_path}" if url_path else f"{url_scheme}://{url_host}:{url_port}"
    
    # 2. Scheme-relative
    if url.startswith('//'):
        # Use base's scheme
        if base_scheme:
            return f"{base_scheme}://{url[2:]}"
        else:
            return url[2:]
    
    # 3. Absolute path
    if url_path and url_path.startswith('/'):
        if base_scheme:
            return f"{base_scheme}://{base_host}:{base_port}{url_path}"
        else:
            return url_path
    
    # 4. Relative path resolution
    # Start with base path
    current_path = base_path
    
    # If base path ends with /, remove it for joining (unless it's just /)
    if current_path and not current_path.endswith('/') and not current_path == '/':
        # Remove trailing slash for joining
        current_path = current_path.rstrip('/')
    
    # If url_path is empty, we're just resolving query/fragment
    if not url_path:
        # Return base path with new query/fragment
        if url_query:
            return f"{current_path}?{url_query}"
        elif url_frag:
            return f"{current_path}#{url_frag}"
        else:
            return current_path
    
    # Resolve relative path
    # Split base path into segments (excluding trailing empty if not root)
    base_segments = current_path.split('/') if current_path else []
    # Remove trailing empty segment if present (from trailing slash)
    if base_segments and base_segments[-1] == '':
        base_segments = base_segments[:-1]
    
    # Split url path
    url_segments = url_path.split('/')
    
    # Walk through url segments
    result_segments = []
    for seg in url_segments:
        if seg == '.':
            continue
        elif seg == '..':
            if result_segments:
                result_segments.pop()
            # If result_segments is empty, ignore (go above root)
        else:
            result_segments.append(seg)
    
    # Reconstruct path
    if result_segments:
        resolved_path = '/'.join(result_segments)
        # Ensure leading slash if base had one
        if base_path.startswith('/') and not resolved_path.startswith('/'):
            resolved_path = '/' + resolved_path
    else:
        resolved_path = '/' if base_path.startswith('/') else ''
    
    # 5. Handle query and fragment
    if url_query:
        resolved_path = f"{resolved_path}?{url_query}"
    if url_frag:
        resolved_path = f"{resolved_path}#{url_frag}"
    
    # 6. If url was empty, return base without fragment
    if not url:
        return f"{base_scheme}://{base_host}:{base_port}{base_path}" if base_scheme else base_path
    
    # Final assembly
    if base_scheme:
        return f"{base_scheme}://{base_host}:{base_port}{resolved_path}"
    else:
        return resolved_path
