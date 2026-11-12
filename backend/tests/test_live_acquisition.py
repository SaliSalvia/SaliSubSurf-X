"""Regression tests for the v1.3.1 live-acquisition fixes.

Background: CDSE rejected the two-entry evalscript input form on EVERY
Process API request ("Script failed to return"), which surfaced as the
misleading "No tile had ≥4 usable scenes" data error. These tests lock in
the corrected evalscript shape and the catalog-guided date selection.
"""

from __future__ import annotations

import json as _json
from typing import Any, Dict, List

import pytest

from subsurface_api.deep import cdse_process
from subsurface_api.deep.pipeline import _evenly_spaced_dates


# ------------------------------------------------------------------ evalscript

def test_evalscript_single_input_object():
    """The whole band list must live in ONE input object — the two-entry
    form ({bands, units}, ["SCL", "dataMask"]) is rejected by CDSE."""
    assert '["SCL", "dataMask"]' not in cdse_process.EVALSCRIPT
    # exactly one input entry inside the input block (output also has "bands")
    input_block = cdse_process.EVALSCRIPT.split("input:", 1)[1].split("output:", 1)[0]
    assert input_block.count("{ bands:") == 1
    for band in ("B02", "B03", "B04", "B08", "B11", "B12", "SCL", "dataMask"):
        assert f'"{band}"' in cdse_process.EVALSCRIPT
    assert 'units: "DN"' in cdse_process.EVALSCRIPT
    assert 'sampleType: "UINT16"' in cdse_process.EVALSCRIPT


def test_band_order_matches_evalscript_layout():
    bands = [b for b in cdse_process.BAND_ORDER]
    assert bands[:6] == ["B02", "B03", "B04", "B08", "B11", "B12"]
    assert bands[6:] == ["SCL", "dataMask"]


# ------------------------------------------------------------------ date spacing

def test_evenly_spaced_dates_passthrough():
    dates = ["2026-06-01", "2026-06-05", "2026-06-10"]
    assert _evenly_spaced_dates(dates, 14) == dates
    assert _evenly_spaced_dates(dates, 3) == dates


def test_evenly_spaced_dates_keeps_both_ends():
    dates = [f"2026-06-{d:02d}" for d in range(1, 29)]
    picked = _evenly_spaced_dates(dates, 4)
    assert len(picked) == 4
    assert picked[0] == dates[0]
    assert picked[-1] == dates[-1]
    # strictly increasing
    assert picked == sorted(picked)
    assert len(set(picked)) == len(picked)


def test_evenly_spaced_dates_single():
    dates = ["2026-06-01", "2026-06-02"]
    assert _evenly_spaced_dates(dates, 1) == ["2026-06-02"]
    assert _evenly_spaced_dates([], 5) == []
    assert _evenly_spaced_dates(dates, 0) == []


# ------------------------------------------------------------------ catalog

class _Resp:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


def _product(name: str, start: str, cloud: float) -> Dict[str, Any]:
    return {
        "Name": name,
        "ContentDate": {"Start": start},
        "Attributes": [{"Name": "cloudCover", "Value": cloud}],
    }


def test_catalog_scenes_filters_and_sorts(monkeypatch):
    ring = [(51.20, 35.60), (51.25, 35.60), (51.25, 35.65), (51.20, 35.65)]
    payload = {
        "value": [
            _product("S2B_MSIL2A_20260908...T39SWV", "2026-09-08T07:16:19Z", 46.56),
            _product("S2B_MSIL1C_20260907...T39SWV", "2026-09-07T07:16:19Z", 1.0),
            _product("S2B_MSIL2A_20260915...T39SWV", "2026-09-15T07:16:19Z", 0.00009),
            _product("S2C_MSIL2A_20260915...T39SWV", "2026-09-15T07:17:00Z", 0.5),
            _product("S2B_MSIL2A_20260615...T39SWV", "2026-06-15T07:16:19Z", 0.033),
        ]
    }
    captured: List[Dict[str, Any]] = []

    def fake_get(url, params=None, timeout=None):
        captured.append({"url": url, "params": params})
        return _Resp(payload)

    monkeypatch.setattr(cdse_process.requests, "get", fake_get)
    scenes = cdse_process.catalog_scenes(ring, "2026-06-01", "2026-09-30",
                                         max_cloud_percent=30.0)
    # L1C dropped, cloudy dropped, per-date minimum cloud kept, sorted ascending
    assert scenes == [
        {"date": "2026-06-15", "cloud": 0.033},
        {"date": "2026-09-15", "cloud": 0.00009},
    ]
    # query shape: hand-built URL with %20 (params= would emit '+' and the
    # OData endpoint would reject it), attributes expanded, ring closed and
    # vertices comma-separated
    got = captured[0]["url"]
    assert captured[0]["params"] is None
    assert got.startswith(cdse_process.CATALOG_URL)
    assert "$expand=Attributes" in got
    assert "+" not in got.split("?", 1)[1]      # never '+' for spaces
    assert "OData.CSC.Intersects" in got
    poly = got.split("POLYGON((", 1)[1].split("))", 1)[0]
    assert poly.count(",") == 4            # 4 vertices + closing vertex
    assert poly.count("%20") == 5          # 5 vertices × one lon<space>lat
    assert poly.startswith("51.200000%2035.600000")  # first vertex …
    assert poly.endswith("51.200000%2035.600000")    # … repeated to close ring


def test_catalog_scenes_network_failure_raises_fetch_error(monkeypatch):
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    def boom(*a, **kw):
        raise cdse_process.requests.RequestException("dns gone")

    monkeypatch.setattr(cdse_process.requests, "get", boom)
    with pytest.raises(cdse_process.DeepFetchError):
        cdse_process.catalog_scenes(ring, "2026-06-01", "2026-06-30")


def test_catalog_scenes_malformed_json_raises_fetch_error(monkeypatch):
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    class _Bad:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(cdse_process.requests, "get", lambda *a, **kw: _Bad())
    with pytest.raises(cdse_process.DeepFetchError):
        cdse_process.catalog_scenes(ring, "2026-06-01", "2026-06-30")


# ------------------------------------------------------------ payload geometry

def test_process_payload_single_day_window_and_cloud():
    ring = [(51.20, 35.60), (51.25, 35.60), (51.25, 35.65), (51.20, 35.65)]
    payload = cdse_process._process_payload(ring, "2026-09-15", 256, 256, 30.0)
    data = payload["input"]["data"][0]
    assert data["type"] == "sentinel-2-l2a"
    assert data["dataFilter"]["timeRange"] == {
        "from": "2026-09-15T00:00:00Z", "to": "2026-09-15T23:59:59Z"}
    assert data["dataFilter"]["maxCloudCoverage"] == 30.0
    coords = payload["input"]["bounds"]["geometry"]["coordinates"][0]
    assert len(coords) == 5  # closed ring
    assert coords[0] == coords[-1]
    assert payload["evalscript"] == cdse_process.EVALSCRIPT
