from geo.routes import distance


def test_known_distance():
    assert 3200 < distance("perth", "sydney") < 3350


def test_cache_hits():
    distance.cache_clear()
    distance("perth", "darwin")
    distance("perth", "darwin")
    info = distance.cache_info()
    assert info["hits"] == 1 and info["misses"] == 1 and info["size"] == 1
