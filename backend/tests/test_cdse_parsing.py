from unittest.mock import MagicMock, patch

from subsurface_api.providers import cdse

RING = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

RAW_PRODUCT = {
    "Id": "abc-123",
    "Name": "S2A_MSIL2A_20250101T082231_N0510_R021_T40SDB_20250101T112358.SAFE",
    "ContentDate": {"Start": "2025-01-01T08:22:31Z", "End": "2025-01-01T08:22:31Z"},
    "ContentLength": 104857600,
    "Attributes": [{"Name": "CloudCoverage", "Value": 12.5}],
    "GeoFootprint": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
}


def test_parse_product_extracts_metadata():
    p = cdse.parse_product(RAW_PRODUCT)
    assert p["id"] == "abc-123"
    assert p["processing_level"] == "S2MSI2A"
    assert p["datetime"] == "2025-01-01T08:22:31Z"
    assert p["cloud_cover_percent"] == 12.5
    assert p["size_mb"] == 100.0
    assert p["footprint"]["type"] == "Polygon"


def test_parse_product_accepts_live_api_attribute_name():
    p = cdse.parse_product({**RAW_PRODUCT, "Attributes": [{"Name": "cloudCover", "Value": 7.25}]})
    assert p["cloud_cover_percent"] == 7.25


def test_parse_product_tolerates_missing_fields():
    p = cdse.parse_product({"Id": "x", "Name": "S2_UNKNOWN"})
    assert p["cloud_cover_percent"] is None
    assert p["size_mb"] is None
    assert p["processing_level"] == "S2"


def test_build_filter_contains_geometry_and_level():
    f = cdse.build_filter(RING, "2025-01-01", "2025-02-01")
    assert "Collection/Name eq 'SENTINEL-2'" in f
    assert "SRID=4326;POLYGON((0.0000000 0.0000000" in f
    assert "ContentDate/Start gt 2025-01-01T00:00:00.000Z" in f
    assert "ContentDate/Start lt 2025-02-01T23:59:59.999Z" in f
    assert "contains(Name,'MSIL2A')" in f


def test_search_products_filters_by_cloud_and_returns_provenance():
    cloudy = dict(RAW_PRODUCT)
    cloudy["Id"] = "cloudy-1"
    cloudy["Attributes"] = [{"Name": "CloudCoverage", "Value": 80.0}]
    response = {"value": [RAW_PRODUCT, cloudy]}
    with patch("subsurface_api.providers.cdse.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = response
        out = cdse.search_products(RING, "2025-01-01", "2025-02-01", 30.0, 10)
    assert [p["id"] for p in out["products"]] == ["abc-123"]
    assert out["total_matched"] == 2
    assert out["provenance"][0]["provider"] == cdse.PROVIDER
    assert out["warnings"] == []
    # $filter/$top/$orderby must be present in the query
    params = mock_get.call_args.kwargs["params"]
    assert params["$top"] == 10
    assert "$orderby" in params and "$filter" in params


def test_search_products_warns_when_all_cloudy():
    cloudy = dict(RAW_PRODUCT)
    cloudy["Attributes"] = [{"Name": "CloudCoverage", "Value": 95.0}]
    with patch("subsurface_api.providers.cdse.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"value": [cloudy]}
        out = cdse.search_products(RING, "2025-01-01", "2025-02-01", 30.0, 10)
    assert out["products"] == []
    assert out["warnings"]


def test_search_products_retries_transient_error_then_raises():
    busy = MagicMock(status_code=429, headers={})
    with patch("subsurface_api.providers.cdse.requests.get", return_value=busy) as mock_get, \
         patch("subsurface_api.providers.cdse._sleep") as sleep:
        try:
            cdse.search_products(RING, "2025-01-01", "2025-02-01", 30.0, 10)
            raised = False
        except RuntimeError as exc:
            raised = True
            assert "429" in str(exc)
        assert raised
    assert mock_get.call_count == 3
    assert sleep.call_count == 2


# ------------------------------------------------- deep Process API evalscript

def test_deep_evalscript_requests_dn_units():
    """CRITICAL regression guard: without units:"DN" the Process API serves
    REFLECTANCE floats (0..1) which truncate to 0/1 under sampleType UINT16 —
    every pixel then fails the (DN-1000)/10000 harmonisation (v1.2.x live-mode bug)."""
    from subsurface_api.deep import cdse_process

    assert 'units: "DN"' in cdse_process.EVALSCRIPT
    assert 'sampleType: "UINT16"' in cdse_process.EVALSCRIPT
    # SCL/dataMask are classification bands and must NOT be in the DN group
    dn_line = [l for l in cdse_process.EVALSCRIPT.splitlines() if 'units: "DN"' in l][0]
    assert "SCL" not in dn_line and "dataMask" not in dn_line


def test_deep_process_payload_shape():
    from subsurface_api.deep import cdse_process

    payload = cdse_process._process_payload(RING, "2026-10-01", 64, 64, 20.0, "bilinear")
    data = payload["input"]["data"][0]
    assert data["type"] == "sentinel-2-l2a"
    assert data["dataFilter"]["maxCloudCoverage"] == 20.0
    assert data["processing"]["resampling"] == "bilinear"
    assert payload["output"]["width"] == 64 and payload["output"]["height"] == 64
    assert payload["evalscript"] == cdse_process.EVALSCRIPT
    # invalid resampling falls back to nearest
    p2 = cdse_process._process_payload(RING, "2026-10-01", 64, 64, 20.0, "cubic!!")
    assert p2["input"]["data"][0]["processing"]["resampling"] == "nearest"
