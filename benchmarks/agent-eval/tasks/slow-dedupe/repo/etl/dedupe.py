"""Remove duplicate records, keeping the first occurrence."""


def dedupe(records, key=None):
    seen = []
    out = []
    for r in records:
        k = key(r) if key else r
        if k not in seen:
            seen.append(k)
            out.append(r)
    return out
