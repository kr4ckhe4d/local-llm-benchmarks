def urljoin_(base, url):
    def parse_url(u):
        scheme, rest = "", u
        if "://" in u:
            scheme, rest = u.split("://", 1)
        elif ":" in u and u.startswith(":"):
            scheme, rest = u.split(":", 1)
            # Handle scheme-relative :http:path
            if rest.startswith(":"):
                rest = rest[1:]
        
        authority, rest = "", rest
        if rest.startswith("//"):
            parts = rest.split("/", 1)
            authority = parts[0]
            rest = "/" + parts[1] if len(parts) > 1 else ""
        elif "://" in u and not rest.startswith("//"):
            # This case is handled by the first split, but for safety:
            pass

        path, query, fragment = "", "", ""
        if rest:
            # Split path from query/fragment
            path_part = rest
            if "?" in path_part:
                path_part, q_part = path_part.split("?", 1)
                query = q_part
            else:
                query = ""
            
            if "#" in path_part:
                path_part, f_part = path_part.split("#", 1)
                fragment = f_part
            elif "#" in q_part:
                # This shouldn't happen with standard parsing but for robustness:
                q_parts = q_part.split("#", 1)
                query = q_parts[0]
                fragment = q_parts[1]
            else:
                fragment = ""
            path = path_part

        # Re-parse query/fragment if they were in the original string but not path
        if "?" in rest:
            q_split = rest.split("?", 1)
            query = q_split[1]
            if "#" in query:
                query, fragment = query.split("#", 1)
        elif "#" in rest:
            f_split = rest.split("#", 1)
            fragment = f_split[1]

        return scheme, authority, path, query, fragment

    def normalize_path(path):
        segments = []
        for part in path.split("/"):
            if part == "..":
                if segments:
                    segments.pop()
            elif part == "." or part == "":
                continue
            else:
                segments.append(part)
        
        res = "/".join(segments)
        if path.startswith("/") and not res.startswith("/"):
            res = "/" + res
        if path.endswith("/") and not res.endswith("/") and res != "/":
            res += "/"
        return res

    # 1. Empty URL returns base without fragment
    if not url:
        s, a, p, q, f = parse_url(base)
        return f"{s}://{a}{p}{q}" if s else f"{a}{p}{q}"

    b_scheme, b_auth, b_path, b_query, b_frag = parse_url(base)
    u_scheme, u_auth, u_path, u_query, u_frag = parse_url(url)

    # 2. Scheme-relative reference (:http:path)
    if url.startswith(":"):
        return f"{u_scheme}://{u_auth}{u_path}{u_query}{u_frag}"

    # 3. Network-path reference (//host/path)
    if url.startswith("//"):
        return f"{b_scheme}://{u_auth}{u_path}{u_query}{u_frag}"

    # 4. Absolute-path reference (/path)
    if url.startswith("/"):
        return f"{b_scheme}://{b_auth}{u_path}{u_query}{u_frag}"

    # 5. Query-only or Fragment-only references
    if url.startswith("?"):
        return f"{b_scheme}://{b_auth}{b_path}{u_query}{u_frag}"
    if url.startswith("#"):
        return f"{b_scheme}://{b_auth}{b_path}{b_query}{u_frag}"

    # 6. Relative-path reference
    # Determine the directory part of the base path
    if not b_path or b_path.endswith("/"):
        dir_part = b_path
    else:
        # Strip the last component
        parts = b_path.rstrip("/").split("/")
        dir_part = "/".join(parts[:-1]) if len(parts) > 1 else "/"
        if not dir_part and b_path: # Handle cases like "file.html" -> ""
            dir_part = ""

    # Join directory part with relative path
    new_path = dir_part + "/" + u_path
    # Normalize the resulting path (handles . and ..)
    new_path = normalize_path(new_path)
    
    # If the base path was empty, the directory part is empty
    if not b_path and not dir_part:
        new_path = u_path

    # Query and fragment logic for relative paths
    final_query = u_query if u_query else b_query
    final_frag = u_frag if u_frag else b_frag

    return f"{b_scheme}://{b_auth}{new_path}{final_query}{final_frag}"
