"""A small memoize decorator with hit/miss counters."""
import functools


def memoize(fn):
    cache = {}
    stats = {"hits": 0, "misses": 0}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            key = (args, frozenset(kwargs.items()))
            hash(key)
        except TypeError:
            return fn(*args, **kwargs)
        if key in cache:
            stats["hits"] += 1
            return cache[key]
        stats["misses"] += 1
        result = fn(*args, **kwargs)
        cache[key] = result
        return result

    wrapper.cache_info = lambda: dict(stats, size=len(cache))

    def cache_clear():
        cache.clear()
        stats.update(hits=0, misses=0)

    wrapper.cache_clear = cache_clear
    return wrapper
