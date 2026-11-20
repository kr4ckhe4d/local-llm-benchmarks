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
        elif ":" in u and "://" not in u:
            parts = u.split(":", 1)
            scheme = parts[0] + ":"
            u = parts[1]
            
        # Extract netloc and path
        if u.startswith("//"):
            u_content = u[2:]
            netloc_parts = u_content.split("/", 1)
            netloc = "//" + netloc_parts[0]
            path = "/" + netloc_parts[1] if len(netloc_parts) > 1 else "/"
        elif u.startswith("/"):
            path = u
        else:
            path = u
                
        return scheme, netloc, path, query, fragment

    b_scheme, b_netloc, b_path, b_query, b_frag = parse_url(base)
    u_scheme, u_netloc, u_path, u_query, u_frag = parse_url(url)

    # 1. If url is empty, return base without fragment
    if not url:
        return base.split('#')[0]

    # 2. Absolute URL (has scheme or netloc)
    if u_scheme or u_netloc:
        res_scheme = u_scheme if u_scheme else b_scheme
        res_netloc = u_netloc if u_netloc else b_netloc
        res_path = u_path
        res_query = u_query
        res_frag = u_frag
    # 3. Scheme-relative (starts with //)
    elif url.startswith("//"):
        res_scheme = b_scheme
        res_netloc = "//" + url[2:].split("/", 1)[0]
        res_path = "/" + url[2:].split("/", 1)[1] if "/" in url[2:] else "/"
        res_query = u_query
        res_frag = u_frag
    # 4. Absolute path (starts with /)
    elif u_path.startswith("/"):
        res_scheme = b_scheme
        res_netloc = b_netloc
        res_path = u_path
        res_query = u_query
        res_frag = u_frag
    # 5. Relative path
    else:
        res_scheme = b_scheme
        res_netloc = b_netloc
        
        if b_path == "" or b_path == "/":
            base_dir = "/"
        elif b_path.endswith("/"):
            base_dir = b_path
        else:
            base_dir = b_path.rsplit("/", 1)[0] + "/" if "/" in b_path else "/"
            
        combined = base_dir + u_path
        parts = combined.split("/")
        stack = []
        for part in parts:
            if part == "" or part == ".":
                continue
            if part == "..":
                if stack:
                    stack.pop()
            else:
                stack.append(part)
        res_path = "/" + "/".join(stack)
        res_query = u_query
        res_frag = u_frag

    # Reconstruct
    result = ""
    if res_scheme: result += res_scheme
    if res_netloc: result += res_netloc
    
    # Path logic: if netloc exists, path must start with / unless it's empty
    if res_netloc:
        if not res_path.startswith("/"):
            res_path = "/" + res_path
    
    result += res_path
    result += res_query
    result += res_frag
    
    return result
