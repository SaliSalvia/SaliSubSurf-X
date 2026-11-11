"""Real terrain analysis from the open AWS Terrain Tiles (Terrarium) global DEM.

The tiles are anonymous-access PNGs in Web Mercator / "Terrarium" encoding:
``elevation_m = R * 256 + G + B / 256 - 32768``.
No account, no API key. The module samples the DEM onto a regular lat/lon grid over the
region, then derives elevation statistics, Horn slope, Riley TRI and the circular
consistency of the gradient orientation — all with per-run provenance.
"""

from __future__ import annotations

import io
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import requests
from PIL import Image

from ..geo import bbox

TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
PROVIDER = "AWS Open Data — Terrain Tiles (Tilezen)"
LICENCE_NOTE = (
    "Composite global DEM of public/open sources (SRTM, GMTED2010, ETOPO1, NED, "
    "EU-DEM, ...). Per-tile source provenance is documented by the Mapzen Terrain "
    "Tiles project. Accessed anonymously over HTTPS."
)
MAX_TILES_DEFAULT = 64
Z_MIN, Z_MAX = 8, 14
GRID_W = GRID_H = 256

CAVEATS: List[str] = [
    "Terrain indicators describe surface shape only — they are NOT evidence of a "
    "buried object and carry no depth information.",
    "DEM cells are tens of metres wide; anything smaller than one cell cannot appear "
    "in the analysis.",
    "Micro-relief can originate from geology, hydrology, vegetation, agriculture, or "
    "DEM processing artefacts.",
    "Any field decision must be confirmed with ground-based geophysics (EMI, "
    "magnetometry, GPR) and local regulations.",
]


# --------------------------------------------------------------------------- #
# Web-Mercator tile math
# --------------------------------------------------------------------------- #

def lonlat_to_tilef(lon: float, lat: float, z: int) -> Tuple[float, float]:
    """Continuous tile coordinates (units = tiles) for a lon/lat point."""
    n = 2.0**z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(max(-85.05112878, min(85.05112878, lat)))
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    return x, y


def tiles_for_bbox(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float, z: int
) -> Tuple[List[int], List[int]]:
    x0f, y0f = lonlat_to_tilef(min_lon, max_lat, z)  # top-left corner
    x1f, y1f = lonlat_to_tilef(max_lon, min_lat, z)  # bottom-right corner
    n = 2**z
    xs = list(range(max(0, int(math.floor(x0f))), min(n - 1, int(math.floor(x1f))) + 1))
    ys = list(range(max(0, int(math.floor(y0f))), min(n - 1, int(math.floor(y1f))) + 1))
    return xs, ys


def choose_zoom(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    max_tiles: int = MAX_TILES_DEFAULT,
) -> Tuple[int, List[int], List[int]]:
    """Highest zoom (best resolution) whose tile count fits the budget."""
    for z in range(Z_MAX, Z_MIN - 1, -1):
        xs, ys = tiles_for_bbox(min_lon, min_lat, max_lon, max_lat, z)
        if len(xs) * len(ys) <= max_tiles:
            return z, xs, ys
    raise ValueError(
        "Region bbox is too large for DEM analysis (tile budget exceeded even at "
        f"zoom {Z_MIN}). Sketch a smaller region."
    )


# --------------------------------------------------------------------------- #
# Tile decoding
# --------------------------------------------------------------------------- #

def decode_terrarium(data: bytes) -> np.ndarray:
    """Decode a Terrarium PNG tile to an elevation grid (metres)."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    arr = np.asarray(img, dtype=np.float64)
    return arr[:, :, 0] * 256.0 + arr[:, :, 1] + arr[:, :, 2] / 256.0 - 32768.0


def fetch_tile(
    z: int, x: int, y: int, timeout: float = 30.0, session: Optional[requests.Session] = None
) -> Optional[np.ndarray]:
    """Download one tile; return None on any failure (caller counts nodata)."""
    getter = session or requests
    try:
        r = getter.get(TILE_URL.format(z=z, x=x, y=y), timeout=timeout)
        if r.status_code != 200:
            return None
        return decode_terrarium(r.content)
    except (requests.RequestException, OSError):
        return None


# --------------------------------------------------------------------------- #
# Terrain metrics
# --------------------------------------------------------------------------- #

def horn_slope(
    grid: np.ndarray, cell_x: float, cell_y: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Horn 3×3 slope (degrees) plus the d/dx, d/dy gradients.

    ``grid`` rows go from north (row 0) to south; columns west→east.
    """
    zp = np.pad(grid, 1, mode="edge")
    a = zp[0:-2, 0:-2]
    b = zp[0:-2, 1:-1]
    c = zp[0:-2, 2:]
    d = zp[1:-1, 0:-2]
    f = zp[1:-1, 2:]
    g = zp[2:, 0:-2]
    h = zp[2:, 1:-1]
    i = zp[2:, 2:]
    dzdx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * cell_x)
    dzdy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * cell_y)
    slope_deg = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    return slope_deg, dzdx, dzdy


def riley_tri(grid: np.ndarray) -> np.ndarray:
    """Riley Terrain Ruggedness Index per cell (sqrt of squared neighbour diffs)."""
    zp = np.pad(grid, 1, mode="edge")
    center = zp[1:-1, 1:-1]
    acc = np.zeros_like(center)
    h, w = center.shape
    for dy in range(3):
        for dx in range(3):
            if dx == 1 and dy == 1:
                continue
            acc += (zp[dy : dy + h, dx : dx + w] - center) ** 2
    return np.sqrt(acc)


def gradient_orientation(dzdx: np.ndarray, dzdy: np.ndarray) -> Tuple[float, float]:
    """Slope-weighted circular mean of the uphill azimuth and its consistency R.

    Rows increase southwards, so the uphill direction in (east, north) components is
    ``(dzdx, -dzdy)``. Azimuth is degrees clockwise from north. ``R`` ∈ [0, 1]:
    1 = one perfectly consistent gradient direction, 0 = uniformly scattered.
    """
    mag = np.hypot(dzdx, dzdy)
    total = float(mag.sum())
    if total <= 0.0:
        return float("nan"), 0.0
    theta = np.arctan2(dzdx, -dzdy)  # radians, from north, clockwise-positive
    sx = float((mag * np.sin(theta)).sum())
    cx = float((mag * np.cos(theta)).sum())
    r = math.hypot(sx, cx) / total
    mean_az = math.degrees(math.atan2(sx, cx)) % 360.0
    return mean_az, r


# --------------------------------------------------------------------------- #
# Region analysis
# --------------------------------------------------------------------------- #

def analyze_region(
    ring: Sequence[Tuple[float, float]], max_tiles: int = MAX_TILES_DEFAULT
) -> Dict:
    """Full DEM analysis for a validated polygon ring; returns a TerrainResponse-shaped dict."""
    min_lon, min_lat, max_lon, max_lat = bbox(ring)
    z, xs, ys = choose_zoom(min_lon, min_lat, max_lon, max_lat, max_tiles)

    mosaic: Dict[Tuple[int, int], Optional[np.ndarray]] = {}
    session = requests.Session()
    for x in xs:
        for y in ys:
            mosaic[(x, y)] = fetch_tile(z, x, y, session=session)
    tiles_fetched = sum(1 for v in mosaic.values() if v is not None)
    if tiles_fetched == 0:
        raise RuntimeError(
            "No DEM tiles could be downloaded; check network connectivity and retry."
        )

    # Regular lat/lon sampling grid over the bbox (row 0 = north).
    lons = np.linspace(min_lon, max_lon, GRID_W)
    lats = np.linspace(max_lat, min_lat, GRID_H)
    lon_g, lat_g = np.meshgrid(lons, lats)

    txf, tyf = np.vectorize(lambda lo, la: lonlat_to_tilef(lo, la, z))(lon_g, lat_g)
    gx = txf * 256.0
    gy = tyf * 256.0
    tx = np.floor(gx / 256.0).astype(int)
    ty = np.floor(gy / 256.0).astype(int)
    fx = gx - tx * 256.0
    fy = gy - ty * 256.0

    grid = np.full((GRID_H, GRID_W), np.nan)
    x0 = np.clip(np.floor(fx).astype(int), 0, 254)
    y0 = np.clip(np.floor(fy).astype(int), 0, 254)
    dx = fx - x0
    dy = fy - y0
    for (x, y), tile in mosaic.items():
        if tile is None:
            continue
        mask = (tx == x) & (ty == y)
        if not mask.any():
            continue
        z00 = tile[y0[mask], x0[mask]]
        z10 = tile[y0[mask], x0[mask] + 1]
        z01 = tile[y0[mask] + 1, x0[mask]]
        z11 = tile[y0[mask] + 1, x0[mask] + 1]
        grid[mask] = (
            z00 * (1 - dx[mask]) * (1 - dy[mask])
            + z10 * dx[mask] * (1 - dy[mask])
            + z01 * (1 - dx[mask]) * dy[mask]
            + z11 * dx[mask] * dy[mask]
        )

    nodata_fraction = float(np.isnan(grid).mean())
    # A mostly-empty grid still yields numbers (min/max/mean of the few covered
    # cells), but they describe a sliver of the region while looking authoritative.
    # Refuse instead of returning a misleading report.
    if nodata_fraction > 0.5:
        raise RuntimeError(
            f"Only {100.0 * (1.0 - nodata_fraction):.0f}% of the DEM grid could be "
            "sampled (missing tiles); retry, or sketch a smaller region."
        )
    mean_elev = float(np.nanmean(grid)) if not np.isnan(grid).all() else float("nan")
    if not math.isfinite(mean_elev):
        # Tiles downloaded but none of them cover the sampling grid (e.g. all overlapping
        # tiles failed). Returning NaN here would later break JSON serialisation with a 500.
        raise RuntimeError(
            "DEM tiles were downloaded but contain no valid samples for this region; retry."
        )
    filled = np.where(np.isnan(grid), mean_elev, grid)

    # Cell size in metres for the sampling grid (rows go southwards).
    lat_mid = 0.5 * (min_lat + max_lat)
    cell_x = (max_lon - min_lon) * 111_320.0 * math.cos(math.radians(lat_mid)) / (GRID_W - 1)
    cell_y = (max_lat - min_lat) * 110_574.0 / (GRID_H - 1)

    slope_deg, dzdx, dzdy = horn_slope(filled, cell_x, cell_y)
    tri = riley_tri(filled)
    mean_az, consistency = gradient_orientation(dzdx, dzdy)

    resolution = 156543.03392 * math.cos(math.radians(lat_mid)) / (2**z)
    elevation = {
        "min_m": round(float(filled.min()), 2),
        "max_m": round(float(filled.max()), 2),
        "mean_m": round(float(filled.mean()), 2),
        "std_m": round(float(filled.std()), 2),
    }
    slope = {
        "mean_deg": round(float(slope_deg.mean()), 3),
        "max_deg": round(float(slope_deg.max()), 3),
        "std_deg": round(float(slope_deg.std()), 3),
        "percent_over_15": round(float((slope_deg > 15.0).mean() * 100.0), 2),
    }
    provenance = [
        {
            "provider": PROVIDER,
            "collection": f"terrarium z{z}",
            "licence_note": LICENCE_NOTE,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    ]
    return {
        "zoom": z,
        "resolution_m_per_px": round(resolution, 2),
        "nodata_fraction": round(nodata_fraction, 4),
        "tiles_fetched": tiles_fetched,
        "elevation": elevation,
        "slope": slope,
        "roughness_tri_mean": round(float(tri.mean()), 3),
        "dominant_gradient_azimuth_deg": (
            round(mean_az, 1) if math.isfinite(mean_az) else None
        ),
        "gradient_consistency": round(consistency, 4),
        "provenance": provenance,
        "caveats": CAVEATS,
    }
