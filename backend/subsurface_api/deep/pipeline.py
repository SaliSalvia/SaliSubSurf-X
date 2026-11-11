"""The deep-processing pipeline: acquisition → evidence → fusion → artifacts.

v1.3.0 introduces two structural upgrades over v1.2.x:

* **CPF-lite statistics** (default ``fusion_mode="cpf"``): the legacy
  hand-weighted z-score fusion is retained for comparability, but detections
  are now declared through a *calibrated* null — context detrending,
  covariance whitening, an empirical chi² null scale and phase-randomised
  surrogate cluster-mass p-values (see ``cpf.py``).  Under smooth seasonal
  drift this keeps false-positive area in the low single digits instead of
  flagging half of the region.
* **Native-resolution tiling**: with ``resolution_m`` set (e.g. 10 m) the AOI
  is analysed on its native Sentinel-2 grid instead of being resampled onto a
  512-pixel grid.  The area is split into space tiles of ≤512 px plus a 24 px
  overlap halo; each tile runs the full chain and the per-tile maps are
  stitched before global connected-component labeling.  Memory stays bounded
  no matter the AOI size (capped at ~4.2 M pixels ≈ 20×20 km at 10 m).

Selftest mode runs the *identical* downstream chain on a deterministic
synthetic stack — every output is flagged ``synthetic: true`` so a planted
ellipse can never be mistaken for a real-terrain detection.

Every artifact is written into ``DEEP_DATA_DIR/<job_id>/`` and summarised in
report.json.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import cdse_process, raster
from . import temporal as temporal_mod
from . import cpf as cpf_mod
from .fusion import WEIGHTS, fuse
from .labels import detections_to_geojson, label_components
from .model import deep_anomaly
from .outputs import (
    write_geotiff,
    write_json,
    write_layer_png,
    write_overlay_png,
    write_score_png,
)

log = logging.getLogger("subsurface_api.deep.pipeline")

ProgressCb = Optional[Callable[[int, str], None]]

ARTIFACTS = [
    "score_map.png",
    "overlay.png",
    "layer_moisture.png",
    "layer_vegetation.png",
    "layer_soil.png",
    "layer_persistence.png",
    "layer_deep_model.png",
    "score.tif",
    "persistence.tif",
    "deep_anomaly.tif",
    "detections.geojson",
    "timeseries.json",
    "report.json",
]

CAVEATS = [
    "Outputs are multi-temporal SURFACE-CHANGE indicators only — never a "
    "probability of a buried target, never a depth estimate (docs/SCIENCE-SCOPE.md).",
    "Optical Sentinel-2 cannot see underground; signatures may also be produced "
    "by ordinary agronomy, hydrology, geology or residual cloud/shadow artefacts.",
    "CPF significance is calibrated against a surrogate null of THIS region: it "
    "controls false positives under smooth seasonal drift, it does not classify "
    "the cause of a change.",
    "In selftest mode all detections live on a synthetic planted anomaly "
    "(synthetic=true) — they verify the deployment, nothing about real terrain.",
    "Any field follow-up must use ground-based geophysics within local law.",
]

# Native-resolution tiling limits (see capabilities endpoint).
TILE_PX_DEFAULT = 512
TILE_HALO_PX = 24
MAX_NATIVE_TOTAL_PX = 4_200_000      # ≈ 20.5 × 20.5 km at 10 m
MAX_NATIVE_SIDE_PX = 3072


@dataclass
class DeepParams:
    polygon: List[List[float]]
    date_from: str
    date_to: str
    grid: int = 512                     # 128 | 256 | 512 (resampled mode)
    max_cloud_percent: float = 20.0
    max_dates: int = 14                 # accepted scenes target (4..24)
    min_valid_fraction: float = 0.55    # per-scene quality gate
    recent_k: int = 4                   # "recent" window length
    z_threshold: float = 1.5            # persistence threshold (legacy)
    score_threshold: float = 55.0       # component cut on the 0-100 score (legacy)
    min_pixels: int = 9
    model: str = "pca"                  # pca | autoencoder
    autoencoder_epochs: int = 300
    # --- v1.3.0 -----------------------------------------------------------
    fusion_mode: str = "cpf"            # cpf | legacy
    n_surrogates: int = 199             # CPF surrogate count (0..999)
    alpha: float = 0.01                 # CPF cluster significance level
    resolution_m: Optional[float] = None  # native mode: 10..100 m (None = grid mode)
    tile_px: int = TILE_PX_DEFAULT      # internal/testing: max tile core size

    def sanitized(self) -> "DeepParams":
        p = DeepParams(**vars(self))
        p.grid = int(min(512, max(64, p.grid)))
        p.max_dates = int(min(24, max(4, p.max_dates)))
        p.recent_k = int(min(max(2, p.recent_k), p.max_dates - 1))
        p.min_valid_fraction = float(min(0.95, max(0.30, p.min_valid_fraction)))
        p.max_cloud_percent = float(min(100.0, max(0.0, p.max_cloud_percent)))
        p.score_threshold = float(min(90.0, max(25.0, p.score_threshold)))
        p.min_pixels = int(max(1, p.min_pixels))
        p.model = "autoencoder" if p.model == "autoencoder" else "pca"
        p.autoencoder_epochs = int(min(1200, max(50, p.autoencoder_epochs)))
        p.fusion_mode = "legacy" if p.fusion_mode == "legacy" else "cpf"
        p.n_surrogates = int(min(999, max(0, p.n_surrogates)))
        p.alpha = float(min(0.1, max(0.001, p.alpha)))
        # The add-1 conformal p-value floor is 1/(1+n_surrogates); without
        # enough surrogates nothing could ever be significant at alpha.
        if p.fusion_mode == "cpf":
            min_surr = int(np.ceil(1.0 / p.alpha)) - 1
            if p.n_surrogates < min_surr:
                p.n_surrogates = min(999, min_surr)
        p.resolution_m = None if p.resolution_m is None else float(min(100.0, max(10.0, p.resolution_m)))
        p.tile_px = int(min(512, max(64, p.tile_px)))
        return p


@dataclass
class SceneInfo:
    date: str
    valid_fraction: float
    indices: Dict[str, np.ndarray] = field(default_factory=dict)
    composite: Optional[np.ndarray] = None


def data_dir() -> str:
    return os.environ.get("DEEP_DATA_DIR", os.path.join(os.getcwd(), "deep_jobs"))


def _cell_size_m(bbox_wsen: Sequence[float], width: int, height: int) -> float:
    west, south, east, north = bbox_wsen
    lat_mid = (north + south) / 2.0
    lon_len_m = (east - west) * 111320.0 * max(0.05, np.cos(np.radians(lat_mid)))
    lat_len_m = (north - south) * 110574.0
    return float(((lon_len_m / width) + (lat_len_m / height)) / 2.0)


def _bbox_wsen(ring: Sequence[Sequence[float]]) -> List[float]:
    lons = [float(p[0]) for p in ring]
    lats = [float(p[1]) for p in ring]
    return [min(lons), min(lats), max(lons), max(lats)]


# ----------------------------------------------------------------- tile plan

@dataclass
class TileSpec:
    """One space tile: core box in the full grid + fetch box (with halo)."""
    row0: int
    col0: int
    rows: int
    cols: int
    halo_top: int
    halo_left: int
    fetch_h: int
    fetch_w: int

    @property
    def fetch_row0(self) -> int:
        return self.row0 - self.halo_top

    @property
    def fetch_col0(self) -> int:
        return self.col0 - self.halo_left


@dataclass
class TilePlan:
    width: int
    height: int
    native: bool
    resolution_m: Optional[float]
    tiles: List[TileSpec]

    @property
    def n_tiles(self) -> int:
        return len(self.tiles)


def _native_grid(bbox_wsen: Sequence[float], resolution_m: float) -> Tuple[int, int]:
    west, south, east, north = bbox_wsen
    lat_mid = float(np.radians((north + south) / 2.0))
    lon_len_m = (east - west) * 111320.0 * max(0.05, float(np.cos(lat_mid)))
    lat_len_m = (north - south) * 110574.0
    w = int(max(64, np.ceil(lon_len_m / resolution_m)))
    h = int(max(64, np.ceil(lat_len_m / resolution_m)))
    if w > MAX_NATIVE_SIDE_PX or h > MAX_NATIVE_SIDE_PX or w * h > MAX_NATIVE_TOTAL_PX:
        raise ValueError(
            f"Native {resolution_m:g} m grid for this AOI is {w}×{h} px "
            f"({w * h / 1e6:.1f} M px) — over the {MAX_NATIVE_TOTAL_PX / 1e6:.1f} M px "
            "budget. Use a coarser resolution_m (e.g. 20), a smaller polygon, or "
            "omit resolution_m to fall back to the resampled grid mode."
        )
    return w, h


def _tile_plan(p: DeepParams, bbox_wsen: Sequence[float]) -> TilePlan:
    """Build the tile decomposition of the AOI bbox.

    Grid mode (``resolution_m=None``): one tile of ``grid×grid`` over the whole
    bbox (v1.2.x behaviour).  Native mode: full native grid split into cores of
    ≤ ``tile_px`` with a ``TILE_HALO_PX`` overlap halo per side.
    """
    west, south, east, north = (float(v) for v in bbox_wsen)
    if p.resolution_m is None:
        w = h = int(p.grid)
        return TilePlan(
            width=w, height=h, native=False, resolution_m=None,
            tiles=[TileSpec(0, 0, h, w, 0, 0, h, w)],
        )

    w, h = _native_grid(bbox_wsen, float(p.resolution_m))
    tile = int(p.tile_px)
    ntx = int(np.ceil(w / tile))
    nty = int(np.ceil(h / tile))
    # even-ish split of the full grid into cores
    def _splits(n: int, k: int) -> List[int]:
        base, rem = divmod(n, k)
        return [base + (1 if i < rem else 0) for i in range(k)]

    cols_sizes = _splits(w, ntx)
    rows_sizes = _splits(h, nty)
    tiles: List[TileSpec] = []
    row0 = 0
    for rs in rows_sizes:
        col0 = 0
        for cs in cols_sizes:
            halo_top = min(TILE_HALO_PX, row0)
            halo_bot = min(TILE_HALO_PX, h - (row0 + rs))
            halo_left = min(TILE_HALO_PX, col0)
            halo_right = min(TILE_HALO_PX, w - (col0 + cs))
            tiles.append(TileSpec(
                row0=row0, col0=col0, rows=rs, cols=cs,
                halo_top=halo_top, halo_left=halo_left,
                fetch_h=rs + halo_top + halo_bot,
                fetch_w=cs + halo_left + halo_right,
            ))
            col0 += cs
        row0 += rs
    return TilePlan(width=w, height=h, native=True,
                    resolution_m=float(p.resolution_m), tiles=tiles)


def _tile_ring(tile: TileSpec, bbox_wsen: Sequence[float], plan: TilePlan) -> List[Tuple[float, float]]:
    """Fetch bbox (pixel edges → lon/lat) as a closed-able rectangle ring."""
    west, south, east, north = (float(v) for v in bbox_wsen)
    r0 = tile.fetch_row0
    c0 = tile.fetch_col0
    r1 = r0 + tile.fetch_h
    c1 = c0 + tile.fetch_w
    fw = plan.width
    fh = plan.height
    lon = lambda c: west + (c / fw) * (east - west)
    lat = lambda r: north - (r / fh) * (north - south)
    return [(lon(c0), lat(r1)), (lon(c1), lat(r1)), (lon(c1), lat(r0)), (lon(c0), lat(r0))]


# ------------------------------------------------------------- per-tile chain

def _analyze_tile(p: DeepParams, scenes: List[SceneInfo]) -> Dict:
    """Run evidence → model → fusion (→ CPF) on ONE tile's scenes."""
    dates, stacks = raster.stack_scenes(scenes)
    evidence = temporal_mod.temporal_evidence(dates, stacks, p.recent_k, p.z_threshold)

    deep_map, model_used = deep_anomaly(evidence, model=p.model,
                                        autoencoder_epochs=p.autoencoder_epochs)
    fused = fuse(evidence, deep_map)

    out: Dict = {
        "dates": dates,
        "stacks": stacks,
        "evidence": evidence,
        "deep_map": deep_map,
        "model_used": model_used,
        "fused": fused,
        "composite": scenes[-1].composite if scenes else None,
        "cpf": None,
    }
    if p.fusion_mode == "cpf":
        out["cpf"] = cpf_mod.cpf_analyze(
            evidence,
            n_surr=p.n_surrogates,
            alpha=p.alpha,
            min_px=p.min_pixels,
        )
    return out


# ------------------------------------------------------------- stitching

def _empty_maps(plan: TilePlan) -> Dict[str, np.ndarray]:
    h, w = plan.height, plan.width
    nan = lambda: np.full((h, w), np.nan, dtype=np.float32)
    return {
        "score": nan(),
        "coherence": nan(),
        "moisture": nan(),
        "vegetation": nan(),
        "soil": nan(),
        "persistence": nan(),
        "deep": nan(),
        "composite": np.zeros((h, w, 3), dtype=np.float32),
        "valid": np.zeros((h, w), bool),
        "tile_labels": np.zeros((h, w), dtype=np.int32),
    }


def _paste_tile(maps: Dict[str, np.ndarray], tile: TileSpec, res: Dict,
                label_offset: int) -> None:
    """Crop the tile core (drop halo) and paste into the stitched maps."""
    r0, c0 = tile.halo_top, tile.halo_left
    r1, c0e = r0 + tile.rows, c0 + tile.cols
    sl = (slice(r0, r1), slice(c0, c0e))
    gr = (slice(tile.row0, tile.row0 + tile.rows),
          slice(tile.col0, tile.col0 + tile.cols))

    fused = res["fused"]
    cpf_res = res["cpf"]
    if cpf_res is not None:
        maps["score"][gr] = cpf_res["sig_score"][sl]
    else:
        maps["score"][gr] = fused["score_0_100"][sl]
    maps["coherence"][gr] = fused["coherence"][sl]
    maps["moisture"][gr] = fused["layers"]["moisture_deficit"][sl]
    maps["vegetation"][gr] = fused["layers"]["vegetation_stress"][sl]
    maps["soil"][gr] = fused["layers"]["soil_exposure"][sl]
    maps["persistence"][gr] = fused["layers"]["persistence"][sl]
    maps["deep"][gr] = fused["layers"]["deep_model"][sl]
    maps["valid"][gr] = np.isfinite(res["evidence"]["z_ndmi"][sl])

    comp = res.get("composite")
    if comp is not None:
        maps["composite"][gr[0], gr[1], :] = comp[sl]

    if cpf_res is not None:
        maps["tile_labels"][gr] = cpf_res["labels"][sl] + label_offset


# ------------------------------------------------------------- finish/report

def _report(p: DeepParams, mode: str, bbox_wsen: Sequence[float], scenes_meta, extra: Dict) -> Dict:
    from . import DEEP_VERSION

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "schema": "subsurf.deep.report/1.3.0",
        "mode": mode,
        "synthetic": mode == "synthetic-selftest",
        "generated_utc": now,
        "deep_version": DEEP_VERSION,
        "bbox_wgs84": list(bbox_wsen),
        "parameters": {
            "grid": p.grid,
            "max_cloud_percent": p.max_cloud_percent,
            "max_dates": p.max_dates,
            "min_valid_fraction": p.min_valid_fraction,
            "recent_k": p.recent_k,
            "z_threshold": p.z_threshold,
            "score_threshold": p.score_threshold,
            "min_pixels": p.min_pixels,
            "model": extra.get("model_used", p.model),
            "fusion_mode": p.fusion_mode,
            "n_surrogates": p.n_surrogates,
            "alpha": p.alpha,
            "resolution_m": p.resolution_m,
        },
        "scenes_used": scenes_meta,
        "caveats": CAVEATS,
        **extra,
    }


def _tile_median_series(res: Dict, n_dates: int) -> Dict[str, List[Optional[float]]]:
    """Per-date nanmedian of every index over ONE tile (for stitching timeseries)."""
    series: Dict[str, List[Optional[float]]] = {}
    for name in raster.INDICES:
        stack = res["stacks"][name]
        with np.errstate(all="ignore"):
            meds = np.nanmedian(stack.reshape(n_dates, -1), axis=1)
        series[name] = [None if not np.isfinite(v) else float(v) for v in meds]
    return series


def _average_tile_series(
    ts_dates: List[str], per_tile: List[Dict[str, List[Optional[float]]]]
) -> Dict:
    """Average the per-tile index medians into one AOI timeseries."""
    names = list(raster.INDICES)
    n = len(ts_dates)
    out: Dict[str, List[Optional[float]]] = {}
    for name in names:
        arr = np.full((len(per_tile), n), np.nan)
        for ti, tile_series in enumerate(per_tile):
            row = tile_series.get(name)
            if not row:
                continue
            for di, v in enumerate(row[:n]):
                if v is not None:
                    arr[ti, di] = v
        with np.errstate(all="ignore"):
            m = np.nanmean(arr, axis=0) if arr.size else np.full(n, np.nan)
        out[name] = [None if not np.isfinite(v) else round(float(v), 4) for v in m]
    return {"dates": ts_dates, "series": out}


def _finish(
    p: DeepParams,
    mode: str,
    ring: Sequence[Sequence[float]],
    plan: TilePlan,
    maps: Dict[str, np.ndarray],
    cluster_p: Dict[int, float],
    tiles_ok: int,
    tiles_failed: int,
    scene_rows: List[Dict],
    model_used: str,
    out_dir: str,
    progress: ProgressCb,
    timeseries: Optional[Dict] = None,
) -> Dict:
    """Global labeling on the stitched maps + artifacts + report."""
    os.makedirs(out_dir, exist_ok=True)
    bbox_wsen = _bbox_wsen(ring)
    width, height = plan.width, plan.height
    cell_size_m = _cell_size_m(bbox_wsen, width, height)

    score = maps["score"]
    coherence = maps["coherence"]
    persistence = maps["persistence"]
    deep_map = maps["deep"]

    if progress:
        progress(88, "global connected components + polygons")

    confidence_by_id: Dict[int, str] = {}
    extra_props_by_id: Dict[int, Dict] = {}
    if p.fusion_mode == "cpf":
        mask = (maps["tile_labels"] > 0) & maps["valid"]
        # significance mask = pixels whose tile cluster is significant
        sig_labels = {i for i, pv in cluster_p.items() if pv <= p.alpha}
        if sig_labels:
            in_sig = np.isin(maps["tile_labels"], list(sig_labels))
            mask = mask & in_sig
        else:
            mask = np.zeros_like(mask)
        labels, count = label_components(mask)
        for cid in range(1, count + 1):
            sel = labels == cid
            if int(sel.sum()) < p.min_pixels:
                continue
            ids = [int(i) for i in np.unique(maps["tile_labels"][sel]) if i > 0]
            p_vals = [cluster_p[i] for i in ids if i in cluster_p]
            p_val = min(p_vals) if p_vals else 1.0
            confidence_by_id[cid] = cpf_mod.confidence_from_p(p_val)
            extra_props_by_id[cid] = {
                "p_value": round(p_val, 5),
                "method": "cpf",
            }
    else:
        mask = (score >= p.score_threshold) & maps["valid"]
        labels, count = label_components(mask)

    features, summaries = detections_to_geojson(
        labels, count, score, coherence, persistence, bbox_wsen, cell_size_m,
        min_pixels=p.min_pixels,
        confidence_by_id=confidence_by_id,
        extra_props_by_id=extra_props_by_id,
        synthetic=(mode == "synthetic-selftest"),
    )

    if progress:
        progress(94, "writing artifacts")
    write_score_png(os.path.join(out_dir, "score_map.png"), score)
    write_overlay_png(os.path.join(out_dir, "overlay.png"), maps["composite"], score)
    write_layer_png(os.path.join(out_dir, "layer_moisture.png"), maps["moisture"])
    write_layer_png(os.path.join(out_dir, "layer_vegetation.png"), maps["vegetation"])
    write_layer_png(os.path.join(out_dir, "layer_soil.png"), maps["soil"])
    write_layer_png(os.path.join(out_dir, "layer_persistence.png"), persistence)
    write_layer_png(os.path.join(out_dir, "layer_deep_model.png"), deep_map)
    write_geotiff(os.path.join(out_dir, "score.tif"), score, bbox_wsen)
    write_geotiff(os.path.join(out_dir, "persistence.tif"), persistence, bbox_wsen)
    write_geotiff(os.path.join(out_dir, "deep_anomaly.tif"), deep_map, bbox_wsen)
    write_json(os.path.join(out_dir, "detections.geojson"),
               {"type": "FeatureCollection",
                "properties": {
                    "synthetic": mode == "synthetic-selftest",
                    "fusion_mode": p.fusion_mode,
                    "cell_size_m": round(cell_size_m, 2),
                },
                "features": features})

    if timeseries is None:
        timeseries = {"dates": [r["date"] for r in scene_rows], "series": {}}
    write_json(os.path.join(out_dir, "timeseries.json"), timeseries)

    high = [s for s in summaries if s["confidence"] in ("high", "medium")]
    extra: Dict = {
        "model_used": model_used,
        "fusion_mode": p.fusion_mode,
        "grid_width_px": width,
        "grid_height_px": height,
        "cell_size_m": round(cell_size_m, 2),
        "coverage_m2": round(cell_size_m * width * height, 1),
        "native_resolution": plan.native,
        "resolution_m": plan.resolution_m,
        "tiles": plan.n_tiles,
        "tiles_ok": tiles_ok,
        "tiles_failed": tiles_failed,
        "scenes_accepted": len(scene_rows),
        "recent_window": [r["date"] for r in scene_rows[-p.recent_k:]],
        "baseline_window": [r["date"] for r in scene_rows[: max(2, len(scene_rows) - p.recent_k + 1)]],
        "score_weights": dict(WEIGHTS),
        "components_detected": len(summaries),
        "components_high_or_medium": len(high),
        "detections": summaries,
        "artifacts": ARTIFACTS,
    }
    if p.fusion_mode == "cpf":
        p_vals = [v for v in cluster_p.values()]
        extra["cpf"] = {
            "alpha": p.alpha,
            "n_surrogates": p.n_surrogates,
            "p_pix": cpf_mod.DEFAULTS["p_pix"],
            "clusters_seeded": len(cluster_p),
            "clusters_significant": sum(1 for v in p_vals if v <= p.alpha),
            "min_cluster_p": round(min(p_vals), 5) if p_vals else None,
            "null_calibration": (
                "phase-randomised surrogate cluster-mass null; add-1 conformal "
                "p-values control the family-wise false-positive rate under "
                "smooth seasonal drift"
            ),
        }
    report = _report(p, mode, bbox_wsen, scene_rows, extra)
    write_json(os.path.join(out_dir, "report.json"), report)
    if progress:
        progress(100, "done")
    return report


# ------------------------------------------------------- backward-compat path

def _finalize(
    p: DeepParams,
    mode: str,
    ring: Sequence[Sequence[float]],
    scenes: List[SceneInfo],
    progress: ProgressCb,
    out_dir: str,
) -> Dict:
    """Single-tile path (grid mode) — v1.2.x-compatible entry point."""
    p = p.sanitized()
    bbox_wsen = _bbox_wsen(ring)
    plan = _tile_plan(p, bbox_wsen)
    tile = plan.tiles[0]

    if progress:
        progress(55, "computing spectral indices + temporal statistics")
    res = _analyze_tile(p, scenes)
    if progress:
        progress(70, f"unsupervised anomaly model ({p.model})")
    if progress:
        progress(80, f"evidence fusion ({p.fusion_mode})")

    maps = _empty_maps(plan)
    cluster_p: Dict[int, float] = {}
    if res["cpf"] is not None:
        cluster_p = {i + 1: pv for i, pv in res["cpf"]["cluster_p"].items()}
    comp = scenes[-1].composite
    if comp is not None:
        maps["composite"] = comp
    _paste_tile(maps, tile, res, label_offset=1)

    scene_rows = [
        {"date": s.date, "valid_fraction": round(s.valid_fraction, 4)} for s in scenes
    ]
    # AOI-median time series per index (chartable in the app/console).
    ts_dates = [s.date for s in scenes]
    series: Dict[str, List] = {}
    for name in raster.INDICES:
        with np.errstate(all="ignore"):
            series[name] = [
                None if not np.isfinite(v) else round(float(v), 4)
                for v in np.nanmedian(res["stacks"][name].reshape(len(ts_dates), -1), axis=1)
            ]
    report = _finish(p, mode, ring, plan, maps, cluster_p, 1, 0, scene_rows,
                     res["model_used"], out_dir, progress,
                     timeseries={"dates": ts_dates, "series": series})
    return report


# ------------------------------------------------------------------ live mode

def run_live(p: DeepParams, ring, progress: ProgressCb, out_dir: str) -> Dict:
    """Live acquisition + full analysis (CDSE credentials required)."""
    p = p.sanitized()
    if not cdse_process.credentials_present():
        raise cdse_process.DeepAuthError(
            "No Copernicus credentials configured (COPERNICUS_USERNAME/"
            "COPERNICUS_PASSWORD or COPERNICUS_CLIENT_ID/COPERNICUS_CLIENT_SECRET)."
        )

    if progress:
        progress(2, "authenticating with Copernicus Data Space")
    token = cdse_process.get_token()

    bbox_wsen = _bbox_wsen(ring)
    plan = _tile_plan(p, bbox_wsen)

    candidates = cdse_process.plan_dates(p.date_from, p.date_to, max_dates=min(60, p.max_dates * 4))
    if not candidates:
        raise ValueError("Empty date window after clamping to today (UTC).")

    maps = _empty_maps(plan)
    cluster_p: Dict[int, float] = {}
    label_offset = 0
    tiles_ok = 0
    tiles_failed = 0
    scene_rows: List[Dict] = []
    model_used = p.model
    ts_dates: List[str] = []
    ts_per_tile: List[Dict[str, List[Optional[float]]]] = []
    resampling = "bilinear" if plan.native else "nearest"

    total_steps = plan.n_tiles * len(candidates)
    step = 0
    for ti, tile in enumerate(plan.tiles):
        tile_ring = _tile_ring(tile, bbox_wsen, plan)
        scenes: List[SceneInfo] = []
        for date_iso in candidates:
            if len(scenes) >= p.max_dates:
                break
            step += 1
            if progress:
                pct = 3 + int(47 * step / max(1, total_steps))
                progress(pct, f"tile {ti + 1}/{plan.n_tiles}: acquiring {date_iso} "
                              f"({len(scenes)}/{p.max_dates} accepted)")
            try:
                stack = cdse_process.fetch_scene_stack(
                    token, tile_ring, date_iso, tile.fetch_w, tile.fetch_h,
                    p.max_cloud_percent, resampling=resampling,
                )
            except cdse_process.DeepFetchError as exc:
                log.warning("skip %s: %s", date_iso, exc)
                continue
            frac = raster.scene_valid_fraction(stack)
            if frac < p.min_valid_fraction:
                log.info("skip %s: valid fraction %.2f < %.2f", date_iso, frac, p.min_valid_fraction)
                continue
            refl = raster.to_reflectance(stack)
            valid = raster.valid_mask(stack)
            info = SceneInfo(date=date_iso, valid_fraction=frac)
            info.indices = raster.compute_indices(refl, valid)
            info.composite = raster.composite_rgb(refl)
            scenes.append(info)

        if len(scenes) < 4:
            log.warning("tile %d/%d rejected: only %d usable scene(s)", ti + 1, plan.n_tiles, len(scenes))
            tiles_failed += 1
            continue

        scenes.sort(key=lambda s: s.date)
        if progress:
            progress(52 + int(36 * ti / max(1, plan.n_tiles)),
                     f"tile {ti + 1}/{plan.n_tiles}: evidence + {p.fusion_mode} fusion")
        res = _analyze_tile(p, scenes)
        model_used = res["model_used"]
        if not ts_dates:
            ts_dates = [s.date for s in scenes]
        ts_per_tile.append(_tile_median_series(res, len(scenes)))
        _paste_tile(maps, tile, res, label_offset=label_offset + 1)
        if res["cpf"] is not None:
            for i, pv in res["cpf"]["cluster_p"].items():
                cluster_p[label_offset + 1 + i] = float(pv)
            label_offset += res["cpf"]["n_clusters"]
        tiles_ok += 1
        if not scene_rows:
            scene_rows = [{"date": s.date, "valid_fraction": round(s.valid_fraction, 4)}
                          for s in scenes]
        del res  # free per-tile intermediates before the next tile

    if tiles_ok == 0:
        raise ValueError(
            "No tile had ≥4 usable scenes in the window. Widen the date range, "
            "raise max_cloud_percent, or lower min_valid_fraction."
        )

    if progress:
        progress(90, "stitching complete")
    return _finish(p, "live", ring, plan, maps, cluster_p, tiles_ok, tiles_failed,
                   scene_rows, model_used, out_dir, progress,
                   timeseries=_average_tile_series(ts_dates, ts_per_tile))


# ------------------------------------------------------------------ selftest

def _synthetic_stack(p: DeepParams, scene_dates: List[str],
                     w: Optional[int] = None, h: Optional[int] = None,
                     row_off: int = 0, col_off: int = 0,
                     full_w: Optional[int] = None, full_h: Optional[int] = None):
    """Deterministic 8-band stacks with an injected drying/stress anomaly.

    ONE ellipse is planted per AOI in FULL-GRID coordinates; every tile
    generates only the part that overlaps its fetch box, so multi-tile
    selftests exercise the stitching path and tiles without the ellipse act
    as in-situ null controls.  ``w``/``h`` default to ``p.grid`` (v1.2.x
    compatibility; offsets default to zero).
    """
    rng = np.random.default_rng(20261107)
    w = int(p.grid if w is None else w)
    h = int(p.grid if h is None else h)
    full_w = int(w if full_w is None else full_w)
    full_h = int(h if full_h is None else full_h)
    # global pixel coordinates of this tile's fetch box
    yy, xx = np.mgrid[row_off:row_off + h, col_off:col_off + w].astype(np.float32)
    n_scenes = len(scene_dates)

    # Gentle natural texture (corrugation + noise) in the "vegetated" scene —
    # continuous in global coordinates, so it stitches seamlessly.
    texture = 0.5 + 0.5 * np.sin(xx / 17.0) * np.sin(yy / 23.0)
    # Radiometric-noise level of real L2A pixels (~0.1% reflectance) — keeps the
    # robust baseline tight so the injected anomaly stands out, like real data.
    noise = lambda: rng.normal(0, 0.0008, size=(h, w)).astype(np.float32)

    # ONE anomaly ellipse in full-grid coordinates, fading in over the recent scenes.
    cy, cx, ay, ax = full_h * 0.38, full_w * 0.62, full_h * 0.11, full_w * 0.15
    ellipse = np.exp(-(((yy - cy) / ay) ** 2 + ((xx - cx) / ax) ** 2)).astype(np.float32)
    ramp = np.clip(
        (np.arange(n_scenes) - (n_scenes - 5)) / 4.0, 0.0, 1.0
    ).astype(np.float32)

    stacks = []
    for t in range(n_scenes):
        a = ellipse * ramp[t]
        # Drying / stress signature: NIR drops (vegetation loss), SWIR1 rises
        # (moisture deficit), visible bands rise (soil exposure).
        blue = (0.05 + 0.01 * texture + noise()) * (1.0 + 0.15 * a)
        green = (0.09 + 0.015 * texture + noise()) * (1.0 + 0.15 * a)
        red = (0.06 + 0.02 * texture + noise()) * (1.0 + 0.60 * a)
        nir = (0.34 + 0.05 * texture + noise()) * (1.0 - 0.28 * a)
        swir1 = (0.20 + 0.02 * texture + noise()) * (1.0 + 0.38 * a)
        swir2 = (0.13 + 0.015 * texture + noise()) * (1.0 + 0.22 * a)
        bands = [blue, green, red, nir, swir1, swir2]
        dn = [np.clip(b, 0.0, 1.4) * 10000.0 + cdse_process.DN_OFFSET for b in bands]
        scl = np.full((h, w), 4, dtype=np.uint16)      # vegetation
        mask = np.ones((h, w), dtype=np.uint16)
        stack = np.stack(dn + [scl, mask], axis=-1).astype(np.uint16)
        stacks.append(stack)
    return stacks


def run_selftest(p: DeepParams, ring, progress: ProgressCb, out_dir: str) -> Dict:
    """Offline end-to-end validation on a deterministic synthetic region."""
    p = p.sanitized()
    if p.resolution_m is None:
        p.grid = min(p.grid, 256)
    bbox_wsen = _bbox_wsen(ring)
    plan = _tile_plan(p, bbox_wsen)

    if progress:
        progress(5, "generating synthetic Sentinel-2 stack (selftest mode)")
    today = datetime.now(timezone.utc).date()
    n_scenes = 9
    scene_dates = [
        (today - timedelta(days=n_scenes - 1 - t)).isoformat() for t in range(n_scenes)
    ]

    maps = _empty_maps(plan)
    cluster_p: Dict[int, float] = {}
    label_offset = 0
    tiles_ok = 0
    scene_rows: List[Dict] = []
    model_used = p.model
    ts_dates: List[str] = scene_dates
    ts_per_tile: List[Dict[str, List[Optional[float]]]] = []

    for ti, tile in enumerate(plan.tiles):
        if progress:
            progress(8 + int(74 * ti / max(1, plan.n_tiles)),
                     f"synthetic tile {ti + 1}/{plan.n_tiles} ({tile.fetch_w}×{tile.fetch_h} px)")
        stacks = _synthetic_stack(p, scene_dates, w=tile.fetch_w, h=tile.fetch_h,
                                  row_off=tile.fetch_row0, col_off=tile.fetch_col0,
                                  full_w=plan.width, full_h=plan.height)

        scenes: List[SceneInfo] = []
        for t, date_iso in enumerate(scene_dates):
            refl = raster.to_reflectance(stacks[t])
            valid = raster.valid_mask(stacks[t])
            info = SceneInfo(date=date_iso, valid_fraction=raster.scene_valid_fraction(stacks[t]))
            info.indices = raster.compute_indices(refl, valid)
            info.composite = raster.composite_rgb(refl)
            scenes.append(info)
        scenes.sort(key=lambda s: s.date)

        res = _analyze_tile(p, scenes)
        model_used = res["model_used"]
        ts_per_tile.append(_tile_median_series(res, len(scenes)))
        _paste_tile(maps, tile, res, label_offset=label_offset + 1)
        if res["cpf"] is not None:
            for i, pv in res["cpf"]["cluster_p"].items():
                cluster_p[label_offset + 1 + i] = float(pv)
            label_offset += res["cpf"]["n_clusters"]
        tiles_ok += 1
        if not scene_rows:
            scene_rows = [{"date": s.date, "valid_fraction": round(s.valid_fraction, 4)}
                          for s in scenes]
        del res

    return _finish(p, "synthetic-selftest", ring, plan, maps, cluster_p, tiles_ok, 0,
                   scene_rows, model_used, out_dir, progress,
                   timeseries=_average_tile_series(ts_dates, ts_per_tile))


def new_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"
