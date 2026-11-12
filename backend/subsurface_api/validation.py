"""Strict region validation: vertex budget, geometry sanity, area bounds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from shapely.geometry import LineString

from .geo import bbox, centroid, normalize_ring, perimeter_m, spherical_area_m2

MIN_VERTICES = 3
MAX_VERTICES = 10
MIN_AREA_M2 = 500.0          # below this the region is meaningless for analysis
WARN_AREA_M2 = 100_000_000.0  # 100 km² — analysis gets coarse
MAX_AREA_M2 = 500_000_000.0   # 500 km² — hard rejection


@dataclass
class RegionCheck:
    valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    vertex_count: int = 0
    area_sqm: float = 0.0
    area_hectares: float = 0.0
    perimeter_m: float = 0.0
    centroid: Tuple[float, float] = (0.0, 0.0)
    bbox: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


def validate_region(points: Sequence[Sequence[float]]) -> RegionCheck:
    """Validate a polygon ring and return a full report (never raises for geometry issues)."""
    issues: List[str] = []
    warnings: List[str] = []

    ring = normalize_ring(points)
    n = len(ring)

    if n < MIN_VERTICES:
        issues.append(
            f"At least {MIN_VERTICES} distinct vertices are required (got {n})."
        )
    if n > MAX_VERTICES:
        issues.append(
            f"At most {MAX_VERTICES} vertices are allowed (got {n}). Extra vertices: "
            f"simplify the outline before submitting."
        )

    for lon, lat in ring:
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            issues.append("Coordinates out of range (longitude ±180, latitude ±90).")
            break

    if n >= MIN_VERTICES and len(set(ring)) == n:
        # shapely checks self-intersection on the open ring
        if not LineString(ring).is_simple:
            issues.append(
                "Polygon edges cross each other (self-intersecting outline)."
            )

    area = spherical_area_m2(ring) if n >= MIN_VERTICES else 0.0
    if n >= MIN_VERTICES:
        if area < MIN_AREA_M2:
            issues.append(
                f"Region too small ({area:.0f} m² < {MIN_AREA_M2:.0f} m² minimum)."
            )
        if area > MAX_AREA_M2:
            issues.append(
                f"Region too large ({area / 1e6:.1f} km² > {MAX_AREA_M2 / 1e6:.0f} km² maximum)."
            )
        elif area > WARN_AREA_M2:
            warnings.append(
                "Large region: catalog metadata and DEM analysis will be coarse. "
                "Prefer regions under 100 km²."
            )

    c = centroid(ring) if n else (0.0, 0.0)
    return RegionCheck(
        valid=not issues,
        issues=issues,
        warnings=warnings,
        vertex_count=n,
        area_sqm=area,
        area_hectares=area / 10_000.0,
        perimeter_m=perimeter_m(ring),
        centroid=(round(c[0], 7), round(c[1], 7)),
        bbox=[round(v, 7) for v in bbox(ring)] if n else [0.0, 0.0, 0.0, 0.0],
    )
