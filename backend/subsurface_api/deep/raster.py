"""Preprocessing + spectral indices on the 8-band UINT16 stacks.

Band layout (see cdse_process.py): ``B02 B03 B04 B08 B11 B12 SCL dataMask``.

Reflectance: L2A quantities are ``(DN - offset) / 10000`` with the baseline-4.0
harmonisation offset (+1000) applied since January 2022. Indices use NaN for
invalid pixels so that downstream medians/z-scores stay honest.

SCL classes kept as *valid surface*: 2 (dark area), 4 (vegetation), 5 (bare),
6 (water), 7 (unclassified). Masked out: 0/1 (nodata/saturated), 3 (cloud
shadow), 8/9 (cloud), 10 (cirrus), 11 (snow/ice) — a moisture/vegetation anomaly
study must not read clouds as ground change.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .cdse_process import DN_OFFSET

I_B02, I_B03, I_B04, I_B08, I_B11, I_B12, I_SCL, I_MASK = range(8)

VALID_SCL = {2, 4, 5, 6, 7}

INDICES = ("ndvi", "ndwi", "mndwi", "ndmi", "nbr", "bsi", "albedo")


def _safe_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a / b with NaN wherever the denominator is ~0 or either side is NaN."""
    out = np.full(np.broadcast(a, b).shape, np.nan, dtype=np.float32)
    ok = np.isfinite(a) & np.isfinite(b) & (np.abs(b) > 1e-6)
    np.divide(a.astype(np.float32), b.astype(np.float32), out=out, where=ok)
    return out


def to_reflectance(stack: np.ndarray) -> np.ndarray:
    """Bands 0..5 (reflectance bands) → surface reflectance in [0, 2]."""
    refl = (stack[..., :6].astype(np.float32) - DN_OFFSET) / 10000.0
    return np.clip(refl, 0.0, 2.0).astype(np.float32)


def valid_mask(stack: np.ndarray) -> np.ndarray:
    """True where the pixel is usable surface (SCL + dataMask)."""
    scl = stack[..., I_SCL].astype(np.int16)
    dm = stack[..., I_MASK].astype(np.int16)
    keep = np.isin(scl, list(VALID_SCL)) & (dm > 0)
    return keep


def scene_valid_fraction(stack: np.ndarray) -> float:
    """Fraction of usable pixels — the per-scene quality gate."""
    vm = valid_mask(stack)
    return float(vm.mean()) if vm.size else 0.0


def compute_indices(refl: np.ndarray, valid: np.ndarray) -> Dict[str, np.ndarray]:
    """All documented indices; invalid pixels are NaN (float32)."""
    b02, b03, b04 = refl[..., 0], refl[..., 1], refl[..., 2]
    b08, b11, b12 = refl[..., 3], refl[..., 4], refl[..., 5]

    ndvi = _safe_div(b08 - b04, b08 + b04)              # vegetation greenness
    ndwi = _safe_div(b03 - b08, b03 + b08)              # open water (McFeeters)
    mndwi = _safe_div(b03 - b11, b03 + b11)             # moist/wet land (Xu)
    ndmi = _safe_div(b08 - b11, b08 + b11)              # canopy/soil moisture
    nbr = _safe_div(b08 - b12, b08 + b12)               # burn/soil dryness proxy
    bsi = _safe_div((b11 + b04) - (b08 + b02),
                    (b11 + b04) + (b08 + b02))          # bare-soil exposure
    albedo = (0.25 * b02 + 0.25 * b03 + 0.25 * b04 + 0.25 * b08).astype(np.float32)

    out: Dict[str, np.ndarray] = {}
    for name, arr in (
        ("ndvi", ndvi), ("ndwi", ndwi), ("mndwi", mndwi), ("ndmi", ndmi),
        ("nbr", nbr), ("bsi", bsi), ("albedo", albedo),
    ):
        arr = arr.astype(np.float32)
        arr[~valid] = np.nan
        out[name] = arr
    return out


def composite_rgb(refl: np.ndarray) -> np.ndarray:
    """Natural-colour composite (B04, B03, B02) as float 0..1, NaN→0."""
    rgb = np.stack([refl[..., 2], refl[..., 1], refl[..., 0]], axis=-1)
    rgb = np.nan_to_num(rgb, nan=0.0)
    return np.clip(rgb, 0.0, 1.0).astype(np.float32)


def stack_scenes(
    per_scene,
) -> Tuple[List[str], Dict[str, np.ndarray]]:
    """Reorganise per-scene objects (``.date``, ``.indices``) into per-index stacks."""
    dates = [s.date for s in per_scene]
    stacks: Dict[str, np.ndarray] = {
        name: np.stack([s.indices[name] for s in per_scene], axis=0).astype(np.float32)
        for name in INDICES
    }
    return dates, stacks
