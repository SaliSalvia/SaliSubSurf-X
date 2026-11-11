"""Robust temporal statistics: baseline, z-scores, persistence, Theil–Sen trend.

Design decisions (documented in docs/DEEP-PROCESSING.md):

* The **baseline** is the pixel-wise *median* of every accepted scene — the median
  resists clouds and other single-scene outliers that survive the SCL mask.
* Dispersion uses the **MAD** (median absolute deviation) scaled to a normal
  equivalent (1.4826), giving a breakdown-robust z-score:
  ``z = (recent_median - baseline_median) / (1.4826 * MAD + eps)``.
* **Persistence** is the fraction of the *recent* scenes in which the pixel
  stayed anomalous (z beyond the threshold) — single-date flashes decay, real
  surface change persists.
* **Trend** is a Theil–Sen slope over the recent window (median of pairwise
  slopes) — robust to the remaining outliers, expressed per 30 days.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Dict, List, Sequence, Tuple

import numpy as np

MAD_TO_SIGMA = 1.4826
EPS = 1e-4

# Anomaly direction per index: True = "anomalous when z is NEGATIVE".
NEGATIVE_ANOMALY = {
    "ndvi": True,   # vegetation stress / loss
    "ndmi": True,   # moisture deficit
    "ndwi": True,   # water loss
    "mndwi": True,  # wet-land drying
    "nbr": True,    # drying / disturbance
    "bsi": False,   # bare-soil exposure rises
    "albedo": False,  # brightening (exposed substrate)
}


def robust_z(
    baseline_stack: np.ndarray, recent_stack: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Pixel-wise robust z of the recent median vs. the full baseline.

    Returns ``(z_map, baseline_median)`` as float32 arrays; NaN pixels stay NaN.
    """
    with np.errstate(all="ignore"):
        base_med = np.nanmedian(baseline_stack, axis=0)
        base_mad = np.nanmedian(
            np.abs(baseline_stack - base_med[None, ...]), axis=0
        )
        recent_med = np.nanmedian(recent_stack, axis=0)
    sigma = MAD_TO_SIGMA * base_mad + EPS
    z = (recent_med - base_med) / sigma
    return z.astype(np.float32), base_med.astype(np.float32)


def per_scene_z(
    baseline_stack: np.ndarray, scenes_stack: np.ndarray
) -> np.ndarray:
    """z-score of each scene against the shared baseline ``(T, H, W)``."""
    with np.errstate(all="ignore"):
        base_med = np.nanmedian(baseline_stack, axis=0)
        base_mad = np.nanmedian(
            np.abs(baseline_stack - base_med[None, ...]), axis=0
        )
    sigma = MAD_TO_SIGMA * base_mad + EPS
    z = (scenes_stack - base_med[None, ...]) / sigma[None, ...]
    return z.astype(np.float32)


def persistence(
    scenes_z: np.ndarray, index_name: str, z_threshold: float
) -> np.ndarray:
    """Fraction of recent scenes in which each pixel was anomalous (0..1)."""
    negative = NEGATIVE_ANOMALY.get(index_name, True)
    if negative:
        hits = scenes_z < -abs(z_threshold)
    else:
        hits = scenes_z > abs(z_threshold)
    with np.errstate(all="ignore"):
        frac = np.nanmean(hits.astype(np.float32), axis=0)
    return np.nan_to_num(frac, nan=0.0).astype(np.float32)


def theil_sen_slope(
    stack: np.ndarray, day_numbers: Sequence[int], max_pairs: int = 36
) -> np.ndarray:
    """Robust slope per pixel, units per day, from up to ``max_pairs`` pairs."""
    t, _, _ = stack.shape
    if t < 2:
        return np.zeros(stack.shape[1:], dtype=np.float32)
    pairs = [
        (i, j)
        for i in range(t)
        for j in range(i + 1, t)
        if day_numbers[j] > day_numbers[i]
    ]
    if not pairs:
        return np.zeros(stack.shape[1:], dtype=np.float32)
    if len(pairs) > max_pairs:
        step = len(pairs) / float(max_pairs)
        pairs = [pairs[int(k * step)] for k in range(max_pairs)]
    slopes = []
    for i, j in pairs:
        dt = float(day_numbers[j] - day_numbers[i])
        slopes.append((stack[j] - stack[i]) / dt)
    arr = np.stack(slopes, axis=0)
    with np.errstate(all="ignore"):
        out = np.nanmedian(arr, axis=0)
    return np.nan_to_num(out, nan=0.0).astype(np.float32)


def day_number(date_iso: str) -> int:
    return _date.fromisoformat(date_iso).toordinal()


def temporal_evidence(
    dates: List[str],
    stacks: Dict[str, np.ndarray],
    recent_k: int,
    z_threshold: float,
) -> Dict[str, np.ndarray]:
    """Build every temporal evidence layer used by the fusion stage.

    Layers (all float32, 0..1 unless noted):
      * ``z_<idx>``       — robust z of the recent median (dimensionless)
      * ``persistence``   — mean persistence across the moisture/vegetation set
      * ``trend_ndmi``    — Theil–Sen slope of NDMI per 30 days (clipped to ±0.1)
      * ``trend_ndvi``    — Theil–Sen slope of NDVI per 30 days (clipped to ±0.1)
    """
    t = len(dates)
    k = max(1, min(int(recent_k), t))
    baseline = {name: stack[: max(2, t - k + 1)] for name, stack in stacks.items()}
    recent = {name: stack[-k:] for name, stack in stacks.items()}

    days = [day_number(d) for d in dates]
    out: Dict[str, np.ndarray] = {}

    persist_sum = None
    persist_count = 0
    for name in ("ndvi", "ndwi", "mndwi", "ndmi", "nbr", "bsi", "albedo"):
        z, _ = robust_z(baseline[name], recent[name])
        out[f"z_{name}"] = z
        p = persistence(per_scene_z(baseline[name], recent[name]), name, z_threshold)
        out[f"persistence_{name}"] = p
        if name in ("ndmi", "ndvi", "bsi", "nbr"):
            persist_sum = p if persist_sum is None else persist_sum + p
            persist_count += 1
    if persist_sum is None:
        persist_sum = np.zeros_like(z)
        persist_count = 1
    out["persistence"] = (persist_sum / max(1, persist_count)).astype(np.float32)

    for name, key in (("ndmi", "trend_ndmi"), ("ndvi", "trend_ndvi")):
        slope = theil_sen_slope(stacks[name], days)
        out[key] = np.clip(slope * 30.0, -0.1, 0.1).astype(np.float32)

    return out
