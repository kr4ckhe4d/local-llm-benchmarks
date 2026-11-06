def urljoin_(base, url):
    """
    Reproduce urllib.parse.urljoin from scratch, implementing RFC 3986 reference resolution.
    """
    # Helper to parse a URL into components: scheme, authority, path, query, fragment
    def parse_url(s):
        if s is None:
            s = ''
        # Extract fragment
        frag = ''
        if '#' in s:
            s, frag = s.rsplit('#', 1)
        # Extract query
        query = ''
        if '?' in s:
            s, query = s.rsplit('?', 1)
        # Extract scheme
        scheme = ''
        rest = s
        if ':' in s:
            # Check if the part before ':' looks like a valid scheme (starts with alpha, then alphanum/+/-/.)
            colon_idx = s.index(':')
            prefix = s[:colon_idx]
            if prefix and prefix[0].isalpha() and all(c.isalnum() or c in '+-.' for c in prefix):
                scheme = prefix
                rest = s[colon_idx + 1:]
        # Extract authority (starts with //)
        authority = ''
        path = rest
        if rest.startswith('//'):
            # Find the end of authority: next /, ?, or # (but ? and # already stripped)
            # Authority ends at the first / after //
            idx = rest.find('/', 2)
            if idx == -1:
                authority = rest[2:]
                path = ''
            else:
                authority = rest[2:idx]
                path = rest[idx:]
        return scheme, authority, path, query, frag

    def remove_dot_segments(path):
        """Implement RFC 3986 Section 5.2.4 remove_dot_segments."""
        # Input buffer
        input_buffer = path
        output_buffer = []

        while input_buffer:
            # A. If the input buffer begins with a prefix of "../" or "./",
            #    remove that prefix from the input buffer.
            if input_buffer.startswith('../'):
                input_buffer = input_buffer[3:]
            elif input_buffer.startswith('./'):
                input_buffer = input_buffer[2:]
            # B. If the input buffer begins with a prefix of "/./" or "/.",
            #    where "." is a complete path segment, replace that prefix
            #    with "/" in the input buffer.
            elif input_buffer.startswith('/./'):
                input_buffer = '/' + input_buffer[3:]
            elif input_buffer == '/.':
                input_buffer = '/'
            # C. If the input buffer begins with a prefix of "/../" or "/..",
            #    where ".." is a complete path segment, replace that prefix
            #    with "/" in the input buffer and remove the last segment
            #    and its preceding "/" (if any) from the output buffer.
            elif input_buffer.startswith('/../'):
                input_buffer = '/' + input_buffer[4:]
                if output_buffer:
                    output_buffer.pop()
            elif input_buffer == '/..':
                input_buffer = '/'
                if output_buffer:
                    output_buffer.pop()
            # D. if the input buffer consists only of "." or "..", then remove
            #    that from the input buffer.
            elif input_buffer == '.' or input_buffer == '..':
                input_buffer = ''
            # E. move the first path segment in the input buffer to the end of
            #    the output buffer, including the initial "/" character (if
            #    any) and any subsequent characters up to, but not including,
            #    the next "/" character or the end of the input buffer.
            else:
                if input_buffer.startswith('/'):
                    # Find next / after the first one
                    next_slash = input_buffer.find('/', 1)
                    if next_slash == -1:
                        output_buffer.append(input_buffer)
                        input_buffer = ''
                    else:
                        output_buffer.append(input_buffer[:next_slash])
                        input_buffer = input_buffer[next_slash:]
                else:
                    # No leading slash, find next /
                    next_slash = input_buffer.find('/')
                    if next_slash == -1:
                        output_buffer.append(input_buffer)
                        input_buffer = ''
                    else:
                        output_buffer.append(input_buffer[:next_slash])
                        input_buffer = input_buffer[next_slash:]

        return ''.join(output_buffer)

    def merge_paths(base_path, ref_path):
        """RFC 3986 Section 5.2.3 merge_paths."""
        if base_authority and not base_path:
            # If base has authority but empty path, treat as "/"
            base_path = '/'
        if ref_path.startswith('/'):
            return ref_path
        else:
            # Find last / in base_path
            last_slash = base_path.rfind('/')
            if last_slash == -1:
                return '/' + ref_path
            else:
                return base_path[:last_slash + 1] + ref_path

    # Parse base and reference URLs
    base_scheme, base_authority, base_path, base_query, base_frag = parse_url(base)
    ref_scheme, ref_authority, ref_path, ref_query, ref_frag = parse_url(url)

    # RFC 3986 Section 5.2.2 Transform References
    if ref_scheme:
        # Reference has scheme: use reference components directly
        target_scheme = ref_scheme
        target_authority = ref_authority
        target_path = remove_dot_segments(ref_path)
        target_query = ref_query
    elif ref_authority:
        # Reference has authority but no scheme: inherit base scheme
        target_scheme = base_scheme
        target_authority = ref_authority
        target_path = remove_dot_segments(ref_path)
        target_query = ref_query
    elif not ref_path:
        # Reference has no path
        if ref_query:
            target_scheme = base_scheme
            target_authority = base_authority
            target_path = base_path
            target_query = ref_query
        else:
            target_scheme = base_scheme
            target_authority = base_authority
            target_path = base_path
            target_query = base_query
    else:
        # Reference has a relative path
        target_scheme = base_scheme
        target_authority = base_authority
        target_path = remove_dot_segments(merge_paths(base_path, ref_path))
        target_query = ref_query

    # Fragment is always taken from reference if present, otherwise from base
    if ref_frag:
        target_frag = ref_frag
    else:
        target_frag = base_frag

    # Reconstruct the URL
    result = ''
    if target_scheme:
        result += target_scheme + ':'
    if target_authority:
        result += '//' + target_authority
    result += target_path
    if target_query:
        result += '?' + target_query
    if target_frag:
        result += '#' + target_frag

    return result
