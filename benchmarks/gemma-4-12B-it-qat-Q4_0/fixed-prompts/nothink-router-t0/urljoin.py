def urljoin_(base, url):
    # Helper to split components manually
    def split_url(u):
        scheme = ""
        rest = u
        if "://" in u:
            scheme, rest = u.split("://", 1)
        
        netloc = ""
        if rest.startswith("//"):
            rest = rest[2:]
            parts = rest.split("/", 1)
            netloc = parts[0]
            rest = "/" + parts[1] if len(parts) > 1 else ""
        elif rest.startswith("/"):
            parts = rest.split("/", 1)
            netloc = ""
            rest = parts[1] if len(parts) > 1 else ""
        else:
            parts = rest.split("/", 1)
            netloc = ""
            rest = parts[0]
            if len(parts) > 1:
                rest = "/" + parts[1]

        path_parts = []
        if rest:
            # Split path, query, and fragment
            path_raw = rest.split("?", 1)[0].split("#", 1)[0]
            query = ""
            if "?" in rest:
                query = rest.split("?", 1)[1]
            fragment = ""
            if "#" in rest:
                fragment = rest.split("#", 1)[1]
            
            # Path normalization
            raw_path = path_raw if path_raw else "/"
            segments = raw_path.split("/")
            for seg in segments:
                if seg == "..":
                    if path_parts: path_parts.pop()
                elif seg == "." or seg == "":
                    continue
                else:
                    path_parts.append(seg)
            
            # Reconstruct path
            new_path = "/" + "/".join(path_parts)
            if not new_path: new_path = "/"
            # If original had trailing slash and wasn't just root
            if path_raw.endswith("/") and new_path != "/":
                new_path += "/"
            
            return scheme, netloc, new_path, query, fragment
        else:
            # Handle cases like "path" or ""
            query = ""
            fragment = ""
            if "?" in rest: query = rest.split("?", 1)[1]
            if "#" in rest: fragment = rest.split("#", 1)[1]
            return scheme, netloc, "", query, fragment

    # Parse base
    b_scheme, b_netloc, b_path, b_query, b_fragment = split_url(base)
    
    # Parse url
    u_scheme, u_netloc, u_path, u_query, u_fragment = split_url(url)

    # RFC 3986 Resolution Logic
    if u_scheme or u_netloc:
        # Absolute URL or scheme-relative //host/path
        res_scheme = u_scheme or b_scheme
        res_netloc = u_netloc or b_netloc
        res_path = u_path if u_path else "/"
        res_query = u_query if u_query else b_query
        res_fragment = u_fragment if u_fragment else b_fragment
    elif u_path.startswith("/"):
        # Absolute path /path
        res_scheme = b_scheme
        res_netloc = b_netloc
        res_path = u_path
        res_query = u_query if u_query else b_query
        res_fragment = u_fragment if u_fragment else b_fragment
    elif url == "":
        # Empty string returns base without fragment
        return base.split("#")[0]
    else:
        # Relative path or . or ..
        res_scheme = b_scheme
        res_netloc = b_netloc
        
        # Base path for relative resolution
        base_path_segments = b_path.split("/")
        if not base_path_segments or base_path_segments == [""]:
            base_path_segments = []
            
        new_segments = list(base_path_segments)
        # If base path is empty, relative path is joined to root
        if not b_path.startswith("/") and not b_netloc:
            # This handles cases where base is just a filename
            pass 

        # Process relative segments
        rel_segments = u_path.split("/")
        for seg in rel_segments:
            if seg == "..":
                if new_segments: new_segments.pop()
            elif seg == "." or seg == "":
                continue
            else:
                new_segments.append(seg)
        
        # Join segments
        if not b_netloc:
            res_path = "/".join(new_segments)
            if not res_path.startswith("/"): res_path = "/" + res_path
        else:
            res_path = "/" + "/".join(new_segments)
            if not res_path.startswith("/"): res_path = "/" + res_path

        res_query = u_query if u_query else b_query
        res_fragment = u_fragment if u_fragment else b_fragment

    # Reconstruct
    result = ""
    if res_scheme:
        result += res_scheme + "://"
    result += res_netloc
    if res_netloc and not res_path.startswith("/"):
        result += "/"
    result += res_path
    if res_query:
        result += "?" + res_query
    if res_fragment:
        result += "#" + res_fragment
        
    return result
