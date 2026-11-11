"""File outputs: GeoTIFF (score, evidence layers), PNG overlays, GeoJSON, report.

GeoTIFFs are written with tifffile + manual GeoTIFF keys (EPSG:4326) so QGIS /
Google Earth / the web console can place them correctly. PNGs are generated with
Pillow: a natural-colour composite plus a hot-colour anomaly overlay, and a
score map with a fixed colour ramp.
"""

from __future__ import annotations

import json
import os
from typing import Optional, Sequence

import numpy as np
import tifffile
from PIL import Image

GT_MODEL_PIXEL_SCALE = 33550
GT_MODEL_TIEPOINT = 33922
GT_GEOKEY_DIRECTORY = 34735


def write_geotiff(path: str, data: np.ndarray, bbox_wsen: Sequence[float]) -> None:
    """Write a single-band float32 GeoTIFF georeferenced to EPSG:4326."""
    h, w = data.shape
    west, south, east, north = (float(v) for v in bbox_wsen)
    sx = (east - west) / w
    sy = (north - south) / h
    geokeys = np.array(
        [1, 1, 0, 3,
         1024, 0, 1, 2,   # GTModelTypeGeoKey = ModelTypeGeographic
         1025, 0, 1, 1,   # GTRasterTypeGeoKey = RasterPixelIsArea
         2048, 0, 1, 4326],  # GeographicTypeGeoKey = WGS84
        dtype=np.float64,
    )
    tifffile.imwrite(
        path,
        np.ascontiguousarray(data, dtype=np.float32),
        photometric="minisblack",
        metadata=None,
        extratags=[
            (GT_MODEL_PIXEL_SCALE, "d", 3, (sx, sy, 1.0), True),
            (GT_MODEL_TIEPOINT, "d", 6, (0.0, 0.0, 0.0, west, north, 0.0), True),
            (GT_GEOKEY_DIRECTORY, "d", 16, geokeys, True),
        ],
    )


# ---------------------------------------------------------------- PNG helpers

def _stretch(arr: np.ndarray, low_p: float = 2.0, high_p: float = 98.0) -> np.ndarray:
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.zeros_like(arr)
    lo, hi = np.percentile(valid, [low_p, high_p])
    if hi - lo < 1e-6:
        hi = lo + 1e-6
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def _hot_lut(t: np.ndarray) -> np.ndarray:
    """Black→purple→red→yellow→white ramp; t in [0,1] → (H,W,3) uint8."""
    xs = np.array([0.0, 0.25, 0.50, 0.75, 1.0], dtype=np.float32)
    colors = np.array(
        [
            [8, 8, 24],
            [74, 12, 107],
            [199, 32, 32],
            [249, 142, 9],
            [255, 250, 190],
        ],
        dtype=np.float32,
    )
    t = np.clip(t, 0.0, 1.0)
    out = np.zeros(t.shape + (3,), dtype=np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, xs, colors[:, ch])
    return out.astype(np.uint8)


def write_score_png(path: str, score: np.ndarray) -> None:
    img = _hot_lut(np.nan_to_num(score, nan=0.0) / 100.0)
    Image.fromarray(img, mode="RGB").save(path, format="PNG")


def write_overlay_png(
    path: str,
    composite: np.ndarray,
    score: np.ndarray,
    alpha_floor: float = 40.0,
) -> None:
    """Natural colour + anomaly overlay (transparent below ``alpha_floor``)."""
    rgb = (_stretch(composite) * 255).astype(np.uint8)
    overlay = _hot_lut(np.nan_to_num(score, nan=0.0) / 100.0).astype(np.float32)
    alpha = np.clip((np.nan_to_num(score, nan=0.0) - alpha_floor) / (100.0 - alpha_floor), 0.0, 1.0)
    alpha = (alpha * 0.85)[..., None]
    blended = rgb.astype(np.float32) * (1 - alpha) + overlay * alpha
    Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), mode="RGB").save(path, format="PNG")


def write_layer_png(path: str, layer: np.ndarray) -> None:
    img = _hot_lut(np.nan_to_num(layer, nan=0.0))
    Image.fromarray(img, mode="RGB").save(path, format="PNG")


# ---------------------------------------------------------------- JSON / misc

def write_json(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def job_dir(base_dir: str, job_id: str) -> str:
    path = os.path.join(base_dir, job_id)
    os.makedirs(path, exist_ok=True)
    return path


SAFE_FILENAME_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


def safe_filename(name: str) -> Optional[str]:
    """Reject path tricks; allow only plain artifact names."""
    if not name or len(name) > 128:
        return None
    if any(ch not in SAFE_FILENAME_CHARS for ch in name) or name.startswith("."):
        return None
    return name
