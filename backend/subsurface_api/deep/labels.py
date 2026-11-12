"""Connected-component labeling + convex-hull polygons (pure numpy/python).

Detection regions are 8-connected groups of valid pixels whose fused score is
at or above the request threshold (legacy mode) or whose CPF cluster is
surrogate-significant (cpf mode). Each region becomes one GeoJSON feature:

* geometry: convex hull of member pixel centres, converted to EPSG:4326;
  the **axis-aligned bbox and length/width ratio** are also reported so
  elongated line-like detections (rows of shafts, access tracks) are not
  hidden by the hull's blob shape;
* properties: area (m², geodesic), mean/max score, persistence, coherence,
  confidence class, centroid, and — in cpf mode — the cluster's conformal
  p-value.

Small isolated specks (< ``min_pixels``) are dropped — at 10 m GSD the default
``min_pixels=9`` means regions must be at least ~900 m² to be reported.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..geo import spherical_area_m2
from .fusion import classify_component

LngLat = Tuple[float, float]


def label_components(mask: np.ndarray) -> Tuple[np.ndarray, int]:
    """8-connected labeling via BFS. Returns ``(labels, count)``; 0 = background."""
    labels = np.zeros(mask.shape, dtype=np.int32)
    current = 0
    h, w = mask.shape
    for r0, c0 in np.argwhere(mask):
        r0, c0 = int(r0), int(c0)
        if labels[r0, c0]:
            continue
        current += 1
        labels[r0, c0] = current
        queue: deque = deque([(r0, c0)])
        while queue:
            r, c = queue.popleft()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < h and 0 <= cc < w and mask[rr, cc] and not labels[rr, cc]:
                        labels[rr, cc] = current
                        queue.append((rr, cc))
    return labels, current


def _convex_hull(points: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Andrew's monotone chain. Returns the hull ring (counter-clockwise)."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return list(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: List[Tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def pixel_to_lonlat(
    x: float, y: float, bbox_wsen: Sequence[float], width: int, height: int
) -> LngLat:
    """Pixel-centre coordinate → lon/lat (bbox = [W, S, E, N])."""
    w_, s_, e_, n_ = bbox_wsen
    lon = w_ + (x + 0.5) / width * (e_ - w_)
    lat = n_ - (y + 0.5) / height * (n_ - s_)
    return (float(lon), float(lat))


def detections_to_geojson(
    labels: np.ndarray,
    count: int,
    score: np.ndarray,
    coherence: np.ndarray,
    persistence: np.ndarray,
    bbox_wsen: Sequence[float],
    cell_size_m: float,
    min_pixels: int = 9,
    max_components: int = 50,
    confidence_by_id: Optional[Dict[int, str]] = None,
    extra_props_by_id: Optional[Dict[int, Dict]] = None,
    synthetic: bool = False,
) -> Tuple[List[Dict], List[Dict]]:
    """Build GeoJSON features + a plain-python summary for the report.

    ``confidence_by_id`` / ``extra_props_by_id`` override/extend per-component
    properties (used by the CPF fusion mode to attach conformal p-values);
    ``synthetic=True`` stamps every feature as living on planted test data.
    """
    w_, s_, e_, n_ = bbox_wsen
    height, width = labels.shape
    approx_area_per_px = cell_size_m * cell_size_m

    features: List[Dict] = []
    summaries: List[Dict] = []

    comp_ids = [i for i in range(1, count + 1) if int((labels == i).sum()) >= min_pixels]
    comp_ids.sort(key=lambda i: int((labels == i).sum()), reverse=True)
    comp_ids = comp_ids[: max_components]

    for cid in comp_ids:
        sel = labels == cid
        n_px = int(sel.sum())
        ys, xs = np.nonzero(sel)

        mean_score = float(np.nanmean(score[sel]))
        max_score = float(np.nanmax(score[sel]))
        mean_coh = float(np.nanmean(coherence[sel]))
        mean_pers = float(np.nanmean(persistence[sel]))
        confidence = (confidence_by_id or {}).get(cid) or classify_component(
            mean_score, mean_coh, mean_pers, n_px
        )

        hull_px = _convex_hull([(float(x), float(y)) for x, y in zip(xs, ys)])
        ring = [pixel_to_lonlat(x, y, bbox_wsen, width, height) for x, y in hull_px]
        if len(ring) >= 3:
            ring = ring + [ring[0]]
            area_m2 = float(spherical_area_m2(ring[:-1]))
        else:
            area_m2 = n_px * approx_area_per_px

        cx, cy = float(xs.mean()), float(ys.mean())
        centroid = pixel_to_lonlat(cx, cy, bbox_wsen, width, height)

        # Axis-aligned footprint + elongation: keeps line-like detections
        # (shaft rows, tracks) visible even though the geometry is a hull.
        bw = pixel_to_lonlat(float(xs.min()), float(ys.min()), bbox_wsen, width, height)
        be = pixel_to_lonlat(float(xs.max()), float(ys.max()), bbox_wsen, width, height)
        span_x_m = max(1.0, (float(xs.max()) - float(xs.min()) + 1) * cell_size_m)
        span_y_m = max(1.0, (float(ys.max()) - float(ys.min()) + 1) * cell_size_m)
        elongation = round(float(max(span_x_m, span_y_m) / min(span_x_m, span_y_m)), 2)

        geometry = {
            "type": "Polygon",
            "coordinates": [[[round(lon, 7), round(lat, 7)] for lon, lat in ring]],
        }
        properties = {
            "component_id": cid,
            "pixels": n_px,
            "area_m2": round(area_m2, 1),
            "area_hectares": round(area_m2 / 10000.0, 4),
            "mean_score_0_100": round(mean_score, 1),
            "max_score_0_100": round(max_score, 1),
            "mean_coherence": round(mean_coh, 3),
            "mean_persistence": round(mean_pers, 3),
            "confidence": confidence,
            "centroid_lonlat": [round(centroid[0], 7), round(centroid[1], 7)],
            "cell_size_m": round(cell_size_m, 2),
            "bbox_wgs84": [round(bw[0], 7), round(bw[1], 7), round(be[0], 7), round(be[1], 7)],
            "elongation_ratio": elongation,
            "synthetic": bool(synthetic),
        }
        if extra_props_by_id and cid in extra_props_by_id:
            properties.update(extra_props_by_id[cid])
        features.append({"type": "Feature", "geometry": geometry, "properties": properties})
        summaries.append(properties)

    summaries.sort(key=lambda d: d["mean_score_0_100"], reverse=True)
    return features, summaries
