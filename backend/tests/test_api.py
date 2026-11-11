"""API endpoint tests — external providers are mocked; no network access."""

from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from subsurface_api.main import app

client = TestClient(app)

SQUARE = [(51.0, 35.0), (51.01, 35.0), (51.01, 35.01), (51.0, 35.01)]
BOWTIE = [(0.0, 0.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0)]

FAKE_PRODUCT = {
    "id": "abc",
    "name": "S2A_MSIL2A_20250101T082231_N0510_R021_T40SDB_20250101T112358.SAFE",
    "processing_level": "S2MSI2A",
    "datetime": "2025-01-01T08:22:31Z",
    "cloud_cover_percent": 5.0,
    "size_mb": 100.0,
    "footprint": None,
}


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_validate_ok():
    r = client.post("/api/v1/regions/validate", json={"polygon": SQUARE})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["vertex_count"] == 4
    assert body["area_hectares"] > 50
    assert len(body["bbox"]) == 4


def test_validate_rejects_bowtie_with_200_and_issues():
    r = client.post("/api/v1/regions/validate", json={"polygon": BOWTIE})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["issues"]


def test_validate_rejects_degenerate_payload():
    r = client.post("/api/v1/regions/validate", json={"polygon": [[0, 0], [1, 1]]})
    assert r.status_code == 422


def test_catalog_search_ok():
    today = date.today()
    payload = {
        "polygon": SQUARE,
        "date_from": str(today - timedelta(days=30)),
        "date_to": str(today),
        "max_cloud_percent": 30.0,
        "max_results": 5,
    }
    with patch("subsurface_api.providers.cdse.search_products") as fake:
        fake.return_value = {
            "products": [FAKE_PRODUCT],
            "total_matched": 1,
            "provenance": [{"provider": "Copernicus Data Space Ecosystem"}],
            "warnings": [],
        }
        r = client.post("/api/v1/regions/catalog-search", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["region"]["valid"] is True
    assert body["products"][0]["name"].startswith("S2A_MSIL2A")
    assert body["provenance"]


def test_catalog_search_rejects_invalid_region():
    today = date.today()
    payload = {
        "polygon": BOWTIE,
        "date_from": str(today - timedelta(days=30)),
        "date_to": str(today),
    }
    r = client.post("/api/v1/regions/catalog-search", json=payload)
    assert r.status_code == 400


def test_catalog_search_rejects_bad_dates():
    r = client.post(
        "/api/v1/regions/catalog-search",
        json={"polygon": SQUARE, "date_from": "2025-13-40", "date_to": "2025-12-01"},
    )
    assert r.status_code == 422


def test_catalog_search_rejects_future_range():
    today = date.today()
    r = client.post(
        "/api/v1/regions/catalog-search",
        json={
            "polygon": SQUARE,
            "date_from": str(today - timedelta(days=10)),
            "date_to": str(today + timedelta(days=400)),
        },
    )
    assert r.status_code == 422


FAKE_TERRAIN = {
    "zoom": 13,
    "resolution_m_per_px": 9.5,
    "nodata_fraction": 0.0,
    "tiles_fetched": 4,
    "elevation": {"min_m": 100.0, "max_m": 400.0, "mean_m": 250.0, "std_m": 60.0},
    "slope": {"mean_deg": 8.0, "max_deg": 32.0, "std_deg": 5.0, "percent_over_15": 12.0},
    "roughness_tri_mean": 9.0,
    "dominant_gradient_azimuth_deg": 123.4,
    "gradient_consistency": 0.42,
    "provenance": [{"provider": "AWS Open Data — Terrain Tiles (Tilezen)"}],
    "caveats": ["Terrain indicators describe surface shape only."],
}


def test_terrain_indicators_ok_with_score():
    with patch("subsurface_api.providers.terrain.analyze_region") as fake:
        fake.return_value = dict(FAKE_TERRAIN)
        r = client.post("/api/v1/regions/terrain-indicators", json={"polygon": SQUARE})
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["surface_anomaly_score"] <= 1.0
    assert set(body["score_components"]) == {
        "slope_variability",
        "roughness",
        "gradient_consistency",
        "relief",
    }
    assert body["caveats"]


def test_terrain_indicators_propagates_tile_budget_error():
    with patch("subsurface_api.providers.terrain.analyze_region") as fake:
        fake.side_effect = ValueError("Region bbox is too large for DEM analysis")
        r = client.post("/api/v1/regions/terrain-indicators", json={"polygon": SQUARE})
    assert r.status_code == 400
