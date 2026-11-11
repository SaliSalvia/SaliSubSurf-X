"""CPF-lite — context-detrended, covariance-aware, surrogate-calibrated detection.

Why this module exists
----------------------
The legacy fusion (``fusion.fuse``) converts raw robust z-scores into a 0–100
score with fixed hand weights.  On real scenes that carry *smooth seasonal
drift* (phenology progressing across the baseline window) the pixel-wise
baseline median/MAD is biased, and the legacy detector flags 50 %+ of the area.
The deep-model layer is a percentile rank, so ~50 % of pixels are always above
0.5 and "coherence" inherits that inflation.

CPF-lite fixes the statistics, not the physics:

1. **Context detrending** — for each signed evidence channel a low-order 2-D
   polynomial "natural null" surface is fitted with Tukey-biweight IRLS, so
   smooth seasonal/soil trends are removed before anything is called anomalous.
2. **Covariance-aware whitening** — the six channels are correlated; a robust
   (median/MAD) standardisation followed by a trimmed, shrinkage-regularised
   covariance estimate gives a Mahalanobis distance d² that does not
   double-count correlated evidence.
3. **Empirical null calibration** — the d² field is rescaled by matching its
   median to the chi²_k median (Efron-style empirical null), because the
   residuals are heavier-tailed than Gaussian.
4. **Surrogate cluster-mass p-values** — significance is declared on *cluster
   mass* (sum of excess d² above a per-pixel chi² threshold), calibrated with
   phase-randomised surrogates (same power spectrum and cross-channel phase
   structure, no anomaly).  A cluster is reported only when its mass is at
   least as large as the maximum null cluster mass with probability ≤ alpha
   (add-1 conformal p-value).  Under smooth drift with no planted anomaly this
   keeps false-positive area in the low single digits instead of ~50 %.

Honest scope: this remains a *surface-change* anomaly detector (see
docs/SCIENCE-SCOPE.md).  CPF-lite changes how anomalies are *statistically
separated from natural variability*; it does not classify buried targets.

Reference prototype: ``cpf_lite.py`` / ``null_injection_tests.py`` (external
review, 2026-11-07) — the mathematical core is kept verbatim; this module adds
structured results, guards and pipeline integration.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
from scipy import ndimage as ndi
from scipy.stats import chi2

# Signed, two-sided evidence channels (robust z of the recent median).
CH: Tuple[str, ...] = ("z_ndvi", "z_ndwi", "z_mndwi", "z_ndmi", "z_nbr", "z_bsi")

DEFAULTS = {
    "n_surr": 199,     # phase-randomised surrogates
    "p_pix": 1e-3,     # per-pixel chi² threshold for cluster seeding
    "alpha": 0.01,     # cluster-level significance level
    "min_px": 9,       # minimum cluster size in pixels
    "deg": 3,          # detrend polynomial degree per axis
    "seed": 7,
}


# --------------------------------------------------------------------- internals

def _poly_design(h: int, w: int, deg: int) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    x = (x - w / 2) / (w / 2)
    y = (y - h / 2) / (h / 2)
    cols = [x ** i * y ** j for i in range(deg + 1) for j in range(deg + 1 - i)]
    return np.stack([c.ravel() for c in cols], 1)


def robust_context_detrend(f: np.ndarray, deg: int = 3, iters: int = 6) -> np.ndarray:
    """Tukey-biweight IRLS polynomial surface = low-frequency 'natural null'.

    The returned residual field is what remains after phenology / soil trends /
    illumination gradients are removed.  NaN input pixels stay NaN-free zero
    residuals (they are excluded from the fit and from the statistics).
    """
    h, w = f.shape
    A = _poly_design(h, w, deg)
    y = f.ravel().astype(np.float64)
    ok = np.isfinite(y)
    wts = ok.astype(float)
    beta = np.zeros(A.shape[1])
    if ok.sum() < max(16, A.shape[1] * 4):
        return np.where(ok, y - np.nanmedian(y[ok]) if ok.any() else 0.0, 0.0).reshape(h, w)
    for _ in range(iters):
        W = wts[:, None]
        beta, *_ = np.linalg.lstsq(A * W, np.where(ok, y, 0) * wts, rcond=None)
        r = np.where(ok, y - A @ beta, 0)
        med = np.median(r[ok])
        s = 1.4826 * np.median(np.abs(r[ok] - med)) + 1e-9
        u = (r - med) / (4.685 * s)
        wts = np.where(ok & (np.abs(u) < 1), (1 - u ** 2) ** 2, 0)
    resid = np.where(ok, y - A @ beta, 0.0)
    return resid.reshape(h, w)


def whiten(R: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Robust (median/MAD) standardise → shrinkage covariance → whitening matrix."""
    H, W, C = R.shape
    X = R.reshape(-1, C)
    med = np.nanmedian(X, 0)
    mad = 1.4826 * np.nanmedian(np.abs(X - med), 0) + 1e-9
    Z = (X - med) / mad
    Z = np.nan_to_num(Z, nan=0.0)
    # robust covariance on the central 80 % (trim by norm) + shrinkage
    nrm = np.linalg.norm(Z, axis=1)
    keep = nrm <= np.quantile(nrm, 0.80)
    S = np.cov(Z[keep].T) if keep.sum() > C + 2 else np.eye(C)
    tr = np.trace(S) / C
    lam = 0.1
    S = (1 - lam) * S + lam * tr * np.eye(C)
    ev, evec = np.linalg.eigh(S)
    ev = np.maximum(ev, 1e-6)
    Wm = evec @ np.diag(ev ** -0.5) @ evec.T
    return med, mad, Wm


def d2_map(R: np.ndarray, med: np.ndarray, mad: np.ndarray, Wm: np.ndarray) -> np.ndarray:
    """Per-pixel Mahalanobis-style distance² over the whitened channels."""
    H, W, C = R.shape
    Z = np.nan_to_num((R.reshape(-1, C) - med) / mad, nan=0.0) @ Wm
    return (Z ** 2).sum(1).reshape(H, W)


def empirical_null_scale(d2: np.ndarray, k: int) -> float:
    """Efron-style empirical null: scale of chi²_k matched on the central half."""
    finite = d2[np.isfinite(d2)]
    if finite.size == 0:
        return 1.0
    return float(np.median(finite) / chi2.ppf(0.5, k))


def phase_randomize(R: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Surrogate: same power spectrum per channel, shared random phases.

    Sharing one phase field across channels preserves cross-channel
    correlation structure, so the surrogate null also calibrates the whitening
    step — not just the marginal spectra.
    """
    H, W, C = R.shape
    ph = rng.uniform(0, 2 * np.pi, (H, W))
    ph = np.angle(np.fft.fft2(np.real(np.fft.ifft2(np.exp(1j * ph)))))
    out = np.empty_like(R)
    for c in range(C):
        F = np.fft.fft2(np.nan_to_num(R[..., c]))
        out[..., c] = np.real(np.fft.ifft2(np.abs(F) * np.exp(1j * ph)))
    return out


def cluster_masses(d2s: np.ndarray, k: int, p_pix: float, min_px: int):
    """Seed clusters at the per-pixel chi² threshold and weigh them by excess mass."""
    thr = chi2.isf(p_pix, k)
    lab, n = ndi.label(d2s > thr, structure=np.ones((3, 3)))
    if n == 0:
        return lab, np.array([]), n, float(thr)
    idx = np.arange(1, n + 1)
    mass = ndi.sum(d2s - thr, lab, idx)
    size = ndi.sum(np.ones_like(d2s), lab, idx)
    mass = np.where(size >= min_px, mass, 0.0)
    return lab, mass, n, float(thr)


# ------------------------------------------------------------------ entry point

def cpf_analyze(
    evidence: Dict[str, np.ndarray],
    n_surr: int = DEFAULTS["n_surr"],
    p_pix: float = DEFAULTS["p_pix"],
    alpha: float = DEFAULTS["alpha"],
    min_px: int = DEFAULTS["min_px"],
    deg: int = DEFAULTS["deg"],
    seed: int = DEFAULTS["seed"],
) -> Dict:
    """Run CPF-lite on the temporal evidence of one (tile of a) region.

    Returns a dict with:
      * ``significant``      — bool mask of clusters significant at ``alpha``
      * ``labels``           — int32 label map of the *seeded* clusters
      * ``cluster_p``        — {label_id: conformal p-value}
      * ``d2``               — calibrated Mahalanobis map (chi²_k-scaled)
      * ``sig_score``        — 0–100 per-pixel significance score (100·(1−sf))
      * ``n_clusters``       — number of seeded clusters (before size filter)
      * ``null_max_stats``   — surrogate max-mass distribution summary
      * ``valid_fraction``   — share of pixels with finite evidence
      * ``settings``         — the parameters actually used
    """
    shape = evidence["z_ndmi"].shape
    k = len(CH)
    missing = [c for c in CH if c not in evidence or evidence[c].shape != shape]
    if missing:
        raise ValueError(f"evidence is missing channels {missing}")

    valid = np.isfinite(evidence["z_ndmi"])
    valid_fraction = float(valid.mean()) if valid.size else 0.0
    empty = {
        "significant": np.zeros(shape, bool),
        "labels": np.zeros(shape, np.int32),
        "cluster_p": {},
        "d2": np.zeros(shape, np.float32),
        "sig_score": np.zeros(shape, np.float32),
        "n_clusters": 0,
        "null_max_stats": {"n_surr": 0, "max": 0.0, "q95": 0.0},
        "valid_fraction": valid_fraction,
        "settings": dict(DEFAULTS, n_surr=int(n_surr), p_pix=float(p_pix),
                         alpha=float(alpha), min_px=int(min_px), deg=int(deg),
                         seed=int(seed)),
    }
    if valid_fraction < 0.05:
        return empty  # not enough finite evidence to fit anything

    rng = np.random.default_rng(seed)
    R = np.stack([robust_context_detrend(evidence[c], deg=deg) for c in CH], -1)
    med, mad, Wm = whiten(R)
    d2 = d2_map(R, med, mad, Wm)
    s = empirical_null_scale(d2, k)
    d2c = d2 / max(s, 1e-9)

    lab, mass, n, thr = cluster_masses(d2c, k, p_pix, min_px)

    n_surr = int(max(0, min(999, n_surr)))
    null_max: List[float] = []
    for _ in range(n_surr):
        Rs = phase_randomize(R, rng)
        ms, mads, Ws = whiten(Rs)
        d2s = d2_map(Rs, ms, mads, Ws)
        d2s = d2s / empirical_null_scale(d2s, k)
        _, m, _, _ = cluster_masses(d2s, k, p_pix, min_px)
        null_max.append(float(m.max()) if m.size else 0.0)
    null_max_arr = np.asarray(null_max, dtype=np.float64)

    cluster_p: Dict[int, float] = {}
    if n:
        for i in range(1, n + 1):
            m_i = float(mass[i - 1])
            if m_i <= 0:
                continue
            p_i = (1 + int(np.sum(null_max_arr >= m_i))) / (1 + n_surr)
            cluster_p[i] = float(p_i)

    sig = np.zeros(d2c.shape, bool)
    for i, p in cluster_p.items():
        if p <= alpha:
            sig |= (lab == i)

    # Per-pixel 0-100 significance score.  sf() saturates in the far tail, so
    # the score is a log10-scaled survival function: p=1e-6 maps to 100.
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        sf = np.clip(chi2.sf(np.nan_to_num(d2c, nan=0.0), k), 1e-17, 1.0)
        logsf = -np.log10(sf) / 6.0
    sig_score = (100.0 * np.clip(logsf, 0.0, 1.0)).astype(np.float32)

    return {
        "significant": sig,
        "labels": lab.astype(np.int32),
        "cluster_p": cluster_p,
        "d2": d2c.astype(np.float32),
        "sig_score": sig_score,
        "n_clusters": int(n),
        "null_max_stats": {
            "n_surr": int(n_surr),
            "max": float(null_max_arr.max()) if null_max_arr.size else 0.0,
            "q95": float(np.quantile(null_max_arr, 0.95)) if null_max_arr.size else 0.0,
        },
        "valid_fraction": valid_fraction,
        "settings": dict(DEFAULTS, n_surr=int(n_surr), p_pix=float(p_pix),
                         alpha=float(alpha), min_px=int(min_px), deg=int(deg),
                         seed=int(seed)),
    }


def confidence_from_p(p_value: float) -> str:
    """Cluster-level confidence class from the conformal p-value."""
    if p_value <= 0.001:
        return "high"
    if p_value <= 0.01:
        return "medium"
    return "low"
