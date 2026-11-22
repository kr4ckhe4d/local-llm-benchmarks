"""Remove duplicate records, keeping the first occurrence."""


def _freeze(v):
    # Equal values must map to equal frozen forms, mirroring ==: 1 == 1.0 == True, (1, 2) != [1, 2].
    if isinstance(v, dict):
        return ("d", frozenset((k, _freeze(x)) for k, x in v.items()))
    if isinstance(v, list):
        return ("l", tuple(_freeze(x) for x in v))
    if isinstance(v, tuple):
        return ("t", tuple(_freeze(x) for x in v))
    if isinstance(v, (set, frozenset)):
        return ("s", frozenset(_freeze(x) for x in v))
    return v


def dedupe(records, key=None):
    seen = set()
    out = []
    for r in records:
        k = _freeze(key(r) if key else r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out
