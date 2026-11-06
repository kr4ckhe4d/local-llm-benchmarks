def urljoin_(base, url):
    """
    Join a base URL and a relative/absolute URL according to RFC 3986,
    reproducing the common behaviour of urllib.parse.urljoin without
    importing urllib.
    """
    if base is None:
        base = ""
    if url is None:
        url = ""

    base = str(base)
    url = str(url)

    # An empty reference means "the base URL, but without its fragment".
    if url == "":
        if "#" in base:
            return base.split("#", 1)[0]
        return base

    def _valid_scheme(s):
        if not s:
            return False
        if not ("a" <= s[0] <= "z" or "A" <= s[0] <= "Z"):
            return False
        for ch in s[1:]:
            if not (
                "a" <= ch <= "z"
                or "A" <= ch <= "Z"
                or "0" <= ch <= "9"
                or ch in "+-."
            ):
                return False
        return True

    def _split_url(value):
        # Fragment
        fragment = ""
        if "#" in value:
            value, fragment = value.split("#", 1)

        # Query
        query = ""
        if "?" in value:
            value, query = value.split("?", 1)

        # Scheme
        scheme = ""
        colon = value.find(":")
        if colon != -1:
            candidate = value[:colon]
            if _valid_scheme(candidate):
                scheme = candidate.lower()
                value = value[colon + 1:]

        # Authority
        netloc = ""
        if value.startswith("//"):
            value = value[2:]
            end = len(value)
            for i, ch in enumerate(value):
                if ch in "/?#":
                    end = i
                    break
            netloc = value[:end]
            value = value[end:]

        path = value
        return scheme, netloc, path, query, fragment

    def _remove_dot_segments(path):
        # RFC 3986, Section 5.2.4
        output = []
        while path:
            if path.startswith("../"):
                path = path[3:]
            elif path.startswith("./"):
                path = path[2:]
            elif path.startswith("/./"):
                path = "/" + path[3:]
            elif path == "/.":
                path = "/"
            elif path.startswith("/../"):
                path = "/" + path[4:]
                if output:
                    output.pop()
            elif path == "/..":
                path = "/"
                if output:
                    output.pop()
            elif path in (".", ".."):
                path = ""
            else:
                if path.startswith("/"):
                    i = path.find("/", 1)
                    if i == -1:
                        output.append(path)
                        path = ""
                    else:
                        output.append(path[:i])
                        path = path[i:]
                else:
                    i = path.find("/")
                    if i == -1:
                        output.append(path)
                        path = ""
                    else:
                        output.append(path[:i])
                        path = path[i:]
        return "".join(output)

    def _merge_paths(base_path, rel_path):
        # RFC 3986, Section 5.2.3
        if base_netloc and base_path == "":
            return "/" + rel_path
        slash = base_path.rfind("/")
        if slash == -1:
            return rel_path
        return base_path[: slash + 1] + rel_path

    def _unsplit(scheme, netloc, path, query, fragment):
        result = ""
        if scheme:
            result += scheme + ":"
        if netloc:
            result += "//" + netloc
        result += path
        if query:
            result += "?" + query
        if fragment:
            result += "#" + fragment
        return result

    b_scheme, b_netloc, b_path, b_query, b_fragment = _split_url(base)
    r_scheme, r_netloc, r_path, r_query, r_fragment = _split_url(url)

    # Absolute URL: replace the base entirely.
    if r_scheme:
        t_scheme = r_scheme
        t_netloc = r_netloc
        t_path = _remove_dot_segments(r_path)
        t_query = r_query
        t_fragment = r_fragment

    # Scheme-relative URL: //host/path
    elif r_netloc:
        t_scheme = b_scheme
        t_netloc = r_netloc
        t_path = _remove_dot_segments(r_path)
        t_query = r_query
        t_fragment = r_fragment

    # Empty path: query-only or fragment-only reference.
    elif r_path == "":
        t_scheme = b_scheme
        t_netloc = b_netloc
        t_path = b_path
        t_query = r_query if r_query != "" else b_query
        t_fragment = r_fragment

    # Absolute path: /path
    elif r_path.startswith("/"):
        t_scheme = b_scheme
        t_netloc = b_netloc
        t_path = _remove_dot_segments(r_path)
        t_query = r_query
        t_fragment = r_fragment

    # Relative path.
    else:
        t_scheme = b_scheme
        t_netloc = b_netloc
        t_path = _remove_dot_segments(_merge_paths(b_path, r_path))
        t_query = r_query
        t_fragment = r_fragment

    return _unsplit(t_scheme, t_netloc, t_path, t_query, t_fragment)
