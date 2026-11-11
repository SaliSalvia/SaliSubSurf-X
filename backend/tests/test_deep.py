"""Tests for the deep temporal-processing pipeline (offline, no network)."""

from __future__ import annotations

import os

import numpy as np
import pytest

from subsurface_api.deep import raster, temporal
from subsurface_api.deep.labels import _convex_hull, label_components
from subsurface_api.deep.outputs import safe_filename, write_geotiff
from subsurface_api.deep.pipeline import DeepParams, _synthetic_stack


# --------------------------------------------------------------------- raster

def _stack_from_reflectance(bands, scl=4, shape=(4, 4)):
    arrs = [np.full(shape, b, np.float32) if np.isscalar(b) else np.asarray(b, np.float32) for b in bands]
    dn = [np.clip(a, 0, 1.4) * 10000.0 + 1000.0 for a in arrs]
    h, w = arrs[0].shape
    return np.stack(dn + [np.full((h, w), scl, np.uint16), np.ones((h, w), np.uint16)], -1).astype(np.uint16)


def test_reflectance_offset_applied():
    stack = _stack_from_reflectance([0.10, 0.10, 0.10, 0.10, 0.10, 0.10])
    refl = raster.to_reflectance(stack)
    assert abs(float(refl[..., 0].mean()) - 0.10) < 1e-3


def test_indices_known_values():
    # uniform scene: NDVI = (0.4-0.1)/(0.4+0.1) = 0.6
    stack = _stack_from_reflectance(
        [0.05, 0.08, 0.10, 0.40, 0.20, 0.13]
    )
    refl = raster.to_reflectance(stack)
    valid = raster.valid_mask(stack)
    idx = raster.compute_indices(refl, valid)
    assert abs(float(idx["ndvi"][0, 0]) - 0.6) < 1e-3
    assert abs(float(idx["ndmi"][0, 0]) - (0.40 - 0.20) / 0.60) < 1e-3
    assert float(np.nanmax(idx["bsi"])) >= -1.0


def test_cloud_pixels_become_nan():
    stack = _stack_from_reflectance([0.10] * 6, scl=8)  # 8 = cloud
    refl = raster.to_reflectance(stack)
    valid = raster.valid_mask(stack)
    idx = raster.compute_indices(refl, valid)
    assert not valid.any()
    assert np.isnan(idx["ndvi"]).all()
    assert raster.scene_valid_fraction(stack) == 0.0


# ------------------------------------------------------------------- temporal

def _scene_stack(values_per_scene, shape=(4, 4)):
    return np.stack(
        [np.full(shape, v, np.float32) for v in values_per_scene], axis=0
    )


def test_robust_z_detects_drop():
    baseline = _scene_stack([0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
    recent = _scene_stack([0.2, 0.2, 0.2, 0.2])
    z, med = temporal.robust_z(baseline, recent)
    # sigma ~ 0 → eps floor; z strongly negative
    assert float(z.mean()) < -50
    assert abs(float(med.mean()) - 0.5) < 1e-6


def test_persistence_counts_consecutive_hits():
    baseline = _scene_stack([0.5] * 6)
    recent = _scene_stack([-1.0, -1.0, -1.0, 0.5])
    z_recent = temporal.per_scene_z(baseline, recent)
    pers = temporal.persistence(z_recent, "ndmi", 1.5)
    assert abs(float(pers.mean()) - 0.75) < 1e-6


def test_theil_sen_positive_trend():
    vals = [0.0, 0.1, 0.2, 0.3]
    stack = _scene_stack(vals)
    slope = temporal.theil_sen_slope(stack, [10, 11, 12, 13])
    assert abs(float(slope.mean()) - 0.1) < 1e-5


# --------------------------------------------------------------------- labels

def test_label_components_two_blobs():
    mask = np.zeros((10, 10), bool)
    mask[1:3, 1:3] = True
    mask[7:9, 7:9] = True
    labels, count = label_components(mask)
    assert count == 2
    assert set(np.unique(labels)) == {0, 1, 2}


def test_convex_hull_contains_points():
    pts = [(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5)]
    hull = _convex_hull(pts)
    assert len(hull) == 4  # centre point is not a hull vertex


# -------------------------------------------------------------------- outputs

def test_geotiff_roundtrip(tmp_path):
    data = np.arange(64, dtype=np.float32).reshape(8, 8)
    path = str(tmp_path / "t.tif")
    write_geotiff(path, data, [50.0, 29.0, 50.1, 29.1])
    import tifffile

    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        tags = {t.code: t.value for t in page.tags.values()}
        assert page.shape == (8, 8)
        assert tags[33550][0] == pytest.approx(0.1 / 8)  # ModelPixelScaleTag
        geokeys = np.asarray(tags[34735], dtype=float)   # GeoKeyDirectoryTag
        assert geokeys.size == 16
        assert 4326 in geokeys


def test_safe_filename_blocks_traversal():
    assert safe_filename("score_map.png") == "score_map.png"
    assert safe_filename("../evil.png") is None
    assert safe_filename("a/b.png") is None
    assert safe_filename(".hidden") is None


# ------------------------------------------------- synthetic pipeline (offline)

def test_synthetic_stack_runs_through_downstream(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = DeepParams(
        polygon=[[50.0, 29.0], [50.1, 29.0], [50.1, 29.08], [50.0, 29.08]],
        date_from="2026-10-01",
        date_to="2026-11-01",
        grid=128,
    ).sanitized()
    dates = [f"2026-10-{d:02d}" for d in range(1, 10)]
    stacks = _synthetic_stack(p, dates)

    from subsurface_api.deep.pipeline import _finalize
    from subsurface_api.deep import raster as r

    scenes = []
    for t, date_iso in enumerate(dates):
        refl = r.to_reflectance(stacks[t])
        valid = r.valid_mask(stacks[t])
        from subsurface_api.deep.pipeline import SceneInfo

        info = SceneInfo(date=date_iso, valid_fraction=r.scene_valid_fraction(stacks[t]))
        info.indices = r.compute_indices(refl, valid)
        info.composite = r.composite_rgb(refl)
        scenes.append(info)

    out_dir = tmp_path / "job"
    out_dir.mkdir()
    report = _finalize(p, "synthetic-selftest", [tuple(q) for q in p.polygon], scenes, None, str(out_dir))
    assert report["mode"] == "synthetic-selftest"
    assert report["scenes_accepted"] == 9
    # the injected ellipse must be found with elevated confidence
    assert report["components_detected"] >= 1
    assert report["components_high_or_medium"] >= 1
    best = report["detections"][0]
    assert best["mean_score_0_100"] > 60
    for artifact in report["artifacts"]:
        assert (out_dir / artifact).exists(), artifact
    assert (out_dir / "score.tif").stat().st_size > 1000
    assert os.path.getsize(out_dir / "report.json") > 500


# ------------------------------------------------------------------ API layer

def test_api_capabilities_and_selftest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient

    from subsurface_api.main import app

    client = TestClient(app)
    r = client.get("/api/v1/deep/capabilities")
    assert r.status_code == 200
    caps = r.json()
    assert caps["selftest_mode_available"] is True
    assert set(caps["models"]) == {"pca", "autoencoder"}
    assert set(caps["fusion_modes"]) == {"cpf", "legacy"}
    assert caps["native_resolution"]["available"] is True

    r2 = client.post("/api/v1/deep/selftest?grid=96&n_surrogates=39&alpha=0.05")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["ok"] is True
    assert body["synthetic"] is True
    assert body["summary"]["mode"] == "synthetic-selftest"
    assert body["summary"]["synthetic"] is True
    assert body["summary"]["components"] >= 1
    assert body["report"]["synthetic"] is True
    assert body["report"]["detections"][0]["synthetic"] is True


def test_analyze_requires_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for var in ("COPERNICUS_USERNAME", "COPERNICUS_PASSWORD",
                "COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    from fastapi.testclient import TestClient

    from subsurface_api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/v1/deep/analyze",
        json={
            "polygon": [[50.0, 29.0], [50.1, 29.0], [50.1, 29.08], [50.0, 29.08]],
            "date_from": "2026-09-01",
            "date_to": "2026-11-01",
            "mode": "live",
        },
    )
    assert r.status_code == 503

    r2 = client.post(
        "/api/v1/deep/analyze",
        json={
            "polygon": [[50.0, 29.0], [50.1, 29.0], [50.1, 29.08], [50.0, 29.08]],
            "date_from": "2026-09-01",
            "date_to": "2026-11-01",
            "mode": "selftest",
            "grid": 64,
            "n_surrogates": 39,
            "alpha": 0.05,
        },
    )
    assert r2.status_code == 200
    job_id = r2.json()["job_id"]
    # poll briefly (synchronous executor worker)
    import time

    for _ in range(120):
        st = client.get(f"/api/v1/deep/jobs/{job_id}").json()
        if st["status"] in ("done", "error"):
            break
        time.sleep(0.5)
    assert st["status"] == "done", st
    res = client.get(f"/api/v1/deep/jobs/{job_id}/result").json()
    assert res["report"]["mode"] == "synthetic-selftest"
    assert res["report"]["synthetic"] is True
    assert res["report"]["detections"][0]["p_value"] <= 0.05
    png = client.get(f"/api/v1/deep/jobs/{job_id}/files/score_map.png")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    bad = client.get(f"/api/v1/deep/jobs/{job_id}/files/..%2Fsecret")
    assert bad.status_code in (404, 400)
