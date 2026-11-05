def urljoin_(base, url):
    # Handle bytes
    is_bytes = isinstance(base, bytes) or isinstance(url, bytes)
    if is_bytes:
        if isinstance(base, str):
            base = base.encode('utf-8')
        if isinstance(url, str):
            url = url.encode('utf-8')
    
    def _parse(u):
        """Parse a URL into (scheme, netloc, path, query, fragment)."""
        scheme = None
        netloc = None
        path = None
        query = None
        fragment = None
        
        s = u
        
        # Check for scheme
        if len(s) > 0:
            first = s[0:1]
            if is_bytes:
                is_alpha = (65 <= first[0] <= 90) or (97 <= first[0] <= 122)
            else:
                is_alpha = first.isalpha()
            
            if is_alpha:
                # Find the colon
                colon_idx = -1
                for i in range(1, len(s)):
                    c = s[i:i+1]
                    if is_bytes:
                        ch = c[0]
                        valid = (48 <= ch <= 57) or (65 <= ch <= 90) or (97 <= ch <= 122) or ch == 43 or ch == 45 or ch == 46
                    else:
                        valid = c.isalnum() or c in '+-.'
                    if c == b':' if is_bytes else c == ':':
                        colon_idx = i
                        break
                    if not valid:
                        break
                
                if colon_idx != -1:
                    scheme = s[:colon_idx].lower()
                    s = s[colon_idx+1:]
        
        # Check for netloc
        if s.startswith(b'//' if is_bytes else '//'):
            s = s[2:]
            # Netloc ends at first /, ?, or #
            end_idx = -1
            for i in range(len(s)):
                c = s[i:i+1]
                if c == b'/' or c == b'?' or c == b'#':
                    end_idx = i
                    break
            if end_idx == -1:
                netloc = s
                s = b'' if is_bytes else ''
            else:
                netloc = s[:end_idx]
                s = s[end_idx:]
        
        # Now s contains path, query, fragment
        # Split off fragment
        frag_idx = s.find(b'#' if is_bytes else '#')
        if frag_idx != -1:
            fragment = s[frag_idx+1:]
            s = s[:frag_idx]
        
        # Split off query
        query_idx = s.find(b'?' if is_bytes else '?')
        if query_idx != -1:
            query = s[query_idx+1:]
            s = s[:query_idx]
        
        path = s
        
        return (scheme, netloc, path, query, fragment)
    
    base_scheme, base_netloc, base_path, base_query, base_fragment = _parse(base)
    url_scheme, url_netloc, url_path, url_query, url_fragment = _parse(url)
    
    # Determine result components
    if url_scheme is not None:
        # Absolute URL
        result_scheme = url_scheme
        result_netloc = url_netloc
        result_path = url_path
        result_query = url_query
        result_fragment = url_fragment
    else:
        result_scheme = base_scheme
        result_netloc = base_netloc
        
        # Check for empty reference
        if url == (b'' if is_bytes else ''):
            result_path = base_path
            result_query = base_query
            result_fragment = None  # Drop fragment
        elif url_netloc is not None and url_netloc != (b'' if is_bytes else ''):
            # Reference has authority
            result_netloc = url_netloc
            result_path = url_path
            result_query = url_query
            result_fragment = url_fragment
        elif url_path is not None and url_path != (b'' if is_bytes else '') and base_path is not None and base_path == (b'' if is_bytes else ''):
            # Reference path non-empty, base path empty
            result_path = url_path
            result_query = url_query
            result_fragment = url_fragment
        elif url_path is not None and url_path != (b'' if is_bytes else '') and (url_path.startswith(b'/' if is_bytes else '/')):
            # Absolute path
            result_path = url_path
            result_query = url_query
            result_fragment = url_fragment
        else:
            # Relative path - need to merge
            # Determine query and fragment
            if url_query is not None:
                result_query = url_query
            elif url_fragment is not None:
                result_query = None
            else:
                result_query = None
            
            if url_fragment is not None:
                result_fragment = url_fragment
            else:
                result_fragment = None
            
            # Merge paths
            # Start from base_path, remove last segment
            bp = base_path if base_path is not None else (b'' if is_bytes else '')
            up = url_path if url_path is not None else (b'' if is_bytes else '')
            
            # Remove last segment from base path
            if bp == (b'' if is_bytes else ''):
                merged_base = bp
            elif bp == (b'/' if is_bytes else '/'):
                merged_base = bp
            else:
                # Find last /
                last_slash = bp.rfind(b'/' if is_bytes else '/')
                if last_slash == -1:
                    merged_base = b'' if is_bytes else ''
                else:
                    merged_base = bp[:last_slash+1]
            
            # Now process url_path segments
            # Split up on /
            if up == (b'' if is_bytes else ''):
                segments = []
            else:
                # Split on /
                segments = []
                current = b'' if is_bytes else ''
                for c in up:
                    if c == (b'/' if is_bytes else '/'):
                        segments.append(current)
                        current = b'' if is_bytes else ''
                    else:
                        current = current + c
                segments.append(current)
            
            # Process segments
            # Start with merged_base
            # We'll build the path as a list of segments
            # merged_base ends with / or is empty or is /
            
            # Let's represent the current path as a list of segments
            # If merged_base is '', path is empty
            # If merged_base is '/', path is [''] (root)
            # If merged_base is '/a/', path is ['a']
            # If merged_base is '/a', path is ['a']
            
            if merged_base == (b'' if is_bytes else ''):
                path_segments = []
            elif merged_base == (b'/' if is_bytes else '/'):
                path_segments = []  # Root, represented as empty list with leading slash
            else:
                # merged_base ends with /
                # Remove trailing /
                mb = merged_base[:-1] if merged_base.endswith(b'/' if is_bytes else '/') else merged_base
                if mb == (b'' if is_bytes else ''):
                    path_segments = []
                else:
                    path_segments = mb.split(b'/' if is_bytes else '/')
            
            # Process each segment in url_path
            for seg in segments:
                if seg == (b'..' if is_bytes else '..'):
                    if path_segments:
                        path_segments.pop()
                    # If empty, stay at root
                elif seg == (b'.' if is_bytes else '.'):
                    pass  # Ignore
                else:
                    path_segments.append(seg)
            
            # Reconstruct path
            if path_segments == []:
                # Check if we should have trailing slash
                # If url_path ended with / or was just . or .., we need trailing slash
                # Actually, let's check: if the last processed segment was . or .., or if up ended with /
                # Simpler: if up ends with / or up is . or up is .., add trailing /
                if up == (b'' if is_bytes else ''):
                    result_path = merged_base
                else:
                    # Check if up ends with /
                    if up.endswith(b'/' if is_bytes else '/'):
                        result_path = (b'/' if is_bytes else '/') + (b'/'.join(path_segments) if path_segments else b'' if is_bytes else '')
                        if result_path == (b'/' if is_bytes else '/'):
                            result_path = (b'/' if is_bytes else '/')
                    else:
                        # Check if last segment was . or ..
                        if segments and (segments[-1] == (b'.' if is_bytes else '.') or segments[-1] == (b'..' if is_bytes else '..')):
                            result_path = (b'/' if is_bytes else '/') + (b'/'.join(path_segments) if path_segments else b'' if is_bytes else '')
                            if result_path == (b'/' if is_bytes else '/'):
                                result_path = (b'/' if is_bytes else '/')
                        else:
                            result_path = (b'/' if is_bytes else '/') + (b'/'.join(path_segments) if path_segments else b'' if is_bytes else '')
                            if result_path == (b'/' if is_bytes else '/'):
                                result_path = (b'/' if is_bytes else '/')
            else:
                result_path = (b'/' if is_bytes else '/') + (b'/'.join(path_segments) if path_segments else b'' if is_bytes else '')
                if result_path == (b'/' if is_bytes else '/'):
                    result_path = (b'/' if is_bytes else '/')
    
    # Reconstruct
    parts = []
    if result_scheme is not None:
        parts.append(result_scheme + (b':' if is_bytes else ':'))
    if result_netloc is not None and result_netloc != (b'' if is_bytes else ''):
        parts.append((b'//' if is_bytes else '//') + result_netloc)
    if result_path is not None:
        parts.append(result_path)
    if result_query is not None:
        parts.append((b'?' if is_bytes else '?') + result_query)
    if result_fragment is not None:
        parts.append((b'#' if is_bytes else '#') + result_fragment)
    
    result = b''.join(parts) if is_bytes else ''.join(parts)
    
    if is_bytes:
        return result
    else:
        return result
