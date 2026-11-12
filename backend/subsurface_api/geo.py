"""Geodesic helpers shared by validation, catalog and terrain modules.

All functions work with rings expressed as ``(lon, lat)`` pairs in EPSG:4326 degrees.
The spherical polygon-area formula is the same one used by Turf.js / PostGIS geography
(spherical excess of the edge integral), accurate to well under a percent for the
region sizes this API accepts.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

EARTH_RADIUS_M = 6378137.0

# (lon, lat) in degrees
LngLat = Tuple[float, float]


def normalize_ring(points: Sequence[Sequence[float]]) -> List[LngLat]:
    """Clean a raw vertex list into an open ring.

    * converts to ``(lon, lat)`` float pairs,
    * drops consecutive duplicate vertices (including the duplicated closing vertex).
    """
    ring: List[LngLat] = []
    for p in points:
        pair = (float(p[0]), float(p[1]))
        if not ring or pair != ring[-1]:
            ring.append(pair)
    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring.pop()
    return ring


def spherical_area_m2(ring: Sequence[LngLat]) -> float:
    """Geodesic polygon area in square metres (spherical excess approximation)."""
    if len(ring) < 3:
        return 0.0
    total = 0.0
    n = len(ring)
    for i in range(n):
        lon1, lat1 = ring[i]
        lon2, lat2 = ring[(i + 1) % n]
        total += math.radians(lon2 - lon1) * (
            2.0 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2))
        )
    return abs(total) * EARTH_RADIUS_M * EARTH_RADIUS_M / 2.0


def haversine_m(a: LngLat, b: LngLat) -> float:
    """Great-circle distance in metres between two (lon, lat) points."""
    lon1, lat1 = a
    lon2, lat2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, h)))


def perimeter_m(ring: Sequence[LngLat]) -> float:
    """Closed-geodesic perimeter in metres."""
    if len(ring) < 2:
        return 0.0
    total = 0.0
    n = len(ring)
    for i in range(n):
        total += haversine_m(ring[i], ring[(i + 1) % n])
    return total


def centroid(ring: Sequence[LngLat]) -> LngLat:
    """Arithmetic mean of the vertices (adequate for the small regions accepted here)."""
    if not ring:
        return (0.0, 0.0)
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return (lon, lat)


def bbox(ring: Sequence[LngLat]) -> List[float]:
    """``[min_lon, min_lat, max_lon, max_lat]`` of the ring."""
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return [min(lons), min(lats), max(lons), max(lats)]


def ring_to_wkt(ring: Sequence[LngLat]) -> str:
    """WKT POLYGON string (closed ring) for OData geography filters."""
    if len(ring) < 3:
        raise ValueError("A polygon needs at least 3 distinct vertices.")
    closed = list(ring) + [ring[0]]
    coords = ", ".join(f"{lon:.7f} {lat:.7f}" for lon, lat in closed)
    return f"POLYGON(({coords}))"
