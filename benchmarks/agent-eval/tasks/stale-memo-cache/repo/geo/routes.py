import math

from .cache import memoize

CITIES = {"perth": (-31.95, 115.86), "sydney": (-33.87, 151.21), "melbourne": (-37.81, 144.96),
          "adelaide": (-34.93, 138.60), "darwin": (-12.46, 130.84)}
KM_PER_MI = 1.609344


@memoize
def distance(a: str, b: str, units: str = "km") -> float:
    (la1, lo1), (la2, lo2) = CITIES[a], CITIES[b]
    p1, p2, dl = math.radians(la1), math.radians(la2), math.radians(lo2 - lo1)
    km = 6371 * math.acos(min(1.0, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))
    return round(km if units == "km" else km / KM_PER_MI, 1)


@memoize
def route_length(stops, units: str = "km") -> float:
    return round(sum(distance(a, b, units=units) for a, b in zip(stops, stops[1:])), 1)
