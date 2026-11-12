"""Unit tests for the terrain module — no network access is performed."""

import io

import numpy as np
from PIL import Image

from subsurface_api.providers import terrain as t


def _terrarium_png(elev_grid):
    """Encode a float elevation grid (2-D array) into a Terrarium-format PNG."""
    v = np.asarray(elev_grid) + 32768.0
    r = np.floor(v / 256.0)
    g = v - r * 256.0
    b = (g - np.floor(g)) * 256.0
    rgb = np.stack([r, np.floor(g), np.floor(b)], axis=-1).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, format="PNG")
    return buf.getvalue()


def test_decode_terrarium_roundtrip():
    grid = np.array([[123.5, 0.0], [-40.25, 900.75]])
    elev = t.decode_terrarium(_terrarium_png(grid))
    assert np.allclose(elev, grid, atol=1.0 / 256.0 + 1e-6)


def test_lonlat_to_tile_reference_values():
    x, y = t.lonlat_to_tilef(0.0, 0.0, 1)
    assert abs(x - 1.0) < 1e-9 and abs(y - 1.0) < 1e-9
    x, y = t.lonlat_to_tilef(-180.0, 85.05112878, 2)
    assert abs(x - 0.0) < 1e-6 and abs(y - 0.0) < 1e-6


def test_tiles_for_bbox_single_tile():
    xs, ys = t.tiles_for_bbox(0.01, -0.01, 0.02, -0.02, 8)
    # At z8 the equator lies exactly on the 128 tile boundary.
    assert xs == [128] and ys == [128]


def test_choose_zoom_respects_budget():
    xs, ys = t.tiles_for_bbox(0.0, 0.0, 1.0, 1.0, 8)  # sanity: ~4 tiles at z8
    assert len(xs) * len(ys) <= 4
    z, xs, ys = t.choose_zoom(0.0, 0.0, 1.0, 1.0, max_tiles=64)
    assert t.Z_MIN <= z <= t.Z_MAX


def test_horn_slope_linear_ramp_is_45_degrees():
    grid = np.tile(np.arange(64, dtype=float), (64, 1))  # 1 m rise per 1 m cell
    slope, dzdx, dzdy = t.horn_slope(grid, cell_x=1.0, cell_y=1.0)
    # interior cells are exactly 45°; the two edge columns are halved by edge padding
    assert np.allclose(slope[:, 1:-1], 45.0, atol=0.5)
    assert np.allclose(slope[:, 0], 26.565, atol=0.01)
    assert np.allclose(slope[:, -1], 26.565, atol=0.01)
    assert np.allclose(dzdx[:, 1:-1], 1.0, atol=1e-9)
    assert np.allclose(dzdy, 0.0, atol=1e-9)


def test_gradient_orientation_ramp_uphill_is_east():
    grid = np.tile(np.arange(64, dtype=float), (64, 1))  # rises eastwards
    _, dzdx, dzdy = t.horn_slope(grid, 1.0, 1.0)
    az, consistency = t.gradient_orientation(dzdx, dzdy)
    assert abs(az - 90.0) < 1.0  # uphill azimuth = 90° (east)
    assert consistency > 0.99


def test_riley_tri_flat_surface_is_zero():
    grid = np.zeros((16, 16))
    tri = t.riley_tri(grid)
    assert np.allclose(tri, 0.0)
