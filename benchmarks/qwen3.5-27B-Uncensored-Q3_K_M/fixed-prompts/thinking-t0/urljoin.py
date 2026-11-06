def urljoin_(base, url):
    def parse_url(s):
        scheme = ''
        authority = ''
        path = ''
        query = ''
        fragment = ''
        
        if ':' in s:
            idx = s.find(':')
            scheme = s[:idx]
            s = s[idx+1:]
        
        if s.startswith('//'):
            s = s[2:]
            idx = s.find('/')
            if idx == -1:
                idx = s.find('?')
                if idx == -1:
                    idx = s.find('#')
                    if idx == -1:
                        idx = len(s)
            authority = s[:idx]
            s = s[idx:]
        
        idx = s.find('?')
        if idx == -1:
            idx = s.find('#')
            if idx == -1:
                idx = len(s)
        path = s[:idx]
        s = s[idx:]
        
        idx = s.find('#')
        if idx == -1:
            idx = len(s)
        query = s[:idx]
        fragment = s[idx:]
        
        return scheme, authority, path, query, fragment
    
    def normalize_path(path):
        if not path:
            return path
        segments = path.split('/')
        result = []
        for seg in segments:
            if seg == '.':
                continue
            elif seg == '..':
                if result:
                    result.pop()
            else:
                result.append(seg)
        return '/'.join(result)
    
    def build_url(scheme, authority, path, query, fragment):
        result = ''
        if scheme:
            result += f'{scheme}:'
        if authority:
            result += f'//{authority}'
        result += path
        if query:
            result += f'?{query}'
        if fragment:
            result += f'#{fragment}'
        return result
    
    base_scheme, base_authority, base_path, base_query, base_fragment = parse_url(base)
    rel_scheme, rel_authority, rel_path, rel_query, rel_fragment = parse_url(url)
    
    if rel_scheme:
        scheme = rel_scheme
        authority = rel_authority
        path = rel_path
        query = rel_query
        fragment = rel_fragment
    elif rel_authority:
        scheme = base_scheme
        authority = rel_authority
        path = rel_path
        query = rel_query
        fragment = rel_fragment
    elif rel_path.startswith('/'):
        scheme = base_scheme
        authority = base_authority
        path = rel_path
        query = rel_query
        fragment = rel_fragment
    elif not rel_path:
        if rel_query:
            scheme = base_scheme
            authority = base_authority
            path = base_path
            query = rel_query
            fragment = rel_fragment
        elif rel_fragment:
            scheme = base_scheme
            authority = base_authority
            path = base_path
            query = base_query
            fragment = rel_fragment
        else:
            scheme = base_scheme
            authority = base_authority
            path = base_path
            query = base_query
            fragment = ''
    else:
        scheme = base_scheme
        authority = base_authority
        if base_path.endswith('/'):
            path = base_path + rel_path
        else:
            path = base_path[:base_path.rfind('/')+1] + rel_path
        query = rel_query
        fragment = rel_fragment
    
    path = normalize_path(path)
    return build_url(scheme, authority, path, query, fragment)
