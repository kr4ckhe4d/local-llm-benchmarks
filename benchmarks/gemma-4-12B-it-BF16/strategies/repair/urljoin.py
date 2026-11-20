def urljoin_(base, url):
    def parse_url(u):
        scheme = ""
        netloc = ""
        path = ""
        query = ""
        fragment = ""
        
        if not u:
            return scheme, netloc, path, query, fragment
            
        # Extract fragment
        if "#" in u:
            u, fragment = u.split("#", 1)
            fragment = "#" + fragment
            
        # Extract query
        if "?" in u:
            u, query = u.split("?", 1)
            query = "?" + query
            
        # Extract scheme
        if "://" in u:
            scheme, u = u.split("://", 1)
            scheme += "://"
        elif ":" in u and "/" not in u.split(":")[0]:
            parts = u.split(":", 1)
            scheme = parts[0] + ":"
            u = parts[1]
            
        # Extract netloc and path
        if u.startswith("//"):
            u = u[2:]
            parts = u.split("/", 1)
            netloc = parts[0]
            path = "/" + parts[1] if len(parts) > 1 else "/"
        elif u.startswith("/"):
            path = u
        else:
            parts = u.split("/", 1)
            netloc = ""
            path = parts[0]
            if len(parts) > 1:
                path += "/" + parts[1]
                
        return scheme, netloc, path, query, fragment

    # Parse base and target
    b_scheme, b_netloc, b_path, b_query, b_frag = parse_url(base)
    t_scheme, t_netloc, t_path, t_query, t_frag = parse_url(url)

    # 1. Empty string returning base without its fragment
    if url == "":
        return b_scheme + b_netloc + b_path + b_query

    # 2. Absolute URL (has scheme or starts with //)
    # Note: t_netloc is populated if it starts with // even if t_scheme is empty
    if t_scheme or t_netloc:
        # If it's a scheme-relative URL (starts with //), we keep the base scheme
        if not t_scheme and url.startswith("//"):
            return b_scheme + "//" + t_netloc + t_path + t_query + t_frag
        return t_scheme + t_netloc + t_path + t_query + t_frag

    # 3. Absolute path (starts with /)
    if t_path.startswith("/"):
        return b_scheme + b_netloc + t_path + t_query + t_frag

    # 4. Query-only or Fragment-only references
    if t_path == "" and t_query:
        return b_scheme + b_netloc + b_path + t_query + t_frag
    if t_path == "" and t_frag:
        return b_scheme + b_netloc + b_path + b_query + t_frag

    # 5. Relative path, . , ..
    # Determine base directory
    if not b_path or b_path == "/":
        base_dir = "/"
    else:
        last_slash = b_path.rfind("/")
        if last_slash == -1:
            base_dir = "/"
        else:
            base_dir = b_path[:last_slash + 1]

    # Normalize path segments
    segments = [s for s in base_dir.split("/") if s]
    new_segments = []
    
    # Add base segments
    for s in segments:
        new_segments.append(s)
        
    # Process target path
    target_parts = t_path.split("/")
    for part in target_parts:
        if part == "..":
            if new_segments:
                new_segments.pop()
        elif part == "." or part == "":
            continue
        else:
            new_segments.append(part)

    # Reconstruct path
    res_path = "/" + "/".join(new_segments)
    if not res_path: res_path = "/"
    
    return b_scheme + b_netloc + res_path + t_query + t_frag
