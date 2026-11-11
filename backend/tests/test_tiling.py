"""Native-resolution tiling tests (offline, synthetic selftest)."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from subsurface_api.deep.pipeline import (
    DeepParams,
    _native_grid,
    _tile_plan,
    run_selftest,
)

RING = [(50.0, 29.0), (50.02, 29.0), (50.02, 29.015), (50.0, 29.015)]


def _params(**kw):
    base = dict(
        polygon=[list(p) for p in RING],
        date_from="2026-10-08",
        date_to="2026-11-07",
        alpha=0.05,
        n_surrogates=19,   # p floor = 1/20 = 0.05 ≤ alpha
    )
    base.update(kw)
    return DeepParams(**base).sanitized()


def test_native_grid_dimensions_and_caps():
    # ~1.95 km x 1.66 km at 10 m -> ~195x166 px
    w, h = _native_grid([50.0, 29.0, 50.02, 29.015], 10.0)
    assert 180 <= w <= 210
    assert 155 <= h <= 180
    # a 1-degree box at 10 m must be refused (budget)
    with pytest.raises(ValueError, match="budget"):
        _native_grid([50.0, 29.0, 51.0, 30.0], 10.0)


def test_tile_plan_grid_mode_single_tile():
    p = _params(grid=128)
    plan = _tile_plan(p, [50.0, 29.0, 50.02, 29.015])
    assert plan.native is False
    assert plan.n_tiles == 1
    t = plan.tiles[0]
    assert (t.rows, t.cols) == (128, 128)
    assert t.halo_top == 0 and t.halo_left == 0


def test_tile_plan_native_tiles_cover_grid_exactly():
    p = _params(resolution_m=10, tile_px=96)
    plan = _tile_plan(p, [50.0, 29.0, 50.02, 29.015])
    assert plan.native is True and plan.n_tiles >= 4
    covered = np.zeros((plan.height, plan.width), int)
    for t in plan.tiles:
        assert t.fetch_w >= t.cols and t.fetch_h >= t.rows
        # fetch box stays inside the full grid
        assert t.fetch_row0 >= 0 and t.fetch_col0 >= 0
        assert t.fetch_row0 + t.fetch_h <= plan.height
        assert t.fetch_col0 + t.fetch_w <= plan.width
        covered[t.row0:t.row0 + t.rows, t.col0:t.col0 + t.cols] += 1
    # every pixel covered exactly once by a tile CORE
    assert (covered == 1).all()


def test_native_selftest_stitches_and_detects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = _params(resolution_m=10, tile_px=96)
    out = str(tmp_path / "job")
    report = run_selftest(p, RING, None, out)

    assert report["native_resolution"] is True
    assert report["tiles"] >= 4 and report["tiles_ok"] == report["tiles"]
    assert report["cell_size_m"] == pytest.approx(10.0, abs=0.5)
    assert report["synthetic"] is True
    assert report["fusion_mode"] == "cpf"
    # the single planted ellipse must survive stitching
    assert report["components_detected"] >= 1
    for det in report["detections"]:
        assert det["synthetic"] is True
        assert "p_value" in det and det["p_value"] <= 0.05
        assert det["cell_size_m"] == pytest.approx(10.0, abs=0.5)
    for artifact in report["artifacts"]:
        assert os.path.exists(os.path.join(out, artifact)), artifact
    ts = json.load(open(os.path.join(out, "timeseries.json")))
    assert len(ts["dates"]) == 9
    assert any(v is not None for v in ts["series"]["ndvi"])
    gj = json.load(open(os.path.join(out, "detections.geojson")))
    assert gj["properties"]["synthetic"] is True


def test_grid_selftest_reports_single_tile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = _params(grid=96, fusion_mode="legacy")
    out = str(tmp_path / "job")
    report = run_selftest(p, RING, None, out)
    assert report["tiles"] == 1
    assert report["native_resolution"] is False
    assert report["components_detected"] >= 1
    assert report["detections"][0]["synthetic"] is True


def test_legacy_fusion_mode_native(tmp_path, monkeypatch):
    """legacy scoring must also work through the tiled path."""
    monkeypatch.chdir(tmp_path)
    p = _params(resolution_m=10, tile_px=96, fusion_mode="legacy", score_threshold=55.0)
    out = str(tmp_path / "job")
    report = run_selftest(p, RING, None, out)
    assert report["fusion_mode"] == "legacy"
    assert report["components_detected"] >= 1
    assert "cpf" not in report
    assert report["detections"][0]["mean_score_0_100"] > 60
