"""Funções geográficas puras (sem dependência de banco)."""
from math import asin, cos, radians, sin, sqrt

Point = tuple[float, float]  # (lat, lng)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = radians(lat1), radians(lat2)
    dphi, dl = p2 - p1, radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _xy(p: Point, ref_lat: float) -> tuple[float, float]:
    return p[1] * 111_320 * cos(radians(ref_lat)), p[0] * 110_540


def point_segment_distance_m(p: Point, a: Point, b: Point) -> float:
    px, py = _xy(p, p[0])
    ax, ay = _xy(a, p[0])
    bx, by = _xy(b, p[0])
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return sqrt((px - ax) ** 2 + (py - ay) ** 2)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return sqrt((px - cx) ** 2 + (py - cy) ** 2)


def distance_to_polyline_m(p: Point, polyline: list[Point]) -> float:
    if len(polyline) == 1:
        return haversine_m(p[0], p[1], *polyline[0])
    return min(point_segment_distance_m(p, polyline[i], polyline[i + 1]) for i in range(len(polyline) - 1))


def polyline_length_m(polyline: list[Point]) -> float:
    return sum(haversine_m(*polyline[i], *polyline[i + 1]) for i in range(len(polyline) - 1))
