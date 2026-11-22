from geo.cache import memoize
from geo.routes import distance, route_length


def test_units_not_mixed():
    distance.cache_clear()
    km = distance("perth", "sydney", units="km")
    mi = distance("perth", "sydney", units="mi")
    assert mi < km * 0.7
    assert distance("perth", "sydney", "mi") == mi


def test_waypoints_list():
    stops = ["perth", "adelaide", "melbourne", "sydney"]
    assert route_length(stops) > route_length(["perth", "sydney"])
    assert route_length(stops, units="mi") < route_length(stops, units="km")


def test_kwarg_order_and_hits():
    calls = []

    @memoize
    def f(a, *, x=0, y=0):
        calls.append((a, x, y))
        return a + 10 * x + 100 * y

    assert f(1, x=2, y=3) == 321
    assert f(1, y=3, x=2) == 321
    assert len(calls) == 1
    assert f(1, x=3, y=2) == 231
    assert f(1) == 1 and f(1, x=0) == 1
    assert f.cache_info()["hits"] >= 1


def test_unhashable_not_cached_but_works():
    calls = []

    @memoize
    def g(xs, k=None):
        calls.append(1)
        return sum(xs)

    assert g([1, 2]) == 3 and g([1, 2]) == 3 and g([1, 2], k={"a": 1}) == 3
    assert len(calls) == 3
    assert g((1, 2)) == 3 and g((1, 2)) == 3
    assert len(calls) == 4


def test_positional_vs_keyword_distinct_values():
    @memoize
    def h(a, b=0):
        return (a, b)

    assert h(1, 2) == (1, 2)
    assert h(1, b=3) == (1, 3)
    assert h(1) == (1, 0)


def test_clear():
    distance("perth", "darwin")
    distance.cache_clear()
    assert distance.cache_info() == {"hits": 0, "misses": 0, "size": 0}
