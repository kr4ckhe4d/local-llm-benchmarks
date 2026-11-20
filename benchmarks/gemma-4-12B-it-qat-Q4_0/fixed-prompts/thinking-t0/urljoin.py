def urljoin_(base, url):
    if not url:
        return base.split('#', 1)[0]

    # Parse base components
    scheme = ""
    rest = base
    if "://" in base:
        scheme, rest = base.split("://", 1)
    
    # Find netloc and path
    if "/" in rest:
        netloc, path_part = rest.split("/", 1)
        path = "/" + path_part
    else:
        netloc = rest
        path = ""

    # Split path into query and fragment
    path_query = path_part if "/" in rest else path
    path, query, fragment = "", "", ""
    
    if "?" in path_query:
        path, query_part = path_query.split("?", 1)
        fragment = ""
        if "#" in query_part:
            query, fragment = query_part.split("#", 1)
        else:
            query = query_part
    elif "#" in path_query:
        path, fragment = path_query.split("#", 1)
        query = ""
    else:
        path = path_query

    # Handle URL types
    if url.startswith("//"):
        # Scheme-relative: keep scheme, replace netloc and path
        new_netloc = url[2:]
        new_path = ""
        if "/" in new_netloc:
            new_netloc, new_path = new_netloc.split("/", 1)
            new_path = "/" + new_path
        else:
            new_path = "/"
        return f"{scheme}://{new_netloc}{new_path}"

    if url.startswith("/"):
        # Absolute path: keep scheme and netloc, replace path
        new_path = url
        # If query or fragment in url, they replace base's
        new_query = ""
        new_fragment = ""
        if "?" in new_path:
            p, q_part = new_path.split("?", 1)
            new_path = p
            if "#" in q_part:
                new_query, new_fragment = q_part.split("#", 1)
            else:
                new_query = q_part
        elif "#" in new_path:
            p, f_part = new_path.split("#", 1)
            new_path = p
            new_fragment = f_part
        return f"{scheme}://{netloc}{new_path}"

    if url.startswith("?"):
        # Query-only: keep base path, replace query
        new_query = url[1:]
        new_fragment = ""
        if "#" in new_query:
            new_query, new_fragment = new_query.split("#", 1)
        return f"{scheme}://{netloc}{path}?{new_query}"

    if url.startswith("#"):
        # Fragment-only: keep base path and query, replace fragment
        new_fragment = url[1:]
        return f"{scheme}://{netloc}{path}{f'{? {query}}' if query else ''}#{new_fragment}"

    # Relative path resolution
    # If path ends in /, append url. Else, remove last component and append url.
    if path.endswith("/"):
        new_path = path + url
    else:
        # Remove last segment of path
        if "/" in path:
            last_slash = path.rfind("/")
            path_head = path[:last_slash]
            # If the last slash was at the start (e.g., "/a"), path_head becomes empty
            # but we need to preserve the leading slash for absolute paths
            if last_slash == 0:
                path_head = "/"
            new_path = path_head + url
        else:
            new_path = url

    # Normalize Dot Segments (RFC 3986 5.2.4)
    segments = []
    for seg in new_path.split("/"):
        if seg == "..":
            if segments:
                segments.pop()
        elif seg != "." and seg != "":
            segments.append(seg)
    
    # Reconstruct path with leading slash if original was absolute
    prefix = "/" if path.startswith("/") else ""
    normalized_path = prefix + "/".join(segments)
    if not normalized_path and path.startswith("/"):
        normalized_path = "/"

    # Handle query/fragment in relative URL
    new_query = ""
    new_fragment = ""
    if "?" in url:
        q_part = url.split("?", 1)[1]
        if "#" in q_part:
            new_query, new_fragment = q_part.split("#", 1)
        else:
            new_query = q_part
    elif "#" in url:
        new_fragment = url.split("#", 1)[1]

    # Final assembly
    res = f"{scheme}://{netloc}{normalized_path}"
    if new_query:
        res += f"?{new_query}"
    if new_fragment:
        res += f"#{new_fragment}"
    
    # If no scheme was provided in base, don't add ://
    if not scheme:
        res = res.replace("://", "", 1)
    return res
