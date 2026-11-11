"""Deep-processing API routes (``/api/v1/deep/...``) + optional API-key gate."""

from __future__ import annotations

import hmac
import logging
import os
import re
import shutil
import threading
from datetime import date as _date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from ..geo import normalize_ring
from ..validation import validate_region
from . import cdse_process
from .jobs import QueueFull, manager
from .outputs import safe_filename
from .pipeline import ARTIFACTS, DeepParams, run_selftest

log = logging.getLogger("subsurface_api.deep.router")

router = APIRouter(prefix="/api/v1/deep", tags=["deep"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ------------------------------------------------------------- auth (optional)

async def require_api_key(request: Request) -> None:
    """If ``DEEP_API_KEY`` is set, the header ``X-API-Key`` must match it.

    Comparison is constant-time (:func:`hmac.compare_digest`) so attackers
    cannot recover the key byte-by-byte from response timing.
    """
    expected = os.environ.get("DEEP_API_KEY")
    if not expected:
        return
    got = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(got.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")


# -------------------------------------------------------------------- schemas

class DeepAnalyzeRequest(BaseModel):
    polygon: List[List[float]]
    date_from: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    grid: int = Field(512, ge=64, le=512)
    max_cloud_percent: float = Field(20.0, ge=0.0, le=100.0)
    max_dates: int = Field(14, ge=4, le=24)
    min_valid_fraction: float = Field(0.55, ge=0.30, le=0.95)
    recent_k: int = Field(4, ge=2, le=12)
    z_threshold: float = Field(1.5, ge=0.5, le=4.0)
    score_threshold: float = Field(55.0, ge=25.0, le=90.0)
    min_pixels: int = Field(9, ge=1, le=4096)
    model: str = Field("pca", pattern=r"^(pca|autoencoder)$")
    mode: str = Field("live", pattern=r"^(live|selftest)$")
    autoencoder_epochs: int = Field(300, ge=50, le=1200)
    # --- v1.3.0: statistical calibration + native resolution ---------------
    fusion_mode: str = Field("cpf", pattern=r"^(cpf|legacy)$")
    n_surrogates: int = Field(199, ge=0, le=999)
    alpha: float = Field(0.01, ge=0.001, le=0.1)
    resolution_m: Optional[float] = Field(None, ge=10.0, le=100.0)

    @field_validator("polygon")
    @classmethod
    def _check_pairs(cls, v: List[List[float]]) -> List[List[float]]:
        if len(v) < 3:
            raise ValueError("polygon needs at least 3 vertices")
        for p in v:
            if len(p) != 2:
                raise ValueError("each vertex must be a [lon, lat] pair")
        return v


def _validate_window(date_from: str, date_to: str) -> None:
    if not (_DATE_RE.match(date_from) and _DATE_RE.match(date_to)):
        raise HTTPException(status_code=422, detail=["Dates must be YYYY-MM-DD."])
    d0, d1 = _date.fromisoformat(date_from), _date.fromisoformat(date_to)
    today = datetime.now(timezone.utc).date()
    if d0 > d1:
        raise HTTPException(status_code=422, detail=["date_from must be ≤ date_to."])
    if (d1 - d0).days > 366:
        raise HTTPException(status_code=422, detail=["Date range is limited to 366 days."])
    if d1 > today + timedelta(days=1):
        raise HTTPException(status_code=422, detail=["date_to is in the future."])


# ------------------------------------------------------------------ endpoints

@router.get("/capabilities")
def capabilities() -> dict:
    """What this deployment can do right now (credentials present or not)."""
    return {
        "live_mode_available": cdse_process.credentials_present(),
        "selftest_mode_available": True,
        "models": ["pca", "autoencoder"],
        "fusion_modes": ["cpf", "legacy"],
        "grid_limits_px": [64, 512],
        "max_dates": [4, 24],
        "native_resolution": {
            "available": True,
            "resolution_m_limits": [10, 100],
            "max_total_pixels": 4_200_000,
            "tiling": "space tiles of ≤512 px (24 px overlap) stitched globally",
        },
        "artifacts": ARTIFACTS,
        "requires_credentials_for_live": {
            "personal_account": ["COPERNICUS_USERNAME", "COPERNICUS_PASSWORD"],
            "oauth_client": ["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"],
        },
        "optional_api_key_env": "DEEP_API_KEY",
    }


@router.post("/analyze", dependencies=[Depends(require_api_key)])
def analyze(req: DeepAnalyzeRequest) -> dict:
    _validate_window(req.date_from, req.date_to)
    # Same strict geometry gate as the catalog/terrain endpoints: a
    # self-intersecting, out-of-range or oversized polygon must never reach the
    # Process API. Normalising also drops a duplicated closing vertex, which
    # would otherwise be sent as an invalid ring.
    check = validate_region(req.polygon)
    if not check.valid:
        raise HTTPException(status_code=400, detail=check.issues)
    ring = [[float(lon), float(lat)] for lon, lat in normalize_ring(req.polygon)]
    if req.mode == "live" and not cdse_process.credentials_present():
        raise HTTPException(
            status_code=503,
            detail=(
                "Live deep analysis needs Copernicus credentials. Configure "
                "COPERNICUS_USERNAME/COPERNICUS_PASSWORD (or OAuth client id/secret) "
                "in the service environment, or run mode='selftest'."
            ),
        )
    params = DeepParams(
        polygon=ring,
        date_from=req.date_from,
        date_to=req.date_to,
        grid=req.grid,
        max_cloud_percent=req.max_cloud_percent,
        max_dates=req.max_dates,
        min_valid_fraction=req.min_valid_fraction,
        recent_k=req.recent_k,
        z_threshold=req.z_threshold,
        score_threshold=req.score_threshold,
        min_pixels=req.min_pixels,
        model=req.model,
        autoencoder_epochs=req.autoencoder_epochs,
        fusion_mode=req.fusion_mode,
        n_surrogates=req.n_surrogates,
        alpha=req.alpha,
        resolution_m=req.resolution_m,
    )
    try:
        job_id = manager.submit(params.sanitized(), req.mode)
    except QueueFull as exc:
        raise HTTPException(
            status_code=429, detail=str(exc), headers={"Retry-After": "30"}
        ) from exc
    job = manager.get(job_id)
    return {"accepted": True, **(job.public() if job else {"job_id": job_id})}


@router.get("/jobs", dependencies=[Depends(require_api_key)])
def jobs() -> dict:
    return {"jobs": manager.list()}


@router.get("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def job_status(job_id: str) -> dict:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    return job.public()


@router.get("/jobs/{job_id}/result", dependencies=[Depends(require_api_key)])
def job_result(job_id: str) -> dict:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    if job.status == "error":
        return JSONResponse(status_code=502, content={**job.public(), "report": None})
    if job.status != "done" or job.report is None:
        return JSONResponse(status_code=202, content=job.public())
    return {"job_id": job.job_id, "status": job.status, "report": job.report}


@router.get("/jobs/{job_id}/files/{filename}", dependencies=[Depends(require_api_key)])
def job_file(job_id: str, filename: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    safe = safe_filename(filename)
    if not safe or safe not in ARTIFACTS:
        raise HTTPException(status_code=404, detail="Unknown artifact name.")
    path = os.path.join(job._dir, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Artifact not produced by this job.")
    media = "image/png" if safe.endswith(".png") else "application/json"
    if safe.endswith(".tif"):
        media = "image/tiff"
    if safe.endswith(".geojson"):
        media = "application/geo+json"
    return FileResponse(path, media_type=media, filename=safe)


SELFTEST_KEEP = 10
# Selftest is a synchronous, RAM-heavy diagnostic. Two concurrent runs are
# plenty for humans; a third caller gets a retryable 429 instead of pushing the
# host into swap. (Deep /analyze has its own bounded job queue.)
_SELFTEST_SLOTS = threading.BoundedSemaphore(2)


def _prune_selftest_dirs(base: str, keep: int = SELFTEST_KEEP) -> None:
    """Delete old ``selftest-*`` artifact directories, keeping the newest ``keep``.

    These runs are not registered with the job manager, so without this they
    would accumulate until the artifact volume fills up.
    """
    try:
        names = sorted(n for n in os.listdir(base) if n.startswith("selftest-"))
    except OSError:
        return
    for name in names[: max(0, len(names) - keep)]:
        shutil.rmtree(os.path.join(base, name), ignore_errors=True)


@router.post("/selftest", dependencies=[Depends(require_api_key)])
def selftest(grid: int = 192, resolution_m: Optional[float] = None,
              fusion_mode: str = "cpf", n_surrogates: int = 199) -> dict:
    """Synchronous offline end-to-end run on synthetic data (no credentials).

    Returns are flagged ``synthetic: true`` everywhere — detections found here
    live on a deterministic planted anomaly, not on real terrain.
    """
    if not _SELFTEST_SLOTS.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="Two selftest runs are already in flight; retry in a few seconds.",
            headers={"Retry-After": "15"},
        )
    try:
        grid_c = int(min(256, max(64, grid)))
        fusion_mode = "legacy" if fusion_mode == "legacy" else "cpf"
        res_m = None if resolution_m is None else float(min(100.0, max(10.0, resolution_m)))
        n_surr = int(min(999, max(0, n_surrogates)))
        polygon = [[50.0, 29.0], [50.12, 29.0], [50.12, 29.09], [50.0, 29.09]]
        today = datetime.now(timezone.utc).date()
        params = DeepParams(
            polygon=polygon,
            date_from=(today - timedelta(days=30)).isoformat(),
            date_to=today.isoformat(),
            grid=grid_c,
            fusion_mode=fusion_mode,
            n_surrogates=n_surr,
            resolution_m=res_m,
        )
        from .outputs import job_dir
        from .pipeline import data_dir

        base = data_dir()
        _prune_selftest_dirs(base)
        out = job_dir(base, f"selftest-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
        report = run_selftest(params.sanitized(), [(p[0], p[1]) for p in polygon], None, out)
        return {
            "ok": report.get("components_detected", 0) >= 0,
            "synthetic": True,
            "output_dir": os.path.basename(out),
            "summary": {
                "mode": report["mode"],
                "synthetic": True,
                "scenes": report["scenes_accepted"],
                "components": report["components_detected"],
                "high_or_medium": report["components_high_or_medium"],
                "model": report["model_used"],
                "fusion_mode": report.get("fusion_mode"),
            },
            "report": report,
        }
    finally:
        _SELFTEST_SLOTS.release()
