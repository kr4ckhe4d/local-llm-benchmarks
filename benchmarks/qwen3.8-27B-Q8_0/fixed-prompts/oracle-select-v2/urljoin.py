def urljoin_(base, url):
    """
    Reproduce urllib.parse.urljoin from scratch per RFC 3986.
    """
    if not base:
        base = ''
    if not url:
        url = ''

    # Split a URL into its components
    def split_url(u):
        # Returns (scheme, authority, path, query, fragment)
        scheme = ''
        authority = ''
        path = ''
        query = ''
        fragment = ''

        # Check for fragment
        if '#' in u:
            u, fragment = u.split('#', 1)

        # Check for query
        if '?' in u:
            u, query = u.split('?', 1)

        # Check for scheme
        # Scheme: ALPHA *( ALPHA / DIGIT / "+" / "-" / "." ) ':'
        i = 0
        n = len(u)
        if i < n and (u[i].isalpha()):
            j = i + 1
            while j < n and (u[j].isalnum() or u[j] in '+-.'):
                j += 1
            if j < n and u[j] == ':':
                scheme = u[i:j]
                u = u[j+1:]
                i = 0
                n = len(u)

        # Check for authority
        if u.startswith('//'):
            u = u[2:]
            # Authority ends at '/', '?', or '#'
            end = len(u)
            for k in range(len(u)):
                if u[k] in '/?#':
                    end = k
                    break
            authority = u[:end]
            u = u[end:]

        # The rest is path
        path = u

        return scheme, authority, path, query, fragment

    def merge_path(base_path, ref_path):
        """
        Merge base path with reference path per RFC 3986 section 5.2.2
        """
        if base_path and base_path[-1] == '/':
            return base_path + ref_path
        else:
            # Remove everything after the last '/'
            last_slash = base_path.rfind('/')
            if last_slash != -1:
                base_path = base_path[:last_slash + 1]
            return base_path + ref_path

    def remove_dot_segments(path):
        """
        Remove dot segments from a path per RFC 3986 section 5.2.4
        """
        if not path:
            return path

        # We'll use a stack-based approach
        # Split by '/'
        # Note: we need to handle leading slash
        in_path = path
        out = []

        # Process the path
        while in_path:
            # If path starts with '../'
            if in_path.startswith('../'):
                in_path = in_path[3:]
            # If path starts with './'
            elif in_path.startswith('./'):
                in_path = in_path[2:]
            # If path starts with '/./' or is '/.'
            elif in_path.startswith('/./'):
                in_path = '/' + in_path[3:]
            elif in_path == '/.':
                in_path = '/'
            # If path starts with '/../' or is '/..'
            elif in_path.startswith('/../'):
                in_path = '/' + in_path[4:]
                # Remove the last segment from output
                if out:
                    out.pop()
            elif in_path == '/..':
                in_path = '/'
                if out:
                    out.pop()
            # If path starts with '.' or '..' (without trailing slash, at end)
            elif in_path in ('.', '..'):
                in_path = ''
            else:
                # Move the first path segment (including initial '/' if any) to output
                if in_path.startswith('/'):
                    # Find next '/'
                    next_slash = in_path.find('/', 1)
                    if next_slash == -1:
                        out.append(in_path)
                        in_path = ''
                    else:
                        out.append(in_path[:next_slash])
                        in_path = in_path[next_slash:]
                else:
                    next_slash = in_path.find('/')
                    if next_slash == -1:
                        out.append(in_path)
                        in_path = ''
                    else:
                        out.append(in_path[:next_slash])
                        in_path = in_path[next_slash:]

        result = ''.join(out)
        # Normalize multiple slashes
        while '//' in result:
            result = result.replace('//', '/')
        return result

    base_scheme, base_authority, base_path, base_query, base_fragment = split_url(base)
    ref_scheme, ref_authority, ref_path, ref_query, ref_fragment = split_url(url)

    # If the reference has a scheme, use it entirely
    if ref_scheme:
        # Absolute URL: use reference as-is
        result_scheme = ref_scheme
        result_authority = ref_authority
        result_path = ref_path
        result_query = ref_query
        result_fragment = ref_fragment
    else:
        # No scheme in reference
        if ref_authority:
            # Scheme-relative or authority present
            # If base has no scheme, result has no scheme
            if base_scheme:
                result_scheme = base_scheme
            else:
                result_scheme = ''
            result_authority = ref_authority
            result_path = remove_dot_segments(ref_path)
            result_query = ref_query
            result_fragment = ref_fragment
        else:
            # No authority in reference
            result_scheme = base_scheme
            result_authority = base_authority

            if not ref_path and not ref_query:
                # Empty path and query - just fragment
                result_path = base_path
                result_query = base_query
                result_fragment = base_fragment if not ref_fragment else ref_fragment
            elif not ref_path:
                # Empty path, but has query
                result_path = base_path
                result_query = ref_query
                result_fragment = ref_fragment
            else:
                # Has path
                if ref_path.startswith('/'):
                    # Absolute path
                    result_path = remove_dot_segments(ref_path)
                    result_query = ref_query
                    result_fragment = ref_fragment
                else:
                    # Relative path
                    if result_authority and not base_path:
                        # Base has authority but empty path
                        result_path = '/' + ref_path
                    else:
                        result_path = merge_path(base_path, ref_path)
                    result_path = remove_dot_segments(result_path)
                    result_query = ref_query
                    result_fragment = ref_fragment

    # Build the result
    result = ''
    if result_scheme:
        result += result_scheme + ':'
    if result_authority:
        result += '//' + result_authority
    result += result_path
    if result_query:
        result += '?' + result_query
    if result_fragment:
        result += '#' + result_fragment

    return result
