"""Operational behaviour: retries, request ids, readiness and the deep-job queue cap."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from subsurface_api.main import app
from subsurface_api.providers import cdse

client = TestClient(app)
RING = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
SQUARE = [(51.0, 35.0), (51.01, 35.0), (51.01, 35.01), (51.0, 35.01)]


def _product(pid: str = "p1", cloud: float = 5.0) -> dict:
    return {
        "Id": pid,
        "Name": "S2A_MSIL2A_20250101T082231_N0510_R021_T40SDB_20250101T112358.SAFE",
        "Attributes": [{"Name": "cloudCover", "Value": cloud}],
    }


def test_request_id_is_generated_and_echoed():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")

    r2 = client.get("/api/v1/health", headers={"X-Request-ID": "suite-123.abc"})
    assert r2.headers["x-request-id"] == "suite-123.abc"


def test_invalid_request_id_header_is_replaced():
    r = client.get("/api/v1/health", headers={"X-Request-ID": "bad id with spaces"})
    assert r.headers["x-request-id"] != "bad id with spaces"
    assert len(r.headers["x-request-id"]) == 32


def test_ready_reports_writable_artifacts_dir():
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["artifacts_dir"] is True


def test_catalog_retries_transient_failure_then_succeeds():
    ok = MagicMock(status_code=200, headers={})
    ok.json.return_value = {"value": [_product()], "@odata.count": 42}
    busy = MagicMock(status_code=503, headers={"Retry-After": "0"})
    with patch("subsurface_api.providers.cdse.requests.get", side_effect=[busy, ok]) as get, \
         patch("subsurface_api.providers.cdse._sleep") as sleep:
        out = cdse.search_products(RING, "2025-01-01", "2025-02-01", 30.0, 10)
    assert get.call_count == 2
    assert sleep.call_count == 1
    assert out["total_matched"] == 42
    assert get.call_args.kwargs["params"]["$count"] == "true"


def test_catalog_reports_malformed_json():
    bad = MagicMock(status_code=200, headers={})
    bad.json.side_effect = ValueError("not json")
    with patch("subsurface_api.providers.cdse.requests.get", return_value=bad):
        with pytest.raises(RuntimeError, match="malformed JSON"):
            cdse.search_products(RING, "2025-01-01", "2025-02-01", 30.0, 10)


def test_deep_analyze_returns_429_when_queue_full():
    from subsurface_api.deep.jobs import QueueFull

    payload = {
        "polygon": SQUARE,
        "date_from": str(date.today() - timedelta(days=10)),
        "date_to": str(date.today()),
        "mode": "selftest",
    }
    with patch("subsurface_api.deep.router.manager.submit", side_effect=QueueFull("full")):
        r = client.post("/api/v1/deep/analyze", json=payload)
    assert r.status_code == 429
    assert r.headers.get("retry-after") == "30"


def test_job_manager_enforces_active_cap(tmp_path, monkeypatch):
    from subsurface_api.deep.jobs import MAX_ACTIVE_JOBS, JobManager, QueueFull
    from subsurface_api.deep.pipeline import DeepParams

    monkeypatch.setenv("DEEP_DATA_DIR", str(tmp_path))
    manager = JobManager()
    manager._pool.submit = lambda *a, **k: None  # type: ignore[method-assign]
    params = DeepParams(
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        date_from="2026-01-01",
        date_to="2026-02-01",
    )
    for _ in range(MAX_ACTIVE_JOBS):
        manager.submit(params, "selftest")
    with pytest.raises(QueueFull):
        manager.submit(params, "selftest")
    manager._pool.shutdown(wait=False)


def test_deep_analyze_rejects_invalid_geometry():
    payload = {
        "polygon": [[0.0, 0.0], [1.0, 1.0], [1.0, 0.0], [0.0, 1.0]],  # bow-tie
        "date_from": str(date.today() - timedelta(days=10)),
        "date_to": str(date.today()),
        "mode": "selftest",
    }
    r = client.post("/api/v1/deep/analyze", json=payload)
    assert r.status_code == 400
    assert r.json()["detail"]


def test_deep_analyze_normalises_closed_ring(monkeypatch):
    from subsurface_api.deep import router as deep_router

    captured = {}

    def fake_submit(params, mode):
        captured["polygon"] = params.polygon
        return "job-test"

    monkeypatch.setattr(deep_router.manager, "submit", fake_submit)
    monkeypatch.setattr(deep_router.manager, "get", lambda job_id: None)
    payload = {
        "polygon": [list(p) for p in SQUARE] + [list(SQUARE[0])],  # closed ring
        "date_from": str(date.today() - timedelta(days=10)),
        "date_to": str(date.today()),
        "mode": "selftest",
    }
    r = client.post("/api/v1/deep/analyze", json=payload)
    assert r.status_code == 200
    assert r.json()["job_id"] == "job-test"
    assert captured["polygon"] == [list(p) for p in SQUARE]


def test_fetch_scene_stack_does_not_sleep_after_last_attempt():
    from subsurface_api.deep.cdse_process import DeepFetchError, fetch_scene_stack

    busy = MagicMock(status_code=503, headers={})
    with patch("subsurface_api.deep.cdse_process.requests.post", return_value=busy), \
         patch("subsurface_api.deep.cdse_process.time.sleep") as sleep:
        with pytest.raises(DeepFetchError):
            fetch_scene_stack("token", RING, "2025-01-01", 16, 16, retries=2)
    assert sleep.call_count == 1


def test_prune_selftest_dirs_keeps_newest(tmp_path):
    from subsurface_api.deep.router import _prune_selftest_dirs

    for i in range(6):
        (tmp_path / f"selftest-2026010{i}T000000Z").mkdir()
    (tmp_path / "20260101T000000Z-job").mkdir()  # not a selftest directory
    _prune_selftest_dirs(str(tmp_path), keep=2)
    names = sorted(p.name for p in tmp_path.iterdir())
    kept = [n for n in names if n.startswith("selftest-")]
    assert kept == ["selftest-20260104T000000Z", "selftest-20260105T000000Z"]
    assert "20260101T000000Z-job" in names


def test_selftest_rejects_when_slots_exhausted():
    from subsurface_api.deep import router as deep_router

    assert deep_router._SELFTEST_SLOTS.acquire(blocking=False)
    assert deep_router._SELFTEST_SLOTS.acquire(blocking=False)
    try:
        r = client.post("/api/v1/deep/selftest?grid=64")
        assert r.status_code == 429
        assert r.headers.get("retry-after") == "15"
    finally:
        deep_router._SELFTEST_SLOTS.release()
        deep_router._SELFTEST_SLOTS.release()
